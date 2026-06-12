"""Wave Survival Segmentation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_survival_segmentation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_survival_segmentation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_SURVIVAL_SEGMENTATION.md")
    if not os.path.isfile(path):
        return [], [], [], [], ""
    cohort, feat, curve, contrib, conclusion = [], [], [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "cohort"
            elif line.startswith("## 5."):
                section = "feat"
            elif line.startswith("## 7."):
                section = "curve"
            elif line.startswith("## 9."):
                section = "contrib"
            elif line.startswith("## 12."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "cohort" and line.startswith("|") and "label" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    cohort.append(f"{parts[0]}: n={parts[1]}, avg20={parts[4]}")
            elif section == "feat" and line.startswith("|") and "feature" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    feat.append(f"{parts[0]}: delta={parts[3]}")
            elif section == "curve" and line.startswith("|") and "horizon" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    curve.append(f"+{parts[0]}: {parts[2]}")
            elif section == "contrib" and line.startswith("- **"):
                contrib.append(line.replace("- ", "").replace("**", ""))
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return cohort[:4], feat[:6], curve[:4], contrib[:5], conclusion


def render_wave_survival_segmentation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Survival Segmentation")

    df = load_survival_segmentation()
    if df.empty:
        st.warning("Survival Segmentation 데이터 없음 — wave_survival_segmentation_sweep.py 실행 필요")
        return

    cohort, feat, curve, contrib, conclusion = _load_report_snippets()

    st.markdown("**Survival Cohort**")
    for row in cohort:
        st.caption(row)
    if not cohort:
        st.caption("—")

    st.markdown("**Feature Difference**")
    for row in feat:
        st.caption(row)
    if not feat:
        st.caption("—")

    st.markdown("**Survival Curve**")
    for row in curve:
        st.caption(row)
    if not curve:
        st.caption("—")

    st.markdown("**Contribution**")
    for row in contrib:
        st.caption(row)
    if not contrib:
        st.caption("—")

    st.markdown("**Active Candidate Overlay**")
    if "section" in df.columns:
        active = df[df["section"] == "active_candidate"].sort_values("survival_rank")
        for _, row in active.head(6).iterrows():
            st.caption(
                f"- {row.get('symbol', '')} {row.get('timeframe', '')} {row.get('rule', '')}: "
                f"surv={row.get('historical_survival_rate', '—')}, fail={row.get('historical_failure_rate', '—')}"
            )
        if active.empty:
            st.caption("—")

    if conclusion:
        st.caption(conclusion)
