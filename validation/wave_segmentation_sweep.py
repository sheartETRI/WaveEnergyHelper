"""Wave Segmentation 스윕 · REPORT · PNG.

실행: python validation/wave_segmentation_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_segmentation import build_segmentation, summarize_segmentation
from data.binance import get_auto_limit
from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]

CSV_COLS = [
    "timestamp", "success", "strong_success", "strong_failure",
    "state", "initial_type", "survival_bucket", "verdict", "family",
    "stable_family", "major_k", "major_d", "kd_gap", "return_pct",
]


def _plot_top_factors(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_segmentation_{symbol}_{interval}.png")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, items, title, color in [
        (axes[0], stats.get("top10_success", []), "Top Success 10", "#2E7D32"),
        (axes[1], stats.get("top10_failure", []), "Top Failure 10", "#C62828"),
    ]:
        if not items:
            ax.text(0.5, 0.5, "no data", ha="center")
            continue
        labels = [x.get("label", x.get("condition", ""))[:40] for x in items]
        vals = [
            x.get("success_rate", x.get("failure_rate", 0)) for x in items
        ]
        y = np.arange(len(labels))
        ax.barh(y, vals, color=color, alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xlabel("%")
        ax.set_title(title)
        ax.invert_yaxis()

    fig.suptitle(f"{symbol} {interval} — Segmentation (TP3)")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_SEGMENTATION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    lines = [
        "# REPORT_WAVE_SEGMENTATION",
        "",
        "TP3_SL3_TIMEOUT20 기준 성공/실패 Segmentation",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval, limit in TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        pipeline = run_indicator_pipeline(bare)
        seg = build_segmentation(symbol, interval, bare, pipeline)
        csv_path = os.path.join(OUT_DIR, f"wave_segmentation_{symbol}_{interval}.csv")
        out_cols = [c for c in CSV_COLS if c in seg.columns]
        seg[out_cols].to_csv(csv_path, index=False)
        stats = summarize_segmentation(seg)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot_top_factors(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- TP3 에피소드: {stats['count']}")
        lines.append(f"- 전체 성공률: {stats.get('success_rate', 0):.1f}%")
        lines.append("")

        for title, col in [
            ("성공률 by feature", "success_rate"),
            ("실패율 by feature", "failure_rate"),
        ]:
            lines.append(f"### {title}")
            lines.append("")
            lines.append("| feature | value | n | rate |")
            lines.append("|---|---|---:|---:|")
            for feat, rates in stats.get("by_feature", {}).items():
                for r in sorted(rates, key=lambda x: x[col], reverse=True):
                    lines.append(
                        f"| {feat} | {r['value']} | {r['n']} | {r[col]:.1f}% |"
                    )
            lines.append("")

        lines.append("### TOP_SUCCESS_FACTORS")
        lines.append("")
        for i, r in enumerate(stats.get("top_success", [])[:20], 1):
            lines.append(
                f"{i}. {r['label']} — success {r['success_rate']:.1f}% (n={r['n']})"
            )
        lines.append("")

        lines.append("### TOP_FAILURE_FACTORS")
        lines.append("")
        for i, r in enumerate(stats.get("top_failure", [])[:20], 1):
            lines.append(
                f"{i}. {r['label']} — failure {r['failure_rate']:.1f}% (n={r['n']})"
            )
        lines.append("")

        lines.append("### 조건 조합 (n≥5)")
        lines.append("")
        lines.append("| condition | n | success | success% |")
        lines.append("|---|---|---:|---:|")
        for r in stats.get("combos", [])[:15]:
            lines.append(
                f"| {r['condition']} | {r['n']} | {r['success']} | {r['success_rate']:.1f} |"
            )
        sp = stats.get("strongest_pair")
        wp = stats.get("weakest_pair")
        if sp:
            lines.append("")
            lines.append(
                f"- strongest pair: {sp['condition']} — {sp['success_rate']:.1f}% (n={sp['n']})"
            )
        if wp:
            lines.append(
                f"- weakest pair: {wp['condition']} — {wp['success_rate']:.1f}% (n={wp['n']})"
            )
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append(f"| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        lines.append(
            f"| 전체 성공률 | {a.get('success_rate', 0):.1f}% | "
            f"{b.get('success_rate', 0):.1f}% |"
        )
        for feat in ("initial_type", "family", "stable_family", "survival_bucket"):
            lines.append(f"| | | |")
            for r_a in a.get("by_feature", {}).get(feat, []):
                match = next(
                    (x for x in b.get("by_feature", {}).get(feat, [])
                     if x["value"] == r_a["value"]),
                    None,
                )
                bv = f"{match['success_rate']:.1f}" if match else "—"
                lines.append(
                    f"| {feat}={r_a['value']} | {r_a['success_rate']:.1f}% | {bv} |"
                )
        lines.append("")

    write_report(lines)
    print("wave segmentation sweep complete")


if __name__ == "__main__":
    main()
