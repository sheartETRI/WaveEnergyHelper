"""Wave Outcome 스윕 · REPORT · PNG.

실행: python validation/wave_outcome_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_outcome import (
    INITIAL_CROSS,
    INITIAL_SLOPE,
    INITIAL_TB,
    OUTCOME_HORIZONS,
    SURVIVAL_FILTER_THRESHOLDS,
    build_outcomes_from_lifecycle,
    summarize_outcomes,
)
from analysis.wave_survival import SURVIVAL_INITIAL_TYPES, lifecycle_csv_path
from data.binance import get_auto_limit
from display.asof import fetch_ohlcv_bare

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]

_TYPE_COLORS = {
    INITIAL_SLOPE: "#1565C0",
    INITIAL_CROSS: "#2E7D32",
    INITIAL_TB: "#6A1B9A",
}

_PLOT_HORIZONS = (20, 40, 80)


def _plot_outcome_bars(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_outcome_{symbol}_{interval}.png")
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(_PLOT_HORIZONS))
    width = 0.25
    offsets = [-width, 0, width]

    for offset, itype in zip(offsets, SURVIVAL_INITIAL_TYPES):
        bt = stats["by_type"].get(itype, {})
        if not bt.get("count"):
            continue
        vals = [bt.get(f"mean_return_{h}") or 0.0 for h in _PLOT_HORIZONS]
        ax.bar(
            x + offset, vals, width,
            label=itype.replace("_CONFIRMED", ""),
            color=_TYPE_COLORS[itype],
            alpha=0.85,
        )

    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"+{h}" for h in _PLOT_HORIZONS])
    ax.set_ylabel("mean return (%)")
    ax.set_title(f"{symbol} {interval} — Outcome by INITIAL type")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _fmt(v):
    return f"{v:.2f}" if v is not None else "—"


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_OUTCOME.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    import pandas as pd

    lines = ["# REPORT_WAVE_OUTCOME", "", "INITIAL 경로별 가격 성과 분석", ""]
    all_stats: dict[str, dict] = {}

    for symbol, interval, limit in TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            raise RuntimeError(f"fetch failed {symbol} {interval}")

        lc_path = lifecycle_csv_path(symbol, interval)
        lifecycle = pd.read_csv(lc_path, parse_dates=["timestamp"])
        outcomes = build_outcomes_from_lifecycle(lifecycle, bare)
        csv_path = os.path.join(OUT_DIR, f"wave_outcome_{symbol}_{interval}.csv")
        outcomes.to_csv(csv_path, index=False)
        stats = summarize_outcomes(outcomes)
        all_stats[f"{symbol}_{interval}"] = stats
        png_path = _plot_outcome_bars(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png_path)}`")
        lines.append(f"- 에피소드: {stats['count']}")
        lines.append("")

        for title, prefix in [
            ("평균 수익률 (%)", "mean_return"),
            ("중앙값 수익률 (%)", "median_return"),
            ("승률 (%)", "win"),
            ("평균 MFE (%)", "mean_mfe"),
            ("평균 MAE (%)", "mean_mae"),
        ]:
            lines.append(f"### {title}")
            lines.append("")
            hdr = "| type | " + " | ".join(f"+{h}" for h in OUTCOME_HORIZONS) + " |"
            lines.append(hdr)
            lines.append("|---|" + "|".join(["---:"] * len(OUTCOME_HORIZONS)) + "|")
            for itype in SURVIVAL_INITIAL_TYPES:
                bt = stats["by_type"].get(itype, {})
                if bt.get("count"):
                    cells = " | ".join(_fmt(bt.get(f"{prefix}_{h}")) for h in OUTCOME_HORIZONS)
                    lines.append(f"| {itype} | {cells} |")
            lines.append("")

        lines.append("### 생존 조건별 평균 수익률 (%)")
        lines.append("")
        lines.append("| type | filter | n | mean +20 | mean +40 | mean +80 |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for itype in SURVIVAL_INITIAL_TYPES:
            bt = stats["by_type"].get(itype, {})
            if not bt.get("count"):
                continue
            lines.append(
                f"| {itype} | 전체 | {bt['count']} | "
                f"{_fmt(bt.get('mean_return_20'))} | {_fmt(bt.get('mean_return_40'))} | "
                f"{_fmt(bt.get('mean_return_80'))} |"
            )
            for thr in SURVIVAL_FILTER_THRESHOLDS:
                sc = bt.get("survival_cond", {}).get(thr, {})
                if sc.get("count"):
                    lines.append(
                        f"| {itype} | survival≥{thr} | {sc['count']} | "
                        f"{_fmt(sc.get('mean_return_20'))} | {_fmt(sc.get('mean_return_40'))} | "
                        f"{_fmt(sc.get('mean_return_80'))} |"
                    )
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        for itype, short in [
            (INITIAL_SLOPE, "SLOPE"),
            (INITIAL_CROSS, "CROSS"),
            (INITIAL_TB, "TB"),
        ]:
            for h in (20, 40, 80):
                va = a["by_type"].get(itype, {}).get(f"mean_return_{h}")
                vb = b["by_type"].get(itype, {}).get(f"mean_return_{h}")
                lines.append(f"| {short} +{h} avg | {_fmt(va)} | {_fmt(vb)} |")
        lines.append("")

    write_report(lines)
    print("wave outcome sweep complete")


if __name__ == "__main__":
    main()
