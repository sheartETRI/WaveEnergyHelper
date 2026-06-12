"""Wave Live Forward Journal UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_forward_journal():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_live_forward_journal.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_sections():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_LIVE_FORWARD_JOURNAL.md")
    if not os.path.isfile(path):
        return [], [], [], []
    active, rule_rows, priority, pattern = [], [], [], []
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 1."):
                section = "active"
            elif line.startswith("## 2."):
                section = "rule"
            elif line.startswith("## 8."):
                section = "prio"
            elif line.startswith("## 10."):
                section = "pattern"
            elif line.startswith("## ") and section:
                section = None
            elif section == "active" and line.startswith("|") and "symbol" not in line and "---" not in line and "—" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 7:
                    active.append(f"{parts[0]} {parts[1]} {parts[2]} ({parts[6]})")
            elif section == "rule" and line.startswith("|") and "rule" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 9:
                    rule_rows.append(f"{parts[0]}: wr20={parts[6]}, avg20={parts[8]}")
            elif section == "prio" and line.startswith("- #"):
                priority.append(line.lstrip("- "))
            elif section == "pattern" and line.startswith("- **"):
                pattern.append(line.lstrip("- "))
    return active[:8], rule_rows[:5], priority[:6], pattern[:3]


def render_wave_live_forward_journal_panel(symbol: str, interval: str) -> None:
    st.markdown("### Live Forward Journal")

    df = load_forward_journal()
    if df.empty:
        st.warning("Forward Journal 데이터 없음 — wave_live_forward_journal_sweep.py 실행 필요")
        return

    active_snip, rule_snip, prio_snip, pattern_snip = _load_report_sections()

    st.markdown("**Active Candidates**")
    for row in active_snip:
        st.caption(f"- {row}")
    if not active_snip:
        st.caption("—")

    st.markdown("**Pending Events**")
    if "status" in df.columns:
        pend = df[df["status"] != "COMPLETED"]["status"].value_counts()
        for st_name, cnt in pend.head(5).items():
            st.caption(f"- {st_name}: {cnt}")
        if pend.empty:
            st.caption("—")
    else:
        st.caption("—")

    st.markdown("**Completed Events**")
    if "status" in df.columns:
        comp = int((df["status"] == "COMPLETED").sum())
        st.caption(f"COMPLETED: {comp}")
    else:
        st.caption("—")

    st.markdown("**Rule별 Forward 성과**")
    for row in rule_snip:
        st.caption(row)
    if not rule_snip:
        st.caption("—")

    st.markdown("**현재 추적 우선순위**")
    for row in prio_snip:
        st.caption(f"- {row}")
    if not prio_snip:
        st.caption("—")

    cell = df[(df["symbol"] == symbol) & (df["timeframe"] == interval)] if "symbol" in df.columns else df.iloc[0:0]
    if not cell.empty and "freshness" in cell.columns:
        recent = cell[cell["freshness"].isin(["ACTIVE", "RECENT"])].sort_values("timestamp")
        if not recent.empty:
            st.markdown("**현재 심볼/TF Journal**")
            for _, row in recent.tail(3).iterrows():
                st.caption(
                    f"- {row.get('rule', '')} {row.get('status', '')} "
                    f"ret20={row.get('return_20', '—')} {row.get('outcome_20', '')}"
                )

    if pattern_snip:
        st.caption(pattern_snip[0])
