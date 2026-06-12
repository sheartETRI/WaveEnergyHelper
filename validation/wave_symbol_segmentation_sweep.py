"""Wave Symbol Segmentation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_symbol_segmentation import full_symbol_segmentation_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_symbol_segmentation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    rs = stats.get("rule_symbol", [])
    ax = axes[0, 0]
    if rs:
        rules = sorted({r["rule"] for r in rs})
        syms = ["BNB", "BTC", "ETH", "SOL"]
        sym_map = {f"{s}USDT": i for i, s in enumerate(["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"])}
        mat = np.zeros((len(rules), len(syms)))
        for r in rs:
            ri = rules.index(r["rule"])
            si = sym_map.get(r["symbol"])
            if si is not None:
                mat[ri, si] = r.get("avg_return_20") or 0
        im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-2, vmax=2)
        ax.set_xticks(range(len(syms)))
        ax.set_xticklabels(syms)
        ax.set_yticks(range(len(rules)))
        ax.set_yticklabels(rules)
        ax.set_title("Rule × Symbol avg20")
        fig.colorbar(im, ax=ax, fraction=0.046)

    rtf = stats.get("rule_symbol_tf", [])
    ax2 = axes[0, 1]
    if rtf:
        labels = [f"{r['symbol'][:3]}/{r['timeframe']}\n{r['rule'][-1]}" for r in rtf[:15]]
        vals = [r.get("avg_return_20") or 0 for r in rtf[:15]]
        colors = ["#2E7D32" if v > 0 else "#C62828" for v in vals]
        ax2.barh(range(len(labels)), vals, color=colors, alpha=0.85)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(labels, fontsize=6)
        ax2.invert_yaxis()
        ax2.axvline(0, color="gray", linewidth=0.8)
        ax2.set_title("Rule×Symbol×TF (sample)")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    champ = stats.get("champion_avg20", [])[:10]
    ax3 = axes[0, 2]
    if champ:
        labels = [f"{c['symbol'][:3]}/{c['timeframe']}" for c in champ]
        vals = [c.get("avg_return_20") or 0 for c in champ]
        ax3.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
        ax3.set_yticks(range(len(labels)))
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.invert_yaxis()
        ax3.set_title("Champion Cells (avg20)")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    robust = stats.get("robustness", [])
    ax4 = axes[1, 0]
    if robust:
        rules = [r["rule"] for r in robust]
        cell_r = [r.get("positive_cell_ratio") or 0 for r in robust]
        sym_r = [r.get("positive_symbol_ratio") or 0 for r in robust]
        x = np.arange(len(rules))
        ax4.bar(x - 0.15, cell_r, 0.3, label="Cell %", color="#6A1B9A")
        ax4.bar(x + 0.15, sym_r, 0.3, label="Symbol %", color="#E65100")
        ax4.set_xticks(x)
        ax4.set_xticklabels(rules)
        ax4.set_title("Positive Cell / Symbol Ratio")
        ax4.legend(fontsize=7)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    contrib = stats.get("contribution", [])
    ax5 = axes[1, 1]
    if contrib:
        labels = [c.get("rule", "") for c in contrib if c.get("rule") != "RESIDUAL"]
        vals = [c.get("value") or 0 for c in contrib if c.get("rule") != "RESIDUAL"]
        ax5.pie(vals, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 8})
        ax5.set_title("Rule vs Symbol Contribution")
    else:
        ax5.text(0.5, 0.5, "no data", ha="center")

    active = stats.get("active_candidates", [])[:8]
    ax6 = axes[1, 2]
    if active:
        labels = [f"{a['symbol'][:3]}/{a['timeframe']}" for a in active]
        hist = [a.get("historical_avg20") or 0 for a in active]
        ax6.barh(range(len(labels)), hist, color="#2E7D32", alpha=0.85)
        ax6.set_yticks(range(len(labels)))
        ax6.set_yticklabels(labels, fontsize=7)
        ax6.invert_yaxis()
        ax6.axvline(0, color="gray", linewidth=0.8)
        ax6.set_title("Active Candidate hist avg20")
    else:
        ax6.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Symbol Segmentation — Rule vs Symbol")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# REPORT — Wave Symbol Segmentation",
        "",
        f"분석 Symbol: {', '.join(stats.get('available_symbols', []))}",
        "",
        "## 1. Rule × Symbol 성과",
        "",
        "| rule | symbol | n | completed | wr20 | avg20 | exp20 | avg40 | exp40 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in stats.get("rule_symbol", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('n', 0)} | "
            f"{r.get('completed_n', 0)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | {_fmt(r.get('expectancy_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} | {_fmt(r.get('expectancy_40'), pct=True)} |"
        )

    lines.extend(["", "## 2. Rule × Symbol × TF 성과", ""])
    lines.append("| rule | symbol | tf | n | wr20 | avg20 | avg40 |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in stats.get("rule_symbol_tf", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
            f"{r.get('n', 0)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | {_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 3. Champion Cells (avg20 Top 10)", ""])
    lines.append("| rank | rule | symbol | tf | n | avg20 | exp20 |")
    lines.append("|---:|---|---|---|---:|---:|---:|")
    for c in stats.get("champion_avg20", [])[:10]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('rule', '')} | {c.get('symbol', '')} | "
            f"{c.get('timeframe', '')} | {c.get('n', 0)} | "
            f"{_fmt(c.get('avg_return_20'), pct=True)} | {_fmt(c.get('expectancy_20'), pct=True)} |"
        )

    lines.extend(["", "## 4. Worst Cells (avg20 Bottom 10)", ""])
    lines.append("| rank | rule | symbol | tf | n | avg20 |")
    lines.append("|---:|---|---|---|---:|---:|")
    for c in stats.get("worst_cells", [])[:10]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('rule', '')} | {c.get('symbol', '')} | "
            f"{c.get('timeframe', '')} | {c.get('n', 0)} | {_fmt(c.get('avg_return_20'), pct=True)} |"
        )

    lines.extend(["", "## 5. Failure Cause 분포 (Rule × Symbol)", ""])
    lines.append("| rule | symbol | n | STRUCTURE | MF_DROP | SL3 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for f in stats.get("failure_causes", []):
        lines.append(
            f"| {f.get('rule', '')} | {f.get('symbol', '')} | {f.get('n', 0)} | "
            f"{_fmt(f.get('structure_fail_pct'), pct=True)} | "
            f"{_fmt(f.get('money_flow_drop_pct'), pct=True)} | "
            f"{_fmt(f.get('stop_loss_3_pct'), pct=True)} |"
        )

    lines.extend(["", "## 6. Positive Cell / Symbol Ratio", ""])
    lines.append("| rule | cell_ratio | symbol_ratio | signs |")
    lines.append("|---|---:|---:|---|")
    for r in stats.get("robustness", []):
        lines.append(
            f"| {r.get('rule', '')} | {_fmt(r.get('positive_cell_ratio'), pct=True)} | "
            f"{_fmt(r.get('positive_symbol_ratio'), pct=True)} | {r.get('symbol_signs', '')} |"
        )

    lines.extend(["", "## 7. Variance 분해", ""])
    lines.append("**Within Rule Variance (symbol 간)**")
    for v in stats.get("within_rule_variance", []):
        lines.append(f"- {v.get('rule')}: { _fmt(v.get('value'))}")
    lines.append("")
    lines.append("**Within Symbol Variance (rule 간)**")
    for v in stats.get("within_symbol_variance", []):
        lines.append(f"- {v.get('symbol')}: {_fmt(v.get('value'))}")

    lines.extend(["", "## 8. Rule / Symbol Contribution (SS %)", ""])
    for c in stats.get("contribution", []):
        lines.append(f"- **{c.get('rule')}**: {_fmt(c.get('value'), pct=True)}")

    lines.extend(["", "## 9. Active Candidate 재평가 (hist avg20 기준)", ""])
    lines.append("| rank | symbol | tf | rule | hist_avg20 | hist_exp20 | watchlist | freshness |")
    lines.append("|---:|---|---|---|---:|---:|---:|---|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('current_rank', a.get('rank', ''))} | {a.get('symbol', '')} | "
            f"{a.get('timeframe', '')} | {a.get('rule', '')} | "
            f"{_fmt(a.get('historical_avg20'), pct=True)} | {_fmt(a.get('historical_expectancy20'), pct=True)} | "
            f"{_fmt(a.get('watchlist_score'))} | {a.get('freshness', '')} |"
        )

    lines.extend(["", "## 10. 현재 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"hist20={_fmt(p.get('historical_avg20'), pct=True)} score={_fmt(p.get('watchlist_score'))}"
        )

    lines.extend(["", "## 11. 핵심 결론", ""])
    contrib = {c.get("rule"): c.get("value") for c in stats.get("contribution", [])}
    rule_c = contrib.get("RULE", 0)
    sym_c = contrib.get("SYMBOL", 0)
    rb = next((r for r in stats.get("robustness", []) if r.get("rule") == "RULE_B"), {})
    if sym_c > rule_c:
        verdict = "Symbol 효과가 Rule 효과보다 큼 — RULE_B 성과는 BNB 등 특정 Symbol 착시 가능성 높음"
    else:
        verdict = "Rule 효과가 Symbol 효과보다 큼 — Rule 자체 기여 우세"
    lines.append(f"**{verdict}**")
    lines.append(
        f"- Contribution: Rule {_fmt(rule_c, pct=True)} vs Symbol {_fmt(sym_c, pct=True)}"
    )
    lines.append(
        f"- RULE_B Positive Symbol Ratio: {_fmt(rb.get('positive_symbol_ratio'), pct=True)} "
        f"({rb.get('symbol_signs', '')})"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_SYMBOL_SEGMENTATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building symbol segmentation analysis...")
    stats = full_symbol_segmentation_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_symbol_segmentation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_symbol_segmentation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("symbol segmentation sweep complete")


if __name__ == "__main__":
    main()
