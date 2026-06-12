"""Wave Quality Rule Set UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_ruleset_csv():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_quality_ruleset.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_top_rules():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_QUALITY_RULESET.md")
    if not os.path.isfile(path):
        return [], ""
    top_rules = []
    vs_result = ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "top"
            elif line.startswith("## 2."):
                section = None
            elif "Rule Set vs Quality Score" in line:
                vs_result = line.replace("**", "").strip()
            elif section == "top" and line.startswith("|") and "---" not in line and "rule" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    top_rules.append({
                        "rule": parts[0],
                        "n": parts[1],
                        "win_rate": parts[2],
                        "expectancy": parts[3],
                    })
                if len(top_rules) >= 5:
                    section = None
    return top_rules, vs_result


def render_wave_quality_ruleset_panel(symbol: str, interval: str) -> None:
    st.markdown("### Quality Rule Set")

    df = load_ruleset_csv()
    if df.empty:
        st.warning("Rule Set 데이터 없음 — wave_quality_ruleset_sweep.py 실행 필요")
        return

    top_rules, vs_result = _load_report_top_rules()

    if vs_result:
        st.caption(vs_result)

    st.markdown("**Top Expectancy Rules**")
    if top_rules:
        for i, r in enumerate(top_rules[:5], 1):
            st.caption(f"{i}. {r['rule']} — n={r['n']}, exp={r['expectancy']}")
    else:
        st.caption("—")

    qs_path = os.path.join(_VALIDATION_DIR, "wave_quality_score.csv")
    if os.path.isfile(qs_path):
        import pandas as pd
        qdf = pd.read_csv(qs_path)
        sub = qdf[qdf["symbol"] == symbol]
        if not sub.empty:
            last = sub.iloc[-1]
            flags = []
            for col, lbl in [
                ("flag_tb", "TB"), ("flag_structure", "Struct≥3"),
                ("flag_energy", "E≥3"), ("flag_money_flow", "MF≥4"),
                ("flag_divergence", "Div"), ("flag_price_ma480", "<MA480"),
                ("flag_ma120_slope", "MA120↑"),
            ]:
                if last.get(col) in (True, "True", 1, "1"):
                    flags.append(lbl)
            st.caption(f"Current flags: {', '.join(flags) if flags else '—'}")
