# A1 — Which Training Factor Buys Cliff Position?

**Status: design doc v0.1, 2026-06-12. Hypothesis owner: Andrew (HYPOTHESES.md A1). Companions: A1_SCALING_FEASIBILITY.md (model-suite inventory and budgets — verdict: inference-only, no training needed; Gemstones/Pythia/DataDecide dissociate all four factors, gated on a cheap floor pilot) and A1_INFERENCE_PLAN.md (engineering plan — verdict: self-hosted vLLM via Inspect's `vllm-completions` provider on one rented GPU; pilot $2–5, full sweep $10–35; no second harness needed).**

## 1. The hypothesis

Experiment 1 located C0 cliffs for one model. A1 asks what moves them. Across models, cliff positions presumably improve with scale — but "scale" bundles at least four factors: **parameter count**, **depth in layers**, **training-data quantity**, and **training-data quality**. A1 conjectures these dissociate: some factor(s) move the cliffs and some don't, and the interesting result is the dissociation itself. Candidate headline: *"parameter count helps, but more training data doesn't."* A result of this shape would show that some axis of training improvement — one the field spends heavily on — fails to pay out on problems that are trivial to generate and verify.

This is the project's bridge from benchmarking to *mechanism*: Experiment 1 says the cliffs exist; A3 says where code can't rescue them; A1 says what kind of scaling, if any, removes them — which is evidence about whether they are capability gaps (training fixes them) or architecture signatures (training moves constants, not laws — H12's claim, now testable at the factor level).

## 2. Theoretical stakes, per factor

The circuit-complexity frame (LITERATURE.md §1) makes differentiated predictions, which is what makes A1 more than a fishing expedition:

- **Depth in layers.** A forward pass is a constant-depth circuit; each layer buys a constant number of sequential composition steps. For *serial* families (automata, chaos — where C0 accuracy looks like per-step fidelity p^k), theory points at depth as the binding factor: more layers should move serial cliffs more than equivalent parameters spent on width. This is the sharpest registrable sub-prediction.
- **Parameter count at fixed depth (width).** Buys representation capacity and (empirically) better per-step fidelity p, but no new serial steps. Should help breadth-loaded families (argmax-style aggregation) more than depth-loaded ones.
- **Data quantity.** Buys better heuristics, memorized schemata, and format competence — should move *easy-level* accuracy and possibly per-step fidelity, but has no mechanism for adding serial computation. The conjectured non-payer.
- **Data quality.** Same mechanism class as quantity (better p per token spent), plausibly bigger effect per token; no serial mechanism either. Caveat: heavily curated/synthetic recipes (textbook-style) may specifically rehearse multi-step procedures, which could mimic a depth effect — worth keeping the families' counterfactual variants (DIMENSIONS.md §5) on hand to separate procedure-memorization from computation.

Caveat to register honestly: with chain-of-thought, the model can externalize serial steps into tokens, which weakens the pure depth argument (CoT rents depth). The depth prediction therefore applies most cleanly to the within-forward-pass regime — short outputs, or the easiest levels where models answer without long derivations — and the analysis should condition on output length.

## 3. Design

### Outcome measures

Per model × family: **cliff position** (knob value at 50% accuracy, logistic fit over the 10-level grid from Experiment 1, extended downward with easier levels — see floor problem below), plus the functional-form parameters where they exist: per-step fidelity p (automata, H2), digit-horizon k* (chaos, H3). Functional-form parameters are more informative than cliff position alone: A1's strongest possible result is "factor X moves p, factor Y doesn't."

### Factor isolation strategy: within-suite contrasts, not cross-model regression

Public models differ in everything at once; regression across heterogeneous models is hopelessly confounded (architecture, tokenizer, data, post-training all covary). The design therefore leans on **suites that hold everything fixed but one factor**:

| Factor | Instrument | What's held fixed |
|---|---|---|
| Parameter count | Pythia ladder (70M–12B) | data, data order, architecture family, tokenizer |
| Data quantity | intermediate training checkpoints (Pythia: 154/size; OLMo similar) | everything — same run, earlier step |
| Depth vs width | aspect-ratio suites (Gemstones-style; MobileLLM at sub-1B) — inventory delegated to A1_SCALING_FEASIBILITY.md | params (approximately), data |
| Data quality | recipe-ablation models (FineWeb vs FineWeb-Edu ablation octet primary; DataDecide if its ≤1B sizes clear the task floor; DCLM deprioritized — not vLLM-loadable per A1_INFERENCE_PLAN.md) | architecture, token budget |

Cross-suite comparisons are secondary and explicitly labeled observational. A frontier-API arm (Haiku, plus whatever frontier models Phase 2 selects) rides along for the cliff atlas but contributes nothing to factor isolation — vendors disclose none of the factors.

### The three measurement problems

1. **The floor problem.** Small base models may score zero everywhere on the Experiment-1 grids — no cliff, no data point. Mitigation: extend every family's grid *downward* (automata k=1 at width 4; 3×3 mazes already exist; chaos with 1–2 decimal places; 3-variable SAT; argmax over 5 points). The generators support this today. Gate the study on a **pilot**: 3 suite models spanning the size range × easiest 3 levels × 2 families; proceed only if the smallest models clear 20% somewhere.
2. **The context-window constraint (added after the inference plan).** Pythia, Gemstones, FineWeb-ablation, and MobileLLM models have 2,048-token contexts — Experiment 1's prompt+output budget doesn't fit. The base arm therefore uses trimmed prompts and short completions (~640 tokens, stop sequences). This is less of a loss than it sounds: short-output is precisely the no-CoT regime where the depth prediction (§2, A1-P6) applies most cleanly — the constraint and the theory point the same direction. The CoT-permitted arm of A1-P6 runs only on models whose context allows it (Pythia ≥ 2.8B variants if extended-context releases exist, OLMo 2, and the frontier rideshare arm).
3. **The format problem.** Base models don't reliably follow "ANSWER: X" instructions. Mitigations, in preference order: (a) few-shot prompts (k=5 worked examples, stop sequence at the next delimiter) — keeps the generation-based scoring identical to Experiment 1; (b) likelihood scoring over enumerated answer candidates where the answer space is small (SAT yes/no; multiple-choice-ified variants) — robust but changes the task, so it becomes a labeled variant, never pooled with generative scoring; (c) never light SFT — it injects exactly the procedure-rehearsal confound §2 warns about. Parse-failure rates get reported per model (H10's validity gate applies: if format failures exceed a few percent, fix prompts and rerun, don't interpret).

### Conditions

A1 is a **C0-only study**. C1/C∞ require tool-following ability that base models lack, and the hypothesis is about internal computation anyway. This keeps the per-model cost small (480 short samples) — the study's cost is dominated by serving many models, not by sample count (engineering plan delegated to A1_INFERENCE_PLAN.md).

## 4. Pre-registered predictions

Labeled by owner, registered 2026-06-12, before any A1 runs:

- **A1-P1 (Andrew, the hypothesis itself):** the four factors dissociate — at least one factor moves cliffs substantially and at least one moves them negligibly. Exploratory; no confidence number.
- **A1-P2 (agent):** depth in layers predicts serial-family cliff position (automata, chaos) better than parameter count does, in the aspect-ratio suite: at matched params, deeper-narrower beats shallower-wider on serial families. Confidence 0.6.
- **A1-P3 (agent):** data quantity saturates early — over intermediate checkpoints, cliff positions stop moving well before training ends (final-quarter-of-training movement < 1 grid level on serial families), while easy-level accuracy and format competence keep improving. Confidence 0.6.
- **A1-P4 (agent):** parameter count at fixed data (Pythia ladder) moves every family's cliff, but sublinearly — each 10× in params buys ≤ 2 grid levels — consistent with H12's "shift, don't remove." Confidence 0.7.
- **A1-P5 (agent):** no factor changes the functional forms: automata stay exponential-in-k, chaos horizons stay Lyapunov-scaled; factors move constants (p, D), never laws. Confidence 0.75. This is the architecture-signature claim, and it is the prediction whose falsification would be most interesting.
- **A1-P6 (agent, added after the feasibility review, same day, still pre-run):** the depth effect interacts with chain-of-thought — in the aspect-ratio suite, layer depth moves the *no-CoT* (direct-answer) cliff substantially and the *CoT-permitted* cliff much less, because CoT rents serial depth in tokens and substitutes for layers. Requires running both prompt modes per model (the feasibility doc budgets for two prompt modes). Confidence 0.6. This converts §2's CoT caveat from a limitation into a registered theory test.

## 5. Analysis plan

1. Cliff position (logistic-fit midpoint) per model × family, with parse-failure and output-length covariates reported.
2. Within-suite contrasts as the primary inference: Pythia ladder (params), checkpoint sweeps (data quantity), aspect-ratio suite (depth at matched params), recipe pairs (quality). Each contrast is a per-family plot of cliff position vs the factor.
3. Functional-form fits: p (per-step fidelity) and k* (digit horizon) vs each factor — the headline figure if A1-P2 or A1-P5 lands.
4. Cross-suite observational regression (cliff ~ log params + layers + log tokens) reported with heavy caveats, mainly to check the within-suite findings generalize beyond one architecture family.
5. Negative results are results: "no factor we can vary moves the chaos cliff past k=8" would be the strongest possible support for the architectural thesis.

## 6. Phasing and gates

1. **Pilot** (gate): 3 models × 2 families × easiest 3 levels, few-shot prompts. Pass = smallest model clears 20% somewhere and parse failures < 10% with few-shot prompting. Cost: trivial.
2. **Param + data-quantity arms:** Pythia ladder (8 sizes) + ~6 checkpoints/size on 2 sizes. ~20 model-points × 480 samples.
3. **Depth and quality arms:** contingent on A1_SCALING_FEASIBILITY.md's inventory — if no public aspect-ratio suite covers our needs, this is where the train-our-own decision (with its budget) gets made, scoped in that doc.
4. **Write-up gate:** A1 results merge into the paper only if the pilot-validated grid yields measurable cliffs for ≥ 70% of model × family cells; otherwise A1 reports the floor finding and the frontier-only cliff atlas.
