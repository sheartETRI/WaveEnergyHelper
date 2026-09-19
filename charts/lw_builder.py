"""lightweight-charts 렌더 계층 — Plotly 와 병존 (2단계: 하위 pane · 마커 · 게이트 공급 · 세로 줌).

구조 결정(1단계 위임장 §0 고정, 2단계에도 유지):
- 서드파티 Streamlit 래퍼를 쓰지 않는다. ``st.components.v1.html`` 에 lightweight-charts
  standalone JS 를 직접 임베드한다.
- JS 는 CDN 이 아니라 저장소에 벤더링한다: ``charts/vendor/lightweight-charts.standalone.js``
  (버전은 VENDOR_VERSION 과 파일 헤더 주석에 명기). iframe 은 저장소 파일을 못 읽으므로
  HTML 문자열에 인라인한다.
- ``charts/plotly_builder.py`` 는 수정하지 않는다 — 색·굵기·표시 창·마커 스타일 토큰만 import 해 승계한다.

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

from analysis.alarm_signals import macd_event_positions
from charts.plotly_builder import (
    _MACD_EVENT_STYLE,
    COLOR_BEAR,
    COLOR_BULL,
    RECENT_WINDOW,
    STOCH_GUIDES,
    TV_BACKGROUND,
    TV_GRID,
    TV_TEXT,
)
from charts.theme import MACD_HIST_COLORS, ZONE_FILL_COLORS
from config.settings import (
    MA_COLORS,
    MA_LINE_WIDTHS,
    RSI_PARAMS,
    STOCH_BAND,
    STOCH_GAP,
    STOCH_LAYERS,
    STOCH_MAX_Y,
)

VENDOR_VERSION = "5.2.1"
VENDOR_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vendor", "lightweight-charts.standalone.js",
)
VENDOR_HEADER_MARK = f"Lightweight Charts™ v{VENDOR_VERSION}"   # 원본 라이선스 헤더의 버전 문구

# 라벨 — main 8cdd4e5 문구 승계 (상태 기술형, 변경 금지)
STRUCT_LOW_LABEL = "직전 확정 패턴 저점"
STRUCT_LINE_LABEL = "패턴 저점 기준선 (검증 중)"
STRUCT_LINE_MISSING = "기준선 없음"
STRUCT_LOW_COLOR = "#8D6E63"
STRUCT_LINE_COLOR = "#EF5350"

DASHED_MA_PERIODS = {40, 80}          # plotly_builder 와 동일: 40·80 은 점선 보조선
VOLUME_SCALE_TOP_MARGIN = 0.80        # 거래량은 가격 pane 하단 20% 오버레이
PRICE_SCALE_BOTTOM_MARGIN = 0.22      # 캔들이 거래량 띠와 겹치지 않게
LW_LINE_STYLE_SOLID = 0
LW_LINE_STYLE_DOTTED = 1
LW_LINE_STYLE_DASHED = 2

# --- pane 구성: Plotly '지표 중심' 비중(가격 0.34 + 거래량 0.05 / 스토캐 0.26 / MACD 0.19 / RSI 0.16) 근사 ---
PANE_KINDS = ("price", "stoch", "macd", "rsi")
PANE_STRETCH = {"price": 39, "stoch": 26, "macd": 19, "rsi": 16}
PANE_LABELS = {"price": "가격", "stoch": "스토캐", "macd": "MACD", "rsi": "RSI"}
# pane 단독 확대 모드: iframe 내부 버튼 [전체 | 가격 | 스토캐 | MACD | RSI]. JS 만으로 stretch factor 를 재배분한다
# (Streamlit rerun 없음 → 줌·팬·세로 줌 상태 유지). 나머지 pane 은 0 으로 숨기지 않고 SOLO_COLLAPSED_PX 띠로 접는다.
# - 접힌 띠 높이 실측(v5.2.1): 레이아웃이 pane 높이를 max(·, 2) 로 바닥 처리하므로 stretch 로는 2px 까지 내려가고
#   0 은 불가(setHeight API 는 30 클램프, 분리선 드래그도 30 클램프). 시리즈·마커·고정 스케일·가격선은 모델 객체라
#   높이와 무관하게 유지된다(2px 까지 확인). 14px 는 띠 위에 pane 이름(10px 글자)을 얹을 수 있는 최소값.
# - 단독 모드에서는 iframe(window.frameElement — Streamlit 의 srcdoc iframe 은 allow-same-origin)과 #lw-wrap 높이를
#   접힌 띠 합계만큼 늘려, 선택 pane 이 전체 모드의 pane 영역 전체(= 그 pane 이 가질 수 있는 최대)를 차지하게 한다.
SOLO_ALL = "all"
SOLO_COLLAPSED_PX = 14
SOLO_STRIP_FONT_PX = 10
SOLO_STRIP_BG = "#F0F3FA"   # 불투명 — 접힌 띠에는 pane 이름만 보인다
# 오버레이(캡션·버튼·접힌 띠) z-index — LW v5 pane 분리선 히트 영역(z-index 50, 세로 9px)보다 위. 띠가 14px 이면
# 분리선 히트 영역이 버튼 줄(top 6px)과 겹쳐 클릭을 가로채므로 반드시 50 초과.
LW_OVERLAY_Z = 60
# 크로스헤어 정보 오버레이(#lw-ohlc): 게이트·기준선 캡션 줄(top 6px, 높이 ≈20px) 바로 아래. 겹치지 않게 고정 오프셋.
OHLC_OVERLAY_OFFSET_PX = 24   # 실측: 캡션 높이 22.5px(top 6 → bottom 28.5) → 30px 에서 시작
PANE_SEPARATOR_COLOR = "#E0E3EB"
PANE_SEPARATOR_HOVER_COLOR = "rgba(178, 181, 189, 0.35)"

# --- 하위 패널 토큰 (plotly_builder 의 값 그대로) ---
STOCH_GUIDE_COLOR = "rgba(120,120,120,0.9)"
STOCH_SEPARATOR_COLOR = "rgba(80,80,80,0.7)"
MACD_LINE_COLOR = "#FF3344"
MACD_SIGNAL_COLOR = "#2F6BFF"
# MACD 히스토그램 4색은 charts/theme.py 토큰 — 여기서는 참조만 (하드코딩 금지)
RSI_LINE_COLOR = "#000000"
RSI_GUIDE_STYLE = (   # (값 키, 색, 선 스타일) — plotly add_rsi_panel 의 ob/os/mid 구성
    ("overbought", "rgba(255,165,0,0.5)", LW_LINE_STYLE_DASHED),
    ("oversold", "rgba(0,255,255,0.5)", LW_LINE_STYLE_DASHED),
    ("midline", "rgba(0,128,0,0.8)", LW_LINE_STYLE_DOTTED),
)

# --- 알람 마커 (plotly add_stochastic_*_markers · _MACD_EVENT_STYLE 승계) ---
# 텍스트 라벨 유지, 방향 색 승계. Plotly 심볼 → LW shape: circle→circle, diamond→square.
# 텍스트 위치 top center → aboveBar, bottom center → belowBar. 위치(봉)는 지표 컬럼 non-null 봉 /
# macd_event_positions 의 확정 봉 — plotly 와 동일 원칙, 억제 로직 없음.
STOCH_MARKER_STYLE = {   # kind → (text, shape, color, position)
    "db": ("DB", "circle", "#0B8F45", "aboveBar"),
    "dt": ("DT", "circle", "#C62828", "belowBar"),
    "tb": ("TB", "square", "#1565C0", "aboveBar"),
    "tt": ("TT", "square", "#AD1457", "belowBar"),
}
_LW_SHAPE = {"circle": "circle", "diamond": "square", "square": "square"}
_LW_POSITION = {"top center": "aboveBar", "bottom center": "belowBar"}


# ------------------------------------------------------------------ 토큰
def lw_line_width(width: float) -> int:
    """Plotly 선 굵기(실수 px) → LW lineWidth(정수 1~4). 1.0/1.2/1.4 → 1, 1.6/1.8 → 2."""
    return max(1, min(4, int(round(float(width)))))


def ma_styles() -> dict:
    """이평 토큰 승계: config.MA_COLORS · MA_LINE_WIDTHS, 40·80 점선."""
    return {
        str(period): {
            "color": color,
            "width": lw_line_width(MA_LINE_WIDTHS.get(period, 1.0)),
            "style": LW_LINE_STYLE_DASHED if period in DASHED_MA_PERIODS else LW_LINE_STYLE_SOLID,
        }
        for period, color in MA_COLORS.items()
    }


def macd_hist_color(cur, prev) -> str:
    """MACD 히스토그램 4색 (charts/theme.MACD_HIST_COLORS): 부호가 1차, 직전 봉 대비 증감이 2차.

    hist ≥ 0 & hist > prev → 진한 적 / hist ≥ 0 & hist ≤ prev → 옅은 적 /
    hist < 0 & hist < prev → 진한 청 / hist < 0 & hist ≥ prev → 옅은 청. 첫 봉(prev 결측)은 부호의 진한 색.
    표시 계층 내부 계산 — df 에 컬럼을 쓰지 않는다. (Plotly 경로의 규칙과는 다르다: 그쪽은 이번 범위 밖.)
    """
    cur = float(cur)
    if cur >= 0:
        if pd.isna(prev) or cur > float(prev):
            return MACD_HIST_COLORS["pos_rising"]
        return MACD_HIST_COLORS["pos_falling"]
    if pd.isna(prev) or cur < float(prev):
        return MACD_HIST_COLORS["neg_falling"]
    return MACD_HIST_COLORS["neg_rising"]


# ------------------------------------------------------------------ 직렬화
def _unix_seconds(ts: pd.Timestamp) -> int:
    """naive 인덱스는 UTC 로 간주한다 — LW 도 UTC 로 표시하므로 Plotly 가 보여주던 벽시계와 같다."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return int(ts.timestamp())


def _line_points(times: list[int], series: pd.Series) -> list[dict]:
    return [{"time": t, "value": float(v)} for t, v in zip(times, series) if pd.notna(v)]


def _normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
    frame = df.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame, [_unix_seconds(ts) for ts in frame.index]


def stoch_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    """스토캐 3중 — 한 pane 에 오프셋 배치(shifted 컬럼 그대로), 층당 20/80 참조선, 분리선 2."""
    layers = []
    for layer in STOCH_LAYERS:
        label, offset = layer["label"], float(layer["offset"])
        k_col, d_col = f"stoch_k_shifted_{label}", f"stoch_d_shifted_{label}"
        if k_col not in frame.columns or d_col not in frame.columns:
            continue
        k, d = _line_points(times, frame[k_col]), _line_points(times, frame[d_col])
        if not k:
            continue
        layers.append({
            "label": label, "offset": offset, "k": k, "d": d,
            "k_color": layer["k_color"], "d_color": layer["d_color"],
            "guides": [float(g + offset) for g in STOCH_GUIDES],
        })
    if not layers:
        return None
    return {
        "layers": layers,
        "separators": [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5],
        "max_y": float(STOCH_MAX_Y),
    }


def macd_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    if not {"macd", "macd_signal", "macd_hist"}.issubset(frame.columns):
        return None
    prev = frame["macd_hist_prev"] if "macd_hist_prev" in frame.columns else frame["macd_hist"].shift(1)
    hist = [
        {"time": t, "value": float(c), "color": macd_hist_color(float(c), p)}
        for t, c, p in zip(times, frame["macd_hist"], prev) if pd.notna(c)
    ]
    macd, signal = _line_points(times, frame["macd"]), _line_points(times, frame["macd_signal"])
    if not macd:
        return None
    return {"hist": hist, "macd": macd, "signal": signal}


def rsi_payload(frame: pd.DataFrame, times: list[int]) -> Optional[dict]:
    if "rsi" not in frame.columns:
        return None
    line = _line_points(times, frame["rsi"])
    if not line:
        return None
    guides = [{"value": float(RSI_PARAMS[key]), "color": color, "style": style}
              for key, color, style in RSI_GUIDE_STYLE]
    return {"line": line, "guides": guides}


def _marker(t: int, style: tuple) -> dict:
    text, shape, color, position = style
    return {"time": t, "position": position, "shape": shape, "color": color, "text": text}


def _column_markers(frame: pd.DataFrame, times: list[int], col: str, style: tuple) -> list[dict]:
    if col not in frame.columns:
        return []
    return [_marker(t, style) for t, v in zip(times, frame[col]) if pd.notna(v)]


def markers_payload(frame: pd.DataFrame, times: list[int]) -> dict:
    """알람 마커 — 시리즈별(스토캐 층별 K · RSI · MACD) 시간 오름차순 목록.

    - 스토캐 DB/DT/TB/TT: ``stoch_{kind}_{label}`` non-null 봉 (plotly 와 동일 컬럼).
    - RSI DB/DT: ``rsi_db`` / ``rsi_dt`` (plotly 는 스토캐 DB/DT 마커 함수를 재사용 → 같은 스타일).
    - MACD GC/DC/0↑/0↓: ``analysis.alarm_signals.macd_event_positions`` 의 확정 봉 (알람과 동일).
    """
    time_of = dict(zip(pd.to_datetime(frame.index), times))
    stoch: dict = {}
    for layer in STOCH_LAYERS:
        label = layer["label"]
        out: list[dict] = []
        for kind, style in STOCH_MARKER_STYLE.items():
            out += _column_markers(frame, times, f"stoch_{kind}_{label}", style)
        out.sort(key=lambda m: m["time"])
        if out:
            stoch[label] = out
    rsi = (_column_markers(frame, times, "rsi_db", STOCH_MARKER_STYLE["db"])
           + _column_markers(frame, times, "rsi_dt", STOCH_MARKER_STYLE["dt"]))
    rsi.sort(key=lambda m: m["time"])
    macd: list[dict] = []
    if "macd" in frame.columns:
        for kind, positions in macd_event_positions(frame).items():
            text, symbol, color, text_position = _MACD_EVENT_STYLE[kind]
            style = (text, _LW_SHAPE[symbol], color, _LW_POSITION[text_position])
            macd += [_marker(time_of[ts], style) for ts in positions if ts in time_of]
        macd.sort(key=lambda m: m["time"])
    return {"stoch": stoch, "rsi": rsi, "macd": macd}


def frame_to_lw_payload(df: pd.DataFrame) -> dict:
    """데이터프레임 → LW setData 용 JSON 직렬화 가능 dict.

    - 시간 오름차순 정렬, 중복 시각은 마지막 행만(LW 는 단조 증가 시각을 요구).
    - NaN 은 시리즈별로 그 점만 뺀다(캔들은 OHLC 중 하나라도 NaN 이면 제외).
    - 거래량 색은 종가≥시가 적 / 그 외 청 (plotly_builder.add_volume_panel 과 동일 규칙).
    - 하위 패널(stoch/macd/rsi)은 컬럼이 없으면 None — pane 을 만들지 않는다.
    """
    empty = {"candles": [], "volume": [], "mas": {}, "stoch": None, "macd": None, "rsi": None,
             "markers": {"stoch": {}, "rsi": [], "macd": []}, "zones": zone_thresholds()}
    required = {"open", "high", "low", "close"}
    if df is None or df.empty or not required.issubset(df.columns):
        return empty

    frame, times = _normalize(df)
    candles, volume = [], []
    ohlc_ok = frame[["open", "high", "low", "close"]].notna().all(axis=1).to_numpy()
    has_volume = "volume" in frame.columns
    for i, (t, row) in enumerate(zip(times, frame.itertuples(index=False))):
        if not ohlc_ok[i]:
            continue
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        if has_volume and pd.notna(row.volume):
            volume.append({"time": t, "value": float(row.volume),
                           "color": COLOR_BULL if c >= o else COLOR_BEAR})

    mas: dict = {}
    for period in MA_COLORS:
        col = f"MA{period}"
        if col in frame.columns:
            pts = _line_points(times, frame[col])
            if pts:
                mas[str(period)] = pts
    return {
        "candles": candles, "volume": volume, "mas": mas,
        "stoch": stoch_payload(frame, times),
        "macd": macd_payload(frame, times),
        "rsi": rsi_payload(frame, times),
        "markers": markers_payload(frame, times),
        # 영역 음영 임계값 — plotly 와 동일: 스토캐 20/80(층별 오프셋은 layers[].guides), RSI oversold/overbought
        "zones": zone_thresholds(),
    }


def zone_thresholds() -> dict:
    """과매수·과매도 임계값(표시 계층). 스토캐는 STOCH_GUIDES(20/80), RSI 는 RSI_PARAMS 의 oversold/overbought."""
    return {
        "stoch": {"low": float(STOCH_GUIDES[0]), "high": float(STOCH_GUIDES[1])},
        "rsi": {"low": float(RSI_PARAMS["oversold"]), "high": float(RSI_PARAMS["overbought"])},
    }


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
        f' · 추적{more} <span style="color:{low["color"]}">─</span> 저점 {format_price(low["price"])}'
        f' · <span style="color:{ref["color"]}">┄</span> 기준선 {format_price(ref["price"])} (미검증)'
    )


# ------------------------------------------------------------------ HTML
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


# ------------------------------------------------------------------ 시간 표기 (한국식 순서, UTC)
# 프레임 인덱스는 naive UTC(_unix_seconds) 이고 LW 도 UTC 로 그린다 — 알람 탭 신호 시각과 같은 벽시계.
# 시간대 변환은 하지 않는다(정의·알람 시각과 어긋나면 안 됨).
DAILY_PLUS_SUFFIXES = ("d", "w", "M")   # 일봉 이상: 툴팁에 시:분을 생략 (봉 시각이 항상 00:00 이라 정보가 없다)


def tooltip_shows_clock(interval: str) -> bool:
    """툴팁(크로스헤어 시간 라벨)에 HH:MM 을 붙일지 — 분·시간봉만 True."""
    return not str(interval).endswith(DAILY_PLUS_SUFFIXES)


# tickMarkType: 0 Year · 1 Month · 2 DayOfMonth · 3 Time · 4 TimeWithSeconds (LW 기본 밀도 단계 그대로, 순서만 한국식)
TIME_FORMAT_JS = """
function lwPad(n) { return (n < 10 ? '0' : '') + n; }
function lwParts(t) {
  var sec = (typeof t === 'number') ? t : (t && t.timestamp !== undefined ? t.timestamp
            : Date.UTC(t.year, t.month - 1, t.day) / 1000);
  var d = new Date(sec * 1000);
  return { y: d.getUTCFullYear(), m: lwPad(d.getUTCMonth() + 1), d: lwPad(d.getUTCDate()),
           h: lwPad(d.getUTCHours()), mi: lwPad(d.getUTCMinutes()), s: lwPad(d.getUTCSeconds()) };
}
function lwYmd(p) { return p.y + '-' + p.m + '-' + p.d; }
function lwTooltipTime(t) { var p = lwParts(t); return TOOLTIP_CLOCK ? lwYmd(p) + ' ' + p.h + ':' + p.mi : lwYmd(p); }
function lwTickMark(t, type) {
  var p = lwParts(t);
  if (type === 0) return String(p.y);
  if (type === 1) return p.y + '-' + p.m;
  if (type === 2) return p.m + '-' + p.d;
  if (type === 3) return p.h + ':' + p.mi;
  return p.h + ':' + p.mi + ':' + p.s;
}
"""


_JS_TEMPLATE = """
(function () {
  var LWC = LightweightCharts;
  var el = document.getElementById('lw-chart');
  var chart = LWC.createChart(el, OPTS);
  // 시간 표기: JSON 옵션에는 함수를 못 실으므로 생성 뒤 적용 (TIME_FORMAT_JS)
  chart.applyOptions({ localization: { timeFormatter: lwTooltipTime },
                       timeScale: { tickMarkFormatter: lwTickMark } });
  var LINE_BASE = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  function line(opts, pane) { return chart.addSeries(LWC.LineSeries, Object.assign({}, LINE_BASE, opts), pane); }
  function guide(series, price, color, style) {
    series.createPriceLine({ price: price, color: color, lineWidth: 1, lineStyle: style, axisLabelVisible: false, title: '' });
  }
  // 고정 스케일 pane(스토캐 0~320 · RSI 0~100): autoScale 을 끄고 setVisibleRange 로 못 박는다.
  // (autoscale 은 마커 여백을 더해 범위를 넓히므로 Plotly 의 고정 range 와 달라진다.) 축 더블클릭으로
  // autoScale 이 켜져도 모든 시리즈에 같은 범위의 provider 를 걸어 크게 벗어나지 않게 한다.
  var fixedScales = [];
  function fixedRange(seriesList, lo, hi, margin) {
    var provider = function () { return { priceRange: { minValue: lo, maxValue: hi }, margins: { above: 0, below: 0 } }; };
    seriesList.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: provider }); });
    var scale = seriesList[0].priceScale();
    scale.applyOptions({ autoScale: false, scaleMargins: { top: margin, bottom: margin } });
    fixedScales.push({ scale: scale, lo: lo, hi: hi });
  }
  function applyFixedScales() {
    fixedScales.forEach(function (f) { try { f.scale.setVisibleRange({ from: f.lo, to: f.hi }); } catch (e) {} });
  }
  // 영역 음영: BaselineSeries(baseValue=임계값). 위 구간(side='above')은 top 채움만, 아래 구간은 bottom 채움만
  // 켜고 선은 숨긴다 → 시리즈와 임계선 사이만 채워져 plotly 의 add_masked_fill_segments 와 같은 모양.
  var TRANSPARENT = 'rgba(0,0,0,0)';
  function zoneFill(data, base, side, color, pane) {
    var above = side === 'above';
    var s = chart.addSeries(LWC.BaselineSeries, Object.assign({}, LINE_BASE, {
      baseValue: { type: 'price', price: base }, lineVisible: false, lineWidth: 1,
      topLineColor: TRANSPARENT, bottomLineColor: TRANSPARENT,
      topFillColor1: above ? color : TRANSPARENT, topFillColor2: above ? color : TRANSPARENT,
      bottomFillColor1: above ? TRANSPARENT : color, bottomFillColor2: above ? TRANSPARENT : color,
    }), pane);
    s.setData(data);
    return s;
  }
  var paneOf = {};
  PANES.forEach(function (p, i) { paneOf[p.kind] = i; });

  // ---- pane 0: 가격 + 이평 + 거래량 오버레이 + 구조 기준선
  var candles = chart.addSeries(LWC.CandlestickSeries, CANDLE_OPTS, 0);
  candles.setData(PAYLOAD.candles);
  var volume = chart.addSeries(LWC.HistogramSeries, {
    priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false,
  }, 0);
  volume.priceScale().applyOptions({ scaleMargins: { top: VOLUME_TOP, bottom: 0 } });
  volume.setData(PAYLOAD.volume);
  var maSeries = {};
  Object.keys(PAYLOAD.mas).forEach(function (period) {
    var s = MA_STYLES[period] || { color: '#888888', width: 1, style: 0 };
    var ser = line({ color: s.color, lineWidth: s.width, lineStyle: s.style }, 0);
    ser.setData(PAYLOAD.mas[period]);
    maSeries[period] = ser;
  });
  STRUCT_LINES.forEach(function (l) {
    candles.createPriceLine({ price: l.price, color: l.color, lineWidth: 1, lineStyle: l.style,
                              axisLabelVisible: true, title: l.title });
  });

  // ---- pane 스토캐 3중 (한 pane 에 오프셋 배치, 층당 20/80, 분리선 2)
  var stochK = {}, stochD = {}, stochZones = [], rsiZones = [];
  if (PAYLOAD.stoch && paneOf.stoch !== undefined) {
    var sp = paneOf.stoch, anchor = null;
    PAYLOAD.stoch.layers.forEach(function (L) {
      // 음영은 선보다 먼저 추가(아래 레이어) — 층별 임계값 = 20/80 + 오프셋 (guides 와 동일)
      stochZones.push(zoneFill(L.k, L.guides[1], 'above', ZONE_FILL.stoch_overbought, sp));
      stochZones.push(zoneFill(L.k, L.guides[0], 'below', ZONE_FILL.stoch_oversold, sp));
      var k = line({ color: L.k_color, lineWidth: 1 }, sp); k.setData(L.k);
      var d = line({ color: L.d_color, lineWidth: 1 }, sp); d.setData(L.d);
      L.guides.forEach(function (g) { guide(k, g, STOCH_GUIDE_COLOR, 2); });
      stochK[L.label] = k; stochD[L.label] = d;
      if (!anchor) anchor = k;
    });
    PAYLOAD.stoch.separators.forEach(function (s) { guide(anchor, s, STOCH_SEP_COLOR, 0); });
    fixedRange(Object.keys(stochK).map(function (k) { return stochK[k]; })
               .concat(Object.keys(stochD).map(function (k) { return stochD[k]; }), stochZones), 0, PAYLOAD.stoch.max_y, 0.02);
  }

  // ---- pane MACD: hist + macd/signal + 0선
  var macdLine = null, macdHist = null, macdSignal = null;
  if (PAYLOAD.macd && paneOf.macd !== undefined) {
    var mp = paneOf.macd;
    macdHist = chart.addSeries(LWC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false, base: 0 }, mp);
    macdHist.setData(PAYLOAD.macd.hist);
    macdLine = line({ color: MACD_COLORS.macd, lineWidth: 1 }, mp); macdLine.setData(PAYLOAD.macd.macd);
    macdSignal = line({ color: MACD_COLORS.signal, lineWidth: 1 }, mp); macdSignal.setData(PAYLOAD.macd.signal);
    guide(macdLine, 0, STOCH_GUIDE_COLOR, 2);
    // 가격 pane 의 8%/22% 마진(거래량 띠용)을 물려받지 않게 하위 pane 은 대칭 마진
    macdLine.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
  }

  // ---- pane RSI: 라인 + 30/50/70
  var rsiLine = null;
  if (PAYLOAD.rsi && paneOf.rsi !== undefined) {
    var rp = paneOf.rsi;
    rsiZones = [
      zoneFill(PAYLOAD.rsi.line, PAYLOAD.zones.rsi.high, 'above', ZONE_FILL.rsi_overbought, rp),
      zoneFill(PAYLOAD.rsi.line, PAYLOAD.zones.rsi.low, 'below', ZONE_FILL.rsi_oversold, rp),
    ];
    rsiLine = line({ color: RSI_COLOR, lineWidth: 1 }, rp); rsiLine.setData(PAYLOAD.rsi.line);
    PAYLOAD.rsi.guides.forEach(function (g) { guide(rsiLine, g.value, g.color, g.style); });
    fixedRange([rsiLine].concat(rsiZones), 0, 100, 0.05);
  }

  // ---- 알람 마커 (createSeriesMarkers) — 텍스트 라벨 유지, 확정 봉 위치
  var M = PAYLOAD.markers || { stoch: {}, rsi: [], macd: [] };
  Object.keys(M.stoch).forEach(function (label) {
    if (stochK[label] && M.stoch[label].length) LWC.createSeriesMarkers(stochK[label], M.stoch[label]);
  });
  if (rsiLine && M.rsi.length) LWC.createSeriesMarkers(rsiLine, M.rsi);
  if (macdLine && M.macd.length) LWC.createSeriesMarkers(macdLine, M.macd);

  // ---- 크로스헤어 정보 오버레이: 커서 봉의 시/고/저/종·직전 종가 대비 변화율 + 하위 pane 값.
  //      값은 PAYLOAD(시간→값 맵)에서 읽으므로 hover 와 '커서 밖 = 마지막 봉' 이 같은 경로다.
  function tmap(arr) { var m = {}; (arr || []).forEach(function (p) { m[p.time] = p.value; }); return m; }
  var candleAt = {}, candleIdx = {};
  PAYLOAD.candles.forEach(function (c, i) { candleAt[c.time] = c; candleIdx[c.time] = i; });
  var subMaps = { stoch: [], macd: null, rsi: null };
  if (PAYLOAD.stoch) PAYLOAD.stoch.layers.forEach(function (L) {
    subMaps.stoch.push({ label: L.label, offset: L.offset, k: tmap(L.k), d: tmap(L.d) });
  });
  if (PAYLOAD.macd) subMaps.macd = { macd: tmap(PAYLOAD.macd.macd), signal: tmap(PAYLOAD.macd.signal), hist: tmap(PAYLOAD.macd.hist) };
  if (PAYLOAD.rsi) subMaps.rsi = tmap(PAYLOAD.rsi.line);
  var fmtPrice = function (v) { try { return candles.priceFormatter().format(v); } catch (e) { return String(v); } };
  function fmt1(v) { return (v === undefined || v === null || isNaN(v)) ? '—' : (Math.round(v * 10) / 10).toFixed(1); }
  function span(text, color) { return '<span style="color:' + color + '">' + text + '</span>'; }
  function renderInfo(time) {
    var c = candleAt[time];
    var box = document.getElementById('lw-ohlc');
    if (!c) { box.innerHTML = ''; return; }
    var i = candleIdx[time], prev = i > 0 ? PAYLOAD.candles[i - 1].close : null;
    var chg = (prev && prev !== 0) ? (c.close - prev) / prev * 100 : null;
    var up = chg === null ? (c.close >= c.open) : chg >= 0;
    var col = up ? CANDLE_OPTS.upColor : CANDLE_OPTS.downColor;
    var chgText = chg === null ? '' : ' ' + span((chg >= 0 ? '+' : '') + chg.toFixed(2) + '%', col);
    var line1 = lwTooltipTime(time) + ' · 시 ' + fmtPrice(c.open) + ' 고 ' + fmtPrice(c.high)
              + ' 저 ' + fmtPrice(c.low) + ' 종 ' + span(fmtPrice(c.close), col) + chgText;
    var parts = [];
    if (subMaps.stoch.length && paneOf.stoch !== undefined) {
      parts.push('스토캐 K ' + subMaps.stoch.map(function (L) {
        var k = L.k[time]; return L.label + ' ' + fmt1(k === undefined ? undefined : k - L.offset);
      }).join(' · '));
    }
    if (subMaps.macd && paneOf.macd !== undefined) {
      parts.push('MACD ' + fmt1(subMaps.macd.macd[time]) + ' / 신호 ' + fmt1(subMaps.macd.signal[time])
                 + ' / 히스토 ' + fmt1(subMaps.macd.hist[time]));
    }
    if (subMaps.rsi && paneOf.rsi !== undefined) parts.push('RSI ' + fmt1(subMaps.rsi[time]));
    box.innerHTML = line1 + (parts.length ? '<br>' + parts.join(' · ') : '');
  }
  var lastTime = PAYLOAD.candles.length ? PAYLOAD.candles[PAYLOAD.candles.length - 1].time : null;
  chart.subscribeCrosshairMove(function (param) {
    var t = (param && param.time !== undefined && candleAt[param.time]) ? param.time : lastTime;
    renderInfo(t);
  });
  renderInfo(lastTime);

  // ---- pane 비중 (지표 중심 근사) — 경계 드래그로 사용자가 바꿀 수 있다
  var panes = chart.panes();
  PANES.forEach(function (p, i) { if (panes[i]) panes[i].setStretchFactor(p.stretch); });

  // ---- 세로 줌 (가격 pane): 가격축 위 휠 → 고정 범위(autoscaleInfoProvider 오버라이드),
  //      가격축 더블클릭 → autoScale 복귀. 차트 본체 휠은 건드리지 않는다(LW 시간축 줌 그대로).
  var wrap = document.getElementById('lw-wrap');
  var priceSeries = [candles].concat(Object.keys(maSeries).map(function (k) { return maSeries[k]; }));
  var vz = { active: false, lo: null, hi: null };
  function priceAxisWidth() { try { return chart.priceScale('right').width(); } catch (e) { return 0; } }
  function pricePaneHeight() { var p = chart.panes(); return p.length ? p[0].getHeight() : el.clientHeight; }
  function overPriceAxis(e) {
    var r = el.getBoundingClientRect();
    var x = e.clientX - r.left, y = e.clientY - r.top;
    return x >= r.width - priceAxisWidth() && y >= 0 && y <= pricePaneHeight();
  }
  function applyFixed(lo, hi) {
    if (!(hi > lo)) return;
    vz.active = true; vz.lo = lo; vz.hi = hi;
    var provider = function () { return { priceRange: { minValue: lo, maxValue: hi }, margins: { above: 0, below: 0 } }; };
    priceSeries.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: provider }); });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0, bottom: 0 }, autoScale: true });
  }
  function resetVertical() {
    vz.active = false; vz.lo = null; vz.hi = null;
    priceSeries.forEach(function (s) { s.applyOptions({ autoscaleInfoProvider: undefined }); });
    candles.priceScale().applyOptions({ scaleMargins: OPTS.rightPriceScale.scaleMargins, autoScale: true });
  }
  wrap.addEventListener('wheel', function (e) {
    if (!overPriceAxis(e)) return;                       // 본체 휠 = LW 시간축 줌
    e.preventDefault(); e.stopPropagation();
    var h = pricePaneHeight();
    var top = candles.coordinateToPrice(0), bottom = candles.coordinateToPrice(h);
    if (top === null || bottom === null) return;
    var y = e.clientY - el.getBoundingClientRect().top;
    var at = candles.coordinateToPrice(Math.max(0, Math.min(h, y)));
    if (at === null) at = (top + bottom) / 2;
    var f = e.deltaY < 0 ? VZOOM_IN : VZOOM_OUT;        // 위로 굴리면 확대
    applyFixed(at - (at - bottom) * f, at + (top - at) * f);
  }, { capture: true, passive: false });
  wrap.addEventListener('dblclick', function (e) { if (overPriceAxis(e)) resetVertical(); }, true);

  // ---- pane 단독 확대 모드: stretch factor 만 재배분 (rerun 없음 → 줌·팬·세로 줌 상태 유지).
  //      나머지 pane 은 SOLO_COLLAPSED_PX 띠로 접는다(0 높이는 쓰지 않음). '전체' 로 초기 비중 복원.
  //      단독 진입 시 컨테이너(#lw-wrap)와 iframe 높이를 접힌 띠 합계만큼 늘려 선택 pane 이 전체 모드의
  //      pane 영역 전체를 차지하게 하고, 전체 복귀 시 원래 높이로 되돌린다. 접힌 띠 위에는 pane 이름만 얹는다(클릭 → 그 pane 단독).
  var solo = { kind: SOLO_ALL, baseHeight: wrap.clientHeight };
  var frameEl = null;
  try { frameEl = window.frameElement; } catch (e) { frameEl = null; }   // 교차 출처면 null → iframe 확장 생략
  function setContainerHeight(h) {
    wrap.style.height = h + 'px';
    if (!frameEl) return;
    frameEl.style.height = h + 'px'; frameEl.setAttribute('height', String(h));
    // Streamlit 요소 컨테이너(stElementContainer)는 flex: 0 0 <height>px 로 고정돼 있어 iframe 만 키우면 아래
    // 캡션과 겹친다 → 인라인으로 같은 값을 준다(전체 복귀 시 base 로 되돌림).
    var holder = frameEl.parentElement;
    if (holder) { holder.style.height = h + 'px'; holder.style.flexBasis = h + 'px'; }
  }
  var strips = {};
  var stripBox = document.getElementById('lw-strips');
  PANES.forEach(function (p) {
    var d = document.createElement('div');
    d.className = 'lw-strip'; d.setAttribute('data-kind', p.kind); d.textContent = PANE_LABELS[p.kind] || p.kind;
    d.style.display = 'none';
    d.addEventListener('click', function () { applySolo(p.kind); });
    stripBox.appendChild(d); strips[p.kind] = d;
  });
  function layoutStrips() {
    var panes = chart.panes(), wr = wrap.getBoundingClientRect();
    PANES.forEach(function (p, i) {
      var d = strips[p.kind];
      if (!panes[i] || solo.kind === SOLO_ALL || p.kind === solo.kind) { d.style.display = 'none'; return; }
      var r = panes[i].getHTMLElement().getBoundingClientRect();
      d.style.display = 'block';
      d.style.top = (r.top - wr.top) + 'px'; d.style.left = (r.left - wr.left) + 'px';
      d.style.width = r.width + 'px'; d.style.height = r.height + 'px'; d.style.lineHeight = r.height + 'px';
    });
  }
  function applySolo(kind) {
    var panes = chart.panes();
    var total = panes.reduce(function (a, p) { return a + p.getHeight(); }, 0);
    var others = Math.max(0, PANES.length - 1);
    var extra = kind === SOLO_ALL ? 0 : SOLO_COLLAPSED_PX * others;
    // 전체 모드의 pane 영역 = 선택 pane 이 가질 수 있는 최대 → 컨테이너를 띠 합계만큼 늘려 그 크기를 보장
    var fullArea = solo.kind === SOLO_ALL ? total : total - SOLO_COLLAPSED_PX * others;
    setContainerHeight(solo.baseHeight + extra);
    PANES.forEach(function (p, i) {
      if (!panes[i]) return;
      if (kind === SOLO_ALL) { panes[i].setStretchFactor(p.stretch); return; }
      // stretch 는 상대값 — 목표 px 를 그대로 factor 로 주면 비례 배분이 정확히 px 가 된다
      panes[i].setStretchFactor(p.kind === kind ? Math.max(1, fullArea) : SOLO_COLLAPSED_PX);
    });
    solo.kind = kind;
    var btns = document.querySelectorAll('#lw-solo button');
    for (var b = 0; b < btns.length; b++) btns[b].classList.toggle('on', btns[b].getAttribute('data-kind') === kind);
    // 가격 pane 이 접히면 캡션·버튼 줄을 띠 아래로 내려 '가격' 띠 이름과 겹치지 않게 한다
    var overlayTop = (kind !== SOLO_ALL && kind !== 'price') ? (SOLO_COLLAPSED_PX + 6) : 6;
    document.getElementById('lw-caption').style.top = overlayTop + 'px';
    document.getElementById('lw-ohlc').style.top = (overlayTop + OHLC_OFFSET) + 'px';
    document.getElementById('lw-solo').style.top = overlayTop + 'px';
    applyFixedScales();
    layoutStrips();
    requestAnimationFrame(layoutStrips);   // autoSize(ResizeObserver) 반영 뒤 한 번 더
  }
  var soloBtns = document.querySelectorAll('#lw-solo button');
  for (var bi = 0; bi < soloBtns.length; bi++) {
    soloBtns[bi].addEventListener('click', function (ev) { applySolo(ev.currentTarget.getAttribute('data-kind')); });
  }
  if (window.ResizeObserver) { new ResizeObserver(function () { requestAnimationFrame(layoutStrips); }).observe(el); }
  wrap.addEventListener('mouseup', function () { requestAnimationFrame(layoutStrips); });   // 경계 드래그 뒤 재배치

  var n = PAYLOAD.candles.length;
  if (n > WINDOW) { chart.timeScale().setVisibleLogicalRange({ from: n - WINDOW, to: n + 2 }); }
  else { chart.timeScale().fitContent(); }
  applyFixedScales();
  window.__lw = { chart: chart, candles: candles, volume: volume, mas: maSeries, panes: PANES,
                  stochK: stochK, stochD: stochD, macd: macdLine, macdHist: macdHist, macdSignal: macdSignal,
                  rsi: rsiLine, vzoom: vz, resetVertical: resetVertical, overPriceAxis: overPriceAxis,
                  solo: solo, applySolo: applySolo, stochZones: stochZones, rsiZones: rsiZones,
                  strips: strips, layoutStrips: layoutStrips, frameEl: frameEl,
                  renderInfo: renderInfo };  // 검증·측정용 핸들
})();
"""


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
) -> str:
    """components.html 에 넘길 HTML 문자열.

    gate_context 는 필수(비어 있으면 ValueError) — 게이트 상태 없이 가격 화면이 단독 표시되지 않는다.
    tracker_lines 는 60MA 전환 추적(미검증) 대기 중 후보의 가격선(구조 기준선과 같은 사전 형식) — 없으면 불변.
    """
    if not isinstance(gate_context, str) or not gate_context.strip():
        raise ValueError("gate_context 는 필수다 — 게이트 상태 라벨 없이 가격 화면을 그리지 않는다")
    payload = frame_to_lw_payload(df)
    panes = pane_layout(payload, show_stochastic=show_stochastic, show_macd=show_macd, show_rsi=show_rsi)
    lines = struct_reference_lines(struct_reference)
    extra = list(tracker_lines or [])
    caption_html = (f"{_escape(str(symbol))} {_escape(str(display_interval))} · {_escape(gate_context)}"
                    f"{struct_caption_html(lines)}{tracker_caption_html(extra)}")
    vendor = vendor_js if vendor_js is not None else load_vendor_js()
    height = int(chart_height)

    consts = "\n".join([
        f"var PAYLOAD = {json.dumps(payload, ensure_ascii=False)};",
        f"var PANES = {json.dumps(panes)};",
        f"var OPTS = {json.dumps(chart_options(), ensure_ascii=False)};",
        f"var CANDLE_OPTS = {json.dumps(candle_options())};",
        f"var MA_STYLES = {json.dumps(ma_styles())};",
        # label(의미)은 캡션 전용 — JS 로는 가격선 속성만 보낸다(title 은 빈 문자열).
        f"var STRUCT_LINES = {json.dumps([{k: v for k, v in l.items() if k != 'label'} for l in lines + extra], ensure_ascii=False)};",
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

# 세로 줌(가격 pane 전용): 가격축 위 휠 1틱당 배율. 공개 API 는 autoscaleInfoProvider 오버라이드 —
# 세로 줌 중에는 고정 범위, 가격축 더블클릭으로 autoScale 복귀.
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
) -> None:
    """LW 엔진 렌더. 높이는 사이드바 셀렉트 값을 그대로 iframe 높이로 쓴다."""
    if df is None or df.empty:
        return
    html = build_lw_html(
        df, symbol, display_interval, gate_context,
        chart_height=chart_height, struct_reference=struct_reference,
        show_stochastic=show_stochastic, show_macd=show_macd, show_rsi=show_rsi,
        tracker_lines=tracker_lines,
    )
    components.html(html, height=int(chart_height), scrolling=False)
    st.caption(LW_CONTROLS_CAPTION)
