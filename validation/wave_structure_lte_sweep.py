"""Wave Structure LTE 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_structure_lte import CSV_EXPORT_COLS, MA_PERIODS, full_lte_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_structure_lte.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    tb = stats.get("tb_lte_combos", [])
    ax = axes[0, 0]
    if tb:
        labels = [c["combo"][:20] for c in tb if c.get("n", 0) > 0]
        vals = [c.get("expectancy") or 0 for c in tb if c.get("n", 0) > 0]
        if labels:
            ax.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=6)
            ax.set_title("TB + LTE Combos")
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, "no data", ha="center")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    cmp_rows = stats.get("feature_compare", [])[:6]
    ax2 = axes[0, 1]
    if cmp_rows:
        labels = [r["feature"][:14] for r in cmp_rows]
        vals = [r.get("effect_size") or 0 for r in cmp_rows]
        ax2.bar(labels, vals, color="#2E7D32", alpha=0.85)
        ax2.set_title("Top LTE Separators")
        ax2.tick_params(axis="x", rotation=30, labelsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    pos = stats.get("ma_position_perf", [])
    ax3 = axes[1, 0]
    below = [p for p in pos if "below" in p.get("combo", "") and p.get("n", 0) > 0]
    if below:
        labels = [p["combo"][:16] for p in below]
        vals = [p.get("expectancy") or 0 for p in below]
        ax3.bar(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
        ax3.set_xticks(range(len(labels)))
        ax3.set_xticklabels(labels, rotation=30, ha="right", fontsize=6)
        ax3.set_title("MA Position (below)")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    sym = stats.get("symbol_comparison", [])
    ax4 = axes[1, 1]
    if sym:
        labels = [s["symbol"] for s in sym]
        vals = [s.get("lte_position_score_avg") or 0 for s in sym]
        ax4.bar(labels, vals, color="#00838F", alpha=0.85)
        ax4.set_title("LTE Position Score by Symbol")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Structure LTE Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building structure LTE analysis...")
    stats = full_lte_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_structure_lte.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_STRUCTURE_LTE",
        "",
        "Structure LTE — Long-Term MA Context Observation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        "",
        "## 1. 성공 vs 실패 LTE 구조 차이",
        "",
        "| feature | success_mean | failure_mean | effect_size |",
        "|---|---:|---:|---:|",
    ]
    for r in stats.get("feature_compare", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 2. Top LTE Separators")
    lines.append("")
    lines.append("| feature | success_mean | failure_mean | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_separators", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 3. MA 위치별 성과")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("ma_position_perf", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 4. MA slope별 성과")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("ma_slope_perf", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5–7. TB + MA 조합")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("tb_lte_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 8. WAVE3 + LTE")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("wave3_lte_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 9. ETH/BTC/SOL/BNB")
    lines.append("")
    lines.append("| symbol | lte_score_avg | win_rate | expectancy | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {_fmt(r.get('lte_position_score_avg'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append("## 10. 1h/4h/1d 비교")
    lines.append("")
    lines.append("| tf | lte_score_avg | win_rate | expectancy | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("timeframe_comparison", []):
        lines.append(
            f"| {r.get('timeframe', '')} | {_fmt(r.get('lte_position_score_avg'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    fc = stats.get("final_combo", {})
    lines.append("## 최종 Structure + LTE Pattern")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| {fc.get('combo', '')} | {fc.get('n', 0)} | "
        f"{_fmt(fc.get('win_rate'), pct=True)} | {_fmt(fc.get('expectancy'))} | "
        f"{_fmt(fc.get('profit_factor'))} |"
    )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_STRUCTURE_LTE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave structure LTE sweep complete")


if __name__ == "__main__":
    main()
