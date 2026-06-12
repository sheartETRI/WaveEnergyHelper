"""Wave Grade Failure UI."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_grade_failure():
    path = os.path.join(_VALIDATION_DIR, "wave_grade_failure.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_GRADE_FAILURE.md")
    if not os.path.isfile(path):
        return [], [], [], []
    causes, timing, funnel, seps = [], [], [], []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Failure Causes"):
                section = "causes"
            elif line.startswith("## Failure Timing"):
                section = "timing"
            elif line.startswith("## False Positive Funnel"):
                section = "funnel"
            elif line.startswith("## Top Separators"):
                section = "sep"
            elif line.startswith("## ") and section:
                section = None
            elif section == "causes" and line.startswith("|") and "cause" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    causes.append({"cause": parts[0], "pct": parts[2]})
            elif section == "timing" and line.startswith("|") and "horizon" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    timing.append({"horizon": parts[0], "pct": parts[2]})
            elif section == "funnel" and line.startswith("|") and "stage" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    funnel.append({"stage": parts[0], "survivors": parts[1]})
            elif section == "sep" and line.startswith("|") and not line.startswith("| rank"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[0].isdigit():
                    seps.append({"feature": parts[1], "effect": parts[2]})
    return causes[:5], timing[:4], funnel, seps[:5]


def render_wave_grade_failure_panel(symbol: str, interval: str) -> None:
    st.markdown("### Grade Failure")

    df = load_grade_failure()
    if df.empty:
        st.warning("Grade Failure 데이터 없음 — wave_grade_failure_sweep.py 실행 필요")
        return

    if "success" in df.columns:
        succ = len(df[df["success"] == True])
        fail = len(df[df["success"] == False])
        st.caption(f"SUCCESS={succ}, FAILURE={fail}")

    causes, timing, funnel, seps = _load_report_sections()

    st.markdown("**Failure Causes**")
    for r in causes:
        st.caption(f"- {r['cause']}: {r['pct']}%")
    if not causes:
        st.caption("—")

    st.markdown("**Failure Timing**")
    for r in timing:
        st.caption(f"horizon {r['horizon']}: {r['pct']}%")
    if not timing:
        st.caption("—")

    st.markdown("**Funnel**")
    for r in funnel:
        st.caption(f"{r['stage']}: {r['survivors']}")
    if not funnel:
        st.caption("—")

    st.markdown("**Top Separators**")
    for i, r in enumerate(seps, 1):
        st.caption(f"{i}. {r['feature']} — effect {r['effect']}")
    if not seps:
        st.caption("—")
