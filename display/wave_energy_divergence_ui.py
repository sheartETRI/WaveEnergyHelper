"""Wave Energy Divergence UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_energy_divergence():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_energy_divergence.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_ENERGY_DIVERGENCE.md")
    if not os.path.isfile(path):
        return None, [], []
    bull_rate, wave_combos, success_rate = None, [], None
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1. Bullish"):
                section = "bull"
            elif line.startswith("## 4. Wave + Divergence"):
                section = "wave"
            elif line.startswith("- success_div_rate:"):
                success_rate = line.split(":")[-1].strip().strip("*")
            elif line.startswith("- bullish_div_rate:") and bull_rate is None:
                bull_rate = line.split(":")[-1].strip().strip("*")
            elif section == "wave" and line.startswith("|") and "combo" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    wave_combos.append({
                        "combo": parts[0], "n": parts[1],
                        "win_rate": parts[2], "expectancy": parts[3],
                    })
            elif line.startswith("## ") and section:
                section = None
    return bull_rate, wave_combos[:5], success_rate


def render_wave_energy_divergence_panel(symbol: str, interval: str) -> None:
    st.markdown("### Energy Divergence")

    df = load_energy_divergence()
    if df.empty:
        st.warning("Energy Divergence 데이터 없음 — wave_energy_divergence_sweep.py 실행 필요")
        return

    bull_rate, wave_combos, success_rate = _load_report_sections()
    sub = df[df["symbol"] == symbol]

    st.markdown("**Current Divergence**")
    if not sub.empty:
        last = sub.iloc[-1]
        bull = str(last.get("bullish_div", ""))
        st.caption(f"Latest: {bull if bull else 'none'} (관측용)")
    else:
        st.caption("—")

    st.markdown("**Divergence Strength**")
    if not sub.empty and "div_strength" in sub.columns:
        st.caption(f"div_strength: {sub['div_strength'].iloc[-1]:.1f}")
    else:
        st.caption("—")

    st.markdown("**Wave + Divergence**")
    for r in wave_combos:
        st.caption(f"{r['combo']}: n={r['n']}, win={r['win_rate']}, exp={r['expectancy']}")
    if not wave_combos:
        st.caption("—")

    st.markdown("**Success Rate**")
    st.caption(f"Bullish div (overall): {bull_rate or '—'}")
    st.caption(f"Bullish div (success cohort): {success_rate or '—'}")
