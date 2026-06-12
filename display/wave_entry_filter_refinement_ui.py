"""Wave Entry Filter Refinement UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_entry_filter_refinement():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_entry_filter_refinement.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_ENTRY_FILTER_REFINEMENT.md")
    if not os.path.isfile(path):
        return [], [], [], [], ""
    champs, rules, robust, active, conclusion = [], [], [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 5."):
                section = "champ"
            elif line.startswith("## 1."):
                section = "rule"
            elif line.startswith("## 7."):
                section = "robust"
            elif line.startswith("## 9."):
                section = "active"
            elif line.startswith("## 11."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "champ" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    champs.append(f"#{parts[0]} exp={parts[3]} n={parts[2]}")
            elif section == "rule" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    rules.append(f"{parts[0]}: exp={parts[3]}, delta={parts[6] if len(parts) > 6 else '—'}")
            elif section == "robust" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    robust.append(f"#{parts[0]} cell+={parts[2]} stab")
            elif section == "active" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    active.append(f"#{parts[0]} {parts[1]} {parts[3]} exp={parts[5]}")
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return champs[:10], rules[:4], robust[:6], active[:8], conclusion


def render_wave_entry_filter_refinement_panel(symbol: str, interval: str) -> None:
    st.markdown("### Entry Filter Refinement")

    df = load_entry_filter_refinement()
    if df.empty:
        st.warning("Entry Filter Refinement 데이터 없음 — wave_entry_filter_refinement_sweep.py 실행 필요")
        return

    champs, rules, robust, active, conclusion = _load_report_snippets()

    st.markdown("**Champion Filters**")
    for row in champs:
        st.caption(row)

    st.markdown("**Rule Filter Performance**")
    for row in rules:
        st.caption(row)

    st.markdown("**Robustness**")
    for row in robust:
        st.caption(row)

    st.markdown("**Active Candidate Overlay**")
    for row in active:
        st.caption(row)

    if conclusion:
        st.info(conclusion)

    png = os.path.join(_VALIDATION_DIR, "wave_entry_filter_refinement.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)

    sym_df = df[(df.get("symbol") == symbol) | (df.get("symbol_filter") == symbol)]
    if not sym_df.empty:
        st.markdown(f"**{symbol} 관련 필터**")
        show_cols = [c for c in ("section", "filter_id", "rule", "expectancy", "survival_rate", "expectancy_delta", "score") if c in sym_df.columns]
        st.dataframe(sym_df[show_cols].head(20), use_container_width=True, hide_index=True)
