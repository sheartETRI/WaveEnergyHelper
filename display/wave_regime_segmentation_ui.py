"""Wave Regime Segmentation UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_regime_segmentation():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_regime_segmentation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_REGIME_SEGMENTATION.md")
    if not os.path.isfile(path):
        return [], [], [], "", ""
    rule_reg, champ, contrib, pos_line, conclusion = [], [], [], "", ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "rr"
            elif line.startswith("## 4."):
                section = "champ"
            elif line.startswith("## 8."):
                section = "contrib"
            elif line.startswith("## 6."):
                section = "pos"
            elif line.startswith("## 11."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "rr" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    rule_reg.append(f"{parts[0]} {parts[1]}: avg20={parts[5]}")
            elif section == "champ" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 6:
                    champ.append(f"#{parts[0]} {parts[2]} {parts[3]} {parts[1]} avg20={parts[5]}")
            elif section == "contrib" and line.startswith("- **"):
                contrib.append(line.replace("- ", "").replace("**", ""))
            elif section == "pos" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    pos_line += f"{parts[0]} regime={parts[1]}; "
            elif section == "conc" and line.startswith("**"):
                conclusion = line.replace("**", "")
    return rule_reg[:8], champ[:5], contrib[:4], pos_line[:180], conclusion


def render_wave_regime_segmentation_panel(symbol: str, interval: str) -> None:
    st.markdown("### Regime Segmentation")

    df = load_regime_segmentation()
    if df.empty:
        st.warning("Regime Segmentation 데이터 없음 — wave_regime_segmentation_sweep.py 실행 필요")
        return

    rule_reg, champ, contrib, pos_line, conclusion = _load_report_snippets()

    st.markdown("**Rule × Regime**")
    for row in rule_reg:
        st.caption(row)
    if not rule_reg:
        st.caption("—")

    st.markdown("**Champion Regimes**")
    for row in champ:
        st.caption(row)
    if not champ:
        st.caption("—")

    st.markdown("**Contribution**")
    for row in contrib:
        st.caption(row)
    if not contrib:
        st.caption("—")

    st.markdown("**Positive Regime Ratio**")
    st.caption(pos_line or "—")

    st.markdown("**Active Candidate Overlay**")
    if "section" in df.columns:
        active = df[df["section"] == "active_candidate"].sort_values("regime_rank")
        for _, row in active.head(6).iterrows():
            st.caption(
                f"- {row.get('symbol', '')} {row.get('timeframe', '')} {row.get('rule', '')} "
                f"{row.get('regime', '')}: hist20={row.get('historical_avg20_in_regime', '—')}"
            )
        if active.empty:
            st.caption("—")

    if conclusion:
        st.caption(conclusion)
