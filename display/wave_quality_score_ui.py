"""Wave Quality Score UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_quality_score():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_quality_score.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_QUALITY_SCORE.md")
    if not os.path.isfile(path):
        return {}
    sections = {}
    current = None
    lines_acc: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                if current:
                    sections[current] = "\n".join(lines_acc)
                current = line[3:].strip()
                lines_acc = []
            elif current:
                lines_acc.append(line.rstrip())
        if current:
            sections[current] = "\n".join(lines_acc)
    return sections


def render_wave_quality_score_panel(symbol: str, interval: str) -> None:
    st.markdown("### Wave Quality Score")

    df = load_quality_score()
    if df.empty:
        st.warning("Quality Score 데이터 없음 — wave_quality_score_sweep.py 실행 필요")
        return

    sub = df[df["symbol"] == symbol]
    if sub.empty:
        st.caption(f"{symbol} 데이터 없음")
        return

    last = sub.iloc[-1]
    score = int(last.get("quality_score", 0))
    st.caption(f"Quality Score: {score}/7 (관측용)")

    flags = [
        ("TB", last.get("flag_tb")),
        ("Structure≥3", last.get("flag_structure")),
        ("Energy≥3", last.get("flag_energy")),
        ("MF≥4", last.get("flag_money_flow")),
        ("Bull Div", last.get("flag_divergence")),
        ("<MA480", last.get("flag_price_ma480")),
        ("MA120↑", last.get("flag_ma120_slope")),
    ]
    active = [name for name, on in flags if on in (True, "True", 1, "1")]
    st.caption(f"Active: {', '.join(active) if active else '—'}")

    sections = _load_report_sections()
    mono = sections.get("10. Monotonicity 판정", "")
    if mono:
        st.markdown("**Monotonicity**")
        for line in mono.splitlines()[:3]:
            if line.strip():
                st.caption(line.strip())

    imp = sections.get("Feature Importance Ranking", "")
    if imp:
        st.markdown("**Importance (top 3)**")
        for line in imp.splitlines():
            if line.startswith("|") and "---" not in line and "rank" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    st.caption(f"{parts[0]}. {parts[1]}")
                if parts and parts[0] == "3":
                    break
