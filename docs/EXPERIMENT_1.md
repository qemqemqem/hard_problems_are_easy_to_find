# Experiment 1 — Difficulty-response curves for Haiku under C0 / C1 / C∞

Status: designed 2026-06-11. Model under test: `anthropic/claude-haiku-4-5`, temperature 0.

## 1. Question

For each problem family, how does performance fall off with difficulty under
each execution condition? The headline figure is one panel per family:
x = difficulty level (10 levels), y = score, three curves (C0, C1, C∞).

Pre-registered expectations (HYPOTHESES.md): C0 collapses at the calibrated
cliff; C1 and C∞ stay near ceiling across the entire feasible grid; C1 ≈ C∞
on these families (one program suffices — no alternation needed yet).
Divergences from any of these are the interesting outcomes.

## 2. Design

- **Factors:** family (6) × difficulty level (10) × condition (C0/C1/C∞).
- **Replication:** seeds 1–8 at every cell → 480 samples per condition,
  1,440 total.
- **Paired instances:** all three conditions share one spec file, so every
  condition sees byte-identical instances. C0 vs C1 vs C∞ comparisons are
  within-instance (McNemar-style), not between-sample.
- **Difficulty is ordinal:** plots use level index 1–10 on the x-axis with
  knob values as tick labels. This accommodates argmax (2-D knob path) and
  chaos (system switch at the easy end) without pretending the knob is a
  single linear scale.

### Grids (anchored on the C0 calibration; calibrated cliff marked ▾)

| # | tsp `n` | maze `size` | sat `n_vars` | argmax `(domain, modes)` | chaos `(system, k)` | automata `k` (w=10, r=110) |
|---|---------|-------------|--------------|--------------------------|---------------------|-----------------------------|
| 1 | 4       | 3           | 4            | (10, 1)                  | henon 1             | 1                           |
| 2 | 6       | 4           | 5            | (20, 1)                  | logistic 1 ▾        | 2 ▾                         |
| 3 | 8       | 5           | 6            | (50, 1)                  | logistic 2          | 3                           |
| 4 | 9       | 6 ▾         | 7 ▾          | (50, 2) ▾                | logistic 3          | 4                           |
| 5 | 10      | 7           | 8            | (100, 2)                 | logistic 4          | 5                           |
| 6 | 11      | 8           | 9            | (100, 3)                 | logistic 5          | 6                           |
| 7 | 12 ▾    | 10          | 10           | (200, 3)                 | logistic 6          | 8                           |
| 8 | 13      | 12          | 12           | (500, 4)                 | logistic 8          | 12                          |
| 9 | 14      | 16          | 16           | (1000, 6)                | logistic 16         | 16                          |
| 10| 16      | 20          | 24           | (10000, 12)              | logistic 32         | 32                          |

Rationale:
- Levels are densest around each family's calibrated cliff (we want the
  transition shape, not just its location) and extend well past it for
  dynamic range on the gradated metric.
- Upper ends are capped by **ground-truth feasibility**, not by the model:
  tsp n≤16 (exact Held-Karp), sat n_vars≤24 (reference DPLL). This is a
  stated limitation: within ranges we can verify exactly, a correct program
  always wins — which is the thesis, not a bug. Probing where *code itself*
  struggles needs planted-ground-truth families (Phase 2).
- Chaos has no C0 headroom below logistic k=1 (calibration), so level 1 is
  henon k=1 (gentler arithmetic) to give the C0 curve a top.

### Condition configuration

| | solver | caps | scored on |
|---|---|---|---|
| C0 | plain `generate()` | `--max-tokens 8192` | chat completion |
| C1 | plain `generate()` + program preamble | exec timeout 60 s, sandbox: python:3.12-slim, no network | program stdout |
| C∞ | `cinf_solver` (python tool loop) | ~10 tool calls (message-limit), 30 s/exec, `--max-tokens 8192` per turn | final chat message |

## 3. What each measurement probes

- **Binary accuracy** (headline): position and sharpness of each cliff.
- **Gradated value** (tour ratio, Hamming fraction, digit precision,
  argmax closeness): dynamic range *past* the cliff, where binary is
  pinned at 0. Distinguishes "near miss" decay (tsp, automata) from
  "instant garbage" decay (sat certificates).
- **Label distribution** (`invalid` vs `valid_suboptimal` vs `parse_error`
  vs `no_program`/`exec_*`): separates can't-compute from can't-stay-legal
  from can't-follow-format. The SAT certificate asymmetry and maze
  invalid-move failures live here.
- **`stop_reason`**: separates genuine wrong answers from token
  exhaustion (rambling). A C0 "failure" with `stop_reason=max_tokens` is a
  different finding than a confidently wrong answer.
- **C∞ tool-call count per sample**: does the model scale effort with
  difficulty? Does it verify before answering? (Transcripts retained for
  the alternation-pattern analysis.)
- **C1 failure decomposition**: `no_program` (refused the format) vs
  `exec_*` (wrote crashing/hanging code) vs wrong-algorithm (clean run,
  wrong stdout) — only the last is a genuine understanding failure.

## 4. Confounds and controls

- **Prompt length:** difficulty and prompt size covary (tsp distance lists,
  maze grids). C1/C∞ act as the control: the model reads the *same* prompt
  there, so flat code curves + falling C0 curves implicate computation, not
  reading. Prompt token counts are recorded per sample for regression.
- **Temperature 0** throughout; single model; no retries.
- **Paired seeds** kill instance-sampling variance across conditions.
- **Token exhaustion** is accounted (stop_reason), not silently folded
  into "incorrect".

## 5. Analysis plan

1. Per family: accuracy-vs-level and mean-value-vs-level, three conditions,
   binomial 95% CIs (n=8/cell; CIs are wide per-cell — the inference is in
   the curve, not the point).
2. Pooled headline: mean accuracy across families per condition per level.
3. Paired C0-vs-C1 contingency (per family, pooling levels): McNemar exact.
4. Cliff localization: first level where accuracy ≤ 0.5 having been ≥ 0.5
   (logistic fit if the data cooperate).
5. C∞ effort curve: tool calls vs level per family.
6. Failure taxonomy table: label × family × condition.

## 6. Budget estimate

Haiku 4.5 at $1/$5 per Mtok (in/out), prompt caching on.
C0 ≈ 480×(0.7k in + ~2k out) ≈ $5; C1 ≈ 480×(1k in + 0.7k out) ≈ $2.5;
C∞ ≈ 480×(~12k in cached + ~3k out) ≈ $10–15. Total ≈ **$20 ± 5**,
within the remaining Phase-1 envelope.

## 7. Run notes (learned the hard way)

- 2026-06-11 C0 run: 16 connections × 8,192 max-tokens tripped Anthropic
  rate limits hard (~900 HTTP retries; final samples stuck in 25-minute
  backoffs). **Future runs: `--max-connections 8`, `--max-retries 6`, and
  `--max-samples` near the connection count** so a throttled tail fails fast
  and is finished by a cheap `inspect eval-retry` instead of stalling the
  whole eval. (Anthropic reserves `max_tokens` against the output-TPM
  budget per in-flight request, so connections × max-tokens is the real
  knob, not request rate.)

## 8. Artifacts

- Spec: `experiments/exp1/grid.json` (built by `experiments/exp1/make_grid.py`).
- Logs: `logs/exp1_c0/`, `logs/exp1_c1/`, `logs/exp1_cinf/`.
- Plots + summary tables: `experiments/exp1/out/` (built by
  `experiments/exp1/analyze.py`).
