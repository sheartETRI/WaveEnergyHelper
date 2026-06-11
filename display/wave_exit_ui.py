"""Wave Exit UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_exit import summarize_exits



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





def _exit_csv_path(symbol: str, interval: str) -> str:

    return os.path.join(_VALIDATION_DIR, f"wave_exit_{symbol}_{interval}.csv")





@st.cache_data(show_spinner=False, ttl=3600)

def load_exit_csv(symbol: str, interval: str):

    import pandas as pd



    path = _exit_csv_path(symbol, interval)

    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path)





def render_wave_exit_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Exit")

    df = load_exit_csv(symbol, interval)

    if df.empty:

        st.warning("Wave Exit 데이터 없음 (wave_exit CSV 필요)")

        return



    stats = summarize_exits(df)

    st.caption(f"{symbol} {interval} — 상위 3 policy")



    for i, (policy, v) in enumerate(stats.get("top3", []), 1):

        st.markdown(f"**#{i} {policy}**")

        c1, c2, c3 = st.columns(3)

        c1.metric("avg return", f"{v['avg_return']:.2f}%")

        c2.metric("win rate", f"{v['win_rate']:.1f}%")

        c3.metric("avg bars held", f"{v['avg_bars_held']:.1f}")


