"""Wave Confluence 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_confluence import build_confluence, summarize_confluence
from data.binance import get_auto_limit
from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS = [("ETHUSDT", "4h", 1600), ("BTCUSDT", "1d", None)]


def _fmt(v, d=2):
    return "—" if v is None else f"{v:.{d}f}"


def _plot(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_confluence_{symbol}_{interval}.png")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    top = stats.get("top_confluence_factors", [])[:8]
    ax = axes[0]
    if top:
        labels = [t["label"][:28] for t in top]
        vals = [t["score"] for t in top]
        y = np.arange(len(labels))
        ax.barh(y, vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_title("Top Factors")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    bundles = stats.get("top_confluence_bundles", [])[:8]
    ax2 = axes[1]
    if bundles:
        labels = [b["bundle"][:28] for b in bundles]
        vals = [b["expectancy"] for b in bundles]
        y = np.arange(len(labels))
        ax2.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax2.axvline(0, color="gray", ls="--", lw=0.8)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.set_title("Top Bundles")
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    scores = stats.get("score_summary", [])
    ax3 = axes[2]
    if scores:
        xs = [s["score"] for s in scores]
        ys = [s["expectancy"] for s in scores]
        ax3.bar(xs, ys, color="#2E7D32", alpha=0.85)
        ax3.axhline(0, color="gray", ls="--", lw=0.8)
        ax3.set_xlabel("Confluence Score")
        ax3.set_ylabel("Expectancy %")
        ax3.set_title("Score vs Expectancy")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle(f"{symbol} {interval} — Wave Confluence")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    lines = ["# REPORT_WAVE_CONFLUENCE", "", "MACD/RSI/EMA/변동성 Confluence 관측", ""]
    all_stats = {}

    for symbol, interval, limit in TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        pipeline = run_indicator_pipeline(bare)
        df = build_confluence(symbol, interval, bare, pipeline)
        csv_path = os.path.join(OUT_DIR, f"wave_confluence_{symbol}_{interval}.csv")
        df.to_csv(csv_path, index=False)
        stats = summarize_confluence(df, symbol)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `wave_confluence_{symbol}_{interval}.csv`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- 이벤트: {stats['count']} (success cohort {stats.get('success_count',0)}, failure {stats.get('failure_count',0)})")
        lines.append("")

        lines.append("### Top Confluence Factors")
        lines.append("")
        for i, f in enumerate(stats.get("top_confluence_factors", [])[:15], 1):
            if f.get("kind") == "numeric":
                lines.append(
                    f"{i}. {f['label']} — effect {_fmt(f['score'])} "
                    f"(S:{_fmt(f.get('success_avg'))} / F:{_fmt(f.get('failure_avg'))})"
                )
            else:
                lines.append(
                    f"{i}. {f['label']} — lift {_fmt(f['score'])} "
                    f"(win {f.get('success_rate',0):.1f}%, n={f.get('n',0)})"
                )
        lines.append("")

        lines.append("### Top Confluence Bundles (n≥5)")
        lines.append("")
        lines.append("| bundle | n | win | expectancy |")
        lines.append("|---|---:|---:|---:|")
        for b in stats.get("top_confluence_bundles", [])[:15]:
            lines.append(
                f"| {b['bundle'][:70]} | {b['n']} | {b['win']} | {_fmt(b['expectancy'])} |"
            )
        lines.append("")

        lines.append("### Score vs Win Rate")
        lines.append("")
        lines.append("| score | count | win% |")
        lines.append("|---:|---:|---:|")
        for s in stats.get("score_summary", []):
            lines.append(f"| {s['score']} | {s['count']} | {_fmt(s['win_rate'])} |")
        lines.append("")

        lines.append("### Score vs Expectancy")
        lines.append("")
        lines.append("| score | count | expectancy |")
        lines.append("|---:|---:|---:|")
        for s in stats.get("score_summary", []):
            lines.append(f"| {s['score']} | {s['count']} | {_fmt(s['expectancy'])} |")
        lines.append("")

        for title, key in [("MACD", "macd_comparison"), ("RSI", "rsi_comparison"), ("EMA", "ema_comparison")]:
            lines.append(f"### {title} Comparison")
            lines.append("")
            lines.append("| feature | success avg | failure avg | effect_size |")
            lines.append("|---|---:|---:|---:|")
            for r in stats.get(key, []):
                lines.append(
                    f"| {r['feature']} | {_fmt(r['success_avg'])} | "
                    f"{_fmt(r['failure_avg'])} | {_fmt(r['effect_size'])} |"
                )
            lines.append("")

    if len(all_stats) == 2:
        a, b = all_stats["ETHUSDT_4h"], all_stats["BTCUSDT_1d"]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        lines.append(f"| success cohort | {a.get('success_count',0)} | {b.get('success_count',0)} |")
        lines.append(f"| failure cohort | {a.get('failure_count',0)} | {b.get('failure_count',0)} |")
        ta = a.get("top_confluence_factors", [{}])[0] if a.get("top_confluence_factors") else {}
        tb = b.get("top_confluence_factors", [{}])[0] if b.get("top_confluence_factors") else {}
        lines.append(f"| top factor | {ta.get('label','—')} | {tb.get('label','—')} |")
        lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_CONFLUENCE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave confluence sweep complete")


if __name__ == "__main__":
    main()
