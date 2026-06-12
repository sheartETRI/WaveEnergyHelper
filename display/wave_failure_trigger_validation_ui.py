"""Wave Failure Trigger Validation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_failure_trigger_validation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_failure_trigger_validation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_FAILURE_TRIGGER_VALIDATION.md")
    if not os.path.isfile(path):
        return [], [], [], [], ""
    pr_rows, timing, combos, active, conclusion = [], [], [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "pr"
            elif line.startswith("## 2."):
                section = "timing"
            elif line.startswith("## 8."):
                section = "combo"
            elif line.startswith("## 10."):
                section = "active"
            elif line.startswith("## 12."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "pr" and line.startswith("|") and "trigger" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    pr_rows.append(f"{parts[0]}: f1={parts[4]}, false_exit={parts[5]}")
            elif section == "timing" and line.startswith("|") and "trigger" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    timing.append(f"{parts[0]}: avg={parts[2]}b, early={parts[4]}")
            elif section == "combo" and line.startswith("|") and "combo" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    combos.append(f"{parts[0][:40]}: f1={parts[2]}")
            elif section == "active" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 7:
                    active.append(f"#{parts[0]} {parts[1]} {parts[2]} {parts[3]} risk={parts[4]}")
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return pr_rows[:8], timing[:6], combos[:4], active[:8], conclusion


def render_wave_failure_trigger_validation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Failure Trigger Validation")

    df = load_failure_trigger_validation()
    if df.empty:
        st.warning("Failure Trigger Validation 데이터 없음 — wave_failure_trigger_validation_sweep.py 실행 필요")
        return

    pr_rows, timing, combos, active, conclusion = _load_report_snippets()

    st.markdown("**Trigger Precision / Recall**")
    for row in pr_rows:
        st.caption(row)
    if not pr_rows:
        st.caption("—")

    st.markdown("**Trigger Timing**")
    for row in timing:
        st.caption(row)

    st.markdown("**Trigger Combinations**")
    for row in combos:
        st.caption(row)

    st.markdown("**Active Candidate Risk**")
    for row in active:
        st.caption(row)

    if conclusion:
        st.info(conclusion)

    png = os.path.join(_VALIDATION_DIR, "wave_failure_trigger_validation.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)

    sym_df = df[(df.get("symbol") == symbol) & (df.get("timeframe") == interval)]
    if not sym_df.empty:
        st.markdown(f"**{symbol} {interval} 관련 행**")
        show_cols = [c for c in ("section", "trigger_type", "combo", "rule", "failure_rate", "f1", "false_exit_rate", "trigger_risk_score") if c in sym_df.columns]
        st.dataframe(sym_df[show_cols].head(20), use_container_width=True, hide_index=True)
