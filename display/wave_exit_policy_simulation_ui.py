"""Wave Exit Policy Simulation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_exit_policy_simulation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_exit_policy_simulation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_EXIT_POLICY_SIMULATION.md")
    if not os.path.isfile(path):
        return [], [], [], [], [], ""
    summary, champs, false_ex, saved, active, conclusion = [], [], [], [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "summary"
            elif line.startswith("## 9."):
                section = "champ"
            elif line.startswith("## 3."):
                section = "false"
            elif line.startswith("## 4."):
                section = "saved"
            elif line.startswith("## 11."):
                section = "active"
            elif line.startswith("## 13."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "summary" and line.startswith("|") and "policy" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    summary.append(f"{parts[0]}: ret={parts[2]}, exp={parts[3]}")
            elif section == "champ" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    champs.append(f"#{parts[0]} {parts[1]} score={parts[2]}")
            elif section == "false" and line.startswith("|") and "policy" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    false_ex.append(f"{parts[0]}: {parts[3]}")
            elif section == "saved" and line.startswith("|") and "policy" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    saved.append(f"{parts[0]}: {parts[3]}")
            elif section == "active" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    active.append(f"#{parts[0]} {parts[1]} {parts[4]} prot={parts[5]}")
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return summary[:8], champs[:8], false_ex[:6], saved[:6], active[:8], conclusion


def render_wave_exit_policy_simulation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Exit Policy Simulation")

    df = load_exit_policy_simulation()
    if df.empty:
        st.warning("Exit Policy Simulation 데이터 없음 — wave_exit_policy_simulation_sweep.py 실행 필요")
        return

    summary, champs, false_ex, saved, active, conclusion = _load_report_snippets()

    st.markdown("**Policy Summary**")
    for row in summary:
        st.caption(row)

    st.markdown("**Champion Policies**")
    for row in champs:
        st.caption(row)

    st.markdown("**False Exit**")
    for row in false_ex:
        st.caption(row)

    st.markdown("**Saved Failure**")
    for row in saved:
        st.caption(row)

    st.markdown("**Active Candidate Overlay**")
    for row in active:
        st.caption(row)

    if conclusion:
        st.info(conclusion)

    png = os.path.join(_VALIDATION_DIR, "wave_exit_policy_simulation.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)

    sym_df = df[(df.get("symbol") == symbol) & (df.get("timeframe") == interval)]
    if not sym_df.empty:
        st.markdown(f"**{symbol} {interval} 관련 행**")
        show_cols = [c for c in ("section", "policy", "rule", "avg_return", "expectancy", "false_exit_rate", "saved_failure_rate") if c in sym_df.columns]
        st.dataframe(sym_df[show_cols].head(20), use_container_width=True, hide_index=True)
