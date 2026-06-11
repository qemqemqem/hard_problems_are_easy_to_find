# PROBLEMS — Brainstorm

**Companion to [DESIGN.md](./DESIGN.md). Status: brainstorm, v0.1.**

Organizing principle: each problem family is classified by **why** it is hard for an LLM (the four-category taxonomy from DESIGN.md §1), and each entry sketches: the generator, the scorer, the difficulty knobs, and why token-level reasoning specifically struggles. ★ marks Phase 1 shortlist candidates.

A good family satisfies: **cheap to generate, cheap to verify, parametrically hard, and short to state** (the prompt shouldn't need to be huge for the problem to be hard — though some families use prompt size itself as the difficulty knob).

---

## Category 1 — Formally hard for everyone (NP-hard and friends)

The model fails because everything fails. Interesting measurements: where is the cliff relative to instance size? Does the model degrade gracefully (good approximations) or catastrophically (invalid answers)? Does it *know* it's beaten?

### 1.1 ★ Traveling Salesman (TSP)
- **Generator:** n random points in a plane (or random distance matrix); compute optimum with a classical solver at gen time (exact for n ≲ 15–20 via Held-Karp/branch-and-bound; certified bounds or Concorde for larger).
- **Prompt:** coordinate list, "give the shortest tour as a permutation."
- **Scorer:** gradated — tour validity + approximation ratio vs. optimum. Also compare against cheap classical baselines (nearest-neighbor, 2-opt): *does the model beat greedy?* is a beautiful, brutal question.
- **Knobs:** n, metric vs. random matrix (random matrices kill geometric intuition).
- **Why interesting:** gradated scoring gives smooth curves, not just cliffs; famous enough for the blog post.

### 1.2 ★ SAT at the phase transition
- **Generator:** random 3-SAT with clause/variable ratio ≈ 4.27 (the empirically hard region). Filter through a SAT solver for satisfiability ground truth.
- **Scorer:** if model says SAT, it must provide an assignment → verify in linear time (no trusting "yes"). If UNSAT, binary against solver ground truth.
- **Knobs:** n variables, clause ratio (sweeping ratio across the phase transition is itself a gorgeous plot).
- **Why interesting:** the verification asymmetry is maximally clean; phase-transition structure connects to a deep literature.

### 1.3 Graph coloring / vertex cover / clique
- Random graphs G(n, p); ask for a k-coloring / cover of size ≤ k / clique of size ≥ k. Verifier is trivial. Knobs: n, p, k relative to the true optimum (asking for exactly-optimal is brutal; asking for slack-k measures graceful degradation).

### 1.4 Subset sum / knapsack / bin packing
- Small integer instances are famously LLM-friendly-looking but search-explosive. Subset sum with dense vs. sparse targets; knapsack scored by ratio to optimum (DP gives exact optima cheaply at gen time — note these are only *weakly* NP-hard, which is worth a footnote in the paper).

### 1.5 Hamiltonian path / Sokoban-like puzzle planning
- Sokoban is PSPACE-complete (technically Category 1+; see 5.x). Hamiltonian path on random graphs near the connectivity threshold; certificate = the path, verified trivially.

---

## Category 2 — Easy programmatically, hard by thinking (P, but computationally deep)

The scandal category: ten lines of Python solve these exactly, and models fail. Hardness comes from **serial computational depth** — transformers compute bounded-depth circuits per token; chain-of-thought buys depth at the price of tokens and compounding per-step error. Expected signature: accuracy ≈ (per-step accuracy)^(depth) — exponential decay in depth.

### 2.1 ★ Grid pathfinding (mazes)
- **Generator:** random maze (DFS/Wilson's algorithm) or grid with random obstacles; ask for a shortest path between two cells, as a move sequence.
- **Scorer:** validity (no wall collisions, reaches goal) + optimality (length vs. BFS optimum) — three-level score: invalid / valid-suboptimal / optimal.
- **Knobs:** grid size, obstacle density, maze vs. open grid, ASCII map vs. coordinate-list presentation (presentation-format sensitivity is a finding in itself).
- **Why interesting:** BFS is ~10 lines; humans solve mazes visually with ease; the model must do spatial state tracking in text.

### 2.2 ★ Iterated function / automaton simulation
- **Generator:** simple deterministic systems — elementary cellular automata (incl. Rule 110), Game of Life on a small torus, register machines / tiny assembly programs, "apply this permutation k times".
- **Scorer:** exact match on final state.
- **Knobs:** state size, **number of steps k** (the depth knob in its purest form).
- **Why interesting:** cleanest possible test of serial-depth limits; ground truth costs microseconds.

### 2.3 Long arithmetic & algebra
- Multiplication of n-digit numbers, modular exponentiation, polynomial expansion, determinant of an n×n integer matrix. Knob: n. Well-trodden (good for related-work anchoring) but cheap to include and the curves calibrate the suite.

### 2.4 Parity, counting, and state tracking
- Parity of an n-bit string presented in prose; counting occurrences of a token under distractors; tracking k objects through a long sequence of swaps ("box A and box C exchange contents…"). Knobs: n, k, distractor density. Directly targets known architectural weaknesses (parity is the classic transformer-hard function).

### 2.5 Sorting / order statistics at scale
- "What is the 37th-smallest number in this list of 500?" Exact match. Hardness from attention precision over long unstructured lists, not depth — a useful contrast to 2.2.

---

## Category 3 — Chaos and inverse problems (verification easy, search/precision hard)

### 3.1 ★ Chaotic dynamical systems
- **Generator:** logistic map (r = 3.9...), Hénon map, double pendulum / Lorenz (discretized, with the integrator pinned and specified in the prompt to make ground truth exact).
- **Prompt:** system definition + initial condition (given to full precision) + "state after k steps, to 4 decimal places."
- **Scorer:** gradated — number of correct digits, or divergence step (first step where the model's implied trajectory leaves an ε-tube). 
- **Knobs:** k (horizon), required precision, system. Lyapunov exponents give a *theoretical prediction* for the achievable horizon under fixed per-step precision — a rare chance for theory-vs-measurement plots in an LLM eval.
- **Note:** maps (logistic/Hénon) are preferable to ODEs for v1 — exact arithmetic ground truth, no integrator ambiguity.

### 3.2 ★ Argmax / inverse function problems
- **Generator:** explicit nasty function (e.g., sum of sinusoids + polynomial, random Fourier features) on an interval or integer domain; ask for the argmax, or "find x such that f(x) = y".
- **Scorer:** gradated — f(model's x) / f(true argmax), or |f(x) − y| tolerance. Ground truth by grid search/exact methods at gen time.
- **Knobs:** number of modes, domain size, dimension.
- **Why interesting:** evaluation is one substitution; search is global. Cleanest "inverse problem" framing.

### 3.3 Constraint-satisfaction inversions
- Cryptarithms (SEND+MORE=MONEY, generated fresh), Latin-square / Sudoku completion with parametric blank count, "find an input string whose SHA-256-truncated-to-b-bits equals X" (b = 8…20 sweeps from easy to hopeless; careful framing — this is *designed* impossibility and should be a sidebar, not a headline).
- Program-input synthesis: given a 5-line Python function and a target output, find an input. Verifier just runs the function.

### 3.4 Sequence inversion / preimage under iteration
- Given the state of a cellular automaton or map after k steps, recover the initial state (when injective or with certificate checking). Pairs beautifully with 2.2: same systems, forward vs. inverse, P vs. NP-hard-ish — a controlled within-family comparison.

---

## Category 4 — Reasoning-internals probes

Less "complexity theory", more "what is reasoning made of". These overlap with Category 2 but are *designed* around suspected mechanisms.

### 4.1 Compositional depth (function composition)
- Define k simple named functions; ask for (f₃ ∘ f₇ ∘ …)(x) with composition chains of length d. Knob: d, k. Probes whether CoT actually executes compositions or pattern-matches.

### 4.2 Needle-free long-context state
- A long narrative where an object's state changes n times under paraphrase variation ("the key moved", "Alice pocketed it"…). Final question: where is the key? Knobs: n, narrative length, paraphrase diversity. (Distinct from needle-in-haystack: every update *must* be integrated; nothing can be skipped.)

### 4.3 Self-referential / fixed-point questions
- "How many words are in your answer to this question?" / "Write a sentence containing exactly as many 'e's as it claims." Verifiable, cute, and probes a genuinely different mechanism (output planning). Blog-post gold; paper sidebar.

### 4.4 Adversarial instances for known heuristics
- Generate instances where greedy/intuitive heuristics fail badly (TSP instances adversarial to nearest-neighbor; SAT instances where pure-literal intuitions mislead). Measures whether the model is *doing* search or *mimicking* heuristics. Requires Category 1 infrastructure first — Phase 2.

---

## Category 5 — Beyond NP (sidebar material)

- **QBF** (PSPACE-complete): tiny quantified boolean formulas; ground truth from a QBF solver. The "∀∃∀" alternation depth is a beautiful knob.
- **Generalized game endgames** (EXPTIME flavor): small-board Hex / generalized tic-tac-toe positions, "who wins with perfect play?" — solvable at gen time by retrograde search at small sizes.
- **Halting-flavored** (undecidable in general, decidable for the generated subset): "does this 6-line program terminate within 10⁶ steps?" Ground truth by running it. Framing must be careful (we only generate decidable instances) — paper sidebar on the undecidability horizon.

---

## Category 6 — Hybrid linguistic × computational problems (the frontier conjecture)

**Conjecture (pre-registered as H11):** there exist problems where *no single program suffices* and even unlimited interactive python (C∞) underperforms, because candidate evaluation requires linguistic/world knowledge that lives in the model, while the search requires computation that lives in the machine. Solving them needs fine-grained alternation — the model as an oracle *inside* the search loop. If true, this is the strongest evidence in the suite that "transformer + REPL" is a workaround rather than an architecture. Either outcome is informative; this is the highest-uncertainty, highest-payoff category. Phase 2.

### 6.1 ★(Phase 2) Anagram-clue crossword fill
- **Generator:** build a small crossword grid from a fixed wordlist (CSP solve at generation time — guaranteed solvable, answer key known); clue each entry mechanically, e.g. anagram clues ("rearrange 'silent'"), definition-by-synonym from a thesaurus table, or first-letters clues. Fully mechanical generation *and* verification, yet solving requires vocabulary knowledge (which anagram is a real word that *also* fits the crossing letters) interleaved with constraint propagation.
- **Scorer:** exact grid match (or per-cell score). 
- **Knobs:** grid size, wordlist size disclosed vs. undisclosed, clue type mix.
- **Why hybrid:** a program can propagate constraints but can't rank candidate words without the model; the model can rank words but can't propagate constraints reliably (C0). The open question is whether C1 code that embeds a vocabulary list closes the gap — *we don't know*, which is exactly the point.

### 6.2 Natural-language-constrained packing/scheduling
- NP-hard core (scheduling/knapsack) with constraints stated idiomatically in prose ("Alice refuses to work weekends unless Bob is also on shift, but she's flexible during the holidays…"). Formalization requires commonsense disambiguation; solving requires search. Scorer: mechanical check against the formal constraint set used by the generator. Risk: formalization ambiguity must be controlled (generator works backward from formal constraints to templated-but-varied prose).

### 6.3 Constrained meaningful text generation
- "Write a grammatical English sentence of exactly n words where word i has f(i) letters" / lipogram-with-content tasks. Formal part verified mechanically; "meaningfulness" is the judged part — which violates our no-judge rule, so this stays brainstorm-only unless a mechanical proxy (parser + wordlist) proves sufficient.

### 6.4 Proof/derivation search with semantic lemma selection
- Equation-chain puzzles where the search space is huge but human-meaningful intermediate forms guide the search. Hard to generate with certified difficulty; speculative.

**Prediction sketch:** 6.1 is the buildable one. C0 fails early; C1's fate depends on whether the model thinks to embed a wordlist (itself a finding about planning-to-compute); C∞ should do best but we conjecture a residual gap at larger grids. See HYPOTHESES.md H11.

---

## Cross-cutting design notes

1. **Decision vs. certificate.** Never trust a bare yes/no on hard decision problems — a coin flip gets 50%. Demand certificates wherever the answer is "yes" (assignment, tour, path), and use solver ground truth for "no". Report certificate-validity rate separately from correctness.
2. **Graceful-degradation metrics are the good plots.** Approximation ratios, digits-correct, divergence horizons. Binary accuracy gives cliffs; gradated scores give curves with shape worth explaining.
3. **Within-family forward/inverse pairs** (2.2 ↔ 3.4, function eval ↔ argmax) are the strongest controlled comparisons in the suite — same surface form, wildly different complexity.
4. **Presentation effects** are a confound *and* a finding: ASCII maze vs. adjacency list, prose parity vs. bit-string parity. Fix one canonical presentation per family for headline numbers; run presentation ablations on a subset.
5. **Instance filtering:** reject degenerate instances (trivially-satisfiable SAT, mazes with the goal adjacent to start) at generation time; document the rejection rules — they're part of the generator's spec.
6. **Difficulty calibration pass:** before big runs, binary-search each family's knobs on the cheap model to find the 90%→10% accuracy band; concentrate the instance budget there.

## Proposed Phase 1 shortlist (one per category, +1)

| Family | Category | Scoring | Why first |
|---|---|---|---|
| 1.1 TSP | NP-hard | approximation ratio | gradated, famous, classical baselines |
| 1.2 3-SAT @ phase transition | NP-hard | certificate verification | cleanest verification asymmetry |
| 2.1 Maze pathfinding | P-but-deep | validity + optimality | "10 lines of Python" punchline |
| 2.2 Automaton simulation | P-but-deep | exact match | purest depth knob |
| 3.1 Logistic/Hénon map | chaos | digits / divergence horizon | theory-predicted curves (Lyapunov) |
| 3.2 Argmax | inverse | value ratio | cleanest inverse-problem framing |

(Trim to 4 if Phase 1 budget demands; cut 3.2 and 1.2 first.)
