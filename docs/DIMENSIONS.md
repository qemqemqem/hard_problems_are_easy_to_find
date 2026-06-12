# DIMENSIONS — Axes of problem variation beyond scalar difficulty

Status: brainstorm, 2026-06-12, post-Experiment-1. Companion doc:
`VARIATION_DIMENSIONS_LIT.md` (literature scan of the same question).

Experiment 1 varied one thing per family: a scalar difficulty knob. That
found the cliffs. This doc asks: **what else can we vary**, such that the
*pattern* of variation tells us something about what LLM "reasoning" is —
not just where it stops. Each axis below states the manipulation, the
prediction, and what a result would mean. Ordered roughly by how promising
I think they are.

---

## 1. Serial depth vs parallel breadth (matched total work)

**The manipulation.** Hold total computation roughly constant; vary its
*shape*. Examples:
- automata: width w × steps k with w·k fixed (10×32 vs 32×10 vs 320×1);
- arithmetic: sum 1,000 numbers (breadth-1,000, depth-1 with a
  reduction tree) vs iterate a map 1,000 times (depth-1,000, state-1);
- argmax (breadth: independent evaluations) vs chaos (pure depth) are
  already a cross-family version of this contrast — formalize it.

**Prediction.** Depth kills C0 far faster than breadth at matched work.
Transformers are constant-depth parallel machines (TC⁰ framing); a long
serial chain must be unrolled into output tokens, where per-step error
compounds (H2's p^k), while wide-shallow work can be partly absorbed by
attention in parallel.

**Why it matters.** This is the most theory-connected axis in the whole
project: it turns the RASP-L / circuit-depth conversation into a measured
2-D surface (accuracy over depth × breadth) instead of a 1-D cliff. If
iso-accuracy contours run nearly parallel to the breadth axis, that's a
clean architectural signature — and a concrete spec for what a successor
architecture must fix (serial fidelity, not capacity).

## 2. Representation / rendering invariance

**The manipulation.** Same abstract instance, different surface form:
- maze: ASCII grid vs wall-coordinate list vs natural-language room
  descriptions;
- TSP: coordinate pairs vs explicit distance matrix vs "city A is 3km
  from city B" prose;
- chaos/arithmetic: decimal digits vs number words vs scientific
  notation; digit grouping (tokenization stress).

**Prediction.** C0 swings hard across renderings (the literature on
presentation sensitivity suggests 10–30 points); C1 stays flat, because
the program normalizes the representation before computing.

**Why it matters.** A *double dissociation*: difficulty knobs show
computation failing while parsing survives (Exp 1); rendering knobs show
parsing wobbling while the computation — once externalized — is immune.
Together they cleanly factor "solving" into read → represent → compute.
Cheap to run: same ground truth, same scorers, only the renderer changes.
Our `Instance`-object design (data separate from text) was built for
exactly this and we haven't used it yet.

## 3. Solution density / slack

**The manipulation.** Hold instance *size* fixed; vary how many solutions
exist or how forgiving the solution path is:
- maze: braided (many shortest paths) vs unique-path perfect mazes;
- SAT: planted instances with controllable solution counts (1 vs 10⁶),
  at fixed n and α;
- TSP: clustered points (big gap between optimal and 2nd-best tour) vs
  uniform (near-ties everywhere);
- argmax: plateau width around the global optimum.

**Prediction.** C0 accuracy at fixed size tracks solution density — the
model is doing something greedy/noisy, and dense solution spaces forgive
noise. If true, part of every "cliff" in Exp 1 is a solution-density
artifact, not pure size. That's a refinement we'd want before making
strong claims about cliff *locations*.

**Why it matters.** Distinguishes "the model computes badly" from "the
model computes noisily" — noisy computation + dense solutions still
scores. Also de-confounds our own Exp 1 result.

## 4. Verification vs generation asymmetry

**The manipulation.** For every family, add the *verifier* task: here is
a candidate (tour / assignment / path / trajectory) — is it valid? Is it
optimal? Score against ground truth. Compare the verify-cliff to the
generate-cliff at matched instance size. Variants: verify-own-answer
(feed back the model's C0 output) vs verify-foreign.

**Prediction.** Verification cliffs sit substantially right of generation
cliffs for NP-ish families (checking is in P), but **not** for chaos and
automata, where verifying a trajectory requires re-running the same serial
computation — verification is exactly as deep as generation. That split
prediction is sharp, falsifiable, and family-derivable from theory.

**Why it matters.** Ties directly to H8 (does the model know it's
beaten?) and to the self-correction literature. If models can verify but
not generate, abstention should be learnable; if they can't even verify
(chaos), confabulated confidence is the only possible behavior.

## 5. Familiarity / memorization distance (counterfactual variants)

**The manipulation.** Hold formal structure fixed; vary distance from the
training distribution:
- automata: rule 110 (famous) vs random rules of the same Wolfram class;
- chaos: logistic map (textbook) vs an obscure same-Lyapunov map;
- TSP/maze: canonical framing ("traveling salesman") vs semantically
  camouflaged re-skins (drone routing, warehouse picking) vs pure
  abstract symbols;
- explicitly *naming* the problem class in the prompt vs not.

**Prediction.** Naming/familiarity helps C0 a little at easy levels
(retrieval of solution schemata) and not at all past the cliff — the
cliff is computational, not retrieval-bound. For C1 the effect
concentrates in *algorithm selection*: "this is TSP" might be what
finally triggers Held–Karp instead of 2-opt (Exp 1's most interesting
micro-finding).

**Why it matters.** Engages the reasoning-vs-reciting literature, and
counterfactual variants are our contamination story for frontier models.

## 6. Knowledge coupling (the Phase-2 hybrid axis)

**The manipulation.** Vary how much *world knowledge* the search loop
needs per node, from zero (all current families) to heavy:
- crossword-fill / anagram-chain problems where candidate evaluation
  needs a lexicon;
- "semantic Wordle" where constraints are meanings, not letters;
- code-golf against a natural-language spec.

**Prediction (= H11).** There is a regime where even C∞ stays under 50%
at sizes a human-plus-laptop handles, because ≤10 coarse tool calls can't
put model knowledge *inside* the inner loop.

**Why it matters.** This is the load-bearing axis for the architectural
thesis. Exp 1 showed transformer+REPL solves everything we can verify;
the paper's "we need different foundation models" claim is hollow unless
we exhibit problems where the REPL patch fails. Highest stakes, hardest
to build well (scoring needs care).

## 7. Distractor load / relevance filtering

**The manipulation.** Hold the core instance fixed; inject irrelevant
material: superfluous SAT clauses subsumed by others, unreachable maze
regions, TSP cities that are provably never on the optimal tour, padding
prose. Vary distractor fraction 0→90%.

**Prediction.** C0 degrades with distractor load even at sizes the model
handles cleanly; C1 degrades much less (the program ignores nothing — it
processes everything mechanically). Separates *attention/retrieval*
failure from *computation* failure, and de-confounds prompt length from
difficulty (a stated Exp 1 confound — this axis turns the confound into a
measured variable).

## 8. Error-propagation structure

**The manipulation.** Within iterated systems, vary the Lyapunov
exponent / damping directly: contracting maps (errors die), neutral, and
chaotic (errors explode), at matched step count and arithmetic load.
Automata analog: rules with light-cone error spread vs self-correcting
(majority-vote-like) rules.

**Prediction.** C0 horizon scales as D·ln(10)/λ (H3 generalized): on
contracting systems the model tracks far more steps than on chaotic ones
*despite identical per-step arithmetic*. This upgrades H3 from one curve
to a law with a swept parameter — the strongest "theory line through LLM
data" plot available to us.

## 9. Decomposability / coupling

**The manipulation.** Problems that factor vs problems that don't, at
matched size: block-diagonal TSP (k well-separated clusters) vs uniform;
SAT instances that are unions of independent subformulas vs connected;
automata with separable regions.

**Prediction.** Models exploit visible decomposition in C0 (solve
clusters independently) — accuracy tracks *largest component* size, not
total size. If they don't, that's a notable strategic blindness.

## 10. Interactivity / partial observability (Phase 3)

**The manipulation.** Fog-of-war maze: the model sees only a local window
and must issue moves to observe more. The problem stops being computation
and becomes exploration policy. C0 = dialogue turns, C∞ = tool calls.

**Why deferred.** Different harness shape (stateful environment), and the
results stop being about the compute-vs-understand thesis. Park it.

---

## Cross-cutting design notes

- **Factor out, then cross.** Each axis should first be swept alone at a
  fixed mid-cliff difficulty (where Exp 1 says C0 ≈ 30–50%, maximum
  sensitivity), not crossed with everything. Full factorials explode the
  budget; difficulty × one-axis-at-a-time is enough for Phase 2.
- **Our architecture already supports most of this.** Renderings (#2),
  distractors (#7), planted solutions (#3), and counterfactual rules
  (#5) are generator/renderer changes; verification tasks (#4) are new
  scorers on existing instances. Only #6 and #10 need genuinely new
  families.
- **The C1 column is the control everywhere.** Every axis predicts a
  C0/C1 *divergence pattern*; flat-C1 is what licenses the inference.
  Axes where C1 also moves (expected: #6, maybe #5's algorithm-selection
  effect) are the architecturally interesting ones.
- **Priority order for Phase 2:** depth-vs-breadth (#1) and
  verification-vs-generation (#4) for theory contact; rendering (#2) and
  distractors (#7) as cheap, clean dissociations; solution density (#3)
  as a validity check on Exp 1's cliffs; knowledge coupling (#6) as the
  high-risk, thesis-critical build.

---

## Revisions after the literature scan (2026-06-12)

`VARIATION_DIMENSIONS_LIT.md` (companion survey, ~45 papers) confirms the
axis list above but corrects several predictions and priorities:

1. **My verification prediction (#4) was probably backwards.** I
   predicted verify-cliffs sit right of generate-cliffs for NP-ish
   families because checking is in P. A 2026 line (Srivastava et al.,
   "When Verification is Harder Than Solving") finds LLMs are often
   *worse* at verifying than solving — acceptance bias, blindness to
   localized errors in near-correct candidates. Reframed: the axis is
   now a *contested empirical question*, which is better for us. The
   novelty is the within-suite contrast the literature lacks: SAT
   verification is theoretically cheap (O(m)) while chaos verification
   is exactly as serially deep as generation — does the model's
   verify-cliff track the *theoretical* asymmetry or ignore it? Emit
   three candidate types per instance: correct, near-miss (single-edit
   corruption), random-plausible.
2. **H11's prior just got worse.** SweepClip (NAACL 2025) reaches 93%
   character accuracy on NYT crosswords with LLM-guided search —
   knowledge-in-the-loop is weaker ground for "even C∞ fails" than
   hoped. But their loop used far more than 10 model calls, so the
   salvage is to make **knowledge-call budget the swept knob** (C∞ with
   1/3/10/30 calls) and instrument C1 programs for embedded-wordlist
   incidence. Also notable: their residual failure mode is sub-token
   letter *counting* — a processing failure inside the knowledge loop,
   squarely our thesis.
3. **Curve shape is a fingerprint — add it to the analysis plan.** The
   literatures report exponential decay for serial depth (seqBench),
   log-linear for working-memory load (PI-LLM), sigmoid for composite
   complexity (GSM-Infinite). If a single family swept along two axes
   shows the *shape* switching, that identifies which resource binds —
   stronger than any cliff location. This argues for treating state
   size (CA width, map dimensionality, maze frontier size) as its own
   axis rather than folding it into #1.
4. **Adopt minimal pairs.** Random ensembles inflate accuracy via
   base-rate exploitation (models call nearly everything SAT). The
   paired-instance methodology — single-edit SAT/UNSAT counterparts,
   scored on getting *both* right — is a cheap retrofit for every
   binary-scored family (maze with one wall flipping a bound, tour with
   one weight crossing an optimality threshold).
5. **Free retro-analysis:** Pencil Puzzle Bench finds solution
   *compressibility* predicts difficulty ~4× better than solution
   length. We can compute move-sequence compressibility for Exp 1 maze
   and automata answers from existing logs and test this on our data
   with zero new API spend.
6. **Where our marginal value is (per the survey's gap analysis):** the
   field has generators and scalar difficulty knobs in abundance; what
   it lacks is (a) factorial designs at matched total work, (b) any
   suite crossing knobs with a think/code/interactive **condition
   ladder**, and (c) problem-side error dynamics and solution-density
   knobs. The C1 column is unmeasured across essentially every axis —
   it is our unique instrument, and the cross-axis *profile* of where
   C1 is invariant vs. where it is also brittle is the paper.
