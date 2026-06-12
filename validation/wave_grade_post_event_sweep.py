"""Wave Grade Post-Event 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_post_event import (
    CSV_EXPORT_COLS,
    ENTRY_DELAYS,
    FORWARD_HORIZONS,
    full_post_event_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_grade_post_event.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    decay = stats.get("decay", [])
    ax = axes[0, 0]
    if decay:
        labels = [f"d{r['delay']}" for r in decay]
        vals = [(r.get("expectancy") or 0) for r in decay]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title("Delay vs Expectancy")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    outcomes = stats.get("delay_outcomes", [])
    ax2 = axes[0, 1]
    if outcomes:
        labels = [f"d{r['delay']}" for r in outcomes]
        vals = [(r.get("win_rate") or 0) for r in outcomes]
        ax2.bar(labels, vals, color="#2E7D32", alpha=0.85)
        ax2.set_title("Delay vs Win Rate (%)")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    epd = stats.get("exit_policy_by_delay", [])
    ax3 = axes[1, 0]
    if epd:
        policies = sorted({r["policy"] for r in epd})
        x = np.arange(len(ENTRY_DELAYS))
        width = 0.15
        for i, pol in enumerate(policies):
            vals = []
            for delay in ENTRY_DELAYS:
                row = next((r for r in epd if r["delay"] == delay and r["policy"] == pol), None)
                vals.append(row.get("expectancy") or 0 if row else 0)
            ax3.bar(x + i * width, vals, width, label=pol[:12], alpha=0.85)
        ax3.set_xticks(x + width * (len(policies) - 1) / 2)
        ax3.set_xticklabels([f"d{d}" for d in ENTRY_DELAYS])
        ax3.set_title("Policy by Delay")
        ax3.legend(fontsize=6)
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    valid = stats.get("valid_until_delay", -1)
    if decay:
        labels = [f"d{r['delay']}" for r in decay]
        valid_flags = [1 if r["delay"] <= valid else 0 for r in decay]
        colors = ["#2E7D32" if f else "#E65100" for f in valid_flags]
        vals = [(r.get("expectancy") or 0) for r in decay]
        ax4.bar(labels, vals, color=colors, alpha=0.85)
        ax4.axhline(0, color="gray", linewidth=0.8)
        ax4.set_title(f"Validity Window (until delay {valid})")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Grade Post-Event — Delay Entry Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building grade post-event analysis...")
    stats = full_post_event_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_grade_post_event.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_GRADE_POST_EVENT",
        "",
        "Grade A Post-Event Outcome — Delayed Entry Analysis",
        "",
        f"- Grade A events: {stats.get('event_count', 0)}",
        f"- reference policy: {stats.get('reference_policy', '—')}",
        f"- valid_until_delay: {stats.get('valid_until_delay', '—')}",
        "",
        "## Delay Outcome",
        "",
        "| delay | win_rate | expectancy | n |",
        "|---|---:|---:|---:|",
    ]
    for r in stats.get("delay_outcomes", []):
        lines.append(
            f"| {r.get('delay', '')} | {_fmt(r.get('win_rate'), pct=True)} | "
            f"{_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append("## Forward Return")
    lines.append("")
    hdr = "| delay | " + " | ".join(f"+{n}" for n in FORWARD_HORIZONS) + " |"
    lines.append(hdr)
    lines.append("|" + "---|" * (len(FORWARD_HORIZONS) + 1))
    for r in stats.get("forward_returns", []):
        cells = [_fmt(r.get(f"return_{n}"), pct=True) for n in FORWARD_HORIZONS]
        lines.append(f"| {r.get('delay', '')} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Exit Policy by Delay")
    lines.append("")
    lines.append("| delay | policy | expectancy | win_rate | profit_factor | avg_bars_held |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("exit_policy_by_delay", []):
        lines.append(
            f"| {r.get('delay', '')} | {r.get('policy', '')} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('profit_factor'))} | "
            f"{_fmt(r.get('avg_bars_held'))} |"
        )
    lines.append("")

    lines.append("## Validity Window")
    lines.append("")
    lines.append(f"- valid_until_delay: **{stats.get('valid_until_delay', '—')}**")
    lines.append("")
    lines.append("| delay | expectancy | win_rate | valid |")
    lines.append("|---|---:|---:|---|")
    valid_until = stats.get("valid_until_delay", -1)
    for r in stats.get("decay", []):
        ok = r["delay"] <= valid_until
        lines.append(
            f"| {r.get('delay', '')} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {'yes' if ok else 'no'} |"
        )
    lines.append("")

    lines.append("## Failure After Grade A")
    lines.append("")
    lines.append("| category | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("failure_distribution", []):
        lines.append(
            f"| {r.get('category', '')} | {r.get('count', 0)} | "
            f"{_fmt(r.get('pct'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Symbol/TF Comparison")
    lines.append("")
    lines.append("| symbol | tf | delay | expectancy | win_rate | n |")
    lines.append("|---|---|---|---:|---:|---:|")
    for r in stats.get("symbol_tf_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('timeframe', '')} | {r.get('delay', '')} | "
            f"{_fmt(r.get('expectancy'))} | {_fmt(r.get('win_rate'), pct=True)} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_GRADE_POST_EVENT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave grade post-event sweep complete")


if __name__ == "__main__":
    main()
