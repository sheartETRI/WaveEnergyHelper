"""Wave Outcome UI."""

from __future__ import annotations



import os



import pandas as pd

import streamlit as st



from analysis.wave_outcome import summarize_outcomes

from analysis.wave_survival import lifecycle_csv_path

from data.binance import get_auto_limit

from display.asof import fetch_ohlcv_bare

from analysis.wave_outcome import build_outcomes_from_lifecycle, load_outcomes



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





def _outcome_csv_path(symbol: str, interval: str) -> str:

    return os.path.join(_VALIDATION_DIR, f"wave_outcome_{symbol}_{interval}.csv")





@st.cache_data(show_spinner=False, ttl=3600)

def load_outcome_data(symbol: str, interval: str) -> pd.DataFrame:

    cached = _outcome_csv_path(symbol, interval)

    if os.path.isfile(cached):

        return pd.read_csv(cached)

    limit = get_auto_limit(interval)

    if symbol == "ETHUSDT" and interval == "4h":

        limit = 1600

    bare = fetch_ohlcv_bare(symbol, interval, limit, paginated=limit > 1000)

    if bare is None or bare.empty:

        return pd.DataFrame()

    return load_outcomes(symbol, interval, bare)





def render_wave_outcome_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Outcome")

    outcomes = load_outcome_data(symbol, interval)

    if outcomes.empty:

        st.warning("Wave Outcome 데이터 없음")

        return



    stats = summarize_outcomes(outcomes)

    st.caption(f"{symbol} {interval}")



    from analysis.wave_survival import SURVIVAL_INITIAL_TYPES



    for itype in SURVIVAL_INITIAL_TYPES:

        bt = stats["by_type"].get(itype, {})

        if not bt.get("count"):

            continue

        short = itype.replace("_CONFIRMED", "")

        st.markdown(f"**{short}** (n={bt['count']})")

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("+20 avg", f"{bt.get('mean_return_20', 0) or 0:.2f}%")

        c2.metric("+40 avg", f"{bt.get('mean_return_40', 0) or 0:.2f}%")

        c3.metric("+80 avg", f"{bt.get('mean_return_80', 0) or 0:.2f}%")

        c4.metric("20봉 승률", f"{bt.get('win_20', 0) or 0:.1f}%")

        c5.metric("40봉 승률", f"{bt.get('win_40', 0) or 0:.1f}%")


