"""F2-b 게이트 패널 · 추적 현황 · 데이터 신선도 (표시 전용).

세 패널 모두 상태 기술형 문구만 쓰고, 성과 지표는 표시하지 않는다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.wave_align_gate_forward import PROMOTED_LTF_TO_HTF
from analysis.wave_htf_gate_v2 import SYMBOLS_V2
from analysis.mm_shadow import VARIANTS
from display.wave_gate_context import (
    GATE_CLOSED,
    GATE_NA,
    GATE_OPEN,
    format_lag,
    freshness,
    gate_rows,
    gate_state_for,
    promoted_htf,
    state_text,
    tracking_counts,
)

HTFS = ("1d", "4h")

GATE_PANEL_CAPTION = (
    "F2-b(MA60·120·240 동시 상승) 상태. 마지막 **닫힌** HTF 봉 기준이며 "
    "진행 중 봉은 반영하지 않는다. 상태 표시일 뿐 매매 지시가 아니다."
)


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:2px 8px;"
        f"border-radius:10px;font-size:0.82rem'>{text}</span>"
    )


def render_gate_panel() -> None:
    """항목 1 — 심볼×HTF 게이트 표. 메인 화면 상단 고정."""
    st.markdown("#### 상위 TF 게이트 (F2-b)")
    rows = gate_rows()
    if not rows:
        st.caption("게이트 상태를 불러오지 못했습니다. (표시 전용 — 분석은 계속됩니다)")
        return

    header = st.columns([1.1, 1, 1, 1])
    header[0].markdown("**HTF / 심볼**")
    for col, sym in zip(header[1:], SYMBOLS_V2):
        col.markdown(f"**{sym.replace('USDT', '')}**")

    for htf in HTFS:
        cols = st.columns([1.1, 1, 1, 1])
        cols[0].markdown(f"`{htf}`")
        for col, sym in zip(cols[1:], SYMBOLS_V2):
            r = gate_state_for(sym, htf, rows)
            label = state_text(r)
            color = {"개방": "#2E7D32", "폐쇄": "#9E9E9E", "미적용": "#BDBDBD"}[label]
            col.markdown(_badge(label, color), unsafe_allow_html=True)
            bars = int(r.get("open_bars") or 0)
            rate = r.get("open_rate_recent")
            rate_txt = "—" if rate is None else f"{rate * 100:.0f}%"
            col.caption(f"연속 {bars}봉 · 최근 120봉 {rate_txt}")

    st.caption(GATE_PANEL_CAPTION)


def render_tracking_status() -> None:
    """항목 5 — 기록 행 수·커버리지·다음 열람일. **성과 지표 표시 금지.**"""
    t = tracking_counts()
    st.markdown("#### 추적 현황")
    cols = st.columns(3)
    cols[0].metric("F2-b 사이드카 (승격 쌍)", f"{t['gate_rows']}행")
    shadow_total = sum(t["shadow_by_variant"].values())
    cols[1].metric("MM 섀도 기록", f"{shadow_total}행")
    cols[2].metric("다음 열람일", str(pd.Timestamp(t["review_due"]).date()))

    by_variant = " · ".join(f"{v} {t['shadow_by_variant'].get(v, 0)}" for v in VARIANTS)
    st.caption(f"섀도 변형별: {by_variant}")

    def _span(a, b):
        if a is None or b is None:
            return "—"
        return f"{pd.Timestamp(a).date()} ~ {pd.Timestamp(b).date()}"

    st.caption(
        f"커버리지 — 게이트 {_span(t.get('gate_first'), t.get('gate_last'))} · "
        f"섀도 {_span(t.get('shadow_first'), t.get('shadow_last'))}"
    )
    st.caption(
        "기록 현황만 표시한다. 성과 지표(G·Δ·수익률·승률)는 열람일까지 화면에 "
        "올리지 않는다 — 상시 표시는 열람 동결의 우회다."
    )


def render_data_freshness(symbol: str, interval: str, df) -> None:
    """항목 6 — 마지막 수신 봉·사이드카 기록 시각·지연. 색상 경고만."""
    st.markdown("#### 데이터 신선도")
    now = pd.Timestamp.utcnow().tz_localize(None)

    last_bar = None
    if df is not None and not getattr(df, "empty", True):
        last_bar = pd.Timestamp(df.index[-1])
    f = freshness(interval, last_bar, now)

    rows = [{
        "대상": f"{symbol} {interval} 마지막 봉",
        "시각": "—" if f["last_bar"] is None else str(f["last_bar"]),
        "지연": format_lag(f["lag"]),
        "warn": f["warn"],
    }]

    htf = promoted_htf(interval)
    if htf:
        for r in gate_rows():
            if r.get("symbol") == symbol and r.get("htf") == htf:
                hf = freshness(htf, r.get("htf_open_time"), now)
                rows.append({
                    "대상": f"{symbol} {htf} 게이트 기준 봉",
                    "시각": "—" if hf["last_bar"] is None else str(hf["last_bar"]),
                    "지연": format_lag(hf["lag"]),
                    "warn": hf["warn"],
                })
                break

    t = tracking_counts()
    for label, key in (("F2-b 사이드카 기록", "gate_mtime"), ("MM 섀도 기록", "shadow_mtime")):
        ts = t.get(key)
        rows.append({
            "대상": label,
            "시각": "—" if ts is None else str(pd.Timestamp(ts)),
            "지연": "—" if ts is None else format_lag(now - pd.Timestamp(ts)),
            "warn": False,
        })

    for r in rows:
        color = "#EF5350" if r["warn"] else "#9E9E9E"
        st.markdown(
            f"<div style='font-size:0.86rem'>"
            f"<span style='color:{color}'>●</span> {r['대상']} — "
            f"{r['시각']} (지연 {r['지연']})</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        f"지연이 해당 TF {2}봉을 넘으면 붉게 표시한다. 알림·자동 실행은 하지 않는다."
    )
