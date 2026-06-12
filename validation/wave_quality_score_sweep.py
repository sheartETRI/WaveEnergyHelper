"""Wave Quality Score 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_quality_score import CSV_EXPORT_COLS, full_quality_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_quality_score.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    sp = [r for r in stats.get("score_performance", []) if r.get("n", 0) > 0]
    ax = axes[0, 0]
    if sp:
        scores = [r["score"] for r in sp]
        exp = [r.get("expectancy") or 0 for r in sp]
        ax.bar(scores, exp, color="#1565C0", alpha=0.85)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_xlabel("Quality Score")
        ax.set_title("Score vs Expectancy")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    cum = stats.get("cumulative_performance", [])
    ax2 = axes[0, 1]
    if cum:
        labels = [f">={r['threshold']}" for r in cum if r.get("n", 0) > 0]
        vals = [r.get("win_rate") or 0 for r in cum if r.get("n", 0) > 0]
        ax2.plot(range(len(labels)), vals, marker="o", color="#2E7D32")
        ax2.set_xticks(range(len(labels)))
        ax2.set_xticklabels(labels)
        ax2.set_title("Cumulative Score vs Win Rate")
        ax2.set_ylabel("win_rate")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    imp = stats.get("feature_importance", [])[:7]
    ax3 = axes[1, 0]
    if imp:
        labels = [r["feature"][:18] for r in imp]
        vals = [r.get("importance") or 0 for r in imp]
        ax3.barh(range(len(labels)), vals, color="#6A1B9A", alpha=0.85)
        ax3.set_yticks(range(len(labels)))
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.set_title("Feature Importance (|Δ expectancy|)")
        ax3.invert_yaxis()
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    top = stats.get("top_combinations", [])[:8]
    ax4 = axes[1, 1]
    if top:
        labels = [c["combo"][:20] for c in top]
        vals = [c.get("expectancy") or 0 for c in top]
        ax4.barh(range(len(labels)), vals, color="#00838F", alpha=0.85)
        ax4.set_yticks(range(len(labels)))
        ax4.set_yticklabels(labels, fontsize=6)
        ax4.set_title("Top Combinations")
        ax4.invert_yaxis()
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Quality Score Analysis")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building quality score analysis...")
    stats = full_quality_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_quality_score.csv"), index=False)
    png = _plot(stats)

    mono = stats.get("monotonicity", {})
    theory = stats.get("theory_evaluation", {})
    score5 = stats.get("score5_comparison", {})
    practical = stats.get("practical_minimum", {})

    lines = [
        "# REPORT_WAVE_QUALITY_SCORE",
        "",
        "Wave Quality Score — 통합 관측 레이어 검증",
        "",
        f"- events: {stats.get('event_count', 0)}",
        "",
        "## 1. Quality Score별 성능",
        "",
        "| score | count | win_rate | expectancy | profit_factor |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in stats.get("score_performance", []):
        lines.append(
            f"| {r.get('score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 2. Score 누적 (score≥k)")
    lines.append("")
    lines.append("| threshold | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("cumulative_performance", []):
        lines.append(
            f"| >={r.get('threshold', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 3. Top Quality Combination (상위 20)")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("top_combinations", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 4. Worst Quality Combination (하위 20)")
    lines.append("")
    lines.append("| combo | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("worst_combinations", []):
        lines.append(
            f"| {r.get('combo', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 5. Quality Score vs Failure Rate")
    lines.append("")
    lines.append("| score | n | failure_rate | strong_failure_rate |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("failure_rate_by_score", []):
        lines.append(
            f"| {r.get('quality_score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('failure_rate'), pct=True)} | "
            f"{_fmt(r.get('strong_failure_rate'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 6. Quality Score vs Survival")
    lines.append("")
    lines.append("| score | n | avg_survival_bars | avg_bucket_mid |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("survival_by_score", []):
        lines.append(
            f"| {r.get('quality_score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('avg_survival_bars'))} | {_fmt(r.get('avg_survival_bucket_mid'))} |"
        )
    lines.append("")

    lines.append("## 7. Quality Score vs Forward Return")
    lines.append("")
    lines.append("| score | n | avg_return_20 | avg_return_40 | avg_return_80 |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("forward_return_by_score", []):
        lines.append(
            f"| {r.get('quality_score', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} | "
            f"{_fmt(r.get('avg_return_80'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 8. ETH / BTC 비교")
    lines.append("")
    lines.append("| symbol | n | avg_quality_score | win_rate | expectancy |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('avg_quality_score'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")

    lines.append("## 9. 4h / 1d 비교")
    lines.append("")
    lines.append("| tf | n | avg_quality_score | win_rate | expectancy |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("timeframe_comparison", []):
        lines.append(
            f"| {r.get('timeframe', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('avg_quality_score'))} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")

    lines.append("## 10. Monotonicity 판정")
    lines.append("")
    lines.append(f"**결과: {mono.get('result', 'FAIL')}**")
    lines.append("")
    for metric, detail in mono.get("details", {}).items():
        lines.append(f"- {metric}: {'PASS' if detail.get('pass') else 'FAIL'} — {detail.get('values', {})}")
    lines.append("")

    lines.append("## Feature Importance Ranking")
    lines.append("")
    lines.append("| rank | feature | n_on | n_off | expectancy_on | expectancy_off | delta |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|")
    for i, r in enumerate(stats.get("feature_importance", []), 1):
        lines.append(
            f"| {i} | {r.get('feature', '')} | {r.get('n_on', 0)} | {r.get('n_off', 0)} | "
            f"{_fmt(r.get('expectancy_on'))} | {_fmt(r.get('expectancy_off'))} | "
            f"{_fmt(r.get('delta_expectancy'))} |"
        )
    lines.append("")

    high = score5.get("high", {})
    low = score5.get("low", {})
    lines.append("## Score≥5 유의미성")
    lines.append("")
    lines.append("| group | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, row in [("score>=5", high), ("score<5", low)]:
        lines.append(
            f"| {label} | {row.get('n', 0)} | "
            f"{_fmt(row.get('win_rate'), pct=True)} | {_fmt(row.get('expectancy'))} | "
            f"{_fmt(row.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 실전 최소 조건")
    lines.append("")
    if practical:
        lines.append(
            f"- **{practical.get('combo', '—')}** — n={practical.get('n', 0)}, "
            f"win_rate={_fmt(practical.get('win_rate'), pct=True)}, "
            f"expectancy={_fmt(practical.get('expectancy'))}"
        )
    else:
        lines.append("- 데이터 부족")
    lines.append("")

    lines.append("## 이론 최종 평가")
    lines.append("")
    lines.append(f"- Monotonicity: {theory.get('monotonicity', 'FAIL')}")
    lines.append(f"- Score≥5 유의미: {'YES' if theory.get('score5_significant') else 'NO'}")
    lines.append(f"- Overall: **{theory.get('overall', 'WEAK')}**")
    lines.append(f"- Supported layers: {', '.join(theory.get('supported_layers', [])) or '—'}")
    lines.append(f"- Weak layers: {', '.join(theory.get('weak_layers', [])) or '—'}")
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_QUALITY_SCORE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave quality score sweep complete")


if __name__ == "__main__":
    main()
