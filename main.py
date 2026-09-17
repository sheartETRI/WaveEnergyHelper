# main.py — WaveEnergyHelper 진입점 (signal-alarm: 차트 + 알람 전용 슬림 구성).
#
# 다섯 가지만 본다:
#   · 차트 (캔들 + 이평 + 스토캐 3층 스택 + MACD + RSI)
#   · 스토캐 쌍바닥 / 쌍봉 검출
#   · RSI 과매도 / 과매수 진입
#   · MACD 골든 / 데드크로스, 0선 상향 / 하향
# 검출기는 기존 것을 그대로 쓴다(indicators/). 알람 패널만 신규(display/alarm_panel.py).
#
# 조립부만 담당한다 — 화면 상단에 알람, 아래에 차트. 연구·검증 패널 없음.
import streamlit as st

from charts.lw_builder import render_lw_chart
from charts.plotly_builder import (
    CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT, DEFAULT_LAYOUT_MODE, LAYOUT_MODE_LABELS, LAYOUT_MODES,
    render_chart,
)
from config.settings import CUSTOM_INTERVALS, STOCH_LAYERS, SUPPORTED_SYMBOLS, TIMEFRAMES
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from display.alarm_panel import DEFAULT_HISTORY_BARS, render_alarm_panel
from display.code_version import render_code_version
from indicators.moving_averages import add_moving_averages
from indicators.oscillators import add_macd, add_rsi
from indicators.stochastic import add_stochastic_slow_layers

# 레이어 선택 표시용 — "대(20,10,10)" 형태. 값은 STOCH_LAYERS의 label.
_ROLE_KO = {"Top": "대", "Mid": "중", "Bot": "소"}
_LAYER_CHOICES = {f"{_ROLE_KO.get(l['name'], l['name'])}{l['label']}": l["label"] for l in STOCH_LAYERS}

DEFAULT_INTERVAL = "1h"

# "MACD 패널" 토글이 기본 꺼지는 TF. 15m 은 크로스 채터링이 가장 잦아 기본 꺼짐 — 켜면 다른 TF와
# 정의·동작이 같다(정의 차등 없음). 토글은 MACD 계산·알람·차트 패널을 함께 켜고 끈다.
MACD_PANEL_DEFAULT_OFF_INTERVALS = ("15m",)

# 차트 엔진(1단계): Plotly 기본 유지 — LW 검수 통과 전까지 기본값을 바꾸지 않는다.
CHART_ENGINES = ("Plotly", "LW")
DEFAULT_CHART_ENGINE = "Plotly"

# 게이트 문맥 라벨 — LW 렌더 함수의 필수 인자(main 브랜치 8cdd4e5 원칙 승계).
# signal-alarm 은 main 과 2026-06-12(9436ed1) 에 갈라져 게이트 모듈(display/wave_gate_context ·
# analysis/wave_align_gate_forward)이 없다. 상태를 지어내지 않고 "모듈 없음" 을 그대로 표기한다.
# 공급원을 이식할지는 별도 결정 사항 — 이식되면 이 함수만 gate_label 로 바꾼다.
GATE_CONTEXT_UNAVAILABLE = "[게이트 미적용 — 이 브랜치에 게이트 모듈 없음]"


def gate_context_for(symbol: str, interval: str) -> str:
    """LW 차트에 병기할 게이트 상태 라벨. 이 브랜치에는 공급원이 없어 고정 문구를 돌려준다."""
    return GATE_CONTEXT_UNAVAILABLE


def macd_panel_default(interval: str) -> bool:
    """'MACD 패널' 토글 기본값 — 15m 만 꺼짐, 나머지 켬."""
    return interval not in MACD_PANEL_DEFAULT_OFF_INTERVALS


def load_frame(symbol: str, interval: str, with_macd: bool = True):
    """OHLCV 적재 → 지표 계산. 실패 시 None.

    with_macd=False 면 add_macd 를 건너뛴다 → MACD 컬럼이 없어 알람 레이어가 MACD 4종을 조용히
    건너뛰고 차트에도 MACD 패널이 없다("MACD 패널" 토글 꺼짐).
    fetch/build/지표는 각자 st.cache_data(ttl=600)를 갖고 있어 여기서 추가 캐시는 두지 않는다.
    """
    fetch_interval = get_fetch_interval(interval)
    raw = fetch_klines(symbol, fetch_interval, get_auto_limit(interval))
    if not raw:
        return None

    df = build_dataframe(raw)
    if df is None or df.empty:
        return None
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)

    df = add_moving_averages(df)
    df = add_stochastic_slow_layers(df)
    if with_macd:
        df = add_macd(df)
    df = add_rsi(df)
    return df


def render_sidebar() -> dict:
    """전역 필터만 사이드바에 둔다(본문은 메인 영역)."""
    st.sidebar.header("대상")
    symbol = st.sidebar.selectbox("심볼", options=SUPPORTED_SYMBOLS, index=0)
    interval = st.sidebar.selectbox(
        "타임프레임",
        options=TIMEFRAMES,
        index=TIMEFRAMES.index(DEFAULT_INTERVAL) if DEFAULT_INTERVAL in TIMEFRAMES else 0,
    )

    st.sidebar.divider()
    st.sidebar.header("알람")
    history_bars = st.sidebar.slider(
        "이력 구간 (봉)", min_value=20, max_value=500, value=DEFAULT_HISTORY_BARS, step=10,
        help="최근 몇 봉까지의 신호를 이력 표에 보여줄지",
    )
    include_candidates = st.sidebar.checkbox(
        "후보 신호 포함", value=True,
        help="두 번째 피봇까지 성립했으나 넥라인 돌파 전인 미확정 패턴",
    )
    layer_names = st.sidebar.multiselect(
        "스토캐 레이어", options=list(_LAYER_CHOICES), default=list(_LAYER_CHOICES),
    )

    st.sidebar.divider()
    st.sidebar.header("차트")
    chart_engine = st.sidebar.radio(
        "차트 엔진", options=list(CHART_ENGINES), index=list(CHART_ENGINES).index(DEFAULT_CHART_ENGINE),
        horizontal=True,
        help="Plotly=현행. LW=lightweight-charts 1단계(가격 패널만: 캔들·이평·거래량·기준선·게이트 라벨). "
             "하위 지표·알람 마커는 2단계 예정.",
    )
    show_stoch = st.sidebar.checkbox("스토캐 패널", value=True)
    # 값은 plotly_builder가 분기하는 문자열 그대로여야 한다("Separated" 철자 주의).
    stoch_view = st.sidebar.radio(
        "스토캐 표시", options=["Stacked", "Separated"], index=0, horizontal=True,
        disabled=not show_stoch,
        help="Stacked=3층 한 패널, Separated=레이어별 패널 분리",
    )
    # key 없이 value 만 바꾸면 TF 전환 시 새 위젯으로 잡혀 기본값이 TF 별로 적용된다.
    show_macd = st.sidebar.checkbox(
        "MACD 패널", value=macd_panel_default(interval),
        help="MACD 계산·크로스/0선 알람·차트 패널을 함께 켜고 끕니다. 15m 은 기본 꺼짐(켜면 동일 동작).",
    )
    show_rsi = st.sidebar.checkbox("RSI 패널", value=True)
    # 표시 모드: 패널 비중 세트(지표 중심 = 하위 3패널 합 0.61, 기본형 = 0.44)와 하위 패널 라벨 표시.
    layout_mode = st.sidebar.radio(
        "표시 모드", options=list(LAYOUT_MODES), index=list(LAYOUT_MODES).index(DEFAULT_LAYOUT_MODE),
        format_func=lambda mode: LAYOUT_MODE_LABELS[mode], horizontal=True,
        help="지표 중심=가격 0.34·스토캐 0.26·MACD 0.19·RSI 0.16, 하위 패널 라벨 표시. 기본형=가격 0.50, 라벨 숨김.",
    )
    chart_height = st.sidebar.selectbox(
        "차트 높이 (px)", options=list(CHART_HEIGHT_OPTIONS),
        index=list(CHART_HEIGHT_OPTIONS).index(DEFAULT_CHART_HEIGHT),
        help="Streamlit 은 화면 높이를 읽지 못해 선택식. 세로 확대·축소는 차트 위 휠로.",
    )

    render_code_version()   # 사이드바 맨 아래: 기동 HEAD · 기동 시각 · 경로

    return {
        "symbol": symbol,
        "interval": interval,
        "chart_engine": chart_engine,
        "history_bars": history_bars,
        "include_candidates": include_candidates,
        "layers": [_LAYER_CHOICES[name] for name in layer_names],
        "show_stoch": show_stoch,
        "stoch_view": stoch_view,
        "show_macd": show_macd,
        "show_rsi": show_rsi,
        "layout_mode": layout_mode,
        "chart_height": chart_height,
    }


def main():
    st.set_page_config(layout="wide", page_title="WaveEnergyHelper — 알람")
    cfg = render_sidebar()
    symbol, interval = cfg["symbol"], cfg["interval"]

    with st.spinner(f"{symbol} {interval} 적재 중..."):
        df = load_frame(symbol, interval, with_macd=cfg["show_macd"])

    if df is None or df.empty:
        st.error(f"{symbol} {interval} 데이터를 불러오지 못했습니다.")
        return

    render_alarm_panel(
        df, symbol, interval,
        history_bars=cfg["history_bars"],
        include_candidates=cfg["include_candidates"],
        layers=cfg["layers"] or None,
    )

    if cfg["chart_engine"] == "LW":
        # 1단계: 가격 패널만. struct_reference 공급원(analysis/wave_mm_struct_stop)도 이 브랜치에 없어
        # None → "기준선 없음" 폴백. gate_context 는 필수 인자.
        render_lw_chart(
            df, symbol, interval, gate_context_for(symbol, interval),
            chart_height=cfg["chart_height"], struct_reference=None,
        )
        return

    render_chart(
        df, symbol, interval,
        show_stochastic=cfg["show_stoch"],
        stochastic_view_mode=cfg["stoch_view"],
        show_stoch_fill=cfg["show_stoch"],
        show_macd=cfg["show_macd"],
        show_rsi=cfg["show_rsi"],
        show_rsi_fill=cfg["show_rsi"],
        chart_height=cfg["chart_height"],
        layout_mode=cfg["layout_mode"],
    )


if __name__ == "__main__":
    main()
