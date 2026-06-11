"""종합 판정(verdict) 타임라인 백트레이스 — 룩어헤드 없이 봉별 재계산.

실행: python validation/verdict_sweep.py [--stride N]
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.dynamics_rules import evaluate_transitions
from data.binance import get_auto_limit
from display.asof import (
    analyze_wave_energy_asof,
    build_ohlcv_cache,
    fetch_ohlcv_bare,
    run_indicator_pipeline,
    truncate_to_asof,
)
from validation.verdict_categories import (
    CATEGORY_COLORS,
    CATEGORY_ORDER,
    is_buy_category,
    verdict_category,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# MA240 워밍업 — 이보다 이른 봉은 파이프라인 재계산 불가(룩어헤드 스윕 제외).
MA_WARMUP_BARS = 240

SWEEP_TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]


def _headline_fields(report):
    dyn = report.dynamics
    if dyn is None or dyn.headline is None:
        return "", "", ""
    h = dyn.headline
    rule_id = getattr(h, "rule_id", "") or ""
    if hasattr(h, "bullish"):
        direction = "상방" if h.bullish else "하방"
    else:
        direction = ""
    desc = getattr(h, "description", "") or ""
    return rule_id, direction, desc


def _regime(report) -> str:
    if report.dynamics is not None and report.dynamics.regime:
        return report.dynamics.regime
    if report.trend.valid:
        if report.trend.direction == "상승":
            return "UP"
        if report.trend.direction == "하락":
            return "DOWN"
    return "판단불가"


def sweep_symbol_interval(
    symbol: str,
    interval: str,
    ohlcv_cache: dict,
    bare: pd.DataFrame,
    stride: int = 1,
) -> pd.DataFrame:
    rows = []
    hit_times = []
    start = min(MA_WARMUP_BARS, len(bare) - 1)
    indices = range(start, len(bare), max(int(stride), 1))

    for i in indices:
        as_of = bare.index[i]
        report = analyze_wave_energy_asof(symbol, interval, as_of, ohlcv_cache)
        cat = verdict_category(report.verdict)
        rule_id, direction, hdesc = _headline_fields(report)
        cut = truncate_to_asof(bare, as_of)
        base_df = run_indicator_pipeline(cut)
        for th in evaluate_transitions(base_df):
            if th.bar_index == as_of:
                hit_times.append(as_of)
        rows.append({
            "timestamp": as_of,
            "trend_1d": report.trend.direction if report.trend.valid else "검증불가",
            "verdict": report.verdict,
            "category": cat,
            "regime": _regime(report),
            "headline_rule_id": rule_id,
            "headline_direction": direction,
            "headline_description": hdesc,
        })

    df = pd.DataFrame(rows)
    df.attrs["hit_times"] = hit_times
    return df


def state_transitions(timeline: pd.DataFrame) -> pd.DataFrame:
    if timeline.empty:
        return timeline
    changes = []
    prev = None
    for _, row in timeline.iterrows():
        cur = row["category"]
        if prev is not None and cur != prev:
            changes.append({
                "timestamp": row["timestamp"],
                "from_category": prev,
                "to_category": cur,
                "verdict": row["verdict"],
            })
        prev = cur
    return pd.DataFrame(changes)


def sanity_last_bar(symbol: str, interval: str, timeline: pd.DataFrame, ohlcv_cache: dict) -> None:
    last_ts = timeline["timestamp"].iloc[-1]
    sweep_verdict = timeline["verdict"].iloc[-1]
    live = analyze_wave_energy_asof(symbol, interval, last_ts, ohlcv_cache)
    assert live.verdict == sweep_verdict, (
        f"sanity fail {symbol} {interval}: sweep={sweep_verdict!r} live={live.verdict!r}"
    )


def plot_verdict_timeline(symbol: str, interval: str, timeline: pd.DataFrame, bare: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(16, 6))
    close = bare["close"].astype(float)
    ax.plot(bare.index, close, color="#333333", linewidth=0.8, label="close")

    t1 = bare.index[-1]
    seg_start = None
    prev_cat = None
    for _, row in timeline.iterrows():
        ts, cat = row["timestamp"], row["category"]
        if seg_start is None:
            seg_start, prev_cat = ts, cat
            continue
        if cat != prev_cat:
            ax.axvspan(seg_start, ts, color=CATEGORY_COLORS.get(prev_cat, "#eee"), alpha=0.25)
            seg_start, prev_cat = ts, cat
    if seg_start is not None and prev_cat is not None:
        ax.axvspan(seg_start, t1, color=CATEGORY_COLORS.get(prev_cat, "#eee"), alpha=0.25)

    for ht in timeline.attrs.get("hit_times", []):
        ax.axvline(ht, color="#1565c0", linewidth=0.6, alpha=0.7)

    ax.set_title(f"{symbol} {interval} — verdict timeline")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, f"verdict_{symbol}_{interval}.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def write_report(sections: list) -> str:
    path = os.path.join(OUT_DIR, "REPORT_VERDICT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stride", type=int, default=1, help="평가 stride (기본 1)")
    args = parser.parse_args()

    report_lines = [
        "# REPORT_VERDICT",
        "",
        f"- stride: {args.stride}",
        "",
    ]

    for symbol, interval, limit in SWEEP_TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            raise RuntimeError(f"fetch failed {symbol} {interval}")
        extra = {"4h": lim} if interval == "4h" else {}
        cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)

        timeline = sweep_symbol_interval(symbol, interval, cache, bare, stride=args.stride)
        timeline.attrs["hit_times"] = timeline.attrs.get("hit_times", [])

        sanity_last_bar(symbol, interval, timeline, cache)

        csv_path = os.path.join(OUT_DIR, f"verdict_timeline_{symbol}_{interval}.csv")
        timeline.to_csv(csv_path, index=False)

        trans = state_transitions(timeline)
        trans_path = os.path.join(OUT_DIR, f"verdict_transitions_{symbol}_{interval}.csv")
        trans.to_csv(trans_path, index=False)

        png = plot_verdict_timeline(symbol, interval, timeline, bare)

        report_lines.append(f"## {symbol} {interval}")
        report_lines.append("")
        report_lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        report_lines.append(f"- transitions: `{os.path.basename(trans_path)}`")
        report_lines.append(f"- PNG: `{os.path.basename(png)}`")
        report_lines.append(f"- 평가 봉 수: {len(timeline)}")
        report_lines.append("")
        report_lines.append("### 카테고리별 비율")
        report_lines.append("")
        counts = timeline["category"].value_counts()
        total = len(timeline) or 1
        for cat in CATEGORY_ORDER:
            n = int(counts.get(cat, 0))
            if n:
                report_lines.append(f"- {cat}: {n} ({n / total * 100:.1f}%)")
        report_lines.append("")

        report_lines.append("### 상태 전환 목록")
        report_lines.append("")
        if trans.empty:
            report_lines.append("- (없음)")
        else:
            for _, r in trans.iterrows():
                ts = pd.Timestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M")
                report_lines.append(
                    f"- {ts}: {r['from_category']} → {r['to_category']}"
                )
        report_lines.append("")

        buy_segs = trans[trans["to_category"].map(is_buy_category)]
        report_lines.append("### 매수 계열 진입 전환")
        report_lines.append("")
        if buy_segs.empty:
            report_lines.append("- (없음)")
        else:
            for _, r in buy_segs.iterrows():
                ts = pd.Timestamp(r["timestamp"])
                regime = timeline.loc[timeline["timestamp"] == ts, "regime"]
                reg = regime.iloc[0] if len(regime) else "-"
                report_lines.append(
                    f"- {ts.strftime('%Y-%m-%d %H:%M')} · "
                    f"{r['from_category']}→{r['to_category']} · regime={reg}"
                )
        report_lines.append("")

        if symbol == "ETHUSDT" and interval == "4h":
            report_lines.append("### 1월 UP 구간 verdict 추이 (2026-01-13 ~ 2026-01-31)")
            report_lines.append("")
            jan = timeline[
                (timeline["timestamp"] >= "2026-01-13")
                & (timeline["timestamp"] <= "2026-01-31 23:59:59")
            ]
            for _, r in jan.iterrows():
                ts = pd.Timestamp(r["timestamp"]).strftime("%m-%d %H:%M")
                vshort = r["verdict"][:50] + ("..." if len(r["verdict"]) > 50 else "")
                report_lines.append(
                    f"- {ts} · {r['category']} · regime={r['regime']} · {vshort}"
                )
            report_lines.append("")

    report_lines.append("## sanity")
    report_lines.append("")
    report_lines.append("- 각 조합 마지막 봉: 스윕 verdict == as-of 재계산 verdict (assert 통과)")
    report_lines.append("")
    report_lines.append("## Playwright 파리티")
    report_lines.append("")
    parity_path = os.path.join(OUT_DIR, "REPORT_VERDICT_PARITY.md")
    if os.path.isfile(parity_path):
        report_lines.append(f"- 상세: `{os.path.basename(parity_path)}` (별도 실행)")
    else:
        report_lines.append("- `python validation/verdict_playwright.py` (Streamlit 기동 후)")
    report_lines.append("")

    write_report(report_lines)
    print("verdict sweep complete")


if __name__ == "__main__":
    main()
