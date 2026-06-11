"""Wave Paths UI."""

from __future__ import annotations



import os



import streamlit as st



from analysis.wave_path_analysis import summarize_paths



_VALIDATION_DIR = os.path.join(

    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

    "validation",

)





@st.cache_data(show_spinner=False, ttl=3600)

def load_paths(symbol: str, interval: str):

    import pandas as pd



    path = os.path.join(

        _VALIDATION_DIR, f"wave_paths_{symbol}_{interval}.csv",

    )

    if not os.path.isfile(path):

        return pd.DataFrame()

    return pd.read_csv(path, parse_dates=["timestamp"])





def render_wave_paths_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Paths")

    df = load_paths(symbol, interval)

    if df.empty:

        st.warning("Wave Paths 데이터 없음")

        return



    stats = summarize_paths(df)

    st.caption(

        f"{symbol} {interval} — TP3 (n={stats['count']}, "

        f"paths={stats.get('unique_paths', 0)})"

    )



    st.markdown("**Top Winning Paths**")

    for i, r in enumerate(stats.get("top_winning_paths", [])[:5], 1):

        st.caption(

            f"{i}. {r['path'][:60]} — exp {r['expectancy']:.2f}% (n={r['n']})"

        )



    st.markdown("**Top Losing Paths**")

    for i, r in enumerate(stats.get("top_losing_paths", [])[:5], 1):

        st.caption(

            f"{i}. {r['path'][:60]} — exp {r['expectancy']:.2f}% (n={r['n']})"

        )



    st.markdown("**Transition Summary**")

    for t in stats.get("transitions", [])[:5]:

        st.caption(f"- {t['label']}: {t['pct']:.1f}% (n={t['count']})")

    tb = stats.get("tb_required_from_db")

    wc = stats.get("w3_completed_from_db")

    if tb is not None:

        st.caption(f"- DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRED: {tb:.1f}%")

    if wc is not None:

        st.caption(f"- DOUBLE_BOTTOM → WAVE3_COMPLETED: {wc:.1f}%")


