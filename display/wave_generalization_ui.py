"""Wave Generalization UI."""

from __future__ import annotations

import os

import streamlit as st

from analysis.wave_generalization import summarize_generalization

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_generalization():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_generalization.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def render_wave_generalization_panel(symbol: str, interval: str) -> None:
    st.markdown("### Generalization")

    df = load_generalization()
    if df.empty:
        st.warning("Generalization 데이터 없음 — wave_generalization_sweep.py 실행 필요")
        return

    rows = df.to_dict("records")
    stats = summarize_generalization(rows)
    st.caption(f"12-cell matrix — {stats['total_cells']} cells")

    st.markdown("**Rule Ranking**")
    for i, r in enumerate(stats.get("top_rules", [])[:5], 1):
        gs = r.get("generalization_score")
        gs_txt = f"{gs:.2f}" if gs is not None else "—"
        st.caption(
            f"{i}. {r.get('rule', '')} — gen {gs_txt}, "
            f"med exp {_fmt(r.get('median_expectancy'))}% "
            f"(+{r.get('positive_cells', 0)} cells)"
        )

    st.markdown("**Positive Cell Ratio**")
    for r in stats.get("rule_summary", [])[:5]:
        st.caption(
            f"- {r.get('rule', '')}: {r.get('positive_rate', 0):.1f}% "
            f"({r.get('positive_cells', 0)} cells)"
        )

    st.markdown("**Variance Ranking**")
    for i, v in enumerate(stats.get("rule_variance", [])[:5], 1):
        st.caption(
            f"{i}. {v.get('rule', '')} — variance {_fmt(v.get('overall_variance'))}"
        )


def _fmt(v):
    if v is None:
        return "—"
    return f"{v:.2f}"
