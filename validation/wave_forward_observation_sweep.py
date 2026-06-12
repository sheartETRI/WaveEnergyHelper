"""Wave Forward Observation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_forward_observation import full_forward_observation_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_forward_observation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    tier = stats.get("tier_dashboard", [])
    ax = axes[0, 0]
    if tier:
        names = [t["observation_tier"] for t in tier]
        exps = [t.get("expectancy") or 0 for t in tier]
        bases = [t.get("baseline_expectancy") or 0 for t in tier]
        x = np.arange(len(names))
        ax.bar(x - 0.2, exps, 0.4, label="live", color="#1565C0")
        ax.bar(x + 0.2, bases, 0.4, label="research", color="#9E9E9E")
        ax.set_xticks(x)
        ax.set_xticklabels(names)
        ax.set_title("Tier Expectancy vs Research")
        ax.legend()

    rolling = stats.get("rolling_performance", [])
    ax = axes[0, 1]
    if rolling:
        for tier, color in zip(("TIER_1", "TIER_2", "TIER_3"), ("#C62828", "#2E7D32", "#6A1B9A")):
            sub = [r for r in rolling if r.get("observation_tier") == tier]
            if sub:
                ax.plot([r["window_days"] for r in sub], [r.get("expectancy") or 0 for r in sub],
                        marker="o", label=tier, color=color)
        ax.set_title("Rolling Expectancy")
        ax.legend()

    drift = stats.get("drift_detection", [])
    ax = axes[0, 2]
    exp_drift = [d for d in drift if d.get("drift_metric") == "expectancy"]
    if exp_drift:
        names = [d["observation_tier"] for d in exp_drift]
        vals = [d.get("drift_pct") or 0 for d in exp_drift]
        colors = ["#C62828" if v < -25 else "#2E7D32" if v > 25 else "#F9A825" for v in vals]
        ax.bar(names, vals, color=colors)
        ax.set_title("Expectancy Drift % vs Research")
        ax.axhline(0, color="black", linewidth=0.5)

    monthly = stats.get("monthly_summary", [])
    ax = axes[1, 0]
    if monthly:
        months = [m["month"] for m in monthly[-6:]]
        ns = [m.get("n", 0) for m in monthly[-6:]]
        ax.bar(months, ns, color="#00838F")
        ax.set_title("Monthly Event Count")
        ax.tick_params(axis="x", rotation=45)

    cands = stats.get("candidate_queue", [])[:8]
    ax = axes[1, 1]
    if cands:
        labels = [f"{c['symbol'][:3]}/{c['timeframe']}" for c in cands]
        tiers = [c.get("observation_tier", "") for c in cands]
        ax.barh(labels, [1] * len(cands), color=["#C62828" if t == "TIER_1" else "#2E7D32" if t == "TIER_2" else "#6A1B9A" for t in tiers])
        ax.set_title("Current Candidates")

    maint = stats.get("maintenance", {})
    ax = axes[1, 2]
    verdict = maint.get("verdict", "MONITORING")
    colors = {"MAINTAINED": "#2E7D32", "PARTIAL": "#F9A825", "NOT_MAINTAINED": "#C62828", "MONITORING": "#1565C0"}
    ax.bar([verdict], [1], color=colors.get(verdict, "#9E9E9E"), width=0.5)
    ax.set_title(f"Maintenance: {verdict}")
    ax.set_ylim(0, 1.2)
    ax.set_yticks([])

    fig.suptitle("Wave Forward Observation Mode", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    maint = stats.get("maintenance", {})
    lines = [
        "# Wave Forward Observation Report",
        "",
        "실시간 Forward 관측 운영 모드 (#27). 연구 종료 후 관측 전용.",
        "",
        f"**Maintenance Verdict: {maint.get('verdict', '—')}**",
        "",
        "## 1. Tier별 성과",
        "",
        "| tier | filter | n | expectancy | survival | win_rate | research_exp | research_surv |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t in stats.get("tier_dashboard", []):
        lines.append(
            f"| {t.get('observation_tier', '')} | {t.get('filter_match', '')} | {t.get('n', '')} | "
            f"{_fmt(t.get('expectancy'))} | {_fmt(t.get('survival_rate'), pct=True)} | "
            f"{_fmt(t.get('win_rate'), pct=True)} | {_fmt(t.get('baseline_expectancy'))} | "
            f"{_fmt(t.get('baseline_survival_rate'), pct=True)} |"
        )

    lines.extend(["", "## 2. 현재 Candidate Queue", ""])
    lines.append("| rank | symbol | tf | rule | tier | filter | status |")
    lines.append("|---:|---|---|---|---|---|---|")
    for c in stats.get("candidate_queue", [])[:12]:
        lines.append(
            f"| {c.get('rank', '')} | {c.get('symbol', '')} | {c.get('timeframe', '')} | "
            f"{c.get('rule', '')} | {c.get('observation_tier', '')} | {c.get('filter_match', '')} | "
            f"{c.get('forward_status', '')} |"
        )

    lines.extend(["", "## 3. Rolling 30/60/90일 성과", ""])
    lines.append("| window | tier | n | expectancy | survival |")
    lines.append("|---:|---|---:|---:|---:|")
    for r in stats.get("rolling_performance", []):
        lines.append(
            f"| {r.get('window_days', '')}d | {r.get('observation_tier', '')} | {r.get('n', '')} | "
            f"{_fmt(r.get('expectancy'))} | {_fmt(r.get('survival_rate'), pct=True)} |"
        )

    lines.extend(["", "## 4. Drift 분석", ""])
    lines.append("| tier | metric | live | baseline | drift% | flag |")
    lines.append("|---|---|---:|---:|---:|---|")
    for d in stats.get("drift_detection", []):
        lines.append(
            f"| {d.get('observation_tier', '')} | {d.get('drift_metric', '')} | "
            f"{_fmt(d.get('drift_value'))} | {_fmt(d.get('baseline_value'))} | "
            f"{_fmt(d.get('drift_pct'), pct=True)} | {d.get('drift_flag', '')} |"
        )

    lines.extend(["", "## 5. Observation Summary", ""])
    obs = stats.get("observation_journal")
    n = len(obs) if obs is not None and not obs.empty else 0
    lines.append(f"- Total observation events: {n}")
    for t in stats.get("tier_dashboard", []):
        lines.append(f"- {t.get('observation_tier')}: n={t.get('n')}, exp={_fmt(t.get('expectancy'))}")

    lines.extend(["", "## 6. Alerts", ""])
    for a in stats.get("alerts", [])[:10]:
        lines.append(f"- [{a.get('alert_type')}] {a.get('alert_message', '')}")

    lines.extend(["", "## 7. 현재 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('priority_rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"{p.get('observation_tier')} drift={p.get('drift_flag')}"
        )

    lines.extend(["", "## 8. 실시간 유지 여부", ""])
    lines.append(f"- **Verdict: {maint.get('verdict', '')}** (drift_down={maint.get('drift_down_count', 0)})")
    lines.append("- 연구 baseline 대비 90일 rolling expectancy/survival drift로 판정")
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_FORWARD_OBSERVATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building forward observation...")
    stats = full_forward_observation_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_forward_observation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_forward_observation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print(f"maintenance: {stats.get('maintenance', {}).get('verdict')}")
    print("forward observation sweep complete")


if __name__ == "__main__":
    main()
