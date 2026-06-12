"""Wave Quality Rule Set 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_quality_ruleset import CSV_EXPORT_COLS, full_ruleset_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_quality_ruleset.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    top = stats.get("top_expectancy", [])[:10]
    ax = axes[0, 0]
    if top:
        labels = [r["rule_label"][:22] for r in top]
        vals = [r.get("expectancy") or 0 for r in top]
        ax.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_title("Top Expectancy Rule Sets")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    size_eff = stats.get("rule_size_effect", [])
    ax2 = axes[0, 1]
    if size_eff:
        sizes = [r["rule_size"] for r in size_eff]
        avg_exp = [r.get("avg_expectancy") or 0 for r in size_eff]
        max_exp = [r.get("max_expectancy") or 0 for r in size_eff]
        x = np.arange(len(sizes))
        w = 0.35
        ax2.bar(x - w / 2, avg_exp, w, label="avg exp", color="#2E7D32", alpha=0.85)
        ax2.bar(x + w / 2, max_exp, w, label="max exp", color="#6A1B9A", alpha=0.85)
        ax2.set_xticks(x)
        ax2.set_xticklabels([f"{s} cond" for s in sizes])
        ax2.set_title("Rule Size Effect")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    pareto = stats.get("pareto_frontier", [])[:12]
    ax3 = axes[1, 0]
    if pareto:
        wr = [r.get("win_rate") or 0 for r in pareto]
        exp = [r.get("expectancy") or 0 for r in pareto]
        ns = [r.get("n", 3) for r in pareto]
        ax3.scatter(wr, exp, s=[n * 15 for n in ns], alpha=0.7, c="#00838F")
        ax3.set_xlabel("win_rate")
        ax3.set_ylabel("expectancy")
        ax3.set_title("Pareto Frontier")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    interact = stats.get("feature_interaction", [])
    ax4 = axes[1, 1]
    deltas = [r for r in interact if r.get("delta_expectancy") is not None]
    if deltas:
        labels = [r["chain"][-25:] for r in deltas]
        vals = [r.get("delta_expectancy") or 0 for r in deltas]
        colors = ["#2E7D32" if v >= 0 else "#C62828" for v in vals]
        ax4.barh(range(len(labels)), vals, color=colors, alpha=0.85)
        ax4.set_yticks(range(len(labels)))
        ax4.set_yticklabels(labels, fontsize=6)
        ax4.set_title("ΔExpectancy (chain steps)")
        ax4.invert_yaxis()
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Quality Rule Set Discovery")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _rule_table(lines: list, rules: list, title: str):
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| rule | n | win_rate | expectancy | profit_factor | robustness_gap |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in rules:
        lines.append(
            f"| {r.get('rule_label', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} | {_fmt(r.get('robustness_gap'))} |"
        )
    lines.append("")


def main():
    print("building quality ruleset analysis...")
    stats = full_ruleset_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_quality_ruleset.csv"), index=False)
    png = _plot(stats)

    practical = stats.get("practical_rules", {})
    vs = stats.get("vs_quality_score", {})
    lines = [
        "# REPORT_WAVE_QUALITY_RULESET",
        "",
        "Wave Quality Rule Set — 최소 Rule Set 발견",
        "",
        f"- events: {stats.get('event_count', 0)}",
        f"- valid rule sets (n>={3}): {stats.get('rule_count', 0)}",
        "",
    ]

    _rule_table(lines, stats.get("top_expectancy", []), "1. Top Expectancy Rule Set 30")
    _rule_table(lines, stats.get("top_win_rate", []), "2. Top Win Rate Rule Set 30")
    _rule_table(lines, stats.get("top_profit_factor", []), "3. Top Profit Factor Rule Set 30")
    _rule_table(lines, stats.get("top_robust", []), "4. Top Robust Rule Set 30")

    lines.append("## 5. Pareto Frontier Rule Set")
    lines.append("")
    lines.append("| rule | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("pareto_frontier", []):
        lines.append(
            f"| {r.get('rule_label', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 6. Rule Set Size 효과")
    lines.append("")
    lines.append("| size | rule_count | avg_n | avg_win_rate | avg_expectancy | max_expectancy |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in stats.get("rule_size_effect", []):
        lines.append(
            f"| {r.get('rule_size', '')} | {r.get('rule_count', 0)} | "
            f"{_fmt(r.get('avg_n'))} | {_fmt(r.get('avg_win_rate'), pct=True)} | "
            f"{_fmt(r.get('avg_expectancy'))} | {_fmt(r.get('max_expectancy'))} |"
        )
    lines.append("")

    lines.append("## 7. Feature Interaction Map")
    lines.append("")
    lines.append("| chain | step | n | expectancy | win_rate | Δexp | Δwr |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in stats.get("feature_interaction", []):
        lines.append(
            f"| {r.get('chain', '')} | {r.get('step', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('expectancy'))} | {_fmt(r.get('win_rate'), pct=True)} | "
            f"{_fmt(r.get('delta_expectancy'))} | {_fmt(r.get('delta_win_rate'), pct=True)} |"
        )
    lines.append("")

    for key, title in (
        ("best_expectancy", "최고 Expectancy Rule"),
        ("best_robust", "최고 Robust Rule"),
        ("best_sample", "최고 Sample Rule"),
        ("best_balanced", "최고 균형 Rule"),
    ):
        r = practical.get(key, {})
        if r:
            lines.append(f"### {title}")
            lines.append("")
            lines.append(
                f"- **{r.get('rule_label', '—')}** — n={r.get('n', 0)}, "
                f"win_rate={_fmt(r.get('win_rate'), pct=True)}, "
                f"expectancy={_fmt(r.get('expectancy'))}, "
                f"robustness_gap={_fmt(r.get('robustness_gap'))}"
            )
            lines.append("")

    lines.append("## 8. ETH / BTC 비교 (균형 Rule)")
    lines.append("")
    lines.append("| symbol | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_comparison", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 9. 4h / 1d 비교 (균형 Rule)")
    lines.append("")
    lines.append("| tf | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("timeframe_comparison", []):
        lines.append(
            f"| {r.get('timeframe', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    qbest = vs.get("quality_best", {})
    rbest = vs.get("rule_best", {})
    lines.append("## 10. Quality Score 대비 개선")
    lines.append("")
    lines.append(f"**Rule Set vs Quality Score: {vs.get('result', 'FAIL')}**")
    lines.append("")
    lines.append(f"- Quality best: {qbest.get('method', '—')} — n={qbest.get('n', 0)}, "
                 f"expectancy={_fmt(qbest.get('expectancy'))}")
    lines.append(f"- Rule best: {rbest.get('rule_label', '—')} — n={rbest.get('n', 0)}, "
                 f"expectancy={_fmt(rbest.get('expectancy'))}")
    lines.append(f"- Δ expectancy: {_fmt(vs.get('expectancy_improvement'))}")
    lines.append("")

    lines.append("## 11. 요소 필요성 (Essential / Useful / Weak)")
    lines.append("")
    lines.append("| element | top15_freq | solo_n | solo_exp | class |")
    lines.append("|---|---:|---:|---:|---|")
    for r in stats.get("element_necessity", []):
        lines.append(
            f"| {r.get('element', '')} | {r.get('top15_frequency', 0)} | "
            f"{r.get('solo_n', 0)} | {_fmt(r.get('solo_expectancy'))} | "
            f"{r.get('classification', '')} |"
        )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_QUALITY_RULESET.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave quality ruleset sweep complete")


if __name__ == "__main__":
    main()
