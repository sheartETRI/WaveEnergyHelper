"""Wave Cross Market Validation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_CROSS_MARKET_VALIDATION.md")
    if not os.path.isfile(path):
        return {}
    data = {"champion": "", "verdict": "", "positive": [], "overfit": []}
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 8."):
                section = "champion"
            elif line.startswith("## 9."):
                section = "overfit"
            elif line.startswith("## 10."):
                section = "verdict"
            elif line.startswith("## 2."):
                section = "positive"
            elif line.startswith("## ") and section:
                section = None
            elif section == "champion" and line.startswith("**"):
                data["champion"] = line.replace("**", "")
            elif section == "verdict" and line.startswith("**"):
                data["verdict"] = line.replace("**", "")
            elif section == "positive" and line.startswith("|") and "---" not in line and "rule" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    data["positive"].append(f"{parts[0]}: {parts[3]}")
            elif section == "overfit" and line.startswith("|") and "---" not in line and "rule" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 7:
                    data["overfit"].append(f"{parts[0]}: {parts[6]}")
    return data


def render_wave_cross_market_validation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Cross Market Validation")

    report = _load_report()
    if not report:
        st.warning("Cross Market 데이터 없음 — wave_cross_market_validation_sweep.py 실행 필요")
        return

    if report.get("verdict"):
        st.caption(report["verdict"])

    st.markdown("**Champion Rule v2**")
    st.caption(report.get("champion") or "—")

    st.markdown("**Positive Ratio**")
    for row in report.get("positive", [])[:5]:
        st.caption(row)

    st.markdown("**Overfitting Risk**")
    for row in report.get("overfit", [])[:5]:
        st.caption(row)
