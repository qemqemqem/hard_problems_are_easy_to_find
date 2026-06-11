# Decisions & Open Questions

## Decided (2026-06-11)

| # | Decision | Notes |
|---|---|---|
| D1 | **Harness: Inspect AI** | Re-examined under the code-execution extension — the extension *strengthens* the choice (sandboxed `python()` tool + agent loops are Inspect's home turf; see [HARNESSES.md](./HARNESSES.md) §Code execution). |
| D2 | **Phase 1 shortlist: all 6 families** | TSP, 3-SAT@phase-transition, maze pathfinding, automaton simulation, chaotic maps, argmax. Implementation dispatched. |
| D3 | **Phase 1 API budget: ~$50** | Haiku 4.5. Rough envelope: 6 families × 5 levels × 30 instances × 3 conditions × ~2k tok ≈ $30–45 — fits with headroom for calibration runs. Instance counts trimmed to stay inside. |
| D4 | **Frontier model set + budget: decide after Phase 1 results** | Revisit with real per-instance token data in hand. |
| D5 | **Execution conditions are a primary experimental axis**, not an ablation. Three conditions: **C0** pure thinking (no code), **C1** write one program, we run it, stdout is the answer; **C∞** interactive python, run as many times as needed. | Core question: is C1 closer to C0 or to C∞? Genuinely uncertain → pre-registered in [HYPOTHESES.md](./HYPOTHESES.md) (H5). |
| D6 | **Reframed thesis**: failure of *processing*, not *understanding* — and a hint that foundation models should grow beyond pure-transformer token computation. | DESIGN.md §1 updated. In conversation with RASP-L / TC⁰ / CoT-expressivity literature. |
| D7 | **Abstention scoring extension adopted** ("+1 correct / −1 wrong / 0 for 'I don't know'") | Pre-registered as H8; run on a subset, Phase 1 if budget allows, else Phase 2. |

## Open

- **Q-A. Paper framing:** elevate theory-testing (RASP-L/TC⁰ predictions + Lyapunov horizons) to the *primary* framing, with NP-hard families as calibration anchors? My recommendation: yes — see LITERATURE.md §8 for why the alternative framing is crowded.
- **Q-B. Hybrid family for Phase 2** (linguistic × computational, PROBLEMS.md Category 6): which one to build first? My lean: anagram-clue crossword fill — fully mechanical generation/verification, genuinely uncertain whether C∞ closes it.
- **Q-C. C∞ execution cap:** 10 tool calls? Token-budget cap instead? (Affects cost and comparability; proposal in HYPOTHESES.md definitions.)
- **Q-D. Venue** for the paper (benchmark/dataset track vs. workshop first). Defer until Phase 2 data exists.
