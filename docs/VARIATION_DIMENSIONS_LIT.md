# Dimensions of Problem Variation — Speculative Literature Survey

**Companion to [LITERATURE.md](./LITERATURE.md) (which this does not duplicate), [DESIGN.md](./DESIGN.md), and [EXPERIMENT_1.md](./EXPERIMENT_1.md). Status: v0.1, web-search-based survey (2026-06-12).**

Scope: what axes of variation in *generated* problems — beyond a scalar difficulty knob — does the literature suggest are interesting for probing LLM reasoning limits? For each axis: key papers, what is established, what is untested, and what it suggests we should vary in our six families (TSP, maze, 3-SAT, argmax, chaos, automata) under the C0/C1/C∞ condition ladder. Claims are based on abstracts/texts retrieved during this search; items not directly confirmed are flagged **[unverified]**. Note several citations carry 2026 arXiv IDs (26xx.*) — these are recent preprints, venue status often unknown.

---

## Executive summary — the five most promising under-explored axes for *this* project

Ordered by (scientific novelty × fit to our existing families and condition ladder):

1. **Serial depth vs. parallel breadth at matched total work.** Theory now cleanly says depth is the scarce resource (log-depth suffices for state tracking and connectivity; width and CoT are exponentially/superlogarithmically more expensive — Merrill & Sabharwal 2025), and empirics confirm sequential test-time scaling beats parallel on serial tasks. But **nobody has built matched-total-work wide/deep instance pairs within one problem family** and measured where the C0 cliff sits for each, let alone whether code conditions erase the difference. Our automata and argmax families can do this almost for free (one CA run of k steps on width w has work ≈ k·w; sweep the k:w aspect ratio at fixed k·w). This is the most theory-grounded open measurement we found.
2. **Error-propagation structure (Lyapunov-signed knob).** The literature on error compounding is all about *the model's* errors snowballing (hallucination snowballing, contextual drag); essentially nothing varies *the problem's* intrinsic error dynamics. Our chaos family generalizes naturally: sweep λ from negative (contractive — errors self-heal) through zero to positive (chaotic — errors amplify) at matched step count and digit budget. Prediction: C0 accuracy at fixed k should be a function of λ, not k. No prior work does this; it extends our pre-registered H3 into a full axis.
3. **Working-memory (state-size) load as a separate axis from step count.** 2025–26 work (PI-LLM, WMF-AM, BAPO-style variable tracking) establishes a finite, resource-like capacity (log-linear decay; ~5–10 tracked variables before chance) — but on retrieval/accumulation toys, never crossed factorially with serial depth in formal problems, and never against code conditions. CA grid width × iteration count is a clean 2-factor design; chaos offers map dimensionality (logistic 1D vs Hénon 2D vs higher).
4. **Surface-form invariance under the condition ladder (representation × familiarity × C0/C1).** Representation effects (EHOP, Talk-like-a-Graph, RRB) and familiarity/counterfactual effects (Wu et al., Embers of Autoregression) are *thoroughly established for direct answering* — and **entirely unmeasured for the code-writing condition**. Our thesis ("processing failure, not understanding failure") makes a sharp falsifiable prediction: C1 accuracy should be nearly invariant to renderings and counterfactual dressing that crater C0. If C1 is *also* brittle, the formalization step itself is pattern-matched — a major finding either way. Cheap to run: re-render existing instances.
5. **Verification ↔ generation flips within families.** The folk claim (verification easier than generation; Wei's "verifier's law") is now empirically contested — a 2026 line finds LLMs are often *worse* at verifying than solving, with epistemic (acceptance) bias and insensitivity to localized errors. Our generators produce certified instances and can emit near-miss candidates (tour with one swapped edge, SAT assignment with one flipped variable, CA trajectory with one corrupted cell), so we can measure whether the verification cliff sits at the same knob value as the generation cliff, per family, per condition. No prior work does this with difficulty-matched formal pairs.

Runners-up: **instance structure** (random vs. planted vs. adversarially-paired instances — the paired-SAT/ADR methodology is worth adopting outright), **interactivity** (partially observable maze where C1 must emit a *policy* rather than an answer — a genuinely new use of the condition ladder), and **solution-space density** (unique vs. many solutions at fixed size; note the finding that solution *compressibility* predicts difficulty far better than solution length).

Well-covered areas we should *not* claim as novel: scalar-difficulty cliffs (ZebraLogic, NPHardEval, seqBench, GSM-Infinite all do this), representation effects on direct answering, counterfactual brittleness as such, knowledge-coupled crossword solving with search scaffolds (surprisingly strong results exist — see §5, which complicates H11).

---

## 1. Serial depth vs. parallel breadth

**Key papers**

- Merrill & Sabharwal, *A Little Depth Goes a Long Way: The Expressive Power of Log-Depth Transformers* (arXiv 2503.03961, 2025): transformers with depth growing Θ(log n) can express regular-language recognition (state tracking) and graph connectivity — both inexpressible at fixed depth under standard conjectures. Crucially for us, the comparison is quantitative: achieving the same power by **width requires superpolynomial growth**, and by **CoT requires superlogarithmic steps**; experiments find practical training-depth requirements track the theory.
- Ramezanali, Vazifeh & Santi, *seqBench* (EMNLP 2025): a parametrized pathfinding benchmark with three independent knobs — **logical depth** (number of sequential actions), **backtracking count** (deferred-precondition detours), and **noise ratio** (distractor facts). Universal finding: accuracy collapses exponentially beyond a model-specific logical depth, even at minimal search complexity. The closest existing "multi-knob" design to ours.
- *Let Me Think! A Long Chain-of-Thought Can Be Worth Exponentially Many Short Ones* (arXiv 2505.21825, 2025): on adversarial graph-connectivity distributions ("two-path", "bridge" graphs) and AIME, sequential test-time scaling decisively beats parallel sampling at matched token budgets — with diminishing returns once serial scale is large, after which parallel becomes cost-effective.
- Liu, Preechakul, Kuwaranancharoen & Bai, *The Serial Scaling Hypothesis* (arXiv 2507.12549, 2025): position paper formalizing the work/depth distinction (Blelloch) for ML; argues inherently serial problems (reasoning, physics simulation, sequential decision-making) cannot be bought with parallel compute. Uses Sudoku's easy/hard distinction (parallel-fillable vs. dependent-chain) as the parable — directly the axis we want to operationalize.
- Counterpoint: *ParaThinker* (arXiv 2509.04475, 2025) reports native parallel-path generation beating sequential depth-scaling on AIME/MATH at matched budgets — evidence the answer is task-dependent (math contest problems are presumably more parallelizable than permutation composition).

**What's established.** Depth (serial computation) is the binding constraint for fixed transformers; CoT rents serial steps at characterized prices (see LITERATURE.md §1 for the Li et al./Merrill–Sabharwal CoT results); empirically, sequential test-time compute dominates parallel on inherently serial tasks and the reverse can hold on parallelizable ones.

**What's untested.** No one constructs **matched-total-work instance pairs within a single family** — wide-and-shallow vs. narrow-and-deep at equal work — and locates the C0 cliff in the (depth, width) plane. And no one asks whether the depth/width distinction *survives the code condition* (it shouldn't: Python executes both in microseconds — which is exactly the point of our design).

**What we should vary.** For cellular automata: fix k·w (steps × grid width), sweep the aspect ratio from (k=2, w=512) to (k=512, w=2). For argmax: number of modes (breadth of comparison) vs. nesting/composition depth of the function. Prediction: C0 iso-accuracy contours run along constant-depth lines, not constant-work lines; C1 contours are flat. This would be the cleanest "the architecture rations serial steps, not FLOPs" plot in the literature.

## 2. Working-memory / state-size load

**Key papers**

- Wang et al.(?), *Unable to Forget: Proactive Interference Reveals Working Memory Limits in LLMs Beyond Context Length* (arXiv 2506.08184, 2025) **[author list unverified]**: key-value update tracking under interference. Retrieval accuracy declines **log-linearly** along three orthogonal load axes (number of updates per key, number of keys tracked, value token-length) with no plateau, independent of context length — a finite, resource-like capacity, from 0.6B to 600B+ models.
- Hou et al., *WMF-AM: Probing LLM Working Memory via Depth-Parameterized Cumulative State Tracking* (arXiv 2603.27343, 2026): no-scratchpad cumulative tracking of K sequential operations; discriminative window K≈3–7, floors beyond K≈10; ablations isolate cumulative load from arithmetic skill and entity tracking; explicitly designed as a *recalibratable* knob.
- Zhang, Jian, Ouyang & Vosoughi, *Working Memory Identifies Reasoning Limits in Language Models* (EMNLP 2024): n-back tasks; capacity grows with scale but stays bounded under complex conditions.
- *(LLMs) Do Not Have Human-Like Working Memory* (arXiv 2505.10571, 2025): critique — n-back-style tests let models attend to context; designs tasks (number guessing, yes/no deduction) where state must be held *latently*, and finds consistent failure across 17 frontier models even with CoT.
- BAPO-line variable tracking (summarized in a Towards Data Science analysis of bounded-attention theory, 2025) **[primary paper not retrieved]**: frontier models regress to chance when tracking more than ~5–10 interacting variables, far below context limits.

**What's established.** A separable, finite "working memory" resource exists in LLMs, distinct from context length and from step count, with smooth log-linear (not cliff) degradation; different load types (count, update-depth, item size) are roughly interchangeable taxes on one budget. Note the contrast with our cliff-shaped C0 curves — load type may determine curve shape.

**What's untested.** Crossing state size × serial depth factorially in *formal algorithmic* problems (the load literature uses retrieval/accumulation toys); and whether the C1/C∞ conditions erase the state-size axis entirely (trivially they should — `list` is cheap — making any *residual* C1 sensitivity a formalization-failure signal).

**What we should vary.** CA: grid width w at fixed steps k (state size per step) vs. k at fixed w — partially overlapping with axis 1 but analyzed as memory-vs-depth rather than work-matched contours. Chaos: map dimensionality (logistic 1D → Hénon 2D → coupled 3–4D systems) at matched λ and k. Maze: corridor mazes (small frontier) vs. braided mazes (large frontier) at matched path length — frontier size is the working set of BFS-by-hand. Also worth checking whether C0 curve *shape* differs (log-linear for memory load vs. exponential for depth, per the two literatures).

## 3. Representation / encoding effects

**Key papers**

- Duchnowski, Pavlick & Koller, *A Knapsack by Any Other Name* (EHOP; Findings of EMNLP 2025): the same NP-hard instances rendered as textbook formulations vs. real-life "costume" vs. inverted-rule variants. LLMs systematically solve textbook framings best; reasoning models reduce but do not eliminate the gap. Directly: presentation is a difficulty knob at fixed abstract instance.
- Fatemi, Halcrow & Perozzi, *Talk like a Graph* (ICLR 2024): graph-to-text encoding (adjacency pairs vs. incident lists vs. named-friendship prose) changes accuracy by 5–60+ points on basic graph tasks; node-naming and question framing matter; graph *structure* interacts (cycle-check accuracy depends on whether cycles are common in the graph distribution). Follow-up work (arXiv 2402.07140) shows mere *edge ordering* (BFS vs. DFS vs. random listing) moves shortest-path accuracy from 42% → 70%.
- *Robust Reasoning Benchmark* (arXiv 2604.08571, 2026): 13–14 deterministic, reversible structural transformations of AIME problems (string reversals, 2D grid encodings, rail-fence) with the decode rule given in-prompt. Frontier models largely resilient; open-weights reasoning models collapse (some to 0%) via tokenization breakdown and "intra-query attention dilution" — accuracy on a final problem degrades as context fills with the model's own prior CoT. Also: horizontal vs. vertical snake layouts of the *same text* produce huge gaps (Gemini 98% → 65%), exposing 1D autoregressive bias.
- Singh & Strouse, *Tokenization counts* (arXiv 2402.14903, 2024): left-to-right vs. right-to-left digit grouping (forced by comma separators) substantially changes GPT-3.5/4 arithmetic; errors are *stereotyped*, not noise; the gap shrinks with scale. Claude tokenizers group digits R2L for this reason **[the Claude detail from secondary sources]**.
- *The Lookahead Limitation* (BlackboxNLP 2025): multi-operand addition fails exactly where cascading carries exceed a one-digit lookahead heuristic, regardless of tokenizer — a mechanistic account of why some formats are hard.

**What's established (thoroughly — this is a crowded axis for C0-style evaluation).** LLMs are not presentation-invariant: encoding, ordering, naming, framing, and tokenization all move accuracy at fixed abstract instance, sometimes by tens of points; failures are systematic (tokenizer-aligned, autoregressive-bias-aligned, frequency-aligned); the effect shrinks but persists in frontier reasoning models.

**What's untested.** **All of this is measured in direct-answer mode.** We found no work measuring whether the *formalization* step (read problem → write correct program) inherits the same brittleness. Also untested: presentation effects on *interactive* tool use (does a hostile rendering cost extra C∞ iterations?).

**What we should vary.** Two renderings per family minimum (maze: ASCII grid vs. edge list vs. prose directions; SAT: DIMACS vs. natural-language clauses vs. EHOP-style costume; chaos: decimal vs. fraction vs. symbolic initial conditions), crossed with condition. The headline statistic is the **representation × condition interaction**: large C0 main effect, near-zero C1 effect would be the cleanest "understanding is rendering-invariant, processing is not" result; a nonzero C1 effect would qualify H4 importantly.

## 4. Memorization / familiarity gradients

**Key papers**

- Wu, Qiu, Ross, Akyürek, Chen, Wang, Kim, Andreas & Kim, *Reasoning or Reciting?* (NAACL 2024): 11 counterfactual task variants (base-9 arithmetic, swapped chess rules, rotated coordinate systems, alternate Python indexing). Models retain above-random but heavily degraded performance on counterfactual versions — "approximate retrieval" rather than rule execution.
- McCoy, Yao, Friedman, Hardy & Griffiths, *Embers of Autoregression* (PNAS 2024): performance on *deterministic* tasks varies with task frequency (common vs. rare Pig Latin variant: 42% vs. 23%; ROT-13 vs. ROT-2), output probability (cipher decoding: 51% on high-probability outputs vs. 13% low), and input probability. The "teleological" framing — predict failures from the pre-training objective — is the right theoretical frame for this axis.
- Lewis & Mitchell, *Counterfactual analogies* (arXiv 2402.08955, 2024): GPT-4's analogical reasoning drops sharply on alphabet-permuted letter-string analogies — same abstraction, unfamiliar substrate.
- Adjacent, already in LITERATURE.md: GSM-Symbolic (value perturbation), Mystery Blocksworld (lexical scrambling). A 2024 Amazon-science line (*Inductive or Deductive?*) extends the base-arithmetic paradigm to bases 8/9/11/16 and finds deductive (rule-given) mode is the weak one.

**What's established.** Distance-from-training-distribution is a *graded, measurable* knob (task frequency estimable by corpus statistics; output probability directly computable), and it moves performance on tasks of identical formal complexity. This is among the most replicated findings in the field.

**What's untested.** The familiarity × condition interaction. Wu et al. ran a "code generation" probe on some tasks **[detail unverified]**, but no systematic counterfactual-variant sweep under an execute-the-model's-program condition exists. Also largely untested: familiarity as a *continuous* knob (base-10 → base-9 → base-7 → base-13 with frequency estimates) rather than a binary default/counterfactual contrast.

**What we should vary.** Counterfactual dressings of existing families: CA under a renamed/permuted rule table (rule 110 semantically, presented as an arbitrary lookup — vs. presented as "rule 110", which is heavily discussed in training data — contamination check *and* familiarity probe in one); chaos with the logistic map disguised by variable renaming and algebraic rearrangement vs. presented canonically; maze on hex grids. Sharp prediction from our thesis: **C1 rescue rate should be invariant to counterfactual dressing** (the model demonstrably "understands" because it formalizes correctly); any drop in C1 on counterfactual variants directly quantifies how much of "understanding" is itself recitation.

## 5. Knowledge-coupled vs. knowledge-free problems

**Key papers**

- Saha et al.(?), *Language Models are Crossword Solvers* (NAACL 2025) **[author list unverified]**: SOTA LLMs decipher cryptic clues 2–3× better than prior SOTA; with **SweepClip** (LLM-guided search exploiting grid constraints), GPT-4-Turbo reaches 93.1% character accuracy on NYT puzzles, 48% perfectly solved. Two findings matter for us: (a) the search loop with the model as clue-oracle *works* — directly relevant evidence against a strong version of H11; (b) the binding failure is **sub-token length counting** (can't reliably count letters in candidate answers, worse for rare words) — a processing failure inside the knowledge loop, exactly our wheelhouse.
- *CrossWordBench* (arXiv 2504.00043, 2025): controllable crossword generation (text + image renderings, prefill-ratio difficulty knob, direct vs. interactive evaluation modes); reasoning LLMs substantially outperform non-reasoning by exploiting crossing-letter constraints.
- *LR2Bench* (arXiv 2502.17848, 2025): six CSP families spanning knowledge-based constraints (crossword, acrostic, cryptogram) and knowledge-free ones (sudoku, logic puzzles); even DeepSeek-R1/o1-preview struggle — a ready-made knowledge-coupled vs. knowledge-free contrast within one benchmark.
- BALROG's "knowing-doing gap" (see §10) is the agentic version: models *state* the relevant knowledge but fail to deploy it inside the control loop.

**What's established.** Knowledge-in-the-loop problems are no longer reliably hard for model+search scaffolds at NYT-crossword scale; the failure modes that remain are computational adjuncts (length constraints, grid parsing) rather than knowledge retrieval per se; controllable generators exist (CrossWordBench).

**What's untested.** The precise H11 question — whether a *generated* knowledge-coupled family exists where C∞ (≤10 calls) plateaus below 50% while humans+laptop succeed — is open, but the SweepClip result shifts the prior: their loop used *many* more than 10 LLM calls. The interesting untested variable is **the knowledge-call budget**: accuracy as a function of allowed model-as-oracle invocations inside the search. Also untested: whether models *think to embed* knowledge resources (wordlists) in C1 programs — our pre-registered sub-prediction.

**What we should vary.** Keep the crossword-fill family for Phase 2 but (a) use anagram/cryptic clue types where SweepClip-style accuracy was lowest **[their per-type numbers unverified]**, (b) make tool-call budget the swept knob (C∞ with 1/3/10/30 calls), (c) instrument C1 programs for embedded-wordlist incidence. Add a matched knowledge-free control with identical grid structure (fill from an explicit given wordlist) to isolate the knowledge coupling itself.

## 6. Verification vs. generation asymmetry

**Key papers**

- Wei, *Asymmetry of verification and verifier's law* (blog, 2025): the framing everyone cites — tasks easy to verify will fall to RL; verifiability decomposes into objectivity, speed, scalability, noise, reward continuity. Our entire suite scores 5/5 on his criteria by construction (worth one line in the paper).
- Saad-Falcon et al.(?), *Weaver: Shrinking the Generation-Verification Gap with Weak Verifiers* (arXiv 2506.18203, 2025) **[author list unverified]**: defines the gap as Pass@K − success-rate-with-verifier-selection; weak verifiers (judges, reward models) are noisy and poorly calibrated, but weak-supervision aggregation closes most of the gap without labels.
- Srivastava, Damle & Padala, *Rethinking LLMs as Verifiers: When Verification is Harder Than Solving* (ICLR 2026 workshop): across benchmarks and model families, **verification accuracy is often below solving accuracy** on the same items. Mechanisms: *epistemic bias* (accepting plausible-but-wrong far more readily than rejecting), *perturbation insensitivity* (missing localized errors in near-correct solutions), strong dependence on rubric conditioning.
- *Trust but Verify!* survey (arXiv 2508.16665, 2025): organizes verifier design around the asymmetry; notes generative verifiers fail precisely on hard-to-verify tasks.
- GraphArena's hallucination taxonomy (already in LITERATURE.md) is the certificate-validity version: well-formatted but infeasible outputs grow with size.

**What's established.** The naive "models are better verifiers than generators" assumption is false in general; verification has its own failure modes (acceptance bias, near-miss blindness) that look suspiciously like our C0 processing failures (checking a 20-city tour's length *is* serial arithmetic; checking a SAT assignment *is* clause-by-clause state tracking).

**What's untested.** Verification as a function of a *difficulty knob* on formally certified instances: does the verify-cliff sit at the same knob value as the generate-cliff? Near-miss verification (candidate with exactly one error, error position randomized) as a parametric family. And the condition ladder applies to verification too (C1 = write a checker — trivial; so any C0-verify failure is again pure processing).

**What we should vary.** For each family, emit three candidate types at each difficulty level: correct certificate, near-miss (single-edit corruption), and random plausible. Score verify-accuracy vs. knob alongside generate-accuracy vs. knob. The chaos family is the marquee case: verifying a claimed trajectory requires re-doing the iteration (no asymmetry), vs. SAT where verification is genuinely O(m) — so the *theoretical* verification asymmetry itself varies across our families, and we can test whether models exploit it. We found no prior work making that within-suite contrast.

## 7. Error-propagation structure

**Key papers**

- Zhang, Press, Merrill, Liu & Smith, *How Language Model Hallucinations Can Snowball* (2023): models over-commit to early mistakes and generate downstream errors they can recognize as wrong in isolation (67–87% self-recognition).
- *Contextual Drag* (arXiv 2602.04288, Princeton PLI, 2026): failed attempts in context bias subsequent generations toward *structurally similar* errors (tree-edit-distance analysis); 10–20% drops across 11 models / 8 tasks; iterative self-refinement can collapse into self-deterioration; persists even after successful error recognition. Directly relevant to C∞: iteration is not automatically self-correcting.
- Tyen, Mansoor, Cărbune, Chen & Mak, *LLMs cannot find reasoning errors, but can correct them given the error location* (Findings of ACL 2024): mistake-*finding* is the bottleneck, not mistake-fixing — backtracking with oracle error locations restores performance.
- *Self-Correction Bench* (arXiv 2507.02778, 2025): systematic "self-correction blind spot" — models correct injected errors in others' outputs far better than identical errors in their own; appending "Wait" partially restores correction.
- Gan et al.(?), *Rethinking External Slow-Thinking: From Snowball Errors to Probability of Correct Reasoning* (arXiv 2501.15602, 2025) **[author list unverified]**: information-theoretic model connecting snowball errors to correct-reasoning probability; argues specific search frameworks matter less than total search scope.
- Faith and Fate's multiplicative error compounding (LITERATURE.md §2) is the foundational datapoint.

**What's established.** Model-side error dynamics: errors compound, self-detection is the bottleneck, own-context errors are sticky (drag), and these dynamics partially survive feedback. All of this is about the *model's* errors.

**What's untested.** **Problem-side error dynamics as a generator knob.** No work we found varies the *intrinsic* error-amplification structure of the task — whether the problem forgives or amplifies small slips — at matched step count. This is wide open and our chaos family owns it.

**What we should vary.** Three-level contraction knob at matched k and digit budget: λ < 0 (contractive maps — iterate to a fixed point/cycle; a sloppy intermediate digit self-heals), λ ≈ 0 (neutral/quasi-periodic — errors persist but don't grow), λ > 0 (chaotic — errors double every ~1/λ steps). Also a discrete analog in CA: rule classes by Wolfram class (class 1/2 self-organizing vs. class 3 chaotic vs. class 4) — does C0 accuracy at fixed k track the rule's error-spreading speed (Lyapunov-like spreading exponent of the CA)? Combined with H3 this turns "accuracy = p^k" into a two-parameter law: accuracy ≈ f(p, λ·k). Secondary: measure whether C∞ recovers differently on forgiving vs. amplifying problems (contextual-drag prediction: less than you'd hope).

## 8. Instance structure: random vs. adversarial vs. real-world-structured

**Key papers**

- *Satisfiability Solving with LLMs* (arXiv 2605.28602, 2026; also flagged in LITERATURE.md §4): introduces **paired formulas** — minimally different SAT/UNSAT counterparts via single-literal edits — and the Accurate Differentiation Rate (both members correct). Pairing eliminates the statistical cues that inflate accuracy on random instances (models classify nearly everything SAT); ADR cleanly separates reasoning-mode from heuristic-mode models and declines smoothly with n. Also tests representation invariance via reductions to Vertex Cover and 3D packing (decisions largely consistent across reductions).
- *SATBench* (OpenReview 2025): SAT formulas auto-wrapped in natural-language stories with solver-checked round-tripping — instance structure crossed with narrative dressing; difficulty controlled by clause/variable counts.
- Fatemi et al.'s graph-structure finding (ICLR 2024, §3 above): the *distribution* of instances matters independently of encoding — cycle-check is easy on graphs where cycles are base-rate-likely and hard on path graphs, i.e., models exploit instance-distribution priors, not procedures.
- Classical background: random vs. structured (pigeonhole, encoded Hanoi) SAT instances stress solvers in categorically different ways; industrial instances have community structure and low treewidth that CDCL exploits. Whether any of this transfers to LLMs is essentially unmeasured. EALG-style adversarial instance co-evolution against solvers exists **[unverified — surfaced only in search synthesis]**.
- Hazra et al.'s α-sweep (LITERATURE.md §4) is the random-ensemble baseline we already replicate.

**What's established.** LLM accuracy on random ensembles is inflated by base-rate exploitation; minimal pairs are the antidote. Instance-distribution priors leak into "reasoning". Almost nothing is known about LLMs on planted-solution, adversarial, or industrially-structured instances.

**What's untested.** (a) Planted-solution instances (guaranteed-SAT with hidden assignment; TSP with known-optimal planted tour): does the model *find* planted structure that makes classical search easy? (b) Adversarial instances tuned against the model (not the solver). (c) Structure that helps CDCL/2-opt (community structure, locality): does it help or hurt C0? Any of these is a paper-grade question; (a) is the cheapest.
 
**What we should vary.** Adopt paired/minimal-edit instances for SAT (and analogues: maze with one wall added that flips solvability of a path-length bound; tour with one edge weight perturbed across an optimality threshold) and report ADR-style both-correct rates — this kills base-rate confounds in our yes/no scoring at minimal cost. Add planted-solution SAT at α above the transition (hard for random, trivial if you find the plant) as a "does structure rescue C0" probe.

## 9. Solution-space geometry

**Key papers**

- Lin et al., *ZebraLogic* (ICML 2025; already in LITERATURE.md): search-space size as the complexity metric, plus Z3 conflict count as a solver-effort metric — two geometry-adjacent knobs, one family.
- *Pencil Puzzle Bench* (arXiv 2603.02119, 2026): 62,231 puzzles across 94 varieties, every instance SAT-solver-certified to have a **unique** solution, with step-level verification. Headline analytical finding for us: **solution compressibility (compression ratio of the move sequence) predicts solve rate ~4× better than move count** — i.e., the *algorithmic regularity of the solution path*, not its length, is the operative difficulty variable. This is a genuinely novel difficulty-knob candidate.
- *NPPC: Nondeterministic Polynomial-time Problem Challenge* (OpenReview, 2025): 25 NP-complete problems with unlimited instance generation ("ever-scaling"); drives advanced LLMs below 10%; replicates the token/"aha-moment" rise-then-fall as instances harden (the Illusion-of-Thinking token-collapse signature, independently observed — useful corroboration for H9).
- *LR2Bench* (§5): constrainedness explicitly framed via solution-space ratios across six CSP families **[level of analysis unverified]**.
- Background: the constrainedness parameter κ generalizing the SAT α-transition to CSPs exists in the classical literature (Gent et al. 1996) **[not surfaced in this search; general knowledge]**.

**What's established.** Search-space size produces robust collapse curves (ZebraLogic's "curse of complexity"); unique-solution certification at scale is practical (SAT-solver pipelines); solution-path compressibility beats solution length as a difficulty predictor.

**What's untested.** **Solution count/density as a controlled knob at fixed instance size.** Nobody generates, e.g., 7-variable SAT instances with exactly 1 vs. 10 vs. 1000 satisfying assignments and measures C0 accuracy against density (theory: more solutions = easier for blind guessing *and* for local search; unclear for LLM pattern-completion). Similarly untested: basin-of-attraction size for argmax (how much of the domain funnels to the global optimum), number of optimal tours for TSP (degenerate vs. unique optima).

**What we should vary.** Solution-count-controlled SAT (model-counting tools make this generable); maze with unique vs. many shortest paths; argmax with sharp isolated global optimum vs. broad dominant basin at matched mode count. Also: compute solution compressibility for our maze/automata answers retroactively from Experiment 1 logs — a free analysis that tests the Pencil-Puzzle-Bench finding on our data.

## 10. Interactivity / observability

**Key papers**

- Paglieri et al.(?), *BALROG* (ICLR 2025) **[author list unverified]**: agentic evaluation on BabyAI → NetHack. Models manage easy games, flatline on NetHack (best: 1.5% progression); the **knowing-doing gap** — models can state the game knowledge they then fail to act on; vision input makes things *worse*.
- *EvoEmpirBench* (AAAI 2026): locally-observable maze navigation and match-2 elimination where each action structurally changes the environment; mainstream models show key limitations in dynamic spatial reasoning and long-term memory.
- *Evaluating Interactive Reasoning in LLMs: A Hierarchical Benchmark with Executable Games* (arXiv 2606.00103, 2026): 474 executable games × 5 difficulty levels where the model receives only the rules and must *actively query* to reduce uncertainty — "reasoning as sequential information acquisition", explicitly contamination-resistant since there's no fixed prompt-answer pair.
- Adjacent: Searchformer (LITERATURE.md §3) shows token-serialized search is learnable; TextWorld/MiniHack are the older substrate.

**What's established.** Interactive, partially observable settings are much harder than static ones for current models, with the knowing-doing gap as the signature failure; active-querying benchmarks exist as of 2026; long-horizon exploration remains near-floor (NetHack).

**What's untested.** A *controlled within-family* comparison — the same maze instance presented (a) fully observed vs. (b) fog-of-war with an explore/move API — at matched difficulty knob, isolating observability from all the confounds (graphics, rules complexity, horizon) that differ across BALROG-style suites. Also: the condition ladder mutates interestingly — in a partially observable setting **C1 must emit a policy (program with a sensing loop), not an answer**, and C∞ becomes "the model is the policy". No literature contrasts model-as-policy vs. model-writes-policy; closest is general agent-scaffolding work.

**What we should vary.** Add a fog-of-war maze variant: same generated mazes, observation = k-cell radius, actions = move/sense. Conditions: C0 (impossible by design — include as sanity floor), C1 (write a Python policy against our API — tests whether the model can formalize *exploration*, e.g., emit wall-follower or frontier-BFS), C∞ (model acts step by step). Prediction worth registering: C1-policy ≈ C∞ ≫ C0 again, which would extend the thesis from computation to *control*.

## 11. Recent procedurally generated suites — what knobs exist, what they found

A compact map of the 2024–2026 generator-benchmark landscape and the knobs each turns (excluding those already in LITERATURE.md: DyVal, NPHardEval, GSM-Symbolic, ZebraLogic, GraphArena):

- **Reasoning Gym** (Stojanovski, Stanley, Sharratt, Jones, Adefioye, Kaddour & Köpf; NeurIPS 2025 spotlight): 100+ procedural generators with verifiers across algebra, algorithms, graphs, logic, games; design principles = algorithmic verifiability, large solution spaces (anti-reward-hacking), parametric difficulty for curricula. Primarily an RLVR *training* resource, but its generator catalog overlaps several of our families (worth a related-work paragraph and possibly code reuse; MIT-style license **[unverified]**).
- **GSM-Infinite** (arXiv 2502.05252, 2025): computational-graph generator for GSM-style problems with independent knobs for reasoning complexity (graph ops) and context length (noise nodes/edges — *non-retrievable* noise, defeating RAG). Findings: sigmoid accuracy decline in complexity; **exponential inference compute buys linear performance** — a quantitative version of our H9.
- **seqBench** (EMNLP 2025; §1): depth / backtracking / noise-ratio knobs; exponential depth collapse.
- **NPPC / npgym** (2025; §9): 25 NP-complete generators, "ever-scaling" manifesto (scale over complexity, instance, oversight, coverage); token rise-then-fall replication.
- **CrossWordBench** (2025; §5): prefill-ratio knob, dual text/image rendering, direct vs. interactive modes.
- **Pencil Puzzle Bench** (2026; §9): 94 varieties, step-level verification, compressibility finding.
- **SATBench** (2025; §8): formula → story pipeline with round-trip validation; SAT/UNSAT balance as a knob.
- **WMF-AM** (2026; §2): depth-K cumulative-load probe, explicitly recalibratable.
- **SCALER** (Research Square preprint, 2025–26 **[unreviewed]**): claims a multi-dimensional complexity metric — reasoning depth, branching factor, working-memory load, domain parameters — across six domains with verified solutions. Closest in *stated* ambition to a multi-axis design; worth tracking, but preprint status and no model findings retrieved.
- **Robust Reasoning Benchmark** (2026; §3): transformation taxonomy as the knob.
- **Sudoku-Bench** (Seely et al., 2025) **[only seen via citation table]**: variant sudokus designed "easy for humans, hard for AI".

**Synthesis.** The field has converged on generators-not-datasets, and on scalar difficulty knobs (size, clause count, search space). What remains rare: (a) **factorial designs** crossing two hardness sources at matched totals (only seqBench and the unreviewed SCALER even gesture at it); (b) **condition ladders** (think vs. one-shot code vs. interactive tools) crossed with any knob — we found *no* suite doing this; (c) problem-side error dynamics (§7) and solution-density (§9) knobs — absent everywhere. Those three gaps are exactly where our marginal value lies.

---

## Cross-cutting design notes

1. **Curve shape is a fingerprint.** The literatures report different functional forms for different load types: exponential decay in serial depth (seqBench, our H2), log-linear in working-memory interference (PI-LLM), sigmoid in composite complexity (GSM-Infinite). If these shapes are reproducible signatures of *which* resource binds, a single family swept along two axes should show the shape switching — a much stronger mechanistic claim than any single cliff.
2. **Minimal pairs beat ensembles.** The paired-SAT/ADR move (§8) generalizes: wherever our scoring is binary over a base-rate-skewed ensemble, single-edit pairs immunize against statistical-cue exploitation. Cheap retrofit.
3. **The C1 column is our unique instrument.** Nearly every axis above is established for direct answering and unmeasured for write-then-execute. Each axis where C1 turns out *invariant* sharpens "processing not understanding"; each axis where C1 is *also* sensitive (representation? counterfactual dressing?) localizes a failure in formalization itself. Either result is publishable per axis; the *profile* across axes is the paper.
4. **Watch the token-collapse replication.** NPPC independently observed thinking-token rise-then-fall near the capability edge. Our H9 token-spend curves should be plotted against this and Illusion-of-Thinking from day one.
