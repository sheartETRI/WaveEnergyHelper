"""Wave Energy Divergence 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_energy_divergence import CSV_EXPORT_COLS, full_divergence_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_energy_divergence.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    raw = stats.get("raw")
    if raw is not None and not raw.empty:
        df = raw
    else:
        df = None

    ax = axes[0, 0]
    if df is not None and "div_strength" in df.columns:
        sub = df[df["bullish_div"]]
        if not sub.empty:
            ax.hist(sub["div_strength"].dropna(), bins=12, color="#1565C0", alpha=0.85)
            ax.set_title("Divergence Strength (Bullish)")
        else:
            ax.text(0.5, 0.5, "no bullish div", ha="center")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    s_rate = stats.get("success_div_rate", 0)
    f_rate = stats.get("failure_div_rate", 0)
    ax2.bar(["success", "failure"], [s_rate, f_rate], color=["#2E7D32", "#E65100"], alpha=0.85)
    ax2.set_title("Bullish Div Rate (%)")
    ax2.set_ylabel("%")

    ax3 = axes[1, 0]
    combos = stats.get("wave_div_combos", [])
    if combos:
        labels = [c["combo"][:24] for c in combos if c.get("n", 0) > 0]
        vals = [c.get("expectancy") or 0 for c in combos if c.get("n", 0) > 0]
        if labels:
            ax3.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
            ax3.set_yticks(range(len(labels)))
            ax3.set_yticklabels(labels, fontsize=7)
            ax3.set_title("Wave + Divergence Expectancy")
            ax3.invert_yaxis()
        else:
            ax3.text(0.5, 0.5, "no combo data", ha="center")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    sym_cmp = stats.get("symbol_comparison", [])
    if sym_cmp:
        labels = [r["symbol"] for r in sym_cmp]
        vals = [r.get("div_rate") or 0 for r in sym_cmp]
        ax4.bar(labels, vals, color="#00838F", alpha=0.85)
        ax4.set_title("Symbol Bullish Div Rate (%)")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Energy Divergence Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building energy divergence analysis...")
    stats = full_divergence_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_energy_divergence.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_ENERGY_DIVERGENCE",
        "",
        "Energy Divergence — OBV Accumulation Observation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        f"- bullish_div_rate: {_fmt(stats.get('bullish_div_rate'), pct=True)}",
        f"- success_div_rate: {_fmt(stats.get('success_div_rate'), pct=True)}",
        f"- failure_div_rate: {_fmt(stats.get('failure_div_rate'), pct=True)}",
        "",
        "## 1. Bullish Divergence 발생률",
        "",
        f"- 전체: **{_fmt(stats.get('bullish_div_rate'), pct=True)}**",
        f"- 성공 집단: **{_fmt(stats.get('success_div_rate'), pct=True)}**",
        f"- 실패 집단: **{_fmt(stats.get('failure_div_rate'), pct=True)}**",
        "",
        "## 2. 성공 vs 실패 비교",
        "",
        "| metric | success | failure | effect_size |",
        "|---|---:|---:|---:|",
    ]
    for r in stats.get("feature_compare", []):
        lines.append(
            f"| {r.get('metric', '')} | {_fmt(r.get('success'))} | "
            f"{_fmt(r.get('failure'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 3. Top Divergence Separators")
    lines.append("")
    lines.append("| metric | success | failure | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_separators", []):
        lines.append(
            f"| {r.get('metric', '')} | {_fmt(r.get('success'))} | "
            f"{_fmt(r.get('failure'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 4. Wave + Divergence")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("wave_div_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5. Energy Score + Divergence")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("energy_div_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 6. Failure Reclassification")
    lines.append("")
    lines.append("| cause | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("failure_reclass", []):
        lines.append(
            f"| {r.get('cause', '')} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 7. ETH/BTC/SOL/BNB 비교")
    lines.append("")
    lines.append("| symbol | div_rate | expectancy | win_rate | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {_fmt(r.get('div_rate'), pct=True)} | "
            f"{_fmt(r.get('expectancy'))} | {_fmt(r.get('win_rate'), pct=True)} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append("## Volume Event Timing")
    lines.append("")
    lines.append("| offset | div_rate | n |")
    lines.append("|---|---:|---:|")
    for r in stats.get("timing", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('div_rate'), pct=True)} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_ENERGY_DIVERGENCE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave energy divergence sweep complete")


if __name__ == "__main__":
    main()
