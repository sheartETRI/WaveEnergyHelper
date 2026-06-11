"""Wave Regime Gated UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_regime_gated():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_regime_gated.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def render_wave_regime_gated_panel(symbol: str, interval: str) -> None:
    st.markdown("### Regime Gated")

    df = load_regime_gated()
    if df.empty:
        st.warning("Regime Gated 데이터 없음 — wave_regime_gated_sweep.py 실행 필요")
        return

    base = df[df["filter"] == "BASE_RULE"]
    gated = df[df["filter"] != "BASE_RULE"]

    if not base.empty:
        b = base.iloc[0]
        st.caption(
            f"BASE_RULE — n={int(b.get('n', 0))}, "
            f"exp {b.get('expectancy', 0):.2f}%, win {b.get('win_rate', 0):.1f}%"
        )

    st.markdown("**Top Filters**")
    top = gated.sort_values("improvement", ascending=False, na_position="last").head(5)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        st.caption(
            f"{i}. {r['filter'][:55]} — Δexp {r.get('improvement', 0):.2f}% "
            f"(n={int(r.get('n', 0))})"
        )

    st.markdown("**Top Improvements**")
    for i, (_, r) in enumerate(top.head(3).iterrows(), 1):
        st.caption(
            f"- Δwin {r.get('delta_win_rate', 0):.1f}%, "
            f"PF Δ {r.get('delta_profit_factor', 0):.2f}"
        )

    st.markdown("**Robustness**")
    rob = gated.dropna(subset=["robustness_gap"]).sort_values("robustness_gap").head(3)
    for i, (_, r) in enumerate(rob.iterrows(), 1):
        st.caption(
            f"{i}. {r['filter'][:45]} — gap {r.get('robustness_gap', 0):.2f} "
            f"(n={int(r.get('n', 0))})"
        )
