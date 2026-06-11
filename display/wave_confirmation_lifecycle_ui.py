"""Wave Confirmation Lifecycle UI."""

from __future__ import annotations



import os



import pandas as pd

import streamlit as st



from analysis.wave_confirmation_lifecycle import run_lifecycle_timeline

from display.asof import build_ohlcv_cache



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





def _csv_path(symbol: str, interval: str) -> str:

    return os.path.join(_VALIDATION_DIR, f"wave_confirmation_lifecycle_{symbol}_{interval}.csv")





@st.cache_data(show_spinner=False, ttl=3600)

def load_or_build_lifecycle(

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

    return run_lifecycle_timeline(symbol, interval, bare, cache)





def get_lifecycle_episodes(

    symbol: str,

    interval: str,

    df: pd.DataFrame,

    ohlcv_cache: dict,

    as_of_iso: str = "",

) -> pd.DataFrame:

    if as_of_iso:

        return run_lifecycle_timeline(symbol, interval, df, ohlcv_cache)

    return load_or_build_lifecycle(

        symbol, interval, as_of_iso, tuple(pd.Timestamp(t) for t in df.index),

    )





def render_wave_lifecycle_panel(lifecycle: pd.DataFrame) -> None:

    st.markdown("### Wave Lifecycle")

    if lifecycle.empty:

        st.warning("Wave Lifecycle 데이터 없음")

        return



    last = lifecycle.iloc[-1]

    st.caption("최근 DB 에피소드")



    c1, c2 = st.columns(2)

    c1.metric("INITIAL", last.get("initial_outcome", "—"))

    c2.metric("POST", last.get("post_outcome", "—"))



    c3, c4 = st.columns(2)

    bi = last.get("bars_until_initial")

    bh = last.get("bars_held_after_initial")

    c3.metric("bars_until_initial", "—" if pd.isna(bi) else f"{int(bi)}")

    c4.metric("bars_held_after_initial", "—" if pd.isna(bh) else f"{int(bh)}")


