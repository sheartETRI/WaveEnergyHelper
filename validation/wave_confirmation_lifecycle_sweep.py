"""Wave Confirmation Lifecycle 스윕 · REPORT · PNG.

실행: python validation/wave_confirmation_lifecycle_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_confirmation_lifecycle import (
    ALL_INITIAL,
    ALL_POST,
    INITIAL_CROSS,
    INITIAL_NO_CONFIRM,
    INITIAL_SLOPE,
    INITIAL_TB,
    POST_EXPIRED,
    POST_HELD,
    POST_LATER_LL,
    POST_LATER_OS,
    run_lifecycle_timeline,
    summarize_lifecycle,
)
from data.binance import get_auto_limit
from display.asof import build_ohlcv_cache, fetch_ohlcv_bare

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MA_WARMUP_BARS = 240

SWEEP_TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]

_FLOW_COLORS = {
    INITIAL_CROSS: "#2E7D32",
    INITIAL_SLOPE: "#1565C0",
    INITIAL_TB: "#6A1B9A",
    INITIAL_NO_CONFIRM: "#9E9E9E",
    POST_HELD: "#81C784",
    POST_LATER_LL: "#EF5350",
    POST_LATER_OS: "#FF9800",
    POST_EXPIRED: "#BDBDBD",
    POST_LATER_OS: "#FF9800",
}


def _plot_lifecycle_sankey(df: pd.DataFrame, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_confirmation_lifecycle_{symbol}_{interval}.png")
    if df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No episodes", ha="center", va="center")
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return path

    counts: dict[tuple[str, str], int] = {}
    for _, row in df.iterrows():
        key = (str(row["initial_outcome"]), str(row["post_outcome"]))
        counts[key] = counts.get(key, 0) + 1

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(f"{symbol} {interval} — DB → INITIAL → POST")

    init_y = {INITIAL_CROSS: 0.82, INITIAL_SLOPE: 0.62, INITIAL_TB: 0.42, INITIAL_NO_CONFIRM: 0.22}
    post_y = {POST_HELD: 0.82, POST_LATER_LL: 0.62, POST_LATER_OS: 0.42, POST_EXPIRED: 0.22, "LATER_INVALIDATED": 0.12}

    for name, y in init_y.items():
        c = _FLOW_COLORS.get(name, "#888")
        ax.add_patch(plt.Rectangle((0.05, y - 0.06), 0.25, 0.1, color=c, alpha=0.85))
        ax.text(0.175, y, name.replace("_", "\n"), ha="center", va="center", fontsize=7, color="white", weight="bold")

    for name, y in post_y.items():
        c = _FLOW_COLORS.get(name, "#888")
        ax.add_patch(plt.Rectangle((2.7, y - 0.06), 0.25, 0.1, color=c, alpha=0.85))
        ax.text(2.825, y, name.replace("_", "\n"), ha="center", va="center", fontsize=7, color="white", weight="bold")

    ax.text(0.175, 0.95, "DB", ha="center", fontsize=10, weight="bold")
    ax.annotate("", xy=(0.35, 0.5), xytext=(0.05, 0.5), arrowprops=dict(arrowstyle="->", lw=2))
    ax.text(0.5, 0.5, "INITIAL", ha="center", fontsize=10, weight="bold")
    ax.annotate("", xy=(2.7, 0.5), xytext=(0.65, 0.5), arrowprops=dict(arrowstyle="->", lw=2))
    ax.text(2.825, 0.95, "POST", ha="center", fontsize=10, weight="bold")

    max_c = max(counts.values()) if counts else 1
    for (init, post), cnt in counts.items():
        y1 = init_y.get(init, 0.5)
        y2 = post_y.get(post, 0.5)
        lw = 0.5 + 4.0 * cnt / max_c
        ax.plot([0.32, 2.68], [y1, y2], color=_FLOW_COLORS.get(init, "#666"), alpha=0.45, linewidth=lw)
        mx, my = 1.5, (y1 + y2) / 2
        ax.text(mx, my, str(cnt), ha="center", va="center", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8))

    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_CONFIRMATION_LIFECYCLE.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def _fmt_num(v):
    return f"{v:.2f}" if v is not None else "—"


def main():
    lines = [
        "# REPORT_WAVE_CONFIRMATION_LIFECYCLE",
        "",
        "DB → INITIAL → POST 생존(lifecycle) 분석",
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

        df = run_lifecycle_timeline(symbol, interval, bare, cache, warmup=MA_WARMUP_BARS)
        csv_path = os.path.join(OUT_DIR, f"wave_confirmation_lifecycle_{symbol}_{interval}.csv")
        df.to_csv(csv_path, index=False)
        png_path = _plot_lifecycle_sankey(df, symbol, interval)
        stats = summarize_lifecycle(df)
        all_stats[f"{symbol}_{interval}"] = stats

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- PNG: `{os.path.basename(png_path)}`")
        lines.append(f"- DB 에피소드: {stats['count']}")
        lines.append("")

        lines.append("### INITIAL 분포")
        lines.append("")
        lines.append("| outcome | count | ratio |")
        lines.append("|---|---:|---:|")
        for st in ALL_INITIAL:
            d = stats["initial_dist"].get(st, {"count": 0, "ratio": 0.0})
            if d["count"]:
                lines.append(f"| {st} | {d['count']} | {d['ratio']:.1f}% |")
        lines.append("")

        lines.append("### POST 분포")
        lines.append("")
        lines.append("| outcome | count | ratio |")
        lines.append("|---|---:|---:|")
        for st in ALL_POST:
            d = stats["post_dist"].get(st, {"count": 0, "ratio": 0.0})
            if d["count"]:
                lines.append(f"| {st} | {d['count']} | {d['ratio']:.1f}% |")
        lines.append("")

        lines.append("### INITIAL → POST 전이")
        lines.append("")
        lines.append("| INITIAL | POST | count |")
        lines.append("|---|---|---:|")
        for (init, post), cnt in sorted(stats["transition"].items(), key=lambda x: -x[1]):
            lines.append(f"| {init} | {post} | {cnt} |")
        lines.append("")

        lines.append("### 평균 유지 기간 (INITIAL별 avg held)")
        lines.append("")
        lines.append("| INITIAL | avg held |")
        lines.append("|---|---:|")
        for init in (INITIAL_CROSS, INITIAL_SLOPE, INITIAL_TB):
            avg = stats["held_by_initial_avg"].get(init)
            lines.append(f"| {init} | {_fmt_num(avg)} |")
        lines.append("")

        mi = stats.get("mean_bars_until_initial")
        mh = stats.get("mean_bars_held_after_initial")

        lines.append("### 핵심 관측")
        lines.append("")
        lines.append(f"- 평균 bars_until_initial: {_fmt_num(mi)}")
        lines.append(f"- 평균 bars_held_after_initial: {_fmt_num(mh)}")
        lines.append(f"- 최장 bars_held: {stats.get('max_bars_held', '—')}")
        lines.append(f"- CROSS → HELD: {stats['cross_held_pct']:.1f}%")
        lines.append(f"- SLOPE → HELD: {stats['slope_held_pct']:.1f}%")
        lines.append(f"- CROSS → NEW_LL: {stats['cross_ll_pct']:.1f}%")
        lines.append(f"- SLOPE → NEW_LL: {stats['slope_ll_pct']:.1f}%")
        lines.append("")

    if len(all_stats) == 2:
        keys = list(all_stats.keys())
        a, b = all_stats[keys[0]], all_stats[keys[1]]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append(f"| 지표 | {keys[0]} | {keys[1]} |")
        lines.append("|---|---:|---:|")
        lines.append(f"| 에피소드 수 | {a['count']} | {b['count']} |")
        for label, key in [
            ("평균 bars_until_initial", "mean_bars_until_initial"),
            ("평균 bars_held", "mean_bars_held_after_initial"),
            ("CROSS→HELD %", "cross_held_pct"),
            ("SLOPE→HELD %", "slope_held_pct"),
            ("CROSS→NEW_LL %", "cross_ll_pct"),
            ("SLOPE→NEW_LL %", "slope_ll_pct"),
        ]:
            va, vb = a.get(key), b.get(key)
            sa = f"{va:.1f}" if va is not None else "—"
            sb = f"{vb:.1f}" if vb is not None else "—"
            lines.append(f"| {label} | {sa} | {sb} |")
        lines.append("")

    write_report(lines)
    print("wave confirmation lifecycle sweep complete")


if __name__ == "__main__":
    main()
