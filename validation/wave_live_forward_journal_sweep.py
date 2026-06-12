"""Wave Live Forward Journal 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_live_forward_journal import CSV_EXPORT_COLS, full_forward_journal_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_live_forward_journal.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    cands = stats.get("active_candidates", [])[:8]
    ax = axes[0, 0]
    if cands:
        labels = [f"{c['symbol'][:3]}/{c['timeframe']}\n{c['rule'][-1]}" for c in cands]
        vals = [c.get("watchlist_score") or 0 for c in cands]
        ax.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.invert_yaxis()
        ax.set_title("Active Candidates (watchlist score)")
    else:
        ax.text(0.5, 0.5, "no active", ha="center")

    rule_sum = stats.get("rule_summary", [])
    ax2 = axes[0, 1]
    if rule_sum:
        rules = [r["rule"] for r in rule_sum]
        x = np.arange(len(rules))
        w = 0.2
        for i, h in enumerate((5, 10, 20, 40)):
            vals = [r.get(f"win_rate_{h}") or 0 for r in rule_sum]
            ax2.bar(x + i * w, vals, width=w, label=f"+{h}")
        ax2.set_xticks(x + w * 1.5)
        ax2.set_xticklabels(rules)
        ax2.set_title("Rule Forward Win Rate (%)")
        ax2.legend(fontsize=7)
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    journal = stats.get("journal")
    ax3 = axes[1, 0]
    if journal is not None and not journal.empty:
        status_counts = journal["status"].value_counts()
        ax3.pie(
            status_counts.values,
            labels=status_counts.index,
            autopct="%1.0f%%",
            textprops={"fontsize": 7},
        )
        ax3.set_title("Pending / Completed")
    else:
        ax3.text(0.5, 0.5, "no data", ha="center")

    h1h4 = stats.get("compare_1h_4h", [])
    ax4 = axes[1, 1]
    if h1h4:
        labels = [r["timeframe"] for r in h1h4]
        for h in (5, 20, 40):
            vals = [r.get(f"avg_return_{h}") or 0 for r in h1h4]
            ax4.plot(labels, vals, marker="o", label=f"+{h}")
        ax4.axhline(0, color="gray", linewidth=0.8)
        ax4.set_title("1h vs 4h Avg Return (%)")
        ax4.legend(fontsize=7)
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Live Forward Journal")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    journal = stats.get("journal")
    lines = [
        "# REPORT — Wave Live Forward Journal",
        "",
        f"총 이벤트: {len(journal) if journal is not None and not journal.empty else 0}",
        f"Pending: {stats.get('pending_count', 0)} | Completed: {stats.get('completed_count', 0)}",
        f"Active/Recent 후보: {stats.get('active_recent_count', 0)}",
        "",
        "## 1. Active / Recent 후보",
        "",
        "| symbol | tf | rule | bars_since | status | pending | score |",
        "|---|---|---|---:|---|---:|---:|",
    ]
    for c in stats.get("active_candidates", []):
        lines.append(
            f"| {c.get('symbol', '')} | {c.get('timeframe', '')} | {c.get('rule', '')} | "
            f"{c.get('bars_since_signal', '')} | {c.get('status', '')} | "
            f"{c.get('pending_horizon') or '—'} | {_fmt(c.get('watchlist_score'))} |"
        )
    if not stats.get("active_candidates"):
        lines.append("| — | — | — | — | — | — | — |")

    lines.extend(["", "## 2. Rule별 Forward 성과", ""])
    lines.append("| rule | n | completed | pending | wr5 | wr10 | wr20 | wr40 | avg20 | avg40 | backtest | delta |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in stats.get("rule_summary", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('n', 0)} | {r.get('completed_n', 0)} | "
            f"{r.get('pending_n', 0)} | {_fmt(r.get('win_rate_5'), pct=True)} | "
            f"{_fmt(r.get('win_rate_10'), pct=True)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('win_rate_40'), pct=True)} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} | {_fmt(r.get('backtest_expect_20'), pct=True)} | "
            f"{_fmt(r.get('delta_vs_backtest'), pct=True)} |"
        )

    lines.extend(["", "## 3. Symbol별 Forward 성과", ""])
    lines.append("| symbol | n | completed | wr20 | avg20 | avg40 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in stats.get("symbol_summary", []):
        lines.append(
            f"| {r.get('symbol', '')} | {r.get('n', 0)} | {r.get('completed_n', 0)} | "
            f"{_fmt(r.get('win_rate_20'), pct=True)} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 4. Timeframe별 Forward 성과", ""])
    lines.append("| tf | n | completed | wr20 | avg20 | avg40 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in stats.get("timeframe_summary", []):
        lines.append(
            f"| {r.get('timeframe', '')} | {r.get('n', 0)} | {r.get('completed_n', 0)} | "
            f"{_fmt(r.get('win_rate_20'), pct=True)} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 5. Pending 이벤트", ""])
    if journal is not None and not journal.empty:
        pend = journal[journal["status"] != "COMPLETED"].groupby("status").size()
        for st, cnt in pend.items():
            lines.append(f"- {st}: {cnt}")
    else:
        lines.append("_없음_")

    lines.extend(["", "## 6. Completed 이벤트", ""])
    lines.append(f"- COMPLETED: {stats.get('completed_count', 0)}")

    lines.extend(["", "## 7. Failure Cause 분포", ""])
    lines.append("| cause | count | pct |")
    lines.append("|---|---:|---:|")
    for f in stats.get("failure_causes", []):
        lines.append(
            f"| {f.get('failure_cause', '')} | {f.get('count', 0)} | {_fmt(f.get('pct'), pct=True)} |"
        )
    if not stats.get("failure_causes"):
        lines.append("| — | 0 | — |")

    lines.extend(["", "## 8. 현재 추적 우선순위", ""])
    for p in stats.get("tracking_priority", [])[:10]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} {p.get('rule')} "
            f"({p.get('freshness')}) status={p.get('status')} score={_fmt(p.get('watchlist_score'))}"
        )

    lines.extend(["", "## 9. 1h vs 4h 비교", ""])
    lines.append("| tf | n | wr5 | wr20 | avg5 | avg20 | avg40 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in stats.get("compare_1h_4h", []):
        lines.append(
            f"| {r.get('timeframe', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('win_rate_5'), pct=True)} | {_fmt(r.get('win_rate_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_5'), pct=True)} | {_fmt(r.get('avg_return_20'), pct=True)} | "
            f"{_fmt(r.get('avg_return_40'), pct=True)} |"
        )

    lines.extend(["", "## 10. 핵심 Live Forward Pattern", ""])
    for r in stats.get("rule_summary", []):
        delta = r.get("delta_vs_backtest")
        align = "일치" if delta is not None and abs(delta) < 1.5 else "불일치"
        lines.append(
            f"- **{r.get('rule')}**: live avg20={_fmt(r.get('avg_return_20'), pct=True)}, "
            f"backtest={_fmt(r.get('backtest_expect_20'), pct=True)}, delta={_fmt(delta, pct=True)} → {align}"
        )
    lines.append("")
    lines.append(
        "Journal 체계로 live 발생 후 forward 결과를 지속 추적하며, "
        "백테스트 기대와의 괴리를 모니터링한다."
    )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_LIVE_FORWARD_JOURNAL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building live forward journal...")
    stats = full_forward_journal_summary()
    journal = stats.get("journal")
    if journal is not None and not journal.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in journal.columns]
        journal[cols].to_csv(os.path.join(OUT_DIR, "wave_live_forward_journal.csv"), index=False)
        print(f"saved {len(journal)} journal rows")
    else:
        import pandas as pd
        pd.DataFrame(columns=list(CSV_EXPORT_COLS)).to_csv(
            os.path.join(OUT_DIR, "wave_live_forward_journal.csv"), index=False,
        )
        print("saved empty journal csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("live forward journal sweep complete")


if __name__ == "__main__":
    main()
