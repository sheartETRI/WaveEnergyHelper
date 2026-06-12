"""Wave Confirmation Gate UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_confirmation_gate():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_confirmation_gate.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_CONFIRMATION_GATE.md")
    if not os.path.isfile(path):
        return [], [], [], None
    gates, composites, funnel, best_h = [], [], [], None
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Top Gates"):
                section = "gates"
            elif line.startswith("## Composite Gates"):
                section = "comp"
            elif line.startswith("## Gate Funnel"):
                section = "funnel"
            elif line.startswith("## Best Horizon"):
                section = "horizon"
            elif line.startswith("## ") and section:
                section = None
            elif section == "gates" and line.startswith("|") and "gate" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    gates.append({"gate": parts[0], "precision": parts[1], "recall": parts[2]})
            elif section == "comp" and line.startswith("|") and "gate" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    composites.append({"gate": parts[0], "precision": parts[1], "recall": parts[2]})
            elif section == "funnel" and line.startswith("|") and "stage" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    funnel.append({"stage": parts[0], "survivors": parts[1]})
            elif section == "horizon" and line.startswith("- horizon:"):
                val = line.split("**")
                if len(val) >= 2:
                    best_h = val[1]
    return gates[:5], composites[:5], funnel, best_h


def render_wave_confirmation_gate_panel(symbol: str, interval: str) -> None:
    st.markdown("### Confirmation Gate")

    df = load_confirmation_gate()
    if df.empty:
        st.warning("Confirmation Gate 데이터 없음 — wave_confirmation_gate_sweep.py 실행 필요")
        return

    gates, composites, funnel, best_h = _load_report_sections()

    st.markdown("**Top Gates**")
    for r in gates:
        st.caption(f"- {r['gate'][:50]} — P {r['precision']}, R {r['recall']}")
    if not gates:
        st.caption("—")

    st.markdown("**Composite Gates**")
    for r in composites:
        st.caption(f"- {r['gate'][:45]} — P {r['precision']}, R {r['recall']}")
    if not composites:
        st.caption("—")

    st.markdown("**Funnel**")
    for r in funnel:
        st.caption(f"{r['stage']}: {r['survivors']}")
    if not funnel:
        st.caption("—")

    st.markdown("**Best Horizon**")
    st.caption(f"+{best_h}" if best_h else "—")
