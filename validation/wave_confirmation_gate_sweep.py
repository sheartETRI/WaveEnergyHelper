"""Wave Confirmation Gate 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_confirmation_gate import full_confirmation_gate_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "timestamp", "symbol", "timeframe", "success", "gate_name", "gate_pass",
    "horizon", "major_k", "major_k_slope_1", "major_k_minus_d",
    "rsi", "macd_hist", "ema20_slope_3",
)


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v * 100:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_confirmation_gate.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    gates = stats.get("gates", [])[:10]
    ax = axes[0, 0]
    if gates:
        labels = [g["gate"][:18] for g in gates]
        prec = [(g.get("precision") or 0) * 100 for g in gates]
        ax.barh(range(len(labels)), prec, color="#1565C0", alpha=0.85)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_title("Gate Precision")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    if gates:
        rec = [(g.get("recall") or 0) * 100 for g in gates]
        ax2.barh(range(len(labels)), rec, color="#6A1B9A", alpha=0.85)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.set_title("Gate Recall")
        ax2.invert_yaxis()
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
        ax3.set_title("Gate Funnel")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    best_h = stats.get("best_horizon", {})
    horizons = [1, 2, 3]
    prec_by_h = []
    for h in horizons:
        if best_h.get("horizon") == h:
            prec_by_h.append((best_h.get("precision") or 0) * 100)
        else:
            hg = [g for g in stats.get("gates", []) if g["gate"].endswith(f"_+{h}")]
            prec_by_h.append((hg[0].get("precision") or 0) * 100 if hg else 0)
    ax4.bar([str(h) for h in horizons], prec_by_h, color="#E65100", alpha=0.85)
    ax4.set_title("Horizon Comparison (top gate precision)")
    ax4.set_xlabel("horizon")
    fig.suptitle("Wave Confirmation Gate — Post-Warning Survival")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building confirmation gate analysis...")
    stats = full_confirmation_gate_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_confirmation_gate.csv"), index=False)
    png = _plot(stats)

    lines = [
        "# REPORT_WAVE_CONFIRMATION_GATE",
        "",
        "Confirmation Gate Analysis — Post Early Warning Survival",
        "",
        f"- SUCCESS: {stats.get('success_count', 0)}",
        f"- FAILURE: {stats.get('failure_count', 0)}",
        "",
        "## Top Gates",
        "",
        "| gate | precision | recall | coverage | future GradeA rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stats.get("gates", [])[:20]:
        lines.append(
            f"| {r.get('gate', '')[:55]} | {_fmt(r.get('precision'), pct=True)} | "
            f"{_fmt(r.get('recall'), pct=True)} | {_fmt(r.get('coverage'), pct=True)} | "
            f"{_fmt(r.get('positive_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Composite Gates")
    lines.append("")
    lines.append("| gate | precision | recall | coverage | future GradeA rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("composites", [])[:20]:
        lines.append(
            f"| {r.get('gate', '')[:55]} | {_fmt(r.get('precision'), pct=True)} | "
            f"{_fmt(r.get('recall'), pct=True)} | {_fmt(r.get('coverage'), pct=True)} | "
            f"{_fmt(r.get('positive_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append("## Gate Funnel")
    lines.append("")
    lines.append("| stage | survivors |")
    lines.append("|---|---:|")
    for r in stats.get("funnel", []):
        lines.append(f"| {r.get('stage', '')} | {r.get('survivors', 0)} |")
    lines.append("")

    bh = stats.get("best_horizon", {})
    lines.append("## Best Horizon")
    lines.append("")
    lines.append(f"- horizon: **+{bh.get('horizon', '—')}**")
    lines.append(f"- gate: {bh.get('gate', '—')}")
    lines.append(f"- precision: {_fmt(bh.get('precision'), pct=True)}")
    lines.append(f"- recall: {_fmt(bh.get('recall'), pct=True)}")
    lines.append("")

    lines.append("## Success vs Failure")
    lines.append("")
    lines.append("| feature | horizon | success | failure | effect |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("separators", [])[:20]:
        lines.append(
            f"| {r.get('feature', '')} | {r.get('horizon', '')} | "
            f"{_fmt(r.get('success_mean'))} | {_fmt(r.get('failure_mean'))} | "
            f"{_fmt(r.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    bg = stats.get("best_gate", {})
    lines.append(f"- reference gate: {bg.get('gate', '—')}")
    lines.append("")
    lines.append("| symbol | n | precision | recall | future GradeA rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('n', 0)} | {_fmt(cmp.get('precision'), pct=True)} | "
            f"{_fmt(cmp.get('recall'), pct=True)} | {_fmt(cmp.get('positive_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_CONFIRMATION_GATE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave confirmation gate sweep complete")


if __name__ == "__main__":
    main()
