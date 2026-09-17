"""lightweight-charts 렌더 계층 — 1단계: 가격 패널만, Plotly 와 병존.

구조 결정(위임장 §0 고정):
- 서드파티 Streamlit 래퍼를 쓰지 않는다. ``st.components.v1.html`` 에 lightweight-charts
  standalone JS 를 직접 임베드한다.
- JS 는 CDN 이 아니라 저장소에 벤더링한다: ``charts/vendor/lightweight-charts.standalone.js``
  (버전은 VENDOR_VERSION 과 파일 헤더 주석에 명기). iframe 은 저장소 파일을 못 읽으므로
  HTML 문자열에 인라인한다.
- ``charts/plotly_builder.py`` 는 수정하지 않는다 — 색·굵기·표시 창 토큰만 import 해 승계한다.

1단계 범위: 캔들 + 이평선 전부 + 거래량 히스토그램(하단 오버레이) + 구조 기준선(가격선 2개)
+ 게이트 상태 라벨(차트 위 HTML 오버레이 캡션). 스토캐·MACD·RSI·알람 마커는 2단계 —
여기서는 "2단계 예정" 캡션만 낸다.

계약 승계(main 브랜치 8cdd4e5 의 원칙):
- ``gate_context`` 는 **필수 인자**다. 가격 화면이 상위 게이트 상태 없이 단독으로 표시되지
  않게 한다. 값의 산출은 호출부(display) 몫이며 여기서는 표기만 한다.
- ``struct_reference`` 는 ``{"reference_low": float, "line_price": float}`` (직전 확정 swing 저점과
  ×0.995 기준선). None 이면 선을 그리지 않고 캡션에 "기준선 없음" 을 병기한다. 라벨은 상태
  기술형으로 고정 — 손절 권고 류 표현을 쓰지 않는다.

동작 요건(위임장 §2): x 줌·팬 시 y 자동 밀착(rightPriceScale.autoScale), 휠 줌·드래그 팬·
크로스헤어, 컨테이너 폭 추종(autoSize=ResizeObserver), 높이는 사이드바 셀렉트 승계,
상승 적/하락 청 토큰 승계.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from charts.plotly_builder import (
    COLOR_BEAR,
    COLOR_BULL,
    RECENT_WINDOW,
    TV_BACKGROUND,
    TV_GRID,
    TV_TEXT,
)
from config.settings import MA_COLORS, MA_LINE_WIDTHS

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
STAGE2_CAPTION = "LW 엔진 1단계: 가격 패널만. 스토캐·MACD·RSI·알람 마커는 2단계 예정."

DASHED_MA_PERIODS = {40, 80}          # plotly_builder 와 동일: 40·80 은 점선 보조선
VOLUME_SCALE_TOP_MARGIN = 0.80        # 거래량은 하단 20% 오버레이
PRICE_SCALE_BOTTOM_MARGIN = 0.22      # 캔들이 거래량 띠와 겹치지 않게
LW_LINE_STYLE_SOLID = 0
LW_LINE_STYLE_DOTTED = 1
LW_LINE_STYLE_DASHED = 2


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


# ------------------------------------------------------------------ 직렬화
def _unix_seconds(ts: pd.Timestamp) -> int:
    """naive 인덱스는 UTC 로 간주한다 — LW 도 UTC 로 표시하므로 Plotly 가 보여주던 벽시계와 같다."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return int(ts.timestamp())


def frame_to_lw_payload(df: pd.DataFrame) -> dict:
    """데이터프레임 → LW setData 용 JSON 직렬화 가능 dict.

    - 시간 오름차순 정렬, 중복 시각은 마지막 행만(LW 는 단조 증가 시각을 요구).
    - NaN 은 시리즈별로 그 점만 뺀다(캔들은 OHLC 중 하나라도 NaN 이면 제외).
    - 거래량 색은 종가≥시가 적 / 그 외 청 (plotly_builder.add_volume_panel 과 동일 규칙).
    """
    required = {"open", "high", "low", "close"}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"candles": [], "volume": [], "mas": {}}

    frame = df.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    times = [_unix_seconds(ts) for ts in frame.index]

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
        if col not in frame.columns:
            continue
        series = frame[col]
        pts = [{"time": t, "value": float(v)} for t, v in zip(times, series) if pd.notna(v)]
        if pts:
            mas[str(period)] = pts
    return {"candles": candles, "volume": volume, "mas": mas}


def struct_reference_lines(struct_reference: Optional[dict]) -> list[dict]:
    """구조 기준선 2개(저점·×0.995). 없음/불완전이면 빈 목록 → 호출부가 '기준선 없음' 폴백."""
    if not struct_reference:
        return []
    low = struct_reference.get("reference_low")
    line = struct_reference.get("line_price")
    if low is None or line is None or pd.isna(low) or pd.isna(line):
        return []
    return [
        {"price": float(low), "color": STRUCT_LOW_COLOR, "style": LW_LINE_STYLE_DOTTED,
         "title": STRUCT_LOW_LABEL},
        {"price": float(line), "color": STRUCT_LINE_COLOR, "style": LW_LINE_STYLE_DASHED,
         "title": STRUCT_LINE_LABEL},
    ]


# ------------------------------------------------------------------ HTML
def chart_options() -> dict:
    """createChart 옵션 — 동작 요건(§2)을 여기 한곳에 둔다."""
    return {
        "autoSize": True,   # ResizeObserver 로 컨테이너 폭·높이 추종
        "layout": {"background": {"type": "solid", "color": TV_BACKGROUND}, "textColor": TV_TEXT,
                   "attributionLogo": False},
        "grid": {"vertLines": {"color": TV_GRID}, "horzLines": {"color": TV_GRID}},
        "rightPriceScale": {"autoScale": True, "borderVisible": False,
                            "scaleMargins": {"top": 0.08, "bottom": PRICE_SCALE_BOTTOM_MARGIN}},
        "timeScale": {"timeVisible": True, "secondsVisible": False, "borderVisible": False,
                      "rightOffset": 3},
        "crosshair": {"mode": 0},   # Normal — 자유 크로스헤어
        "handleScroll": {"mouseWheel": True, "pressedMouseMove": True,
                         "horzTouchDrag": True, "vertTouchDrag": False},
        "handleScale": {"mouseWheel": True, "pinch": True, "axisPressedMouseMove": True},
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


_JS_TEMPLATE = """
(function () {
  var el = document.getElementById('lw-chart');
  var chart = LightweightCharts.createChart(el, OPTS);
  var candles = chart.addSeries(LightweightCharts.CandlestickSeries, CANDLE_OPTS);
  candles.setData(PAYLOAD.candles);
  var volume = chart.addSeries(LightweightCharts.HistogramSeries, {
    priceFormat: { type: 'volume' }, priceScaleId: 'volume',
    lastValueVisible: false, priceLineVisible: false,
  });
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: VOLUME_TOP, bottom: 0 } });
  volume.setData(PAYLOAD.volume);
  var maSeries = {};
  Object.keys(PAYLOAD.mas).forEach(function (period) {
    var st = MA_STYLES[period] || { color: '#888888', width: 1, style: 0 };
    var s = chart.addSeries(LightweightCharts.LineSeries, {
      color: st.color, lineWidth: st.width, lineStyle: st.style,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    });
    s.setData(PAYLOAD.mas[period]);
    maSeries[period] = s;
  });
  STRUCT_LINES.forEach(function (l) {
    candles.createPriceLine({ price: l.price, color: l.color, lineWidth: 1, lineStyle: l.style,
                              axisLabelVisible: true, title: l.title });
  });
  var n = PAYLOAD.candles.length;
  if (n > WINDOW) { chart.timeScale().setVisibleLogicalRange({ from: n - WINDOW, to: n + 2 }); }
  else { chart.timeScale().fitContent(); }
  window.__lw = { chart: chart, candles: candles, volume: volume, mas: maSeries };  // 검증·측정용 핸들
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
    vendor_js: Optional[str] = None,
) -> str:
    """components.html 에 넘길 HTML 문자열.

    gate_context 는 필수(비어 있으면 ValueError) — 게이트 상태 없이 가격 화면이 단독 표시되지 않는다.
    """
    if not isinstance(gate_context, str) or not gate_context.strip():
        raise ValueError("gate_context 는 필수다 — 게이트 상태 라벨 없이 가격 화면을 그리지 않는다")
    payload = frame_to_lw_payload(df)
    lines = struct_reference_lines(struct_reference)
    struct_caption = "" if lines else f" · {STRUCT_LINE_MISSING}"
    caption = f"{symbol} {display_interval} · {gate_context}{struct_caption}"
    vendor = vendor_js if vendor_js is not None else load_vendor_js()
    height = int(chart_height)

    consts = "\n".join([
        f"var PAYLOAD = {json.dumps(payload, ensure_ascii=False)};",
        f"var OPTS = {json.dumps(chart_options(), ensure_ascii=False)};",
        f"var CANDLE_OPTS = {json.dumps(candle_options())};",
        f"var MA_STYLES = {json.dumps(ma_styles())};",
        f"var STRUCT_LINES = {json.dumps(lines, ensure_ascii=False)};",
        f"var VOLUME_TOP = {VOLUME_SCALE_TOP_MARGIN};",
        f"var WINDOW = {RECENT_WINDOW};",
    ])
    return (
        "<!-- lw_builder stage1 -->\n"
        f'<div id="lw-wrap" style="position:relative;width:100%;height:{height}px;'
        f'background:{TV_BACKGROUND};font-family:-apple-system,Segoe UI,Roboto,sans-serif;">\n'
        f'  <div id="lw-caption" style="position:absolute;top:6px;left:8px;z-index:5;'
        f'font-size:12px;color:{TV_TEXT};background:rgba(255,255,255,0.85);padding:2px 6px;'
        f'border-radius:3px;pointer-events:none;">{_escape(caption)}</div>\n'
        '  <div id="lw-chart" style="position:absolute;inset:0;"></div>\n'
        "</div>\n"
        f"<script>{vendor}</script>\n"
        f"<script>\n{consts}\n{_JS_TEMPLATE}</script>\n"
    )


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_lw_chart(
    df: pd.DataFrame,
    symbol: str,
    display_interval: str,
    gate_context: str,
    *,
    chart_height: int,
    struct_reference: Optional[dict] = None,
) -> None:
    """LW 엔진 렌더(1단계). 높이는 사이드바 셀렉트 값을 그대로 iframe 높이로 쓴다."""
    if df is None or df.empty:
        return
    html = build_lw_html(
        df, symbol, display_interval, gate_context,
        chart_height=chart_height, struct_reference=struct_reference,
    )
    components.html(html, height=int(chart_height), scrolling=False)
    st.caption(STAGE2_CAPTION)
