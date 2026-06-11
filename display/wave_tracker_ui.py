"""Wave Tracker UI 표시 레이어."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from analysis.wave_tracker import (
    ALL_STATES,
    STATE_COLORS,
    WaveTrackerState,
    run_timeline,
)
from display.asof import build_ohlcv_cache

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)
LOOKBACK_BARS = 200


def _csv_path(symbol: str, interval: str) -> str:
    return os.path.join(_VALIDATION_DIR, f"wave_tracker_{symbol}_{interval}.csv")


@st.cache_data(show_spinner=False, ttl=3600)
def load_or_build_timeline(
    symbol: str,
    interval: str,
    as_of_iso: str,
    index_tuple: tuple,
) -> pd.DataFrame:
    path = _csv_path(symbol, interval)
    if os.path.isfile(path):
        tl = pd.read_csv(path, parse_dates=["timestamp"])
        idx = pd.DatetimeIndex(index_tuple)
        sub = tl[tl["timestamp"].isin(idx)]
        if len(sub) >= max(len(idx) - 250, len(idx) * 0.8):
            return sub.reset_index(drop=True)

    from data.binance import get_auto_limit
    from display.asof import fetch_ohlcv_bare, parse_as_of, truncate_to_asof

    limit = get_auto_limit(interval)
    if as_of_iso and symbol == "ETHUSDT" and interval == "4h":
        limit = 1600
    bare = fetch_ohlcv_bare(symbol, interval, limit, paginated=limit > 1000)
    if bare is None or bare.empty:
        return pd.DataFrame()
    if as_of_iso:
        as_of = parse_as_of(as_of_iso)
        if as_of is not None:
            bare = truncate_to_asof(bare, as_of)
    bare = bare.loc[bare.index.isin(pd.DatetimeIndex(index_tuple))]
    extra = {"4h": limit} if interval == "4h" else {}
    cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)
    return run_timeline(symbol, interval, bare, cache)


def get_wave_tracker_timeline(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
    ohlcv_cache: dict,
    as_of_iso: str = "",
) -> pd.DataFrame:
    if as_of_iso:
        return run_timeline(symbol, interval, df, ohlcv_cache)
    return load_or_build_timeline(
        symbol, interval, as_of_iso, tuple(pd.Timestamp(t) for t in df.index),
    )


def align_timeline_to_index(timeline: pd.DataFrame, df_index: pd.Index) -> pd.DataFrame:
    if timeline.empty:
        return timeline
    keyed = timeline.set_index("timestamp")
    out = keyed.reindex(pd.DatetimeIndex(df_index))
    out.index.name = "timestamp"
    return out.reset_index()


def render_wave_tracker_panel(aligned: pd.DataFrame) -> None:
    valid = aligned.dropna(subset=["state"])
    if valid.empty:
        st.warning("Wave Tracker 데이터 없음")
        return

    last = valid.iloc[-1]
    st.markdown("### Wave Tracker")
    c1, c2, c3 = st.columns(3)
    c1.metric("Current State", last["state"])
    c2.metric("Duration", f"{int(last['duration'])} bars")
    c3.metric("Reason", last.get("reason", "") or "—")

    if last.get("invalidated"):
        st.caption(f"INVALIDATED — {last.get('reason', '')}")


def compute_panel_metrics(aligned: pd.DataFrame) -> dict:
    valid = aligned.dropna(subset=["state"])
    if valid.empty:
        return {}
    return {
        "current": valid.iloc[-1]["state"],
        "duration": int(valid.iloc[-1]["duration"]),
    }
