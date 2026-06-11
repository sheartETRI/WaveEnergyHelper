"""Wave Paths 스윕 · REPORT · PNG.

실행: python validation/wave_paths_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_path_analysis import PATH_SEP, build_path_rows, summarize_paths

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
]

CSV_COLS = ("timestamp", "path", "success", "return_pct", "expectancy_group")


def _plot_paths(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_paths_{symbol}_{interval}.png")
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1])

    top10 = stats.get("top10_paths", [])
    ax1 = fig.add_subplot(gs[0, :])
    if top10:
        labels = [p["path"][:55] for p in top10]
        counts = [p["n"] for p in top10]
        y = np.arange(len(labels))
        ax1.barh(y, counts, color="#1565C0", alpha=0.85)
        ax1.set_yticks(y)
        ax1.set_yticklabels(labels, fontsize=6)
        ax1.set_xlabel("count")
        ax1.set_title("Top 10 Paths (by n)")
        ax1.invert_yaxis()
    else:
        ax1.text(0.5, 0.5, "no data", ha="center")

    transitions = stats.get("transitions", [])[:12]
    ax2 = fig.add_subplot(gs[1, 0])
    if transitions:
        labels = [t["label"][:30] for t in transitions]
        pcts = [t["pct"] for t in transitions]
        y = np.arange(len(labels))
        ax2.barh(y, pcts, color="#6A1B9A", alpha=0.85)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.set_xlabel("%")
        ax2.set_title("Top Transitions")
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = fig.add_subplot(gs[1, 1])
    if transitions:
        try:
            from matplotlib.sankey import Sankey
            top = transitions[:6]
            sankey = Sankey(ax=ax3, scale=0.01, offset=0.2, head_length=0.4)
            flows = []
            labels = []
            for i, t in enumerate(top):
                flows.append(t["count"])
                labels.append(t["from"][:12])
            if flows:
                sankey.add(
                    flows=flows + [-sum(flows)],
                    labels=labels + ["sink"],
                    orientations=[0] * len(flows) + [0],
                )
                sankey.finish()
            ax3.set_title("Transition Sankey (top 6)")
        except Exception:
            ax3.text(0.5, 0.5, "sankey unavailable", ha="center")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle(f"{symbol} {interval} — Wave Paths (TP3)")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    out = os.path.join(OUT_DIR, "REPORT_WAVE_PATHS.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return out


def main():
    lines = [
        "# REPORT_WAVE_PATHS",
        "",
        "DB 기준 Wave Tracker 상태 전이 경로 분석 (TP3)",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval in TARGETS:
        df = build_path_rows(symbol, interval)
        csv_path = os.path.join(OUT_DIR, f"wave_paths_{symbol}_{interval}.csv")
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(csv_path, index=False)
        stats = summarize_paths(df)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot_paths(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- 에피소드: {stats['count']}")
        lines.append(f"- 고유 Path: {stats.get('unique_paths', 0)}")
        lines.append("")

        lines.append("### Top Winning Paths (n≥5)")
        lines.append("")
        lines.append("| path | n | win | expectancy |")
        lines.append("|---|---:|---:|---:|")
        for p in stats.get("top_winning_paths", [])[:20]:
            lines.append(
                f"| {p['path'][:80]} | {p['n']} | {p['win']} | "
                f"{p['expectancy']:.2f} |"
            )
        lines.append("")

        lines.append("### Top Losing Paths (n≥5)")
        lines.append("")
        lines.append("| path | n | win | expectancy |")
        lines.append("|---|---:|---:|---:|")
        for p in stats.get("top_losing_paths", [])[:20]:
            lines.append(
                f"| {p['path'][:80]} | {p['n']} | {p['win']} | "
                f"{p['expectancy']:.2f} |"
            )
        lines.append("")

        lines.append("### Transition Matrix")
        lines.append("")
        lines.append("| from | to | count | % |")
        lines.append("|---|---|---:|---:|")
        for t in stats.get("transitions", [])[:20]:
            lines.append(
                f"| {t['from']} | {t['to']} | {t['count']} | {t['pct']:.1f} |"
            )
        tb = stats.get("tb_required_from_db")
        wc = stats.get("w3_completed_from_db")
        lines.append("")
        if tb is not None:
            lines.append(
                f"- DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRED: **{tb:.1f}%**"
            )
        if wc is not None:
            lines.append(f"- DOUBLE_BOTTOM → WAVE3_COMPLETED: **{wc:.1f}%**")
        lines.append("")

        lines.append("### Path 빈도 (상위 10)")
        lines.append("")
        for path, cnt in list(stats.get("path_counts", {}).items())[:10]:
            lines.append(f"- {cnt}건 — {path[:90]}")
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        lines.append(
            f"| 고유 Path 수 | {a.get('unique_paths', 0)} | "
            f"{b.get('unique_paths', 0)} |"
        )
        tb_a = a.get("tb_required_from_db")
        tb_b = b.get("tb_required_from_db")
        wc_a = a.get("w3_completed_from_db")
        wc_b = b.get("w3_completed_from_db")
        lines.append(
            f"| DB→TB_REQUIRED | "
            f"{tb_a:.1f}% | {tb_b:.1f}% |"
            if tb_a is not None and tb_b is not None else
            "| DB→TB_REQUIRED | — | — |"
        )
        lines.append(
            f"| DB→W3_COMPLETED | "
            f"{wc_a:.1f}% | {wc_b:.1f}% |"
            if wc_a is not None and wc_b is not None else
            "| DB→W3_COMPLETED | — | — |"
        )
        top_a = a.get("top_winning_paths", [{}])[0] if a.get("top_winning_paths") else {}
        top_b = b.get("top_winning_paths", [{}])[0] if b.get("top_winning_paths") else {}
        lines.append(
            f"| Best Path Exp | {top_a.get('expectancy', 0):.2f} | "
            f"{top_b.get('expectancy', 0):.2f} |"
        )
        lines.append("")

    write_report(lines)
    print("wave paths sweep complete")


if __name__ == "__main__":
    main()
