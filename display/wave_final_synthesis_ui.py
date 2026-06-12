"""Wave Final Synthesis UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_FINAL_SYNTHESIS.md")
    if not os.path.isfile(path):
        return "", [], "", ""
    exec_sum, framework, verdict = [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## Executive Summary"):
                section = "exec"
            elif line.startswith("## Final Champion Framework"):
                section = "fw"
            elif line.startswith("## Final Verdict"):
                section = "verdict"
            elif line.startswith("## ") and section:
                section = None
            elif section == "exec" and line.startswith("- "):
                exec_sum.append(line[2:])
            elif section == "fw" and line.startswith("- **"):
                framework.append(line)
            elif section == "verdict" and line.startswith("### **"):
                verdict = line.replace("### **", "").replace("**", "")
    return exec_sum[:6], framework[:6], verdict, path


def render_wave_final_synthesis_panel(symbol: str, interval: str) -> None:
    st.markdown("### Final Synthesis")

    exec_sum, framework, verdict, report_path = _load_report_sections()
    if not report_path:
        st.warning("Final Synthesis 없음 — wave_final_synthesis_sweep.py 실행 필요")
        return

    st.markdown("**Executive Summary**")
    for row in exec_sum:
        st.caption(row)

    if verdict:
        st.markdown(f"**Final Verdict: {verdict}**")

    st.markdown("**Champion Framework**")
    for row in framework:
        st.caption(row.replace("**", ""))

    png = os.path.join(_VALIDATION_DIR, "wave_final_synthesis.png")
    if os.path.isfile(png):
        st.image(png, use_container_width=True)
