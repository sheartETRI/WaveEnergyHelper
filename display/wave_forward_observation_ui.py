"""Wave Forward Observation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=1800)
def load_forward_observation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_forward_observation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=1800)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_FORWARD_OBSERVATION.md")
    if not os.path.isfile(path):
        return [], [], [], "", ""
    tier, cands, drift, verdict, alerts = [], [], [], "", []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "tier"
            elif line.startswith("## 2."):
                section = "cand"
            elif line.startswith("## 4."):
                section = "drift"
            elif line.startswith("## 6."):
                section = "alert"
            elif line.startswith("## 8."):
                section = "verdict"
            elif line.startswith("## ") and section:
                section = None
            elif section == "tier" and line.startswith("|") and "tier" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    tier.append(f"{parts[0]} {parts[1]}: n={parts[2]}, exp={parts[3]}")
            elif section == "cand" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    cands.append(f"#{parts[0]} {parts[1]} {parts[2]} {parts[4]}")
            elif section == "drift" and line.startswith("|") and "tier" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    drift.append(f"{parts[0]} {parts[1]}: {parts[5]}")
            elif section == "alert" and line.startswith("- ["):
                alerts.append(line[2:])
            elif section == "verdict" and line.startswith("- **Verdict"):
                verdict = line
    return tier[:4], cands[:8], drift[:6], verdict, alerts[:6]


def render_wave_forward_observation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Forward Observation")

    df = load_forward_observation()
    if df.empty:
        st.warning("Forward Observation 데이터 없음 — wave_forward_observation_sweep.py 실행 필요")
        return

    tier, cands, drift, verdict, alerts = _load_report_snippets()

    if verdict:
        st.markdown(f"**{verdict.replace('- **', '').replace('**', '')}**")

    st.markdown("**Tier Performance**")
    for row in tier:
        st.caption(row)

    st.markdown("**Current Candidates**")
    for row in cands:
        st.caption(row)

    st.markdown("**Drift Detection**")
    for row in drift:
        st.caption(row)

    st.markdown("**Alerts**")
    for row in alerts:
        st.caption(row)

    png = os.path.join(_VALIDATION_DIR, "wave_forward_observation.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)

    sym_df = df[(df.get("symbol") == symbol) | (df.get("timeframe") == interval)]
    if not sym_df.empty:
        events = sym_df[sym_df.get("section") == "observation_event"] if "section" in sym_df.columns else sym_df
        if not events.empty:
            st.markdown(f"**{symbol} 관련 관측 이벤트**")
            cols = [c for c in ("event_id", "observation_tier", "filter_match", "forward_status", "return_20") if c in events.columns]
            st.dataframe(events[cols].head(15), use_container_width=True, hide_index=True)
