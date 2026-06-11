"""Wave Segmentation UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_segmentation import summarize_segmentation



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





@st.cache_data(show_spinner=False, ttl=3600)

def load_segmentation(symbol: str, interval: str):

    import pandas as pd



    path = os.path.join(
        _VALIDATION_DIR, f"wave_segmentation_{symbol}_{interval}.csv",
    )
    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path, parse_dates=["timestamp"])





def render_wave_segmentation_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Segmentation")

    df = load_segmentation(symbol, interval)

    if df.empty:

        st.warning("Wave Segmentation 데이터 없음")

        return



    stats = summarize_segmentation(df)

    st.caption(f"{symbol} {interval} — TP3 기준 (n={stats['count']})")



    st.markdown("**Top Success Factors**")

    for i, r in enumerate(stats.get("top_success", [])[:5], 1):

        st.caption(f"{i}. {r['label']} — {r['success_rate']:.1f}% (n={r['n']})")



    st.markdown("**Top Failure Factors**")

    for i, r in enumerate(stats.get("top_failure", [])[:5], 1):

        st.caption(f"{i}. {r['label']} — {r['failure_rate']:.1f}% (n={r['n']})")


