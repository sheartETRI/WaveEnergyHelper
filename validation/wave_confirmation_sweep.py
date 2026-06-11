"""Wave Confirmation DB 에피소드 스윕 · REPORT · PNG.

실행: python validation/wave_confirmation_sweep.py
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

from analysis.wave_confirmation import (
    CONFIRM_WINDOWS,
    run_episodes_timeline,
    summarize_episodes,
)
from data.binance import get_auto_limit
from display.asof import build_ohlcv_cache, fetch_ohlcv_bare

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MA_WARMUP_BARS = 240

SWEEP_TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]


def _plot_delay_bars(episodes: pd.DataFrame, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_confirmation_delay_{symbol}_{interval}.png")
    n = len(episodes)
    if n == 0:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.text(0.5, 0.5, "No DB episodes", ha="center", va="center")
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return path

    x = np.arange(n)
    width = 0.35
    cross = episodes["confirm_cross_delay"].fillna(-1).astype(float)
    slope = episodes["confirm_slope_delay"].fillna(-1).astype(float)
    no_cross = cross < 0
    no_slope = slope < 0

    fig, ax = plt.subplots(figsize=(max(10, n * 0.35), 5))
    bars_c = ax.bar(x - width / 2, np.where(no_cross, 0, cross), width, label="cross delay", color="#2E7D32")
    bars_s = ax.bar(x + width / 2, np.where(no_slope, 0, slope), width, label="slope delay", color="#1565C0")

    for i, (bc, bs, nc, ns) in enumerate(zip(bars_c, bars_s, no_cross, no_slope)):
        if nc:
            bc.set_hatch("///")
            bc.set_facecolor("#BDBDBD")
            bc.set_height(0.5)
        if ns:
            bs.set_hatch("\\\\\\")
            bs.set_facecolor("#E0E0E0")
            bs.set_height(0.5)

    ax.set_xlabel("DB episode #")
    ax.set_ylabel("delay (bars)")
    ax.set_title(f"{symbol} {interval} — DB → K confirm delay")
    ax.legend()
    ax.set_xticks(x)
    ax.set_xticklabels([f"#{i+1}" for i in range(n)], rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_CONFIRMATION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    lines = [
        "# REPORT_WAVE_CONFIRMATION",
        "",
        "소파동 DB 이후 대파동 K 전환 지연시간 (관측 레이어)",
        "",
    ]
    all_stats: dict[str, dict] = {}

    for symbol, interval, limit in SWEEP_TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            raise RuntimeError(f"fetch failed {symbol} {interval}")
        extra = {"4h": lim} if interval == "4h" else {}
        cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)

        episodes = run_episodes_timeline(symbol, interval, bare, cache, warmup=MA_WARMUP_BARS)
        csv_path = os.path.join(OUT_DIR, f"wave_confirmation_{symbol}_{interval}.csv")
        episodes.to_csv(csv_path, index=False)
        png_path = _plot_delay_bars(episodes, symbol, interval)
        stats = summarize_episodes(episodes)
        all_stats[f"{symbol}_{interval}"] = stats

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png_path)}`")
        lines.append(f"- DB 에피소드 수: {stats['count']}")
        lines.append("")
        lines.append("### outcome 비율")
        lines.append("")
        lines.append(f"- CROSS_CONFIRMED: {stats['cross_pct']:.1f}%")
        lines.append(f"- SLOPE_CONFIRMED: {stats['slope_pct']:.1f}%")
        lines.append(f"- TB_REQUIRED: {stats['tb_required_pct']:.1f}%")
        lines.append(f"- TB_CONFIRMED: {stats['tb_confirmed_pct']:.1f}%")
        lines.append(f"- INVALIDATED: {stats['invalidated_pct']:.1f}%")
        lines.append(f"- NO_CONFIRM_WITHIN_WINDOW: {stats['no_confirm_pct']:.1f}%")
        if stats.get("mean_cross_delay") is not None:
            lines.append(f"- 평균 cross delay: {stats['mean_cross_delay']:.2f} 봉")
        else:
            lines.append("- 평균 cross delay: —")
        if stats.get("mean_slope_delay") is not None:
            lines.append(f"- 평균 slope delay: {stats['mean_slope_delay']:.2f} 봉")
        else:
            lines.append("- 평균 slope delay: —")
        lines.append("")

        lines.append("### delay 분포")
        lines.append("")
        lines.append("| delay | cross count | slope count |")
        lines.append("|---:|---:|---:|")
        for d in sorted(stats.get("delay_dist", {})):
            c = stats["delay_dist"][d]
            if c["cross"] or c["slope"]:
                lines.append(f"| {d} | {c['cross']} | {c['slope']} |")
        lines.append("")

        lines.append("### 윈도별 확인 비율")
        lines.append("")
        lines.append("| window | cross within % | slope within % |")
        lines.append("|---:|---:|---:|")
        for w in CONFIRM_WINDOWS:
            ws = stats["window_stats"][w]
            lines.append(f"| {w} | {ws['cross']:.1f} | {ws['slope']:.1f} |")
        lines.append("")

    if len(all_stats) == 2:
        lines.append("## ETH / BTC 비교")
        lines.append("")
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append(f"| 지표 | {keys[0]} | {keys[1]} |")
        lines.append("|---|---:|---:|")
        lines.append(f"| DB 에피소드 | {a['count']} | {b['count']} |")
        lines.append(f"| CROSS_CONFIRMED % | {a['cross_pct']:.1f} | {b['cross_pct']:.1f} |")
        lines.append(f"| SLOPE_CONFIRMED % | {a['slope_pct']:.1f} | {b['slope_pct']:.1f} |")
        lines.append(f"| TB_REQUIRED % | {a['tb_required_pct']:.1f} | {b['tb_required_pct']:.1f} |")
        lines.append(f"| NO_CONFIRM % | {a['no_confirm_pct']:.1f} | {b['no_confirm_pct']:.1f} |")
        mc_a = a.get("mean_cross_delay")
        mc_b = b.get("mean_cross_delay")
        ms_a = a.get("mean_slope_delay")
        ms_b = b.get("mean_slope_delay")

        def _fmt_delay(v):
            return f"{v:.2f}" if v is not None else "—"

        lines.append(
            f"| 평균 cross delay | {_fmt_delay(mc_a)} | {_fmt_delay(mc_b)} |"
        )
        lines.append(
            f"| 평균 slope delay | {_fmt_delay(ms_a)} | {_fmt_delay(ms_b)} |"
        )
        lines.append("")
        for w in CONFIRM_WINDOWS:
            wa, wb = a["window_stats"][w], b["window_stats"][w]
            lines.append(f"- window={w} cross within: {wa['cross']:.1f}% vs {wb['cross']:.1f}%")
        lines.append("")

    write_report(lines)
    print("wave confirmation sweep complete")


if __name__ == "__main__":
    main()
