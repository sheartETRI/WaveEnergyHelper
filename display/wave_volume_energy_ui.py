"""Wave Volume Energy UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_volume_energy():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_volume_energy.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_VOLUME_ENERGY.md")
    if not os.path.isfile(path):
        return [], [], []
    score_perf, combos, separators = [], [], []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 3. Energy Score"):
                section = "score"
            elif line.startswith("## 4. Wave + Energy"):
                section = "combo"
            elif line.startswith("## 2. Top Volume"):
                section = "sep"
            elif line.startswith("## ") and section:
                section = None
            elif section == "score" and line.startswith("|") and "score" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    score_perf.append({
                        "score": parts[0], "n": parts[1],
                        "win_rate": parts[2], "expectancy": parts[3],
                    })
            elif section == "combo" and line.startswith("|") and "combo" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3:
                    combos.append({"combo": parts[0], "n": parts[1], "expectancy": parts[3] if len(parts) > 3 else "—"})
            elif section == "sep" and line.startswith("|") and "feature" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    separators.append({"feature": parts[0], "effect_size": parts[3]})
    return score_perf[:6], combos[:5], separators[:5]


def render_wave_volume_energy_panel(symbol: str, interval: str) -> None:
    st.markdown("### Volume Energy")

    df = load_volume_energy()
    if df.empty:
        st.warning("Volume Energy 데이터 없음 — wave_volume_energy_sweep.py 실행 필요")
        return

    score_perf, combos, separators = _load_report_sections()
    sub = df[(df["symbol"] == symbol) & (df["timeframe"] == interval)]

    st.markdown("**Current Energy Score**")
    if not sub.empty and "energy_score" in sub.columns:
        last = sub.iloc[-1]
        st.caption(f"Latest: {last.get('energy_score', '—')} (관측용, 신호 아님)")
    else:
        st.caption("—")

    st.markdown("**Volume Ratio**")
    if not sub.empty and "vol_ratio_20" in sub.columns:
        st.caption(f"vol_ratio_20: {sub['vol_ratio_20'].iloc[-1]:.2f}")
    else:
        st.caption("—")

    st.markdown("**OBV Direction**")
    if not sub.empty and "obv_slope_5" in sub.columns:
        os5 = float(sub["obv_slope_5"].iloc[-1])
        st.caption(f"obv_slope_5: {os5:.2f} ({'up' if os5 > 0 else 'down'})")
    else:
        st.caption("—")

    st.markdown("**Energy Score별 성과**")
    for r in score_perf:
        st.caption(f"score {r['score']}: n={r['n']}, win={r['win_rate']}, exp={r['expectancy']}")
    if not score_perf:
        st.caption("—")

    st.markdown("**Wave + Energy 조합 성과**")
    for r in combos:
        st.caption(f"{r['combo']}: n={r['n']}, exp={r['expectancy']}")
    if not combos:
        st.caption("—")

    if separators:
        st.caption(f"Top separator: {separators[0]['feature']} (d={separators[0]['effect_size']})")
