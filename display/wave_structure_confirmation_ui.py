"""Wave Structure Confirmation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_structure_confirmation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_structure_confirmation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def render_wave_structure_confirmation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Structure Confirmation")

    df = load_structure_confirmation()
    if df.empty:
        st.warning("Structure Confirmation 데이터 없음 — wave_structure_confirmation_sweep.py 실행 필요")
        return

    sub = df[df["symbol"] == symbol]
    if sub.empty:
        st.caption(f"{symbol} 데이터 없음")
        return

    last = sub.iloc[-1]

    st.markdown("**Current Structure Score**")
    st.caption(f"Score: {int(last.get('structure_score', 0))} (관측용)")

    for label, col in [
        ("HH", "hh"), ("HL", "hl"), ("HHHL", "hhhl"),
        ("Neckline Recovery", "neckline_recovery"),
        ("Resistance Break", "resistance_break"),
        ("Support Hold", "support_hold"),
    ]:
        st.markdown(f"**{label}**")
        val = last.get(col, False)
        if isinstance(val, str):
            on = val.lower() in ("true", "1", "yes")
        else:
            on = bool(val)
        st.caption("yes" if on else "no")
