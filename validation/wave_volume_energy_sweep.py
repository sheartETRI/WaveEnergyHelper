"""Wave Volume Energy 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_volume_energy import CSV_EXPORT_COLS, full_volume_energy_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_volume_energy.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    esp = stats.get("energy_score_perf", [])
    ax = axes[0, 0]
    if esp:
        labels = [str(r["score"]) for r in esp if r.get("n", 0) > 0]
        vals = [r.get("expectancy") or 0 for r in esp if r.get("n", 0) > 0]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title("Energy Score vs Expectancy")
        ax.set_xlabel("score")
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
        ax2.set_title("Success vs Failure Volume Profile")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ts, tf = stats.get("timing_success", []), stats.get("timing_failure", [])
    ax3 = axes[1, 0]
    if ts and tf:
        offsets = [r["offset"] for r in ts]
        s_vr = [r.get("vol_ratio_20") or 0 for r in ts]
        f_vr = [r.get("vol_ratio_20") or 0 for r in tf]
        ax3.plot(offsets, s_vr, "o-", label="success", color="#2E7D32")
        ax3.plot(offsets, f_vr, "o-", label="failure", color="#E65100")
        ax3.axhline(1.0, color="gray", linewidth=0.8, linestyle="--")
        ax3.set_title("Volume Event Timing (vol_ratio_20)")
        ax3.set_xlabel("offset (bars)")
        ax3.legend(fontsize=7)
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    combos = stats.get("wave_energy_combos", [])
    ax4 = axes[1, 1]
    if combos:
        labels = [c["combo"][:22] for c in combos if c.get("n", 0) > 0]
        vals = [c.get("expectancy") or 0 for c in combos if c.get("n", 0) > 0]
        if labels:
            ax4.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
            ax4.set_yticks(range(len(labels)))
            ax4.set_yticklabels(labels, fontsize=6)
            ax4.set_title("Wave + Energy Combo Expectancy")
            ax4.invert_yaxis()
        else:
            ax4.text(0.5, 0.5, "no combo data", ha="center")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Volume Energy Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building volume energy analysis...")
    stats = full_volume_energy_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_volume_energy.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_VOLUME_ENERGY",
        "",
        "Volume Energy Layer — Success vs Failure Observation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        f"- success: {stats.get('success_count', 0)}",
        f"- failure: {stats.get('failure_count', 0)}",
        "",
        "## 1. Volume Feature 성공/실패 비교",
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

    lines.append("## 2. Top Volume Separators")
    lines.append("")
    lines.append("| feature | success_mean | failure_mean | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("top_separators", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## 3. Energy Score별 성과")
    lines.append("")
    lines.append("| score | n | win_rate | expectancy | profit_factor | avg_return |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in stats.get("energy_score_perf", []):
        lines.append(
            f"| {r.get('score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} | {_fmt(r.get('avg_return'))} |"
        )
    lines.append("")

    lines.append("## 4. Wave + Energy 조합 성과")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("wave_energy_combos", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5. Volume Event Timing")
    lines.append("")
    lines.append("### Success")
    lines.append("")
    lines.append("| offset | vol_ratio_20 | obv_slope_5 | n |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("timing_success", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('vol_ratio_20'))} | "
            f"{_fmt(r.get('obv_slope_5'))} | {r.get('n', 0)} |"
        )
    lines.append("")
    lines.append("### Failure")
    lines.append("")
    lines.append("| offset | vol_ratio_20 | obv_slope_5 | n |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("timing_failure", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('vol_ratio_20'))} | "
            f"{_fmt(r.get('obv_slope_5'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append("## 6. Failure Reclassification")
    lines.append("")
    lines.append("| failure_cause | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("failure_reclass", []):
        lines.append(
            f"| {r.get('failure_cause', '')} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 7. Symbol/TF 비교")
    lines.append("")
    lines.append("| symbol | tf | energy_score_avg | expectancy | win_rate | n |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_tf_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('timeframe', '')} | "
            f"{_fmt(r.get('energy_score_avg'))} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_VOLUME_ENERGY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave volume energy sweep complete")


if __name__ == "__main__":
    main()
