"""Wave Structure LTE UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_structure_lte():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_structure_lte.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def render_wave_structure_lte_panel(symbol: str, interval: str) -> None:
    st.markdown("### Structure LTE")

    df = load_structure_lte()
    if df.empty:
        st.warning("Structure LTE 데이터 없음 — wave_structure_lte_sweep.py 실행 필요")
        return

    sub = df[df["symbol"] == symbol]
    if sub.empty:
        st.caption(f"{symbol} 데이터 없음")
        return

    last = sub.iloc[-1]
    st.caption(f"LTE Position Score: {int(last.get('lte_position_score', 0))} (관측용)")
    for p in (120, 240, 480, 960):
        pvm = last.get(f"price_vs_ma{p}")
        slope = last.get(f"ma{p}_slope")
        if pvm is not None:
            st.caption(f"price vs MA{p}: {float(pvm):.2f}% | slope: {float(slope):.4f}" if slope is not None else f"price vs MA{p}: {float(pvm):.2f}%")
