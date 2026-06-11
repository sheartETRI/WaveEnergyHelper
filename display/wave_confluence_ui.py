"""Wave Confluence UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_confluence import summarize_confluence



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





@st.cache_data(show_spinner=False, ttl=3600)

def load_confluence(symbol: str, interval: str):

    import pandas as pd



    path = os.path.join(_VALIDATION_DIR, f"wave_confluence_{symbol}_{interval}.csv")

    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path, parse_dates=["timestamp"])





def render_wave_confluence_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Confluence")

    df = load_confluence(symbol, interval)

    if df.empty:

        st.warning("Wave Confluence 데이터 없음")

        return



    stats = summarize_confluence(df, symbol)

    st.caption(f"{symbol} {interval} — n={stats['count']}")



    st.markdown("**Top Factors**")

    for i, f in enumerate(stats.get("top_confluence_factors", [])[:5], 1):

        st.caption(f"{i}. {f.get('label', '')} — score {f.get('score', 0):.2f}")



    st.markdown("**Top Bundles**")

    for i, b in enumerate(stats.get("top_confluence_bundles", [])[:5], 1):

        st.caption(

            f"{i}. {b.get('bundle', '')[:50]} — exp {b.get('expectancy', 0):.2f}% (n={b['n']})"

        )



    st.markdown("**Score Summary**")

    for s in stats.get("score_summary", []):

        st.caption(

            f"- score {s['score']}: win {s['win_rate']:.1f}%, "

            f"exp {s['expectancy']:.2f}% (n={s['count']})"

        )


