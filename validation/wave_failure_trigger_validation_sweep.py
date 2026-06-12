"""Wave Failure Trigger Validation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_failure_trigger_validation import full_failure_trigger_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_failure_trigger_validation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    pr = stats.get("precision_recall", [])
    ax = axes[0, 0]
    if pr:
        names = [p["trigger_type"][:12] for p in pr if p.get("n")]
        f1s = [p.get("f1") or 0 for p in pr if p.get("n")]
        ax.barh(names, f1s, color="#C62828")
        ax.set_title("Trigger F1 (%)")
        ax.set_xlabel("f1")

    timing = stats.get("trigger_timing", [])
    ax = axes[0, 1]
    if timing:
        names = [t["trigger_type"][:12] for t in timing]
        early = [t.get("early_trigger_ratio") or 0 for t in timing]
        ax.bar(names, early, color="#1565C0")
        ax.set_title("Early Trigger Ratio (<=5 bars)")
        ax.tick_params(axis="x", rotation=45)

    perf = stats.get("trigger_performance", [])
    ax = axes[0, 2]
    if perf:
        names = [p["trigger_type"][:12] for p in perf]
        fail = [p.get("failure_rate") or 0 for p in perf]
        ax.bar(names, fail, color="#6A1B9A")
        ax.set_title("Failure Rate when Triggered")
        ax.tick_params(axis="x", rotation=45)

    dist = stats.get("failed_first_trigger_dist", {})
    ax = axes[1, 0]
    if dist:
        labels = list(dist.keys())
        vals = list(dist.values())
        ax.pie(vals, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title("FAILED_20 First Trigger")

    combos = stats.get("combos", [])
    ax = axes[1, 1]
    if combos:
        names = [c["combo"][:20] for c in combos]
        f1s = [c.get("f1") or 0 for c in combos]
        ax.barh(names, f1s, color="#2E7D32")
        ax.set_title("Combo F1 (%)")

    best = stats.get("best_triggers", [])[:8]
    ax = axes[1, 2]
    if best:
        names = [b["trigger_type"][:12] for b in best]
        scores = [b.get("score") or 0 for b in best]
        ax.bar(names, scores, color="#EF6C00")
        ax.set_title("Best Trigger Score")
        ax.tick_params(axis="x", rotation=45)

    fig.suptitle("Wave Failure Trigger Validation", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# Wave Failure Trigger Validation Report",
        "",
        "실패 이벤트 조기 무효화 trigger 검증 (관측 전용).",
        "",
        "## 1. Trigger 성능 (Precision / Recall / F1)",
        "",
        "| trigger | n | precision | recall | f1 | false_exit_rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for p in stats.get("precision_recall", []):
        if not p.get("n"):
            continue
        lines.append(
            f"| {p.get('trigger_type', '')} | {p.get('n', '')} | "
            f"{_fmt(p.get('precision'), pct=True)} | {_fmt(p.get('recall'), pct=True)} | "
            f"{_fmt(p.get('f1'), pct=True)} | {_fmt(p.get('false_exit_rate'), pct=True)} |"
        )

    lines.extend(["", "## 2. Trigger Timing", ""])
    lines.append("| trigger | n | avg_bars | median_bars | early_ratio |")
    lines.append("|---|---:|---:|---:|---:|")
    for t in stats.get("trigger_timing", []):
        lines.append(
            f"| {t.get('trigger_type', '')} | {t.get('n', '')} | "
            f"{_fmt(t.get('avg_bars_to_trigger'))} | {_fmt(t.get('median_bars_to_trigger'))} | "
            f"{_fmt(t.get('early_trigger_ratio'), pct=True)} |"
        )

    lines.extend(["", "## 3. FAILED_20 First Trigger 분포", ""])
    for k, v in stats.get("failed_first_trigger_dist", {}).items():
        lines.append(f"- **{k}**: {v}")

    lines.extend(["", "## 4. Trigger별 Failure Rate (triggered events)", ""])
    lines.append("| trigger | n | failure_rate | survival_rate | avg_return_20 |")
    lines.append("|---|---:|---:|---:|---:|")
    for p in stats.get("trigger_performance", []):
        lines.append(
            f"| {p.get('trigger_type', '')} | {p.get('n', '')} | "
            f"{_fmt(p.get('failure_rate'), pct=True)} | {_fmt(p.get('survival_rate'), pct=True)} | "
            f"{_fmt(p.get('avg_return_20'), pct=True)} |"
        )

    lines.extend(["", "## 5. Rule별 Trigger", ""])
    for r in stats.get("rule_trigger", []):
        lines.append(
            f"- {r.get('rule')}: n={r.get('n')}, fail={_fmt(r.get('failure_rate'), pct=True)}, "
            f"top={r.get('top_trigger')}, false_exit={_fmt(r.get('false_exit_rate'), pct=True)}"
        )

    lines.extend(["", "## 6. Symbol별 Trigger", ""])
    for r in stats.get("symbol_trigger", [])[:8]:
        lines.append(
            f"- {r.get('symbol')}: n={r.get('n')}, top={r.get('top_trigger')}, "
            f"false_exit={_fmt(r.get('false_exit_rate'), pct=True)}"
        )

    lines.extend(["", "## 7. Regime별 Trigger", ""])
    for r in stats.get("regime_trigger", []):
        lines.append(
            f"- {r.get('regime')}: n={r.get('n')}, top={r.get('top_trigger')}, "
            f"false_exit={_fmt(r.get('false_exit_rate'), pct=True)}"
        )

    lines.extend(["", "## 8. Trigger Combination (OR)", ""])
    lines.append("| combo | n | f1 | precision | recall | false_exit |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for c in stats.get("combos", []):
        lines.append(
            f"| {c.get('combo', '')} | {c.get('n', '')} | {_fmt(c.get('f1'), pct=True)} | "
            f"{_fmt(c.get('precision'), pct=True)} | {_fmt(c.get('recall'), pct=True)} | "
            f"{_fmt(c.get('false_exit_rate'), pct=True)} |"
        )

    lines.extend(["", "## 9. Best Trigger Top 10", ""])
    lines.append("| rank | trigger | score | f1 | false_exit | early_ratio |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    for b in stats.get("best_triggers", []):
        lines.append(
            f"| {b.get('rank', '')} | {b.get('trigger_type', '')} | {_fmt(b.get('score'))} | "
            f"{_fmt(b.get('f1'), pct=True)} | {_fmt(b.get('false_exit_rate'), pct=True)} | "
            f"{_fmt(b.get('early_trigger_ratio'), pct=True)} |"
        )

    lines.extend(["", "## 10. Active Candidate Risk Overlay", ""])
    lines.append("| rank | symbol | tf | rule | risk | trigger | status |")
    lines.append("|---:|---|---|---|---:|---|---|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {a.get('trigger_risk_score', '')} | "
            f"{a.get('highest_risk_trigger') or '—'} | {a.get('current_trigger_status', '')} |"
        )

    lines.extend(["", "## 11. 현재 추적 우선순위 (Trigger Risk)", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"risk={p.get('trigger_risk_score')} trigger={p.get('highest_risk_trigger')}"
        )

    best = stats.get("best_triggers", [{}])[0] if stats.get("best_triggers") else {}
    top_pr = max(
        (p for p in stats.get("precision_recall", []) if p.get("f1")),
        key=lambda x: x.get("f1") or 0,
        default={},
    )
    dist = stats.get("failed_first_trigger_dist", {})
    top_fail = max(dist, key=dist.get) if dist else "—"

    lines.extend(["", "## 12. 핵심 결론", ""])
    lines.append(
        f"**FAILED_20 최다 first trigger: {top_fail}** — "
        f"Best trigger: {best.get('trigger_type', '—')} (score {_fmt(best.get('score'))}, "
        f"f1 {_fmt(best.get('f1'), pct=True)}, false_exit {_fmt(best.get('false_exit_rate'), pct=True)})."
    )
    lines.append(
        f"- 최고 F1 단일 trigger: {top_pr.get('trigger_type', '—')} "
        f"({_fmt(top_pr.get('f1'), pct=True)})"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_FAILURE_TRIGGER_VALIDATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building failure trigger validation...")
    stats = full_failure_trigger_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_failure_trigger_validation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_failure_trigger_validation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("failure trigger validation sweep complete")


if __name__ == "__main__":
    main()
