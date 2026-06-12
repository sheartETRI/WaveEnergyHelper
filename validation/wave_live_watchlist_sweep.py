"""Wave Live Watchlist 스윕 · REPORT · PNG."""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_live_watchlist import CSV_EXPORT_COLS, full_live_watchlist_summary

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _fmt(v, d=2, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if pct:
        return f"{v:.{d}f}%"
    return f"{v:.{d}f}"


def _plot(stats: dict) -> str:
    path = os.path.join(OUT_DIR, "wave_live_watchlist.png")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    ranking = stats.get("ranking", [])[:10]
    ax = axes[0, 0]
    if ranking:
        labels = [f"{r['symbol'][:3]}/{r['timeframe']}\n{r['rule'][-1]}" for r in ranking]
        vals = [r.get("score") or 0 for r in ranking]
        ax.barh(range(len(labels)), vals, color="#1565C0", alpha=0.85)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=7)
        ax.invert_yaxis()
        ax.set_title("Watchlist Ranking (top 10)")
    else:
        ax.text(0.5, 0.5, "no data", ha="center")

    heatmap = stats.get("heatmap", [])
    ax2 = axes[0, 1]
    syms = ["ETH", "BTC", "SOL", "BNB"]
    tfs = ["1h", "4h", "1d"]
    state_map = {"NONE": 0, "RULE_C": 1, "RULE_A": 2, "RULE_B": 3}
    mat = np.zeros((len(syms), len(tfs)))
    if heatmap:
        for h in heatmap:
            si = next((i for i, s in enumerate(syms) if h["symbol"].startswith(s)), None)
            ti = tfs.index(h["timeframe"]) if h["timeframe"] in tfs else None
            if si is not None and ti is not None:
                mat[si, ti] = state_map.get(h.get("state", "NONE"), 0)
        im = ax2.imshow(mat, aspect="auto", cmap="YlOrRd", vmin=0, vmax=3)
        ax2.set_xticks(range(len(tfs)))
        ax2.set_xticklabels(tfs)
        ax2.set_yticks(range(len(syms)))
        ax2.set_yticklabels(syms)
        ax2.set_title("Symbol/TF Heatmap")
        fig.colorbar(im, ax=ax2, ticks=[0, 1, 2, 3], label="NONE/C/A/B")
    else:
        ax2.text(0.5, 0.5, "no data", ha="center")

    events = stats.get("events")
    ax3 = axes[1, 0]
    if events is not None and not events.empty:
        recent = events.sort_values("timestamp").tail(40)
        colors = {"RULE_A": "#1565C0", "RULE_B": "#2E7D32", "RULE_C": "#E65100"}
        y_pos = range(len(recent))
        for i, (_, row) in enumerate(recent.iterrows()):
            c = colors.get(row["rule"], "gray")
            ax3.barh(i, row.get("watchlist_score") or 0, color=c, alpha=0.8)
        ax3.set_yticks([])
        ax3.set_title("Recent Events Timeline (watchlist score)")
        ax3.set_xlabel("watchlist_score")
    else:
        ax3.text(0.5, 0.5, "no events", ha="center")

    fwd = [r for r in stats.get("forward_tracking", []) if "rule" not in r]
    ax4 = axes[1, 1]
    if fwd:
        hs = [r["horizon_bars"] for r in fwd]
        avgs = [r.get("avg_return") or 0 for r in fwd]
        ax4.plot(hs, avgs, marker="o", color="#6A1B9A")
        ax4.axhline(0, color="gray", linewidth=0.8)
        ax4.set_title("Forward Tracking (avg return %)")
        ax4.set_xlabel("bars")
    else:
        ax4.text(0.5, 0.5, "no data", ha="center")

    fig.suptitle("Wave Live Watchlist — RULE_A/B/C Observation")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_report(stats: dict, png: str) -> None:
    lines = [
        "# REPORT — Wave Live Watchlist",
        "",
        f"기준 시점: {stats.get('ref_timestamp', '—')}",
        f"스캔 봉수: {stats.get('scan_bars', 500)}",
        f"총 이벤트: {stats.get('total_events', 0)}",
        f"ACTIVE 이벤트: {stats.get('active_event_count', 0)}",
        "",
        "## 1. 최근 발생 빈도 (30/90/180일)",
        "",
        "| rule | symbol | tf | 30d | 90d | 180d |",
        "|---|---|---|---:|---:|---:|",
    ]
    for r in stats.get("frequency", []):
        lines.append(
            f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
            f"{r.get('count_30d', 0)} | {r.get('count_90d', 0)} | {r.get('count_180d', 0)} |"
        )
    lines.extend(["", "## 2. Rule 발생률 (avg bars between events)", ""])
    lines.append("| rule | symbol | tf | events | avg_bars |")
    lines.append("|---|---|---|---:|---:|")
    for r in stats.get("bars_between", []):
        if r.get("avg_bars_between") is not None:
            lines.append(
                f"| {r.get('rule', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
                f"{r.get('event_count', 0)} | {_fmt(r.get('avg_bars_between'), 1)} |"
            )
    agg: dict = {}
    for r in stats.get("bars_between", []):
        rule = r.get("rule", "")
        if r.get("avg_bars_between") is not None:
            agg.setdefault(rule, []).append(r["avg_bars_between"])
    lines.append("")
    for rule, vals in agg.items():
        lines.append(f"- **{rule}**: 평균 {_fmt(float(np.mean(vals)), 1)}봉마다 1회 (셀 평균)")

    lines.extend(["", "## 3. Active Candidates", ""])
    cands = stats.get("candidates", [])
    if cands:
        lines.append("| symbol | tf | rule | watchlist_score | bars_since | freshness |")
        lines.append("|---|---|---|---:|---:|---|")
        for c in cands:
            lines.append(
                f"| {c.get('symbol', '')} | {c.get('timeframe', '')} | {c.get('rule', '')} | "
                f"{_fmt(c.get('watchlist_score'))} | {c.get('bars_since_signal', '')} | {c.get('freshness', '')} |"
            )
    else:
        lines.append("_현재 ACTIVE/RECENT 후보 없음_")

    lines.extend(["", "## 4. Watchlist Ranking", ""])
    lines.append("| rank | symbol | tf | rule | score |")
    lines.append("|---:|---|---|---|---:|")
    for r in stats.get("ranking", [])[:15]:
        lines.append(
            f"| {r.get('rank', '')} | {r.get('symbol', '')} | {r.get('timeframe', '')} | "
            f"{r.get('rule', '')} | {_fmt(r.get('score'))} |"
        )

    lines.extend(["", "## 5. Symbol/TF Heatmap", ""])
    lines.append("| symbol | tf | state |")
    lines.append("|---|---|---|")
    for h in stats.get("heatmap", []):
        lines.append(f"| {h.get('symbol', '')} | {h.get('timeframe', '')} | {h.get('state', '')} |")

    lines.extend(["", "## 6. Freshness", ""])
    lines.append("| symbol | tf | rule | freshness | bars_since |")
    lines.append("|---|---|---|---|---:|")
    for f in stats.get("freshness", []):
        if f.get("freshness") != "NONE":
            lines.append(
                f"| {f.get('symbol', '')} | {f.get('timeframe', '')} | {f.get('rule', '')} | "
                f"{f.get('freshness', '')} | {f.get('bars_since_signal', '—')} |"
            )

    lines.extend(["", "## 7. Forward Tracking", ""])
    lines.append("| horizon | n | avg_return | max | min |")
    lines.append("|---:|---:|---:|---:|---:|")
    for r in stats.get("forward_tracking", []):
        if "rule" in r:
            continue
        lines.append(
            f"| +{r.get('horizon_bars', '')} | {r.get('n', 0)} | "
            f"{_fmt(r.get('avg_return'), pct=True)} | {_fmt(r.get('max_return'), pct=True)} | "
            f"{_fmt(r.get('min_return'), pct=True)} |"
        )

    lines.extend(["", "## 8. 실시간 관측 우선순위", ""])
    for p in stats.get("observation_priority", [])[:8]:
        lines.append(
            f"- #{p.get('rank')} {p.get('symbol')} {p.get('timeframe')} "
            f"{p.get('rule')} score={_fmt(p.get('score'))} heatmap={p.get('heatmap_state')}"
        )

    strongest = stats.get("strongest_candidate")
    lines.extend(["", "## 9. 현재 최강 후보", ""])
    if strongest:
        lines.append(
            f"**{strongest.get('symbol')} {strongest.get('timeframe')} {strongest.get('rule')}** — "
            f"score={_fmt(strongest.get('score'))}, watchlist={_fmt(strongest.get('watchlist_score'))}, "
            f"freshness={strongest.get('freshness')}, bars_since={strongest.get('bars_since_signal')}"
        )
    else:
        lines.append("_후보 없음_")

    lines.extend(["", "## 10. 결론", ""])
    total = stats.get("total_events", 0)
    active = stats.get("active_event_count", 0)
    cands_n = len(cands)
    lines.append(
        f"최근 500봉 스캔에서 RULE_A/B/C 이벤트 **{total}건** (ACTIVE **{active}건**). "
        f"관측 후보(ACTIVE/RECENT) **{cands_n}건**."
    )
    if cands_n > 0:
        lines.append(
            "현재 시장에서 RULE_A/B는 간헐적으로 발생하며, 관찰할 만한 후보가 존재한다."
        )
    else:
        lines.append(
            "현재 시장에서 즉시 관찰할 ACTIVE/RECENT 후보는 없으나, "
            "히스토리 스캔으로 발생 패턴은 확인 가능하다."
        )
    lines.append("")
    lines.append(f"- PNG: `{os.path.basename(png)}`")
    lines.append("")

    with open(os.path.join(OUT_DIR, "REPORT_WAVE_LIVE_WATCHLIST.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("building live watchlist analysis...")
    stats = full_live_watchlist_summary()
    events = stats.get("events")
    if events is not None and not events.empty:
        cols = [c for c in CSV_EXPORT_COLS if c in events.columns]
        events[cols].to_csv(os.path.join(OUT_DIR, "wave_live_watchlist.csv"), index=False)
        print(f"saved {len(events)} events")
    else:
        pd = __import__("pandas")
        pd.DataFrame(columns=list(CSV_EXPORT_COLS)).to_csv(
            os.path.join(OUT_DIR, "wave_live_watchlist.csv"), index=False,
        )
        print("saved empty events csv")

    png = _plot(stats)
    _write_report(stats, png)
    print("live watchlist sweep complete")


if __name__ == "__main__":
    main()
