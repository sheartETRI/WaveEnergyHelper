# main.py — WaveEnergyHelper 진입점 (signal-alarm: 차트 + 알람 전용 슬림 구성).
#
# 네 가지만 본다:
#   · 차트 (캔들 + 이평 + 스토캐 3층 스택 + RSI)
#   · 스토캐 쌍바닥 / 쌍봉 검출
#   · RSI 과매도 / 과매수 진입
# 검출기는 기존 것을 그대로 쓴다(indicators/). 알람 패널만 신규(display/alarm_panel.py).
#
# 조립부만 담당한다 — 화면 상단에 알람, 아래에 차트. 연구·검증 패널 없음.
import streamlit as st

from charts.plotly_builder import render_chart
from config.settings import CUSTOM_INTERVALS, STOCH_LAYERS, SUPPORTED_SYMBOLS, TIMEFRAMES
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from display.alarm_panel import DEFAULT_HISTORY_BARS, render_alarm_panel
from indicators.moving_averages import add_moving_averages
from indicators.oscillators import add_rsi
from indicators.stochastic import add_stochastic_slow_layers

# 레이어 선택 표시용 — "대(20,10,10)" 형태. 값은 STOCH_LAYERS의 label.
_ROLE_KO = {"Top": "대", "Mid": "중", "Bot": "소"}
_LAYER_CHOICES = {f"{_ROLE_KO.get(l['name'], l['name'])}{l['label']}": l["label"] for l in STOCH_LAYERS}

DEFAULT_INTERVAL = "1h"


def load_frame(symbol: str, interval: str):
    """OHLCV 적재 → 지표 계산. 실패 시 None.

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
    show_stoch = st.sidebar.checkbox("스토캐 패널", value=True)
    stoch_view = st.sidebar.radio(
        "스토캐 표시", options=["Stacked", "Separate"], index=0, horizontal=True,
        disabled=not show_stoch,
    )
    show_rsi = st.sidebar.checkbox("RSI 패널", value=True)

    return {
        "symbol": symbol,
        "interval": interval,
        "history_bars": history_bars,
        "include_candidates": include_candidates,
        "layers": [_LAYER_CHOICES[name] for name in layer_names],
        "show_stoch": show_stoch,
        "stoch_view": stoch_view,
        "show_rsi": show_rsi,
    }


def main():
    st.set_page_config(layout="wide", page_title="WaveEnergyHelper — 알람")
    cfg = render_sidebar()
    symbol, interval = cfg["symbol"], cfg["interval"]

    with st.spinner(f"{symbol} {interval} 적재 중..."):
        df = load_frame(symbol, interval)

    if df is None or df.empty:
        st.error(f"{symbol} {interval} 데이터를 불러오지 못했습니다.")
        return

    render_alarm_panel(
        df, symbol, interval,
        history_bars=cfg["history_bars"],
        include_candidates=cfg["include_candidates"],
        layers=cfg["layers"] or None,
    )

    render_chart(
        df, symbol, interval,
        show_stochastic=cfg["show_stoch"],
        stochastic_view_mode=cfg["stoch_view"],
        show_stoch_fill=cfg["show_stoch"],
        show_macd=False,
        show_rsi=cfg["show_rsi"],
        show_rsi_fill=cfg["show_rsi"],
    )


if __name__ == "__main__":
    main()
