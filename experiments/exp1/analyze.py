"""Experiment 1 analysis: difficulty-response curves for C0/C1/C-inf.

Reads the latest eval log in each of logs/exp1_c0, logs/exp1_c1,
logs/exp1_cinf, joins samples back to grid levels via the deterministic
sample-id scheme, and emits plots + summary tables to experiments/exp1/out/.

Usage: python experiments/exp1/analyze.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from inspect_ai.log import read_eval_log

sys.path.insert(0, str(Path(__file__).parent))
from make_grid import GRID  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "out"

CONDITIONS = {  # condition -> (log dir, scorer name)
    "C0": ("logs/exp1_c0", "family_scorer"),
    "C1": ("logs/exp1_c1", "c1_scorer"),
    "C∞": ("logs/exp1_cinf", "family_scorer"),
}

COLORS = {"C0": "#d62728", "C1": "#1f77b4", "C∞": "#2ca02c"}

FAMILIES = list(GRID)


def diff_id(difficulty: dict) -> str:
    """Mirror of the adapter's sample-id difficulty encoding."""
    return "_".join(f"{k}{v}" for k, v in sorted(difficulty.items()))


def level_label(family: str, difficulty: dict) -> str:
    """Short human-readable tick label for one grid level."""
    d = dict(difficulty)
    if family == "tsp":
        return str(d["n"])
    if family == "maze":
        return str(d["size"])
    if family == "sat":
        return str(d["n_vars"])
    if family == "argmax":
        return f"{d['domain_size']},{d['n_modes']}"
    if family == "chaos":
        return f"{'H' if d['system'] == 'henon' else 'L'}{d['k']}"
    if family == "automata":
        return str(d["k"])
    return diff_id(d)


# (family, diff_id) -> (level index 1-10, tick label)
LEVEL_OF = {
    (fam, diff_id(diff)): (i + 1, level_label(fam, diff))
    for fam, levels in GRID.items()
    for i, diff in enumerate(levels)
}


def load_condition(cond: str) -> pd.DataFrame:
    log_dir, scorer_name = CONDITIONS[cond]
    paths = sorted((REPO / log_dir).glob("*.eval"))
    if not paths:
        raise FileNotFoundError(f"no eval logs in {log_dir}")
    log = read_eval_log(str(paths[-1]))
    if log.status != "success":
        print(f"WARNING: {cond} log status = {log.status}")
    rows = []
    for s in log.samples or []:
        sid = str(s.id)
        family = sid.split("_", 1)[0]
        # id = {family}_{diff_id}_s{seed}
        rest, seed = sid.rsplit("_s", 1)
        did = rest[len(family) + 1 :]
        level, label = LEVEL_OF[(family, did)]
        sc = s.scores[scorer_name]
        meta = sc.metadata or {}
        rows.append(
            {
                "condition": cond,
                "family": family,
                "level": level,
                "tick": label,
                "seed": int(seed),
                "correct": bool(meta.get("correct", sc.answer == "C")),
                "value": float(sc.value),
                "label": meta.get("label", sc.explanation),
                "stop_reason": meta.get("stop_reason"),
                "tool_calls": sum(1 for m in s.messages if m.role == "tool"),
            }
        )
    return pd.DataFrame(rows)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def curve_figure(df: pd.DataFrame, metric: str, fname: str, title: str) -> Path:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey=True)
    for ax, family in zip(axes.flat, FAMILIES):
        fdf = df[df.family == family]
        ticks = (
            fdf[["level", "tick"]].drop_duplicates().sort_values("level")
        )
        for cond in CONDITIONS:
            g = (
                fdf[fdf.condition == cond]
                .groupby("level")
                .agg(k=("correct", "sum"), n=("correct", "size"), v=("value", "mean"))
                .reset_index()
                .sort_values("level")
            )
            if metric == "accuracy":
                y = g.k / g.n
                ci = [wilson_ci(int(k), int(n)) for k, n in zip(g.k, g.n)]
                lo = [y_i - c[0] for y_i, c in zip(y, ci)]
                hi = [c[1] - y_i for y_i, c in zip(y, ci)]
                ax.errorbar(
                    g.level, y, yerr=[lo, hi], color=COLORS[cond], marker="o",
                    markersize=4, capsize=2, linewidth=1.8, label=cond, alpha=0.9,
                )
            else:
                ax.plot(
                    g.level, g.v, color=COLORS[cond], marker="o", markersize=4,
                    linewidth=1.8, label=cond, alpha=0.9,
                )
        ax.set_title(family)
        ax.set_xticks(ticks.level)
        ax.set_xticklabels(ticks.tick, fontsize=7, rotation=45)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.25)
    axes.flat[0].legend(loc="lower left", fontsize=9)
    fig.suptitle(title, fontsize=13)
    fig.supxlabel("difficulty level (knob value)", fontsize=10)
    fig.tight_layout()
    out = OUT / fname
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def pooled_figure(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for cond in CONDITIONS:
        g = (
            df[df.condition == cond]
            .groupby("level")["correct"]
            .mean()
            .reset_index()
        )
        ax.plot(g.level, g.correct, color=COLORS[cond], marker="o", linewidth=2, label=cond)
    ax.set_xlabel("difficulty level (pooled across families)")
    ax.set_ylabel("accuracy")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks(range(1, 11))
    ax.grid(alpha=0.25)
    ax.legend()
    ax.set_title("Haiku 4.5: pooled accuracy by difficulty level")
    fig.tight_layout()
    out = OUT / "pooled_accuracy.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def effort_figure(df: pd.DataFrame) -> Path:
    cdf = df[df.condition == "C∞"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for family in FAMILIES:
        g = cdf[cdf.family == family].groupby("level")["tool_calls"].mean().reset_index()
        ax.plot(g.level, g.tool_calls, marker="o", linewidth=1.5, label=family)
    ax.set_xlabel("difficulty level")
    ax.set_ylabel("mean python-tool calls")
    ax.set_xticks(range(1, 11))
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    ax.set_title("C∞ effort: tool calls vs difficulty")
    fig.tight_layout()
    out = OUT / "cinf_effort.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = pd.concat([load_condition(c) for c in CONDITIONS], ignore_index=True)
    df.to_csv(OUT / "samples.csv", index=False)

    acc = (
        df.groupby(["family", "condition"])["correct"]
        .mean()
        .unstack("condition")
        .round(3)
    )
    print("\n=== accuracy by family x condition (pooled over levels) ===")
    print(acc.to_string())
    acc.to_csv(OUT / "accuracy_by_family.csv")

    lab = (
        df.groupby(["condition", "family", "label"])
        .size()
        .unstack("label", fill_value=0)
    )
    print("\n=== label taxonomy ===")
    print(lab.to_string())
    lab.to_csv(OUT / "label_taxonomy.csv")

    exhausted = df[df.stop_reason.astype(str).str.contains("max_tokens|length", na=False)]
    print(f"\ntoken-exhausted samples: {len(exhausted)}")
    if len(exhausted):
        print(exhausted.groupby(["condition", "family"]).size().to_string())

    p1 = curve_figure(df, "accuracy", "accuracy_curves.png",
                      "Haiku 4.5 — exact-answer accuracy by difficulty (8 seeds/cell, Wilson 95% CI)")
    p2 = curve_figure(df, "value", "value_curves.png",
                      "Haiku 4.5 — mean gradated score by difficulty")
    p3 = pooled_figure(df)
    p4 = effort_figure(df)
    print("\nplots:", *[str(p) for p in (p1, p2, p3, p4)], sep="\n  ")


if __name__ == "__main__":
    main()
