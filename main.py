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
from typing import Optional

import pandas as pd
import streamlit as st

from charts.lw_builder import render_lw_chart
from charts.theme import CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT
from config.settings import CUSTOM_INTERVALS, STOCH_LAYERS, SUPPORTED_SYMBOLS, TIMEFRAMES
from data.binance import clear_klines_cache, fetch_klines, get_auto_limit, last_fetch_at
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from display.alarm_panel import DEFAULT_HISTORY_BARS, render_alarm_panel
from display.code_version import render_code_version
from display.lw_gate_context import gate_label, struct_reference
from display.ma60_turn_tracker import render_tracker_section, tracker_reference_lines
from display.trend_structure import render_structure_section, structure_markers
from display.tz_label import KST_LABEL, to_kst
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

# 차트 엔진: LW(lightweight-charts) 단일. 2단계(위임 §6)에서 기본을 LW 로 전환한 뒤 회귀 확인용으로
# 남겨 두던 Plotly 라디오·표시 모드·스토캐 표시 컨트롤을 걷어냈다 — main 은 plotly 패키지 없이 기동한다.
# charts/plotly_builder.py 는 파일로 남아 있으며(레거시·연구 패널 경로) main 에서는 import 하지 않는다.

# 본문 탭 — 첫 탭이 기본(차트). 알람 패널은 두 번째 탭으로 이동(표시 계층 재배치만, 정의 무접촉).
MAIN_TABS = ("차트", "알람")

# 게이트 문맥 라벨 — LW 렌더 함수의 필수 인자(main 8cdd4e5 원칙 승계). 공급원은 main 에서 체리픽한
# 정의 파일(analysis/wave_align_gate_forward 등)을 display/lw_gate_context 가 import 만 해서 라이브 계산한다.


def gate_context_for(symbol: str, interval: str) -> str:
    """LW 차트에 병기할 상위 게이트 상태 라벨 (F2-b, 마지막 닫힌 봉 asof)."""
    return gate_label(symbol, interval)


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


# 데이터 새로고침 — 데이터 계층 캐시(fetch_klines, ttl=600)를 비우고 이 rerun 에서 최신 봉까지 다시 받는다.
# 버튼 클릭 자체가 rerun 이므로 별도 rerun 호출은 없다. 자동 주기 갱신은 없다(금지 사항).
REFRESH_BUTTON_LABEL = "🔄 데이터 새로고침"
REFRESH_RESET_NOTE = "새로고침 시 차트 줌·확대 상태가 초기화됩니다."


def data_freshness_caption(loaded_at: Optional[float], last_bar) -> str:
    """'마지막 로드 YYYY-MM-DD HH:MM:SS · 마지막 봉 MM-DD HH:MM (KST)' 1줄 — 둘 다 KST 표시(표시 직전 변환).

    loaded_at 은 실제 수신 시각(epoch, UTC 기준) — 캐시 히트 rerun 에서는 바뀌지 않는다. 없으면 '—'.
    봉 시각은 데이터(UTC) 를 to_kst 로만 바꾼다; 머신 로컬 시간대에 의존하지 않는다.
    """
    loaded = f"{to_kst(pd.Timestamp(loaded_at, unit='s')):%Y-%m-%d %H:%M:%S}" if loaded_at else "—"
    bar = f"{to_kst(last_bar):%m-%d %H:%M}" if last_bar is not None else "—"
    return f"마지막 로드 {loaded} · 마지막 봉 {bar} {KST_LABEL}"


def render_refresh_button() -> "st.delta_generator.DeltaGenerator":
    """사이드바 상단: 새로고침 버튼 + 신선도 캡션 자리(적재 뒤 main 이 채움) + 상태 초기화 고지."""
    if st.sidebar.button(REFRESH_BUTTON_LABEL, help="OHLCV 캐시를 비우고 최신 봉까지 다시 받습니다."):
        clear_klines_cache()
    slot = st.sidebar.empty()
    st.sidebar.caption(REFRESH_RESET_NOTE)
    return slot


def render_sidebar() -> dict:
    """전역 필터만 사이드바에 둔다(본문은 메인 영역)."""
    freshness_slot = render_refresh_button()
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
        help="두 번째 극점이 형성 중이고 폭 조건은 현재 충족하나 이탈 확정 전인 미확정 패턴",
    )
    layer_names = st.sidebar.multiselect(
        "스토캐 레이어", options=list(_LAYER_CHOICES), default=list(_LAYER_CHOICES),
    )

    st.sidebar.divider()
    st.sidebar.header("차트")
    st.sidebar.caption(
        "lightweight-charts: 가격·스토캐 3중·MACD·RSI pane, 알람 마커, 게이트 라벨·구조 기준선, "
        "패널 경계 드래그·세로 줌."
    )
    show_stoch = st.sidebar.checkbox("스토캐 패널", value=True)
    # key 없이 value 만 바꾸면 TF 전환 시 새 위젯으로 잡혀 기본값이 TF 별로 적용된다.
    show_macd = st.sidebar.checkbox(
        "MACD 패널", value=macd_panel_default(interval),
        help="MACD 계산·크로스/0선 알람·차트 패널을 함께 켜고 끕니다. 15m 은 기본 꺼짐(켜면 동일 동작).",
    )
    show_rsi = st.sidebar.checkbox("RSI 패널", value=True)
    chart_height = st.sidebar.selectbox(
        "차트 높이 (px)", options=list(CHART_HEIGHT_OPTIONS),
        index=list(CHART_HEIGHT_OPTIONS).index(DEFAULT_CHART_HEIGHT),
        help="Streamlit 은 화면 높이를 읽지 못해 선택식. 세로 확대·축소는 차트 위 휠로.",
    )

    render_code_version()   # 사이드바 맨 아래: 기동 HEAD · 기동 시각 · 경로

    return {
        "symbol": symbol,
        "interval": interval,
        "history_bars": history_bars,
        "include_candidates": include_candidates,
        "layers": [_LAYER_CHOICES[name] for name in layer_names],
        "show_stoch": show_stoch,
        "show_macd": show_macd,
        "show_rsi": show_rsi,
        "chart_height": chart_height,
        "freshness_slot": freshness_slot,
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
    cfg["freshness_slot"].caption(
        data_freshness_caption(last_fetch_at(symbol, get_fetch_interval(interval)), df.index[-1])
    )

    # 본문 2탭: [차트](기본) / [알람]. 사이드바 위젯은 공통. st.tabs 는 비활성 탭도 렌더한다(프론트에서 숨김).
    tab_chart, tab_alarm = st.tabs(MAIN_TABS)

    with tab_alarm:
        render_alarm_panel(
            df, symbol, interval,
            history_bars=cfg["history_bars"],
            include_candidates=cfg["include_candidates"],
            layers=cfg["layers"] or None,
        )
        # 60MA 전환 추적 (미검증) — 별도 섹션. 검출은 validation/wave_ma60_turn_probe 를 import 해 소비.
        # 반환된 후보 표의 '대기 중' 저점·기준선을 LW 가격 pane 에 함께 그린다(알람 푸시 대상 아님).
        tracker_frame = render_tracker_section(df, symbol, interval)
        # 추세 구조 추적 (미검증) — 고점·저점 연쇄(파동 번호 없음). 스윙 마커를 LW 가격 pane 에 함께 그린다.
        structure_result = render_structure_section(df, symbol, interval)

    with tab_chart:
        # gate_context 는 필수 인자. struct_reference 는 적재된 LTF 프레임으로 라이브 계산
        # (미검출·퇴화 시 None → "기준선 없음" 폴백).
        render_lw_chart(
            df, symbol, interval, gate_context_for(symbol, interval),
            chart_height=cfg["chart_height"], struct_reference=struct_reference(df, symbol, interval),
            show_stochastic=cfg["show_stoch"], show_macd=cfg["show_macd"], show_rsi=cfg["show_rsi"],
            tracker_lines=tracker_reference_lines(tracker_frame),
            structure_markers=structure_markers(structure_result),
        )

if __name__ == "__main__":
    main()
