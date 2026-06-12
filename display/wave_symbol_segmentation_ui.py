"""Wave Symbol Segmentation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_segmentation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_symbol_segmentation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_SYMBOL_SEGMENTATION.md")
    if not os.path.isfile(path):
        return [], [], [], "", ""
    rule_sym, champ, worst, robust_line, conclusion = [], [], [], "", ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "rs"
            elif line.startswith("## 3."):
                section = "champ"
            elif line.startswith("## 4."):
                section = "worst"
            elif line.startswith("## 6."):
                section = "robust"
            elif line.startswith("## 11."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "rs" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    rule_sym.append(f"{parts[0]} {parts[1]}: avg20={parts[5]}")
            elif section == "champ" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    champ.append(f"#{parts[0]} {parts[2]} {parts[3]} {parts[1]} avg20={parts[5]}")
            elif section == "worst" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    worst.append(f"#{parts[0]} {parts[2]} {parts[3]} {parts[1]} avg20={parts[5]}")
            elif section == "robust" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    robust_line += f"{parts[0]}: cell={parts[1]} sym={parts[2]}; "
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return rule_sym[:8], champ[:5], worst[:5], robust_line[:200], conclusion


def render_wave_symbol_segmentation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Symbol Segmentation")

    df = load_segmentation()
    if df.empty:
        st.warning("Symbol Segmentation 데이터 없음 — wave_symbol_segmentation_sweep.py 실행 필요")
        return

    rule_sym, champ, worst, robust, conclusion = _load_report_snippets()

    st.markdown("**Rule × Symbol**")
    for row in rule_sym:
        st.caption(row)
    if not rule_sym:
        st.caption("—")

    st.markdown("**Champion Cells**")
    for row in champ:
        st.caption(row)
    if not champ:
        st.caption("—")

    st.markdown("**Worst Cells**")
    for row in worst:
        st.caption(row)
    if not worst:
        st.caption("—")

    st.markdown("**Positive Symbol Ratio**")
    st.caption(robust or "—")

    st.markdown("**Active Candidate Ranking**")
    if "section" in df.columns:
        active = df[df["section"] == "active_candidate"].sort_values("rank")
        for _, row in active.head(6).iterrows():
            st.caption(
                f"- {row.get('symbol', '')} {row.get('timeframe', '')} {row.get('rule', '')}: "
                f"hist20={row.get('historical_avg20', '—')}, score={row.get('watchlist_score', '—')}"
            )
        if active.empty:
            st.caption("—")

    if conclusion:
        st.caption(conclusion)
