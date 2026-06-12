"""Wave Rule Set Robustness 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_ruleset_robustness import full_robustness_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_ruleset_robustness.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    scores = stats.get("robustness_scores", [])
    ax = axes[0, 0]
    if scores:
        labels = [s["rule"] for s in scores]
        vals = [s.get("robustness_score") or 0 for s in scores]
        ax.bar(labels, vals, color="#1565C0", alpha=0.85)
        ax.set_ylim(0, 100)
        ax.set_title("Robustness Score by Rule")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    walk = stats.get("walk_forward", [])
    ax2 = axes[0, 1]
    rules = sorted({r["rule"] for r in walk})
    if walk and rules:
        for rule in rules:
            rw = [r for r in walk if r["rule"] == rule]
            qs = [r["segment"] for r in rw]
            exps = [r.get("expectancy") or 0 for r in rw]
            ax2.plot(qs, exps, marker="o", label=rule)
        ax2.axhline(0, color="gray", linewidth=0.8)
        ax2.set_title("Walk Forward Expectancy")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    sens = stats.get("exit_sensitivity", [])
    ax3 = axes[1, 0]
    if sens:
        labels = [s["rule"] for s in sens]
        vals = [s.get("exit_policy_sensitivity") or 0 for s in sens]
        ax3.bar(labels, vals, color="#6A1B9A", alpha=0.85)
        ax3.set_title("Exit Policy Sensitivity")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    sym = stats.get("symbol_robustness", [])
    ax4 = axes[1, 1]
    heat_rules = sorted({r["rule"] for r in sym})
    heat_syms = ["ETHUSDT", "BTCUSDT"]
    if sym and heat_rules:
        mat = np.zeros((len(heat_rules), len(heat_syms)))
        for i, rule in enumerate(heat_rules):
            for j, s in enumerate(heat_syms):
                row = next((r for r in sym if r["rule"] == rule and r["segment"] == s), {})
                mat[i, j] = row.get("expectancy") or 0
        im = ax4.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-2, vmax=3)
        ax4.set_xticks(range(len(heat_syms)))
        ax4.set_xticklabels(heat_syms, fontsize=8)
        ax4.set_yticks(range(len(heat_rules)))
        ax4.set_yticklabels(heat_rules, fontsize=7)
        ax4.set_title("Symbol Expectancy Heatmap")
        fig.colorbar(im, ax=ax4, fraction=0.046)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Rule Set Robustness")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building ruleset robustness analysis...")
    stats = full_robustness_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_ruleset_robustness.csv"), index=False)
    png = _plot(stats)

    champ = stats.get("champion", {})
    pf = stats.get("practical_pass_fail", {})

    lines = [
        "# REPORT_WAVE_RULESET_ROBUSTNESS",
        "",
        "Rule Set Robustness Validation",
        "",
        f"- events: {stats.get('event_count', 0)}",
        "",
        "## 1. 기본 성과",
        "",
        "| rule | n | win_rate | expectancy | profit_factor | payoff_ratio | avg_return | median_return | avg_survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in stats.get("baseline", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} | {_fmt(r.get('payoff_ratio'))} | "
            f"{_fmt(r.get('avg_return'))} | {_fmt(r.get('median_return'))} | "
            f"{_fmt(r.get('avg_survival'))} |"
        )
    lines.append("")

    lines.append("## 2. Walk Forward")
    lines.append("")
    lines.append("| rule | quarter | n | win_rate | expectancy | profit_factor |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("walk_forward", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('segment', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('profit_factor'))} |"
        )
    lines.append("")

    lines.append("## 3. Rolling Window")
    lines.append("")
    lines.append("| rule | n | windows | avg_exp | min_exp | max_exp | variance | neg_ratio |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in stats.get("rolling", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('n', 0)} | {r.get('window_count', '—')} | "
            f"{_fmt(r.get('avg_expectancy'))} | {_fmt(r.get('min_expectancy'))} | "
            f"{_fmt(r.get('max_expectancy'))} | {_fmt(r.get('expectancy_variance'))} | "
            f"{_fmt(r.get('negative_window_ratio'))} |"
        )
    lines.append("")

    lines.append("## 4. Exit Policy Stability")
    lines.append("")
    lines.append("| rule | policy | n | win_rate | expectancy | rank |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("exit_policy", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('segment', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} | "
            f"{r.get('policy_rank', '—')} |"
        )
    lines.append("")
    lines.append("| rule | exit_policy_sensitivity |")
    lines.append("|---|---:|")
    for r in stats.get("exit_sensitivity", []):
        lines.append(f"| {r.get('rule', '')} | {_fmt(r.get('exit_policy_sensitivity'))} |")
    lines.append("")

    lines.append("## 5. Symbol Robustness")
    lines.append("")
    lines.append("| rule | symbol | n | win_rate | expectancy |")
    lines.append("|---|---|---:|---:|---:|")
    for r in stats.get("symbol_robustness", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('segment', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")
    for rule, ratio in stats.get("symbol_positive_ratio", {}).items():
        lines.append(f"- {rule} symbol_positive_ratio: {_fmt(ratio * 100, pct=True)}")
    lines.append("")

    lines.append("## 6. Timeframe Robustness")
    lines.append("")
    lines.append("| rule | timeframe | n | win_rate | expectancy |")
    lines.append("|---|---|---:|---:|---:|")
    for r in stats.get("timeframe_robustness", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('segment', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")
    for rule, ratio in stats.get("timeframe_positive_ratio", {}).items():
        lines.append(f"- {rule} timeframe_positive_ratio: {_fmt(ratio * 100, pct=True)}")
    lines.append("")

    lines.append("## 7. Regime Robustness")
    lines.append("")
    lines.append("| rule | regime | n | win_rate | expectancy |")
    lines.append("|---|---|---:|---:|---:|")
    for r in stats.get("regime_robustness", []):
        if r.get("n", 0) > 0:
            lines.append(
                f"| {r.get('rule', '')} | {r.get('segment', '')} | {r.get('n', 0)} | "
                f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
            )
    lines.append("")
    for rule, ratio in stats.get("regime_positive_ratio", {}).items():
        lines.append(f"- {rule} regime_positive_ratio: {_fmt(ratio * 100, pct=True)}")
    lines.append("")

    lines.append("## 8. Robustness Score")
    lines.append("")
    lines.append("| rule | overall | walk | rolling | exit | symbol | tf | regime |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in stats.get("robustness_scores", []):
        lines.append(
            f"| {s.get('rule', '')} | {_fmt(s.get('robustness_score'))} | "
            f"{_fmt(s.get('score_walk_forward'))} | {_fmt(s.get('score_rolling'))} | "
            f"{_fmt(s.get('score_exit_stability'))} | {_fmt(s.get('score_symbol'))} | "
            f"{_fmt(s.get('score_timeframe'))} | {_fmt(s.get('score_regime'))} |"
        )
    lines.append("")

    base = champ.get("baseline", {})
    lines.append("## 9. Champion Rule")
    lines.append("")
    lines.append(
        f"**{champ.get('rule', '—')}** — robustness={_fmt(champ.get('robustness_score'))}, "
        f"n={base.get('n', 0)}, win_rate={_fmt(base.get('win_rate'), pct=True)}, "
        f"expectancy={_fmt(base.get('expectancy'))}"
    )
    lines.append("")

    lines.append("## 10. 실전 사용 가능성")
    lines.append("")
    lines.append(f"**{pf.get('result', 'FAIL')}**")
    lines.append("")
    lines.append(
        f"- robustness_score={_fmt(pf.get('robustness_score'))}, "
        f"expectancy={_fmt(pf.get('expectancy'))}, n={pf.get('n', 0)}"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_RULESET_ROBUSTNESS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave ruleset robustness sweep complete")


if __name__ == "__main__":
    main()
