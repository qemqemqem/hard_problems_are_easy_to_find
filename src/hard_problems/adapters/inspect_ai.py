"""Inspect AI adapter: maps hard_problems families onto Inspect tasks.

This is the ONLY module in the package that imports inspect_ai
(docs/ARCHITECTURE.md goal 5). Conditions C0/C1/C-inf live here and in run
configs; families know nothing about them.

Currently implemented: C0 (pure thinking) and oracle mode (answer revealed
in-prompt, used to validate the render -> model -> parse -> score loop
end-to-end; expected ~100%).
"""

from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import CORRECT, INCORRECT, Score as InspectScore, Target, accuracy, mean, scorer, stderr
from inspect_ai.solver import TaskState, generate

from hard_problems.core import get_family

ORACLE_PREAMBLE = (
    "\n\nNOTE: For pipeline-validation purposes, the correct answer is provided"
    " below. Reply with exactly this answer line and nothing else.\n{answer_line}\n"
)


def family_samples(
    family_name: str,
    *,
    seeds: list[int],
    difficulty: dict,
    oracle: bool = False,
) -> list[Sample]:
    """Generate Inspect Samples for one family at one difficulty point."""
    fam = get_family(family_name)
    samples = []
    for seed in seeds:
        inst = fam.generate(seed, **difficulty)
        prompt = fam.render(inst)
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
            metadata={"label": s.label, "correct": s.correct, **s.detail},
        )

    return score_fn


@task
def sweep(spec: str) -> Task:
    """Difficulty-calibration sweep, condition C0.

    spec: path to a JSON file: {family_name: [{"difficulty": {...}, "seeds": [...]}, ...]}
    All levels run in one eval for batching efficiency; analysis groups by sample id.
    """
    import json as _json

    with open(spec) as f:
        plan: dict[str, list[dict]] = _json.load(f)
    samples: list[Sample] = []
    for family_name, levels in plan.items():
        for level in levels:
            samples.extend(
                family_samples(
                    family_name, seeds=level["seeds"], difficulty=level["difficulty"]
                )
            )
    return Task(dataset=MemoryDataset(samples), solver=generate(), scorer=family_scorer())


@task
def smoke_c0(n: int = 3, oracle: bool = False) -> Task:
    """Live smoke test: n easiest-level instances per family, condition C0.

    oracle=True appends the correct answer to every prompt; scores should be
    ~100% (validates parse/score plumbing, not the model).
    """
    samples: list[Sample] = []
    from hard_problems.core import KNOWN_FAMILIES

    for name in KNOWN_FAMILIES:
        fam = get_family(name)
        easiest = {k: v[0] for k, v in fam.difficulty_params.items()}
        samples.extend(
            family_samples(name, seeds=list(range(1, n + 1)), difficulty=easiest, oracle=oracle)
        )
    return Task(dataset=MemoryDataset(samples), solver=generate(), scorer=family_scorer())
