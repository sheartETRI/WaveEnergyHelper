"""Wave Grade Origin UI."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from analysis.wave_grade_origin import GRADE_A, GRADE_BC

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_grade_origin():
    path = os.path.join(_VALIDATION_DIR, "wave_grade_origin.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_separators():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_GRADE_ORIGIN.md")
    if not os.path.isfile(path):
        return [], [], []
    seps, leads, timeline = [], [], []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Top Separators"):
                section = "sep"
            elif line.startswith("## Lead Indicators"):
                section = "lead"
            elif line.startswith("## Origin Timeline"):
                section = "timeline"
            elif line.startswith("## ") and section:
                section = None
            elif section == "sep" and line.startswith("|") and not line.startswith("| rank"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[0].isdigit():
                    seps.append({"feature": parts[1], "effect": parts[2]})
            elif section == "lead" and line.startswith("|") and "feature" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    leads.append({"feature": parts[0], "effect": parts[1], "lead_bars": parts[2]})
            elif section == "timeline" and line.startswith("|") and "offset" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    timeline.append({"offset": parts[0], "major_k": parts[1], "rsi": parts[2]})
    return seps[:5], leads[:5], timeline[:6]


def render_wave_grade_origin_panel(symbol: str, interval: str) -> None:
    st.markdown("### Grade Origin")

    df = load_grade_origin()
    if df.empty:
        st.warning("Grade Origin 데이터 없음 — wave_grade_origin_sweep.py 실행 필요")
        return

    a_n = len(df[df["grade"] == GRADE_A])
    bc_n = len(df[df["grade"] == GRADE_BC])
    st.caption(f"GRADE_A n={a_n}, GRADE_BC n={bc_n}")

    seps, leads, timeline = _load_report_separators()

    st.markdown("**Top Separators**")
    if seps:
        for i, r in enumerate(seps, 1):
            st.caption(f"{i}. {r['feature']} — effect {r['effect']}")
    else:
        for feat in ("major_k", "rsi", "ema20_slope_3", "atr_pct"):
            if feat not in df.columns:
                continue
            av = df[df["grade"] == GRADE_A][feat].dropna()
            bv = df[df["grade"] == GRADE_BC][feat].dropna()
            if len(av) and len(bv):
                st.caption(f"{feat}: A={av.mean():.2f}, BC={bv.mean():.2f}")

    st.markdown("**Lead Indicators**")
    for r in leads:
        st.caption(f"- {r['feature']} effect {r['effect']} ({r['lead_bars']}b before)")
    if not leads:
        st.caption("—")

    st.markdown("**Origin Timeline**")
    for r in timeline:
        st.caption(
            f"offset {r['offset']}: major_k={r['major_k']}, rsi={r['rsi']}"
        )
    if not timeline:
        st.caption("—")
