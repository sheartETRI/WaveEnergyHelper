"""Wave Grade Early Warning 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_early_warning import (
    EARLY_OFFSETS,
    full_early_warning_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "timestamp", "symbol", "timeframe", "offset", "positive",
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "rsi_slope_1", "macd", "ema20_slope_3", "atr_pct", "volatility_20",
)


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v * 100:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_grade_early_warning.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    seps = stats.get("separators", [])[:10]
    ax = axes[0, 0]
    if seps:
        labels = [f"{r['feature'][:12]}\n({r['offset']})" for r in seps]
        vals = [r["effect_size"] for r in seps]
        y = np.arange(len(labels))
        ax.barh(y, vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_title("Separator Ranking")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    cands = stats.get("candidates", [])[:8]
    if cands:
        labels = [c["candidate"][:22] for c in cands]
        prec = [(c.get("precision") or 0) * 100 for c in cands]
        rec = [(c.get("recall") or 0) * 100 for c in cands]
        x = np.arange(len(labels))
        w = 0.35
        ax2.bar(x - w / 2, prec, w, label="precision", color="#2E7D32", alpha=0.85)
        ax2.bar(x + w / 2, rec, w, label="recall", color="#6A1B9A", alpha=0.85)
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=6)
        ax2.set_title("Precision / Recall")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1, 0]
    horizon = stats.get("horizon", {})
    by_off = horizon.get("by_offset", {})
    if by_off:
        offs = sorted(by_off.keys())
        vals = [by_off[o] for o in offs]
        ax3.bar([str(o) for o in offs], vals, color="#E65100", alpha=0.85)
        ax3.set_title("Horizon Comparison (avg effect)")
        ax3.set_xlabel("offset")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    if cands:
        labels = [c["candidate"][:18] for c in cands[:8]]
        rates = [(c.get("positive_rate") or 0) * 100 for c in cands[:8]]
        ax4.bar(range(len(labels)), rates, color="#1565C0", alpha=0.85)
        ax4.set_xticks(range(len(labels)))
        ax4.set_xticklabels(labels, rotation=45, ha="right", fontsize=6)
        ax4.set_title("Future Grade A Rate")
        ax4.set_ylabel("%")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Grade Early Warning — Grade A Pre-Formation Signals")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building grade early warning analysis...")
    stats = full_early_warning_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_grade_early_warning.csv"), index=False)
    png = _plot(stats)

    horizon = stats.get("horizon", {})
    lines = [
        "# REPORT_WAVE_GRADE_EARLY_WARNING",
        "",
        "Grade A Early Warning — Pre-Formation Observation",
        "",
        f"- Grade A events: {stats.get('a_count', 0)}",
        f"- Best Horizon: {horizon.get('offset', '—')} (avg effect {_fmt(horizon.get('avg_effect'))})",
        "",
        "## Top Early Separators",
        "",
        "| feature | effect | offset | pos_mean | neg_mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stats.get("separators", [])[:20]:
        lines.append(
            f"| {r.get('feature', '')} | {_fmt(r.get('effect_size'))} | "
            f"{r.get('offset', '')} | {_fmt(r.get('pos_mean'))} | {_fmt(r.get('neg_mean'))} |"
        )
    lines.append("")

    lines.append("## Best Horizon")
    lines.append("")
    lines.append("| offset | avg_effect |")
    lines.append("|---:|---:|")
    for off, val in sorted(horizon.get("by_offset", {}).items()):
        marker = " **" if off == horizon.get("offset") else ""
        lines.append(f"| {off}{marker} | {_fmt(val)} |")
    lines.append("")

    lines.append("## Top Candidates")
    lines.append("")
    lines.append("| candidate | precision | recall | coverage | future GradeA rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("candidates", [])[:15]:
        lines.append(
            f"| {r.get('candidate', '')[:60]} | {_fmt(r.get('precision'), pct=True)} | "
            f"{_fmt(r.get('recall'), pct=True)} | {_fmt(r.get('coverage'), pct=True)} | "
            f"{_fmt(r.get('positive_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Precision / Recall (Best Candidate)")
    lines.append("")
    best = stats.get("best_candidate", {})
    lines.append(f"- candidate: {best.get('candidate', '—')}")
    lines.append(f"- precision: {_fmt(best.get('precision'), pct=True)}")
    lines.append(f"- recall: {_fmt(best.get('recall'), pct=True)}")
    lines.append(f"- TP/FP/FN: {best.get('tp', 0)}/{best.get('fp', 0)}/{best.get('fn', 0)}")
    lines.append("")

    lines.append("## Future Grade A Rate")
    lines.append("")
    lines.append("| candidate | rate | fired |")
    lines.append("|---|---:|---:|")
    for r in stats.get("candidates", [])[:10]:
        lines.append(
            f"| {r.get('candidate', '')[:50]} | {_fmt(r.get('positive_rate'), pct=True)} | "
            f"{r.get('fired', 0)} |"
        )
    lines.append("")

    lines.append("## False Positive Analysis")
    lines.append("")
    lines.append("| cause | count | pct |")
    lines.append("|---|---:|---:|")
    for r in stats.get("fp_analysis", []):
        lines.append(
            f"| {r.get('cause', '')} | {r.get('count', 0)} | {_fmt(r.get('pct'))} |"
        )
    lines.append("")

    lines.append("## Formation Order (관측용)")
    lines.append("")
    lines.append("| order | feature | offset | effect |")
    lines.append("|---:|---|---:|---:|")
    for i, r in enumerate(stats.get("formation_order", []), 1):
        lines.append(
            f"| {i} | {r.get('feature', '')} | {r.get('offset', '')} | "
            f"{_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    lines.append("| symbol | pos snapshots | top feature | effect |")
    lines.append("|---|---:|---|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('positive_snapshots', 0)} | "
            f"{cmp.get('top_feature', '—')} | {_fmt(cmp.get('top_effect'))} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_GRADE_EARLY_WARNING.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave grade early warning sweep complete")


if __name__ == "__main__":
    main()
