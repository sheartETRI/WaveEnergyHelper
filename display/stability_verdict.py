"""Stability Verdict 표시 레이어 — 엔진/CSV/REPORT 변경 없음."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from analysis.verdict_stability import (
    BUY_FAMILY,
    SELL_FAMILY,
    enrich_timeline_stability,
)
from display.asof import analyze_wave_energy_asof
from validation.verdict_categories import verdict_category

MA_WARMUP_BARS = 240
LOOKBACK_BARS = 200
TRANSITION_LOG_LIMIT = 50
STABLE_COL = "family_smoothed_3"

STRIP_COLORS = {
    BUY_FAMILY: "#4CAF50",
    SELL_FAMILY: "#EF5350",
    "NEUTRAL": "#BDBDBD",
}

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


def _timeline_csv_path(symbol: str, interval: str) -> str:
    return os.path.join(_VALIDATION_DIR, f"verdict_timeline_{symbol}_{interval}.csv")


def count_transitions(seq: list) -> int:
    if len(seq) <= 1:
        return 0
    return sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])


def _spell_lengths(seq: list) -> list[int]:
    if not seq:
        return []
    out: list[int] = []
    cur = seq[0]
    n = 1
    for v in seq[1:]:
        if v == cur:
            n += 1
        else:
            out.append(n)
            cur, n = v, 1
    out.append(n)
    return out


def spell_summary(seq: list) -> dict:
    spells = _spell_lengths(seq)
    if not spells:
        return {"transitions": 0, "mean": 0.0, "median": 0.0, "max": 0, "le2_ratio": 0.0}
    s = pd.Series(spells, dtype=float)
    return {
        "transitions": count_transitions(seq),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "max": int(s.max()),
        "le2_ratio": float((s <= 2).mean()),
    }


def duration_at(seq: list, idx: int) -> int:
    if idx < 0 or idx >= len(seq):
        return 0
    val = seq[idx]
    n = 1
    j = idx - 1
    while j >= 0 and seq[j] == val:
        n += 1
        j -= 1
    return n


def build_category_timeline(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
    ohlcv_cache: dict,
) -> pd.DataFrame:
    """봉별 category 타임라인 (표시 전용). CSV가 있으면 우선 사용."""
    if df is None or df.empty:
        return pd.DataFrame()

    csv_map: dict[pd.Timestamp, dict] = {}
    csv_path = _timeline_csv_path(symbol, interval)
    if os.path.isfile(csv_path):
        tl = pd.read_csv(csv_path, parse_dates=["timestamp"])
        for _, r in tl.iterrows():
            csv_map[pd.Timestamp(r["timestamp"])] = r.to_dict()

    start = min(MA_WARMUP_BARS, len(df) - 1)
    rows = []
    for i in range(start, len(df)):
        ts = pd.Timestamp(df.index[i])
        if ts in csv_map:
            hit = csv_map[ts]
            cat = hit.get("category") or verdict_category(str(hit.get("verdict", "")))
            rows.append({
                "timestamp": ts,
                "verdict": hit.get("verdict", ""),
                "category": cat,
            })
        else:
            report = analyze_wave_energy_asof(symbol, interval, ts, ohlcv_cache)
            rows.append({
                "timestamp": ts,
                "verdict": report.verdict,
                "category": verdict_category(report.verdict),
            })
    return pd.DataFrame(rows)


def build_stability_enriched_live(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
    ohlcv_cache: dict,
) -> pd.DataFrame:
    timeline = build_category_timeline(symbol, interval, df, ohlcv_cache)
    if timeline.empty:
        return timeline
    return enrich_timeline_stability(timeline)


@st.cache_data(show_spinner=False, ttl=3600)
def build_stability_enriched_cached(
    symbol: str,
    interval: str,
    as_of_iso: str,
    index_tuple: tuple,
) -> pd.DataFrame:
    """비 as-of 경로 캐시 — df 인덱스만으로 재조립."""
    from data.binance import get_auto_limit
    from display.asof import build_ohlcv_cache, fetch_ohlcv_bare, parse_as_of, truncate_to_asof

    limit = get_auto_limit(interval)
    if as_of_iso and symbol == "ETHUSDT" and interval == "4h":
        limit = 1600
    full = fetch_ohlcv_bare(symbol, interval, limit, paginated=limit > 1000)
    if full is None or full.empty:
        return pd.DataFrame()
    if as_of_iso:
        as_of = parse_as_of(as_of_iso)
        if as_of is not None:
            full = truncate_to_asof(full, as_of)
    idx = pd.DatetimeIndex(index_tuple)
    full = full.loc[full.index.isin(idx)]
    extra = {"4h": limit} if interval == "4h" else {}
    cache = build_ohlcv_cache(symbol, interval, full, extra_limits=extra)
    return build_stability_enriched_live(symbol, interval, full, cache)


def get_stability_enriched(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
    ohlcv_cache: dict,
    as_of_iso: str = "",
) -> pd.DataFrame:
    """as-of는 live 경로, 그 외 캐시."""
    if as_of_iso:
        return build_stability_enriched_live(symbol, interval, df, ohlcv_cache)
    return build_stability_enriched_cached(
        symbol, interval, as_of_iso, tuple(pd.Timestamp(t) for t in df.index),
    )


def align_enriched_to_index(enriched: pd.DataFrame, df_index: pd.Index) -> pd.DataFrame:
    if enriched.empty:
        return enriched
    keyed = enriched.set_index("timestamp")
    out = keyed.reindex(pd.DatetimeIndex(df_index))
    out.index.name = "timestamp"
    return out.reset_index()


def build_transition_log(
    timestamps: list,
    stable_seq: list,
    limit: int = TRANSITION_LOG_LIMIT,
) -> list[dict]:
    if len(stable_seq) <= 1:
        return []
    events = []
    spell_start = 0
    prev = stable_seq[0]
    for i in range(1, len(stable_seq)):
        if stable_seq[i] != prev:
            events.append({
                "timestamp": timestamps[i],
                "from_family": prev,
                "to_family": stable_seq[i],
                "duration": i - spell_start,
            })
            spell_start = i
            prev = stable_seq[i]
    return list(reversed(events[-limit:]))


def longest_spell(seq: list, target: str) -> int:
    best = 0
    cur = 0
    for v in seq:
        if v == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def render_stability_verdict_panel(aligned: pd.DataFrame) -> None:
    if aligned.empty or STABLE_COL not in aligned.columns:
        st.warning("Stability 데이터 없음")
        return

    valid = aligned.dropna(subset=["family", STABLE_COL])
    if valid.empty:
        st.warning("Stability 데이터 없음 (워밍업 구간)")
        return

    raw = valid["family"].tolist()
    stable = valid[STABLE_COL].tolist()
    ts_list = valid["timestamp"].tolist()

    look = min(LOOKBACK_BARS, len(raw))
    raw_lb = raw[-look:]
    stable_lb = stable[-look:]

    st.markdown("### Stability Verdict")
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Family", raw[-1])
    c2.metric("Current Stable Family", stable[-1])
    c3.metric("Family Duration", f"{duration_at(stable, len(stable) - 1)} bars")

    st.caption(
        f"Raw Family Changes: {count_transitions(raw_lb)} · "
        f"Stable Family Changes: {count_transitions(stable_lb)} "
        f"(last {look} bars)"
    )

    with st.expander("Stability Transition Log", expanded=False):
        for ev in build_transition_log(ts_list, stable):
            ts = pd.Timestamp(ev["timestamp"]).strftime("%Y-%m-%d")
            st.markdown(
                f"**{ts}**  \n"
                f"{ev['from_family']} → {ev['to_family']}  \n"
                f"duration: {ev['duration']} bars"
            )

    raw_st = spell_summary(raw_lb)
    stable_st = spell_summary(stable_lb)
    st.markdown("**Comparison (last 200 bars)**")
    st.table({
        "": ["Transitions", "Mean spell", "Max spell"],
        "Raw Family": [
            raw_st["transitions"],
            f"{raw_st['mean']:.1f}",
            raw_st["max"],
        ],
        "Stable Family": [
            stable_st["transitions"],
            f"{stable_st['mean']:.1f}",
            stable_st["max"],
        ],
    })


def compute_observation_metrics(aligned: pd.DataFrame, lookback: int = LOOKBACK_BARS) -> dict:
    if aligned.empty:
        return {}
    raw = aligned["family"].dropna().tail(lookback).tolist()
    stable = aligned[STABLE_COL].dropna().tail(lookback).tolist()
    rt = count_transitions(raw)
    st_t = count_transitions(stable)
    return {
        "lookback": len(raw),
        "raw_transitions": rt,
        "stable_transitions": st_t,
        "transition_reduction_pct": (rt - st_t) / rt * 100 if rt else 0.0,
        "longest_buy_raw": longest_spell(raw, BUY_FAMILY),
        "longest_buy_stable": longest_spell(stable, BUY_FAMILY),
        "longest_sell_raw": longest_spell(raw, SELL_FAMILY),
        "longest_sell_stable": longest_spell(stable, SELL_FAMILY),
    }
