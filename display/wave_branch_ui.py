"""Wave Branch UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_branch_analysis import summarize_branch_analysis



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





@st.cache_data(show_spinner=False, ttl=3600)

def load_branch(symbol: str, interval: str):

    import pandas as pd



    path = os.path.join(

        _VALIDATION_DIR, f"wave_branch_{symbol}_{interval}.csv",

    )

    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path, parse_dates=["timestamp"])





def render_wave_branch_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Branch")

    df = load_branch(symbol, interval)

    if df.empty:

        st.warning("Wave Branch 데이터 없음")

        return



    stats = summarize_branch_analysis(df)

    st.caption(

        f"{symbol} {interval} — DOUBLE_BOTTOM events={stats['count']}, "

        f"analyzed={stats.get('analyzed_count', 0)}"

    )



    st.markdown("**Branch Count**")

    for br, cnt in stats.get("branch_counts", {}).items():

        st.caption(f"- {br}: {cnt}")



    st.markdown("**Branch Performance**")

    for br, p in stats.get("branch_performance", {}).items():

        st.caption(

            f"- {br}: win {p.get('win_rate', 0):.1f}%, "

            f"exp {p.get('expectancy', 0):.2f}% (n={p.get('n', 0)})"

        )



    st.markdown("**Top Separators**")

    for i, r in enumerate(stats.get("top_numeric_separators", [])[:3], 1):

        st.caption(f"{i}. {r['feature']} — effect {r['effect_size']:.2f}")

    for i, r in enumerate(stats.get("top_categorical_separators", [])[:3], 1):

        st.caption(

            f"{i}. {r['feature']}={r['value']} — lift {r['lift']:.2f}"

        )


