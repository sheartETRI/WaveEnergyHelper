"""기준 TF 레이더 — 대파동 쌍바닥/쌍봉 후 60MA 전환 관찰이 열린 TF를 가리킨다 (표시 전용).

파동에너지 이론의 기준 TF: 대파동 쌍바닥(쌍봉)이 확정된 TF 가 그 국면의 기준 TF 이며,
그 TF 에서 60MA 의 상방(하방) 전환 여부를 관찰한다. 이 레이더는 그 관찰을 전 TF 로
펼쳐 "어느 TF 에서 60MA 전환을 지켜봐야 하는지"를 한 표로 요약한다.
docs/SPEC_SWEEP_RECLAIM.md §10 동결 스펙.

검출·창 규칙 무수정 — display.ma60_turn_tracker / ma60_down_tracker 의
track_candidates·summarize 를 소비만 한다(관찰 창 20봉 = probe 사전등록값, 상태
문자열도 그쪽 상수를 단일 출처로 승계). 마감 기준 설명은 SPEC §10.1.
판정·게이팅·푸시·기록 없음.

우선순위(동률은 입력 순서 = 상위 TF 먼저):
  2  대기 중    관찰 창이 열려 있음 — 지금 지켜봐야 하는 기준 TF
  1  전환 발생  최근 창(recent_bars)에서 전환이 이미 옴 — 기준 TF 활성 직후
  0  없음      소멸·해당 없음·후보 없음
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

import display.ma60_down_tracker as _down
import display.ma60_turn_tracker as _up

# 섹션 제목·고정 캡션 — 화면과 전체 복사용 텍스트(display.alarm_copy_text)가 같은 문자열을 쓴다
SECTION_TITLE = "기준 TF 레이더 — 쌍바닥/쌍봉 × 60MA 관찰"
FIXED_CAPTION = ("마감봉 기준: 대파동 쌍바닥·쌍봉 이후 60MA 전환을 관찰할 TF와 다음 확인 조건. "
                 "대기 우선·동률은 큰 TF 우선인 관찰 순서이며 성공 확률이 아닙니다. SPEC §10.1")


@dataclass(frozen=True)
class BasisRow:
    """TF 한 줄 — 상방(쌍바닥)·하방(쌍봉) 관찰 상태 요약."""

    interval: str
    score: int          # 2 대기 중 / 1 전환 발생 / 0 없음
    up_text: str        # 쌍바닥→60MA 상방 셀
    down_text: str      # 쌍봉→60MA 하방 셀
    detail: str         # 헤드라인용 — 우선 방향의 상태 설명


def _waiting_first(frame: pd.DataFrame) -> Optional[pd.Series]:
    if frame is None or frame.empty or "상태" not in frame.columns:
        return None
    waiting = frame[frame["상태"] == _up.STATUS_WAITING]
    return waiting.iloc[0] if len(waiting) else None


def _cell(summ: dict, frame: pd.DataFrame) -> tuple[str, int]:
    """한 방향의 (셀 텍스트, 점수)."""
    if summ.get("waiting"):
        first = _waiting_first(frame)
        extra = ""
        if first is not None:
            elapsed = str(first.get("경과/소요", "") or "")
            div = str(first.get("다이버전스", "") or "")
            bits = [b for b in (f"{elapsed}봉" if elapsed else "", f"다이버전스 {div}" if div else "") if b]
            extra = f" ({' · '.join(bits)})" if bits else ""
        return f"대기 {summ['waiting']}{extra}", 2
    if summ.get("turned"):
        return f"전환 발생 {summ['turned']}", 1
    parts = []
    if summ.get("expired"):
        parts.append(f"소멸 {summ['expired']}")
    already = summ.get("already_up", 0) or summ.get("already_down", 0)
    if already:
        parts.append(f"이미 {already}")
    return (" · ".join(parts) or "―"), 0


def build_basis_rows(
    frames: dict[str, Optional[pd.DataFrame]],
    track_up: Callable[[pd.DataFrame], pd.DataFrame] = _up.track_candidates,
    track_down: Callable[[pd.DataFrame], pd.DataFrame] = _down.track_candidates,
) -> list[BasisRow]:
    """{interval: 지표 계산 완료 df} -> 우선순위 내림차순 BasisRow 목록.

    frames 의 키 순서 = 동률 시 우선순위(상위 TF 먼저). df 가 None 이면 데이터 없음 행.
    track_* 주입은 테스트용 이음새 — 기본은 실제 트래커.
    """
    rows: list[BasisRow] = []
    for interval, df in frames.items():
        if df is None or df.empty:
            rows.append(BasisRow(interval, 0, "데이터 없음", "데이터 없음", ""))
            continue
        f_up, f_dn = track_up(df), track_down(df)
        up_text, up_score = _cell(_up.summarize(f_up), f_up)
        down_text, down_score = _cell(_down.summarize(f_dn), f_dn)
        if up_score == down_score and up_score > 0:
            detail = f"상·하방 동시 관찰 — 쌍바닥 {up_text} / 쌍봉 {down_text}"
        elif up_score > down_score:
            detail = f"쌍바닥→60MA 상방 {up_text}"
        elif down_score > 0:
            detail = f"쌍봉→60MA 하방 {down_text}"
        else:
            detail = ""
        rows.append(BasisRow(interval, max(up_score, down_score), up_text, down_text, detail))

    order = {interval: i for i, interval in enumerate(frames)}
    rows.sort(key=lambda r: (-r.score, order[r.interval]))
    return rows


def pick_basis_focus(rows: list[BasisRow]) -> Optional[BasisRow]:
    """"기준 TF 관찰 대상" — score > 0 인 최상위 행. 없으면 None."""
    for row in rows:
        if row.score > 0:
            return row
    return None


def headline_line(focus: Optional[BasisRow]) -> str:
    """화면 헤드라인 한 줄(마크다운) — 화면·전체 복사용 텍스트 공통."""
    if focus is None:
        return "기준 TF 관찰 대상: **없음** — 열려 있는 60MA 관찰 창 없음"
    return f"📌 기준 TF 관찰: **{focus.interval}** — {focus.detail}"


def basis_table(rows: list[BasisRow]) -> pd.DataFrame:
    return pd.DataFrame([
        {"TF": r.interval, "쌍바닥→상방": r.up_text, "쌍봉→하방": r.down_text}
        for r in rows
    ])


def render_basis_radar_section(symbol: str, on_open_chart: Optional[Callable[[str], None]] = None) -> dict:
    """알람 탭 섹션 — TF 레이더 아래. 적재는 TF 레이더와 같은 캐시를 공유한다.

    반환값은 화면에 그린 값(view) — 전체 복사용 텍스트(display.alarm_copy_text)가 재계산 없이 옮긴다:
    headline(마크다운 한 줄) · table(표시용 표) · guidance(같은 설명 카드 view).
    """
    import streamlit as st

    from display.tf_radar_panel import load_radar_frames
    from display.mtf_guidance_model import build_guidance
    from display.mtf_guidance import (
        candidate_frames, prepare_closed_frames, remember_radar_observation, render_guidance,
    )

    st.subheader(SECTION_TITLE)
    st.caption(FIXED_CAPTION)
    with st.spinner(f"{symbol} 전 TF 기준 관찰 스캔 중..."):
        asof = pd.Timestamp.now(tz="UTC")
        frames = prepare_closed_frames(load_radar_frames(symbol), asof)
        candidates = candidate_frames(frames)
        by_frame = {id(frame): candidates[tf] for tf, frame in frames.items() if frame is not None}
        rows = build_basis_rows(frames, track_up=lambda df: by_frame[id(df)][0],
                                track_down=lambda df: by_frame[id(df)][1])
    focus = pick_basis_focus(rows)
    headline = headline_line(focus)
    st.markdown(headline)
    st.caption("선정 이유는 레이더가 고른 TF를 설명합니다. 사이드바에서 보는 차트 TF를 바꿔도 설명 대상은 바뀌지 않습니다.")
    if focus is not None:
        guidance = render_guidance(build_guidance(focus.interval, frames, candidates, asof),
                                   symbol=symbol, scope="radar", on_open_chart=on_open_chart)
        remember_radar_observation(symbol, guidance, asof)
    else:
        unavailable = [tf for tf, frame in frames.items() if frame is None or frame.empty or len(frame) < 62]
        if len(unavailable) == len(frames):
            reason = "마감봉 자료가 없거나 부족하여 관찰 TF 판단을 보류합니다. 레이더를 다시 조회하세요."
        else:
            reason = "현재 레이더의 관찰 조건을 충족하는 TF가 없습니다. 임의의 TF를 관찰 대상으로 지정하지 않습니다."
            if unavailable:
                reason += " 자료 부족·미수신 TF: " + ", ".join(unavailable)
        st.info(reason)
        guidance = {"text": reason}
        remember_radar_observation(symbol, None, asof, empty_reason=reason)
    table = basis_table(rows)
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption("이 표와 설명은 마감된 봉을 사용합니다. 아래 기존 알람·전환 추적 표에는 진행 중인 봉이 포함될 수 있습니다.")
    return {"headline": headline, "table": table, "guidance": guidance}
