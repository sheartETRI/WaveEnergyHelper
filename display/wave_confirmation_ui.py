"""Wave Confirmation UI 표시 레이어."""

from __future__ import annotations



import os



import pandas as pd

import streamlit as st



from analysis.wave_confirmation import CONFIRM_WINDOWS, run_episodes_timeline

from display.asof import build_ohlcv_cache



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





def _csv_path(symbol: str, interval: str) -> str:

    return os.path.join(_VALIDATION_DIR, f"wave_confirmation_{symbol}_{interval}.csv")





@st.cache_data(show_spinner=False, ttl=3600)

def load_or_build_episodes(

    symbol: str,

    interval: str,

    as_of_iso: str,

    index_tuple: tuple,

) -> pd.DataFrame:

    path = _csv_path(symbol, interval)

    if os.path.isfile(path):

        return pd.read_csv(path, parse_dates=["timestamp"])



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

    extra = {"4h": limit} if interval == "4h" else {}

    cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)

    return run_episodes_timeline(symbol, interval, bare, cache)





def get_confirmation_episodes(

    symbol: str,

    interval: str,

    df: pd.DataFrame,

    ohlcv_cache: dict,

    as_of_iso: str = "",

) -> pd.DataFrame:

    if as_of_iso:

        return run_episodes_timeline(symbol, interval, df, ohlcv_cache)

    return load_or_build_episodes(

        symbol, interval, as_of_iso, tuple(pd.Timestamp(t) for t in df.index),

    )





def render_wave_confirmation_panel(episodes: pd.DataFrame) -> None:

    st.markdown("### Wave Confirmation")

    if episodes.empty:

        st.warning("Wave Confirmation 데이터 없음")

        return



    last = episodes.iloc[-1]

    st.caption("최근 DB 에피소드 기준")



    c1, c2 = st.columns(2)

    c1.metric("DB time", str(last["timestamp"])[:16])

    c2.metric("Final outcome", last.get("final_outcome", "—"))



    c3, c4 = st.columns(2)

    cross_d = last.get("confirm_cross_delay")

    slope_d = last.get("confirm_slope_delay")

    c3.metric("Cross delay", "—" if pd.isna(cross_d) else f"{int(cross_d)} bars")

    c4.metric("Slope delay", "—" if pd.isna(slope_d) else f"{int(slope_d)} bars")



    within_parts = []

    for w in CONFIRM_WINDOWS:

        cx = last.get(f"within_{w}_cross", False)

        sl = last.get(f"within_{w}_slope", False)

        within_parts.append(f"{w}: cross={'Y' if cx else 'N'} slope={'Y' if sl else 'N'}")

    st.caption("Within windows — " + " | ".join(within_parts))



    if last.get("required_tb_before_confirm"):

        st.caption("TB occurred before K confirm")

    if last.get("invalidated_before_confirm"):

        st.caption("Invalidated before confirm")


