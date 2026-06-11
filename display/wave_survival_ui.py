"""Wave Survival UI."""

from __future__ import annotations



import pandas as pd

import streamlit as st



from analysis.wave_survival import (

    INITIAL_CROSS,

    INITIAL_SLOPE,

    INITIAL_TB,

    SURVIVAL_INITIAL_TYPES,

    load_survival,

    summarize_survival,

)





def get_survival_data(symbol: str, interval: str) -> pd.DataFrame:

    return load_survival(symbol, interval)





def render_wave_survival_panel(symbol: str, interval: str) -> None:

    st.markdown("### Wave Survival")

    survival = load_survival(symbol, interval)

    if survival.empty:

        st.warning("Wave Survival 데이터 없음 (lifecycle CSV 필요)")

        return



    stats = summarize_survival(survival)

    st.caption(f"{symbol} {interval} — INITIAL 경로별 생존")



    for itype in SURVIVAL_INITIAL_TYPES:

        bt = stats["by_type"].get(itype, {})

        if not bt.get("count"):

            continue

        short = itype.replace("_CONFIRMED", "")

        rates = bt.get("rates", {})

        st.markdown(f"**{short}** (n={bt['count']})")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("avg survival", f"{bt['avg']:.1f}")

        c2.metric("median", f"{bt['median']:.1f}")

        c3.metric("20봉 생존율", f"{rates.get(20, 0):.1f}%")

        c4.metric("40봉 생존율", f"{rates.get(40, 0):.1f}%")


