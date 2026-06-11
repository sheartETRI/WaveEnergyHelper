"""Wave Survival 스윕 · REPORT · PNG.

실행: python validation/wave_survival_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_survival import (
    INITIAL_CROSS,
    INITIAL_SLOPE,
    INITIAL_TB,
    SURVIVAL_INITIAL_TYPES,
    SURVIVAL_THRESHOLDS,
    TERM_NEW_LL,
    TERM_OTHER,
    TERM_RE_OVERSOLD,
    build_survival_from_lifecycle,
    load_survival,
    summarize_survival,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
]

_TYPE_COLORS = {
    INITIAL_SLOPE: "#1565C0",
    INITIAL_CROSS: "#2E7D32",
    INITIAL_TB: "#6A1B9A",
}


def _plot_survival_bars(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_survival_{symbol}_{interval}.png")
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(SURVIVAL_THRESHOLDS))
    width = 0.25
    offsets = [-width, 0, width]

    for offset, itype in zip(offsets, SURVIVAL_INITIAL_TYPES):
        bt = stats["by_type"].get(itype, {})
        if not bt.get("count"):
            continue
        rates = [bt.get("rates", {}).get(t, 0.0) for t in SURVIVAL_THRESHOLDS]
        ax.bar(
            x + offset, rates, width,
            label=itype.replace("_CONFIRMED", ""),
            color=_TYPE_COLORS[itype],
            alpha=0.85,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([str(t) for t in SURVIVAL_THRESHOLDS])
    ax.set_xlabel("threshold (bars)")
    ax.set_ylabel("survival rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title(f"{symbol} {interval} — Survival by INITIAL type")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_SURVIVAL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    lines = [
        "# REPORT_WAVE_SURVIVAL",
        "",
        "INITIAL 경로별 생존(Survival) 분석",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval in TARGETS:
        survival = load_survival(symbol, interval)
        csv_path = os.path.join(OUT_DIR, f"wave_survival_{symbol}_{interval}.csv")
        survival.to_csv(csv_path, index=False)
        stats = summarize_survival(survival)
        all_stats[f"{symbol}_{interval}"] = stats
        png_path = _plot_survival_bars(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png_path)}`")
        lines.append(f"- 분석 대상 에피소드: {stats['count']}")
        lines.append("")

        lines.append("### INITIAL 분포")
        lines.append("")
        lines.append("| type | count |")
        lines.append("|---|---:|")
        for itype in SURVIVAL_INITIAL_TYPES:
            c = stats["initial_dist"].get(itype, 0)
            if c:
                lines.append(f"| {itype} | {c} |")
        lines.append("")

        lines.append("### 생존 통계")
        lines.append("")
        lines.append("| type | avg | median | max |")
        lines.append("|---|---:|---:|---:|")
        for itype in SURVIVAL_INITIAL_TYPES:
            bt = stats["by_type"].get(itype, {})
            if bt.get("count"):
                lines.append(
                    f"| {itype} | {bt['avg']:.1f} | {bt['median']:.1f} | {bt['max']:.0f} |"
                )
        lines.append("")

        lines.append("### 생존율 (%)")
        lines.append("")
        hdr = "| type | " + " | ".join(str(t) for t in SURVIVAL_THRESHOLDS) + " |"
        lines.append(hdr)
        lines.append("|---|" + "|".join(["---:"] * len(SURVIVAL_THRESHOLDS)) + "|")
        for itype in SURVIVAL_INITIAL_TYPES:
            bt = stats["by_type"].get(itype, {})
            if bt.get("count"):
                rates = bt.get("rates", {})
                cells = " | ".join(f"{rates.get(t, 0):.1f}" for t in SURVIVAL_THRESHOLDS)
                lines.append(f"| {itype} | {cells} |")
        lines.append("")

        lines.append("### 종료 원인 (%)")
        lines.append("")
        lines.append("| type | NEW_LL | RE_OVERSOLD | OTHER |")
        lines.append("|---|---:|---:|---:|")
        for itype in SURVIVAL_INITIAL_TYPES:
            bt = stats["by_type"].get(itype, {})
            if bt.get("count"):
                h = bt.get("hazard", {})
                lines.append(
                    f"| {itype} | {h.get(TERM_NEW_LL, 0):.1f} | "
                    f"{h.get(TERM_RE_OVERSOLD, 0):.1f} | {h.get(TERM_OTHER, 0):.1f} |"
                )
        lines.append("")

        lg = stats.get("longest", {})
        lines.append("### 최장 생존 사례")
        lines.append("")
        lines.append(f"- timestamp: {lg.get('timestamp', '—')}")
        lines.append(f"- type: {lg.get('initial_type', '—')}")
        lines.append(f"- survival_bars: {lg.get('survival_bars', '—')}")
        lines.append(f"- censored: {lg.get('censored', '—')}")
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        for itype, label in [
            (INITIAL_SLOPE, "SLOPE avg"),
            (INITIAL_CROSS, "CROSS avg"),
            (INITIAL_TB, "TB avg"),
        ]:
            va = a["by_type"].get(itype, {}).get("avg")
            vb = b["by_type"].get(itype, {}).get("avg")
            sa = f"{va:.1f}" if va is not None else "—"
            sb = f"{vb:.1f}" if vb is not None else "—"
            lines.append(f"| {label} | {sa} | {sb} |")
        for thr in (20, 40, 80):
            for itype, short in [(INITIAL_SLOPE, "SLOPE"), (INITIAL_CROSS, "CROSS")]:
                ra = a["by_type"].get(itype, {}).get("rates", {}).get(thr)
                rb = b["by_type"].get(itype, {}).get("rates", {}).get(thr)
                sa = f"{ra:.1f}%" if ra is not None else "—"
                sb = f"{rb:.1f}%" if rb is not None else "—"
                lines.append(f"| {short} {thr}봉 생존율 | {sa} | {sb} |")
        lines.append("")

    write_report(lines)
    print("wave survival sweep complete")


if __name__ == "__main__":
    main()
