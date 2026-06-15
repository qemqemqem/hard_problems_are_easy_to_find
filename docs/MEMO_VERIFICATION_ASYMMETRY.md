# Memo — The Verification Asymmetry That Isn't

**Status: memorandum, 2026-06-12. Sources: VARIATION_DIMENSIONS_LIT.md §6–7, LITERATURE.md, Experiment 1 transcripts. Context: this memo records a prediction reversal — the agent's pre-registered intuition about verification was probably backwards, and the literature found in the 2026-06-12 scans says why.**

## The formal picture

NP is *defined* by the asymmetry: a problem is in NP iff a claimed solution (certificate) can be checked in polynomial time, while finding one may require exponential search. Checking a SAT assignment is one pass over the clauses; checking a tour's length is n additions; checking a maze path is a walk. Every NP-ish family in our suite has verification that is formally trivial relative to generation. The folk inference — popularized as the "verifier's law" framing (Wei, *Asymmetry of verification and verifier's law*, blog, 2025) — is that machine-learned solvers should therefore be much better at verifying than generating, and that easily-verified tasks will fall first.

## The empirical picture: LLMs often verify worse than they solve

The recent literature contradicts the folk inference for LLMs:

- **Srivastava, Damle & Padala, *Rethinking LLMs as Verifiers: When Verification is Harder Than Solving* (ICLR 2026 workshop):** across benchmarks and model families, verification accuracy is often *below* solving accuracy on the same items. Two mechanisms: **epistemic/acceptance bias** (the model accepts plausible-but-wrong candidates far more readily than it rejects them — the "positivity bias" of this memo's title) and **perturbation insensitivity** (near-miss blindness: localized errors in almost-correct solutions go undetected). Verification quality also depends heavily on rubric conditioning.
- **Tyen, Mansoor, Cărbune, Chen & Mak (Findings of ACL 2024), *LLMs cannot find reasoning errors, but can correct them given the error location*:** mistake-*finding* is the bottleneck, not mistake-fixing — given an oracle error location, backtracking restores most performance. Verification fails at localization, not repair.
- **Self-Correction Bench (arXiv 2507.02778, 2025):** a systematic "self-correction blind spot" — models detect injected errors in *others'* outputs far better than identical errors in their own, which makes self-verification the worst case of an already weak capability.
- **Zhang, Press, Merrill, Liu & Smith, *How Language Model Hallucinations Can Snowball* (2023):** models recognize 67–87% of their own earlier errors when those are presented in isolation — the knowledge needed for verification is present, but it doesn't get applied once the error sits inside a committed-to context. Positivity bias toward one's own transcript, mechanically demonstrated.
- **Weaver (arXiv 2506.18203, 2025; author list unverified):** quantifies the generation–verification gap (Pass@K vs. success-with-verifier-selection) and finds weak LLM verifiers noisy and poorly calibrated, requiring aggregation to be useful.
- **Trust but Verify! survey (arXiv 2508.16665, 2025):** organizes the verifier-design literature around exactly this failure: generative verifiers fail precisely on the hard-to-verify tasks the verifier's-law argument needs them for.

## Our own evidence (Experiment 1, preliminary)

The C0 SAT transcripts are a clean in-house instance of acceptance bias: the model walks all 43 clauses of an instance, marks every single one with a checkmark ("39. (F OR T OR F) = T ✓"), and submits an assignment that violates clause 10. It performed the verification procedure, line by line, and the procedure output "accept" anyway. 48 of 80 C0 SAT failures were this pattern — a broken certificate presented as verified. (Related: Hazra et al.'s SAT work, LITERATURE.md, found certificate validity collapsing faster than yes/no accuracy; GraphArena's hallucination taxonomy — well-formatted but infeasible solutions growing with instance size — is the same phenomenon from the generation side.)

## Why the formal argument fails to bite

The complexity-theoretic asymmetry is about *step count*; the LLM failure is about *fidelity under bias*. Verifying a 43-clause certificate is formally O(m), but executing O(m) serial bookkeeping steps without error is precisely what C0 models cannot do (the whole point of this project) — and worse, the errors are not symmetric noise: they are systematically biased toward acceptance. A verifier that errs toward "yes" is worth little even when the procedure is short. Two further wrinkles from our suite: (1) for chaos and automata, verification is *not* formally cheap — checking a claimed trajectory requires re-running the same serially-deep computation, so the suite contains both verification-cheap and verification-deep families; (2) this within-suite contrast lets us test whether models' verify-vs-generate gap tracks the *theoretical* asymmetry at all, which nobody has measured on difficulty-matched certified instances (open gap per VARIATION_DIMENSIONS_LIT.md §6).

## What we plan to do about it (registered direction, not yet run)

Emit three candidate types per instance from existing generators — correct certificate, near-miss (single-edit corruption: one flipped variable, one swapped tour edge, one corrupted cell), random-plausible — and measure verification accuracy vs. the same difficulty knob as generation, per family, per condition. Predictions worth registering when this becomes an experiment: acceptance bias shows up as asymmetric error (false-accept ≫ false-reject), near-misses are the hardest class, C1 verification is near-perfect everywhere a checker is writable (verification code is shorter than solving code — making C0-verify failures the purest processing-failure demonstration in the project), and the C0 verify-vs-generate gap tracks formal asymmetry on SAT/TSP/maze but vanishes on chaos/automata.

## One-line summary

Theory says checking is easy and finding is hard; LLMs invert this in practice because their verification errors are biased toward acceptance and blind to near-misses — they can find answers they cannot then be trusted to judge, and our SAT transcripts show the checkmarks to prove it.
