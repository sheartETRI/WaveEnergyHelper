"""Wave Expectancy UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_expectancy import summarize_expectancy



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





@st.cache_data(show_spinner=False, ttl=3600)

def load_expectancy(symbol: str, interval: str):

    import pandas as pd



    path = os.path.join(

        _VALIDATION_DIR, f"wave_expectancy_{symbol}_{interval}.csv",

    )

    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path, parse_dates=["timestamp"])





def render_wave_expectancy_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Expectancy")

    df = load_expectancy(symbol, interval)

    if df.empty:

        st.warning("Wave Expectancy 데이터 없음")

        return



    stats = summarize_expectancy(df)

    ov = stats.get("overall", {})

    st.caption(

        f"{symbol} {interval} — TP3 (n={stats['count']}, "

        f"exp {ov.get('expectancy', 0):.2f}%)"

    )



    st.markdown("**Top 5 Expectancy**")

    for i, r in enumerate(stats.get("top_expectancy", [])[:5], 1):

        st.caption(

            f"{i}. {r.get('label', '')} — {r.get('expectancy', 0):.2f}% "

            f"(n={r['n']})"

        )



    st.markdown("**Worst 5 Expectancy**")

    for i, r in enumerate(stats.get("worst_expectancy", [])[:5], 1):

        st.caption(

            f"{i}. {r.get('label', '')} — {r.get('expectancy', 0):.2f}% "

            f"(n={r['n']})"

        )


