# The C1 < C∞ Gap — Mechanism Taxonomy, Literature, and Recommended Families

**Companion to [DESIGN.md](./DESIGN.md), [HYPOTHESES.md](./HYPOTHESES.md) (H5, H11), [LITERATURE.md](./LITERATURE.md), and [VARIATION_DIMENSIONS_LIT.md](./VARIATION_DIMENSIONS_LIT.md) (which this does not duplicate; crossword/SweepClip evidence lives there, §5). Status: v0.1, speculative analysis + web-search survey (2026-06-12).**

Motivating result (Experiment 1, Haiku 4.5): C0 pooled 23.8%, C1 95.0%, C∞ 99.4%. Five of six families show C1 ≈ C∞ ≈ 100%. Only TSP separates the code conditions: at n=16, **C1 12.5% optimal vs C∞ 87.5%**. Transcripts show the mechanism: in C1 the model commits one-shot to a 2-opt/or-opt heuristic; in C∞ it iterates and restarts until the tour stops improving. It never writes Held–Karp even though n=16 makes exact DP trivially feasible — *iteration substitutes for algorithm selection*.

The question this doc answers: **which problems show a persistent C1 < C∞ gap, and why** — so we know what to build next.

---

## 0. The load-bearing observation: contingent vs. necessary gaps

Before enumerating mechanisms, one structural fact dominates everything else in this doc:

> **For any deterministic problem whose full instance data is in the prompt and whose verifier is programmatic, a sufficiently foresighted C1 program can simulate C∞.** The program can embed its own iterate-evaluate-retry loop: run 2-opt with random restarts until 55 s of the 60 s budget elapse; try the exact algorithm with a watchdog and fall back to the heuristic on timeout; test which regime the instance is in before choosing a strategy. Nothing in the C1 *protocol* forbids this — only the model's failure to anticipate the need.

This splits the mechanism space in two:

- **Contingent gaps** (mechanisms a–d below): C1 *could* close the gap by writing a more defensive/adaptive program, but doesn't. The gap measures a real and under-studied capability — call it **planning-to-compute** or computational self-knowledge: does the model know what it doesn't know about its own program's behavior, and budget for it? Our TSP result is a contingent gap: `while improving: 2opt(); restart()` inside one program would have matched C∞.
- **Necessary gaps** (mechanisms e–f): no one-shot program can close the gap *in principle*, because something required inside the loop is unavailable to the program — either the model's own knowledge/judgment (e), or information that only crosses the execution boundary as feedback (f). These are the gaps that survive a smarter model, and they're the ones that support the paper's architectural thesis (DESIGN.md §1, hybrid conjecture).

This distinction should be a headline framing of any C1-vs-C∞ analysis: **a contingent gap is a finding about the model's metacognition; a necessary gap is a finding about the paradigm.** Both are worth measuring; they need different problem families; and the transcript signature differs (contingent: C1 writes a non-adaptive program when an adaptive one was available; necessary: even a perfect C1 program provably can't win).

Corollary for instrumentation: for every family below, log whether the C1 program contains an internal iteration/retry/fallback loop. The *incidence of self-iterating C1 programs* is a free, novel measurement — nobody reports it (we found no prior work even asking the question).

---

## Part 1 — Mechanism taxonomy

For each mechanism: what creates it, the minimal generable family with programmatic ground truth that isolates it, and a rank by (cleanness of isolation × buildability in our generator+verifier architecture).

### (a) Algorithm-selection uncertainty — *contingent*

**What creates it.** The instance sits near a feasibility boundary the model can't locate a priori: brute force fits the time budget at n=14 but not n=18; the DP table fits memory at one parameter setting and not another; the exact solver's runtime has high variance across instances of the same size. The model must choose between "exact but maybe too slow" and "fast but maybe too inexact" without being able to run anything. Problem features that create it: (i) superlinear-complexity exact algorithms with instance sizes straddling the budget; (ii) graded scoring (so the heuristic isn't simply *wrong*, just worse — a binary scorer would make the model more paranoid); (iii) runtime that depends on hidden instance structure, not just size (SAT solver variance, branch-and-bound luck).

**Literature anchor.** Models are measurably bad at exactly this judgment: on BigO(Bench) ([Chambon et al. 2025](https://arxiv.org/abs/2503.15242)), the best model gets only 29.2% Pass@1 at *generating code meeting a stated time-complexity bound*, with large drops when complexity control is combined with correctness; CodeComplex ([Baik et al. 2024](https://arxiv.org/abs/2401.08719)) shows worst-case complexity *prediction* is mediocre even for strong models. So the a-priori signal the model would need ("will this fit the budget?") is one it demonstrably lacks.

**Minimal isolating family.** "Budget-trap" optimization: planted-optimum combinatorial problems where the exact algorithm fits the sandbox timeout only below a known difficulty level, and a natural greedy is reliably ~10–20% suboptimal. The knob sweeps the instance size *through* the feasibility boundary. Crucially, publish the timeout in the prompt — the information needed for the choice is all there; only the self-knowledge is missing.

**Rank: 1st among contingent mechanisms.** We already have the TSP existence proof; the family generalizes cheaply (knapsack DP-table size, subset-sum meet-in-the-middle vs. brute force, exact maze on huge grids vs. greedy); isolation is clean if engineering fragility (b) is controlled (simple I/O formats).

### (b) Engineering fragility — *contingent, and mostly a confound to control*

**What creates it.** First-try code crashes, mis-parses, or times out for reasons unrelated to algorithm choice: gnarly input formats, off-by-one indexing, numerical edge cases (overflow, float equality, empty-input branches). Iteration = debugging. First-try correctness is genuinely hard when: the format spec has corner cases that the happy path doesn't exercise; the computation has numerically unstable regions; or the output format is exacting.

**Honest assessment.** This is the *least* scientifically interesting mechanism for our project — it measures software engineering, not reasoning, and a family designed around nasty parsing will read as contrived ("you built an obfuscated-CSV benchmark"). The self-debugging literature (Part 2) says the gains from fixing first-try bugs are real but modest (3–12 points) on tasks of ordinary gnarliness. Our Experiment 1 H5c prediction (C1 fails by engineering, not algorithm choice) was *wrong* for TSP — the failure was algorithm commitment, not bugs — and that's worth reporting.

**Use, not build.** Treat (b) as a confound to be controlled (simple formats everywhere, per design rule 4) and *measured* (categorize every C1 failure as crash / timeout / wrong-algorithm / wrong-answer from transcripts), not as a family to design for. If we want one deliberate probe, a "numerically treacherous evaluation" family (catastrophic cancellation, accumulating float error where the naive formula loses all precision) is the most defensible version — the bug is mathematical, not clerical.

**Rank: last as a build target; mandatory as an error category.**

### (c) Parameter / threshold tuning — *contingent*

**What creates it.** Solution quality depends on constants with no closed-form correct value: annealing schedules, restart counts, convergence tolerances, optimizer initial guesses, regularization strength. The map from constants to quality is only observable by running. Distinct from (a): the *algorithm* is right; its *knobs* aren't. Problem features: rugged objective landscapes where local search stalls; iterative numerical methods whose convergence depends on initialization; quality thresholds set just beyond where default constants land.

**Minimal isolating family.** Planted-parameter recovery: generate data from hidden parameters of a known nasty model (sum of close-frequency sinusoids; mixture with imbalanced components), demand recovery within a tolerance set so that a default one-shot `curve_fit`/`minimize` from a naive initial guess fails ~80% of the time, while inspect-residuals-and-restart succeeds. Ground truth is the planted parameters — fully programmatic. The tolerance knob directly tunes the C1 failure rate, which makes calibration easy.

**Rank: 2nd among contingent mechanisms.** Very clean isolation (the model will essentially always pick the right *method* — scipy — so algorithm selection is held constant), cheap to generate, graded scoring for free (log-distance to planted parameters). One caution: a savvy C1 program writes multi-start optimization in one shot, collapsing the gap — which is fine; that incidence is itself the measurement.

### (d) Information revealed only by execution: instance-regime opacity — *contingent*

**What creates it.** The right strategy depends on instance structure that is opaque to inspection but cheap to compute: is the graph secretly bipartite/planar? Is this SAT instance in the trivially-satisfiable regime? Does the landscape have one basin or many? A one-shot program must either branch on regime (possible! contingent) or commit. Iteration lets the model *probe first, choose second*.

**Minimal isolating family.** Regime-mixture instances: each instance drawn from a mixture of (i) specially structured instances where an exact poly-time algorithm applies (planted bipartite graph → exact max-cut; hidden low treewidth; sorted-under-permutation data) and (ii) unstructured instances where only heuristics work. The prompt states the mixture exists but not which regime this instance is in. Scored on optimality. The model that probes (in code) wins; the model that commits loses on half the instances.

**Rank: 3rd among contingent mechanisms.** Slightly less clean than (a)/(c) because a strong C1 program *should* just always test the regime — the marginal cost of the test is tiny — so the gap may be small for strong models and the family mostly measures whether the model reads the prompt carefully. But the transcript signature (does C∞ run a diagnostic first?) is lovely and directly observable.

### (e) The objective function lives in the model — *necessary*

**What creates it.** Evaluating a candidate requires knowledge or judgment that exists in the model's weights and cannot be serialized into a one-shot program: which letter strings are real words (lexicon), which sentence is grammatical and natural, which room layout a human would prefer. A C1 program cannot embed the model; C∞ can put the model *in the loop* — generate candidates programmatically, judge them linguistically, repeat. This is the only mechanism that predicts **C∞ > C1 AND C∞ ≫ C0 superadditively**: C0 lacks the computation, C1 lacks the judge, only alternation has both. This is H11, and it's the architectural-thesis mechanism.

Two sub-cases matter:

- **(e1) Serializable-in-principle knowledge** (word lists, rhyme tables, synonym sets): a C1 program *could* embed a 200-word lexicon dump from the model's memory. Whether the model thinks to — and whether its from-memory lexicon is good enough — is a measurable, pre-registered question (H11's sub-prediction). The gap here is contingent-leaning but with a knowledge-quality ceiling.
- **(e3) Judgment downstream of execution** *(added 2026-06-12 from A3_PROBLEM_BRAINSTORM.md §0.3)*: code can cheaply produce a representation (rasterize a tour, decode a CA state into a letter bank), but only C∞ ever *perceives* it — C1 launches the transform and is gone before the percept exists. Necessary-by-construction like (f), but the information isn't harness-held; it's computable from the prompt, just not perceivable without running. The planted hybrids (inverse TSP art, trapdoor quiz) isolate it.
- **(e2) Non-serializable judgment** (naturalness, preference, aesthetics — the furniture problem): there is no compact dump. Humans agree the desk doesn't go next to the fridge but can't enumerate all such constraints; the judgment is a learned function, not a rule list. Here the gap is strictly necessary. The catch for *our* architecture: ground truth can't be a 10-line verifier. Part 2 (§2.7) surveys how researchers get rigorous ground truth anyway (pairwise preference + Bradley–Terry/Elo, expert consensus filtering, held-out-rater validation) — rigorous but not free, and it violates our Phase-1 "no judged scoring" rule. The buildable compromise: **objectives that are mechanically verifiable but practically reachable only through model-knowledge-guided search** (crossword fill: exact grid match verifies mechanically, but the search needs a lexicon). That keeps the verifier programmatic while the *search oracle* stays in the model.

**Minimal isolating family.** Crossword-style lexicon fill (PROBLEMS.md 6.1) remains the right first build — see VARIATION_DIMENSIONS_LIT.md §5 for why SweepClip's success at NYT crosswords (with hundreds of model calls) sharpens rather than kills H11: our question is the ≤10-call regime. A second, cheaper isolate: **"common-word preimage" tasks** — e.g., "find an arrangement of these 9 letters into a 3×3 grid such that all rows and columns are English words" with the generator built from a fixed published wordlist, verifier = membership in that list (disclosed vs. undisclosed as a knob). Generation is CSP-solve; verification is exact; search without a lexicon is hopeless.

**Rank: 1st overall in scientific payoff, 3rd in buildability** (generation is more engineering than TSP-style families; difficulty calibration is touchier).

### (f) Adaptive information acquisition across the execution boundary — *necessary, by construction*

**What creates it.** The instance is *deliberately not fully specified in the prompt*. Part of it is held by the harness, accessible only through query–response rounds — and the natural query channel is the execution boundary itself: each C∞ execution's stdout can contain queries; the harness answers in the next turn. C1 gets exactly one round (program runs, prints queries, never sees answers); C0 gets zero. If solving requires k > 1 rounds of *adaptive* information (round-t queries depending on round-(t−1) answers), C1's success probability is bounded information-theoretically — a **provable** ceiling, not an empirical one.

This is the cleanest possible necessary gap, and it's the only mechanism where we can *derive* the C1 ceiling in closed form before running anything (e.g., hidden integer in [1, N], one batch of q queries answered all-at-once gives C1 at most (q+1)/N... actually for batch queries with comparison answers, q non-adaptive comparisons distinguish at most q+1 outcomes vs. 2^q adaptively — the adaptive/non-adaptive query-complexity literature gives the exact gaps). The pre-registered prediction writes itself as a theory line on the plot, like H3's Lyapunov horizon.

**Design honesty.** This changes the C1/C∞ semantics: the gap is engineered by the information protocol, not discovered in the problem. That's a feature for the paper section on *why* iteration helps (it lets us put a known-size information gap under the conditions and check the model saturates it) but it should be reported as its own sub-experiment, not pooled with families where C1 could in principle win. Also note the model could be lazy in C∞ too — failing to query adaptively (the [OQA "planning gap"](https://openreview.net/forum?id=1qLZsyJN2t) finding, Part 2 §2.8, says frontier models leak 1–3 queries vs. the information-theoretic oracle) — so C∞ won't be at ceiling either; we get a three-way comparison against the oracle for free.

**Minimal isolating family.** Hidden-structure identification with a metered query API: hidden monotone threshold (binary search), hidden polynomial of degree d (point queries), hidden subset (membership queries), Mastermind-style codebreaking (the classic). Generator: sample the secret; verifier: exact match; knobs: secret-space size vs. query budget vs. answers-per-round.

**Rank: 1st in cleanness of isolation, 2nd in buildability** (needs one new harness capability: stdout-mediated query answering between C∞ turns, and a one-round variant for C1 — modest Inspect AI work).

### Mechanism interactions and a falsifiable summary table

| Mechanism | Gap type | C1 can close by... | Predicted transcript signature of C∞ advantage |
|---|---|---|---|
| (a) algorithm-selection | contingent | internal fallback/anytime loop | C∞ times a small run, then switches algorithms |
| (b) engineering fragility | contingent | defensive coding | C∞ fixes a crash/timeout on attempt 2 |
| (c) parameter tuning | contingent | internal multi-start/auto-tune | C∞ inspects residuals/score, adjusts constants |
| (d) regime opacity | contingent | internal regime test | C∞ runs a cheap diagnostic before solving |
| (e) model-resident objective | **necessary** (e2); partial (e1) | embedding knowledge dumps (e1 only) | C∞ generates candidates in code, judges them in prose, loops |
| (f) cross-boundary information | **necessary** (provable) | nothing (information-theoretic) | C∞ queries adaptively; C1 prints queries it never sees answered |

The pooled C1-vs-C∞ gap across a suite spanning these mechanisms decomposes into "model didn't plan to iterate" (a–d) vs. "no program could have" (e–f). That decomposition — not the gap itself — is the publishable object.

---

## Part 2 — Literature scan (2024–2026)

Claims verified against retrieved abstracts/texts unless flagged **[unverified]**. Crossword/SweepClip/CrossWordBench/LR2Bench evidence is in VARIATION_DIMENSIONS_LIT.md §5 and not repeated.

### 2.1 One-shot program generation vs. iterated loops: no clean controlled comparison exists

PAL ([Gao et al. 2022](https://arxiv.org/abs/2211.10435)) and Program-of-Thoughts established the C1-style paradigm (one program, interpreter executes, +15 points absolute over CoT on GSM8K with Codex). The survey literature ([Code to Think, Think to Code, 2025](https://arxiv.org/abs/2502.19411); [ACL anthology version](https://aclanthology.org/2025.emnlp-main.130.pdf)) explicitly taxonomizes "single execution" vs. "interactive" code-reasoning methods — but the comparison tables mix models, datasets, and prompting, so **no apples-to-apples C1-vs-C∞ number exists at matched problems**. Bi et al. (2023, cited therein) found PoT/PAL gains depend on code complexity — code helps less as the required program gets more complex — which gestures at our question but doesn't answer it. **Implication: our condition ladder on matched generated instances is genuinely rare; treat that as a positioning asset.**

### 2.2 Self-debugging: execution feedback buys 3–12 points on ordinary codegen — small, and front-loaded

[Chen et al., "Teaching LLMs to Self-Debug" (ICLR 2024)](https://arxiv.org/abs/2304.05128): with unit-test execution available, self-debugging improves baseline accuracy by up to 12% (MBPP, TransCoder); without execution (Spider), 2–3%, rising to 9% on the hardest split. Ablations: execution is the crucial ingredient; richer feedback (traces) helps consistently; **most of the gain arrives in the first debug round**. GPT-4 *without* execution gains only ~1–3.6%.

**Implication for us:** on problems where the program is short and the model understands the task (our five non-TSP families), the literature predicts exactly what we observed — C1 within a few points of C∞. The self-debugging delta is the (b)-mechanism's empirical size: single digits. **Persistent ≥20-point gaps will not come from debugging; they come from search/tuning/judgment mechanisms.** This is the strongest literature-side argument for building (a)/(c)/(e)/(f) families rather than gnarlier engineering.

### 2.3 Competitive programming: iteration gains grow with problem hardness

[AlphaCodium (Ridnik et al. 2024)](https://arxiv.org/abs/2401.08500): on CodeContests, GPT-4 pass@5 goes from 19% (well-designed direct prompt) to 44% with the test-based iterative flow (validation; 12%→29% test) — a 2.3× multiplier, vs. the ~1.1× typical of self-debugging on MBPP. The delta between MBPP-style (+3–12 points) and CodeContests-style (+25 points) tasks is the cleanest published evidence that **the value of iteration scales with the problem's algorithmic difficulty** — consistent with our TSP-only gap. Note AlphaCodium also matched AlphaCode2 with ~4 orders of magnitude fewer LLM calls, i.e., feedback-directed iteration ≫ blind sampling.

### 2.4 Theorem proving: the most decisive one-shot vs. interactive numbers anywhere

[SorryDB (2026)](https://arxiv.org/abs/2603.02668), real-world Lean theorems: one-shot whole-proof generation gets 6–8% pass@1 and 13–15% pass@32; **self-correcting iterative approaches with ≤16 iterations reach 27–30%** — iterative with 16 calls beats pass@32 with double the calls. The authors state "iterative feedback is the dominant factor in performance... much more helpful than longer reasoning budget or fine-tuning." [StepFun-Prover (2025)](https://arxiv.org/abs/2507.20199) reaches 70% pass@1 on miniF2F by RL-training tool-integrated iterative refinement; hierarchical/sketch-based RL work ([OpenReview](https://openreview.net/attachment?id=XzH1yRfhVW&name=pdf)) finds whole-proof generation suffers "exponential decay of proof rates with increasing proof complexity" while iterative variants plateau later.

**Why proving is the extreme case, in our taxonomy's terms:** the verifier (Lean) is exact, cheap, and gives *localized* error feedback; the solution space is vast; one-shot correctness probability decays multiplicatively in proof length. It combines mechanisms (b) at maximal severity (every step must type-check) with (d) (the proof state after each tactic is opaque until executed). It's the existence proof that C∞/C1 ratios of 2×+ persist at the frontier in feedback-rich formal domains.

### 2.5 Model-in-the-loop search systems (extreme C∞): what they imply about which problems need iteration

- [FunSearch (Romera-Paredes et al., Nature 2024)](https://www.nature.com/articles/s41586-023-06924-6): LLM-guided evolution over *programs* found new cap-set constructions and bin-packing heuristics — using **millions of LLM samples** against a fast programmatic evaluator. [AlphaEvolve (2025)](https://arxiv.org/abs/2506.13131) scales this to whole codebases with thousands of samples of stronger models.
- [Eureka (Ma et al., ICLR 2024)](https://openreview.net/pdf?id=IEduRUO55F) — reward-function design for RL: the key ablation for us is "Eureka w/o Evolution (32 samples)" vs. evolution with the same total sample count: **evolution wins at matched budget**, i.e., feedback-directed iteration beats blind parallel sampling, the same shape as AlphaCodium-vs-AlphaCode and SorryDB's iterative-vs-pass@k findings. This matched-budget comparison is rare and worth citing.
- What these systems collectively say about *which* problems need iteration: open-ended solution spaces (programs/heuristics, not answers), graded objectives with headroom above known baselines, and cheap programmatic evaluation. When the answer is a single determinate object computable by a known algorithm (our five clean families), iteration adds nothing; when the answer is the *best found so far* under a measurable objective, iteration is the whole game. Our C1-vs-C∞ axis is the small-budget version of this dichotomy.

### 2.6 Code agents vs. one-shot pipelines on SWE tasks: feedback matters most for long horizons; pipelines with internal sampling blur the line

[SWE-agent (NeurIPS 2024)](https://papers.nips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf) showed feedback *design* (compact editor feedback, linting) moves resolve rates by several points — and that more interaction isn't automatically better (their iterative-search interface *underperformed* no-search because agents exhaustively paged through results). Agentless (Xia et al. 2024) gets within a few points of agent scaffolds with a fixed three-stage pipeline — but note Agentless internally samples and *filters patches by regression tests*, i.e., it smuggles a C∞-style execute-and-select loop into a "one-shot" pipeline; it is not a C1 condition. A SambaNova analysis (2026, blog **[unverified beyond blog]**) reports even top models fail single-shot long-context SWE-bench while mini-SWE-agent loops succeed — "agentic scaffolding is essential." Self-correction caveats from VARIATION_DIMENSIONS_LIT.md §7 (contextual drag, self-correction blind spots) apply: iteration is not automatically self-improving.

### 2.7 Mechanism (e) literature: LLM-as-objective inside search loops, and ground truth for tacit judgment

- **LLM-as-judge inside evolutionary search works and validates against humans:** [QDAIF (Bradley et al., ICLR 2024)](https://qdaif.github.io/) puts the LM in MAP-Elites as *both* mutation operator and quality/diversity evaluator for creative text; human evaluation confirms "reasonable agreement between AI and human evaluation." This is the alternation-as-necessity paradigm running in the wild: neither the generator nor the judge is serializable into one program.
- **Furniture / indoor layout — the user's pet example — is a live LLM-era literature, and its recurring failure mode is exactly our hybrid conjecture in mirror image.** Yu et al.'s ["Make It Home" (SIGGRAPH 2011)](https://dl.acm.org/doi/10.1145/2010324.1964981) formalized layout as simulated-annealing over hand-coded ergonomic constraints (pairwise distances, clearance, visibility) learned/extracted from exemplars. The LLM-era line — LayoutGPT (2023), [Holodeck (2023/24)](https://arxiv.org/abs/2312.09067), I-Design, LayoutVLM, [FlairGPT (2025)](https://arxiv.org/abs/2501.04648), [OptiScene (2025)](https://wrap.warwick.ac.uk/id/eprint/194494/), [ReSpace (2025)](https://arxiv.org/abs/2506.02459), [Architect-Ant (2026)](https://arxiv.org/abs/2606.10953) — converges on a division of labor: **the LLM supplies semantic/commonsense constraints, an external solver supplies geometry**, because "layouts pass coarse semantic checks yet violate overlap, containment, door-clearance, and wall-affinity rules unless an external solver or post-hoc repair step intervenes" (Architect-Ant). That is mechanism (e) inverted: there, the *constraints* live in the model and the *search* needs the machine; one-shot LLM placement fails on geometry, pure solvers fail on semantics. Alternation isn't a luxury in this literature — it's the published architecture of every working system.
- **How researchers get ground truth for tacit objectives** (the desk-next-to-fridge problem):
  1. **Pairwise preference + Bradley–Terry/Elo aggregation.** The aesthetics literature now has clean evidence that comparison beats rating: [VAB (2026)](https://arxiv.org/abs/2605.12684) finds comparative ranking yields **42 percentage points higher inter-annotator agreement** on best-image selection than score-derived rankings; [PPaint (2026)](https://arxiv.org/abs/2605.19776) measures Kendall's W of 0.795 (pairwise) vs. 0.697 (ratings) among domain experts and fuses both into a calibrated ground truth. [Conformal Elo (2026)](https://arxiv.org/abs/2606.13221) adds distribution-free uncertainty intervals on LLM-judge-derived Elo vs. human Elo. And critically, [Correct Looks Better (2026)](https://arxiv.org/abs/2606.09409) shows that where programmatic ground truth *does* exist, Elo from pairwise judgments recovers accuracy rankings at Spearman > 0.9 — pairwise-preference pipelines are a *validated proxy* for mechanical verification, not a separate epistemic regime.
  2. **Consensus filtering with held-out raters:** VAB keeps only items where ≥10 independent experts agree under a dual threshold — operationalizing "high inter-rater agreement but no compact rule statement."
  3. **Learned reward models validated on held-out preferences**, with known caveats: reward models show "significantly lower agreement with human judgments on subjective dimensions" than on verifiable tasks, and rubric-extraction agents now outperform end-to-end RMs on tacit dimensions ([2026](https://arxiv.org/abs/2605.28882)) — tacit knowledge is "latent but not absent."
  4. **DPO on human-inspected synthetic corpora:** OptiScene's 3D-SynthPlace ("GPT synthesize, human inspect", ~17k scenes) then multi-turn DPO toward preferred layouts; symbolic-ontology evaluators validated against human preference ([SceneCritic, 2026](https://arxiv.org/abs/2604.13035)) as a middle path between hand-coded rules and black-box VLM judges.
  - **My read for Phase 2+:** if we ever want a furniture-flavored family, the rigorous-but-affordable recipe is (clearance/overlap/reachability verified mechanically) + (semantic quality scored by pairwise preference against a frozen reference layout, validated once on ~100 human pairwise judgments). That keeps a programmatic floor under a tacit ceiling. But the *first* mechanism-(e) family should stay fully mechanical (crossword/lexicon), per Design rule "no judged scoring" — the furniture version is a paper-2 extension.

### 2.8 Mechanism (f) literature: adaptive querying is a real, measured capability with known inefficiency

[OQA / The Information Game (OpenReview 2025/26)](https://openreview.net/forum?id=1qLZsyJN2t) benchmarks LLM querying against a game-theoretic-optimal oracle on 20-questions-style tasks: frontier models track near-binary-search entropy reduction but leak a **planning gap of 1–3 queries**; synthetic objects (no linguistic priors) widen the deficit. [BED-LLM (Apple, 2025)](https://arxiv.org/abs/2508.21184) shows explicit expected-information-gain planning substantially beats direct prompting at 20 Questions and preference elicitation. **Implication:** in our (f) family, C∞ will be good-but-suboptimal in a *predictable* way — we can plot model query efficiency against the information-theoretic line, our favorite plot shape (cf. H3). None of this work runs a one-shot-program condition; our C1 column would be novel there too.

### 2.9 What the literature does *not* contain (the gaps we'd fill)

1. No controlled one-program-vs-interactive comparison at matched, difficulty-swept, generated instances (closest: AlphaCodium's direct-vs-flow, but on static CodeContests with a multi-stage scaffold, not a minimal condition ladder).
2. Nobody reports the **incidence of self-iterating one-shot programs** (does the model embed its own search loop when it can't get feedback?) — our contingent/necessary decomposition appears to be unarticulated in print.
3. No information-theoretically derived C1 ceiling tested against models (the adaptive-vs-non-adaptive query complexity literature exists in TCS; nobody has put an LLM on those curves).
4. The matched-budget iteration-vs-sampling comparison exists only scattered (Eureka ablation, SorryDB, AlphaCodium vs AlphaCode); a difficulty-swept version is open.

---

## Part 3 — Recommended families

All buildable in our architecture (deterministic generator, programmatic verifier, parametric difficulty). Predicted C1 < C∞ by ≥20 points at the calibrated difficulty band; confidence in parentheses (subjective probability the ≥20-point gap shows at some difficulty level for Haiku-tier models). Ordered by recommended build priority.

### R1. Hidden-information query games — mechanism (f) — **build first**

**Family:** harness holds a secret (integer in [1,N]; degree-d integer polynomial; hidden subset of size k; Mastermind code). Prompt specifies the query protocol: any executed program may print `QUERY: <x>` lines; the harness appends answers to the transcript before the next turn. C1 = one round (queries answered, but no further execution — or zero rounds, both variants worth running); C∞ = ≤10 rounds. Verifier: exact match on the secret. Knobs: log₂(N) vs. round budget vs. queries-per-round.
**Predicted gap:** C1 ceiling is *provable* (non-adaptive query complexity); set knobs so the ceiling is ≤30% while adaptive solving is comfortably feasible → C∞ ≥ 80%. (0.9 — the gap is engineered; residual risk is only C∞ underperforming its budget.)
**Superadditive signature: yes by construction** — C0 ≈ random, C1 ≤ provable ceiling, C∞ alone can win. The "alternation is necessary" exemplar, with a theory line on the plot.
**Transcript signature:** C∞ halves the candidate space per round; C1 prints a batch of queries whose answers it never reads, then guesses.

### R2. Budget-trap optimization — mechanism (a) — **build second; it generalizes our only observed gap**

**Family:** planted-optimum problems where the exact algorithm crosses the published sandbox timeout partway up the difficulty sweep, and the natural greedy is reliably 10–20% suboptimal. Three instantiations from one harness pattern: TSP n=10→22 (Held–Karp crosses ~60 s near n≈21–22 in pure Python **[my estimate — calibrate empirically]**), subset-sum/knapsack where the DP table crosses memory limits, and argmax over an implicit combinatorial space where brute-force enumeration crosses the timeout. Score: optimal-found (binary) + approximation ratio.
**Predicted gap:** ≥30 points in the two levels straddling the feasibility boundary (we already measured 75 points at TSP n=16). (0.8)
**Superadditive: no** — C0 fails outright here; this is a pure C1-vs-C∞ instrument.
**Transcript signature:** C∞ runs a small timing probe or watches a heuristic's improvement curve, then escalates; C1 commits to whichever side of the budget its prior favors — and (the key logged metric) rarely writes an internal anytime loop.

### R3. Planted-parameter recovery with tight tolerance — mechanism (c)

**Family:** generate noisy-but-deterministic data (fixed seed) from hidden parameters of an ill-conditioned model: sum of two sinusoids with close frequencies; double-exponential decay; Gaussian mixture with a small component. Demand parameters to a tolerance calibrated so default-initialized one-shot `scipy.optimize` fails ~80% of the time while residual-inspection + multi-start succeeds. Verifier: distance to planted parameters. Knobs: conditioning (frequency separation), tolerance, dimensionality.
**Predicted gap:** 20–40 points at the calibrated band. (0.6 — the main risk is bimodality: either default fits work too often, or nothing works; needs a careful calibration pass.)
**Superadditive: no** (C0 fails; C1 vs C∞ is the contrast).
**Transcript signature:** C∞ prints residuals/loss, says "the fit converged to a local minimum," perturbs the initial guess; C1 ships the first `curve_fit` result.

### R4. Lexicon-constrained grid fill — mechanism (e) — **the architectural-thesis family (Phase 2, already planned as H11)**

**Family:** as PROBLEMS.md 6.1 / VARIATION_DIMENSIONS_LIT.md §5: CSP-generated word grids, mechanical verification against the generator's wordlist, wordlist disclosed vs. undisclosed as the key knob. Add the small-grid variant (3×3/4×4 "word squares") as the minimal cheap probe before full crosswords.
**Predicted gap (undisclosed wordlist):** C1 ≥20 points below C∞ — C1 wins only when the model embeds a from-memory lexicon *and* its lexicon overlaps the generator's (instrument this incidence; pre-registered at 0.55 it usually won't). (0.65)
**Superadditive: yes — the flagship candidate.** C0 lacks constraint propagation, C1 lacks the lexicon, C∞ alternates candidate generation (model) with constraint checking (code). If C∞@10-calls *also* plateaus below 50% on 7×7 while humans succeed, H11's strong form lands.
**Transcript signature:** C∞ writes a propagation engine, then *itself* proposes word candidates per slot between executions; C1 either hardcodes a wordlist (log it!) or attempts letter-frequency search and fails.

### R5. Regime-mixture instances — mechanism (d) — cheapest add-on, lowest standalone value

**Family:** 50/50 mixture per difficulty cell: instances with hidden exploitable structure (planted bipartite graph for max-cut; permuted-sorted array for search; planted short tour) vs. unstructured controls, mixture disclosed in prompt, structure detectable by a 5-line test. Score: optimality.
**Predicted gap:** 15–25 points, concentrated entirely in the structured half (C1 solves unstructured at parity). Riskiest prediction in this doc: a careful C1 program tests the regime internally and the gap vanishes — which would itself be the first evidence that planning-to-compute *can* be elicited, worth having. (0.45 — deliberately a coin flip, like H5b was.)
**Superadditive: no.**
**Transcript signature:** C∞ runs the diagnostic first ("checking if the graph is bipartite... it is"); C1 applies the general-purpose heuristic everywhere.

### Explicitly not recommended as a build target

A gnarly-parsing/engineering-fragility family (mechanism b): the self-debug literature caps its expected effect at ~10 points, it measures software engineering rather than reasoning, and it hands reviewers the "contrived benchmark" attack. Control it, categorize it in error analysis, don't build for it.

### Cross-cutting instrumentation (do these regardless of family choice)

1. **Log self-iterating-C1 incidence** (internal loops/retries/fallbacks/timing probes in one-shot programs) across all families — the contingent/necessary decomposition depends on it and nobody has published it.
2. **C∞ call-budget sweeps** (1/3/10 executions) on R1 and R4 — turns "iteration helps" into a dose-response curve, and for R1 the information-theoretic optimum is computable per budget.
3. **Score C1 with a "you may not get feedback — write defensively" prompt variant** on R2/R3/R5: if explicit instruction closes the contingent gaps, that's strong evidence the failures are planning defaults, not capability limits — and a cheap, publishable intervention.
