"""Wave Grade Origin 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_origin import (
    GRADE_A,
    GRADE_BC,
    full_grade_origin_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "timestamp", "grade", "symbol", "timeframe",
    "major_k", "major_d", "major_k_slope_1",
    "rsi", "rsi_slope_1",
    "macd", "macd_hist",
    "atr_pct", "volatility_20",
    "dist_ema60_pct", "path", "branch",
)


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_grade_origin.png")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    timeline = stats.get("timeline", [])
    ax = axes[0]
    if timeline:
        offsets = [r["offset"] for r in timeline]
        mk = [r.get("major_k") or 0 for r in timeline]
        rsi = [r.get("rsi") or 0 for r in timeline]
        ax.plot(offsets, mk, "o-", color="#1565C0", label="major_k")
        ax2 = ax.twinx()
        ax2.plot(offsets, rsi, "s-", color="#E65100", label="rsi")
        ax.set_xlabel("offset (bars)")
        ax.set_title("Origin Timeline (Grade A)")
        ax.legend(loc="upper left")
        ax2.legend(loc="upper right")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1]
    leads = stats.get("lead_indicators", [])[:10]
    if leads:
        labels = [f"{r['feature'][:12]}\n({r['lead_bars']}b)" for r in leads]
        vals = [r["effect_size"] for r in leads]
        y = np.arange(len(labels))
        ax3.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax3.set_yticks(y)
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.set_title("Lead Indicator Ranking")
        ax3.invert_yaxis()
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[2]
    seps = stats.get("separators", [])[:8]
    if seps:
        feats = [r["feature"][:14] for r in seps]
        a_vals = [r.get("a_mean") or 0 for r in seps]
        bc_vals = [r.get("bc_mean") or 0 for r in seps]
        x = np.arange(len(feats))
        w = 0.35
        ax4.bar(x - w / 2, a_vals, w, label="GRADE_A", color="#2E7D32", alpha=0.85)
        ax4.bar(x + w / 2, bc_vals, w, label="GRADE_BC", color="#1565C0", alpha=0.85)
        ax4.set_xticks(x)
        ax4.set_xticklabels(feats, rotation=45, ha="right", fontsize=7)
        ax4.set_title("Grade A vs BC Comparison")
        ax4.legend(fontsize=7)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Grade Origin — Grade A Creation Mechanism")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building grade origin analysis...")
    stats = full_grade_origin_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_grade_origin.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_GRADE_ORIGIN",
        "",
        "Grade A Origin Analysis — BASE_RULE + major_k≥70",
        "",
        f"- GRADE_A events: {stats.get('a_count', 0)}",
        f"- GRADE_BC events: {stats.get('bc_count', 0)}",
        f"- GRADE_D (RULE_A ref): {stats.get('grade_d_count', 0)}",
        "",
        "## Grade A vs BC",
        "",
        "| feature | A mean | BC mean | delta | effect |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stats.get("comparison", [])[:15]:
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('a_mean'))} | "
            f"{_fmt(r.get('bc_mean'))} | {_fmt(r.get('delta'))} | "
            f"{_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## Top Separators")
    lines.append("")
    lines.append("| rank | feature | effect_size | A | BC |")
    lines.append("|---:|---|---:|---:|---:|")
    for i, r in enumerate(stats.get("separators", [])[:20], 1):
        lines.append(
            f"| {i} | {r.get('feature', '')} | {_fmt(r.get('effect_size'))} | "
            f"{_fmt(r.get('a_mean'))} | {_fmt(r.get('bc_mean'))} |"
        )
    lines.append("")

    lines.append("## Lead Indicators")
    lines.append("")
    lines.append("| feature | effect_size | lead_bars | A | BC |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("lead_indicators", [])[:20]:
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('effect_size'))} | "
            f"{r.get('lead_bars', '')} | {_fmt(r.get('a_mean'))} | {_fmt(r.get('bc_mean'))} |"
        )
    lines.append("")

    lines.append("## Origin Timeline")
    lines.append("")
    lines.append("| offset | major_k | rsi | macd | ema20_slope | atr |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for r in stats.get("timeline", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('major_k'))} | "
            f"{_fmt(r.get('rsi'))} | {_fmt(r.get('macd'))} | "
            f"{_fmt(r.get('ema20_slope_3'))} | {_fmt(r.get('atr_pct'))} |"
        )
    lines.append("")

    lines.append("## Path Distribution (GRADE_A)")
    lines.append("")
    lines.append("| path | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("paths", [])[:15]:
        lines.append(
            f"| {str(r.get('path', ''))[:70]} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'))} |"
        )
    lines.append("")

    lines.append("## Branch Distribution")
    lines.append("")
    lines.append("| branch | A | BC |")
    lines.append("|---|---:|---:|")
    for r in stats.get("branches", []):
        lines.append(
            f"| {r.get('branch', '')} | {r.get('a', 0)} | {r.get('bc', 0)} |"
        )
    lines.append("")

    lines.append("## Pseudo-Causality Order (관측용)")
    lines.append("")
    lines.append("| order | feature | bars_before |")
    lines.append("|---:|---|---:|")
    for i, r in enumerate(stats.get("causality_order", []), 1):
        lines.append(
            f"| {i} | {r.get('feature', '')} | {r.get('bars_before', '')} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    lines.append("| symbol | A n | BC n | top separator | effect | A major_k | BC major_k |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('a_n', 0)} | {cmp.get('bc_n', 0)} | "
            f"{cmp.get('top_separator', '—')} | {_fmt(cmp.get('top_effect'))} | "
            f"{_fmt(cmp.get('a_avg_major_k'))} | {_fmt(cmp.get('bc_avg_major_k'))} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_GRADE_ORIGIN.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave grade origin sweep complete")


if __name__ == "__main__":
    main()
