"""Wave Rule Grading UI."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from analysis.wave_rule_grading import (
    ALL_SYMBOL,
    ALL_TIMEFRAME,
    GRADE_ORDER,
    check_monotonicity,
    compute_calibration,
)

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_rule_grading():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_rule_grading.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def _summary_from_csv(df):
    all_rows = df[(df["symbol"] == ALL_SYMBOL) & (df["timeframe"] == ALL_TIMEFRAME)]
    summary = {}
    for g in GRADE_ORDER:
        row = all_rows[all_rows["grade"] == g]
        if row.empty:
            continue
        r = row.iloc[0]
        summary[g] = {
            "n": int(r.get("count", 0)),
            "win_rate": float(r.get("win_rate", 0)),
            "expectancy": float(r.get("expectancy", 0)) if pd.notna(r.get("expectancy")) else None,
            "profit_factor": float(r.get("profit_factor", 0)) if pd.notna(r.get("profit_factor")) else None,
        }
    return summary


def render_wave_rule_grading_panel(symbol: str, interval: str) -> None:
    st.markdown("### Rule Grading")

    df = load_rule_grading()
    if df.empty:
        st.warning("Rule Grading 데이터 없음 — wave_rule_grading_sweep.py 실행 필요")
        return

    summary = _summary_from_csv(df)
    mono = check_monotonicity(summary)
    calibration = compute_calibration(summary)

    st.markdown("**Grade Summary**")
    all_rows = df[(df["symbol"] == ALL_SYMBOL) & (df["timeframe"] == ALL_TIMEFRAME)]
    for g in GRADE_ORDER:
        row = all_rows[all_rows["grade"] == g]
        if row.empty:
            continue
        r = row.iloc[0]
        st.caption(
            f"Grade {g} — n={int(r.get('count', 0))}, "
            f"exp {r.get('expectancy', 0):.2f}%, win {r.get('win_rate', 0):.1f}%, "
            f"PF {r.get('profit_factor', 0):.2f}"
        )

    st.markdown("**Calibration**")
    for r in calibration:
        st.caption(f"Grade {r['grade']}: {r.get('actual_win', 0):.1f}%")

    st.markdown("**Monotonicity**")
    st.caption(f"Result: {mono.get('result', 'FAIL')}")
    for metric, detail in mono.get("details", {}).items():
        ok = "PASS" if detail.get("pass") else "FAIL"
        st.caption(f"- {metric}: {ok}")
