"""Wave Robustness Validation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_robustness_validation import full_robustness_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_robustness_validation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    temporal = [t for t in stats.get("temporal_split", []) if t.get("filter_id") == "CHAMPION"]
    ax = axes[0, 0]
    if temporal:
        names = [t["split"] for t in temporal]
        exps = [t.get("expectancy") or 0 for t in temporal]
        ax.bar(names, exps, color="#1565C0")
        ax.set_title("CHAMPION Temporal Split")
        ax.tick_params(axis="x", rotation=45)

    tf = [t for t in stats.get("timeframe_robustness", []) if t.get("filter_id") == "CHAMPION"]
    ax = axes[0, 1]
    if tf:
        names = [t["timeframe"] for t in tf]
        exps = [t.get("expectancy") or 0 for t in tf]
        ax.bar(names, exps, color="#2E7D32")
        ax.set_title("CHAMPION TF Robustness")

    reg = [r for r in stats.get("regime_robustness", []) if r.get("filter_id") == "CHAMPION"]
    ax = axes[0, 2]
    if reg:
        names = [r["regime"] for r in reg]
        exps = [r.get("expectancy") or 0 for r in reg]
        ax.bar(names, exps, color="#6A1B9A")
        ax.set_title("CHAMPION Regime Robustness")

    scores = stats.get("robustness_scores", [])
    ax = axes[1, 0]
    if scores:
        names = [s["filter_id"] for s in scores]
        vals = [s.get("robustness_score") or 0 for s in scores]
        ax.barh(names, vals, color="#EF6C00")
        ax.set_title("Robustness Score")

    overfit = stats.get("robustness_scores", [])
    ax = axes[1, 1]
    if overfit:
        names = [o["filter_id"] for o in overfit]
        vals = [o.get("overfit_risk") or 0 for o in overfit]
        ax.bar(names, vals, color="#C62828")
        ax.set_title("Overfitting Risk")
        ax.tick_params(axis="x", rotation=45)

    alts = stats.get("alternatives", [])[:8]
    ax = axes[1, 2]
    if alts:
        names = [a["filter_id"] for a in alts]
        exps = [a.get("expectancy") or 0 for a in alts]
        ax.barh(names, exps, color="#00838F")
        ax.set_title("Alternative Filters Expectancy")

    fig.suptitle("Wave Robustness Validation", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    champ_v = stats.get("champion_verdict", {})
    lines = [
        "# Wave Robustness Validation Report",
        "",
        f"Champion: {champ_v.get('filter_name', '')} — verdict **{champ_v.get('verdict', '')}**, "
        f"robustness_score {_fmt(champ_v.get('robustness_score'))}, overfit_risk {_fmt(champ_v.get('overfit_risk'))}",
        "",
        "## 1. Temporal Split Validation (CHAMPION)",
        "",
        "| split | n | expectancy | avg_return_20 | survival | PF | tier |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for t in [x for x in stats.get("temporal_split", []) if x.get("filter_id") == "CHAMPION"]:
        lines.append(
            f"| {t.get('split', '')} | {t.get('n', '')} | {_fmt(t.get('expectancy'))} | "
            f"{_fmt(t.get('avg_return_20'), pct=True)} | {_fmt(t.get('survival_rate'), pct=True)} | "
            f"{_fmt(t.get('profit_factor'))} | {t.get('sample_tier', '')} |"
        )

    lines.extend(["", "## 2. Timeframe Robustness (CHAMPION)", ""])
    lines.append("| tf | n | expectancy | survival | PF |")
    lines.append("|---|---:|---:|---:|---:|")
    for t in [x for x in stats.get("timeframe_robustness", []) if x.get("filter_id") == "CHAMPION"]:
        lines.append(
            f"| {t.get('timeframe', '')} | {t.get('n', '')} | {_fmt(t.get('expectancy'))} | "
            f"{_fmt(t.get('survival_rate'), pct=True)} | {_fmt(t.get('profit_factor'))} |"
        )

    lines.extend(["", "## 3. Symbol Robustness", ""])
    lines.append("| filter | symbol | n | expectancy | survival |")
    lines.append("|---|---|---:|---:|---:|")
    for s in stats.get("symbol_robustness", []):
        if s.get("symbol") in ("BNB_only", "without_BNB", "with_BNB") or s.get("filter_id") == "CHAMPION":
            lines.append(
                f"| {s.get('filter_id', '')} | {s.get('symbol', '')} | {s.get('n', '')} | "
                f"{_fmt(s.get('expectancy'))} | {_fmt(s.get('survival_rate'), pct=True)} |"
            )

    lines.extend(["", "## 4. Regime Robustness (CHAMPION)", ""])
    lines.append("| regime | n | expectancy | survival | PF |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in [x for x in stats.get("regime_robustness", []) if x.get("filter_id") == "CHAMPION"]:
        lines.append(
            f"| {r.get('regime', '')} | {r.get('n', '')} | {_fmt(r.get('expectancy'))} | "
            f"{_fmt(r.get('survival_rate'), pct=True)} | {_fmt(r.get('profit_factor'))} |"
        )

    lines.extend(["", "## 5. Leave-One-Out (CHAMPION)", ""])
    lines.append("| condition | n | expectancy | delta |")
    lines.append("|---|---:|---:|---:|")
    for l in [x for x in stats.get("leave_one_out", []) if x.get("filter_id") == "CHAMPION"]:
        lines.append(
            f"| {l.get('loo_condition', '')} | {l.get('n', '')} | {_fmt(l.get('expectancy'))} | "
            f"{_fmt(l.get('expectancy_delta'))} |"
        )

    lines.extend(["", "## 6. Minimum Sample Check (CHAMPION highlights)", ""])
    unstable = [m for m in stats.get("minimum_sample", [])
                if m.get("filter_id") == "CHAMPION" and m.get("sample_tier") in ("LOW", "UNSTABLE")]
    lines.append("| context | n | tier | expectancy |")
    lines.append("|---|---:|---|---:|")
    for m in unstable[:10]:
        ctx = m.get("split") or m.get("timeframe") or m.get("regime") or ""
        lines.append(
            f"| {ctx} | {m.get('n', '')} | {m.get('sample_tier', '')} | {_fmt(m.get('expectancy'))} |"
        )
    if not unstable:
        lines.append("| — | — | — | — |")

    lines.extend(["", "## 7. Robustness Score", ""])
    lines.append("| filter | score | split_cons | tf_cons | reg_cons | verdict |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for r in stats.get("robustness_scores", []):
        lines.append(
            f"| {r.get('filter_id', '')} | {_fmt(r.get('robustness_score'))} | "
            f"{_fmt(r.get('split_consistency_score'), pct=True)} | "
            f"{_fmt(r.get('tf_consistency_score'), pct=True)} | "
            f"{_fmt(r.get('regime_consistency_score'), pct=True)} | {r.get('verdict', '')} |"
        )

    lines.extend(["", "## 8. Overfitting Risk", ""])
    for o in stats.get("robustness_scores", []):
        lines.append(f"- {o.get('filter_id')}: risk={o.get('overfit_risk')} flags={o.get('overfit_flags', '')}")

    lines.extend(["", "## 9. Champion 유지/기각 판단", ""])
    lines.append(f"- **Verdict: {champ_v.get('verdict', '')}**")
    lines.append(f"- n={champ_v.get('n')}, expectancy={_fmt(champ_v.get('expectancy'))}, "
                 f"split_consistency={_fmt(champ_v.get('split_consistency_score'), pct=True)}")

    lines.extend(["", "## 10. Alternative Robust Filter", ""])
    lines.append("| rank | filter | robustness | expectancy | verdict |")
    lines.append("|---:|---|---:|---:|---|")
    for a in stats.get("alternatives", [])[:10]:
        lines.append(
            f"| {a.get('rank', '')} | {a.get('filter_id', '')} | {_fmt(a.get('robustness_score'))} | "
            f"{_fmt(a.get('expectancy'))} | {a.get('verdict', '')} |"
        )

    lines.extend(["", "## 11. Active Candidate Overlay", ""])
    lines.append("| rank | symbol | tf | rule | robust_match | score | risk |")
    lines.append("|---:|---|---|---|---|---:|---:|")
    for a in stats.get("active_candidates", [])[:12]:
        lines.append(
            f"| {a.get('priority_rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {a.get('robust_filter_match', '')} | "
            f"{_fmt(a.get('robustness_score'))} | {a.get('overfit_risk', '')} |"
        )

    lines.extend(["", "## 12. 현재 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('priority_rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"match={p.get('robust_filter_match')} score={_fmt(p.get('robustness_score'))}"
        )

    best_alt = stats.get("alternatives", [{}])[0] if stats.get("alternatives") else {}
    lines.extend(["", "## 13. 핵심 결론", ""])
    lines.append(
        f"Champion Filter verdict: **{champ_v.get('verdict', '')}** — "
        f"overfit_risk {_fmt(champ_v.get('overfit_risk'))}, "
        f"split_consistency {_fmt(champ_v.get('split_consistency_score'), pct=True)}."
    )
    lines.append(
        f"- Best alternative: {best_alt.get('filter_id', '—')} "
        f"(robustness {_fmt(best_alt.get('robustness_score'))}, verdict {best_alt.get('verdict', '')})"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_ROBUSTNESS_VALIDATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building robustness validation...")
    stats = full_robustness_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_robustness_validation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_robustness_validation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("robustness validation sweep complete")


if __name__ == "__main__":
    main()
