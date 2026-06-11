"""Wave Candidate Rules 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_candidate_rules import (
    build_candidate_rules,
    enrich_confluence_events,
    summarize_candidate_rules,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS = [("ETHUSDT", "4h"), ("BTCUSDT", "1d")]


def _fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v == 999.0:
        return "∞"
    return f"{v:.{d}f}"


def _plot(stats: dict, symbol: str, interval: str) -> str:
    path = os.path.join(OUT_DIR, f"wave_candidate_rules_{symbol}_{interval}.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    ranked = stats.get("top_rules", stats.get("rule_performance", []))[:8]

    ax = axes[0, 0]
    if ranked:
        labels = [r["rule"] for r in ranked]
        vals = [r.get("stability_score") or 0 for r in ranked]
        y = np.arange(len(labels))
        ax.barh(y, vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_title("Rule Ranking (Stability)")
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    ax2 = axes[0, 1]
    if ranked:
        labels = [r["rule"] for r in ranked]
        vals = [r.get("expectancy") or 0 for r in ranked]
        y = np.arange(len(labels))
        ax2.barh(y, vals, color="#6A1B9A", alpha=0.85)
        ax2.axvline(0, color="gray", ls="--", lw=0.8)
        ax2.set_yticks(y)
        ax2.set_yticklabels(labels, fontsize=8)
        ax2.set_title("Expectancy %")
        ax2.invert_yaxis()
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    ax3 = axes[1, 0]
    stab = stats.get("stability_scores", [])[:8]
    if stab:
        xs = [s["rule"] for s in stab]
        ys = [s.get("stability_score") or 0 for s in stab]
        ax3.bar(range(len(xs)), ys, color="#2E7D32", alpha=0.85)
        ax3.set_xticks(range(len(xs)))
        ax3.set_xticklabels(xs, rotation=45, ha="right", fontsize=7)
        ax3.set_title("Stability Score")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    ax4 = axes[1, 1]
    if ranked:
        xs = [r["rule"] for r in ranked]
        ys = [r.get("n", 0) for r in ranked]
        ax4.bar(range(len(xs)), ys, color="#E65100", alpha=0.85)
        ax4.set_xticks(range(len(xs)))
        ax4.set_xticklabels(xs, rotation=45, ha="right", fontsize=7)
        ax4.set_title("Sample Count")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle(f"{symbol} {interval} — Candidate Rules")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    lines = [
        "# REPORT_WAVE_CANDIDATE_RULES",
        "",
        "Confluence 우수 조건 Candidate Rule 강건성·안정성 관측",
        "",
    ]
    all_stats = {}

    for symbol, interval in TARGETS:
        conf_path = os.path.join(OUT_DIR, f"wave_confluence_{symbol}_{interval}.csv")
        if not os.path.isfile(conf_path):
            continue
        import pandas as pd
        conf = pd.read_csv(conf_path, parse_dates=["timestamp"])
        enriched = enrich_confluence_events(conf, symbol, interval)
        rules_df = build_candidate_rules(symbol, interval, conf)
        csv_path = os.path.join(OUT_DIR, f"wave_candidate_rules_{symbol}_{interval}.csv")
        rules_df.to_csv(csv_path, index=False)
        stats = summarize_candidate_rules(rules_df, symbol, interval, enriched)
        all_stats[f"{symbol}_{interval}"] = stats
        png = _plot(stats, symbol, interval)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `wave_candidate_rules_{symbol}_{interval}.csv`")
        lines.append(f"- PNG: `{os.path.basename(png)}`")
        lines.append(f"- Confluence 이벤트: {stats['count']}")
        lines.append("")

        lines.append("### Rule Performance")
        lines.append("")
        lines.append("| rule | n | win | expectancy |")
        lines.append("|---|---:|---:|---:|")
        for r in stats.get("rule_performance", []):
            lines.append(
                f"| {r['rule']} | {r.get('n', 0)} | {r.get('win', 0)} | {_fmt(r.get('expectancy'))} |"
            )
        lines.append("")

        lines.append("### Rule Robustness")
        lines.append("")
        lines.append("| rule | windowA | windowB | gap |")
        lines.append("|---|---:|---:|---:|")
        for r in stats.get("rule_robustness", []):
            lines.append(
                f"| {r['rule']} | {_fmt(r.get('window_a'))} | "
                f"{_fmt(r.get('window_b'))} | {_fmt(r.get('gap'))} |"
            )
        lines.append("")

        lines.append("### Rule Stability Score")
        lines.append("")
        lines.append("| rule | stability | expectancy | n |")
        lines.append("|---|---:|---:|---:|")
        for s in stats.get("stability_scores", []):
            lines.append(
                f"| {s['rule']} | {_fmt(s.get('stability_score'))} | "
                f"{_fmt(s.get('expectancy'))} | {s.get('n', 0)} |"
            )
        lines.append("")

        lines.append("### Top Rules")
        lines.append("")
        for i, r in enumerate(stats.get("top_rules", [])[:10], 1):
            lines.append(
                f"{i}. {r['rule']} — stability {_fmt(r.get('stability_score'))}, "
                f"exp {_fmt(r.get('expectancy'))}%, n={r.get('n', 0)}"
            )
        lines.append("")

        lines.append("### Failure Analysis")
        lines.append("")
        lines.append("| rule | failure reason | % |")
        lines.append("|---|---|---:|")
        for f in stats.get("failure_analysis", []):
            lines.append(
                f"| {f['rule']} | {f['failure_reason']} | {_fmt(f.get('pct'))} |"
            )
        lines.append("")

        ms = stats.get("most_stable_rule", {})
        ls = stats.get("least_stable_rule", {})
        lines.append(f"- Most Stable: {ms.get('rule', '—')} (score {_fmt(ms.get('stability_score'))})")
        lines.append(f"- Least Stable: {ls.get('rule', '—')} (score {_fmt(ls.get('stability_score'))})")
        lines.append("")

    if len(all_stats) == 2:
        a, b = all_stats["ETHUSDT_4h"], all_stats["BTCUSDT_1d"]
        lines.append("## ETH / BTC 비교")
        lines.append("")
        lines.append("| 지표 | ETH | BTC |")
        lines.append("|---|---:|---:|")
        ta = a.get("top_rules", [{}])[0] if a.get("top_rules") else {}
        tb = b.get("top_rules", [{}])[0] if b.get("top_rules") else {}
        lines.append(f"| top rule | {ta.get('rule', '—')} | {tb.get('rule', '—')} |")
        lines.append(
            f"| top stability | {_fmt(ta.get('stability_score'))} | {_fmt(tb.get('stability_score'))} |"
        )
        lines.append(
            f"| top expectancy | {_fmt(ta.get('expectancy'))} | {_fmt(tb.get('expectancy'))} |"
        )
        score3_a = next((r for r in a.get("rule_performance", []) if r["rule"] == "RULE_SCORE_3"), {})
        score3_b = next((r for r in b.get("rule_performance", []) if r["rule"] == "RULE_SCORE_3"), {})
        lines.append(
            f"| RULE_SCORE_3 exp | {_fmt(score3_a.get('expectancy'))} | {_fmt(score3_b.get('expectancy'))} |"
        )
        lines.append(
            f"| RULE_SCORE_3 n | {score3_a.get('n', 0)} | {score3_b.get('n', 0)} |"
        )
        lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_CANDIDATE_RULES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wave candidate rules sweep complete")


if __name__ == "__main__":
    main()
