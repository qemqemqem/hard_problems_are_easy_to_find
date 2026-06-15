# A1_GPU_PROVIDER — Which GPU Rental Provider for the A1 Sweeps

**Status: investigated 2026-06-12 (web research; prices and availability spot-checked against provider pages the same day). Companion to A1_INFERENCE_PLAN.md (workload: one A100-80GB/L40S-class GPU, ~200GB of HF checkpoints, a 1–2 GPU-hour pilot, a 10–15 GPU-hour sweep, occasional follow-ups, total spend tens of dollars, everything orchestrated from the terminal by a coding agent after one-time account setup).**

## TL;DR

**Two of the four candidate providers (Railway, Vercel) sell no GPUs at all, so the on-list contest is Lambda vs GCP, and Lambda wins decisively on the criterion that matters: a single API key gets you full instance lifecycle, SSH-key management, and persistent-filesystem creation through one flat REST API with zero IAM/quota ceremony.** GCP's gcloud CLI is the most comprehensive tool in the field, but new accounts start with a GPU quota of zero and quota-increase requests are routinely auto-rejected for days-to-weeks — a real risk of being blocked before the pilot even starts. One honest off-list note: **RunPod is materially better than Lambda on price (A100 80GB $1.39–1.49/hr vs no 1x A100-80GB SKU at Lambda at all), storage ($0.07 vs $0.20/GB/mo), and instant availability**, with an equally scriptable CLI/REST API — it's what A1_INFERENCE_PLAN.md already assumed. Recommendation: **Lambda as the on-list primary (1x A6000 48GB at ~$0.80/hr fits every model in the plan), RunPod as the pragmatic alternative if Lambda capacity-polls get annoying, GCP only if an established billing account with GPU quota already exists.** Expected total: **~$25–50 on Lambda without a persistent filesystem (re-download per burst), ~$65–90 if you keep a 200GB filesystem for a month.**

## 1. The four candidates, honestly

| | Railway | Vercel | **Lambda** | GCP |
|---|---|---|---|---|
| Rentable GPUs? | **No — CPU-only platform** | **No — no GPU compute of any kind** | **Yes** — VMs: B200/H100/GH200/A100/A6000/A10/V100 | **Yes** — Compute Engine A2 (A100), G2 (L4), N1+T4 etc. |
| Suitable for vLLM ≤13B? | n/a | n/a | Yes (1x A6000 48GB, 1x GH200 96GB, 1x A100 40GB) | Yes (A100 80GB spot; L4 24GB too small for 12B bf16) |
| CLI quality | good CLI, wrong product | good CLI, wrong product | **No official CLI, but a clean flat REST API + good community CLIs; everything scriptable with curl+jq** | gcloud is the most complete CLI in existence |
| Auth model | — | — | **One API key, HTTP basic/bearer. Done.** | Project + billing link + API enablement + IAM + per-region per-GPU-type quota |
| Time-to-first-GPU (new account) | never | never | **Minutes** (subject to capacity, see §3) | **Days to weeks**: GPU quota starts at 0, auto-rejections documented through Mar 2026 |
| A100 80GB $/hr | — | — | $2.79/GPU but **8x-only SKU**; 1x fallbacks: A6000 $0.80, GH200 $1.49, H100 PCIe $2.49 | $5.07 on-demand / **$2.53 spot** (a2-ultragpu-1g, us-central1) |
| Persistent storage | — | — | Filesystems, **$0.20/GiB/mo**, billed hourly even when unmounted | PD-SSD ~$0.17/GB/mo + snapshots |
| Spot/preemptible | — | — | No — on-demand only, per-minute billing | Yes (60–91% off, but only ~12% off on G2/L4) |

**Railway**: no GPU offering as of June 2026. Their own feedback board thread ("GPU Support", opened 2024) is still in "please upvote, we'll gauge demand" state with unanswered "any updates?" posts from Jan–Mar 2026; third-party reviews dated March 2026 state flatly "Railway is CPU-only" ([station.railway.com/feedback/gpu-support-56d19c42](https://station.railway.com/feedback/gpu-support-56d19c42), [aibytes.blog Railway-vs-AWS comparison](https://aibytes.blog/comparisons/railway-vs-aws-can-a-100m-ai-native-cloud-platform-actually-compete)). Their infra investment went into "Railway Metal" (own CPU hardware). Lovely CLI, nothing to run vLLM on. **Disqualified.**

**Vercel**: still a frontend/serverless-CPU cloud. Vercel Sandbox explicitly does not provide GPU compute; their own positioning is "Vercel is not a GPU provider — pair us with a GPU backend" ([northflank.com Modal-vs-Vercel-Sandbox comparison](https://northflank.com/blog/modal-vs-vercel-sandbox), [eseospace.com review](https://eseospace.com/blog/why-vercel-is-the-best-host-for-your-ai-app/)). **Disqualified.**

**Lambda (Lambda Cloud / On-Demand Cloud)**: real GPU VMs with per-minute billing, no egress fees, Lambda Stack (CUDA/PyTorch) preinstalled, and a flat REST API that covers the entire lifecycle. Details in §2–3. **Workable; recommended on-list pick.**

**GCP**: the GPU offering itself is fine for us — a2-ultragpu-1g (1x A100 80GB) at $5.07/hr on-demand / ~$2.53/hr spot in us-central1, or A100 40GB a2-highgpu-1g ~$1.80/hr spot ([cloud.google.com accelerator-optimized pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized)). gcloud genuinely does everything: `gcloud compute instances create --accelerator=type=nvidia-tesla-a100,count=1 --provisioning-model=SPOT --max-run-duration=4h` (built-in auto-kill!), `gcloud compute ssh/scp`, disks, snapshots, quotas. But the friction is exactly as feared, plus one blocker the user may not have priced in: **new projects have `GPUS_ALL_REGIONS = 0` and quota-increase requests from young billing accounts are auto-rejected** — Google's own docs say quota is granted automatically only "if your project has an established billing history", and developer-forum threads from Feb–Mar 2026 show paid accounts stuck at "Enter a new quota value between 0 and 0" with both console and `gcloud alpha quotas` rejected ([docs.cloud.google.com GPU quota](https://docs.cloud.google.com/compute/docs/gpus/create-vm-with-gpus), [forum thread Mar 2026](https://discuss.google.dev/t/unable-to-increase-gpu-quota-gpus-all-regions-stuck-at-0-console-and-cli-both-rejected/338502), [forum thread Feb 2026](https://discuss.google.dev/t/how-to-increase-nvidia-t4-cpus-quota-for-new-paid-users/330929)). For a tens-of-dollars workload starting from scratch, that's a possible multi-day stall for zero benefit. **Workable only with a pre-existing, quota-blessed account; otherwise last resort.**

## 2. Lambda CLI/API capability assessment

There is **no official first-party CLI** — Lambda's docs route all automation through the Cloud API ([docs.lambda.ai on-demand overview](https://docs.lambda.ai/public-cloud/on-demand/), [API browser: docs-api.lambda.ai/api/cloud](https://docs-api.lambda.ai/api/cloud)). In practice this is a feature, not a gap, for agent orchestration: the API is small, flat, and entirely driven by one bearer key. Coverage, verified against the API browser and docs:

| Capability | How | Scriptable? |
|---|---|---|
| List instance types + live per-region availability + prices | `GET /api/v1/instance-types` | yes |
| Launch instance (choose type, region, SSH keys, **attach filesystems**, custom image, cloud-init user data) | `POST /api/v1/instance-operations/launch` with `file_system_names: [...]` | yes |
| List / get / restart / terminate instances | `GET /api/v1/instances`, `POST .../restart`, `POST .../terminate` | yes |
| SSH key management (add/list/delete; can upload your existing pubkey) | `POST/GET/DELETE /api/v1/ssh-keys` | yes |
| Persistent filesystems: **create**, list (incl. usage), delete | `POST /api/v1/filesystems` to create (added ~2025 after being console-only); list is the inconsistently-named `GET /api/v1/file-systems` ([filesystems doc](https://docs.lambda.ai/public-cloud/filesystems/)) | yes |
| Firewall rules, images | API endpoints exist | yes |
| Billing/spend visibility | **Console only** (Usage page) — no billing API endpoint | **no — the one real gap** |
| Spot / auto-terminate-on-idle | **Not offered** — on-demand only, you must terminate explicitly | no (script it) |

Community CLIs wrap this API if you'd rather not curl: **`lambda-ai-cloud-api-client`** on PyPI (command `lai`; `lai types --available`, `lai start --cheapest --available --min-gpus 1 --ssh-key K`, `lai ls`, `lai stop`; actively maintained, releases through Dec 2025) and **Strand-AI/lambda-cli** (npm; `lambda start -g <type> -s <key> -f <filesystem>`, plus `lambda find` which **polls until a GPU type becomes available then auto-launches** — useful given §3). There's also a community Terraform provider. All of them are thin wrappers over the same API, so the agent can mix curl and CLI freely.

Two structural constraints to design around ([filesystems doc](https://docs.lambda.ai/public-cloud/filesystems/), [billing doc](https://docs.lambda.ai/public-cloud/billing/)): **(1) filesystems are region-pinned and can only be attached at instance launch** — never to a running instance; pick one region (e.g. us-east-3) and create both filesystem and every instance there; **(2) filesystem billing ($0.20/GiB/mo, hourly increments) runs as long as the filesystem exists, mounted or not** — 200GB parked for a month is $40, which at our scale is a first-order cost (see §5 for the cheaper re-download strategy).

## 3. Availability reality at Lambda

The catalog ([docs.lambda.ai instance types, Dec 2025](https://docs.lambda.ai/public-cloud/on-demand/)) has **no 1x A100 80GB SKU** — A100 SXM 80GB is 8-GPU-only ($2.79/GPU/hr → $22.3/hr, absurd for us). The single-GPU menu that matters for a ≤12B-bf16 workload (≈24GB weights): **1x A6000 48GB (~$0.80/hr)** — the L40S-class workhorse, fits everything in the plan with room to spare; **1x GH200 96GB ($1.49/hr)** — most VRAM per dollar but **ARM (aarch64) host CPU**, so vLLM/torch wheels are a separate lane (supported since vLLM 0.8.x but expect occasional pip friction; test in the pilot before relying on it); **1x A100 40GB ($1.29–1.99/hr)** and **1x H100 PCIe ($2.49/hr)** as faster fallbacks; 1x A10 24GB ($0.75/hr) only if the 12B models are dropped. Lambda has no spot tier and single-GPU types are **frequently sold out per region** — independent April–May 2026 testing reports queues of minutes-to-hours for popular types ([sub-pulse.com A100 comparison](https://sub-pulse.com/blog/a100-cloud-pricing-comparison/)); the mitigation is exactly the loop the community CLIs ship (`lambda find` / poll `GET /instance-types` for `regions_with_capacity_available` across all regions and take the first hit — A6000/A10 are much less contended than A100/H100).

## 4. Recommended end-to-end flow (Lambda)

**Manual, one-time (the user, ~10 minutes):** (1) create account at [cloud.lambda.ai](https://cloud.lambda.ai) and add a payment card (Settings → Billing); (2) generate an API key at cloud.lambda.ai/api-keys/cloud-api; (3) hand the key to the agent (e.g. `export LAMBDA_API_KEY=...` in the project env). That's the entire human surface — SSH keys, filesystems, instances are all API-creatable.

**Scripted (the agent), with raw curl so there's no dependency to trust:**

```bash
API=https://cloud.lambda.ai/api/v1   # legacy alias: cloud.lambdalabs.com/api/v1
AUTH="Authorization: Bearer $LAMBDA_API_KEY"

# 0. one-time: register our SSH public key
curl -s -H "$AUTH" -X POST $API/ssh-keys -H 'Content-Type: application/json' \
  -d "{\"name\":\"a1-key\",\"public_key\":\"$(cat ~/.ssh/id_ed25519.pub)\"}"

# 1. (optional) persistent filesystem for the checkpoint cache — same region as instances, forever-billed until deleted
curl -s -H "$AUTH" -X POST $API/filesystems -H 'Content-Type: application/json' \
  -d '{"name":"a1-hf-cache","region":"us-east-3"}'

# 2. find capacity: poll until our preferred types have a region with stock
curl -s -H "$AUTH" $API/instance-types | jq -r '
  .data | to_entries[] | select(.key|test("gpu_1x_(a6000|a100|gh200|h100_pcie)")) |
  "\(.key)\t$\(.value.instance_type.price_cents_per_hour/100)/hr\t\([.value.regions_with_capacity_available[].name]|join(","))"'

# 3. launch with the filesystem attached (attach is launch-time-only!)
ID=$(curl -s -H "$AUTH" -X POST $API/instance-operations/launch -H 'Content-Type: application/json' \
  -d '{"region_name":"us-east-3","instance_type_name":"gpu_1x_a6000",
       "ssh_key_names":["a1-key"],"file_system_names":["a1-hf-cache"],"name":"a1-sweep"}' \
  | jq -r '.data.instance_ids[0]')

# 4. poll until active, grab IP (boot is ~3-5 min)
until [ "$(curl -s -H "$AUTH" $API/instances/$ID | jq -r .data.status)" = active ]; do sleep 20; done
IP=$(curl -s -H "$AUTH" $API/instances/$ID | jq -r .data.ip)

# 5. run the sweep (filesystem mounts at /lambda/nfs/a1-hf-cache; Lambda Stack has CUDA/Python ready)
ssh ubuntu@$IP 'export HF_HOME=/lambda/nfs/a1-hf-cache/hf HF_HUB_ENABLE_HF_TRANSFER=1 &&
  pip install inspect-ai vllm hf_transfer && bash run_a1.sh'   # run_a1.sh per A1_INFERENCE_PLAN §5

# 6. retrieve results
rsync -avz ubuntu@$IP:~/logs/a1/ ./logs/a1/

# 7. teardown — Lambda has NO stop state and NO idle auto-kill; terminate or keep paying
curl -s -H "$AUTH" -X POST $API/instance-operations/terminate -H 'Content-Type: application/json' \
  -d "{\"instance_ids\":[\"$ID\"]}"
```

**Gotchas**: (a) **terminate is the only off-switch** — per-minute billing runs until you call it, so make `run_a1.sh`'s last act `curl .../terminate` from inside the box (the API key works from anywhere) or run a local watchdog (`sleep 6h && terminate`) before going to bed; (b) filesystem ↔ instance **region pinning** — if your region has no capacity, a filesystem there is useless that day, which is an argument for the no-filesystem strategy below; (c) the **filesystem bills while you sleep** ($40/mo for 200GB) — for 2–3 widely-spaced bursts it's cheaper to skip it, use the instance's huge included local SSD (0.5–1.4 TiB on 1x types, free), and re-download 200GB per burst (~30–60 min of GPU time ≈ $0.50–1 with hf_transfer; downloads are free, no ingress/egress fees); keep the filesystem only if bursts will be days apart during an active week; (d) no billing API — check the console Usage page occasionally, or track spend as hours×rate in the run log; (e) GH200 is aarch64 — verify the vllm wheel installs in the pilot before counting on it as the big-VRAM fallback.

## 5. Cost estimate (top pick: Lambda, 1x A6000 $0.80/hr; A100-40GB $1.99/hr shown as the fast lane)

| Item | Hours | A6000 | A100 40GB |
|---|---|---|---|
| Pilot | 1–2 | $1–2 | $2–4 |
| Full A1 sweep (budgeted, per A1_INFERENCE_PLAN §3) | 10–15 | $8–12 | $20–30 |
| Follow-ups | ~5 | ~$4 | ~$10 |
| Re-download checkpoints 3 bursts (no filesystem) | ~2 | ~$2 | ~$4 |
| **Total, re-download strategy** | | **~$15–20** | **~$36–48** |
| 200GB persistent filesystem, 1 month (alternative) | | +$40 | +$40 |
| **Total, persistent-filesystem strategy** | | **~$55–60** | **~$75–90** |

For calibration: the same workload on off-list RunPod (L40S $0.86/hr or A100 80GB $1.39–1.49/hr, network volume $0.07/GB/mo → $14/mo) lands at **~$18–45 all-in including a month of storage** ([runpod.io/pricing](https://www.runpod.io/pricing)).

## 6. Off-list honorable mentions (if Lambda capacity-polling gets old)

| Provider | One-line verdict |
|---|---|
| **RunPod** | The actual best fit for this workload: A100 80GB $1.39–1.49/hr / L40S $0.86/hr, `runpodctl pod create --gpu-id "NVIDIA A100 80GB PCIe" --network-volume-id ... --ports 22/tcp` + full REST API + cheap network volumes ($0.07/GB/mo) + instant capacity across 30+ regions ([docs.runpod.io](https://docs.runpod.io/runpodctl/reference/runpodctl-pod)); the only honest knock vs Lambda is container-shaped instances (pick a CUDA image) rather than full VMs, and community-cloud hosts vary in quality (use Secure Cloud). |
| **Modal** | Best-in-class orchestration-as-code (Python SDK, per-second billing, volumes), but it's a serverless-function model, not an SSH box — the per-model `vllm serve` loop would need restructuring into Modal functions; L40S $1.95/hr is 2× RunPod. Overkill here. |
| **Vast.ai** | Cheapest (A100 80GB $0.90–1.50/hr) with a real CLI (`vastai search offers / create instance`), but marketplace host quality/reliability variance is the wrong tradeoff for a one-evening sweep. |
| **DigitalOcean (ex-Paperspace)** | Proper VMs, `doctl` is a good CLI, L40S/RTX-6000-Ada from ~$0.76–1.57/hr; fine but no advantage over RunPod/Lambda, fewer GPU regions. |
| **Fly.io** | Out — GPU product is being killed: official deprecation July 31, 2026 ([community.fly.io](https://community.fly.io/t/gpu-migration-fly-io-gpus-will-be-deprecated-as-of-july-31-2026/27110)). |
