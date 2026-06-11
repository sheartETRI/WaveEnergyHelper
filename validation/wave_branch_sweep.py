"""Wave Branch 스윕 · REPORT · PNG.

실행: python validation/wave_branch_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_branch_analysis import (
    BRANCH_COMPLETED,
    BRANCH_REQUIRED,
    build_branch_analysis,
    export_branch_csv,
    summarize_branch_analysis,
)
from data.binance import get_auto_limit
from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]


def _fmt(v, digits=2):
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def _plot_branch(df, stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_branch_{symbol}_{interval}.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    for ax, col, title in [
        (axes[0, 0], "major_k", "major_k by branch"),
        (axes[0, 1], "major_k_minus_d", "major_k_minus_d by branch"),
    ]:
        for branch, color in [
            (BRANCH_COMPLETED, "#C62828"),
            (BRANCH_REQUIRED, "#2E7D32"),
        ]:
            sub = df[df["branch"] == branch][col].dropna()
            if not sub.empty:
                ax.hist(sub, bins=12, alpha=0.55, label=branch, color=color)
        ax.set_title(title)
        ax.legend(fontsize=7)

    top_num = stats.get("top_numeric_separators", [])[:8]
    ax3 = axes[1, 0]
    if top_num:
        labels = [x["feature"] for x in top_num]
        vals = [x["effect_size"] for x in top_num]
        y = np.arange(len(labels))
        ax3.barh(y, vals, color="#1565C0", alpha=0.85)
        ax3.set_yticks(y)
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.set_xlabel("effect_size")
        ax3.set_title("Top Numeric Separators")
        ax3.invert_yaxis()
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    top_cat = stats.get("top_categorical_separators", [])[:8]
    ax4 = axes[1, 1]
    if top_cat:
        labels = [f"{x['feature']}={x['value']}"[:28] for x in top_cat]
        vals = [x["lift"] for x in top_cat]
        y = np.arange(len(labels))
        ax4.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax4.set_yticks(y)
        ax4.set_yticklabels(labels, fontsize=6)
        ax4.set_xlabel("lift")
        ax4.set_title("Top Categorical Separators")
        ax4.invert_yaxis()
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle(f"{symbol} {interval} — Wave Branch")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    lines = [
        "# REPORT_WAVE_BRANCH",
        "",
        "DOUBLE_BOTTOM 분기(WAVE3_COMPLETED vs TRIPLE_BOTTOM_REQUIRED) Feature 비교",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval, limit in TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        pipeline = run_indicator_pipeline(bare)
        df = build_branch_analysis(symbol, interval, bare, pipeline)
        csv_path = os.path.join(OUT_DIR, f"wave_branch_{symbol}_{interval}.csv")
        export_branch_csv(df, csv_path)
        stats = summarize_branch_analysis(df)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot_branch(df, stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- DOUBLE_BOTTOM 이벤트: {stats['count']}")
        lines.append(f"- 분석 대상: {stats.get('analyzed_count', 0)}")
        lines.append(f"- 기타 분기: {stats.get('other_count', 0)}")
        lines.append("")

        lines.append("### Branch Count")
        lines.append("")
        lines.append("| branch | count |")
        lines.append("|---|---:|")
        for br, cnt in sorted(stats.get("branch_counts", {}).items(), key=lambda x: -x[1]):
            lines.append(f"| {br} | {cnt} |")
        lines.append("")

        lines.append("### Branch Performance")
        lines.append("")
        lines.append("| branch | n(linked) | win% | avg return | expectancy |")
        lines.append("|---|---:|---:|---:|---:|")
        for br, p in stats.get("branch_performance", {}).items():
            lines.append(
                f"| {br} | {p.get('n', 0)} | {_fmt(p.get('win_rate'))} | "
                f"{_fmt(p.get('avg_return'))} | {_fmt(p.get('expectancy'))} |"
            )
        lines.append("")

        lines.append("### Numeric Feature Comparison")
        lines.append("")
        lines.append("| feature | completed avg | required avg | effect_size |")
        lines.append("|---|---:|---:|---:|")
        for r in stats.get("numeric_comparison", []):
            lines.append(
                f"| {r['feature']} | {_fmt(r['completed_avg'])} | "
                f"{_fmt(r['required_avg'])} | {_fmt(r['effect_size'])} |"
            )
        lines.append("")

        lines.append("### Categorical Feature Lift")
        lines.append("")
        lines.append("| feature=value | n | required_rate% | lift |")
        lines.append("|---|---:|---:|---:|")
        for r in stats.get("categorical_lift", [])[:25]:
            lines.append(
                f"| {r['feature']}={r['value']} | {r['n']} | "
                f"{_fmt(r['required_rate'])} | {_fmt(r['lift'])} |"
            )
        lines.append("")

        lines.append("### Top Numeric Separators")
        lines.append("")
        for i, r in enumerate(stats.get("top_numeric_separators", [])[:10], 1):
            lines.append(
                f"{i}. {r['feature']} — effect_size {_fmt(r['effect_size'])} "
                f"(C:{_fmt(r['completed_avg'])} / R:{_fmt(r['required_avg'])})"
            )
        lines.append("")

        lines.append("### Top Categorical Separators")
        lines.append("")
        for i, r in enumerate(stats.get("top_categorical_separators", [])[:10], 1):
            lines.append(
                f"{i}. {r['feature']}={r['value']} — lift {_fmt(r['lift'])} "
                f"(req rate {_fmt(r['required_rate'])}%, n={r['n']})"
            )
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        for br in (BRANCH_COMPLETED, BRANCH_REQUIRED):
            pa = a.get("branch_performance", {}).get(br, {})
            pb = b.get("branch_performance", {}).get(br, {})
            lines.append(
                f"| {br} count | {a.get('branch_counts', {}).get(br, 0)} | "
                f"{b.get('branch_counts', {}).get(br, 0)} |"
            )
            lines.append(
                f"| {br} win% | {_fmt(pa.get('win_rate'))} | {_fmt(pb.get('win_rate'))} |"
            )
            lines.append(
                f"| {br} exp | {_fmt(pa.get('expectancy'))} | {_fmt(pb.get('expectancy'))} |"
            )
        lines.append("")

    out = os.path.join(OUT_DIR, "REPORT_WAVE_BRANCH.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave branch sweep complete")


if __name__ == "__main__":
    main()
