"""Wave Expectancy 스윕 · REPORT · PNG.

실행: python validation/wave_expectancy_sweep.py
"""
from __future__ import annotations

import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_expectancy import (
    FAMILY_SHORT,
    build_expectancy,
    export_expectancy_csv,
    summarize_expectancy,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
]


def _fmt(v: float, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and (math.isinf(v) or math.isnan(v))):
        return "—"
    return f"{v:.{digits}f}"


def _plot_expectancy(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_expectancy_{symbol}_{interval}.png")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    for ax, items, title, color in [
        (axes[0], stats.get("top10_expectancy", []), "Top Expectancy 10", "#1565C0"),
        (axes[1], stats.get("worst10_expectancy", []), "Worst Expectancy 10", "#B71C1C"),
    ]:
        if not items:
            ax.text(0.5, 0.5, "no data", ha="center")
            continue
        labels = [x.get("label", x.get("condition", ""))[:35] for x in items]
        vals = [x.get("expectancy", 0) for x in items]
        y = np.arange(len(labels))
        ax.barh(y, vals, color=color, alpha=0.85)
        ax.axvline(0, color="gray", linewidth=0.8, linestyle="--")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_xlabel("Expectancy %")
        ax.set_title(title)
        ax.invert_yaxis()

    scatter = stats.get("scatter", [])
    ax3 = axes[2]
    if scatter:
        xs = [s["success_rate"] for s in scatter]
        ys = [s["expectancy"] for s in scatter]
        ns = [s["n"] for s in scatter]
        ax3.scatter(xs, ys, s=[n * 3 for n in ns], alpha=0.5, c="#5E35B1")
        ax3.axhline(0, color="gray", linewidth=0.8, linestyle="--")
        ax3.axvline(50, color="gray", linewidth=0.8, linestyle="--")
        ax3.set_xlabel("Success Rate %")
        ax3.set_ylabel("Expectancy %")
        ax3.set_title("Success Rate vs Expectancy")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle(f"{symbol} {interval} — Expectancy (TP3)")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_EXPECTANCY.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def _family_table(rows: list[dict]) -> list[str]:
    lines = [
        "| family | n | win | avg win | avg loss | expectancy |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(rows, key=lambda x: x.get("expectancy", -999), reverse=True):
        fam = FAMILY_SHORT.get(r["value"], r["value"])
        lines.append(
            f"| {fam} | {r['n']} | {r['win']} | {_fmt(r['avg_win'])} | "
            f"{_fmt(r['avg_loss'])} | {_fmt(r['expectancy'])} |"
        )
    return lines


def main():
    lines = [
        "# REPORT_WAVE_EXPECTANCY",
        "",
        "TP3_SL3_TIMEOUT20 기준 Expectancy 분석",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval in TARGETS:
        df = build_expectancy(symbol, interval)
        csv_path = os.path.join(OUT_DIR, f"wave_expectancy_{symbol}_{interval}.csv")
        export_expectancy_csv(df, csv_path)
        stats = summarize_expectancy(df)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot_expectancy(stats, symbol, interval)
        ov = stats.get("overall", {})

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- 에피소드: {stats['count']}")
        lines.append(f"- 전체 Expectancy: {_fmt(ov.get('expectancy', 0))}%")
        lines.append(f"- 전체 승률: {_fmt(ov.get('win_rate', 0))}%")
        lines.append("")

        lines.append("### Initial Type")
        lines.append("")
        lines.append("| type | n | win | avg win | avg loss | expectancy |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for r in stats.get("by_feature", {}).get("initial_type", []):
            lines.append(
                f"| {r['value']} | {r['n']} | {r['win']} | {_fmt(r['avg_win'])} | "
                f"{_fmt(r['avg_loss'])} | {_fmt(r['expectancy'])} |"
            )
        lines.append("")

        lines.append("### State")
        lines.append("")
        lines.append("| state | n | expectancy |")
        lines.append("|---|---:|---:|")
        for r in sorted(
            stats.get("by_feature", {}).get("state", []),
            key=lambda x: x.get("expectancy", -999), reverse=True,
        ):
            lines.append(
                f"| {r['value']} | {r['n']} | {_fmt(r['expectancy'])} |"
            )
        lines.append("")

        lines.append("### Family")
        lines.append("")
        lines.extend(_family_table(stats.get("by_feature", {}).get("family", [])))
        lines.append("")

        lines.append("### Survival")
        lines.append("")
        lines.append("| bucket | n | expectancy |")
        lines.append("|---|---:|---:|")
        for r in stats.get("by_feature", {}).get("survival_bucket", []):
            lines.append(
                f"| {r['value']} | {r['n']} | {_fmt(r['expectancy'])} |"
            )
        lines.append("")

        lines.append("### Verdict")
        lines.append("")
        lines.append("| verdict | n | expectancy |")
        lines.append("|---|---:|---:|")
        for r in sorted(
            stats.get("by_feature", {}).get("verdict", []),
            key=lambda x: x.get("expectancy", -999), reverse=True,
        ):
            v = r["value"][:50]
            lines.append(f"| {v} | {r['n']} | {_fmt(r['expectancy'])} |")
        lines.append("")

        lines.append("### TOP_EXPECTANCY")
        lines.append("")
        for i, r in enumerate(stats.get("top_expectancy", [])[:20], 1):
            lines.append(
                f"{i}. {r.get('label', r.get('condition', ''))} — "
                f"exp {_fmt(r['expectancy'])}% (n={r['n']}, win {r['success_rate']:.1f}%)"
            )
        lines.append("")

        lines.append("### WORST_EXPECTANCY")
        lines.append("")
        for i, r in enumerate(stats.get("worst_expectancy", [])[:20], 1):
            lines.append(
                f"{i}. {r.get('label', r.get('condition', ''))} — "
                f"exp {_fmt(r['expectancy'])}% (n={r['n']}, win {r['success_rate']:.1f}%)"
            )
        lines.append("")

        lines.append("### 조건 조합 (n≥5)")
        lines.append("")
        lines.append("| condition | n | expectancy |")
        lines.append("|---|---:|---:|")
        for r in stats.get("combos", [])[:15]:
            lines.append(
                f"| {r['condition']} | {r['n']} | {_fmt(r['expectancy'])} |"
            )
        lines.append("")

        hpf = stats.get("highest_profit_factor")
        hpr = stats.get("highest_payoff_ratio")
        if hpf:
            lines.append(
                f"- Highest Profit Factor: {hpf['label']} — "
                f"{_fmt(hpf['profit_factor'])} (n={hpf['n']})"
            )
        if hpr:
            lines.append(
                f"- Highest Payoff Ratio: {hpr['label']} — "
                f"{_fmt(hpr['payoff_ratio'])} (n={hpr['n']})"
            )
        lines.append("")

        lines.append("### High Win / Low Expectancy")
        lines.append("")
        for r in stats.get("high_win_low_expectancy", [])[:10]:
            lines.append(
                f"- {r['label']}: win {r['success_rate']:.1f}%, "
                f"exp {_fmt(r['expectancy'])}% (n={r['n']})"
            )
        lines.append("")

        lines.append("### Low Win / High Expectancy")
        lines.append("")
        for r in stats.get("low_win_high_expectancy", [])[:10]:
            lines.append(
                f"- {r['label']}: win {r['success_rate']:.1f}%, "
                f"exp {_fmt(r['expectancy'])}% (n={r['n']})"
            )
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        lines.append(
            f"| 전체 Expectancy | "
            f"{_fmt(a['overall'].get('expectancy', 0))}% | "
            f"{_fmt(b['overall'].get('expectancy', 0))}% |"
        )
        lines.append(
            f"| 전체 승률 | "
            f"{_fmt(a['overall'].get('win_rate', 0))}% | "
            f"{_fmt(b['overall'].get('win_rate', 0))}% |"
        )
        for feat in ("initial_type", "family", "survival_bucket"):
            for r_a in a.get("by_feature", {}).get(feat, []):
                match = next(
                    (x for x in b.get("by_feature", {}).get(feat, [])
                     if x["value"] == r_a["value"]),
                    None,
                )
                bv = _fmt(match["expectancy"]) if match else "—"
                val = FAMILY_SHORT.get(r_a["value"], r_a["value"])
                lines.append(f"| {feat}={val} | {_fmt(r_a['expectancy'])} | {bv} |")
        lines.append("")

    write_report(lines)
    print("wave expectancy sweep complete")


if __name__ == "__main__":
    main()
