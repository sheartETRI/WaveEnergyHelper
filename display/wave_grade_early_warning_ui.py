"""Wave Grade Early Warning UI."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_early_warning():
    path = os.path.join(_VALIDATION_DIR, "wave_grade_early_warning.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_GRADE_EARLY_WARNING.md")
    if not os.path.isfile(path):
        return [], None, [], []
    seps, horizon, cands, rates = [], None, [], []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Top Early Separators"):
                section = "sep"
            elif line.startswith("## Best Horizon"):
                section = "horizon"
            elif line.startswith("## Top Candidates"):
                section = "cand"
            elif line.startswith("## Future Grade A Rate"):
                section = "rate"
            elif line.startswith("## ") and section:
                section = None
            elif section == "sep" and line.startswith("|") and "feature" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    seps.append({"feature": parts[0], "effect": parts[1], "offset": parts[2]})
            elif section == "horizon" and line.startswith("|") and "offset" not in line and "---" not in line:
                parts = [p.strip().strip("*") for p in line.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0].lstrip("-").isdigit() or parts[0].startswith("-"):
                    try:
                        off = int(parts[0])
                        if horizon is None or "**" in line:
                            horizon = off
                    except ValueError:
                        pass
            elif section == "cand" and line.startswith("|") and "candidate" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    cands.append({
                        "candidate": parts[0],
                        "precision": parts[1],
                        "recall": parts[2],
                    })
            elif section == "rate" and line.startswith("|") and "candidate" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    rates.append({"candidate": parts[0], "rate": parts[1]})
    return seps[:5], horizon, cands[:5], rates[:5]


def render_wave_grade_early_warning_panel(symbol: str, interval: str) -> None:
    st.markdown("### Grade Early Warning")

    df = load_early_warning()
    if df.empty:
        st.warning("Early Warning 데이터 없음 — wave_grade_early_warning_sweep.py 실행 필요")
        return

    pos_n = len(df[df["positive"] == True]) if "positive" in df.columns else 0
    st.caption(f"Positive snapshots: {pos_n}")

    seps, horizon, cands, rates = _load_report_sections()

    st.markdown("**Top Separators**")
    for i, r in enumerate(seps, 1):
        st.caption(f"{i}. {r['feature']} — effect {r['effect']} (offset {r['offset']})")
    if not seps:
        st.caption("—")

    st.markdown("**Best Horizon**")
    st.caption(f"offset: {horizon if horizon is not None else '—'}")

    st.markdown("**Top Candidates**")
    for r in cands:
        st.caption(f"- {r['candidate'][:50]} — P {r['precision']}, R {r['recall']}")
    if not cands:
        st.caption("—")

    st.markdown("**Future Grade A Rate**")
    for r in rates:
        st.caption(f"- {r['candidate'][:45]}: {r['rate']}")
    if not rates:
        st.caption("—")
