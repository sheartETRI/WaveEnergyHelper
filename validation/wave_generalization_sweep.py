"""Wave Generalization 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_generalization import (
    GENERALIZATION_RULES,
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
    build_generalization,
    summarize_generalization,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "symbol", "timeframe", "rule", "count", "n", "win_rate",
    "expectancy", "profit_factor", "payoff_ratio", "avg_return", "avg_survival",
)


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v == 999.0:
        return "∞"
    return f"{v:.{d}f}"


def _plot(stats: dict, rows: list) -> str:
    path = os.path.join(OUT_DIR, "wave_generalization.png")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    rule_b = "RULE_B"
    hm = stats.get("heatmap_rules", {}).get(rule_b, {})
    ax = axes[0, 0]
    if hm:
        syms = list(GENERALIZATION_SYMBOLS)
        tfs = list(GENERALIZATION_TIMEFRAMES)
        data = np.array([
            [hm.get(s, {}).get(tf) if hm.get(s, {}).get(tf) is not None else np.nan for tf in tfs]
            for s in syms
        ], dtype=float)
        im = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=-3, vmax=3)
        ax.set_xticks(range(len(tfs)))
        ax.set_xticklabels(tfs)
        ax.set_yticks(range(len(syms)))
        ax.set_yticklabels(syms)
        ax.set_title(f"{rule_b} Expectancy Heatmap")
        for i in range(len(syms)):
            for j in range(len(tfs)):
                val = data[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046)
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    ranked = stats.get("top_rules", [])[:5]
    if ranked:
        labels = [r["rule"] for r in ranked]
        vals = [r.get("generalization_score") or 0 for r in ranked]
        y = np.arange(len(labels))
        ax2.barh(y, vals, color="#1565C0", alpha=0.85)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels)
        ax2.set_title("Generalization Score")
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1, 0]
    var_rows = stats.get("rule_variance", [])
    if var_rows:
        labels = [v["rule"] for v in var_rows]
        vals = [v.get("overall_variance") or 0 for v in var_rows]
        y = np.arange(len(labels))
        ax3.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax3.set_yticks(y)
        ax3.set_yticklabels(labels, fontsize=8)
        ax3.set_title("Variance Ranking (overall)")
        ax3.invert_yaxis()
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    pos_data = stats.get("rule_summary", [])
    if pos_data:
        labels = [p["rule"] for p in pos_data]
        vals = [p.get("positive_rate", 0) for p in pos_data]
        ax4.bar(range(len(labels)), vals, color="#2E7D32", alpha=0.85)
        ax4.set_xticks(range(len(labels)))
        ax4.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax4.set_ylabel("Positive Cell %")
        ax4.set_title("Positive Cell Ratio")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Generalization — 4 symbols × 3 timeframes")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building generalization matrix (12 cells)...")
    from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES, load_cell_confluence, evaluate_cell_rules

    all_rows = []
    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            print(f"  cell {sym} {tf}...", flush=True)
            conf = load_cell_confluence(sym, tf)
            all_rows.extend(evaluate_cell_rules(conf, sym, tf))
    from analysis.wave_generalization import aggregate_cells
    df = aggregate_cells(all_rows)
    rows = all_rows
    csv_path = os.path.join(OUT_DIR, "wave_generalization.csv")
    cols = [c for c in CSV_COLS if c in df.columns]
    df[cols].to_csv(csv_path, index=False)
    stats = summarize_generalization(rows)
    png = _plot(stats, rows)

    lines = [
        "# REPORT_WAVE_GENERALIZATION",
        "",
        "Candidate Rule Generalization — 4 symbols × 3 timeframes",
        "",
        f"- CSV: `wave_generalization.csv`",
        f"- PNG: `{os.path.basename(png)}`",
        f"- 총 셀: {stats['total_cells']}",
        "",
        "### Rule Summary",
        "",
        "| rule | positive cells | median expectancy |",
        "|---|---:|---:|",
    ]
    for r in stats.get("rule_summary", []):
        lines.append(
            f"| {r['rule']} | {r.get('positive_cells', 0)} | {_fmt(r.get('median_expectancy'))} |"
        )
    lines.append("")

    lines.append("### Rule Variance")
    lines.append("")
    lines.append("| rule | variance |")
    lines.append("|---|---:|")
    for v in stats.get("rule_variance", []):
        lines.append(f"| {v['rule']} | {_fmt(v.get('overall_variance'))} |")
    lines.append("")

    lines.append("### Top Cells")
    lines.append("")
    lines.append("| symbol | tf | rule | expectancy | n |")
    lines.append("|---|---|---|---:|---:|")
    for rule in GENERALIZATION_RULES:
        cell = stats.get("best_cells_per_rule", {}).get(rule)
        if cell:
            lines.append(
                f"| {cell['symbol']} | {cell['timeframe']} | {cell['rule']} | "
                f"{_fmt(cell.get('expectancy'))} | {cell.get('n', 0)} |"
            )
    lines.append("")

    lines.append("### Worst Cells")
    lines.append("")
    lines.append("| symbol | tf | rule | expectancy | n |")
    lines.append("|---|---|---|---:|---:|")
    for rule in GENERALIZATION_RULES:
        cell = stats.get("worst_cells_per_rule", {}).get(rule)
        if cell:
            lines.append(
                f"| {cell['symbol']} | {cell['timeframe']} | {cell['rule']} | "
                f"{_fmt(cell.get('expectancy'))} | {cell.get('n', 0)} |"
            )
    lines.append("")

    lines.append("### ETH / BTC / SOL / BNB 비교 (RULE_B)")
    lines.append("")
    lines.append("| symbol | data cells | positive | median exp |")
    lines.append("|---|---:|---:|---:|")
    for sym, cmp in stats.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('cells_with_data', 0)} | "
            f"{cmp.get('positive_cells', 0)} | {_fmt(cmp.get('median_expectancy'))} |"
        )
    lines.append("")

    lines.append("### 1h / 4h / 1d 비교 (RULE_B)")
    lines.append("")
    lines.append("| tf | data cells | positive | median exp |")
    lines.append("|---|---:|---:|---:|")
    for tf, cmp in stats.get("timeframe_comparison", {}).items():
        lines.append(
            f"| {tf} | {cmp.get('cells_with_data', 0)} | "
            f"{cmp.get('positive_cells', 0)} | {_fmt(cmp.get('median_expectancy'))} |"
        )
    lines.append("")

    rb = stats.get("rule_b_summary", {})
    lines.append(f"- Most General Rule: {stats.get('most_general_rule', {}).get('rule', '—')}")
    lines.append(f"- Least General Rule: {stats.get('least_general_rule', {}).get('rule', '—')}")
    lines.append(
        f"- RULE_B positive cells: {rb.get('positive_cells', 0)} / "
        f"{stats['total_cells']} (data cells: {rb.get('total_with_data', 0)})"
    )
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_GENERALIZATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave generalization sweep complete")


if __name__ == "__main__":
    main()
