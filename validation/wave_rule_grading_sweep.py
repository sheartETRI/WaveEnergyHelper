"""Wave Rule Grading 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_rule_grading import (
    ALL_SYMBOL,
    ALL_TIMEFRAME,
    GRADE_ORDER,
    full_rule_grading_summary,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_COLS = (
    "grade", "symbol", "timeframe", "count", "win_rate", "expectancy",
    "profit_factor", "avg_return", "avg_survival", "robustness_gap",
)


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v == 999.0:
        return "∞"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_rule_grading.png")
    summary = stats.get("summary", {})
    stability = stats.get("stability", {})

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    grades = list(GRADE_ORDER)
    x = np.arange(len(grades))

    ax = axes[0, 0]
    wr = [summary.get(g, {}).get("win_rate") or 0 for g in grades]
    ax.bar(x, wr, color="#1565C0", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(grades)
    ax.set_title("Grade vs Win Rate (%)")
    ax.set_ylabel("win_rate")

    ax2 = axes[0, 1]
    exp = [summary.get(g, {}).get("expectancy") or 0 for g in grades]
    ax2.bar(x, exp, color="#6A1B9A", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels(grades)
    ax2.axhline(0, color="gray", ls="--", lw=0.8)
    ax2.set_title("Grade vs Expectancy (%)")
    ax2.set_ylabel("expectancy")

    ax3 = axes[1, 0]
    pf = [summary.get(g, {}).get("profit_factor") or 0 for g in grades]
    pf = [min(v, 20) for v in pf]
    ax3.bar(x, pf, color="#2E7D32", alpha=0.85)
    ax3.set_xticks(x)
    ax3.set_xticklabels(grades)
    ax3.set_title("Grade vs Profit Factor")
    ax3.set_ylabel("PF")

    ax4 = axes[1, 1]
    rob = [stability.get(g, {}).get("robustness_gap") or 0 for g in grades]
    ax4.bar(x, rob, color="#E65100", alpha=0.85)
    ax4.set_xticks(x)
    ax4.set_xticklabels(grades)
    ax4.set_title("Grade vs Robustness Gap (lower=better)")
    ax4.set_ylabel("robustness_gap")

    fig.suptitle("Wave Rule Grading — A/B/C/D Confidence Tiers")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    print("building rule grading analysis...")
    stats = full_rule_grading_summary()
    df = stats.get("dataframe")
    if df is not None and not df.empty:
        cols = [c for c in CSV_COLS if c in df.columns]
        df[cols].to_csv(os.path.join(OUT_DIR, "wave_rule_grading.csv"), index=False)
    png = _plot(stats)

    summary = stats.get("summary", {})
    mono = stats.get("monotonicity", {})
    lines = [
        "# REPORT_WAVE_RULE_GRADING",
        "",
        "Rule Confidence Grading — BASE_RULE A/B/C/D",
        "",
        "## Grade Summary",
        "",
        "| grade | count | win_rate | expectancy | PF | payoff | avg_return | median_return | avg_survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for g in GRADE_ORDER:
        s = summary.get(g, {})
        lines.append(
            f"| {g} | {s.get('n', 0)} | {_fmt(s.get('win_rate'))} | "
            f"{_fmt(s.get('expectancy'))} | {_fmt(s.get('profit_factor'))} | "
            f"{_fmt(s.get('payoff_ratio'))} | {_fmt(s.get('avg_return'))} | "
            f"{_fmt(s.get('median_return'))} | {_fmt(s.get('avg_survival'))} |"
        )
    lines.append("")

    lines.append("## Grade Separation")
    lines.append("")
    lines.append("| comparison | Δexpectancy | Δwin_rate | ΔPF |")
    lines.append("|---|---:|---:|---:|")
    for r in stats.get("separation", []):
        lines.append(
            f"| {r.get('comparison', '')} | {_fmt(r.get('delta_expectancy'))} | "
            f"{_fmt(r.get('delta_win_rate'))} | {_fmt(r.get('delta_profit_factor'))} |"
        )
    lines.append("")

    lines.append("## Monotonicity Test")
    lines.append("")
    lines.append(f"- result: **{mono.get('result', 'FAIL')}**")
    lines.append("")
    lines.append("| metric | A | B | C | D | pass |")
    lines.append("|---|---:|---:|---:|---:|:---:|")
    for metric, detail in mono.get("details", {}).items():
        vals = detail.get("values", {})
        ok = "PASS" if detail.get("pass") else "FAIL"
        lines.append(
            f"| {metric} | {_fmt(vals.get('A'))} | {_fmt(vals.get('B'))} | "
            f"{_fmt(vals.get('C'))} | {_fmt(vals.get('D'))} | {ok} |"
        )
    lines.append("")

    lines.append("## Calibration")
    lines.append("")
    lines.append("| grade | actual win |")
    lines.append("|---|---:|")
    for r in stats.get("calibration", []):
        lines.append(f"| {r.get('grade', '')} | {_fmt(r.get('actual_win'))}% |")
    lines.append("")

    lines.append("## Robustness")
    lines.append("")
    lines.append("| grade | 1st half exp | 2nd half exp | robustness_gap |")
    lines.append("|---|---:|---:|---:|")
    for g in GRADE_ORDER:
        st = stats.get("stability", {}).get(g, {})
        lines.append(
            f"| {g} | {_fmt(st.get('first_half_expectancy'))} | "
            f"{_fmt(st.get('second_half_expectancy'))} | {_fmt(st.get('robustness_gap'))} |"
        )
    lines.append("")

    lines.append("## Cross Market")
    lines.append("")
    lines.append("| grade | symbol | expectancy | n |")
    lines.append("|---|---|---:|---:|")
    for r in stats.get("cross_market", []):
        lines.append(
            f"| {r.get('grade', '')} | {r.get('symbol', '')} | "
            f"{_fmt(r.get('expectancy'))} | {r.get('n', 0)} |"
        )
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB 비교")
    lines.append("")
    lines.append("| grade | ETH | BTC | SOL | BNB |")
    lines.append("|---|---:|---:|---:|---:|")
    cross = stats.get("cross_market", [])
    sym_map = {"ETHUSDT": "ETH", "BTCUSDT": "BTC", "SOLUSDT": "SOL", "BNBUSDT": "BNB"}
    for g in GRADE_ORDER:
        cells = []
        for sym in ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT"):
            row = next((r for r in cross if r["grade"] == g and r["symbol"] == sym), None)
            cells.append(_fmt(row.get("expectancy")) if row else "—")
        lines.append(f"| {g} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    lines.append("")

    lines.append(f"- Recommended Grade: **{stats.get('recommended_grade', '—')}**")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_RULE_GRADING.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave rule grading sweep complete")


if __name__ == "__main__":
    main()
