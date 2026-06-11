"""Wave Exit 스윕 · REPORT · PNG.

실행: python validation/wave_exit_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from analysis.wave_exit import (
    ALL_POLICIES,
    POLICY_A,
    POLICY_B,
    POLICY_C,
    POLICY_D,
    POLICY_E,
    build_exit_results,
    lifecycle_csv_path,
    summarize_exits,
)
from analysis.wave_survival import SURVIVAL_INITIAL_TYPES
from data.binance import get_auto_limit
from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]


def _plot_exit_panels(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_exit_{symbol}_{interval}.png")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    policies = [p for p in ALL_POLICIES if stats["by_policy"].get(p, {}).get("count")]
    if not policies:
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return path

    x = np.arange(len(policies))
    avg_ret = [stats["by_policy"][p]["avg_return"] for p in policies]
    win = [stats["by_policy"][p]["win_rate"] for p in policies]
    held = [stats["by_policy"][p]["avg_bars_held"] for p in policies]

    axes[0].bar(x, avg_ret, color="#2E7D32", alpha=0.85)
    axes[0].axhline(0, color="gray", lw=0.8)
    axes[0].set_title("avg return (%)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(policies, rotation=45, ha="right", fontsize=7)

    axes[1].bar(x, win, color="#1565C0", alpha=0.85)
    axes[1].set_title("win rate (%)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(policies, rotation=45, ha="right", fontsize=7)

    axes[2].bar(x, held, color="#FF9800", alpha=0.85)
    axes[2].set_title("avg bars held")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(policies, rotation=45, ha="right", fontsize=7)

    fig.suptitle(f"{symbol} {interval} — Exit Policy Comparison")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_EXIT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    lines = ["# REPORT_WAVE_EXIT", "", "청산 규칙(Exit Policy) 사후 검증", ""]
    all_stats: dict[str, dict] = {}

    for symbol, interval, limit in TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            raise RuntimeError(f"fetch failed {symbol} {interval}")
        pipeline = run_indicator_pipeline(bare)
        lifecycle = pd.read_csv(
            lifecycle_csv_path(symbol, interval), parse_dates=["timestamp"],
        )
        exits = build_exit_results(lifecycle, bare, pipeline)
        csv_path = os.path.join(OUT_DIR, f"wave_exit_{symbol}_{interval}.csv")
        exits.to_csv(csv_path, index=False)
        stats = summarize_exits(exits)
        all_stats[f"{symbol}_{interval}"] = stats
        png_path = _plot_exit_panels(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png_path)}`")
        lines.append(f"- episode×policy 행: {stats['count']}")
        lines.append("")

        for title, key, fmt in [
            ("정책별 평균 수익률 (%)", "avg_return", "{:.2f}"),
            ("정책별 중앙 수익률 (%)", "median_return", "{:.2f}"),
            ("정책별 승률 (%)", "win_rate", "{:.1f}"),
            ("정책별 평균 보유 봉 수", "avg_bars_held", "{:.1f}"),
        ]:
            lines.append(f"### {title}")
            lines.append("")
            lines.append("| policy | value |")
            lines.append("|---|---:|")
            for p in ALL_POLICIES:
                v = stats["by_policy"].get(p, {}).get(key)
                if v is not None and stats["by_policy"].get(p, {}).get("count"):
                    lines.append(f"| {p} | {fmt.format(v)} |")
            lines.append("")

        lines.append("### 정책별 평균 MFE / MAE (%)")
        lines.append("")
        lines.append("| policy | avg MFE | avg MAE |")
        lines.append("|---|---:|---:|")
        def _fmt_m(v):
            return f"{v:.2f}" if v is not None else "—"

        for p in ALL_POLICIES:
            bp = stats["by_policy"].get(p, {})
            if bp.get("count"):
                lines.append(
                    f"| {p} | {_fmt_m(bp.get('avg_mfe'))} | {_fmt_m(bp.get('avg_mae'))} |"
                )
        lines.append("")

        lines.append("### initial_type별 정책 성과")
        lines.append("")
        lines.append("| initial_type | policy | avg return | win rate |")
        lines.append("|---|---|---:|---:|")
        for row in stats.get("by_initial_policy", []):
            lines.append(
                f"| {row['initial_type']} | {row['policy']} | "
                f"{row['avg_return']:.2f} | {row['win_rate']:.1f} |"
            )
        lines.append("")

        lines.append("### 정책 랭킹 (score = avg_return × win_rate / 100)")
        lines.append("")
        for i, (p, v) in enumerate(stats.get("ranked", []), 1):
            lines.append(
                f"{i}. **{p}** — score {v['score']:.3f}, "
                f"avg {v['avg_return']:.2f}%, win {v['win_rate']:.1f}%"
            )
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| policy | ETH avg | BTC avg | ETH win | BTC win |")
        lines.append("|---|---:|---:|---:|---:|")
        for p in ALL_POLICIES:
            pa, pb = a["by_policy"].get(p, {}), b["by_policy"].get(p, {})
            if pa.get("count") or pb.get("count"):
                lines.append(
                    f"| {p} | {pa.get('avg_return', 0):.2f} | {pb.get('avg_return', 0):.2f} | "
                    f"{pa.get('win_rate', 0):.1f} | {pb.get('win_rate', 0):.1f} |"
                )
        lines.append("")

    write_report(lines)
    print("wave exit sweep complete")


if __name__ == "__main__":
    main()
