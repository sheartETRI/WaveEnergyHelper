"""Wave Watchlist Tracker UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_watchlist_tracker():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_watchlist_tracker.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_WATCHLIST_TRACKER.md")
    if not os.path.isfile(path):
        return [], [], None
    conv, funnel, riskiest = [], [], None
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Conversion Rate"):
                section = "conv"
            elif line.startswith("## Watchlist Funnel"):
                section = "funnel"
            elif line.startswith("- riskiest state:"):
                riskiest = line.split(":")[-1].strip()
            elif line.startswith("## ") and section:
                section = None
            elif section == "conv" and line.startswith("|") and "state" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    conv.append({"state": parts[0], "conversion": parts[2]})
            elif section == "funnel" and line.startswith("|") and "state" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    funnel.append({"state": parts[0], "count": parts[1]})
    return conv[:4], funnel[:4], riskiest


def render_wave_watchlist_tracker_panel(symbol: str, interval: str) -> None:
    st.markdown("### Watchlist Tracker")

    df = load_watchlist_tracker()
    if df.empty:
        st.warning("Watchlist Tracker 데이터 없음 — wave_watchlist_tracker_sweep.py 실행 필요")
        return

    conv, funnel, riskiest = _load_report_sections()

    st.markdown("**Current State**")
    st.caption("관측 전용 — 실시간 상태 머신 아님")
    if "state" in df.columns:
        last_states = df["state"].value_counts().head(3)
        for state, cnt in last_states.items():
            st.caption(f"- {state}: {cnt} transitions")

    st.markdown("**Conversion Rate**")
    for r in conv:
        st.caption(f"- {r['state']}: {r['conversion']}")
    if not conv:
        st.caption("—")

    st.markdown("**Funnel**")
    for r in funnel:
        st.caption(f"{r['state']}: {r['count']}")
    if not funnel:
        st.caption("—")

    st.markdown("**Top Failure State**")
    st.caption(f"Riskiest: {riskiest or '—'}")
