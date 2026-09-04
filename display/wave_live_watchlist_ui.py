"""Wave Live Watchlist UI."""

from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)


@st.cache_data(show_spinner=False, ttl=3600)
def load_live_watchlist():
    import pandas as pd

    path = os.path.join(_VALIDATION_DIR, "wave_live_watchlist.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


@st.cache_data(show_spinner=False, ttl=3600)
def _load_report_snippets():
    path = os.path.join(_VALIDATION_DIR, "REPORT_WAVE_LIVE_WATCHLIST.md")
    if not os.path.isfile(path):
        return [], [], ""
    ranking, heatmap, conclusion = [], [], ""
    section = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("## 4."):
                section = "rank"
            elif line.startswith("## 5."):
                section = "heat"
            elif line.startswith("## 10."):
                section = "conc"
            elif line.startswith("## ") and section:
                section = None
            elif section == "rank" and line.startswith("|") and "rank" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 5:
                    ranking.append(f"#{parts[0]} {parts[1]} {parts[2]} {parts[3]} ({parts[4]})")
            elif section == "heat" and line.startswith("|") and "symbol" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[2] != "NONE":
                    heatmap.append(f"{parts[0]} {parts[1]}: {parts[2]}")
            elif section == "conc" and line and not line.startswith("#"):
                conclusion = line
    return ranking[:8], heatmap[:8], conclusion


def _gate_badge(sym: str, tf: str, rows) -> str:
    """항목 3 — 게이트 통과/비통과 뱃지. 기대값 숫자는 표시하지 않는다."""
    from display.wave_gate_context import gate_state_for, promoted_htf

    htf = promoted_htf(tf)
    if htf is None:
        return "<span style='color:#BDBDBD'>게이트 미적용 TF</span>"
    row = gate_state_for(sym, htf, rows)
    if row.get("gate_align") is None:
        return "<span style='color:#BDBDBD'>게이트 상태 불명</span>"
    if row.get("gate_align"):
        return ("<span style='background:#2E7D32;color:#fff;padding:1px 6px;"
                f"border-radius:8px;font-size:0.78rem'>{htf} 게이트 통과</span>")
    return ("<span style='background:#9E9E9E;color:#fff;padding:1px 6px;"
            f"border-radius:8px;font-size:0.78rem'>{htf} 게이트 비통과</span>")


def render_wave_live_watchlist_panel(symbol: str, interval: str) -> None:
    from display.wave_gate_context import GATE_PROFILE_NOTE, gate_rows

    st.markdown("### Live Watchlist")

    df = load_live_watchlist()
    if df.empty:
        st.warning("Live Watchlist 데이터 없음 — wave_live_watchlist_sweep.py 실행 필요")
        return

    ranking_snip, heat_snip, conclusion = _load_report_snippets()

    active = df[df["freshness"].isin(["ACTIVE", "RECENT"])] if "freshness" in df.columns else df.iloc[0:0]
    cell = df[(df["symbol"] == symbol) & (df["timeframe"] == interval)] if "symbol" in df.columns else df.iloc[0:0]

    st.markdown("**Current Candidates**")
    if not active.empty:
        show = active.sort_values("watchlist_score", ascending=False).head(8)
        rows = gate_rows()
        for _, row in show.iterrows():
            sym, tf = str(row.get("symbol", "")), str(row.get("timeframe", ""))
            st.markdown(
                f"<div style='font-size:0.86rem'>· {sym} {tf} "
                f"{row.get('rule', '')} — score={row.get('watchlist_score', '—')}, "
                f"bars={row.get('bars_since_signal', '—')}, {row.get('freshness', '')} "
                f"{_gate_badge(sym, tf, rows)}</div>",
                unsafe_allow_html=True,
            )
        st.caption(GATE_PROFILE_NOTE)
    else:
        st.caption("—")

    st.markdown("**Watchlist Score** (현재 심볼/TF)")
    if not cell.empty:
        last = cell.sort_values("timestamp").iloc[-1]
        st.caption(
            f"{last.get('rule', '—')}: {last.get('watchlist_score', '—')} "
            f"(MF={last.get('money_flow_score', '—')}, E={last.get('energy_score', '—')}, "
            f"S={last.get('structure_score', '—')})"
        )
    else:
        st.caption("—")

    st.markdown("**Freshness**")
    if not cell.empty and "freshness" in cell.columns:
        for rule in ("RULE_B", "RULE_A", "RULE_C"):
            sub = cell[cell["rule"] == rule]
            if sub.empty:
                continue
            last = sub.sort_values("timestamp").iloc[-1]
            st.caption(f"- {rule}: {last['freshness']} ({last['bars_since_signal']} bars)")
    else:
        st.caption("—")

    st.markdown("**Rule Type**")
    if heat_snip:
        for h in heat_snip:
            st.caption(h)
    else:
        st.caption("현재 활성 Rule 셀 없음")

    if ranking_snip:
        st.markdown("**Top Ranking**")
        for r in ranking_snip[:5]:
            st.caption(r)

    if conclusion:
        st.caption(conclusion)
