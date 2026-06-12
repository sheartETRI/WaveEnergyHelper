"""Wave Entry Filter Refinement 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_entry_filter_refinement import full_entry_filter_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_entry_filter_refinement.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    rule_f = stats.get("rule_filter", [])
    ax = axes[0, 0]
    if rule_f:
        names = [r["rule"] for r in rule_f]
        exps = [r.get("expectancy") or 0 for r in rule_f]
        ax.bar(names, exps, color="#1565C0")
        ax.set_title("Rule Filter Expectancy")
        ax.axhline(stats.get("baseline", {}).get("expectancy", 0), color="red", linestyle="--", label="baseline")
        ax.legend()

    sym_f = stats.get("symbol_filter", [])
    ax = axes[0, 1]
    if sym_f:
        names = [s["symbol_filter"].replace("USDT", "") for s in sym_f]
        exps = [s.get("expectancy") or 0 for s in sym_f]
        ax.bar(names, exps, color="#2E7D32")
        ax.set_title("Symbol Filter Expectancy")

    feat_f = stats.get("feature_threshold", [])
    ax = axes[0, 2]
    if feat_f:
        top = sorted(feat_f, key=lambda x: x.get("expectancy") or -999, reverse=True)[:10]
        names = [f["feature_filter"][:18] for f in top]
        exps = [f.get("expectancy") or 0 for f in top]
        ax.barh(names, exps, color="#6A1B9A")
        ax.set_title("Top Feature Thresholds")

    champs = stats.get("champion_filters", [])[:10]
    ax = axes[1, 0]
    if champs:
        labels = [f"#{c['rank']}" for c in champs]
        scores = [c.get("score") or 0 for c in champs]
        ax.bar(labels, scores, color="#EF6C00")
        ax.set_title("Champion Filter Score")

    champs10 = stats.get("champion_filters", [])[:10]
    ax = axes[1, 1]
    if champs10:
        labels = [f"#{c['rank']}" for c in champs10]
        pfs = [min(c.get("profit_factor") or 0, 10) for c in champs10]
        ax.bar(labels, pfs, color="#00838F")
        ax.set_title("Champion Profit Factor")

    rob = stats.get("robustness", [])[:10]
    ax = axes[1, 2]
    if rob:
        labels = [f"#{r.get('rank', '')}" for r in rob]
        stab = [r.get("stability_score") or 0 for r in rob]
        ax.bar(labels, stab, color="#C62828")
        ax.set_title("Robustness Stability Score")

    fig.suptitle("Wave Entry Filter Refinement", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    bl = stats.get("baseline", {})
    lines = [
        "# Wave Entry Filter Refinement Report",
        "",
        f"Baseline (NO_EXIT cohort): n={bl.get('n', '')}, avg_return_20={_fmt(bl.get('avg_return_20'), pct=True)}, "
        f"expectancy={_fmt(bl.get('expectancy'))}, survival={_fmt(bl.get('survival_rate'), pct=True)}",
        "",
        "## 1. Rule Filter 성과",
        "",
        "| rule | n | avg_return_20 | expectancy | profit_factor | survival_rate | delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in stats.get("rule_filter", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('n', '')} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('expectancy'))} | {_fmt(r.get('profit_factor'))} | "
            f"{_fmt(r.get('survival_rate'), pct=True)} | {_fmt(r.get('expectancy_delta'))} |"
        )

    lines.extend(["", "## 2. Symbol Filter 성과", ""])
    lines.append("| symbol | n | expectancy | profit_factor | survival_rate | delta |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for s in stats.get("symbol_filter", []):
        lines.append(
            f"| {s.get('symbol_filter', '')} | {s.get('n', '')} | {_fmt(s.get('expectancy'))} | "
            f"{_fmt(s.get('profit_factor'))} | {_fmt(s.get('survival_rate'), pct=True)} | "
            f"{_fmt(s.get('expectancy_delta'))} |"
        )

    lines.extend(["", "## 3. Regime Filter 성과", ""])
    lines.append("| regime | n | expectancy | survival_rate | delta |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("regime_filter", []):
        lines.append(
            f"| {r.get('regime_filter', '')} | {r.get('n', '')} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('survival_rate'), pct=True)} | {_fmt(r.get('expectancy_delta'))} |"
        )

    lines.extend(["", "## 4. Feature Threshold 성과 (Top 12)", ""])
    lines.append("| feature | n | expectancy | profit_factor | survival_rate |")
    lines.append("|---|---:|---:|---:|---:|")
    feat_sorted = sorted(stats.get("feature_threshold", []), key=lambda x: x.get("expectancy") or -999, reverse=True)
    for f in feat_sorted[:12]:
        lines.append(
            f"| {f.get('feature_filter', '')} | {f.get('n', '')} | {_fmt(f.get('expectancy'))} | "
            f"{_fmt(f.get('profit_factor'))} | {_fmt(f.get('survival_rate'), pct=True)} |"
        )

    lines.extend(["", "## 5. Champion Filter Top 20", ""])
    lines.append("| rank | filter_id | n | expectancy | pf | survival | delta | score |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for c in stats.get("champion_filters", []):
        fid = str(c.get("filter_id", ""))[:50]
        lines.append(
            f"| {c.get('rank', '')} | {fid} | {c.get('n', '')} | {_fmt(c.get('expectancy'))} | "
            f"{_fmt(c.get('profit_factor'))} | {_fmt(c.get('survival_rate'), pct=True)} | "
            f"{_fmt(c.get('expectancy_delta'))} | {_fmt(c.get('score'))} |"
        )

    lines.extend(["", "## 6. Worst Filter Top 20", ""])
    lines.append("| rank | filter_id | n | expectancy | score |")
    lines.append("|---:|---|---:|---:|---:|")
    for w in stats.get("worst_filters", [])[:20]:
        fid = str(w.get("filter_id", ""))[:50]
        lines.append(
            f"| {w.get('rank', '')} | {fid} | {w.get('n', '')} | {_fmt(w.get('expectancy'))} | {_fmt(w.get('score'))} |"
        )

    lines.extend(["", "## 7. Robustness 분석", ""])
    lines.append("| rank | filter_id | cell+ | symbol+ | regime+ |")
    lines.append("|---:|---|---:|---:|---:|")
    for r in stats.get("robustness", []):
        fid = str(r.get("filter_id", ""))[:40]
        lines.append(
            f"| {r.get('rank', '')} | {fid} | {_fmt(r.get('positive_cell_ratio'), pct=True)} | "
            f"{_fmt(r.get('positive_symbol_ratio'), pct=True)} | {_fmt(r.get('positive_regime_ratio'), pct=True)} |"
        )

    lines.extend(["", "## 8. False Discovery 분석", ""])
    lines.append("| rank | n | confidence | stability | expectancy |")
    lines.append("|---:|---:|---:|---:|---:|")
    for f in stats.get("false_discovery", []):
        lines.append(
            f"| {f.get('rank', '')} | {f.get('n', '')} | {_fmt(f.get('confidence_score'))} | "
            f"{_fmt(f.get('stability_score'))} | {_fmt(f.get('expectancy'))} |"
        )

    lines.extend(["", "## 9. Active Candidate Overlay", ""])
    lines.append("| rank | symbol | tf | rule | filter_match | exp | survival |")
    lines.append("|---:|---|---|---|---|---:|---:|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('priority_rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {str(a.get('champion_filter_match', ''))[:30]} | "
            f"{_fmt(a.get('expected_expectancy'))} | {_fmt(a.get('expected_survival'), pct=True)} |"
        )

    lines.extend(["", "## 10. 현재 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('priority_rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"filter={str(p.get('champion_filter_match', ''))[:35]} exp={_fmt(p.get('expected_expectancy'))}"
        )

    champ = stats.get("champion_filters", [{}])[0] if stats.get("champion_filters") else {}
    dual = [c for c in stats.get("champion_filters", [])
            if (c.get("expectancy_delta") or 0) > 0 and (c.get("survival_delta") or 0) > 0]

    lines.extend(["", "## 11. 핵심 결론", ""])
    lines.append(
        f"**Champion #1: {str(champ.get('filter_id', '—'))[:60]}** — "
        f"expectancy {_fmt(champ.get('expectancy'))} (delta {_fmt(champ.get('expectancy_delta'))}), "
        f"survival {_fmt(champ.get('survival_rate'), pct=True)} (delta {_fmt(champ.get('survival_delta'), pct=True)})."
    )
    lines.append(f"- Expectancy+Survival 동시 개선 필터: **{len(dual)}**개")
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_ENTRY_FILTER_REFINEMENT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building entry filter refinement...")
    stats = full_entry_filter_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_entry_filter_refinement.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_entry_filter_refinement.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("entry filter refinement sweep complete")


if __name__ == "__main__":
    main()
