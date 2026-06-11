"""Wave Regime Gated 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_gated import (
    BASE_LABEL,
    full_regime_gated_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "rule", "filter", "count", "n", "win_rate", "expectancy",
    "profit_factor", "robustness_gap", "improvement",
    "delta_expectancy", "delta_win_rate", "delta_profit_factor",
)


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v == 999.0:
        return "∞"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_regime_gated.png")
    df = stats.get("dataframe")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    if df is None or df.empty:
        for ax in axes:
            ax.text(0.5, 0.5, "no data", ha="center")
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return path

    gated = df[df["filter"] != BASE_LABEL].head(15)

    ax = axes[0]
    if not gated.empty:
        labels = [str(f)[:28] for f in gated["filter"]]
        vals = gated["improvement"].fillna(0).tolist()
        y = np.arange(len(labels))
        ax.barh(y, vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=6)
        ax.axvline(0, color="gray", ls="--", lw=0.8)
        ax.set_title("ΔExpectancy Ranking")
        ax.invert_yaxis()

    ax2 = axes[1]
    rob = df[df["filter"] != BASE_LABEL].dropna(subset=["robustness_gap"]).head(15)
    if not rob.empty:
        labels = [str(f)[:28] for f in rob["filter"]]
        vals = rob["robustness_gap"].tolist()
        y = np.arange(len(labels))
        ax2.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.set_title("Robustness Gap (lower=better)")
        ax2.invert_yaxis()

    ax3 = axes[2]
    if not gated.empty:
        xs = range(len(gated))
        ax3.bar(xs, gated["n"].tolist(), color="#2E7D32", alpha=0.85)
        ax3.set_xticks(xs)
        ax3.set_xticklabels([str(f)[:12] for f in gated["filter"]], rotation=45, ha="right", fontsize=6)
        ax3.set_title("Sample Count")
        ax3.set_ylabel("n")

    fig.suptitle("Regime Gated — RULE_B + Filters")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building regime gated analysis...")
    stats = full_regime_gated_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_regime_gated.csv"), index=False)
    png = _plot(stats)

    base = stats.get("base_rule", {})
    dim = stats.get("dimension", {})
    lines = [
        "# REPORT_WAVE_REGIME_GATED",
        "",
        "Regime-Gated Validation — RULE_B + Regime Filter",
        "",
        "## BASE_RULE (RULE_B)",
        "",
        f"- filter: {BASE_LABEL}",
        f"- n: {base.get('n', 0)}",
        f"- win_rate: {_fmt(base.get('win_rate'))}%",
        f"- expectancy: {_fmt(base.get('expectancy'))}%",
        f"- profit_factor: {_fmt(base.get('profit_factor'))}",
        f"- robustness_gap: {_fmt(base.get('robustness_gap'))}",
        "",
        "## Top Improvements",
        "",
        "| filter | n | Δexp | Δwin | improvement |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stats.get("top_improvements", [])[:15]:
        lines.append(
            f"| {r.get('filter', '')[:60]} | {r.get('n', 0)} | "
            f"{_fmt(r.get('delta_expectancy'))} | {_fmt(r.get('delta_win_rate'))} | "
            f"{_fmt(r.get('improvement'))} |"
        )
    lines.append("")

    lines.append("## Top Robust Rules")
    lines.append("")
    lines.append("| filter | n | robustness_gap | expectancy |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_robust", [])[:15]:
        lines.append(
            f"| {r.get('filter', '')[:60]} | {r.get('n', 0)} | "
            f"{_fmt(r.get('robustness_gap'))} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")

    lines.append("## Worst Filters")
    lines.append("")
    lines.append("| filter | n | improvement |")
    lines.append("|---|---:|---:|")
    for r in stats.get("worst_filters", [])[:10]:
        lines.append(
            f"| {r.get('filter', '')[:60]} | {r.get('n', 0)} | "
            f"{_fmt(r.get('improvement'))} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB (best filter vs BASE)")
    lines.append("")
    lines.append(f"- best filter: {dim.get('best_filter', '—')}")
    lines.append("")
    lines.append("| symbol | base_n | gated_n | base exp | gated exp | Δexp | reduction% |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for sym, cmp in dim.get("symbol", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('base_n', 0)} | {cmp.get('gated_n', 0)} | "
            f"{_fmt(cmp.get('base_expectancy'))} | {_fmt(cmp.get('gated_expectancy'))} | "
            f"{_fmt(cmp.get('delta_expectancy'))} | {_fmt(cmp.get('sample_reduction_pct'))} |"
        )
    lines.append("")

    lines.append("## 1h / 4h / 1d")
    lines.append("")
    lines.append("| tf | base_n | gated_n | base exp | gated exp | Δexp | reduction% |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for tf, cmp in dim.get("timeframe", {}).items():
        lines.append(
            f"| {tf} | {cmp.get('base_n', 0)} | {cmp.get('gated_n', 0)} | "
            f"{_fmt(cmp.get('base_expectancy'))} | {_fmt(cmp.get('gated_expectancy'))} | "
            f"{_fmt(cmp.get('delta_expectancy'))} | {_fmt(cmp.get('sample_reduction_pct'))} |"
        )
    lines.append("")

    best = stats.get("best_gated", {})
    lines.append(f"- Best Gated Rule: {best.get('filter', '—')}")
    lines.append(f"- Best improvement: {_fmt(best.get('improvement'))}%")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_REGIME_GATED.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave regime gated sweep complete")


if __name__ == "__main__":
    main()
