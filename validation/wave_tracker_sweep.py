"""Wave Tracker 타임라인 스윕 · REPORT_WAVE_TRACKER.md.

실행: python validation/wave_tracker_sweep.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from analysis.wave_tracker import ALL_STATES, run_timeline
from data.binance import get_auto_limit
from display.asof import build_ohlcv_cache, fetch_ohlcv_bare

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MA_WARMUP_BARS = 240

SWEEP_TARGETS = [
    ("ETHUSDT", "4h", 1600),
    ("BTCUSDT", "1d", None),
]


def _spell_stats(states: list[str]) -> dict[str, dict]:
    if not states:
        return {}
    spells: list[tuple[str, int]] = []
    cur = states[0]
    n = 1
    for s in states[1:]:
        if s == cur:
            n += 1
        else:
            spells.append((cur, n))
            cur, n = s, 1
    spells.append((cur, n))

    by_state: dict[str, list[int]] = {st: [] for st in ALL_STATES}
    for st, length in spells:
        if st in by_state:
            by_state[st].append(length)

    out = {}
    for st in ALL_STATES:
        lengths = by_state[st]
        if not lengths:
            out[st] = {"count": 0, "mean": 0.0, "max": 0}
        else:
            s = pd.Series(lengths, dtype=float)
            out[st] = {"count": len(lengths), "mean": float(s.mean()), "max": int(s.max())}
    return out


def _db_episode_outcomes(timeline: pd.DataFrame) -> dict:
    """DOUBLE_BOTTOM_CANDIDATE 에피소드 → 이후 첫 도달 상태."""
    states = timeline["state"].tolist()
    outcomes = {"completed": 0, "triple_required": 0, "triple_confirmed": 0, "invalidated": 0, "other": 0}
    db_total = 0
    i = 0
    while i < len(states):
        if states[i] != "DOUBLE_BOTTOM_CANDIDATE":
            i += 1
            continue
        db_total += 1
        j = i + 1
        hit = "other"
        while j < len(states):
            s = states[j]
            if s == "WAVE3_COMPLETED":
                hit = "completed"
                break
            if s == "TRIPLE_BOTTOM_REQUIRED":
                hit = "triple_required"
                break
            if s == "TRIPLE_BOTTOM_CONFIRMED":
                hit = "triple_confirmed"
                break
            if s == "INVALIDATED":
                hit = "invalidated"
                break
            if s == "DOUBLE_BOTTOM_CANDIDATE" and j > i + 1:
                break
            j += 1
        outcomes[hit] += 1
        i = j if j > i else i + 1

    inv_bars = int((timeline["state"] == "INVALIDATED").sum())
    total_bars = len(timeline) or 1
    return {
        "db_episodes": db_total,
        "outcomes": outcomes,
        "invalidated_bars": inv_bars,
        "invalidated_ratio": inv_bars / total_bars,
    }


def write_report(sections: list[str]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_WAVE_TRACKER.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
    return path


def main():
    lines = ["# REPORT_WAVE_TRACKER", "", "대파동 3파 하락 종료 추적 (가설 레이어)", ""]

    for symbol, interval, limit in SWEEP_TARGETS:
        lim = limit if limit is not None else get_auto_limit(interval)
        bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            raise RuntimeError(f"fetch failed {symbol} {interval}")
        extra = {"4h": lim} if interval == "4h" else {}
        cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)

        timeline = run_timeline(symbol, interval, bare, cache, warmup=MA_WARMUP_BARS)
        csv_path = os.path.join(OUT_DIR, f"wave_tracker_{symbol}_{interval}.csv")
        timeline.to_csv(csv_path, index=False)

        stats = _spell_stats(timeline["state"].tolist())
        ep = _db_episode_outcomes(timeline)

        lines.append(f"## {symbol} {interval}")
        lines.append("")
        lines.append(f"- CSV: `{os.path.basename(csv_path)}`")
        lines.append(f"- 평가 봉 수: {len(timeline)}")
        lines.append("")

        lines.append("### 상태별 spell")
        lines.append("")
        lines.append("| state | 발생 횟수 | 평균 지속(봉) | 최대 지속(봉) |")
        lines.append("|---|---:|---:|---:|")
        for st in ALL_STATES:
            s = stats[st]
            if s["count"]:
                lines.append(f"| {st} | {s['count']} | {s['mean']:.1f} | {s['max']} |")
        lines.append("")

        db_n = ep["db_episodes"]
        oc = ep["outcomes"]
        lines.append("### DB 에피소드 결과")
        lines.append("")
        lines.append(f"- DOUBLE_BOTTOM_CANDIDATE 에피소드: {db_n}")
        if db_n:
            lines.append(
                f"- DB → WAVE3_COMPLETED: {oc['completed']}/{db_n} "
                f"({oc['completed']/db_n*100:.1f}%)"
            )
            lines.append(
                f"- DB → TRIPLE_BOTTOM_REQUIRED: {oc['triple_required']}/{db_n} "
                f"({oc['triple_required']/db_n*100:.1f}%)"
            )
            lines.append(
                f"- DB → TRIPLE_BOTTOM_CONFIRMED (직접): {oc['triple_confirmed']}/{db_n} "
                f"({oc['triple_confirmed']/db_n*100:.1f}%)"
            )
            lines.append(
                f"- DB → INVALIDATED: {oc['invalidated']}/{db_n} "
                f"({oc['invalidated']/db_n*100:.1f}%)"
            )
        lines.append(
            f"- INVALIDATED 봉 비율: {ep['invalidated_ratio']*100:.1f}% "
            f"({ep['invalidated_bars']}/{len(timeline)})"
        )
        lines.append("")

    write_report(lines)
    print("wave tracker sweep complete")


if __name__ == "__main__":
    main()
