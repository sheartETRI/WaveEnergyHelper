"""TF 레이더 패널 — "지금 볼 TF"를 알람 탭 상단에 표시한다 (표시 전용).

전 TF의 스윕 상태기계 스냅숏을 한 표로 요약해, 사용자가 TF를 순회하는 대신
전투가 벌어지는 TF 를 먼저 가리킨다. 판정·게이팅·푸시 발송 아님 —
docs/SPEC_SWEEP_RECLAIM.md §9. 로직은 analysis/tf_radar (순수), 여기는 적재·표시만.

적재는 네이티브 인터벌만(커스텀 재표집 없음), fetch/build 캐시(ttl 600)에 얹혀
레이더 자체 캐시는 두지 않는다 — 새로고침 시 최신 봉 반영은 기존 버튼 관례를 따른다.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from analysis.tf_radar import RadarRow, STATUS_BATTLE, build_tf_radar, pick_focus
from config.settings import TF_RADAR_PARAMS
from data.binance import fetch_klines, get_auto_limit, stale_age
from data.processor import build_dataframe

# 섹션 제목·고정 캡션 — 화면과 전체 복사용 텍스트(display.alarm_copy_text)가 같은 문자열을 쓴다
SECTION_TITLE = "TF 레이더"
FIXED_CAPTION = ("어느 TF의 뻔한 레벨에서 전투(이탈 에피소드)가 벌어지는지 교차 TF 요약 — "
                 "표시 전용 관측 편의(판정·게이팅·푸시 아님), SPEC §9")


def _radar_frame(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """레이더용 OHLCV 적재 — 실패는 None (그 TF 행만 '데이터 없음')."""
    try:
        raw = fetch_klines(symbol, interval, get_auto_limit(interval))
        if not raw:
            return None
        return build_dataframe(raw)
    except Exception:
        return None


def load_radar_frames(symbol: str) -> dict[str, Optional[pd.DataFrame]]:
    """설정된 사다리(상위 TF 먼저) 순서대로 {interval: df}."""
    return {
        interval: _radar_frame(symbol, interval)
        for interval in TF_RADAR_PARAMS["intervals"]
    }


def _headline(focus: Optional[RadarRow]) -> str:
    if focus is None:
        return "지금 볼 TF: **없음** — 전 TF 조용 (열려 있는 에피소드 없음)"
    line = f"지금 볼 TF: **{focus.interval}** — {focus.status}"
    if focus.side != "―":
        line += f" ({focus.side})"
    if focus.detail:
        line += f" · {focus.detail}"
    return line


def headline_line(focus: Optional[RadarRow]) -> str:
    """화면 헤드라인 한 줄(마크다운) — 전투 중이면 🔔 를 앞에 붙인다. 화면·전체 복사용 텍스트 공통."""
    if focus is not None and focus.status == STATUS_BATTLE:
        return f"🔔 {_headline(focus)}"
    return _headline(focus)


def stale_line(symbol: str) -> Optional[str]:
    """수신 실패로 저장본(data/cache)을 쓴 TF 한 줄 — 없으면 None (표시 전용, SPEC §12)."""
    stale = [f"{tf}({age})" for tf in TF_RADAR_PARAMS["intervals"] if (age := stale_age(symbol, tf))]
    return ("저장본 표시: " + ", ".join(stale)) if stale else None


def radar_table(rows: list[RadarRow]) -> pd.DataFrame:
    """표시용 표 — 우선순위 내림차순 그대로."""
    return pd.DataFrame([
        {
            "TF": r.interval,
            "상태": r.status,
            "쪽": r.side,
            "레벨": None if r.level is None else round(r.level, 2),
            "레벨 대비": "" if r.dist_pct is None else f"{r.dist_pct:+.2f}%",
            "비고": r.detail,
            "마지막 이벤트": r.last_event,
        }
        for r in rows
    ])


def render_tf_radar_section(symbol: str) -> dict:
    """알람 탭 상단 섹션 — 헤드라인 + 교차 TF 표.

    반환값은 화면에 그린 값(view) — 전체 복사용 텍스트(display.alarm_copy_text)가 재계산 없이 옮긴다:
    headline(마크다운 한 줄) · table(표시용 표) · stale(저장본 표시 줄, 없으면 None).
    """
    st.subheader(SECTION_TITLE)
    st.caption(FIXED_CAPTION)
    with st.spinner(f"{symbol} 전 TF 스캔 중..."):
        rows = build_tf_radar(load_radar_frames(symbol))
    headline = headline_line(pick_focus(rows))
    st.markdown(headline)
    table = radar_table(rows)
    st.dataframe(table, hide_index=True, width="stretch")
    # 수신 실패로 저장본(data/cache)을 쓴 TF — 표시 전용 한 줄 (SPEC §12)
    stale = stale_line(symbol)
    if stale:
        st.caption(stale)
    return {"headline": headline, "table": table, "stale": stale}
