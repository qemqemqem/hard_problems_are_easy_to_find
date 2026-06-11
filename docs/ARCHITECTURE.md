# ARCHITECTURE — How to Build Problem Sets of This Type

**Companion to [DESIGN.md](./DESIGN.md) and [PROBLEMS.md](./PROBLEMS.md). Status: v1.0 — this is the implementation contract. Opinionated by design.**

This doc specifies how a problem family is built, tested, and shipped. It is written for implementers (human or agent). Deviations require editing this doc first.

## 1. Design goals, in priority order

1. **Trustworthy ground truth.** A benchmark with wrong answers is worse than no benchmark. Every design decision below serves verifiability first.
2. **Instances are data, text is a view.** A problem instance is a plain data object (JSON-serializable). Rendering to prompt text is a separate, swappable step. This is what makes presentation ablations, code-condition reuse, and downstream analysis possible.
3. **Determinism.** `generate(seed, **knobs)` is a pure function. Same seed + knobs + generator version ⇒ byte-identical instance, forever, on any machine.
4. **One scoring funnel.** Chat answers (C0), program stdout (C1), and final answers after tool use (C∞) all flow through the *same* parse → score path. Conditions stay comparable because scoring is condition-blind.
5. **The harness is a guest.** Core package imports nothing from Inspect AI (or any harness). A thin adapter module maps families onto the harness. If the harness changes, families don't.

### Anti-goals

- No numpy/scipy/networkx in core families. **Stdlib only.** Rationale: exact, platform-independent semantics (no BLAS nondeterminism), trivial install, and reference solvers stay legible — they are part of the paper's argument ("ten lines of Python").
- No cleverness in reference solvers. Brute force with memoization beats an elegant algorithm we can't trust. Solvers run at *generation time*, offline; milliseconds don't matter, correctness does.
- No LLM-judge scoring anywhere in Phase 1.

## 2. Core abstractions

Package: `hard_problems` (src layout). One module per family under `hard_problems/families/`.

```python
@dataclass(frozen=True)
class Instance:
    family: str               # family name, e.g. "tsp"
    family_version: str       # generator version, e.g. "1.0"
    seed: int
    difficulty: dict          # knob values, e.g. {"n": 12}
    data: dict                # the problem itself, JSON-safe (coords, clauses, grid...)
    answer: Any               # ground truth (or None if only verifier-checkable)
    aux: dict                 # solver artifacts: optimum value, certificate, stats

@dataclass(frozen=True)
class Score:
    value: float              # in [0, 1]; 1.0 = perfect
    label: str                # "optimal" | "valid_suboptimal" | "invalid" | "incorrect" | "correct" | "parse_error"
    correct: bool             # headline binary (family defines the threshold)
    detail: dict              # e.g. {"ratio": 1.23, "tour_len": 512}

class Family(ABC):
    name: str
    version: str
    difficulty_params: dict[str, list]    # knob -> default sweep values

    def generate(self, seed, **difficulty) -> Instance
    def render(self, instance) -> str       # full prompt incl. answer-format instructions
    def parse(self, response: str) -> Any   # lenient; raises ParseError
    def score(self, instance, parsed) -> Score
    def solve(self, instance) -> Any        # reference solver -> answer in parse() output format
```

Plus `Family.score_response(instance, response)` (provided by the base class): catches `ParseError` → `Score(0.0, "parse_error", False)`. Parse failures are *tracked, never crash*.

### Contracts and invariants (enforced by tests)

- **I1 Determinism:** `generate(s, **d) == generate(s, **d)`; different seeds ⇒ different instances (no degenerate constant generators).
- **I2 Round-trip:** `Instance.from_json(inst.to_json()) == inst`.
- **I3 Self-consistency:** `score(inst, parse(format(solve(inst))))` is perfect (value 1.0). The reference solution, rendered the way we ask the model to render it, must score perfectly. This single test catches most scorer/parser/renderer bugs.
- **I4 Verifier soundness:** corrupted answers (mutated certificate, off-by-one path, wrong digit) score < 1.0 with the right label. Test by *systematic corruption*, not just random wrong answers.
- **I5 Difficulty monotonicity (weak):** the knob actually controls hardness by some objective proxy (search-space size, optimal path length, steps k). Smoke-tested, not proven.
- **I6 No global state:** `random.Random(seed)` instances only; never the module-level `random`. No reliance on dict iteration tricks, `hash()` randomization, or float platform quirks (stick to operations with exact IEEE-754 float64 semantics, or integers/fractions).

### Answer-format convention

Every prompt ends with explicit format instructions and every response is expected to contain a final line:

```
ANSWER: <payload>
```

`hard_problems.core.extract_answer_line()` implements the shared lenient extraction (last `ANSWER:` wins; tolerate markdown, whitespace, code fences). Families parse only the payload. C1 programs are instructed to `print("ANSWER: ...")` — same funnel (goal 4).

## 3. What makes a family *good* (admission criteria)

A family ships only if:

1. **Known-hard sampling.** NP-hard ≠ hard on average. The generator must sample from distributions with documented hardness: 3-SAT at α≈4.27, mazes with long shortest paths (reject goal-adjacent starts), TSP with uniform random points (and, later, adversarial layouts). Each module documents *why* its distribution is hard and cites the source if there is one.
2. **Certified ground truth.** Exact solver output, or a certificate-checkable criterion. For optimization at sizes where exact solving is infeasible, the generator either doesn't go there or stores certified bounds — never "probably optimal".
3. **Rejection rules documented.** Degenerate-instance filters (trivially satisfiable, duplicate points, start==goal) are part of the generator spec, implemented and tested.
4. **A legible reference solver.** Ideally short enough to display in the paper. It defines the "ten lines of Python" contrast and produces `aux` metadata (optimum, certificate).
5. **A scoring story that degrades gracefully** where the problem allows (ratio, digits, divergence step) — binary only when the problem is genuinely binary.

## 4. Repository layout

```
pyproject.toml             # stdlib-only core; dev extra: pytest
src/hard_problems/
  core.py                  # Instance, Score, Family, ParseError, extract_answer_line, get_family
  families/
    __init__.py            # lazy registry: get_family("tsp") imports families.tsp, returns FAMILY
    tsp.py  maze.py  sat.py  argmax.py  chaos.py  automata.py
  adapters/
    inspect_ai.py          # Phase 1: Family -> Inspect Task/scorer mapping (the ONLY file that imports inspect_ai)
tests/
  test_core.py
  families/test_<family>.py
docs/                      # these design docs
```

Each family module exposes a single `FAMILY: Family` singleton. The registry resolves names by import (`hard_problems.families.<name>`), so **family modules never edit shared files** — modules are independently developable and reviewable (this is also what makes parallel implementation by multiple agents safe).

## 5. Testing doctrine

Per family, `tests/families/test_<name>.py` must cover, at minimum:

| Test | Invariant |
|---|---|
| determinism | I1 |
| json round-trip | I2 |
| solver-vs-brute-force cross-check on small instances | ground truth (two independent implementations agree; brute force lives in the test file) |
| reference solution scores perfect via full render→parse→score loop | I3 |
| corrupted-answer suite (≥3 corruption modes) | I4 |
| garbage responses (empty, prose, malformed) → parse_error, no exception | robustness |
| rejection rules fire | admission criterion 3 |
| difficulty smoke test | I5 |

Plus golden-instance snapshots: one serialized instance per difficulty level committed to the repo; tests regenerate from seed and compare. This pins generator behavior across refactors and Python versions — any intentional change bumps `family_version` and regenerates goldens (versioning policy: goldens never change silently).

Coverage target: the scorer and generator are the trust kernel — they get exhaustive tests; renderers get I3 + snapshot tests.

## 6. Difficulty calibration protocol (pre-run, per family)

1. Pick the default sweep from `difficulty_params` (5 levels spanning "trivial" to "expected-hopeless" based on theory/solver cost).
2. Run ~10 instances/level on Haiku 4.5, C0, default thinking. 
3. Adjust the sweep so observed accuracy spans ≳90% → ≲10% across levels; re-run once.
4. Freeze the sweep in the family module (`difficulty_params`) and record the calibration run in the experiment log. Calibration spend comes out of the $50 budget envelope (~$5 total).

### Implementation notes for the calibration pass (from family implementers, 2026-06-11)

- **sat:** at n≤24, the empirical SAT/UNSAT split is ~73% SAT at ratio 4.27 — the 50/50 crossover sits above 4.27 at small n (finite-size effect). If balanced labels matter, sweep ratio toward ~4.5–5; also a chance to *measure* the finite-size shift.
- **tsp:** n=14 may still be too easy for approximation-ratio contrast; n=16 is available within the Held-Karp cap.
- **maze:** size 32 yields ~70+ move optimal paths — likely already hopeless at C0; the informative band is probably sizes 6–16. The "path ≥ size" rejection floor is vacuous (any S→G path is ≥ 2(size−1)); connectivity is the binding filter.
- **chaos:** logistic perturbations only reach ~6e-3 by k=16, so digit-partial credit persists deep into the sweep; k=32 likely saturates C0. Hénon divergence rejection never fires from the IC box (5000-seed scan) — predicate is tested synthetically.
- **automata:** width 40 × k=32 is probably hopeless at C0. The rule knob (90 = linear/XOR vs 110 = universal, 30 = chaotic) gives a structure-vs-difficulty contrast worth one calibration sweep of its own.

## 7. Execution-condition plumbing (Phase 1 scope)

- **C0:** adapter renders prompt → `generate()` → `score_response`.
- **C1:** prompt prefixed with the standard C1 preamble ("respond with a single self-contained Python program; its stdout must end with `ANSWER: ...`"). Scorer extracts the last code block, runs it via `subprocess` in the Inspect sandbox (timeout 60s, no network, memory-capped), then `score_response(stdout)`. Timeout sized ≥100× reference-solver wall time, published.
- **C∞:** Inspect react-style solver with `python()` tool, execution cap (default 10 calls), then a forced final answer. Tool transcripts retained for the alternation-pattern analysis.

The condition logic lives entirely in `adapters/inspect_ai.py` + run configs. Families don't know conditions exist.

## 8. Things deliberately left out (for now)

- Static dataset releases (Phase 3: pinned seeds + goldens make this a `for` loop).
- Multi-prompt/presentation ablations (post-MVP; the renderer seam is where they'll plug in).
- Adversarial-instance generators (Category 4.4) and hybrid families (Category 6) — Phase 2; they will stress the `aux`/oracle design and may add a `Family.oracle()` hook. Don't build the hook until they need it.
