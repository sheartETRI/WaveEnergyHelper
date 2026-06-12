"""Wave Grade Post-Event UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_grade_post_event():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_grade_post_event.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_GRADE_POST_EVENT.md")
    if not os.path.isfile(path):
        return [], None, []
    delay_out, valid_until, best = [], None, []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Delay Outcome"):
                section = "delay"
            elif line.startswith("## Validity Window"):
                section = "valid"
            elif line.startswith("## Exit Policy by Delay"):
                section = "policy"
            elif line.startswith("- valid_until_delay:"):
                valid_until = line.split(":")[-1].strip().strip("*")
            elif line.startswith("## ") and section:
                section = None
            elif section == "delay" and line.startswith("|") and "delay" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    delay_out.append({
                        "delay": parts[0],
                        "win_rate": parts[1],
                        "expectancy": parts[2],
                    })
            elif section == "policy" and line.startswith("|") and "delay" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    best.append({
                        "delay": parts[0],
                        "policy": parts[1],
                        "expectancy": parts[2],
                    })
    return delay_out[:4], valid_until, best[:8]


def render_wave_grade_post_event_panel(symbol: str, interval: str) -> None:
    st.markdown("### Grade Post Event")

    df = load_grade_post_event()
    if df.empty:
        st.warning("Grade Post Event 데이터 없음 — wave_grade_post_event_sweep.py 실행 필요")
        return

    delay_out, valid_until, best_policies = _load_report_sections()

    st.markdown("**Delay Outcome**")
    for r in delay_out:
        st.caption(f"- delay {r['delay']}: win {r['win_rate']}, exp {r['expectancy']}")
    if not delay_out:
        st.caption("—")

    st.markdown("**Validity Window**")
    st.caption(f"valid_until_delay: {valid_until or '—'}")

    st.markdown("**Best Policy by Delay**")
    for r in best_policies:
        st.caption(f"- d{r['delay']}: {r['policy']} (exp {r['expectancy']})")
    if not best_policies:
        st.caption("—")

    sub = df[(df["symbol"] == symbol) & (df["timeframe"] == interval)]
    if not sub.empty:
        st.caption(f"{symbol} {interval}: {len(sub)} rows in CSV")
