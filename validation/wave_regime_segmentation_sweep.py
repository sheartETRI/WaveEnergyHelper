"""Wave Regime Segmentation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_segmentation import REGIME_DEFINITION, full_regime_segmentation_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_regime_segmentation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    rr = stats.get("rule_regime", [])
    ax = axes[0, 0]
    if rr:
        rules = sorted({r["rule"] for r in rr})
        regimes = ["BULL", "BEAR", "SIDEWAYS"]
        mat = np.zeros((len(rules), len(regimes)))
        for r in rr:
            ri = rules.index(r["rule"])
            gi = regimes.index(r["regime"])
            mat[ri, gi] = r.get("avg_return_20") or 0
        im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-3, vmax=3)
        ax.set_xticks(range(len(regimes)))
        ax.set_xticklabels(regimes)
        ax.set_yticks(range(len(rules)))
        ax.set_yticklabels(rules)
        ax.set_title("Rule × Regime avg20")
        fig.colorbar(im, ax=ax, fraction=0.046)

    sr = stats.get("symbol_regime", [])
    ax2 = axes[0, 1]
    if sr:
        syms = ["BNB", "BTC", "ETH", "SOL"]
        sym_map = {f"{s}USDT": i for i, s in enumerate(["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"])}
        regimes = ["BULL", "BEAR", "SIDEWAYS"]
        mat = np.zeros((len(syms), len(regimes)))
        for r in sr:
            si = sym_map.get(r["symbol"])
            gi = regimes.index(r["regime"])
            if si is not None:
                mat[si, gi] = r.get("avg_return_20") or 0
        im2 = ax2.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-3, vmax=3)
        ax2.set_xticks(range(len(regimes)))
        ax2.set_xticklabels(regimes)
        ax2.set_yticks(range(len(syms)))
        ax2.set_yticklabels(syms)
        ax2.set_title("Symbol × Regime avg20")
        fig.colorbar(im2, ax=ax2, fraction=0.046)

    champ = stats.get("champion_avg20", [])[:10]
    ax3 = axes[0, 2]
    if champ:
        labels = [f"{c['symbol'][:3]}/{c['regime'][:4]}" for c in champ]
        vals = [c.get("avg_return_20") or 0 for c in champ]
        ax3.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
        ax3.set_yticks(range(len(labels)))
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.invert_yaxis()
        ax3.set_title("Champion Regime Cells")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    contrib = stats.get("contribution", [])
    ax4 = axes[1, 0]
    if contrib:
        labels, vals = [], []
        for c in contrib:
            if c.get("rule") == "RULE":
                labels.append("Rule")
                vals.append(c.get("rule_contribution") or 0)
            elif c.get("rule") == "SYMBOL":
                labels.append("Symbol")
                vals.append(c.get("symbol_contribution") or 0)
            elif c.get("rule") == "REGIME":
                labels.append("Regime")
                vals.append(c.get("regime_contribution") or 0)
            elif c.get("rule") == "RESIDUAL":
                labels.append("Residual")
                vals.append(c.get("residual") or 0)
        ax4.bar(labels, vals, color=["#1565C0", "#E65100", "#2E7D32", "#9E9E9E"], alpha=0.85)
        ax4.set_title("Contribution (SS %)")
        ax4.tick_params(axis="x", rotation=20)

    pos = stats.get("positive_ratio", [])
    ax5 = axes[1, 1]
    if pos:
        rules = [p["rule"] for p in pos]
        vals = [p.get("positive_regime_ratio") or 0 for p in pos]
        ax5.bar(rules, vals, color="#6A1B9A", alpha=0.85)
        ax5.set_title("Positive Regime Ratio (%)")
        ax5.set_ylim(0, 100)

    active = stats.get("active_candidates", [])[:8]
    ax6 = axes[1, 2]
    if active:
        labels = [f"{a['symbol'][:3]}/{a['regime'][:4]}" for a in active]
        vals = [a.get("historical_avg20_in_regime") or 0 for a in active]
        ax6.barh(range(len(labels)), vals, color="#2E7D32", alpha=0.85)
        ax6.set_yticks(range(len(labels)))
        ax6.set_yticklabels(labels, fontsize=7)
        ax6.invert_yaxis()
        ax6.axvline(0, color="gray", linewidth=0.8)
        ax6.set_title("Active hist avg20 in regime")
    else:
        ax6.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Regime Segmentation")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# REPORT — Wave Regime Segmentation",
        "",
        "## Regime 정의",
        "",
        REGIME_DEFINITION,
        "",
        "## 1. Rule × Regime 성과",
        "",
        "| rule | regime | n | completed | wr20 | avg20 | exp20 | avg40 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in stats.get("rule_regime", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('regime', '')} | {r.get('n', 0)} | "
            f"{r.get('completed_n', 0)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | {_fmt(r.get('expectancy_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 2. Symbol × Regime 성과", ""])
    lines.append("| symbol | regime | n | wr20 | avg20 | avg40 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in stats.get("symbol_regime", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('regime', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate_20'), pct=True)} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 3. Rule × Symbol × Regime (sample)", ""])
    lines.append("| rule | symbol | regime | n | wr20 | avg20 | exp20 |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in stats.get("rule_symbol_regime", [])[:36]:
        lines.append(
            f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('regime', '')} | "
            f"{r.get('n', 0)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | {_fmt(r.get('expectancy_20'), pct=True)} |"
        )

    lines.extend(["", "## 4. Champion Regime (avg20 Top 20)", ""])
    lines.append("| rank | rule | symbol | regime | n | avg20 |")
    lines.append("|---:|---|---|---|---:|---:|")
    for c in stats.get("champion_avg20", [])[:20]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('rule', '')} | {c.get('symbol', '')} | "
            f"{c.get('regime', '')} | {c.get('n', 0)} | {_fmt(c.get('avg_return_20'), pct=True)} |"
        )

    lines.extend(["", "## 5. Worst Regime (avg20 Bottom 20)", ""])
    lines.append("| rank | rule | symbol | regime | n | avg20 |")
    lines.append("|---:|---|---|---|---:|---:|")
    for c in stats.get("worst_cells", [])[:20]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('rule', '')} | {c.get('symbol', '')} | "
            f"{c.get('regime', '')} | {c.get('n', 0)} | {_fmt(c.get('avg_return_20'), pct=True)} |"
        )

    lines.extend(["", "## 6. Positive Regime Ratio", ""])
    lines.append("| rule | regime_ratio | cell_ratio | symbol_ratio | signs |")
    lines.append("|---|---:|---:|---:|---|")
    for p in stats.get("positive_ratio", []):
        lines.append(
            f"| {p.get('rule', '')} | {_fmt(p.get('positive_regime_ratio'), pct=True)} | "
            f"{_fmt(p.get('positive_cell_ratio'), pct=True)} | "
            f"{_fmt(p.get('positive_symbol_ratio'), pct=True)} | {p.get('regime_signs', '')} |"
        )

    lines.extend(["", "## 7. Failure Cause × Regime", ""])
    lines.append("| regime | n | STRUCTURE | MF_DROP | SL3 |")
    lines.append("|---|---:|---:|---:|---:|")
    for f in stats.get("failure_regime", []):
        lines.append(
            f"| {f.get('regime', '')} | {f.get('n', 0)} | "
            f"{_fmt(f.get('structure_fail_pct'), pct=True)} | "
            f"{_fmt(f.get('money_flow_drop_pct'), pct=True)} | "
            f"{_fmt(f.get('stop_loss_3_pct'), pct=True)} |"
        )

    lines.extend(["", "## 8. Contribution 분석 (SS %)", ""])
    prev_rule, prev_sym = 0.03, 1.89
    lines.append(f"- 이전 (Symbol Seg #19): Rule {_fmt(prev_rule, pct=True)}, Symbol {_fmt(prev_sym, pct=True)}")
    for c in stats.get("contribution", []):
        label = c.get("rule", "")
        if label == "RULE":
            lines.append(f"- **Rule**: {_fmt(c.get('rule_contribution'), pct=True)}")
        elif label == "SYMBOL":
            lines.append(f"- **Symbol**: {_fmt(c.get('symbol_contribution'), pct=True)}")
        elif label == "REGIME":
            lines.append(f"- **Regime**: {_fmt(c.get('regime_contribution'), pct=True)}")
        elif label == "RESIDUAL":
            lines.append(f"- **Residual**: {_fmt(c.get('residual'), pct=True)}")

    lines.extend(["", "## 9. Active Candidate Regime Overlay", ""])
    lines.append("| rank | symbol | tf | rule | regime | hist20_regime | exp20_regime | score |")
    lines.append("|---:|---|---|---|---|---:|---:|---:|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('regime_rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {a.get('regime', '')} | "
            f"{_fmt(a.get('historical_avg20_in_regime'), pct=True)} | "
            f"{_fmt(a.get('historical_expectancy20_in_regime'), pct=True)} | "
            f"{_fmt(a.get('watchlist_score'))} |"
        )

    lines.extend(["", "## 10. 현재 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"regime={p.get('regime')} hist20={_fmt(p.get('historical_avg20_in_regime'), pct=True)}"
        )

    contrib_map = {c.get("rule"): c for c in stats.get("contribution", [])}
    reg_c = contrib_map.get("REGIME", {}).get("regime_contribution", 0)
    sym_c = contrib_map.get("SYMBOL", {}).get("symbol_contribution", 0)
    rule_c = contrib_map.get("RULE", {}).get("rule_contribution", 0)

    lines.extend(["", "## 11. 핵심 결론", ""])
    if reg_c > max(rule_c, sym_c):
        verdict = "Regime 효과가 Rule/Symbol보다 큼 — 특정 시장 상태에서만 유효"
    elif sym_c > rule_c:
        verdict = "Symbol 효과 > Regime > Rule — BNB + 특정 Regime 조합 주목"
    else:
        verdict = "Rule 효과 미미, Regime/Symbol 교차 검증 필요"
    lines.append(f"**{verdict}**")
    rb = next((p for p in stats.get("positive_ratio", []) if p.get("rule") == "RULE_B"), {})
    lines.append(
        f"- RULE_B Positive Regime Ratio: {_fmt(rb.get('positive_regime_ratio'), pct=True)} "
        f"({rb.get('regime_signs', '')})"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_REGIME_SEGMENTATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building regime segmentation analysis...")
    stats = full_regime_segmentation_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_regime_segmentation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_regime_segmentation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("regime segmentation sweep complete")


if __name__ == "__main__":
    main()
