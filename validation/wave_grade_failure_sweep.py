"""Wave Grade Failure 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_failure import full_grade_failure_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "timestamp", "symbol", "timeframe", "success",
    "failure_cause", "failure_horizon",
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "macd", "ema20_slope_3", "atr_pct", "volatility_20",
    "path", "branch",
)


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_grade_failure.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    causes = stats.get("causes", [])
    ax = axes[0, 0]
    if causes:
        labels = [c["cause"] for c in causes if c["count"] > 0]
        vals = [c["count"] for c in causes if c["count"] > 0]
        if labels:
            ax.bar(labels, vals, color="#E65100", alpha=0.85)
            ax.set_title("Failure Cause Distribution")
            ax.tick_params(axis="x", rotation=45, labelsize=7)
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    timing = stats.get("timing", [])
    if timing:
        ax2.bar(
            [str(t["horizon"]) for t in timing],
            [t["failure_pct"] for t in timing],
            color="#1565C0", alpha=0.85,
        )
        ax2.set_title("Failure Timing (cumulative %)")
        ax2.set_xlabel("horizon (bars)")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1, 0]
    funnel = stats.get("funnel", [])
    if funnel:
        stages = [f["stage"] for f in funnel]
        surv = [f["survivors"] for f in funnel]
        ax3.bar(range(len(stages)), surv, color="#2E7D32", alpha=0.85)
        ax3.set_xticks(range(len(stages)))
        ax3.set_xticklabels(stages, rotation=30, ha="right", fontsize=7)
        ax3.set_title("False Positive Funnel")
        ax3.set_ylabel("survivors")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    seps = stats.get("separators", [])[:8]
    if seps:
        feats = [s["feature"][:12] for s in seps]
        sm = [s.get("success_mean") or 0 for s in seps]
        fm = [s.get("failure_mean") or 0 for s in seps]
        x = np.arange(len(feats))
        w = 0.35
        ax4.bar(x - w / 2, sm, w, label="SUCCESS", color="#2E7D32", alpha=0.85)
        ax4.bar(x + w / 2, fm, w, label="FAILURE", color="#E65100", alpha=0.85)
        ax4.set_xticks(x)
        ax4.set_xticklabels(feats, rotation=45, ha="right", fontsize=7)
        ax4.set_title("Success vs Failure")
        ax4.legend(fontsize=7)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Grade Failure — Early Warning Collapse Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building grade failure analysis...")
    stats = full_grade_failure_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_grade_failure.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_GRADE_FAILURE",
        "",
        "Grade A Failure Analysis — Early Warning Collapse",
        "",
        f"- SUCCESS: {stats.get('success_count', 0)}",
        f"- FAILURE: {stats.get('failure_count', 0)}",
        "",
        "## Failure Causes",
        "",
        "| cause | count | pct |",
        "|---|---:|---:|",
    ]
    for r in stats.get("causes", []):
        lines.append(f"| {r.get('cause', '')} | {r.get('count', 0)} | {_fmt(r.get('pct'))} |")
    lines.append("")

    lines.append("## Failure Timing")
    lines.append("")
    lines.append("| horizon | count | failure pct |")
    lines.append("|---:|---:|---:|")
    for r in stats.get("timing", []):
        lines.append(
            f"| {r.get('horizon', '')} | {r.get('count', 0)} | {_fmt(r.get('failure_pct'))} |"
        )
    lines.append("")

    lines.append("## First Failure")
    lines.append("")
    lines.append("| rank | first failure | count | pct |")
    lines.append("|---:|---|---:|---:|")
    for r in stats.get("first_failure", []):
        lines.append(
            f"| {r.get('rank', '')} | {r.get('first_failure', '')} | "
            f"{r.get('count', 0)} | {_fmt(r.get('pct'))} |"
        )
    lines.append("")

    lines.append("## Success vs Failure")
    lines.append("")
    lines.append("| feature | success | failure | delta | effect |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("separators", [])[:15]:
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('delta'))} | "
            f"{_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## Top Separators")
    lines.append("")
    lines.append("| rank | feature | effect_size | success | failure |")
    lines.append("|---:|---|---:|---:|---:|")
    for i, r in enumerate(stats.get("separators", [])[:20], 1):
        lines.append(
            f"| {i} | {r.get('feature', '')} | {_fmt(r.get('effect_size'))} | "
            f"{_fmt(r.get('success_mean'))} | {_fmt(r.get('failure_mean'))} |"
        )
    lines.append("")

    lines.append("## Failure Path")
    lines.append("")
    lines.append("| path | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("paths", []):
        if r.get("count", 0) > 0:
            lines.append(
                f"| {r.get('path', '')} | {r.get('count', 0)} | {_fmt(r.get('pct'))} |"
            )
    lines.append("")

    lines.append("## Failure Branch")
    lines.append("")
    lines.append("| branch | success | failure |")
    lines.append("|---|---:|---:|")
    for r in stats.get("branches", []):
        lines.append(
            f"| {r.get('branch', '')} | {r.get('success', 0)} | {r.get('failure', 0)} |"
        )
    lines.append("")

    lines.append("## Failure Regime")
    lines.append("")
    lines.append("| feature | success | failure | effect |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("regime", []):
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('success_mean'))} | "
            f"{_fmt(r.get('failure_mean'))} | {_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## Escalation Timeline")
    lines.append("")
    lines.append("| offset | success major_k | failure major_k | success rsi | failure rsi |")
    lines.append("|---:|---:|---:|---:|---:|")
    for r in stats.get("escalation", []):
        lines.append(
            f"| {r.get('offset', '')} | {_fmt(r.get('success_major_k'))} | "
            f"{_fmt(r.get('failure_major_k'))} | {_fmt(r.get('success_rsi'))} | "
            f"{_fmt(r.get('failure_rsi'))} |"
        )
    lines.append("")

    lines.append("## False Positive Funnel")
    lines.append("")
    lines.append("| stage | survivors |")
    lines.append("|---|---:|")
    for r in stats.get("funnel", []):
        lines.append(f"| {r.get('stage', '')} | {r.get('survivors', 0)} |")
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    lines.append("| symbol | success | failure | top cause | pct |")
    lines.append("|---|---:|---:|---|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('success', 0)} | {cmp.get('failure', 0)} | "
            f"{cmp.get('top_cause', '—')} | {_fmt(cmp.get('top_cause_pct'))} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_GRADE_FAILURE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave grade failure sweep complete")


if __name__ == "__main__":
    main()
