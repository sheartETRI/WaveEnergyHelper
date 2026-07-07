"""v2 관측 계기판 렌더 (9차 위임 B·C·D) — streamlit 표시 + 관측 저널 누적.

build_* 는 순수 텍스트(테스트 가능), render_* 는 streamlit 래퍼. 모두 관측·표시·저널 전용 —
등급/추천/판정 문구 금지("관측" 라벨 유지). 로직은 analysis/observatory.py.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from analysis.observatory import (
    append_observatory_journal,
    array_state,
    composite_trend_label,
    monthly_stoch_position,
    precursor_channel,
    slope_state,
    slope_state_ko,
)
from analysis.trend_layer import add_trend_observation


# ---------------------------------------------------------------- 데이터 헬퍼
def _load_full(symbol: str, tf: str):
    from analysis.campaign_state_machine import prepare_base_frame
    from display.asof import fetch_ohlcv_bare

    bare = fetch_ohlcv_bare(symbol, tf)
    if bare is None or bare.empty:
        return None
    return prepare_base_frame(bare)


# ---------------------------------------------------------------- C. slope 계기판
def build_slope_dashboard_lines(symbol: str, s1d: Optional[dict], s4d: Optional[dict]) -> List[str]:
    st1 = s1d["state"] if s1d else None
    st4 = s4d["state"] if s4d else None
    comp = composite_trend_label(st1, st4)
    lines = [f"추세 slope 계기판 · {symbol} — [관측]"]
    lines.append(f"1d 60MA: {slope_state_ko(st1)}"
                 + (f" (slope {s1d['slope']*100:+.3f}%, 평탄임계 {s1d['flat_thr']*100:.3f}%)" if s1d else " (데이터 부족)"))
    lines.append(f"4d 60MA: {slope_state_ko(st4)}"
                 + (f" (slope {s4d['slope']*100:+.3f}%, 평탄임계 {s4d['flat_thr']*100:.3f}%)" if s4d else " (데이터 부족)"))
    lines.append(f"종합: {comp['label']}  ·  {comp['note']}")
    return lines


def render_slope_dashboard(symbol: str) -> Optional[dict]:
    import streamlit as st

    f1d = _load_full(symbol, "1d")
    f4d = _load_full(symbol, "4d")
    s1d = slope_state(f1d, period=60) if f1d is not None else None
    s4d = slope_state(f4d, period=60) if f4d is not None else None
    lines = build_slope_dashboard_lines(symbol, s1d, s4d)
    with st.container(border=True):
        st.markdown(f"**{lines[0]}**")
        for ln in lines[1:]:
            st.caption(ln)
    comp = composite_trend_label(s1d["state"] if s1d else None, s4d["state"] if s4d else None)
    ts = f1d.index[-1].isoformat() if f1d is not None and len(f1d) else ""
    append_observatory_journal({
        "ts": ts, "symbol": symbol, "tf": "1d/4d", "kind": "slope_dash",
        "slope_1d_state": s1d["state"] if s1d else "n/a",
        "slope_4d_state": s4d["state"] if s4d else "n/a",
        "composite_label": comp["label"],
    })
    return {"s1d": s1d, "s4d": s4d, "composite": comp}


# ---------------------------------------------------------------- B. 월봉 대파동 위치
def build_monthly_stoch_lines(symbol: str, pos: Optional[dict], n_bars: int) -> List[str]:
    lines = [f"월봉(1M) 대파동 스토캐(40,20,20) 위치 · {symbol} — [관측 · 표본 희소, 통계/승격 아님]"]
    if pos is None:
        lines.append("데이터 부족 — 월봉 스토캐 4층 산출 불가")
        return lines
    dline = f" (K {pos['k']:.1f}" + (f" · D {pos['d']:.1f}" if pos['d'] is not None else "") + ")"
    lines.append(f"현재: {pos['zone']} · {pos['direction']} 제스처{dline}")
    lines.append(f"히스토리 {n_bars}개월 · MA60까지만 산출(MA120 불가) · 대파동 바닥 제스처 눈대중 아닌 수치 확인용")
    return lines


def render_monthly_stoch_panel(symbol: str) -> Optional[dict]:
    import streamlit as st

    f1m = _load_full(symbol, "1M")
    n_bars = 0 if f1m is None else len(f1m)
    pos = None
    if f1m is not None:
        try:
            obs = add_trend_observation(f1m.copy())
            pos = monthly_stoch_position(obs)
        except Exception:
            pos = None
    lines = build_monthly_stoch_lines(symbol, pos, n_bars)
    with st.container(border=True):
        st.markdown(f"**{lines[0]}**")
        for ln in lines[1:]:
            st.caption(ln)
    ts = f1m.index[-1].isoformat() if f1m is not None and len(f1m) else ""
    if pos is not None:
        append_observatory_journal({
            "ts": ts, "symbol": symbol, "tf": "1M", "kind": "monthly_stoch",
            "monthly_zone": pos["zone"], "monthly_direction": pos["direction"],
        })
    return pos


# ---------------------------------------------------------------- D. 전조 채널 슬롯
def build_precursor_lines(tf: str, pc: dict) -> List[str]:
    lines = [f"전조 슬롯 ({tf}) — 배열 {pc['state']} [관측 · 스펙 §2.5]"]
    if not pc["active"]:
        lines.append(pc["reason"])
        return lines
    lines.append(f"활성 채널: {pc['channel']}  ·  이유: {pc['reason']}")
    if pc["confirmed_ts"] is not None:
        lines.append(f"최근 확정 전조: {pd.Timestamp(pc['confirmed_ts']):%Y-%m-%d %H:%M}")
    else:
        lines.append("최근 확정 전조: 없음(관측 창 내)")
    if pc["candidates"]:
        for c in pc["candidates"][:3]:
            nl = "—" if getattr(c, "neckline_price", None) is None else f"{c.neckline_price:.6g}"
            lines.append(f"  후보(candidate): {c.ma_or_layer} 쌍봉 · 넥라인 {nl} 하향 돌파 대기 [미확정]")
    elif pc["state"] == "비정배열":
        lines.append("  (대파동 스토캐 candidate 스캐너 부재 — 확정만 표시)")
    return lines


def render_precursor_slot(full, symbol: str, tf: str) -> Optional[dict]:
    import streamlit as st

    if full is None or len(full) == 0:
        return None
    pc = precursor_channel(full, symbol, tf)
    lines = build_precursor_lines(tf, pc)
    with st.container(border=True):
        st.markdown(f"**{lines[0]}**")
        for ln in lines[1:]:
            st.caption(ln)
    ts = full.index[-1].isoformat() if len(full) else ""
    append_observatory_journal({
        "ts": ts, "symbol": symbol, "tf": tf, "kind": "precursor",
        "array_state": pc["state"], "active_channel": pc["channel"] or "없음",
        "precursor_confirmed_ts": "" if pc["confirmed_ts"] is None else pd.Timestamp(pc["confirmed_ts"]).isoformat(),
        "n_candidates": len(pc["candidates"]),
    })
    return pc
