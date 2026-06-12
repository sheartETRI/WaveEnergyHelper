"""Wave Watchlist Tracker 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_watchlist_tracker import (
    STATE_CONFIRMING,
    STATE_EARLY_WARNING,
    STATE_FAILED,
    STATE_GRADE_A_READY,
    STATE_STRONG_CONFIRMING,
    full_watchlist_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "timestamp", "symbol", "timeframe", "state", "duration", "next_state", "success",
)


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_watchlist_tracker.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    funnel = stats.get("funnel", [])
    ax = axes[0, 0]
    if funnel:
        labels = [f["state"].replace("STATE_", "") for f in funnel]
        vals = [f["count"] for f in funnel]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.set_title("State Funnel")
        ax.tick_params(axis="x", rotation=30, labelsize=7)
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    matrix = stats.get("matrix", [])[:8]
    if matrix:
        labels = [f"{r['from'].replace('STATE_', '')[:6]}→{r['to'].replace('STATE_', '')[:6]}" for r in matrix]
        vals = [r["count"] for r in matrix]
        ax2.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.set_title("Transition Matrix (top)")
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1, 0]
    conv = stats.get("conversions", [])
    if conv:
        labels = [c["state"].replace("STATE_", "") for c in conv]
        vals = [(c.get("conversion") or 0) for c in conv]
        ax3.bar(labels, vals, color="#2E7D32", alpha=0.85)
        ax3.set_title("Conversion Rate (%)")
        ax3.tick_params(axis="x", rotation=20, labelsize=7)
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    leak = stats.get("leakage", [])
    if leak:
        labels = [l["state"].replace("STATE_", "") for l in leak]
        vals = [l.get("fail_rate") or 0 for l in leak]
        ax4.bar(labels, vals, color="#E65100", alpha=0.85)
        ax4.set_title("Failure Leakage (%)")
        ax4.tick_params(axis="x", rotation=20, labelsize=7)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Watchlist Tracker — Grade A State Machine")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building watchlist tracker analysis...")
    stats = full_watchlist_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_watchlist_tracker.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_WATCHLIST_TRACKER",
        "",
        "Watchlist State Machine — Grade A Formation Tracking",
        "",
        f"- events: {stats.get('event_count', 0)}",
        f"- GRADE_A_READY: {stats.get('success_count', 0)}",
        f"- riskiest state: {stats.get('riskiest_state', '—')}",
        "",
        "## Transition Matrix",
        "",
        "| from | to | count | pct |",
        "|---|---|---:|---:|",
    ]
    for r in stats.get("matrix", []):
        lines.append(
            f"| {r.get('from', '')} | {r.get('to', '')} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'))} |"
        )
    lines.append("")

    lines.append("## State Duration")
    lines.append("")
    lines.append("| state | avg | median | max |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("durations", []):
        lines.append(
            f"| {r.get('state', '')} | {_fmt(r.get('avg'))} | "
            f"{_fmt(r.get('median'))} | {r.get('max', '—')} |"
        )
    lines.append("")

    lines.append("## Conversion Rate")
    lines.append("")
    lines.append("| state | entered | conversion |")
    lines.append("|---|---:|---:|")
    for r in stats.get("conversions", []):
        lines.append(
            f"| {r.get('state', '')} | {r.get('entered', 0)} | "
            f"{_fmt(r.get('conversion'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Failure Leakage")
    lines.append("")
    lines.append("| state | fail_count | total_exits | fail_rate |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("leakage", []):
        lines.append(
            f"| {r.get('state', '')} | {r.get('fail_count', 0)} | "
            f"{r.get('total_exits', 0)} | {_fmt(r.get('fail_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Watchlist Funnel")
    lines.append("")
    lines.append("| state | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("funnel", []):
        lines.append(
            f"| {r.get('state', '')} | {r.get('count', 0)} | {_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Success Paths")
    lines.append("")
    lines.append("| path | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("success_paths", []):
        lines.append(
            f"| {str(r.get('path', ''))[:70]} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Failure Paths")
    lines.append("")
    lines.append("| path | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("failure_paths", []):
        lines.append(
            f"| {str(r.get('path', ''))[:70]} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    lines.append("| symbol | n | conversion | fail_rate |")
    lines.append("|---|---:|---:|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('n', 0)} | {_fmt(cmp.get('conversion'), pct=True)} | "
            f"{_fmt(cmp.get('fail_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_WATCHLIST_TRACKER.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave watchlist tracker sweep complete")


if __name__ == "__main__":
    main()
