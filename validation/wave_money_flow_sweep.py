"""Wave Money Flow 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_money_flow import CSV_EXPORT_COLS, full_money_flow_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_money_flow.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    sp = stats.get("score_performance", [])
    ax = axes[0, 0]
    if sp:
        labels = [str(r["score"]) for r in sp if r.get("n", 0) > 0]
        vals = [r.get("expectancy") or 0 for r in sp if r.get("n", 0) > 0]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title("Money Flow Score vs Expectancy")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    cmp_rows = stats.get("feature_compare", [])[:6]
    ax2 = axes[0, 1]
    if cmp_rows:
        labels = [r["feature"] for r in cmp_rows]
        s_vals = [r.get("success_mean") or 0 for r in cmp_rows]
        f_vals = [r.get("failure_mean") or 0 for r in cmp_rows]
        x = np.arange(len(labels))
        w = 0.35
        ax2.bar(x - w / 2, s_vals, w, label="success", color="#2E7D32", alpha=0.85)
        ax2.bar(x + w / 2, f_vals, w, label="failure", color="#E65100", alpha=0.85)
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
        ax2.set_title("Success vs Failure Money Flow")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    combos = (
        stats.get("energy_money_combos", [])
        + stats.get("divergence_money_combos", [])
    )
    ax3 = axes[1, 0]
    if combos:
        labels = [c["combo"][:22] for c in combos if c.get("n", 0) > 0]
        vals = [c.get("expectancy") or 0 for c in combos if c.get("n", 0) > 0]
        if labels:
            ax3.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
            ax3.set_yticks(range(len(labels)))
            ax3.set_yticklabels(labels, fontsize=6)
            ax3.set_title("Energy/Divergence + Money Flow")
            ax3.invert_yaxis()
        else:
            ax3.text(0.5, 0.5, "no combo data", ha="center")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    timing = stats.get("timing", [])
    ax4 = axes[1, 1]
    if timing:
        offsets = [r["offset"] for r in timing]
        vals = [r.get("score") or 0 for r in timing]
        ax4.plot(offsets, vals, "o-", color="#00838F")
        ax4.set_title("Money Flow Score by Offset")
        ax4.set_xlabel("offset (bars)")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Money Flow Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building money flow analysis...")
    stats = full_money_flow_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_money_flow.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_MONEY_FLOW",
        "",
        "Money Flow Layer — MFI/CMF/AD Observation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        "",
        "## 1. 성공 vs 실패",
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

    lines.append("## 2. Top Money Flow Separators")
    lines.append("")
    lines.append("| feature | success_mean | failure_mean | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_separators", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 3. Score별 성과")
    lines.append("")
    lines.append("| score | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("score_performance", []):
        lines.append(
            f"| {r.get('score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 4. Energy + Money Flow")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("energy_money_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5. Divergence + Money Flow")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("divergence_money_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 6. TB + Money Flow")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("tb_money_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 7. WAVE3_COMPLETED + Money Flow")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("wave3_money_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 8. Failure Reclassification")
    lines.append("")
    lines.append("| cause | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("failure_reclass", []):
        lines.append(
            f"| {r.get('cause', '')} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 9. ETH/BTC/SOL/BNB")
    lines.append("")
    lines.append("| symbol | money_flow_score_avg | win_rate | expectancy | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {_fmt(r.get('money_flow_score_avg'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    tc = stats.get("triple_combo", {})
    lines.append("## 10. 최종 Money Flow Pattern")
    lines.append("")
    lines.append("### Triple Combo (Energy>=3 + MoneyFlow>=3 + BullishDiv)")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| {tc.get('combo', '')} | {tc.get('n', 0)} | "
        f"{_fmt(tc.get('win_rate'), pct=True)} | {_fmt(tc.get('expectancy'))} | "
        f"{_fmt(tc.get('profit_factor'))} |"
    )
    lines.append("")

    lines.append("### Money Flow Timing")
    lines.append("")
    lines.append("| offset | score | n |")
    lines.append("|---|---:|---:|")
    for r in stats.get("timing", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('score'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_MONEY_FLOW.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave money flow sweep complete")


if __name__ == "__main__":
    main()
