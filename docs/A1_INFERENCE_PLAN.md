# A1_INFERENCE_PLAN — Calling Open-Weight Model Ladders from the Eval Harness

**Status: investigated 2026-06-12 (web research + verification against the inspect-ai 0.3.239 source installed in this project's venv). Companion to A1_SCALING_FEASIBILITY.md (which models); this doc covers how to call them and what it costs.** Hypothesis A1 needs the Experiment-1 C0 sweeps (6 families × 10 levels × 8 seeds = 480 samples/model, ~1k-token prompts, temperature 0, no tools) replicated across ~30 open-weight model/checkpoint combos: Pythia ladder + intermediate checkpoints, OLMo/OLMo 2, Gemstones/MobileLLM (depth-vs-width), FineWeb/FineWeb-Edu ablations and DCLM baselines (data recipe).

## TL;DR

**Self-hosting is mandatory** — none of the research suites are on serverless APIs (verified per-model below). **Recommended stack: rent one A100 80GB or L40S on RunPod (~$1–2.2/hr), let Inspect's `vllm-completions/` provider launch `vllm serve` per model, loop over models/revisions in a shell script.** The whole A1 observational sweep is **single-digit-to-low-double-digit GPU-hours: ~$15–50 of compute**. The binding constraint is not money or plumbing — it's that **most research suites have 2,048-token context windows**, which is incompatible with Experiment 1's ~1k prompts + ≤8k outputs and forces a redesign of the C0 answer format for the base-model arm (§4).

## 1. Serverless hosting availability

Expectation confirmed: research-ladder models are not on per-token serverless APIs. Verified 2026-06-12:

| Suite | Serverless? | Evidence / notes |
|---|---|---|
| Pythia (70M–12B + 154 step-branches each) | **No** | HF model pages: "This model isn't deployed by any Inference Provider." Fireworks lists `fireworks/pythia-12b` but **on-demand dedicated GPU only — explicitly "Serverless: Not supported"**, and only 2k context. Not on Together's serverless catalog, OpenRouter, DeepInfra, or Hyperbolic. |
| OLMo 2 / OLMo 3 **base** | **No** (base) | Base models not hosted anywhere I could find. |
| OLMo 2 / 3 **Instruct** | **Yes — the one exception** | OpenRouter: `allenai/olmo-2-0325-32b-instruct` at $0.05/M input, $0.20/M output; OLMo 3/3.1 32B Instruct/Think ~$0.20/$0.20. Useful later for an instruct-vs-base comparison arm, not for A1's base ladders. |
| Gemstones (22 models × ~depth/width grid, 4,000+ checkpoints) | **No** | HF org `Gemstone-Models` / `tomg-group-umd`: `availableInferenceProviders: []` on every model page checked. |
| MobileLLM (125M–1.5B) | **No** | `facebook/MobileLLM-*` on HF; no inference providers. |
| FineWeb / FineWeb-Edu ablation models (1.8B, 8 dataset-comparison models + step branches) | **No** | `HuggingFaceFW/ablation-model-*`: `availableInferenceProviders: []`. |
| DCLM baselines (apple/DCLM-7B, 1B) | **No** | Not hosted; worse, **not even transformers/vLLM-native** (see §3 compatibility table). |

HF Inference Providers (the router formerly "serverless inference API") only routes to the same commercial providers (Together, Fireworks, etc.), so it inherits the same absence. Conclusion: every model in the A1 plan except OLMo Instruct variants requires self-hosted inference. (Fireworks on-demand deployment of pythia-12b is just renting their GPU by the hour at a markup — no reason to prefer it over RunPod.)

## 2. Inspect AI provider support (verified against installed inspect-ai 0.3.239 source, not just docs)

Inspect has three relevant local/self-hosted paths, and the situation improved materially in Feb 2026 (PR #3242 added explicit base-model support after issue #3122 "best practice for evaluating a base model"):

- **`hf/` provider** (`inspect eval task.py --model hf/EleutherAI/pythia-410m`): loads via `AutoModelForCausalLM.from_pretrained` in-process. **Revision/branch: works** — unknown `-M` model args pass through to `from_pretrained`, so `-M revision=step3000` selects Pythia intermediate checkpoints (verified in `hf.py` source: `**model_args` forwarded; note the **tokenizer is loaded without revision** — fine for Pythia/FineWeb where the tokenizer never changes across checkpoints, but check per-suite). **Base-model/raw-completion: works** — `-M use_chat_template=false` bypasses chat templating entirely (the in-repo test for this feature literally uses `hf/EleutherAI/pythia-70m`); `-M chat_template=...` overrides with a custom Jinja template. **Batching: yes** — up to `max_connections` (default batch 32) concurrent `generate()` calls are batched; tune `-M batch_size`. **Logprobs: yes** — `logprobs`/`top_logprobs` (0–20) supported; **`prompt_logprobs` is NOT supported on `hf/`** (vLLM only). `trust_remote_code` must be passed explicitly (`-M trust_remote_code=true`). Determinism: `temperature=0` plus `-M do_sample=false`, `seed` supported. Slow (no paged attention, no continuous batching) — fine for smoke tests on a dev box, not for the sweep.
- **`vllm/` and `vllm-completions/` providers**: Inspect launches `vllm serve` itself (and tears it down at eval end), or connects to an external server via `--model-base-url http://host:8000/v1 -M api_key=...`. `-M` args are forwarded as vLLM CLI flags, so `-M revision=step3000` → `vllm serve --revision step3000` (pass `-M tokenizer_revision=...` too if a suite versions its tokenizer). **`vllm-completions/` is the headline feature for us**: routes through `/v1/completions` with raw text, no chat template at all — built for exactly this base-model use case (provider docstring example: `get_model("vllm-completions/EleutherAI/pythia-70m")`). Verified in `vllm_completions.py` source: supports `stop_seqs` (→ `stop`), `seed`, `logprobs`/`top_logprobs`, `prompt_logprobs`, and **defaults to `temperature=0.0`**. Requires `Sample(input="raw text string")` (single user message) — which is exactly what our C0 generators produce. Concurrency via `max_connections` (default 32); vLLM does its own continuous batching.
- **`openai-api/<provider>/<model>` generic provider**: any OpenAI-compatible endpoint (self-managed `vllm serve`, SGLang, TGI). Works, but the chat-completions path applies templates server-side; for base models you'd need the server's completions endpoint, which is what `vllm-completions/` already wraps with proper lifecycle/retry handling. Use `vllm-completions/` instead.

**Few-shot prompting**: no special support needed — C0 prompts are strings we generate, so k-shot exemplars are just prompt construction in our generator package. **Stop sequences**: `GenerateConfig.stop_seqs` flows through to vLLM `stop` (verified). **Likelihood scoring**: Inspect now ships `target_perplexity()` — a scorer computing NLL of trailing target tokens given a prompt, explicitly documented as corresponding to lm-eval-harness's `loglikelihood` pattern — plus `perplexity()` for full-text NLL. Both require `prompt_logprobs`, i.e. **vLLM-backed models only**. The docs specifically recommend `vllm-completions` for this to avoid chat-template token contamination. This closes the main historical reason to bolt on lm-eval-harness (§4).

One caveat from the source: Inspect reuses a single vLLM server entry per base model name, so two `vllm/` instances of the same model at different URLs collapse to one — irrelevant for our one-model-at-a-time loop.

## 3. Self-hosting recipe

**GPU provider options (June 2026 prices, spot-checked across trackers — marketplace prices fluctuate):**

| Provider | RTX 4090 24GB | L40S 48GB | A100 80GB | H100 80GB | Notes |
|---|---|---|---|---|---|
| Vast.ai | $0.27–0.36/hr | $0.19–0.55/hr | $0.67–1.89/hr | $1.65–3.29/hr | cheapest, variable host quality |
| RunPod Community / Secure | $0.34 / $0.69 | ~$0.55–1.0 | $1.64 / $2.21 | $1.99 / $3.49 | good balance; recommended |
| Lambda | — | — | $2.49 | $2.99 | most reliable, pricier |
| Modal (serverless, list) | — | $1.95 | $2.50–3.40 | $3.95 | per-second billing but region/preemption multipliers up to 3.75×; overkill here |

**Hardware sizing**: the largest model in scope is 12B bf16 = 24GB weights; with 2k context the KV cache is trivial. **An L40S (48GB) fits everything; an A100 80GB gives headroom and faster loads.** A 4090 (24GB) fits up to ~7B comfortably but is tight for 12B bf16 — not worth the complexity of a split fleet. Rent **one** GPU; the workload is far too small to parallelize.

**vLLM throughput expectations** (single GPU, batched, short sequences — estimates, not benchmarks): 70M–410M: >15k output tok/s; 1–3B: 5–15k; 7B: ~3–6k; 12B: ~1.5–3k. At 480 samples × ~700 output tokens = ~340k output tokens per model, **generation is 1–4 minutes per model even for the 12B**. Model swap (engine start + weight load from local disk) is ~1–4 min; first-time download of a 12B is ~24GB. **So per-model wall time is dominated by load/swap, not inference — confirming the prior that 480 samples is small.** Don't fight this (keeping models resident, multi-model serving); just eat the ~3 min/swap.

**Disk**: Pythia full ladder ≈ 50GB (sum of 70M…12B at bf16) + ~10 intermediate checkpoints of one or two mid-size models (~3GB each) ≈ 25GB + OLMo 2 1B/7B/13B ≈ 42GB + FineWeb ablations 8 × 3.6GB ≈ 29GB + Gemstones/MobileLLM picks ≈ 20GB ≈ **~200GB; provision a 500GB volume** (RunPod network volume ~$0.07/GB/mo → ~$35/mo, or container disk for the run duration). Pre-download everything with `HF_HUB_ENABLE_HF_TRANSFER=1 hf download` before starting the loop so swap time is pure load time.

**CPU inference for ≤410M models**: technically viable (~20–60 tok/s/stream on a modern desktop CPU → 480 samples × ~500 tok ≈ 2–6 hours per model single-stream) and fine for free local smoke tests via `hf/` on the dev box. **Economically pointless for the real runs**: the same model takes ~2 minutes on the GPU you're already renting for $1/hr. Recommendation: GPU for everything; CPU only for harness debugging.

**Architecture compatibility (the real per-suite engineering cost):**

| Suite | transformers | vLLM | Plan |
|---|---|---|---|
| Pythia (GPTNeoX) | native | native | `vllm-completions/` |
| OLMo 2 / 3 | native | native | `vllm-completions/` |
| FineWeb ablations (Llama arch, gpt2 tokenizer) | native | native | `vllm-completions/`; revisions like `step-001000-2BT` |
| Gemstones (custom `modeling_gemma.py`) | `trust_remote_code=true` | **unverified — assume no** | fall back to `hf/` provider with `-M trust_remote_code=true -M use_chat_template=false`; test one model in vLLM first |
| MobileLLM (custom code per model card) | `trust_remote_code=true` | **unverified** | same fallback as Gemstones |
| DCLM (openlm arch) | **no — needs `open_lm` package shim** (`from open_lm.hf import *`) | no | highest integration cost in the whole plan; either a small custom Inspect ModelAPI wrapping open_lm, or drop/deprioritize DCLM and lean on FineWeb ablations for the data-recipe axis |

**Cost estimates with explicit arithmetic** (rates: L40S $1/hr; A100 $2/hr used as the budget number):

- **Pilot (3 models × 1 family × 3 levels × 8 seeds)**: 3 × 24 = 72 samples/model, 216 total. Tokens ≈ 216 × (1k in + 0.7k out) ≈ 0.4M — generation minutes. Wall time = env setup + downloads (~30–45 min one-time) + 3 swaps × 3 min + generation ~10 min + slack ≈ **1–2 GPU-hours → $2–5**.
- **Full A1 sweep (30 model/checkpoint combos × 480 samples)**: 30 × 480 = **14,400 samples** (sanity: 6 families × 10 levels × 8 seeds = 480 ✓; 30 × 480 = 14,400 ✓). Tokens ≈ 14,400 × (1,000 in + 700 out) ≈ 14.4M in + 10.1M out ≈ **~25M total**. Generation: ≈ sum over models of 340k out-tokens / per-model throughput ≈ 45–90 min aggregate. Swaps: 30 × ~3 min ≈ 1.5 hr. Downloads ~200GB ≈ 0.5–1 hr one-time. Nominal total ≈ **4–6 GPU-hours**; budget 2–3× for re-runs, parse-failure iterations, and stragglers → **10–15 GPU-hours → ~$10–15 (L40S) / ~$20–35 (A100), under $50 either way**. The dominant project cost is engineering time and the answer-format redesign, not compute. Even tripling to 90 combos (e.g., dense Pythia checkpoint trajectories) stays under ~$100.

## 4. Base-model eval mechanics

Published base-model evals (lm-eval-harness conventions) use two patterns: **(a) k-shot generation** — prompt = k exemplars in `Q: … A: …` format, greedy decode, stop sequences (`"\n\n"`, `"Q:"`), exact-match/regex scoring; **(b) loglikelihood scoring** — for enumerable answer candidates, score NLL of each candidate appended to the prompt, pick argmin, no generation at all. (b) is what makes 70M-param models produce non-degenerate accuracy curves on multiple-choice benchmarks.

**Can Inspect do likelihood scoring? Yes, now.** `target_perplexity()` + `prompt_logprobs` via `vllm-completions` implements exactly the lm-eval `loglikelihood` computation (the Inspect docs say so verbatim). For candidate-set scoring we write a small custom solver/scorer: one `generate(max_tokens=1, prompt_logprobs=1)` call per candidate with the candidate appended to the prompt, argmin NLL — a ~30-line solver, not a framework fight. Applicability per family: SAT yes/no (2 candidates), automata final-state (enumerable states), argmax (n candidates) — yes; TSP tours and chaos digit-tracking have unbounded answer spaces — generation-only.

**Two-harness option (lm-eval-harness for the base arm) — honestly compared and rejected.** For: lm-eval is the de-facto standard for base ladders, has `pretrained=...,revision=step3000` built in, battle-tested loglikelihood. Against: HARNESSES.md already scored it 5/10 for this project (YAML+HF-datasets task model fights per-seed procedural generation; fragile regex extraction; no thinking-budget support for the frontier arm we already run); we'd maintain two task definitions of every generator with a permanent risk that prompt rendering, stop handling, or parsing silently diverge between arms — and the entire point of A1 is cross-arm comparability of cliff positions. Since Inspect 0.3.239 closes the capability gap (raw completions + loglikelihood), the consistency argument wins: **one harness, Inspect, same generator/scorer package for both arms.** Revisit only if we hit a concrete vLLM/Inspect wall.

**Chat-template handling for instruct variants**: run instruct models through plain `vllm/` (tokenizer chat template applied automatically) with the identical problem text as the base arm's prompt body, zero-shot; record `elicitation: {completion-kshot | chat-zeroshot}` as an explicit results dimension and never compare across elicitations without saying so. Cheap robustness check: also run one instruct model through `vllm-completions/` with the base-arm k-shot prompt to measure how much elicitation (vs weights) moves the cliff.

**The hard problem found: context length.** Pythia, Gemstones, FineWeb ablations, and MobileLLM are all **2,048-token-context** models (OLMo 2 ≥ 4k). Experiment 1 used ~1k-token prompts and up to 8k output. For the base arm: prompt (problem + k-shot exemplars) + completion must fit in 2,048 tokens. Consequences: (1) trim C0 prompt boilerplate for the base arm (the instruction-heavy framing is useless for base models anyway — exemplars do the work); (2) cap completions at ~512–768 tokens with stop sequences; (3) families whose hard levels need long outputs or long inputs (chaos long trajectories, automata high-k step-by-step traces, TSP with many cities) will hit the window before they hit the model's reasoning cliff — **the difficulty range per family must be re-calibrated to what fits in 2k tokens, and answer formats switched to short-form (final answer only, or likelihood over candidates) rather than chain-of-thought transcripts**. This is a task-design change, not an infrastructure change, and it should be settled in the pilot before burning the sweep. It also means base-arm cliffs measure no-CoT serial depth, which is arguably the cleaner test of A1's circuit-depth framing — but that interpretation choice belongs in A1_SCALING_FEASIBILITY.md / pre-registration, not here.

## 5. Recommendation and runnable sketch

**Stack: one RunPod A100 80GB Secure (~$2.2/hr; or L40S ~$1/hr to halve cost at modest speed loss) + pre-downloaded checkpoints on a 500GB volume + Inspect's `vllm-completions/` provider launching `vllm serve` per model + a bash loop over (model, revision) pairs. `hf/` provider with `trust_remote_code` as the fallback lane for Gemstones/MobileLLM if vLLM rejects them; DCLM deprioritized.**

```bash
# --- one-time setup on the rented box ---
pip install inspect-ai vllm hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1 HF_HOME=/workspace/hf
hf download EleutherAI/pythia-1.4b               # repeat per model
hf download EleutherAI/pythia-1.4b --revision step3000   # repeat per checkpoint

# --- single eval: a Pythia intermediate checkpoint, raw completions, temp 0 ---
inspect eval src/sweeps/c0_base.py \
  --model vllm-completions/EleutherAI/pythia-1.4b \
  -M revision=step3000 \
  --temperature 0 --max-tokens 640 --seed 1 \
  --max-connections 32

# --- fallback lane (trust_remote_code suites) ---
inspect eval src/sweeps/c0_base.py \
  --model hf/Gemstone-Models/Gemstone-1280x36 \
  -M trust_remote_code=true -M use_chat_template=false \
  --temperature 0 -M do_sample=false
```

Stop sequences and few-shot live in the task, not the CLI: the base-arm task wraps the existing generators with a k-shot prefix and sets `GenerateConfig(stop_seqs=["\n\n", "Problem:"], max_tokens=640)`; samples are plain strings, which is what `vllm-completions` requires. Model-loop outline (`run_a1.sh`): a `MODELS` array of `repo[@revision]` entries; for each, parse the optional revision into `-M revision=`, run `inspect eval` with `--log-dir logs/a1/${repo//\//_}_${rev:-main}`, and rely on Inspect to start/stop the vLLM server per invocation (cleanest isolation; ~3 min/swap is acceptable at 30 models). Inspect's log resumability + response cache means a crashed loop re-runs cheaply. Analysis stays `samples_df()` exactly as in Experiment 1.

**Cost & time table** (A100 $2.20/hr; L40S $1.00/hr; estimates from §3 arithmetic):

| Run | Samples | GPU-hours (nominal → budgeted) | $ on L40S | $ on A100 |
|---|---|---|---|---|
| Pilot: 3 models × 1 family × 3 levels × 8 seeds | 216 | ~1 → 2 | ~$2 | ~$4–5 |
| Full A1: 30 combos × 480 | 14,400 | ~5 → 10–15 | ~$10–15 | ~$22–33 |
| 3× expanded (90 combos, dense checkpoints) | 43,200 | ~15 → 30–40 | ~$30–40 | ~$66–88 |

**Unverified items to nail down in the pilot**: (1) vLLM loads Gemstones/MobileLLM (`trust_remote_code` lane otherwise); (2) exact revision-branch naming per suite (Pythia `step3000` ✓ documented, FineWeb `step-001000-2BT` ✓ documented, OLMo 2 `stage1-step…-tokens…B` — check per repo); (3) tokenizer-revision irrelevance per suite (true for Pythia/FineWeb; confirm for OLMo intermediate checkpoints); (4) vLLM temperature-0 determinism is greedy but not bitwise-stable across batch compositions — pin the vLLM version, set `--seed`, and treat ±1-sample wobble per cell as noise; (5) 4090-class GPUs as a further cost cut if the 12B models are dropped or quantized.
