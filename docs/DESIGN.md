# Hard Problems Are Easy to Find

**Design Doc — v0.1 (2026-06-11)**

Status: Draft. Companion docs: [PROBLEMS.md](./PROBLEMS.md) (problem brainstorm), [HARNESSES.md](./HARNESSES.md) (eval harness selection).

## 1. Thesis

Thousands of LLM evals exist, and most are *practical*: SWE-Bench, Terminal-Bench, GPQA, MMLU and descendants. They ask "can the model do useful work?" This project asks a different question:

> **Starting from complexity theory and the formal theory of problem descriptions, it is trivially easy to generate unbounded supplies of problems that are hard — or impossible — for LLMs to solve by "thinking", even when the problems are easy to state, easy to verify, and often easy to solve programmatically.**

This is deliberately *unfair* to the LLM. That's the point. The asymmetry between **generation cost** (cheap), **verification cost** (cheap), and **solution-by-token-prediction cost** (high or unbounded) is a structural fact about computation, not a temporary gap that scaling closes. Some of these problems are hard for humans too (NP-hard instances); others are easy for a human with a pencil or ten lines of Python (maze pathfinding, iterating a logistic map) but resist solution inside a forward pass or even a long chain of thought.

The interesting scientific content is in the *taxonomy of why* problems are hard for LLMs:

1. **Formally hard for everyone** — NP-hard, PSPACE-hard, etc. The LLM fails because everything fails; the question is whether it degrades gracefully (approximation quality, knowing when to give up).
2. **Computationally deep but formally easy** — problems in P that require many serial steps (chaotic dynamics, long iterated computation, big-instance pathfinding). Transformers have bounded serial depth per token; chain-of-thought rents extra depth but pays in tokens, errors compound, and context is finite.
3. **Inverse / search-shaped problems** — argmax of a black-box-ish function, preimage finding, constraint satisfaction. Verification is trivial, search is not; token prediction is a poor search procedure.
4. **Reasoning-internals probes** — problems that target known mechanisms: state tracking, exact arithmetic, parity/counting, compositional depth. These illuminate *what "reasoning" is* in these systems.

**The central experimental move: separating understanding from processing.** Every problem is run under three execution conditions:

- **C0 — pure thinking:** the model answers directly. No code execution.
- **C1 — one shot of code:** the model writes a single program; we execute it (sandboxed, fixed timeout, no feedback); the program's printed output is scored as the answer.
- **C∞ — interactive computation:** the model gets a python tool and may alternate thinking and execution as many times as needed (within a cap) before answering.

The predicted headline result: **LLMs fail at problems ten lines of Python solve exactly — and succeed when allowed to write that code.** That pattern is diagnostic: it shows the failure is not one of *understanding* (the model can formalize the problem perfectly well — C1 proves it) but of *processing* — the serial computation simply cannot run inside token generation. This converts the "unfair benchmark" critique into the finding itself.

Where C1 sits relative to C0 and C∞ is genuinely uncertain and pre-registered ([HYPOTHESES.md](./HYPOTHESES.md)): for cleanly algorithmic problems C1 should land near C∞ (the program is easy to get right first try); for problems requiring tuning, debugging, or search-strategy iteration, C∞ should pull ahead.

**The hybrid conjecture (and the paper's deeper hint).** We conjecture a class of problems where *no single program suffices*: problems that interleave linguistic/world knowledge with heavy combinatorial search (see PROBLEMS.md Category 6 — e.g., crossword-style fill where clue semantics need the model and constraint propagation needs the machine). There, even C∞ may fall short unless the model itself acts as an oracle *inside* the search loop — a paradigm that alternates linguistic thought with computation at fine grain. If that holds, it suggests the current fix (transformers bolted to a REPL) is a workaround, and that the search for foundation-model architectures that natively integrate computation with linguistic reasoning should continue. The paper hints at this; it does not need to prove it.

A secondary thesis: because instances are **procedurally generated with known answers**, this family of evals is immune to training-set contamination and never saturates — difficulty is a knob, not a constant. And we position the empirical work as **in conversation with the expressivity theory** — TC⁰ bounds, CoT-buys-serial-depth theorems, and the RASP-L length-generalization conjecture (Zhou et al. 2024) make quantitative predictions that no one has tested against frontier production models at difficulty-sweep resolution; we will.

## 2. Goals & Deliverables

| Deliverable | Description |
|---|---|
| **Open-source problem sets** | A library of problem *generators* (not static datasets): each emits (text prompt, ground truth / scoring function) pairs with parametric difficulty. Plus pinned, versioned static releases for reproducibility. |
| **Data** | Raw per-sample model transcripts and scores across models and difficulty levels, published (e.g., HuggingFace dataset + repo). |
| **Blog post** | Accessible narrative: "hard problems are easy to find", with the best plots (difficulty-vs-accuracy cliffs). |
| **Academic paper** | Formal treatment: taxonomy of hardness sources, scaling curves vs. difficulty parameters, comparison across model tiers, methodology for contamination-proof procedural evals. |

### Non-goals

- Building a better *practical* benchmark. We are not measuring usefulness.
- Exhaustive model coverage. A handful of well-chosen models across capability tiers suffices.
- A judged/subjective scoring regime. Every Phase 1 family has a mechanical verifier; no LLM-as-judge.

## 3. Anatomy of a Problem

Every problem in the suite is a **generator**, not a dataset:

```
ProblemGenerator(seed, difficulty_params) ->
    instance:
        prompt: str            # full text presentation, incl. answer-format instructions
        answer: Any | None     # ground truth, when one exists
        scorer: (response) -> score   # exact match, numeric tolerance, or verifier
        metadata: {family, difficulty_params, seed, generator_version}
```

Design rules:

1. **Verifiable.** Either a unique ground-truth answer, or a polynomial-time verifier (e.g., "is this a valid 3-coloring?", "what is this tour's length?"). For optimization problems we record the optimum (computed by a classical solver at generation time) or a certified bound.
2. **Parametric difficulty.** Every generator exposes knobs (n, density, horizon, precision) so we can sweep from "trivially easy" to "beyond any model" and plot the cliff. The headline artifact is the **accuracy-vs-difficulty curve**, not a single score.
3. **Contamination-proof.** Instances are sampled fresh from seeds. Published static sets are convenience snapshots; anyone can regenerate disjoint sets.
4. **Format-fault isolation.** Strict but simple answer formats (e.g., "final line: `ANSWER: <comma-separated ints>`"), with a lenient parser, so we measure problem-solving failure, not formatting failure. Parse failures are tracked as a separate category.
5. **Classical baseline.** Each generator ships a reference solver (exact or approximation algorithm) so we can report "lines of Python needed" and solver wall-time alongside model performance — that contrast *is* the paper's punchline.

Scoring modes (per problem family):

- **Binary**: exact answer correct/incorrect (decision problems, unique-answer problems).
- **Gradated**: approximation ratio vs. known optimum (TSP tour length / optimal length), trajectory divergence time (chaotic systems), distance metrics (inverse problems).
- **Calibration** (stretch): does the model *know* it can't solve it, or does it confabulate confidently? Track stated confidence / refusal behavior.

See [PROBLEMS.md](./PROBLEMS.md) for the full brainstorm and the shortlist for Phase 1.

## 4. Evaluation Setup

### Models

(Landscape as of June 2026 — verify at run time.)

- **Development / bulk runs (fast & cheap):** Claude Haiku 4.5 ($1/$5 per Mtok) as the primary workhorse; optionally Gemini 3.1 Flash-Lite ($0.25/$1.50) or GPT-5.4 Nano ($0.20/$1.25) for breadth at the cheap tier.
- **Frontier tier (headline claims):** Claude Opus 4.8, GPT-5.5, Gemini 3.1 Pro — the current three-way frontier. The paper's claim "even cutting-edge models fall off the cliff, just at slightly larger n" requires at least one or two of these, run on a smaller instance budget.
- **Open-weight (optional breadth):** DeepSeek V4-Pro or Kimi K2.6 for an open-model data point.

Run conditions to control and report: **execution condition (C0 / C1 / C∞ — the primary axis, see §1)**, reasoning/thinking budget (off / default / max — does extended thinking move the cliff or just delay it?), temperature (0 where supported), max output tokens, model snapshot IDs pinned.

C1 implementation note: no agent loop required — the model's response *is* a program; the harness extracts it, executes it in a sandbox (fixed timeout, no network), and feeds stdout through the same parser/scorer as a chat answer. C∞ uses the harness's tool-calling loop with a sandboxed python tool and a capped number of executions. All three conditions funnel into identical scoring, so curves are directly comparable.

**Phase 1 budget: ~$50** (decided). Envelope at Haiku 4.5 prices: 6 families × 5 difficulty levels × 30 instances × 3 conditions × ~2k tokens ≈ $30–45, leaving headroom for calibration runs. Frontier-tier model set and budget: **deferred until Phase 1 results are in** (decided).

### Harness

Decision deferred to [HARNESSES.md](./HARNESSES.md). Requirements:

- Programmatic (Python) task definition — our datasets are generated, not loaded.
- Arbitrary-Python custom scorers (verifiers, approximation ratios).
- API-model support across Anthropic/OpenAI/Google with concurrency, retries, caching.
- Per-sample structured logs exportable to pandas for analysis.
- Reasoning-budget configuration per run.

Leading candidates: Inspect AI, lm-evaluation-harness, lighteval, promptfoo, or a deliberately thin custom harness (~500 lines). Evaluation in progress.

### Statistics & analysis

- ≥ 30–100 instances per (family × difficulty level × model) cell for usable confidence intervals; binomial CIs on accuracy, bootstrap for gradated scores.
- Primary plots: accuracy vs. difficulty parameter (per model, per thinking budget); tokens-spent vs. difficulty; approximation ratio vs. difficulty.
- Cost model per run published up front (instances × models × tokens) so budget stays controlled.

## 5. Risks & Open Questions

- **"Unfairness" critique:** reviewers may say "of course LLMs can't do NP-hard search". Mitigation: that's the framing, stated explicitly; the contribution is the taxonomy, the cliff measurements, and the contamination-proof methodology — plus the *category-2* problems (easy in P, still failed) which are genuinely surprising to many readers.
- ~~Tool-use rebuttal~~ — resolved by design: the C0/C1/C∞ contrast *is* the experiment, not a rebuttal to absorb. Remaining risk: sandbox/timeout choices for C1/C∞ become the new attack surface (e.g., "the timeout was too short for the solver"). Mitigation: generous timeouts, published verbatim, sized so the reference solver finishes with 100× margin.
- **Prior work overlap:** there is existing literature (e.g., algorithmic reasoning benchmarks, "faith and fate"-style compositional studies, planning benchmarks). A related-work pass is required early to position the contribution. (Open task.)
- **Prompt sensitivity:** hardness claims must survive prompt variations; include a prompt-robustness check on a subset.
- **Scoring optimization problems without certified optima** at large n (where exact solvers time out): use bounds, or restrict claims to verifiable regimes.
- **Cost control** for frontier-tier runs with max thinking budgets (output tokens at $25–30/Mtok dominate).

## 6. Phasing

### Phase 0 — Design & groundwork (this phase)

- Design docs (this doc, PROBLEMS.md, HARNESSES.md). ✅ in progress
- Related-work survey (subagent task): what exists in algorithmic/complexity-flavored LLM evals; sharpen the novelty claim.
- Choose harness; choose Phase 1 problem shortlist (3–5 families spanning the taxonomy).

**Exit criteria:** harness chosen, shortlist fixed, cost estimate for Phase 1 approved.

### Phase 1 — MVP: generators + cheap-model runs

- Repo scaffolding: generator interface, reference solvers, scorers, tests (see [ARCHITECTURE.md](./ARCHITECTURE.md)).
- Implement the 6 shortlisted families (decided: all 6).
- Wire up Inspect AI; run difficulty sweeps against **Claude Haiku 4.5** under all three execution conditions (C0/C1/C∞), within the ~$50 budget.
- First plots: do we see clean cliffs in C0, and does C1 erase them? Where does C1 land relative to C∞ (H5)? Iterate on difficulty knobs and answer-format robustness.
- Predictions pre-registered in [HYPOTHESES.md](./HYPOTHESES.md) **before** the first full sweep.

**Exit criteria:** end-to-end pipeline produces accuracy-vs-difficulty curves for ≥3 families with tight CIs; per-sample data persisted and re-loadable.

### Phase 2 — Breadth: more problems, more models

- Expand to ~10–15 problem families covering all four taxonomy categories.
- Add frontier tier (Opus 4.8, GPT-5.5, and/or Gemini 3.1 Pro) on calibrated instance budgets.
- Thinking-budget ablation (off/default/max) on a subset.
- Optional: tool-use ablation, open-weight model, calibration scoring.

**Exit criteria:** full results matrix; cliffs measured for frontier models; data frozen and versioned.

### Phase 3 — Open-source release + blog post

- Clean up and publish the generator library (pip-installable, documented, with pinned static sets v1.0).
- Publish run data (HF dataset or similar).
- Blog post: narrative + best 4–6 plots. Aim for the "easy to state, easy to check, impossible to think your way through" hook.

**Exit criteria:** repo public, data public, post published.

### Phase 4 — Paper

- Formal write-up: taxonomy, methodology, results, related work, limitations.
- Likely venue type: ML conference benchmark/dataset track or workshop first (decision deferred).
- Extra rigor passes: prompt-robustness study, statistical review, reproduction-from-scratch run using only the public repo.

**Exit criteria:** submitted preprint (arXiv) + venue submission.

### Rough sequencing note

Phases 1→2 are strictly sequential; Phase 3 (release/blog) can overlap with late Phase 2; Phase 4 starts once the data freezes. The blog post intentionally precedes the paper — it derisks the narrative and surfaces critiques cheaply.
