"""Wave Money Flow UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_money_flow():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_money_flow.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_score_perf():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_MONEY_FLOW.md")
    if not os.path.isfile(path):
        return []
    rows = []
    section = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 3. Score"):
                section = True
            elif line.startswith("## ") and section:
                break
            elif section and line.startswith("|") and "score" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    rows.append({
                        "score": parts[0], "n": parts[1],
                        "win_rate": parts[2], "expectancy": parts[3],
                    })
    return rows[:6]


def render_wave_money_flow_panel(symbol: str, interval: str) -> None:
    st.markdown("### Money Flow")

    df = load_money_flow()
    if df.empty:
        st.warning("Money Flow 데이터 없음 — wave_money_flow_sweep.py 실행 필요")
        return

    sub = df[df["symbol"] == symbol]
    score_perf = _load_report_score_perf()

    st.markdown("**Current MFI**")
    if not sub.empty and "mfi" in sub.columns:
        st.caption(f"MFI: {float(sub['mfi'].iloc[-1]):.1f}")
    else:
        st.caption("—")

    st.markdown("**Current CMF**")
    if not sub.empty and "cmf" in sub.columns:
        st.caption(f"CMF: {float(sub['cmf'].iloc[-1]):.4f}")
    else:
        st.caption("—")

    st.markdown("**Money Flow Score**")
    if not sub.empty and "money_flow_score" in sub.columns:
        st.caption(f"Score: {int(sub['money_flow_score'].iloc[-1])} (관측용)")
    else:
        st.caption("—")

    st.markdown("**Energy Score**")
    if not sub.empty and "energy_score" in sub.columns:
        st.caption(f"Energy: {int(sub['energy_score'].iloc[-1])}")
    else:
        st.caption("—")

    st.markdown("**Divergence**")
    if not sub.empty and "bullish_div" in sub.columns:
        div = str(sub["bullish_div"].iloc[-1])
        st.caption(div if div else "none")
    else:
        st.caption("—")

    st.markdown("**Score별 성과**")
    for r in score_perf:
        st.caption(f"MF {r['score']}: n={r['n']}, win={r['win_rate']}, exp={r['expectancy']}")
