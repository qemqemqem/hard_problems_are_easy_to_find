"""Inspect AI adapter: maps hard_problems families onto Inspect tasks.

This is the ONLY module in the package that imports inspect_ai
(docs/ARCHITECTURE.md goal 5). Conditions C0/C1/C-inf live here and in run
configs; families know nothing about them.

Conditions:
  C0     pure chat; render -> generate() -> score_response(completion).
  C1     model emits one self-contained Python program; we extract the last
         code block, run it in the sandbox, and score_response(stdout).
  C-inf  model gets an interactive python() tool with a capped call budget,
         then must end with a normal chat message holding the ANSWER line;
         scored by the unchanged family_scorer() funnel.

Oracle mode (answer revealed in-prompt) validates the render -> model ->
parse -> score loop end-to-end; expected ~100%.
"""

from __future__ import annotations

import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageUser
from inspect_ai.scorer import CORRECT, INCORRECT, Score as InspectScore, Target, accuracy, mean, scorer, stderr
from inspect_ai.solver import Generate, Solver, TaskState, generate, solver
from inspect_ai.tool import python
from inspect_ai.util import OutputLimitExceededError, apply_limits, message_limit, sandbox

from hard_problems.core import get_family

ORACLE_PREAMBLE = (
    "\n\nNOTE: For pipeline-validation purposes, the correct answer is provided"
    " below. Reply with exactly this answer line and nothing else.\n{answer_line}\n"
)

C1_PREAMBLE = (
    "\n\nIMPORTANT — PROGRAM CONDITION: Do not answer in prose. Respond with"
    " exactly ONE self-contained Python 3 program inside a fenced code block"
    " (```python ... ```). The program must use only the standard library,"
    " must not read input (no input(), no argv, no files), and must print"
    " exactly one final line of the form:\n\n"
    "ANSWER: <payload>\n\n"
    "where <payload> follows the answer-format instructions given in the"
    " problem statement above. Your program's printed output is what gets"
    " graded — the chat text outside the code block is ignored."
)

CINF_PREAMBLE = (
    "\n\nTOOLS: You have a `python` tool that executes a Python 3 program in a"
    " sandbox (standard library only, no network) and returns its output."
    " Each call is independent — no state persists between calls, and you"
    " must print() anything you want to see. You may call it as many times"
    " as you need within the call budget. When you are confident, finish"
    " with a normal chat message (not a tool call) whose final line is"
    " 'ANSWER: <payload>' per the answer-format instructions above."
)

# Final nudge for C-inf when the tool loop ends without an ANSWER line
# (call budget exhausted or model stopped mid-stride).
CINF_FINAL_PROMPT = (
    "Your tool-call budget is exhausted. Based on the work above, reply now"
    " with your final answer as a single line 'ANSWER: <payload>' per the"
    " answer-format instructions. Do not call any more tools."
)

# C1/C-inf run model-written code: isolate it. Plain python image, no
# network, memory-capped (sandbox/compose.yaml at repo root). Resolved to an
# absolute path because Inspect resolves relative sandbox configs against the
# task file's directory, not the repo root.
SANDBOX = ("docker", str(Path(__file__).resolve().parents[3] / "sandbox" / "compose.yaml"))

# Fenced code block: optional language tag after the opening fence, lazy body.
_CODE_BLOCK_RE = re.compile(r"```[ \t]*[\w+-]*[ \t]*\n(.*?)```", re.DOTALL)

# Bare-code heuristic: a line opening with a typical Python construct.
_BARE_CODE_RE = re.compile(r"^\s*(import |from \S+ import|def |class |print\()", re.MULTILINE)


def extract_python_program(response: str) -> str | None:
    """Extract the model's program from a chat response (C1 condition).

    The LAST non-empty fenced block wins (models often emit scratch blocks
    before the final program). With no fences, a response that looks like
    bare Python is taken whole. Lenient by design — same philosophy as
    extract_answer_line.
    """
    blocks = [b.strip() for b in _CODE_BLOCK_RE.findall(response) if b.strip()]
    if blocks:
        return blocks[-1]
    text = response.strip()
    if text and _BARE_CODE_RE.search(text):
        return text
    return None


def family_samples(
    family_name: str,
    *,
    seeds: list[int],
    difficulty: dict,
    oracle: bool = False,
    preamble: str = "",
) -> list[Sample]:
    """Generate Inspect Samples for one family at one difficulty point.

    preamble: condition-specific text appended after the rendered prompt
    (C1/C-inf instructions). Empty for C0.
    """
    fam = get_family(family_name)
    samples = []
    for seed in seeds:
        inst = fam.generate(seed, **difficulty)
        prompt = fam.render(inst)
        if preamble:
            prompt += preamble
        if oracle:
            answer_line = fam.format_answer(fam.solve(inst))
            prompt += ORACLE_PREAMBLE.format(answer_line=answer_line)
        diff_id = "_".join(f"{k}{v}" for k, v in sorted(difficulty.items()))
        samples.append(
            Sample(
                id=f"{family_name}_{diff_id}_s{seed}",
                input=prompt,
                target="",  # ground truth lives in the instance JSON, not the target
                metadata={
                    "family": family_name,
                    "instance_json": inst.to_json(),
                    "oracle": oracle,
                },
            )
        )
    return samples


def _sweep_samples(spec: str, preamble: str = "") -> list[Sample]:
    """Load a sweep spec JSON: {family: [{"difficulty": {...}, "seeds": [...]}, ...]}."""
    import json as _json

    with open(spec) as f:
        plan: dict[str, list[dict]] = _json.load(f)
    samples: list[Sample] = []
    for family_name, levels in plan.items():
        for level in levels:
            samples.extend(
                family_samples(
                    family_name,
                    seeds=level["seeds"],
                    difficulty=level["difficulty"],
                    preamble=preamble,
                )
            )
    return samples


def _smoke_samples(n: int, oracle: bool = False, preamble: str = "") -> list[Sample]:
    """n easiest-level instances per family."""
    from hard_problems.core import KNOWN_FAMILIES

    samples: list[Sample] = []
    for name in KNOWN_FAMILIES:
        fam = get_family(name)
        easiest = {k: v[0] for k, v in fam.difficulty_params.items()}
        samples.extend(
            family_samples(
                name,
                seeds=list(range(1, n + 1)),
                difficulty=easiest,
                oracle=oracle,
                preamble=preamble,
            )
        )
    return samples


@scorer(metrics=[accuracy(), stderr(), mean()])
def family_scorer():
    """Single scoring funnel: delegates to Family.score_response.

    Inspect score value is the family's gradated value in [0,1]; the
    CORRECT/INCORRECT answer field carries the headline binary; label and
    detail land in metadata for analysis.
    """

    async def score_fn(state: TaskState, target: Target) -> InspectScore:
        from hard_problems.core import Instance

        fam = get_family(state.metadata["family"])
        inst = Instance.from_json(state.metadata["instance_json"])
        s = fam.score_response(inst, state.output.completion)
        return InspectScore(
            value=s.value,
            answer=CORRECT if s.correct else INCORRECT,
            explanation=s.label,
            # stop_reason distinguishes token exhaustion from genuine failure
            metadata={
                "label": s.label,
                "correct": s.correct,
                "stop_reason": str(state.output.stop_reason),
                **s.detail,
            },
        )

    return score_fn


@scorer(metrics=[accuracy(), stderr(), mean()])
def c1_scorer(timeout: int = 60):
    """C1 scorer: extract the program, run it in the sandbox, score its stdout.

    Crash/timeout policy: a program may print its ANSWER line and then crash,
    so on nonzero exit we still feed stdout through score_response (the exec
    failure is recorded in metadata). On timeout or output-limit blowup there
    is no stdout to salvage (exec raises without a result), so those score
    0.0 with labels "exec_timeout" / "output_limit".
    """

    async def score_fn(state: TaskState, target: Target) -> InspectScore:
        from hard_problems.core import Instance

        fam = get_family(state.metadata["family"])
        inst = Instance.from_json(state.metadata["instance_json"])

        meta: dict = {"stop_reason": str(state.output.stop_reason)}

        code = extract_python_program(state.output.completion)
        meta["program_found"] = code is not None
        if code is None:
            return InspectScore(
                value=0.0, answer=INCORRECT, explanation="no_program", metadata=meta
            )

        # Write-then-run rather than `python3 -c`: avoids argv-size limits and
        # keeps tracebacks readable (file/line refer to solution.py).
        # timeout_retry=False — rerunning a deterministic over-budget program
        # would just triple the wall time for the same outcome.
        try:
            await sandbox().write_file("solution.py", code)
            result = await sandbox().exec(
                ["python3", "solution.py"], timeout=timeout, timeout_retry=False
            )
        except TimeoutError:
            meta.update(exec_ok=False, exec_timeout=True)
            return InspectScore(
                value=0.0, answer=INCORRECT, explanation="exec_timeout", metadata=meta
            )
        except OutputLimitExceededError as e:
            meta.update(exec_ok=False, output_limit_exceeded=True, error=str(e)[:2000])
            return InspectScore(
                value=0.0, answer=INCORRECT, explanation="output_limit", metadata=meta
            )

        meta.update(
            exec_ok=result.success,
            exec_timeout=False,
            returncode=result.returncode,
            stderr=result.stderr[:2000],
            stdout_len=len(result.stdout),
        )
        s = fam.score_response(inst, result.stdout)
        return InspectScore(
            value=s.value,
            answer=CORRECT if s.correct else INCORRECT,
            explanation=s.label,
            metadata={"label": s.label, "correct": s.correct, **s.detail, **meta},
        )

    return score_fn


@solver
def cinf_solver(max_tool_calls: int = 10, exec_timeout: int = 30) -> Solver:
    """C-inf solver: python() tool loop with a capped call budget.

    Cap semantics: a scoped message_limit of len(messages) + 2*max_tool_calls
    around the tool loop. Each python round costs 2 messages (assistant tool
    call + tool result), so this allows ~max_tool_calls executions; a model
    issuing parallel tool calls in one turn spends budget faster (each result
    message counts). When the limit trips, Inspect raises inside generate();
    we catch it via apply_limits(catch_errors=True) and fall through.

    If the loop ends without an ANSWER line in the completion (budget
    exhausted, or model stopped on a tool turn), we strip the tools and force
    one final plain-chat answer so family_scorer() sees a normal completion.
    Tool transcripts stay in state.messages -> retained in the eval log for
    alternation-pattern analysis.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.tools = [python(timeout=exec_timeout)]
        limit = message_limit(len(state.messages) + 2 * max_tool_calls)
        with apply_limits([limit], catch_errors=True) as scope:
            state = await generate(state, tool_calls="loop")
        if scope.limit_error is not None or "ANSWER" not in state.output.completion.upper():
            state.tools = []
            state.messages.append(ChatMessageUser(content=CINF_FINAL_PROMPT))
            state = await generate(state, tool_calls="none")
        return state

    return solve


@task
def sweep(spec: str) -> Task:
    """Difficulty-calibration sweep, condition C0.

    spec: path to a JSON file: {family_name: [{"difficulty": {...}, "seeds": [...]}, ...]}
    All levels run in one eval for batching efficiency; analysis groups by sample id.
    """
    return Task(
        dataset=MemoryDataset(_sweep_samples(spec)),
        solver=generate(),
        scorer=family_scorer(),
    )


@task
def smoke_c0(n: int = 3, oracle: bool = False) -> Task:
    """Live smoke test: n easiest-level instances per family, condition C0.

    oracle=True appends the correct answer to every prompt; scores should be
    ~100% (validates parse/score plumbing, not the model).
    """
    return Task(
        dataset=MemoryDataset(_smoke_samples(n, oracle=oracle)),
        solver=generate(),
        scorer=family_scorer(),
    )


@task
def sweep_c1(spec: str, timeout: int = 60) -> Task:
    """Difficulty sweep, condition C1 (single program run, scored on stdout)."""
    return Task(
        dataset=MemoryDataset(_sweep_samples(spec, preamble=C1_PREAMBLE)),
        solver=generate(),
        scorer=c1_scorer(timeout=timeout),
        sandbox=SANDBOX,
    )


@task
def smoke_c1(n: int = 1, timeout: int = 60) -> Task:
    """Smoke test, condition C1: n easiest-level instances per family."""
    return Task(
        dataset=MemoryDataset(_smoke_samples(n, preamble=C1_PREAMBLE)),
        solver=generate(),
        scorer=c1_scorer(timeout=timeout),
        sandbox=SANDBOX,
    )


@task
def sweep_cinf(spec: str, max_tool_calls: int = 10, exec_timeout: int = 30) -> Task:
    """Difficulty sweep, condition C-inf (interactive python tool, capped)."""
    return Task(
        dataset=MemoryDataset(_sweep_samples(spec, preamble=CINF_PREAMBLE)),
        solver=cinf_solver(max_tool_calls=max_tool_calls, exec_timeout=exec_timeout),
        scorer=family_scorer(),
        sandbox=SANDBOX,
    )


@task
def smoke_cinf(n: int = 1, max_tool_calls: int = 10, exec_timeout: int = 30) -> Task:
    """Smoke test, condition C-inf: n easiest-level instances per family."""
    return Task(
        dataset=MemoryDataset(_smoke_samples(n, preamble=CINF_PREAMBLE)),
        solver=cinf_solver(max_tool_calls=max_tool_calls, exec_timeout=exec_timeout),
        scorer=family_scorer(),
        sandbox=SANDBOX,
    )
