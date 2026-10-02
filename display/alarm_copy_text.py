"""알람 탭 전체 복사용 텍스트 — 탭에 그린 값을 마크다운 텍스트 한 덩어리로 (표시 계층 전용, signal-alarm).

알람 탭 맨 아래 접힌 상자(expander) 안 st.code 블록 하나에 탭 내용을 옮긴다 — st.code 의 복사 버튼으로 한 번에 복사.
**재계산하지 않는다**: 각 섹션 render_* 가 화면에 그린 뒤 돌려준 값(알람 패널 view, 60MA 상방·하방 추적 후보 표, 기울기
(tf, snapshot) 목록, 추세 구조 분석 결과)만 받아, 화면과 같은 표시 함수(metric_items · display_frame · summary_line ·
summary_frame · chain_frame 등)로 문자열을 만든다. 검출·판정·fetch 없음.

표는 마크다운 표(파이프 구분)로 적고, 고정폭 글꼴에서 열이 맞도록 동아시아 전각 문자(한글·이모지)는 2칸으로 세어 채운다.
섹션 순서는 화면 순서: 심볼·TF·마지막 봉 → 마지막 봉 알람 → 신호 이력 → 60MA 상방 전환 추적(기울기 표 포함) →
60MA 하방 전환 추적 → 추세 구조. 값이 아닌 고정 정의 각주 캡션은 옮기지 않는다. 탭 상단 TF 레이더 2종은 대상 밖.
"""
from __future__ import annotations

import unicodedata
from typing import List, Optional, Sequence, Tuple

import pandas as pd

import display.alarm_panel as AP
import display.ma60_down_tracker as D
import display.ma60_slope as SL
import display.ma60_turn_tracker as T
import display.trend_structure as TS

EXPANDER_LABEL = "전체 복사용 텍스트"
EXPANDER_CAPTION = "알람 탭에 표시된 값을 마크다운 텍스트로 모았습니다 — 블록 오른쪽 위 복사 버튼으로 한 번에 복사합니다."
FILTER_NOTE = "표시 필터 적용 — 전체 {total}건 중 {shown}건"
NL = "\n"


# ------------------------------------------------------------------ 텍스트 표
def display_width(text: str) -> int:
    """고정폭 글꼴 기준 표시 폭 — 동아시아 전각(W·F: 한글·이모지 등)은 2칸, 나머지는 1칸."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _cell(v) -> str:
    """셀 문자열 — 빈 값(None·NaN·NaT)은 공백, 줄바꿈은 공백, 파이프는 마크다운 이스케이프."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    return str(v).replace(NL, " ").replace("|", "\\|")


def text_table(frame: pd.DataFrame, headers: Optional[dict] = None) -> str:
    """문자열 표 → 마크다운 표(열 폭을 표시 폭으로 맞춤). headers 는 컬럼 키 → 화면 헤더 라벨(없으면 키 그대로)."""
    headers = headers or {}
    head = [_cell(headers.get(c, c)) for c in frame.columns]
    body = [[_cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]
    widths = [max([3, display_width(h)] + [display_width(r[i]) for r in body]) for i, h in enumerate(head)]

    def line(cells: Sequence[str]) -> str:
        return "| " + " | ".join(c + " " * (w - display_width(c)) for c, w in zip(cells, widths)) + " |"

    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return NL.join([line(head), rule] + [line(r) for r in body])


def metric_bullets(items: Sequence[Tuple[str, str, Optional[str]]]) -> str:
    """메트릭 (라벨, 값, 도움말) 목록 → '- 라벨: 값' 줄들. 도움말(마우스오버 설명)은 옮기지 않는다."""
    return NL.join(f"- {label}: {value}" for label, value, _help in items)


# ------------------------------------------------------------------ 섹션 (화면 순서)
def alarm_chunks(view: Optional[dict], symbol: str, interval: str) -> List[str]:
    """심볼·TF·마지막 봉 + 마지막 봉 알람 + 신호 이력 — render_alarm_panel 이 돌려준 view 그대로."""
    chunks = [f"# {AP.build_header(symbol, interval)}"]
    if not view or not view.get("metrics"):
        return chunks + ["데이터 없음"]
    chunks.append(metric_bullets(view["metrics"]))
    chunks += list(view["captions"])
    chunks.append(f"## {AP.CURRENT_TITLE}")
    chunks.append(NL.join(f"- {line}" for line in view["current"]) if view["current"] else AP.NO_CURRENT_CAPTION)
    chunks.append(f"## {AP.history_title(view['history_bars'])}")
    shown, total = view.get("history"), int(view.get("history_total") or 0)
    if not total:
        chunks.append(AP.NO_HISTORY_CAPTION)
    elif shown is None or shown.empty:
        chunks.append(AP.NO_FILTER_MATCH_CAPTION)
    else:
        if len(shown) < total:
            chunks.append(FILTER_NOTE.format(total=total, shown=len(shown)))
        chunks.append(text_table(AP.history_text_frame(shown)))
        chunks.append(AP.history_counts(shown))
    return chunks


def slope_chunks(rows: Optional[Sequence[Tuple[str, Optional[dict]]]], symbol: str, interval: str) -> List[str]:
    """60MA 기울기 표 — render_slope_block 이 돌려준 (tf, snapshot) 목록을 화면과 같은 summary_frame 으로."""
    if not rows:
        return []
    return [f"### {SL.BLOCK_TITLE} · {symbol}", text_table(SL.summary_frame(rows, interval))]


def up_tracker_chunks(frame: Optional[pd.DataFrame], slope_rows, symbol: str, interval: str) -> List[str]:
    """60MA 상방 전환 추적 — 기울기 표, 메트릭 5칸, 후보 표, 집계 줄 2개."""
    chunks = [f"## {T.SECTION_TITLE} · {symbol} {interval}", T.FIXED_CAPTION]
    chunks += slope_chunks(slope_rows, symbol, interval)
    chunks.append(metric_bullets(T.metric_items(T.summarize(frame))))
    if frame is None or frame.empty:
        chunks.append(T.EMPTY_CAPTION)
    else:
        chunks += [T.bar_unit_caption(interval), text_table(T.display_frame(frame, symbol, interval), T.DISPLAY_HEADERS)]
    return chunks + [T.summary_line(frame), T.divergence_summary_line(frame)]


def down_tracker_chunks(frame: Optional[pd.DataFrame], symbol: str, interval: str) -> List[str]:
    """60MA 하방 전환 추적 — 메트릭 5칸, 후보 표, 집계 줄 2개."""
    chunks = [f"## {D.SECTION_TITLE} · {symbol} {interval}", D.FIXED_CAPTION,
              metric_bullets(D.metric_items(D.summarize(frame)))]
    if frame is None or frame.empty:
        chunks.append(D.EMPTY_CAPTION)
    else:
        chunks += [T.bar_unit_caption(interval), text_table(D.display_frame(frame, symbol, interval), D.DISPLAY_HEADERS)]
    return chunks + [D.summary_line(frame), D.divergence_summary_line(frame)]


def structure_chunks(result: Optional[dict], symbol: str, interval: str) -> List[str]:
    """추세 구조 추적 — 메트릭 4칸, 기준점·전환 캡션, 스윙 연쇄 표."""
    chunks = [f"## {TS.SECTION_TITLE} · {symbol} {interval}", TS.FIXED_CAPTION]
    if result is None:
        return chunks + [TS.NO_BASE_CAPTION]
    chunks.append(metric_bullets(TS.metric_items(result)))
    chunks += TS.detail_captions(result)
    frame = TS.chain_frame(result)
    chunks.append(TS.NO_SWING_CAPTION if frame.empty else text_table(frame))
    return chunks


def build_copy_text(symbol: str, interval: str, alarm_view: Optional[dict], tracker_frame: Optional[pd.DataFrame],
                    slope_rows, down_frame: Optional[pd.DataFrame], structure_result: Optional[dict]) -> str:
    """탭 전체 텍스트(마크다운) — 인자는 모두 각 render_* 의 반환값(재계산 없음). 덩어리 사이는 빈 줄 하나."""
    chunks = (alarm_chunks(alarm_view, symbol, interval)
              + up_tracker_chunks(tracker_frame, slope_rows, symbol, interval)
              + down_tracker_chunks(down_frame, symbol, interval)
              + structure_chunks(structure_result, symbol, interval))
    return (NL + NL).join(c for c in chunks if c) + NL


# ------------------------------------------------------------------ streamlit
def render_copy_expander(text: str) -> None:
    """알람 탭 맨 아래 접힌 상자 — 펼치면 st.code 블록 하나(복사 버튼 내장)."""
    import streamlit as st

    with st.expander(EXPANDER_LABEL, expanded=False):
        st.caption(EXPANDER_CAPTION)
        st.code(text, language="markdown")
