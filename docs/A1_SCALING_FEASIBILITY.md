# A1 Scaling Feasibility — Can we dissociate training factors without training our own models?

Status: research memo, 2026-06-12. Investigates feasibility of Hypothesis A1 (HYPOTHESES.md): which training factor — parameter count, depth in layers, data quantity, data quality — buys C0 cliff position. All web claims checked June 2026; unverified items flagged inline.

## Executive summary

**A1 is feasible without training a single model.** The community has already built, and released under permissive licenses, controlled model suites that dissociate every factor A1 names. The recommended path is inference-only sweeps over three existing suites — **Gemstones** (depth-vs-width at fixed parameter count, the axis our circuit-depth theory says should bind), **Pythia** (parameter ladder with fixed data and data order, plus 154 intermediate checkpoints per size giving a data-quantity axis), and **DataDecide** (25 data recipes × 14 sizes, the data-quality axis) — using our existing generators with an easy-end extension, few-shot prompting, and constrained/logprob scoring for base models. Total estimated cost: **$300–$1,000 of rented GPU time** (roughly 100–400 H100-hours at $2–3/hr, dominated by checkpoint loading and re-runs, not raw generation) plus engineering time. Training our own ladder is only needed if Gemstones' easy-end floor turns out to be unmeasurable, and even then a bespoke depth ladder at ~500M params is **$2k–8k**, not a lab-scale project. The single biggest risk is not cost but the **floor problem**: every existing suite tops out at 2B (Gemstones), 1B (DataDecide), or 12B (Pythia) base models, and our families may be too hard even at level 1 — this must be settled with a ~$20 pilot before committing to anything.

A second strategic point: the depth question has a sharper registrable form than A1 currently states. Constant-depth transformer theory (Merrill & Sabharwal's TC0 bounds and the CoT-expressivity follow-ups) predicts layer depth binds only when the model must answer *directly*; chain-of-thought tokens buy serial compute that substitutes for layers. So the experiment should run each base model in two modes — forced-immediate-answer and few-shot-CoT — and pre-register: "depth-in-layers moves the no-CoT cliff and barely moves the CoT cliff." That turns a correlational sweep into a theory test, and it is only possible because Gemstones exists.

## Part 1 — Inventory of existing suites

### Summary table

| Suite | Factor isolated | Confounded / held fixed | Sizes | Checkpoints | License | Base or instruct |
|---|---|---|---|---|---|---|
| **Gemstones** (UMD, 2025) | **Depth vs width at fixed params** (groups at 50M/100M/500M/1B/2B ±5%, up to 5 shapes per group; 11 widths 256–3072, 18 depths 3–80) | Data fixed (Dolma, 350B tokens, ctx 2048); LR scaled by shape rule (a deliberate choice, mild confound); no instruct versions | 22 models, 50M–2B | every ~2B tokens, 4,000+ total incl. LR/cooldown ablations | Paper CC-BY; **model license unverified — HF collection `tomg-group-umd`, likely Apache 2.0, check before use** | Base only |
| **Pythia** (EleutherAI, 2023) | **Param count at fixed data + data order**; also **data quantity** via 154 checkpoints/model; also **dedup** (standard vs deduped pairs) | Depth and width co-vary with size (6→36 layers as params grow) — params and depth NOT dissociated within Pythia; data is 300B Pile (dated, weak by 2026 standards) | 8 sizes ×2: 70M, 160M, 410M, 1B, 1.4B, 2.8B, 6.9B, 12B | 154 per model (log-spaced early + every 1k steps) | Apache 2.0 | Base only |
| **DataDecide** (AI2, 2025) | **Data quality/recipe at fixed architecture and token ratio**: 25 corpora (Dolma, DCLM, C4, FineWeb, RefinedWeb + dedup/filter/mix interventions), 3 seeds | Token-to-param ratio fixed at 100×; max size 1B (floor risk is severe); intermediate checkpoints were "uploading after initial release" — **verify they actually landed** | 14 sizes, 4M–1B (1,050 models, 30k+ checkpoints) | Yes (3 seeds × 14 sizes × 25 recipes) | AI2 release, Apache 2.0 (standard for AI2; spot-check per-repo) | Base only |
| **OLMo 2 / OLMo 3** (AI2, 2024/2025) | Clean modern base models with full data transparency; checkpoints across training (data-quantity axis); OLMo 3 adds stage-wise checkpoints (pretrain/midtrain/long-context) | Sizes too sparse for a ladder (OLMo 2: 1B/7B/13B/32B; OLMo 3: 7B/32B); recipe changes between stages | 1B–32B | Thousands per model | Apache 2.0 | Both base and instruct |
| **Cerebras-GPT** (2023) | Param ladder at Chinchilla-optimal 20 tok/param (contrast with Pythia's fixed-300B: same sizes, different data scaling → a params-vs-tokens contrast across suites) | Pile data (dated); depth/width co-vary; intermediate checkpoints exist but in one aggregate repo | 111M, 256M, 590M, 1.3B, 2.7B, 6.7B, 13B | Final + intermediate (aggregate repo) | Apache 2.0 | Base only |
| **LLM360 Amber** (2023) | Data-quantity axis at 7B (360 checkpoints, full data sequence released) | Single size; LLaMA-arch | 7B | 360 | Apache 2.0 | Base |
| **MobileLLM** (Meta, ICML 2024) | Depth vs width at 125M/350M (their internal study trained 19 shape variants) — but **only the winning deep-thin configs were released**, not the shape ladder | Released models differ in size, not shape; 1T tokens unspecified "publicly available" data | 125M, 350M, 600M, 1B, 1.5B | Final only | **FAIR Noncommercial Research License** (fine for a paper, no commercial use) | Base |
| **SmolLM 2/3** (HuggingFace, 2024/2025) | Strong small modern models; SmolLM3-3B has intermediate checkpoints every ~94B tokens; full data mixture public | Single size per generation; multi-stage data curriculum confounds the checkpoint axis | 135M–1.7B (v2), 3B (v3) | v3: yes; v2: partial | Apache 2.0 | Both |
| **FineWeb ablation models** (HuggingFace, 2024) | Data quality at fixed arch: 1.8B Llama-arch trained 350B tokens on each of ~8 corpora (FineWeb, FineWeb-Edu, C4, Pile, RefinedWeb, ...) | Single size; gpt2 tokenizer; 2048 ctx | 1.8B × ~8 datasets | intermediate checkpoints available (collection of 22 ablation models) | Apache 2.0 (verify per-repo) | Base only |
| **Tay et al. "Scale Efficiently" DeepNarrow** (Google, 2021) | Depth vs width for T5 encoder-decoder | Encoder-decoder, span corruption — wrong architecture family for our decoder-only story; checkpoints partially released. **Cite as literature, don't run it.** | T5 small→XL variants | Partial | Apache 2.0 | Base (T5) |

Notable misses: I found no 2025–2026 suite that beats Gemstones on the depth axis (Zuo et al. 2025 study depth in hybrid/Mamba architectures; checkpoint availability unverified). Petty et al. (NAACL 2024) trained 41M/134M/374M fixed-param depth ladders but to my knowledge did not release checkpoints — their result (depth helps compositional generalization but with rapidly diminishing returns beyond a few layers) is the prior to beat, and Gemstones' 18-depth range (3–80 layers) is far wider than theirs.

### What each A1 axis maps to

- **Parameter count:** Pythia ladder (fixed data, fixed order — the cleanest params axis ever released) + Cerebras-GPT ladder (Chinchilla scaling) as robustness check. Within Pythia, params confound depth (6→36 layers); that is exactly what Gemstones un-confounds.
- **Depth in layers at fixed params:** Gemstones, full stop. Up to 5 shapes per param group; e.g. the 1B group spans shallow-wide to deep-thin. This is A1's crown jewel and it is sitting on HuggingFace. Secondary evidence: MobileLLM (released models are all deep-thin "winners"; the internal shape ladder wasn't released, so it's a citation, not a measurement).
- **Training-data quantity:** intermediate checkpoints — Pythia's 154 per size (same data order!), LLM360 Amber's 360 at 7B, OLMo 2 checkpoint trajectories. Caveat: checkpoint number confounds LR-schedule position (a step-100k checkpoint is not a converged model trained on 100k steps of data); Gemstones' cooldown-ablation checkpoints partially address this, and this caveat should be stated in the paper rather than engineered away.
- **Training-data quality:** DataDecide (25 recipes, 3 seeds, 14 sizes — overkill, in a good way), FineWeb ablation octet at 1.8B, Pythia standard-vs-deduped pairs (dedup only). If DataDecide's 1B ceiling is below our task floor, the FineWeb 1.8B octet is the fallback.

## Part 2 — Methodological feasibility

### The floor problem (the binding risk)

The literature is unambiguous that multi-step formal reasoning in sub-1B base models is at or near floor: GSM8K-style multi-step arithmetic is ~0 below 1B; the emergent-abilities-from-loss work (Du et al., ICLR 2024) finds reasoning benchmarks stay at chance until pre-training loss crosses a threshold that small models never reach; CoT prompting is net-harmful below ~1B in several comparative studies. Our level-1 settings are easier than GSM8K items in structure (one automaton step, 3×3 maze, n=4 TSP) but they demand exact symbolic state-tracking and exact output formats, which is precisely what small base models are worst at. Haiku 4.5 — a competent frontier-cheap model — cliffs at automata k=2 and maze 6×6; a Pythia-410M base model is plausibly at 0 on every current level-1 cell except argmax (10,1). Chaos is the worst case: henon k=1 needs 4-decimal arithmetic, which is out of reach for almost everything in these suites.

Mitigations, in order of importance:

1. **Extend the grids downward (level 0, -1, -2).** Our generators already parameterize this: automata width 5 (not 10) at k=1 with simpler rules (rule 254 / OR-spread before rule 110), argmax with domain 5 single-mode, maze 3×3 with the answer being a 2-move path, SAT n=2–3, "k=0" identity/copy controls (output the input state) to separate format failure from computation failure. The copy control is essential: a model that can't echo a 10-bit string in the answer format tells us nothing about its automata cliff.
2. **Lean on gradated metrics, not binary accuracy.** This is our secret weapon and it's already built. Per-cell Hamming fraction on automata gives a measurable per-step fidelity p even when binary accuracy is 0 (a model getting 80% of cells right at k=1 has p≈0.8 measurable from cell errors); H2's accuracy≈p^k framing converts "where is the cliff" into "what is p," and p is estimable for much weaker models than any binary cliff. Same for tour-length ratio (TSP) and digit-precision (chaos). The A1 regression can be run on p (or on logistic-fit cliff midpoint where it exists) rather than on a binary cliff position that may not exist for half the suite.
3. **Pilot before committing ($20–50, 1–2 days).** Run Pythia-410M, Pythia-2.8B, and Pythia-12B (spans 40× in params and 24→36 layers... actually 24/32/36 layers — also note OLMo-2-7B as a modern-data sanity check) on the 3 easiest levels of all 6 families plus the level-0 extensions, 8 seeds, few-shot prompting, on one rented A100/H100 with vLLM. Decision rule: if Pythia-12B can't clear 50% on any family's level 0–1, the suites can't see our tasks and A1 needs either much easier families or our own models trained with task-adjacent data; if 410M already shows partial credit on gradated metrics, the full sweep is green-lit. My prediction (registrable): argmax and automata-Hamming will show signal at 410M+; mazes and SAT binary accuracy will need 2.8B+; chaos will be at floor for everything below ~7B and should be dropped or replaced with integer-map variants for the suite study.

### The format-following confound

Base models do not reliably emit "ANSWER: X". What the ladder-evaluation literature actually does: lm-evaluation-harness and the OLMES standard evaluate base models with (a) few-shot in-context examples (typically 5-shot), (b) loglikelihood scoring over enumerated answer candidates with length normalization wherever possible (this is how MMLU/ARC/HellaSwag numbers for Pythia/OLMo are produced), and (c) generative evaluation with regex extraction only where the answer space is open, accepting higher variance. The "Lessons from the Trenches" paper (EleutherAI 2024) explicitly recommends restricted answer spaces and notes structured/constrained generation as the variance-reducing alternative.

Concrete plan per family (we control the generators, so we can do better than generic benchmarks):

- **SAT (decision form):** 2-candidate logprob comparison (SAT/UNSAT) — pure logprob, zero format risk. Certificate validity becomes a separate generative measure for stronger models only.
- **Argmax:** logprob over the index candidates (domain ≤ a few hundred at the easy end) or constrained decode of an integer.
- **Automata:** constrained decode over {0,1}^w, or teacher-forced per-cell logprob accuracy (feed the correct prefix, score each next cell) — this gives the Hamming/fidelity metric directly with no parsing at all. This is the cleanest family for base models and (per H2) the most theoretically loaded; make it the A1 headline family.
- **Maze:** constrained decode over move tokens {U,D,L,R}*; validity is checkable per-step.
- **TSP:** constrained decode of a permutation; gradated tour-ratio scoring.
- **Chaos:** logprob scoring doesn't help with 4-decimal arithmetic; expect floor (see pilot).
- All families: 5-shot prompts with byte-identical format demonstrations, same shots across all models, shots drawn from a held-out seed range.

On light "format-only" SFT: I recommend **against** it as the primary method. It contaminates the measurement in a way reviewers will (rightly) poke at — SFT on formatted task examples teaches task structure, not just format, and the contamination is worst exactly for the small models where you'd need it most; "format-only" is not a well-defined boundary for these procedural families since the format *is* the task output structure. If a tie-breaker is ever needed, the defensible version is: SFT every model in the suite identically on format demonstrations from *different* families than the one being measured, and show on a mid-size model that it leaves logprob-scored accuracy unchanged. But constrained decoding via vLLM's guided-decoding (or outlines/xgrammar) makes the whole problem mostly moot — we have logit access for every model in every suite, which is the decisive advantage of open weights over the frontier APIs.

One nuance worth pre-registering: few-shot CoT vs direct answering interacts with the depth question (see executive summary). Run both modes; the no-CoT mode is where circuit-depth theory makes its sharpest prediction, and the CoT mode connects to the Haiku results (which had thinking enabled).

### Observational regression across heterogeneous public models

Tempting (40+ open models with public params and layer counts; training tokens public for many: Llama 3 ≈15T, Qwen3 ≈36T, OLMo 2 ≈4–6T, SmolLM3 ≈11T) and nearly worthless as primary evidence. Params, layers, and tokens are collinear across the public-model population (everyone scales them together, r likely >0.9); data quality is unobservable and correlates with recency, which correlates with everything; post-training (instruction tuning, reasoning distillation) differs per model and dominates small-model task behavior; tokenizers differ; contamination with reasoning-adjacent synthetic data (every 2025–2026 model trains on math/code traces) differs and is undisclosed. A regression of cliff position on (params, layers, log tokens) over ~40 models has maybe 2 effective degrees of freedom of independent variation. Verdict: run it cheaply as a *descriptive supplement* (it produces a nice figure and the data costs nothing extra), but the paper's causal claims must rest on the within-suite contrasts where exactly one factor varies. This is also the honest answer to "would reviewers accept it": they would not, and they should not.

### Inference compute and cost

Per-model workload: 6 families × 10 levels × 8 seeds = 480 C0 samples, ~0.7k prompt + (with few-shot) ~2k prompt, ≤2k output tokens for direct-answer mode, more for CoT mode — call it ~2–5M tokens per model per mode. vLLM on one H100 batches this in roughly 5–20 minutes for ≤2B models and ≤1 hour for 7–13B; checkpoint download/load overhead is comparable to compute time for small models.

| Sweep | Model-evaluations | Est. H100-hours | Est. cost @$2.5/hr |
|---|---|---|---|
| Pilot (3 models × easy levels × 2 modes) | 3 | 3–6 | **$10–20** |
| Core: 40 final-checkpoint models (Gemstones 22 + Pythia 8 + selected DataDecide/FineWeb/OLMo), 2 prompt modes | 80 | 40–100 | **$100–250** |
| Data-quantity axis: 10 checkpoints × 8 Pythia sizes | 80 | 30–80 | $75–200 |
| Data-quality axis: 25 DataDecide recipes at 2 sizes (300M, 1B) ×3 seeds | 150 | 40–100 | $100–250 |
| Re-runs, prompt iteration, ablations (2× contingency) | — | 100–250 | $250–600 |
| **Total inference-only program** | ~300 | **150–500** | **$400–1,300** |

Serverless endpoints (Together $0.10/M for <4B models; Fireworks $0.10/M <4B, $0.20/M 4–16B) would make token costs trivially small (~$0.25–1 per model), **but none of the suite models (Pythia, Gemstones, DataDecide, FineWeb ablations) are hosted serverless** — they only host mainstream models (Qwen, Llama, GPT-OSS, OLMo instruct variants). Self-hosted vLLM on rented GPUs is the only real option, and at these scales it is cheap anyway. A single 4090/A100 from Vast.ai ($0.4–1.0/hr) handles every model ≤2.8B, halving the table above; H100 needed only for the 7–13B tail.

## Part 3 — Training our own (if the suites fall short)

Verified price anchors (June 2026): H100 on-demand $1.90–3.29/GPU-hr (Hyperstack $1.90 PCIe, Vast.ai median ~$2.13 SXM, RunPod $2.89–3.29, Lambda $2.99–3.99); A100-80G $0.67–1.49/hr; 8×H100 nodes $13–24/hr. Real training datapoints: TinyLlama-1.1B = 3,456 A100-hours per 300B tokens (~$3.5–7k per 300B tokens at 2026 A100 prices; full 3T-token run ≈ 34,560 A100-hr ≈ $35–50k as reported); Pythia-1B = 4,830 A100-hours per 300B tokens; Karpathy's llm.c GPT-2-774M ≈ $2k for 150B tokens on 8×A100 (~6 days); GPT-2-124M to 3.28 loss = 45 min on 8×H100 in llm.c, now under 3 minutes in modded-nanogpt (i.e., a fully-trained GPT-2-small-quality model costs ~$1 of compute with a modern recipe — the existence proof that small ladders are pocket change); Chinchilla-optimal 1.1B (22B tokens) ≈ 32 hours on 8×A100 per the TinyLlama repo.

FLOPs arithmetic used below: compute ≈ 6·N·D; H100 bf16 ≈ 990 TFLOPS peak; assume 35–45% MFU (OLMo 3 reports 41–43%; modded-nanogpt exceeds this) → ~3.5–4.5e14 FLOP/s sustained per GPU.

### Option A — bespoke ladders (one factor per ladder)

| Ladder | Design | FLOPs | H100-hrs (40% MFU) | Compute $ @$2.5 | Realistic total (data prep, retries, evals, 2–3× margin) |
|---|---|---|---|---|---|
| **Depth ladder** (most likely need) | 6 shapes at fixed ~500M params (e.g. 6/10/16/24/40/64 layers, width adjusted), 10B tokens each (Chinchilla 20×), identical data/order/tokenizer | 6 × 3e19 | ~120 | ~$300 | **$1k–3k** (deep-thin shapes train 2–3× slower in wall-clock per Gemstones' GPU-hour analysis) |
| Depth ladder, overtrained | Same but 50B tokens each (lower floors, better signal) | 6 × 1.5e20 | ~600 | ~$1.5k | **$3k–8k** |
| **Param ladder** | 8 models 100M–1B, Chinchilla 20× each, fixed shape family and data | Σ ≈ 2.5 × 1B-run = 3e20 | ~210 | ~$525 | **$1.5k–4k** |
| **Data-quality pair** | 2 recipes × 3 sizes (160M/410M/1B), 20× tokens | ~3e20 | ~210 | ~$525 | $1.5k–4k — **but don't: DataDecide already did this 25× over** |
| Full custom mini-DataDecide | Don't. | — | — | — | — |

What each answers: the depth ladder answers A1's sharpest sub-question (does depth-in-layers move serial-family cliffs at fixed params?) with cleaner LR/data control than Gemstones and with task-relevant token mixes if we want them (e.g. guaranteeing zero synthetic-reasoning data, which no public suite documents to our standard). The param ladder mostly duplicates Pythia with modern data — only worth it if Pythia's 2023-era Pile data turns out to put everything below our task floor and DataDecide's better recipes don't reach big enough sizes.

A further option worth naming because it is so cheap: a **synthetic-curriculum ladder** in the modded-nanogpt regime (124M–350M models, minutes-to-hours per run) where we *control* exposure to task-adjacent data (e.g. does any automata-like data in pretraining create the cliff?). At ~$1–10 per run this enables dozens of controlled runs for <$500 and connects A1 to the data-quality axis mechanistically. This is the "Physics of Language Models"-style move (Allen-Zhu & Li's small-model synthetic-pretraining papers — well-received precedent for drawing big conclusions from small controlled models).

### Option B — piggyback on existing checkpoints

Continued pretraining or annealing from suite checkpoints (e.g. take Pythia-1B at step 70k and branch it onto two data recipes; or take a Gemstone and continue 5B tokens) costs $10–200 per branch (a 1B model × 5B tokens ≈ 3e19 FLOPs ≈ 20 H100-hr ≈ $50). It buys data-recipe contrasts at matched initialization. The confound is real but manageable: the base checkpoint's data is shared (good — it's a controlled prefix), but anneal-phase dynamics differ from from-scratch training, so effects measured this way are "late-training data effects," not "pretraining data effects." HuggingFace's own dclm-edu work found mid-training ablation results did not transfer to full pretraining — treat Option B as hypothesis-generation, not as the registered test. Format-only SFT (if we ever do it despite my recommendation) also lives here at ~$5–20 per model with LoRA.

### Scientific credibility of sub-2B results

Precedents for small-model controlled studies being well-received: Pythia (cited everywhere, the de-facto standard for "we need a controlled ladder"), DataDecide (ICML 2025), Gemstones (NeurIPS 2025), MobileLLM (ICML 2024), Petty et al. (NAACL 2024), Tay et al. (ICLR 2022), Allen-Zhu's Physics-of-LM series. Reviewers accept small-suite causal claims; what they will not accept is an unargued leap from "depth moves cliffs in 500M models" to "this is why Haiku fails at k=2." Our bridge is H12 (already registered): show the *functional forms* (exponential decay in k, fidelity p, Lyapunov horizon) are shared from 70M to frontier, with only constants shifting — then factor effects measured on the small suite are effects on those constants, and the frontier connection is an extrapolation along a measured invariance rather than a hand-wave. If the functional forms do NOT transfer down to 1B-scale models, that is itself a publishable surprise and A1 dies honestly.

## Recommended path (decision tree)

1. **Now (~$20):** pilot — Pythia 410M/2.8B/12B + OLMo-2-7B on easy levels + level-0 extensions, both prompt modes, constrained decoding. Gate everything on this.
2. **If pilot shows measurable range (~$400–1,300):** full inference program — Gemstones (depth×params), Pythia (params + data-quantity + dedup), DataDecide 300M+1B slice (data quality), FineWeb 1.8B octet (data quality at the largest matched size). Pre-register the CoT/no-CoT × depth interaction before looking.
3. **If the suites' floors are too high but the task floor is reachable by ~7B:** drop to the gradated-metric/fidelity-p analysis (works lower), and supplement with the observational regression as descriptive color.
4. **Only if depth axis is unmeasurable on Gemstones (~$3k–8k):** train the bespoke overtrained depth ladder at 500M with modern data. Budget cap including retries: $10k. Anything beyond that means A1 needs frontier-scale models and should be reframed or dropped.

## Unverified claims register

- Gemstones model license assumed Apache 2.0 from "open-source" language; **not confirmed** — check the HF collection before building on it. Checkpoint interval: project page says every 2B tokens; one arXiv rendering says 22B (4,000 total checkpoints is consistent with ~2B). Whether Gemstones models will few-shot well enough at 50M–2B is exactly what the pilot tests.
- DataDecide intermediate checkpoints were marked "uploading after initial release" (2025) — confirm they exist before planning the data-quality × quantity interaction analysis.
- Petty et al. checkpoint non-release: inferred from absence of a release link, not confirmed.
- The claim "no serverless host offers Pythia/Gemstones/DataDecide" is based on current Together/Fireworks catalogs; niche hosts may exist but won't change the economics.
- MFU and throughput numbers for cost tables are estimates anchored on OLMo 3 (41–43%), TinyLlama (56% on A100), and modded-nanogpt reports; per-ladder costs could vary ±2× with engineering quality.
- 2026 GPU prices verified via aggregator sites (gpuperhour.com, gpucloudlist.com) on 2026-06-12; spot markets move.

## Key sources

Gemstones: arXiv 2502.06857, github.com/mcleish7/gemstone-scaling-laws (NeurIPS 2025). Pythia: arXiv 2304.01373, github.com/EleutherAI/pythia. DataDecide: arXiv 2504.11393, github.com/allenai/DataDecide (ICML 2025). MobileLLM: arXiv 2402.14905 (ICML 2024). Petty et al.: arXiv 2310.19956 (NAACL 2024). OLMo 2: arXiv 2501.00656; OLMo 3 (Nov 2025): allenai.org. FineWeb ablations: HF HuggingFaceFW/ablation-model-* collection. Cerebras-GPT: arXiv 2304.03208. LLM360: arXiv 2312.06550. TinyLlama: arXiv 2401.02385. llm.c GPT-2 cost reports: github.com/karpathy/llm.c discussions #481. modded-nanogpt: github.com/KellerJordan/modded-nanogpt. Eval methodology: EleutherAI lm-evaluation-harness; "Lessons from the Trenches" arXiv 2405.14782; OLMES (Gu et al. 2024); EleutherAI multiple-choice-normalization blog. Emergence/floor: Du et al. "Emergent Abilities from the Loss Perspective" (ICLR 2024); Cobbe et al. GSM8K (2021). Depth theory: Merrill & Sabharwal TC0/CoT-expressivity line (cited from memory — verify exact bounds when writing the paper).
