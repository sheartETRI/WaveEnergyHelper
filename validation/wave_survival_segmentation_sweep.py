"""Wave Survival Segmentation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_survival_segmentation import full_survival_segmentation_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_survival_segmentation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    curve = stats.get("survival_curve", [])
    ax = axes[0, 0]
    if curve:
        hs = [c["horizon"] for c in curve]
        vals = [c.get("survival_rate") or 0 for c in curve]
        ax.plot(hs, vals, marker="o", color="#1565C0", linewidth=2)
        ax.set_title("Survival Curve (>2%)")
        ax.set_xlabel("horizon (bars)")
        ax.set_ylabel("survival_rate (%)")

    feat = stats.get("feature_diff", [])
    ax2 = axes[0, 1]
    if feat:
        labels = [f["feature"].replace("_score", "")[:8] for f in feat]
        deltas = [f.get("delta") or 0 for f in feat]
        colors = ["#2E7D32" if d > 0 else "#C62828" for d in deltas]
        ax2.barh(range(len(labels)), deltas, color=colors, alpha=0.85)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(labels, fontsize=7)
        ax2.invert_yaxis()
        ax2.axvline(0, color="gray", linewidth=0.8)
        ax2.set_title("Feature Diff (SURV - FAIL)")

    rule = stats.get("rule_survival", [])
    ax3 = axes[0, 2]
    if rule:
        labels = [r["rule"] for r in rule]
        surv = [r.get("survival_rate") or 0 for r in rule]
        fail = [r.get("failure_rate") or 0 for r in rule]
        x = np.arange(len(labels))
        ax3.bar(x - 0.15, surv, 0.3, label="Survived", color="#2E7D32")
        ax3.bar(x + 0.15, fail, 0.3, label="Failed", color="#C62828")
        ax3.set_xticks(x)
        ax3.set_xticklabels(labels)
        ax3.set_title("Rule Survival Rate")
        ax3.legend(fontsize=7)

    sym = stats.get("symbol_survival", [])
    ax4 = axes[1, 0]
    if sym:
        labels = [s["symbol"].replace("USDT", "") for s in sym]
        surv = [s.get("survival_rate") or 0 for s in sym]
        ax4.bar(labels, surv, color="#6A1B9A", alpha=0.85)
        ax4.set_title("Symbol Survival Rate (%)")

    reg = stats.get("regime_survival", [])
    ax5 = axes[1, 1]
    if reg:
        labels = [r["regime"] for r in reg]
        surv = [r.get("survival_rate") or 0 for r in reg]
        ax5.bar(labels, surv, color="#E65100", alpha=0.85)
        ax5.set_title("Regime Survival Rate (%)")

    contrib = stats.get("contribution", [])
    ax6 = axes[1, 2]
    if contrib:
        labels, vals = [], []
        for c in contrib:
            lbl = c.get("rule", "")
            if lbl == "RULE":
                labels.append("Rule")
                vals.append(c.get("rule_contribution") or 0)
            elif lbl == "SYMBOL":
                labels.append("Symbol")
                vals.append(c.get("symbol_contribution") or 0)
            elif lbl == "REGIME":
                labels.append("Regime")
                vals.append(c.get("regime_contribution") or 0)
            elif lbl == "SURVIVAL_FEATURE":
                labels.append("SurvFeat")
                vals.append(c.get("survival_feature_contribution") or 0)
            elif lbl == "RESIDUAL":
                labels.append("Residual")
                vals.append(c.get("residual") or 0)
        ax6.bar(labels, vals, color=["#1565C0", "#E65100", "#2E7D32", "#6A1B9A", "#9E9E9E"], alpha=0.85)
        ax6.set_title("Contribution (SS %)")
        ax6.tick_params(axis="x", rotation=20)

    fig.suptitle("Wave Survival Segmentation")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# REPORT — Wave Survival Segmentation",
        "",
        "## 생존 정의",
        "",
        stats.get("survival_definition", ""),
        "",
        "Survival Feature = structure_score + money_flow_score + energy_score",
        "",
        "## 1. Survival Cohort",
        "",
        "| label | n | avg5 | avg10 | avg20 | avg40 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in stats.get("survival_cohort", []):
        lines.append(
            f"| {c.get('survival_label', '')} | {c.get('n', 0)} | "
            f"{_fmt(c.get('avg_return_5'), pct=True)} | {_fmt(c.get('avg_return_10'), pct=True)} | "
            f"{_fmt(c.get('avg_return_20'), pct=True)} | {_fmt(c.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 2. Rule Survival", ""])
    lines.append("| rule | n | survival | failure | neutral |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in stats.get("rule_survival", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('survival_rate'), pct=True)} | {_fmt(r.get('failure_rate'), pct=True)} | "
            f"{_fmt(r.get('neutral_rate'), pct=True)} |"
        )

    lines.extend(["", "## 3. Symbol Survival", ""])
    lines.append("| symbol | n | survival | failure | avg20 | avg40 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for s in stats.get("symbol_survival", []):
        lines.append(
            f"| {s.get('symbol', '')} | {s.get('n', 0)} | "
            f"{_fmt(s.get('survival_rate'), pct=True)} | {_fmt(s.get('failure_rate'), pct=True)} | "
            f"{_fmt(s.get('avg_return_20'), pct=True)} | {_fmt(s.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 4. Regime Survival", ""])
    lines.append("| regime | n | survival | failure | avg20 | avg40 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in stats.get("regime_survival", []):
        lines.append(
            f"| {r.get('regime', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('survival_rate'), pct=True)} | {_fmt(r.get('failure_rate'), pct=True)} | "
            f"{_fmt(r.get('avg_return_20'), pct=True)} | {_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 5. Feature Difference (SURVIVED vs FAILED)", ""])
    lines.append("| feature | survived | failed | delta |")
    lines.append("|---|---:|---:|---:|")
    for f in stats.get("feature_diff", []):
        lines.append(
            f"| {f.get('feature', '')} | {_fmt(f.get('survived_mean'))} | "
            f"{_fmt(f.get('failed_mean'))} | {_fmt(f.get('delta'))} |"
        )

    lines.extend(["", "## 6. Failure Cause 분석", ""])
    lines.append("| cause | n | pct | avg20 | avg40 | avg_bars |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for f in stats.get("failure_cause", []):
        lines.append(
            f"| {f.get('failure_cause', '')} | {f.get('n', 0)} | "
            f"{_fmt(f.get('cause_pct'), pct=True)} | {_fmt(f.get('avg_return_20'), pct=True)} | "
            f"{_fmt(f.get('avg_return_40'), pct=True)} | {_fmt(f.get('avg_bars_elapsed'))} |"
        )

    lines.extend(["", "## 7. Survival Curve", ""])
    lines.append("| horizon | n | survival_rate (>2%) |")
    lines.append("|---:|---:|---:|")
    for c in stats.get("survival_curve", []):
        lines.append(
            f"| +{c.get('horizon', '')} | {c.get('n', 0)} | "
            f"{_fmt(c.get('survival_rate'), pct=True)} |"
        )

    lines.extend(["", "## 8. Champion Survivor (return_40 Top 20)", ""])
    lines.append("| rank | rule | symbol | tf | return_40 | mfe_40 |")
    lines.append("|---:|---|---|---|---:|---:|")
    for c in stats.get("champion_return_40", [])[:20]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('rule', '')} | {c.get('symbol', '')} | "
            f"{c.get('timeframe', '')} | {_fmt(c.get('return_40'), pct=True)} | "
            f"{_fmt(c.get('mfe_40'), pct=True)} |"
        )

    lines.extend(["", "## 9. Contribution 분석 (SS %)", ""])
    lines.append("- 이전 Regime Seg #20: Rule 0.03%, Symbol 1.89%, Regime 0.57%, Residual 97.51%")
    for c in stats.get("contribution", []):
        lbl = c.get("rule", "")
        if lbl == "RULE":
            lines.append(f"- **Rule**: {_fmt(c.get('rule_contribution'), pct=True)}")
        elif lbl == "SYMBOL":
            lines.append(f"- **Symbol**: {_fmt(c.get('symbol_contribution'), pct=True)}")
        elif lbl == "REGIME":
            lines.append(f"- **Regime**: {_fmt(c.get('regime_contribution'), pct=True)}")
        elif lbl == "SURVIVAL_FEATURE":
            lines.append(f"- **Survival Feature**: {_fmt(c.get('survival_feature_contribution'), pct=True)}")
        elif lbl == "RESIDUAL":
            lines.append(f"- **Residual**: {_fmt(c.get('residual'), pct=True)}")

    lines.extend(["", "## 10. Active Candidate Survival Overlay", ""])
    lines.append("| rank | symbol | tf | rule | surv_rate | fail_rate | score |")
    lines.append("|---:|---|---|---|---:|---:|---:|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('survival_rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {_fmt(a.get('historical_survival_rate'), pct=True)} | "
            f"{_fmt(a.get('historical_failure_rate'), pct=True)} | {_fmt(a.get('watchlist_score'))} |"
        )

    lines.extend(["", "## 11. 현재 추적 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"surv={_fmt(p.get('historical_survival_rate'), pct=True)} "
            f"fail={_fmt(p.get('historical_failure_rate'), pct=True)}"
        )

    rb = next((r for r in stats.get("rule_survival", []) if r.get("rule") == "RULE_B"), {})
    fd = {f["feature"]: f for f in stats.get("feature_diff", [])}
    struct_d = fd.get("structure_score", {}).get("delta")
    mf_d = fd.get("money_flow_score", {}).get("delta")

    lines.extend(["", "## 12. 핵심 결론", ""])
    lines.append(
        f"**RULE_B survival rate {_fmt(rb.get('survival_rate'), pct=True)}** — "
        f"생존 이벤트는 structure(+{ _fmt(struct_d)}) 및 money_flow(+{ _fmt(mf_d)}) score가 높음."
    )
    sf = next((c for c in stats.get("contribution", []) if c.get("rule") == "SURVIVAL_FEATURE"), {})
    lines.append(
        f"- Survival Feature Contribution: {_fmt(sf.get('survival_feature_contribution'), pct=True)} "
        f"(Rule/Symbol/Regime 대비 {'높음' if (sf.get('survival_feature_contribution') or 0) > 1.89 else '유사'})"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_SURVIVAL_SEGMENTATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building survival segmentation analysis...")
    stats = full_survival_segmentation_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_survival_segmentation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_survival_segmentation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("survival segmentation sweep complete")


if __name__ == "__main__":
    main()
