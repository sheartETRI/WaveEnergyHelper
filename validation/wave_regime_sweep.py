"""Wave Regime 스윕 · REPORT."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_analysis import (
    REGIME_NUMERIC,
    REGIME_RULES,
    build_full_regime_report,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2):
    if v is None:
        return "—"
    return f"{v:.{d}f}"


def main():
    print("building regime analysis...")
    report = build_full_regime_report()
    primary = report["primary"]

    lines = [
        "# REPORT_WAVE_REGIME",
        "",
        "Timeframe Regime Analysis — Rule이 동작하는 시장 구조",
        "",
        f"- 분석 Rule: {', '.join(REGIME_RULES)}",
        f"- RULE_B 셀: {primary.get('count', 0)} "
        f"(success {primary.get('success_cell_count', 0)}, "
        f"failure {primary.get('failure_cell_count', 0)})",
        "",
        "## 4h vs 1d 차이 (RULE_B)",
        "",
        "| feature | 4h avg | 1d avg | effect_size |",
        "|---|---:|---:|---:|",
    ]
    for s in primary.get("separators_4h_vs_1d", [])[:15]:
        lines.append(
            f"| {s['feature']} | {_fmt(s.get('avg_4h'))} | "
            f"{_fmt(s.get('avg_1d'))} | {_fmt(s.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## Top Regime Separators (success vs failure cells, RULE_B)")
    lines.append("")
    lines.append("| feature | success avg | failure avg | effect_size |")
    lines.append("|---|---:|---:|---:|")
    for s in primary.get("separators", [])[:20]:
        lines.append(
            f"| {s['feature']} | {_fmt(s.get('success_avg'))} | "
            f"{_fmt(s.get('failure_avg'))} | {_fmt(s.get('effect_size'))} |"
        )
    lines.append("")

    lines.append("## Timeframe Regime Profile (RULE_B cells)")
    lines.append("")
    header = "| feature | " + " | ".join(["1h", "4h", "1d"]) + " |"
    lines.append(header)
    lines.append("|" + "---|" * 4)
    tf_prof = primary.get("timeframe_profile", [])
    tf_map = {r["timeframe"]: r for _, r in tf_prof.iterrows()} if hasattr(tf_prof, "iterrows") else {}
    for feat in REGIME_NUMERIC:
        vals = [_fmt(tf_map.get(tf, {}).get(feat)) for tf in ("1h", "4h", "1d")]
        lines.append(f"| {feat} | {' | '.join(vals)} |")
    lines.append("")

    lines.append("## Regime Clusters (RULE_B events)")
    lines.append("")
    lines.append("| cluster | n | win% | expectancy |")
    lines.append("|---|---:|---:|---:|")
    for c in primary.get("clusters", []):
        lines.append(
            f"| {c['cluster']} | {c['n']} | {_fmt(c.get('win_rate'))} | "
            f"{_fmt(c.get('expectancy'))} |"
        )
    lines.append("")

    bc = primary.get("best_cluster", {})
    wc = primary.get("worst_cluster", {})
    lines.append(f"- Best Cluster: {bc.get('cluster', '—')} (exp {_fmt(bc.get('expectancy'))})")
    lines.append(f"- Worst Cluster: {wc.get('cluster', '—')} (exp {_fmt(wc.get('expectancy'))})")
    lines.append("")

    lines.append("## ETH / BTC / SOL / BNB (RULE_B)")
    lines.append("")
    lines.append("| symbol | cells | success | avg exp | avg ATR% | avg major_k |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for sym, cmp in primary.get("symbol_comparison", {}).items():
        lines.append(
            f"| {sym} | {cmp.get('cells', 0)} | {cmp.get('success_cells', 0)} | "
            f"{_fmt(cmp.get('avg_expectancy'))} | {_fmt(cmp.get('avg_atr_pct'))} | "
            f"{_fmt(cmp.get('avg_major_k'))} |"
        )
    lines.append("")

    lines.append("## Rule Comparison")
    lines.append("")
    lines.append("| rule | cells | success | top separator |")
    lines.append("|---|---:|---:|---|")
    for rule in REGIME_RULES:
        st = report["by_rule"].get(rule, {})
        top = st.get("separators", [{}])[0] if st.get("separators") else {}
        lines.append(
            f"| {rule} | {st.get('count', 0)} | {st.get('success_cell_count', 0)} | "
            f"{top.get('feature', '—')} ({_fmt(top.get('effect_size'))}) |"
        )
    lines.append("")

    path = os.path.join(OUT_DIR, "REPORT_WAVE_REGIME.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave regime sweep complete")


if __name__ == "__main__":
    main()
