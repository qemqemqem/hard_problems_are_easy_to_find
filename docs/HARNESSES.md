# HARNESSES — Eval Harness Selection

**Companion to [DESIGN.md](./DESIGN.md). Status: investigated, recommendation drafted — v0.1 (2026-06-11).**

Four open-source candidates were investigated in depth (via dedicated research passes against current docs/repos, June 2026), plus the build-our-own option.

## Requirements (from DESIGN.md §4)

| # | Requirement | Why |
|---|---|---|
| R1 | Programmatic (Python) task & dataset definition | Our datasets are *generated*, not loaded — seeded generators, parametric difficulty |
| R2 | Arbitrary-Python custom scorers | Verifiers (check a SAT assignment, recompute a tour length), approximation ratios, digit-precision metrics |
| R3 | Multi-provider API support (Anthropic, OpenAI, Google, OpenRouter) with pinned model versions | Cheap-tier first, frontier later; reproducibility |
| R4 | Concurrency, rate limiting, retries, response caching | Bulk runs on a budget; don't pay twice for the same call |
| R5 | Per-sample structured logs → pandas | Accuracy-vs-difficulty curves are the core artifact |
| R6 | Reasoning/thinking-budget configuration | Thinking budget is a primary experimental axis |
| R7 | Light enough to not dominate the project | The harness is plumbing, not the contribution |

## Candidates

### 1. Inspect AI (UK AI Security Institute) — **9/10, recommended**

[github.com/UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) · MIT · Python · v0.3.238 (2026-06-08), ~10 releases/month, used by METR, Apollo, other AISIs.

- **R1:** First-class. `MemoryDataset` + `Sample` built in Python inside a parameterized `@task(seed=..., n=...)` — no static files. `metadata` carries instance data (cities, clauses, optimum) to the scorer.
- **R2:** Scorer = arbitrary async Python `(TaskState, Target) -> Score`; full access to metadata. Built-ins for exact/numeric-tolerance matching.
- **R3:** Anthropic/OpenAI/Google/Grok/Mistral/DeepSeek/OpenRouter/any OpenAI-compatible + local vLLM. Docs explicitly recommend pinned snapshot names (`anthropic/claude-haiku-4-5-...`).
- **R4:** Adaptive concurrency (auto-scales 20→100 connections, backs off on 429), exponential-backoff retries, local response cache keyed on model+prompt+config, batch-API mode.
- **R5:** `.eval` logs with full transcripts; `samples_df()`/`evals_df()` return pandas DataFrames directly; log viewer UI.
- **R6:** Best in class: unified `reasoning_effort` (none→max) mapped per provider, explicit token budgets, handles Opus 4.8 / GPT-5.5 / Gemini 3.1 mappings; reasoning traces captured in logs.
- **R7:** Moderate: ~36MB wheel, real framework with a dataset→solver→scorer learning curve — but we use the thin slice (no agents/sandboxes).
- **Pain points:** learning curve; historical memory issues on huge agentic logs (fixed, and irrelevant to our text-in/text-out usage).

### 2. promptfoo — 8/10, strong runner-up

[github.com/promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) · MIT · TypeScript/Node · ~22k stars, weekly releases.

- **R1:** Good: `tests: file://generate_tests.py:create_tests` calls a Python generator function — no intermediate files.
- **R2:** Python assertions (`get_assert`) run arbitrary code, but **as a subprocess per assertion** — slow at our volumes.
- **R3:** Native Anthropic/OpenAI/Google/OpenRouter with dated model IDs.
- **R4:** Excellent: adaptive concurrency honoring `retry-after`, per-provider rate-limit tracking, disk cache on by default.
- **R5:** SQLite + JSON/CSV export; web UI. Less analysis-native than DataFrames/Parquet.
- **R6:** First-class: Anthropic `thinking: {budget_tokens}`, OpenAI `reasoning_effort` per provider config.
- **Why not:** Node runtime + YAML spine in a Python-centric research project; subprocess-per-assertion scoring overhead; telemetry on by default. Built for prompt/app testing more than research evals.

### 3. HF lighteval — 6/10

[github.com/huggingface/lighteval](https://github.com/huggingface/lighteval) · MIT · Python · last release Nov 2025 (6-month gap; install from `main`).

- Pure-Python tasks and arbitrary-Python sample-level metrics fit well; per-sample Parquet details are nice.
- **Dealbreakers:** data must flow through HF `datasets` loaders (JSONL round-trip for procedural generation); `GenerationParameters` exposes **no thinking/budget knobs** (R6 fails without patching); heavy transformers/torch-adjacent install; 0.x API churn.

### 4. EleutherAI lm-evaluation-harness — 5/10

[github.com/EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) · MIT · Python · v0.4.12 (May 2026), de facto academic standard.

- Massive credibility and maturity; custom Python metrics via `!function` work.
- **Dealbreakers:** design center is local-model loglikelihood evals; YAML+HF-datasets task model fights per-seed procedural generation; API support is second-class (Anthropic compat needed repeated fixes); **no extended-thinking support for API models** (R6 fails); no token-aware rate limiting; regex-based answer extraction is fragile for generative outputs.
- Worth keeping in mind for a *future* open-weight/local-model arm of the study.

### 5. Build our own — viable fallback, not recommended (yet)

A thin custom harness is ~300–500 lines: async API clients (or LiteLLM), a retry/cache layer, a results JSONL, and a plotting notebook. Honest assessment:

- **Pro:** zero framework friction; the generator/scorer interface in DESIGN.md §3 *is* the design; total control over logs.
- **Con:** we'd re-implement (worse) what Inspect already does — adaptive rate limiting, caching, provider quirks, reasoning-budget mapping across three providers, resumability. Provider edge cases are where hand-rolled harnesses bleed time.
- **Decision rule:** start with Inspect. If we hit framework friction in Phase 1 (the MVP is also the harness shakedown), the generator/scorer code is harness-agnostic by design and ports to a custom runner in a day.

## Comparison summary

| | Inspect AI | promptfoo | lighteval | lm-eval-harness | custom |
|---|---|---|---|---|---|
| R1 programmatic datasets | ●● | ●● | ○ | ○ | ●● |
| R2 Python scorers | ●● | ● (subprocess) | ●● | ●● | ●● |
| R3 providers + pinning | ●● | ●● | ● | ● | ● (DIY) |
| R4 concurrency/caching | ●● | ●● | ● | ○ | ○ (DIY) |
| R5 logs → pandas | ●● | ● | ●● | ● | ●● |
| R6 thinking budgets | ●● | ●● | ○ | ○ | ● (DIY) |
| R7 lightness | ● | ● | ○ | ○ | ●● |
| Language | Python | Node+YAML | Python | Python | Python |
| Score | **9/10** | 8/10 | 6/10 | 5/10 | — |

●● = native/strong · ● = workable · ○ = fights the design

## Recommendation

**Adopt Inspect AI.** It is the only candidate that meets R1–R6 natively, it's Python end-to-end, actively maintained (near-daily releases), and its `samples_df()` export feeds the analysis pipeline directly. The reasoning-effort abstraction (R6) matters most: thinking budget is a primary experimental axis in this study, and Inspect is the only Python option that handles it across Anthropic/OpenAI/Google without custom code.

Mitigation for lock-in: keep problem generators and scorers in our own pure-Python package with no Inspect imports; a thin adapter module maps them to Inspect `Sample`s and `@scorer`s. This preserves the build-our-own escape hatch and makes the open-source release useful to non-Inspect users.

## Code execution (re-examined 2026-06-11 — decision reaffirmed)

The C0/C1/C∞ execution-condition design (DESIGN.md §1) raised the question: does code execution push us off Inspect AI? **No — it strengthens the choice.** Sandboxed agentic evaluation is the core reason Inspect exists (AISI built it for autonomy/cyber evals):

- **C1 (write code once)** doesn't even need agent infrastructure: a plain `generate()` solver, then the *scorer* extracts the program from the response and executes it in a subprocess/sandbox with a fixed timeout; stdout goes through the same parser as a chat answer. Fully supported today.
- **C∞ (interactive)** maps to Inspect's tool-calling loop: `python()` tool + sandbox environments (`local` or `docker`), with per-sample sandbox isolation, tool-call limits (`message_limit`/custom), and full tool transcripts in the logs — exactly what we need to count executions and analyze alternation patterns.
- The alternatives get *worse* under this requirement: promptfoo's subprocess-per-assertion model and YAML orchestration make multi-turn tool loops awkward; lm-eval-harness and lighteval have no agentic/tool story at all. A custom harness would now mean building a sandboxed tool loop too.

One genuine caveat: if Phase 2's hybrid problems (PROBLEMS.md Category 6) demand an exotic alternation paradigm beyond standard tool calling (e.g., solver-calls-model-as-oracle, inverted control flow), that's custom code in *any* harness — Inspect's composable solver abstraction is at least a reasonable host for it.

## Open questions

- Inspect's `inspect-viz` vs. hand-rolled matplotlib for the paper's figures (decide in Phase 1).
- Whether to use provider batch APIs (50% discount) for big frontier-tier sweeps — Inspect supports batch mode; adds latency, saves real money at Phase 2 scale.
- If we later add an open-weight/local arm, revisit lm-eval-harness vs. Inspect's vLLM support (likely the latter).
