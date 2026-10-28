"""lightweight-charts 렌더 계층 — Plotly 와 병존 (2단계: 하위 pane · 마커 · 게이트 공급 · 세로 줌).

구조 결정(1단계 위임장 §0 고정, 2단계에도 유지):
- 서드파티 Streamlit 래퍼를 쓰지 않는다. ``st.components.v1.html`` 에 lightweight-charts
  standalone JS 를 직접 임베드한다.
- JS 는 CDN 이 아니라 저장소에 벤더링한다: ``charts/vendor/lightweight-charts.standalone.js``
  (버전은 VENDOR_VERSION 과 파일 헤더 주석에 명기). iframe 은 저장소 파일을 못 읽으므로
  HTML 문자열에 인라인한다.
- ``charts/plotly_builder.py`` 를 import 하지 않는다 — 색·표시 창·마커 스타일 토큰은 ``charts/theme.py``
  (단일 공급원, 값은 plotly_builder 에서 그대로 옮긴 것)에서 가져온다. 기본 경로(main)는 plotly 없이 기동한다.

2단계 범위(LW v5 panes — 스택 차트가 아니라 단일 차트의 pane):
- pane 0 가격(캔들 + 이평 + 거래량 하단 오버레이 + 구조 기준선 + 게이트 캡션)
- pane 스토캐 3중: 한 pane 에 3층 오프셋 배치(현행 승계), 층당 20/80 참조선, 층 분리선 2
- pane MACD: hist 히스토그램 + macd/signal 라인 + 0선
- pane RSI: 라인 + 30/50/70 참조선(현행 구성 그대로)
- pane 초기 비중은 Plotly '지표 중심' 세트 근사(PANE_STRETCH), 경계 드래그 리사이즈 활성.
- 꺼진 패널·컬럼 없는 패널은 pane 을 만들지 않는다(축소 폴백).

계약 승계(main 8cdd4e5 원칙): ``gate_context`` 필수 인자, ``struct_reference`` None → "기준선 없음".
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from charts.lw_config import *  # noqa: F401,F403 - 공개 상수 호환
from charts.lw_config import _LW_SHAPE, _LW_POSITION
from charts.lw_payload import *  # noqa: F401,F403 - 공개 직렬화 함수 호환
from charts.lw_payload import _unix_seconds, _display_seconds, _line_points, _normalize, _marker, _column_markers
from charts.lw_templates import TIME_FORMAT_JS, _JS_TEMPLATE

from analysis.alarm_signals import macd_event_positions
from charts.theme import (
    COLOR_BEAR,
    COLOR_BULL,
    MACD_EVENT_STYLE as _MACD_EVENT_STYLE,
    MACD_HIST_COLORS,
    RECENT_WINDOW,
    STOCH_GUIDES,
    TV_BACKGROUND,
    TV_GRID,
    TV_TEXT,
    ZONE_FILL_COLORS,
)
from display.tz_label import KST_LABEL, to_kst
from config.settings import (
    MA_COLORS,
    MA_LINE_WIDTHS,
    RSI_PARAMS,
    STOCH_BAND,
    STOCH_GAP,
    STOCH_LAYERS,
    STOCH_MAX_Y,
)


def pane_layout(payload: dict, *, show_stochastic: bool = True, show_macd: bool = True,
                show_rsi: bool = True) -> list[dict]:
    """pane 목록(순서 = 인덱스). 가격은 항상 0. 토글 꺼짐·데이터 없음이면 pane 을 만들지 않는다."""
    panes = [{"kind": "price", "stretch": PANE_STRETCH["price"]}]
    for kind, on in (("stoch", show_stochastic), ("macd", show_macd), ("rsi", show_rsi)):
        if on and payload.get(kind):
            panes.append({"kind": kind, "stretch": PANE_STRETCH[kind]})
    return panes


def struct_reference_lines(struct_reference: Optional[dict]) -> list[dict]:
    """구조 기준선 2개(저점·×0.995). 없음/불완전이면 빈 목록 → 호출부가 '기준선 없음' 폴백."""
    if not struct_reference:
        return []
    low = struct_reference.get("reference_low")
    line = struct_reference.get("line_price")
    if low is None or line is None or pd.isna(low) or pd.isna(line):
        return []
    # title 은 비운다 — 차트 안 라벨이 캔들을 가리던 문제. 의미(label)는 캡션 줄로 옮기고 축 뱃지는 색으로 구분.
    return [
        {"price": float(low), "color": STRUCT_LOW_COLOR, "style": LW_LINE_STYLE_DOTTED,
         "title": "", "label": STRUCT_LOW_LABEL},
        {"price": float(line), "color": STRUCT_LINE_COLOR, "style": LW_LINE_STYLE_DASHED,
         "title": "", "label": STRUCT_LINE_LABEL},
    ]


def format_price(value: float) -> str:
    """캡션용 가격: 1,000 이상은 정수 천 단위, 그 미만은 소수 2자리."""
    v = float(value)
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"


STRUCT_CAPTION_VERIFYING = "(검증 중)"   # 유지 — 없애지 말 것


def struct_caption_html(lines: list[dict]) -> str:
    """게이트 캡션 뒤에 붙는 기준선 1줄. 색 견본(선 스타일 문자)을 각 선 색으로 칠한다.

    예) ` · ─ 저점 76,046 · ┄ 기준선 75,666 (검증 중)`. 선이 없으면 ` · 기준선 없음`.
    """
    if not lines:
        return f" · {STRUCT_LINE_MISSING}"
    low, ref = lines[0], lines[1]
    return (
        f' · <span style="color:{low["color"]}">─</span> 저점 {format_price(low["price"])}'
        f' · <span style="color:{ref["color"]}">┄</span> 기준선 {format_price(ref["price"])} {STRUCT_CAPTION_VERIFYING}'
    )


def tracker_caption_html(lines: list[dict]) -> str:
    """60MA 전환 추적(미검증) 대기 중 후보의 저점·기준선 캡션 조각. 없으면 빈 문자열(캡션 불변).

    구조 기준선 캡션과 같은 형식(색 견본 + 가격). 후보가 여럿이면 최신 1건만 값으로 적고 건수를 병기한다.
    """
    if not lines:
        return ""
    low, ref = lines[0], lines[1]
    n = len(lines) // 2
    more = f" 외 {n - 1}건" if n > 1 else ""
    return (
        f' · 상방 추적{more} <span style="color:{low["color"]}">─</span> 저점 {format_price(low["price"])}'
        f' · <span style="color:{ref["color"]}">┄</span> 기준선 {format_price(ref["price"])} (미검증)'
    )


def down_tracker_caption_html(lines: list[dict]) -> str:
    """60MA 하방 전환 추적(미검증) 대기 중 후보의 패턴 고점 캡션 조각(1선/후보). 없으면 빈 문자열(캡션 불변)."""
    if not lines:
        return ""
    top = lines[0]
    more = f" 외 {len(lines) - 1}건" if len(lines) > 1 else ""
    return f' · 하방 추적{more} <span style="color:{top["color"]}">─</span> 고점 {format_price(top["price"])} (미검증)'


def chart_options() -> dict:
    """createChart 옵션 — 동작 요건을 여기 한곳에 둔다."""
    return {
        "autoSize": True,   # ResizeObserver 로 컨테이너 폭·높이 추종
        "layout": {
            "background": {"type": "solid", "color": TV_BACKGROUND}, "textColor": TV_TEXT,
            "attributionLogo": False,
            # pane 경계 드래그 리사이즈 (v5)
            "panes": {"enableResize": True, "separatorColor": PANE_SEPARATOR_COLOR,
                      "separatorHoverColor": PANE_SEPARATOR_HOVER_COLOR},
        },
        "grid": {"vertLines": {"color": TV_GRID}, "horzLines": {"color": TV_GRID}},
        "rightPriceScale": {"autoScale": True, "borderVisible": False,
                            "scaleMargins": {"top": 0.08, "bottom": PRICE_SCALE_BOTTOM_MARGIN}},
        "timeScale": {"timeVisible": True, "secondsVisible": False, "borderVisible": False,
                      "rightOffset": 3},
        # Normal(0) — 자유 크로스헤어(Magnet 아님). 어느 pane 위에서든 수직·수평선과 축 라벨을 그린다.
        "crosshair": {"mode": 0,
                      "vertLine": {"visible": True, "labelVisible": True},
                      "horzLine": {"visible": True, "labelVisible": True}},
        "handleScroll": {"mouseWheel": True, "pressedMouseMove": True,
                         "horzTouchDrag": True, "vertTouchDrag": False},
        "handleScale": {"mouseWheel": True, "pinch": True, "axisPressedMouseMove": True,
                        "axisDoubleClickReset": {"time": True, "price": True}},
    }


def candle_options() -> dict:
    """한국 관례 색 토큰 승계: 상승 적(COLOR_BULL) / 하락 청(COLOR_BEAR)."""
    return {
        "upColor": COLOR_BULL, "downColor": COLOR_BEAR,
        "borderUpColor": COLOR_BULL, "borderDownColor": COLOR_BEAR,
        "wickUpColor": COLOR_BULL, "wickDownColor": COLOR_BEAR,
    }


def load_vendor_js(path: str = VENDOR_PATH) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


DAILY_PLUS_SUFFIXES = ("d", "w", "M")   # 일봉 이상: 툴팁에 시:분을 생략 (봉 시각이 항상 00:00 이라 정보가 없다)


def tooltip_shows_clock(interval: str) -> bool:
    """툴팁(크로스헤어 시간 라벨)에 HH:MM 을 붙일지 — 분·시간봉만 True."""
    return not str(interval).endswith(DAILY_PLUS_SUFFIXES)


def build_lw_html(
    df: pd.DataFrame,
    symbol: str,
    display_interval: str,
    gate_context: str,
    *,
    chart_height: int,
    struct_reference: Optional[dict] = None,
    show_stochastic: bool = True,
    show_macd: bool = True,
    show_rsi: bool = True,
    vendor_js: Optional[str] = None,
    tracker_lines: Optional[list[dict]] = None,
    structure_markers: Optional[list[dict]] = None,
    down_tracker_lines: Optional[list[dict]] = None,
) -> str:
    """components.html 에 넘길 HTML 문자열.

    gate_context 는 필수(비어 있으면 ValueError) — 게이트 상태 없이 가격 화면이 단독 표시되지 않는다.
    tracker_lines 는 60MA 전환 추적(미검증) 대기 중 후보의 가격선(구조 기준선과 같은 사전 형식) — 없으면 불변.
    structure_markers 는 추세 구조 추적(미검증)의 스윙 마커 — [{"ts", "position", "color", "shape", "text"}], 없으면 불변.
    down_tracker_lines 는 60MA 하방 전환 추적(미검증) 대기 중 후보의 패턴 고점선(같은 사전 형식, 1선/후보) — 없으면 불변.
    """
    if not isinstance(gate_context, str) or not gate_context.strip():
        raise ValueError("gate_context 는 필수다 — 게이트 상태 라벨 없이 가격 화면을 그리지 않는다")
    payload = frame_to_lw_payload(df)
    panes = pane_layout(payload, show_stochastic=show_stochastic, show_macd=show_macd, show_rsi=show_rsi)
    lines = struct_reference_lines(struct_reference)
    extra = list(tracker_lines or [])
    down = list(down_tracker_lines or [])
    # 캡션 끝 시간대 표기 — 축·툴팁·오버레이 시각은 KST 표시(PAYLOAD 시프트). 알람 탭과 같은 라벨(display.tz_label).
    caption_html = (f"{_escape(str(symbol))} {_escape(str(display_interval))} · {_escape(gate_context)}"
                    f"{struct_caption_html(lines)}{tracker_caption_html(extra)}{down_tracker_caption_html(down)} "
                    f"{_escape(KST_LABEL)}")
    vendor = vendor_js if vendor_js is not None else load_vendor_js()
    height = int(chart_height)

    consts = "\n".join([
        f"var PAYLOAD = {json.dumps(payload, ensure_ascii=False)};",
        f"var PANES = {json.dumps(panes)};",
        f"var OPTS = {json.dumps(chart_options(), ensure_ascii=False)};",
        f"var CANDLE_OPTS = {json.dumps(candle_options())};",
        f"var MA_STYLES = {json.dumps(ma_styles())};",
        # label(의미)은 캡션 전용 — JS 로는 가격선 속성만 보낸다(title 은 빈 문자열).
        f"var STRUCT_LINES = {json.dumps([{k: v for k, v in l.items() if k != 'label'} for l in lines + extra + down], ensure_ascii=False)};",
        f"var VOLUME_TOP = {VOLUME_SCALE_TOP_MARGIN};",
        f"var WINDOW = {RECENT_WINDOW};",
        f"var STOCH_GUIDE_COLOR = {json.dumps(STOCH_GUIDE_COLOR)};",
        f"var STOCH_SEP_COLOR = {json.dumps(STOCH_SEPARATOR_COLOR)};",
        f"var MACD_COLORS = {json.dumps({'macd': MACD_LINE_COLOR, 'signal': MACD_SIGNAL_COLOR})};",
        f"var RSI_COLOR = {json.dumps(RSI_LINE_COLOR)};",
        f"var VZOOM_IN = {VZOOM_IN_FACTOR}; var VZOOM_OUT = {VZOOM_OUT_FACTOR};",
        f"var SOLO_ALL = {json.dumps(SOLO_ALL)}; var SOLO_COLLAPSED_PX = {SOLO_COLLAPSED_PX};",
        f"var PANE_LABELS = {json.dumps(PANE_LABELS, ensure_ascii=False)};",
        f"var ZONE_FILL = {json.dumps(ZONE_FILL_COLORS)};",   # charts/theme.py 토큰 — 하드코딩 금지
        f"var OHLC_OFFSET = {OHLC_OVERLAY_OFFSET_PX};",
        f"var STRUCTURE_MARKERS = {json.dumps(structure_markers_payload(structure_markers), ensure_ascii=False)};",
        f"var INTERVAL = {json.dumps(str(display_interval))};",
        f"var TOOLTIP_CLOCK = {json.dumps(tooltip_shows_clock(display_interval))};",
    ])
    return (
        "<!-- lw_builder stage2 -->\n"
        # iframe 문서의 기본 body 마진(8px)을 없앤다 — 없으면 차트가 8px 밀려 시간축이 잘리고 pane 경계 좌표가 어긋난다.
        "<style>html,body{margin:0;padding:0;overflow:hidden;}</style>\n"
        f'<div id="lw-wrap" style="position:relative;width:100%;height:{height}px;'
        f'background:{TV_BACKGROUND};font-family:-apple-system,Segoe UI,Roboto,sans-serif;">\n'
        f'  <div id="lw-caption" style="position:absolute;top:6px;left:8px;z-index:{LW_OVERLAY_Z};'
        f'font-size:12px;color:{TV_TEXT};background:rgba(255,255,255,0.85);padding:2px 6px;'
        f'border-radius:3px;pointer-events:none;">{caption_html}</div>\n'
        # 크로스헤어 정보(커서 봉의 시/고/저/종·변화율 + 하위 pane 값). 커서 밖이면 마지막 봉. JS 가 채운다.
        f'  <div id="lw-ohlc" style="position:absolute;top:{6 + OHLC_OVERLAY_OFFSET_PX}px;left:8px;z-index:{LW_OVERLAY_Z};'
        f'font-size:12px;color:{TV_TEXT};background:rgba(255,255,255,0.85);padding:2px 6px;'
        f'border-radius:3px;pointer-events:none;white-space:nowrap;"></div>\n'
        f"{solo_buttons_html(panes)}"
        '  <div id="lw-chart" style="position:absolute;inset:0;"></div>\n'
        # 접힌 pane 위에 얹는 이름 띠(단독 모드에서만 표시, 클릭 → 그 pane 단독). 차트 위 z-index.
        '  <div id="lw-strips"></div>\n'
        "</div>\n"
        f"<script>{vendor}</script>\n"
        f"<script>\n{consts}\n{TIME_FORMAT_JS}\n{_JS_TEMPLATE}</script>\n"
    )


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def solo_buttons_html(panes: list[dict]) -> str:
    """우상단 반투명 버튼 줄 [전체 | 가격 | 스토캐 | ...] — 현재 있는 pane 만. 가격축(≈70px)을 피해 오른쪽 여백을 둔다."""
    buttons = [f'<button type="button" data-kind="{SOLO_ALL}" class="on">전체</button>']
    buttons += [f'<button type="button" data-kind="{p["kind"]}">{PANE_LABELS[p["kind"]]}</button>' for p in panes]
    style = ("#lw-solo button{background:rgba(255,255,255,0.82);border:1px solid #cfd3dc;border-radius:3px;"
             f"padding:1px 7px;cursor:pointer;color:{TV_TEXT};font-size:11px;line-height:16px}}"
             f"#lw-solo button.on{{background:{TV_TEXT};color:#fff;border-color:{TV_TEXT}}}"
             f".lw-strip{{position:absolute;z-index:{LW_OVERLAY_Z};box-sizing:border-box;padding:0 8px;overflow:hidden;"
             f"background:{SOLO_STRIP_BG};color:{TV_TEXT};font-size:{SOLO_STRIP_FONT_PX}px;cursor:pointer;"
             "user-select:none;white-space:nowrap}"
             ".lw-strip:hover{background:rgba(226,231,242,0.98)}")
    return (
        f"  <style>{style}</style>\n"
        f'  <div id="lw-solo" style="position:absolute;top:6px;right:80px;z-index:{LW_OVERLAY_Z + 1};display:flex;gap:3px;">'
        + "".join(buttons) + "</div>\n"
    )


LW_CONTROLS_CAPTION = (
    "조작(LW): 휠 = 시간축 확대·축소  ·  드래그 = 이동  ·  가격축 위 휠 = 세로 확대·축소  ·  "
    "가격축 드래그 = 세로 스케일  ·  가격축 더블클릭 = 자동 맞춤 복귀  ·  패널 경계 드래그 = 패널 높이 조절"
)


VZOOM_IN_FACTOR = 0.8


VZOOM_OUT_FACTOR = 1.25


def render_lw_chart(
    df: pd.DataFrame,
    symbol: str,
    display_interval: str,
    gate_context: str,
    *,
    chart_height: int,
    struct_reference: Optional[dict] = None,
    show_stochastic: bool = True,
    show_macd: bool = True,
    show_rsi: bool = True,
    tracker_lines: Optional[list[dict]] = None,
    structure_markers: Optional[list[dict]] = None,
    down_tracker_lines: Optional[list[dict]] = None,
) -> None:
    """LW 엔진 렌더. 높이는 사이드바 셀렉트 값을 그대로 iframe 높이로 쓴다."""
    if df is None or df.empty:
        return
    html = build_lw_html(
        df, symbol, display_interval, gate_context,
        chart_height=chart_height, struct_reference=struct_reference,
        show_stochastic=show_stochastic, show_macd=show_macd, show_rsi=show_rsi,
        tracker_lines=tracker_lines, structure_markers=structure_markers, down_tracker_lines=down_tracker_lines,
    )
    components.html(html, height=int(chart_height), scrolling=False)
    st.caption(LW_CONTROLS_CAPTION)
    if structure_markers:
        st.caption(STRUCTURE_LEGEND_CAPTION)   # 구조 마커 범례 — 마커가 있을 때만
