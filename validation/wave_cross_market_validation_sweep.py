"""Wave Cross Market Validation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_cross_market_validation import RULE_IDS, full_cross_market_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_cross_market_validation.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    matrix = stats.get("matrix", [])
    rules = list(RULE_IDS)
    syms = sorted({r["symbol"] for r in matrix})
    tfs = ["4h"]

    ax = axes[0, 0]
    if matrix and syms:
        mat = np.zeros((len(rules), len(syms)))
        for i, rule in enumerate(rules):
            for j, sym in enumerate(syms):
                row = next(
                    (r for r in matrix if r["rule"] == rule and r["symbol"] == sym and r["timeframe"] == "4h"),
                    {},
                )
                mat[i, j] = row.get("expectancy") or 0
        im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-2, vmax=3)
        ax.set_xticks(range(len(syms)))
        ax.set_xticklabels([s.replace("USDT", "") for s in syms], fontsize=8)
        ax.set_yticks(range(len(rules)))
        ax.set_yticklabels(rules, fontsize=8)
        ax.set_title("Symbol x TF(4h) Expectancy Heatmap")
        fig.colorbar(im, ax=ax, fraction=0.046)
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    pr = stats.get("positive_cell_ratio", [])
    ax2 = axes[0, 1]
    if pr:
        labels = [r["rule"] for r in pr]
        vals = [r.get("positive_ratio", 0) * 100 for r in pr]
        ax2.bar(labels, vals, color="#2E7D32", alpha=0.85)
        ax2.set_ylim(0, 100)
        ax2.set_title("Positive Cell Ratio %")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    drift = stats.get("drift", [])
    ax3 = axes[1, 0]
    if drift:
        by_rule: dict = {}
        for d in drift:
            if d.get("expectancy_drift") is None:
                continue
            by_rule.setdefault(d["rule"], []).append(d["expectancy_drift"])
        labels = list(by_rule.keys())
        vals = [float(np.mean(by_rule[k])) for k in labels]
        colors = ["#2E7D32" if v >= 0 else "#C62828" for v in vals]
        ax3.bar(labels, vals, color=colors, alpha=0.85)
        ax3.axhline(0, color="gray", linewidth=0.8)
        ax3.set_title("Avg Train/Test Expectancy Drift")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    champ_data = []
    for rule in RULE_IDS:
        row = next((r for r in pr if r["rule"] == rule), {})
        surv = next((r for r in stats.get("rule_survival", []) if r["rule"] == rule), {})
        champ_data.append({
            "rule": rule,
            "score": (row.get("positive_ratio") or 0) * 100 + surv.get("survival_market_count", 0) * 5,
        })
    ax4 = axes[1, 1]
    if champ_data:
        labels = [c["rule"] for c in champ_data]
        vals = [c["score"] for c in champ_data]
        ax4.barh(labels, vals, color="#00838F", alpha=0.85)
        ax4.set_title("Champion Ranking (ratio + survival)")
        ax4.invert_yaxis()
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Cross Market Validation")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building cross market validation...")
    stats = full_cross_market_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_cross_market_validation.csv"), index=False)
    png = _plot(stats)

    champ = stats.get("champion_v2", {})
    verdict = stats.get("final_verdict", {})

    lines = [
        "# REPORT_WAVE_CROSS_MARKET_VALIDATION",
        "",
        "Cross Market Validation — Champion Rule 다시장 재현",
        "",
        f"- cells: {stats.get('cell_count', 0)}",
        "",
        "## 1. Cross Market Matrix",
        "",
        "| symbol | tf | rule | n | win_rate | expectancy |",
        "|---|---|---|---:|---:|---:|",
    ]
    for r in stats.get("matrix", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('timeframe', '')} | {r.get('rule', '')} | "
            f"{r.get('n', 0)} | {_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
        )
    lines.append("")

    lines.append("## 2. Positive Cell Ratio")
    lines.append("")
    lines.append("| rule | positive_cells | total_cells | positive_ratio |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("positive_cell_ratio", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('positive_cells', 0)} | "
            f"{r.get('total_cells', 0)} | {_fmt(r.get('positive_ratio', 0) * 100, pct=True)} |"
        )
    lines.append("")

    lines.append("## 3. Train/Test Split")
    lines.append("")
    lines.append("| rule | symbol | tf | dataset | n | win_rate | expectancy |")
    lines.append("|---|---|---|---|---:|---:|---:|")
    for r in stats.get("train_test", []):
        if r.get("n", 0) > 0:
            lines.append(
                f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
                f"{r.get('dataset', '')} | {r.get('n', 0)} | "
                f"{_fmt(r.get('win_rate'), pct=True)} | {_fmt(r.get('expectancy'))} |"
            )
    lines.append("")

    lines.append("## 4. Drift Analysis")
    lines.append("")
    lines.append("| rule | symbol | tf | train_exp | test_exp | exp_drift | wr_drift |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in stats.get("drift", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
            f"{_fmt(r.get('train_expectancy'))} | {_fmt(r.get('test_expectancy'))} | "
            f"{_fmt(r.get('expectancy_drift'))} | {_fmt(r.get('win_rate_drift'), pct=True)} |"
        )
    lines.append("")

    lines.append("## 5. Symbol Independence")
    lines.append("")
    lines.append("| rule | scope | cells | positive | mean_exp | positive_ratio |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_independence", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('scope', '')} | {r.get('cells', 0)} | "
            f"{r.get('positive_cells', 0)} | {_fmt(r.get('mean_expectancy'))} | "
            f"{_fmt(r.get('positive_ratio', 0) * 100, pct=True)} |"
        )
    lines.append("")

    lines.append("## 6. Timeframe Robustness")
    lines.append("")
    lines.append("| rule | timeframe | n | expectancy |")
    lines.append("|---|---|---:|---:|")
    for r in stats.get("timeframe_robustness", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('timeframe', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('expectancy'))} |"
        )
    lines.append("")

    lines.append("## 7. Rule Survival")
    lines.append("")
    for r in stats.get("rule_survival", []):
        markets = ", ".join(r.get("markets", []))
        lines.append(
            f"- **{r.get('rule', '')}**: survival_market_count={r.get('survival_market_count', 0)} "
            f"({markets or '—'})"
        )
    lines.append("")

    lines.append("## 8. Champion Rule v2")
    lines.append("")
    lines.append(
        f"**{champ.get('rule', '—')}** — test_exp_avg={_fmt(champ.get('test_expectancy_avg'))}, "
        f"positive_ratio={_fmt((champ.get('positive_ratio') or 0) * 100, pct=True)}, "
        f"survival={champ.get('survival_market_count', 0)}, variance={_fmt(champ.get('variance'))}"
    )
    lines.append("")

    lines.append("## 9. Overfitting Risk")
    lines.append("")
    lines.append("| rule | total_n | cells | positive_ratio | avg_drift | variance | risk |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for r in stats.get("overfitting_risk", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('total_n', 0)} | {r.get('cell_count', 0)} | "
            f"{_fmt(r.get('positive_ratio', 0) * 100, pct=True)} | {_fmt(r.get('avg_drift'))} | "
            f"{_fmt(r.get('variance'))} | {r.get('risk', '')} |"
        )
    lines.append("")

    lines.append("## 10. 최종 결론")
    lines.append("")
    lines.append(f"**{verdict.get('result', 'FAIL')}** — Champion: {verdict.get('champion', '—')}")
    lines.append("")
    lines.append(f"- ETH 특화: {'YES' if verdict.get('eth_specific') else 'NO'}")
    lines.append(f"- 다시장 재현: {'YES' if verdict.get('multi_market') else 'NO'}")
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_CROSS_MARKET_VALIDATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("cross market validation sweep complete")


if __name__ == "__main__":
    main()
