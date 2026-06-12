"""Wave Robustness Validation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_robustness_validation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_robustness_validation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_ROBUSTNESS_VALIDATION.md")
    if not os.path.isfile(path):
        return [], [], [], "", [], ""
    temporal, tf_rows, reg_rows, verdict, alts, active, conclusion = [], [], [], "", [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "temporal"
            elif line.startswith("## 2."):
                section = "tf"
            elif line.startswith("## 4."):
                section = "reg"
            elif line.startswith("## 9."):
                section = "verdict"
            elif line.startswith("## 10."):
                section = "alt"
            elif line.startswith("## 11."):
                section = "active"
            elif line.startswith("## 13."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "temporal" and line.startswith("|") and "split" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    temporal.append(f"{parts[0]}: n={parts[1]}, exp={parts[2]}")
            elif section == "tf" and line.startswith("|") and "tf" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    tf_rows.append(f"{parts[0]}: exp={parts[2]}")
            elif section == "reg" and line.startswith("|") and "regime" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    reg_rows.append(f"{parts[0]}: exp={parts[2]}")
            elif section == "verdict" and line.startswith("- **Verdict"):
                verdict = line.replace("- **Verdict:", "Verdict:").replace("**", "")
            elif section == "alt" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    alts.append(f"#{parts[0]} {parts[1]} score={parts[2]}")
            elif section == "active" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    active.append(f"#{parts[0]} {parts[1]} match={parts[4]}")
            elif section == "conc" and line.startswith("Champion"):
                conclusion = line
    return temporal[:6], tf_rows[:4], reg_rows[:4], verdict, alts[:8], active[:8], conclusion


def render_wave_robustness_validation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Robustness Validation")

    df = load_robustness_validation()
    if df.empty:
        st.warning("Robustness Validation 데이터 없음 — wave_robustness_validation_sweep.py 실행 필요")
        return

    temporal, tf_rows, reg_rows, verdict, alts, active, conclusion = _load_report_snippets()

    if verdict:
        st.markdown(f"**Champion Verdict** — {verdict}")

    st.markdown("**Temporal Split**")
    for row in temporal:
        st.caption(row)

    st.markdown("**TF Robustness**")
    for row in tf_rows:
        st.caption(row)

    st.markdown("**Regime Robustness**")
    for row in reg_rows:
        st.caption(row)

    st.markdown("**Alternative Filters**")
    for row in alts:
        st.caption(row)

    st.markdown("**Active Candidate Overlay**")
    for row in active:
        st.caption(row)

    if conclusion:
        st.info(conclusion)

    png = os.path.join(_VALIDATION_DIR, "wave_robustness_validation.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)
