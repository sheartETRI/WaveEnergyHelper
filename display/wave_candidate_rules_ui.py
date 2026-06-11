"""Wave Candidate Rules UI."""

from __future__ import annotations

import os

import streamlit as st

from analysis.wave_candidate_rules import summarize_candidate_rules

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_candidate_rules(symbol: str, interval: str):
    import pandas as pd

    path = os.path.join(
        _VALIDATION_DIR, f"wave_candidate_rules_{symbol}_{interval}.csv",
    )
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def render_wave_candidate_rules_panel(symbol: str, interval: str) -> None:
    st.markdown("### Candidate Rules")

    rules_df = load_candidate_rules(symbol, interval)
    if rules_df.empty:
        st.warning("Candidate Rules 데이터 없음")
        return

    stats = summarize_candidate_rules(rules_df, symbol, interval)
    st.caption(f"{symbol} {interval} — confluence events={stats.get('count', 0)}")

    st.markdown("**Top Rules**")
    for i, r in enumerate(stats.get("top_rules", [])[:5], 1):
        st.caption(
            f"{i}. {r.get('rule', '')} — stability {r.get('stability_score', 0):.2f}, "
            f"exp {r.get('expectancy', 0):.2f}% (n={r.get('n', 0)})"
        )

    st.markdown("**Stability Ranking**")
    for i, s in enumerate(stats.get("stability_scores", [])[:5], 1):
        st.caption(
            f"{i}. {s.get('rule', '')} — score {s.get('stability_score', 0):.2f} "
            f"(exp {s.get('expectancy', 0):.2f}%)"
        )

    st.markdown("**Failure Summary**")
    seen = set()
    for f in stats.get("failure_analysis", []):
        key = (f.get("rule"), f.get("failure_reason"))
        if key in seen:
            continue
        seen.add(key)
        st.caption(
            f"- {f.get('rule', '')} / {f.get('failure_reason', '')}: "
            f"{f.get('pct', 0):.1f}%"
        )
        if len(seen) >= 8:
            break
