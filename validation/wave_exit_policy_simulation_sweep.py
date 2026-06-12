"""Wave Exit Policy Simulation 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_exit_policy_simulation import full_exit_policy_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_exit_policy_simulation.png")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    summary = [s for s in stats.get("policy_summary", []) if s.get("policy") != "NO_EXIT"]
    ax = axes[0, 0]
    if summary:
        names = [s["policy"] for s in summary]
        rets = [s.get("avg_return") or 0 for s in summary]
        ax.bar(names, rets, color="#1565C0")
        ax.set_title("Policy Avg Return (%)")
        ax.tick_params(axis="x", rotation=45)

    ax = axes[0, 1]
    if summary:
        names = [s["policy"] for s in summary]
        exps = [s.get("expectancy") or 0 for s in summary]
        ax.bar(names, exps, color="#2E7D32")
        ax.set_title("Expectancy")
        ax.tick_params(axis="x", rotation=45)

    ax = axes[0, 2]
    if summary:
        names = [s["policy"] for s in summary]
        pfs = [min(s.get("profit_factor") or 0, 10) for s in summary]
        ax.bar(names, pfs, color="#6A1B9A")
        ax.set_title("Profit Factor (capped 10)")
        ax.tick_params(axis="x", rotation=45)

    false_ex = stats.get("false_exit", [])
    ax = axes[1, 0]
    if false_ex:
        names = [f["policy"] for f in false_ex if f.get("policy") != "NO_EXIT"]
        vals = [f.get("false_exit_rate") or 0 for f in false_ex if f.get("policy") != "NO_EXIT"]
        ax.bar(names, vals, color="#C62828")
        ax.set_title("False Exit Rate (%)")
        ax.tick_params(axis="x", rotation=45)

    saved = stats.get("saved_failure", [])
    ax = axes[1, 1]
    if saved:
        names = [s["policy"] for s in saved if s.get("policy") != "NO_EXIT"]
        vals = [s.get("saved_failure_rate") or 0 for s in saved if s.get("policy") != "NO_EXIT"]
        ax.bar(names, vals, color="#EF6C00")
        ax.set_title("Saved Failure Rate (%)")
        ax.tick_params(axis="x", rotation=45)

    champs = stats.get("champion_policies", [])[:8]
    ax = axes[1, 2]
    if champs:
        names = [c["policy"] for c in champs]
        scores = [c.get("score") or 0 for c in champs]
        ax.barh(names, scores, color="#00838F")
        ax.set_title("Champion Policy Score")

    fig.suptitle("Wave Exit Policy Simulation", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# Wave Exit Policy Simulation Report",
        "",
        "Exit 정책별 성과 시뮬레이션 (관측 전용). Baseline: NO_EXIT (+20봉 보유).",
        "",
        "## 1. Policy Summary",
        "",
        "| policy | n | avg_return | expectancy | win_rate | profit_factor |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in stats.get("policy_summary", []):
        lines.append(
            f"| {s.get('policy', '')} | {s.get('n', '')} | "
            f"{_fmt(s.get('avg_return'), pct=True)} | {_fmt(s.get('expectancy'))} | "
            f"{_fmt(s.get('win_rate'), pct=True)} | {_fmt(s.get('profit_factor'))} |"
        )

    lines.extend(["", "## 2. Drawdown 분석", ""])
    lines.append("| policy | avg_mae | max_mae | avg_mfe | max_mfe |")
    lines.append("|---|---:|---:|---:|---:|")
    for d in stats.get("drawdown", []):
        lines.append(
            f"| {d.get('policy', '')} | {_fmt(d.get('avg_mae'), pct=True)} | "
            f"{_fmt(d.get('max_mae'), pct=True)} | {_fmt(d.get('avg_mfe'), pct=True)} | "
            f"{_fmt(d.get('max_mfe'), pct=True)} |"
        )

    lines.extend(["", "## 3. False Exit 분석", ""])
    lines.append("| policy | n | false_exit_n | false_exit_rate |")
    lines.append("|---|---:|---:|---:|")
    for f in stats.get("false_exit", []):
        lines.append(
            f"| {f.get('policy', '')} | {f.get('n', '')} | {f.get('false_exit_n', '')} | "
            f"{_fmt(f.get('false_exit_rate'), pct=True)} |"
        )

    lines.extend(["", "## 4. Saved Failure 분석", ""])
    lines.append("| policy | n | saved_failure_n | saved_failure_rate |")
    lines.append("|---|---:|---:|---:|")
    for s in stats.get("saved_failure", []):
        lines.append(
            f"| {s.get('policy', '')} | {s.get('n', '')} | {s.get('saved_failure_n', '')} | "
            f"{_fmt(s.get('saved_failure_rate'), pct=True)} |"
        )

    lines.extend(["", "## 5. Exit Timing", ""])
    lines.append("| policy | avg_exit_bar | median_exit_bar | early_exit_ratio |")
    lines.append("|---|---:|---:|---:|")
    for t in stats.get("exit_timing", []):
        lines.append(
            f"| {t.get('policy', '')} | {_fmt(t.get('avg_exit_bar'))} | "
            f"{_fmt(t.get('median_exit_bar'))} | {_fmt(t.get('early_exit_ratio'), pct=True)} |"
        )

    lines.extend(["", "## 6. Rule별 Exit 효과 (best policy per rule)", ""])
    for rule in ("RULE_A", "RULE_B", "RULE_C"):
        sub = [r for r in stats.get("rule_exit", []) if r.get("rule") == rule]
        if not sub:
            continue
        best = max(sub, key=lambda x: x.get("expectancy") or -999)
        lines.append(
            f"- {rule}: best={best.get('policy')} exp={_fmt(best.get('expectancy'))} "
            f"false_exit={_fmt(best.get('false_exit_rate'), pct=True)} "
            f"saved={_fmt(best.get('saved_failure_rate'), pct=True)}"
        )

    lines.extend(["", "## 7. Symbol별 Exit 효과", ""])
    for sym in sorted({r.get("symbol") for r in stats.get("symbol_exit", []) if r.get("symbol")}):
        sub = [r for r in stats.get("symbol_exit", []) if r.get("symbol") == sym]
        best = max(sub, key=lambda x: x.get("expectancy") or -999) if sub else {}
        lines.append(
            f"- {sym}: best={best.get('policy')} exp={_fmt(best.get('expectancy'))} "
            f"avg_return={_fmt(best.get('avg_return'), pct=True)}"
        )

    lines.extend(["", "## 8. Regime별 Exit 효과", ""])
    for reg in ("BULL", "SIDEWAYS", "BEAR"):
        sub = [r for r in stats.get("regime_exit", []) if r.get("regime") == reg]
        best = max(sub, key=lambda x: x.get("expectancy") or -999) if sub else {}
        lines.append(
            f"- {reg}: best={best.get('policy')} exp={_fmt(best.get('expectancy'))} "
            f"saved={_fmt(best.get('saved_failure_rate'), pct=True)}"
        )

    lines.extend(["", "## 9. Champion Policy Top 10", ""])
    lines.append("| rank | policy | score | expectancy | false_exit | saved_failure |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    for c in stats.get("champion_policies", []):
        lines.append(
            f"| {c.get('rank', '')} | {c.get('policy', '')} | {_fmt(c.get('score'))} | "
            f"{_fmt(c.get('expectancy'))} | {_fmt(c.get('false_exit_rate'), pct=True)} | "
            f"{_fmt(c.get('saved_failure_rate'), pct=True)} |"
        )

    lines.extend(["", "## 10. Worst Policy Top 10", ""])
    lines.append("| rank | policy | score | expectancy | false_exit | saved_failure |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    for w in stats.get("worst_policies", []):
        lines.append(
            f"| {w.get('rank', '')} | {w.get('policy', '')} | {_fmt(w.get('score'))} | "
            f"{_fmt(w.get('expectancy'))} | {_fmt(w.get('false_exit_rate'), pct=True)} | "
            f"{_fmt(w.get('saved_failure_rate'), pct=True)} |"
        )

    lines.extend(["", "## 11. Active Candidate Overlay", ""])
    lines.append("| rank | symbol | tf | rule | recommended | protection | risk |")
    lines.append("|---:|---|---|---|---|---:|---:|")
    for a in stats.get("active_candidates", [])[:15]:
        lines.append(
            f"| {a.get('rank', '')} | {a.get('symbol', '')} | {a.get('timeframe', '')} | "
            f"{a.get('rule', '')} | {a.get('recommended_policy', '')} | "
            f"{_fmt(a.get('expected_protection'), pct=True)} | {_fmt(a.get('risk_score'))} |"
        )

    lines.extend(["", "## 12. 현재 추적 우선순위", ""])
    for p in stats.get("observation_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"policy={p.get('recommended_policy')} protection={_fmt(p.get('expected_protection'), pct=True)}"
        )

    champ = stats.get("champion_policies", [{}])[0] if stats.get("champion_policies") else {}
    baseline = next((s for s in stats.get("policy_summary", []) if s.get("policy") == "NO_EXIT"), {})
    contrib = next((c for c in stats.get("contribution", []) if c.get("policy") == champ.get("policy")), {})

    lines.extend(["", "## 13. 핵심 결론", ""])
    lines.append(
        f"**Champion: {champ.get('policy', '—')}** (score {_fmt(champ.get('score'))}, "
        f"expectancy {_fmt(champ.get('expectancy'))}, false_exit {_fmt(champ.get('false_exit_rate'), pct=True)}, "
        f"saved_failure {_fmt(champ.get('saved_failure_rate'), pct=True)})."
    )
    lines.append(
        f"- Baseline NO_EXIT expectancy: {_fmt(baseline.get('expectancy'))} → "
        f"Champion delta: {_fmt(contrib.get('expectancy_delta'))}"
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_EXIT_POLICY_SIMULATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building exit policy simulation...")
    stats = full_exit_policy_summary()
    df = stats.get("export_df")
    if df is not None and not df.empty:
        df.to_csv(os.path.join(OUT_DIR, "wave_exit_policy_simulation.csv"), index=False)
        print(f"saved {len(df)} rows")
    else:
        import pandas as pd
        pd.DataFrame().to_csv(os.path.join(OUT_DIR, "wave_exit_policy_simulation.csv"), index=False)
        print("saved empty csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("exit policy simulation sweep complete")


if __name__ == "__main__":
    main()
