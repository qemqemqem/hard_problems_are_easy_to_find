# HYPOTHESES — Pre-registered Predictions

**Status: v1.0, frozen 2026-06-11, BEFORE any model runs.** Amendments may be *appended* with dates and reasons; nothing here gets edited in place after the first Phase 1 sweep. Predictions are the agent's (Fable), made deliberately specific enough to be wrong. Confidence = subjective probability the prediction holds as stated.

## Definitions

- **Model:** Claude Haiku 4.5 (pinned snapshot), temperature 0, default thinking unless stated. Phase 1 families: TSP, 3-SAT@α≈4.27, maze, automata, chaos (logistic/Hénon), argmax.
- **Conditions:** **C0** = pure thinking; **C1** = model writes one Python program, we execute (60s sandbox, no feedback), stdout scored; **C∞** = interactive python tool, ≤10 executions.
- **Cliff:** the difficulty-knob interval over which accuracy falls 80% → 20%.
- "Accuracy" = `Score.correct` rate; gradated metrics named explicitly where used.

## Phase 1 hypotheses

### H1 — Cliffs exist everywhere (C0)
Every family shows a cliff within a factor of ~4 of knob range (e.g., maze 8×8 → 32×32, automata k=4 → k=16). No family stays above 50% at our max difficulty level.
**Confidence: 0.90.** Falsified if any family is still ≥50% at max difficulty (then our knobs are mis-set, or Haiku is better than the entire literature suggests).

### H2 — Exponential depth decay (automata, C0)
Accuracy vs. steps k fits accuracy ≈ p^k (linear in log-accuracy) with per-step fidelity p ∈ [0.95, 0.995]. The same model's p is roughly stable across automaton types (it's a property of the model's serial fidelity, not the rule).
**Confidence: 0.70** for the functional form; **0.5** for cross-rule stability of p.

### H3 — Lyapunov-predicted horizon (chaos, C0)
Digit-exact tracking dies at horizon k* ≈ D·ln(10)/λ steps (D = effective digits the model carries per step, λ = Lyapunov exponent). Concretely: logistic map r=3.9 (λ≈0.5), 4-decimal scoring → measured k* between 4 and 16 steps, and Hénon's k* shifts in the direction theory predicts relative to logistic.
**Confidence: 0.65.** This is the highest-payoff plot if it lands: a theory line through LLM data.

### H4 — Code rescues Category 2: the headline result (C1 vs C0)
At difficulty levels where C0 < 5% (maze, automata, chaos, and argmax), C1 ≥ 90%. The model formalizes these problems correctly nearly every time — failure in C0 is processing, not understanding.
**Confidence: 0.85.** Falsified if C1 stalls below ~70% on any of these (which would mean the *formalization* step is weaker than I believe — itself a major finding contradicting the paper's intended headline).

### H5 — Where does C1 land? (the user's genuine uncertainty; my calls)
- **H5a:** On cleanly algorithmic families (maze, automata, chaos, argmax): C1 lands within 10 points of C∞ — i.e., **C1 ≈ C∞ ≫ C0**. The program is easy to get right first try; iteration adds little. **Confidence: 0.65.**
- **H5b:** On search families (SAT n≥30, TSP n≥15): C∞ beats C1 by >10 points (accuracy / approximation ratio respectively) — debugging, timeout management, and strategy iteration matter. **Confidence: 0.55** (close to a coin flip; that's why we're measuring).
- **H5c:** C1's dominant failure mode will be *engineering*, not understanding: timeouts from naive brute force at large n, off-by-one I/O parsing — not wrong algorithms. **Confidence: 0.6.**

### H6 — NP-hard graceful-degradation profile (TSP, C0)
Haiku's tours: invalid-tour rate >30% by n=20; among valid tours, quality worse than nearest-neighbor baseline by n≈12; never beats 2-opt at any n ≥ 10. (Per GraphArena-style findings, hallucinated/infeasible answers grow with n.)
**Confidence: 0.70.**

### H7 — Phase-transition signature (3-SAT, C0)
Accuracy vs. clause ratio α reproduces the easy-hard-easy dip centered near α≈4.3 (replicating Hazra et al. on a current cheap model), with certificate-validity collapsing faster than yes/no accuracy (models will keep *claiming* SAT with broken assignments).
**Confidence: 0.60** for the dip; **0.75** for certificates collapsing faster than claims.

### H8 — Models don't know they're beaten (abstention extension)
Under "+1 correct / −1 wrong / 0 for I-don't-know" scoring (instructions in-prompt), at the two hardest difficulty levels per family: abstention rate < 25% and mean score < 0 (worse than always abstaining). Confabulation dominates calibration even when the incentive is explicit.
**Confidence: 0.75.** The interesting failure of this prediction: high abstention *everywhere* including easy levels (over-conservatism), which I give ~0.1.

### H9 — Thinking budget moves cliffs sublinearly (C0)
Max thinking vs. minimal thinking shifts each family's cliff by less than 2× in knob value, and for at least one family (chaos or automata at high k) extra thinking buys *nothing* measurable. Token spend rises superlinearly relative to the difficulty gain (consistent with the Illusion-of-Thinking token-collapse observation near the cliff).
**Confidence: 0.65.**

### H10 — Format faults stay rare (engineering sanity bar)
After calibration, parse_error < 3% per cell across all families and conditions. (If violated, fix the renderer/parser and *rerun*; format failures must not masquerade as reasoning failures — this is a validity gate, not a finding.)
**Target, not a bet.**

## Phase 2 hypotheses (registered now, tested later)

### H11 — The hybrid conjecture (Category 6, crossword-fill style)
There exists a generated family where, at sizes a human-plus-laptop solves reliably in minutes, **even C∞ stays below 50%** — because candidate evaluation needs model knowledge inside the search loop, and ≤10 tool calls of coarse alternation can't supply it. Specifically for anagram-clue crossword fill: C0 fails by 5×5 grids; C1's fate hinges on whether the model embeds a wordlist in its program (I predict it usually won't think to — confidence 0.55); C∞ improves but plateaus below 50% on 7×7.
**Confidence: 0.50 — maximal uncertainty, deliberately.** Either outcome is a result: failure of the conjecture means "transformer+REPL" is more complete than we argue; success motivates the architectural-search thesis.

### H12 — Frontier models shift cliffs, don't remove them (Phase 2)
Frontier-tier models (set TBD post-Phase 1) move every C0 cliff right by ≤4× in knob value, with the *same functional forms* (H2's exponential, H3's Lyapunov horizon — different constants, same laws). The architecture's signature survives capability scaling.
**Confidence: 0.75.**

## Andrew's hypotheses (added 2026-06-12)

**Provenance note:** H1–H12 above are the agent's (Claude Fable 5) pre-registered predictions, frozen before any model runs. The hypotheses below are **Andrew's own**, stated 2026-06-12 — after Experiment 1's Haiku results but before any scaling, multi-model, or Phase-2 runs. Wording paraphrased by the agent from Andrew's notes; the ideas are his.

### A1 — Which training factor buys cliff position?
Across models, the C0 cliffs improve as a function of *some* training factors and not others — parameter count, depth in layers, training-data size, and training-data quality should be separated. The interesting result is a dissociation: some axis of training improvement fails to pay out on these problems (candidate headline: "parameter count helps, but more training data doesn't"). (Agent note: circuit-depth theory makes "depth in layers moves serial-family cliffs; width/params/data mostly don't" the sharpest registrable version. Requires open-weight model ladders — Pythia/OLMo for data-size at fixed architecture, size ladders for params — since frontier APIs disclose none of these factors.)
*Exploratory — no confidence number assigned.*

### A2 — The C1/C∞ gap generalizes beyond TSP
There are other problem classes where one-shot code persistently underperforms interactive code. Framed as a question, not a bet: *which* problems exhibit this gap, and what mechanism drives each? (Investigation delegated 2026-06-12; findings to land in `C1_CINF_GAP.md`.)

### A3 — Tacit-objective problems break the C1 rescue (the furniture-placement conjecture)
There exist real-world-like problems whose constraints are driven by intuition: strong inter-rater agreement among humans about what's good, but laborious to spell out exhaustively (canonical example: furniture placement — the desk shouldn't sit next to the fridge, walking space must remain, and enumerating every such constraint is impractical even though people agree on them). For these, outsourcing to program execution doesn't help, because *writing the program requires articulating the very objective that is tacit* — the thinker must do the thinking internally. Prediction: on such problems the C1 rescue observed everywhere in Experiment 1 fails (C1 ≈ C0), and this is the most important regime for the C0/C1 comparison because it implies a genuine real-world failure that code execution cannot patch. (Agent note: the measurable signature is super-additivity — C∞ > max(C0, C1) — since C∞ is the only condition where model-resident judgment and external search can combine.)
*Acknowledged hard to operationalize; ground-truth design is the open problem.*

### A4 — Distractors hurt the program, not just the answer
Heavy distractor load may make the right program harder to *write* (C1 degrades), not just the direct answer harder to produce (C0 degrades). Counter-hypothesis, also Andrew's: the distractor axis might reduce to needle-in-a-haystack retrieval in disguise, in which case it is less interesting than it looks.

## Scoring this document

When Phase 1 data lands: each hypothesis gets graded (held / partially / falsified) in a RESULTS.md appendix, including the misses — the pre-registration only has value if the misses are reported with the hits.

---
*Amendment log: 2026-06-12 — appended provenance note and Andrew's hypotheses A1–A4. No edits to H1–H12.*
