"""Summarize a calibration sweep log: mean gradated value + correct rate per level."""

import json
import sys
from collections import defaultdict

from inspect_ai.log import read_eval_log


def main(log_path: str) -> None:
    log = read_eval_log(log_path)
    rows = defaultdict(list)
    for s in log.samples:
        sc = s.scores["family_scorer"]
        level = str(s.id).rsplit("_s", 1)[0]
        rows[level].append((float(sc.value), bool(sc.metadata["correct"]), sc.metadata["label"]))
    print(f"{'level':42s} {'n':>2s} {'value':>6s} {'correct':>8s}  labels")
    for level in sorted(rows):
        vals = rows[level]
        n = len(vals)
        mv = sum(v for v, _, _ in vals) / n
        cr = sum(c for _, c, _ in vals) / n
        labels = ",".join(l for _, _, l in vals)
        print(f"{level:42s} {n:2d} {mv:6.2f} {cr:8.2f}  {labels}")


if __name__ == "__main__":
    main(sys.argv[1])
