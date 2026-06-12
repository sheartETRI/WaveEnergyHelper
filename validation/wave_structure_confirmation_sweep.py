"""Wave Structure Confirmation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_structure_confirmation import CSV_EXPORT_COLS, full_structure_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_structure_confirmation.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    sp = stats.get("score_performance", [])
    ax = axes[0, 0]
    if sp:
        labels = [str(r["score"]) for r in sp if r.get("n", 0) > 0]
        vals = [r.get("expectancy") or 0 for r in sp if r.get("n", 0) > 0]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title("Structure Score vs Expectancy")
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
        ax2.set_title("Success vs Failure Structure")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    combos = (
        stats.get("energy_structure_combos", [])
        + stats.get("mf_structure_combos", [])
    )
    ax3 = axes[1, 0]
    if combos:
        labels = [c["combo"][:22] for c in combos if c.get("n", 0) > 0]
        vals = [c.get("expectancy") or 0 for c in combos if c.get("n", 0) > 0]
        if labels:
            ax3.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
            ax3.set_yticks(range(len(labels)))
            ax3.set_yticklabels(labels, fontsize=6)
            ax3.set_title("Energy/MF + Structure")
            ax3.invert_yaxis()
        else:
            ax3.text(0.5, 0.5, "no combo data", ha="center")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    sym_cmp = stats.get("symbol_comparison", [])
    ax4 = axes[1, 1]
    if sym_cmp:
        labels = [r["symbol"] for r in sym_cmp]
        vals = [r.get("structure_score_avg") or 0 for r in sym_cmp]
        ax4.bar(labels, vals, color="#00838F", alpha=0.85)
        ax4.set_title("Symbol Structure Score Avg")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Structure Confirmation")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building structure confirmation analysis...")
    stats = full_structure_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_structure_confirmation.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_STRUCTURE_CONFIRMATION",
        "",
        "Structure Confirmation — HH/HL/Neckline Recovery Observation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        "",
        "## 1. 성공 vs 실패 Structure 차이",
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

    lines.append("## 2. Top Structure Separators")
    lines.append("")
    lines.append("| feature | success_mean | failure_mean | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_separators", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 3. Structure Score별 성과")
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

    lines.append("## 4. Energy + Structure")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("energy_structure_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5. Money Flow + Structure")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("mf_structure_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 6. TB + Structure")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("tb_structure_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 7. WAVE3_COMPLETED + Structure")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("wave3_structure_combos", []):
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
    lines.append("| symbol | structure_score_avg | win_rate | expectancy | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {_fmt(r.get('structure_score_avg'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    ems = stats.get("ems_combo", {})
    lines.append("## 10. 최종 Structure Pattern")
    lines.append("")
    lines.append("### Energy + MF + Structure")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| {ems.get('combo', '')} | {ems.get('n', 0)} | "
        f"{_fmt(ems.get('win_rate'), pct=True)} | {_fmt(ems.get('expectancy'))} | "
        f"{_fmt(ems.get('profit_factor'))} |"
    )
    lines.append("")

    lines.append("### Structure Timing")
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

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_STRUCTURE_CONFIRMATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave structure confirmation sweep complete")


if __name__ == "__main__":
    main()
