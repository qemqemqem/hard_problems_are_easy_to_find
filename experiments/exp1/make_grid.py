"""Build the Experiment 1 grid spec (docs/EXPERIMENT_1.md section 2).

Emits experiments/exp1/grid.json in the sweep-spec format consumed by the
sweep/sweep_c1/sweep_cinf tasks, and dry-runs every (cell, seed) through
generate() so ground-truth feasibility failures surface here, not mid-eval.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from hard_problems.core import get_family

SEEDS = list(range(1, 9))

# Ten levels per family, ordinal. Anchored on calibration/calibrated.json;
# dense around each C0 cliff, extended past it for gradated-metric range.
# Upper ends capped by ground-truth feasibility (tsp n<=16, sat n_vars<=24).
GRID: dict[str, list[dict]] = {
    "tsp": [{"n": n} for n in [4, 6, 8, 9, 10, 11, 12, 13, 14, 16]],
    "maze": [{"size": s, "density": 0.25} for s in [3, 4, 5, 6, 7, 8, 10, 12, 16, 20]],
    "sat": [{"n_vars": v, "ratio": 4.27} for v in [4, 5, 6, 7, 8, 9, 10, 12, 16, 24]],
    "argmax": [
        {"domain_size": d, "n_modes": m}
        for d, m in [
            (10, 1), (20, 1), (50, 1), (50, 2), (100, 2),
            (100, 3), (200, 3), (500, 4), (1000, 6), (10000, 12),
        ]
    ],
    "chaos": [{"system": "henon", "k": 1}]
    + [{"system": "logistic", "k": k} for k in [1, 2, 3, 4, 5, 6, 8, 16, 32]],
    "automata": [
        {"width": 10, "k": k, "rule": 110} for k in [1, 2, 3, 4, 5, 6, 8, 12, 16, 32]
    ],
}


def main() -> None:
    spec = {
        family: [{"difficulty": diff, "seeds": SEEDS} for diff in levels]
        for family, levels in GRID.items()
    }
    for family, levels in GRID.items():
        fam = get_family(family)
        for diff in levels:
            t0 = time.monotonic()
            for seed in SEEDS:
                fam.generate(seed, **diff)
            dt = time.monotonic() - t0
            print(f"{family} {diff}: {len(SEEDS)} seeds in {dt:.2f}s")

    out = Path(__file__).parent / "grid.json"
    out.write_text(json.dumps(spec, indent=2))
    n = sum(len(levels) * len(SEEDS) for levels in GRID.values())
    print(f"\nwrote {out} ({n} samples per condition)")


if __name__ == "__main__":
    main()
