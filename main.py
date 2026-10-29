# main.py — WaveEnergyHelper 진입점 (차트 / 알람 / 추세·관찰).
#
# 다섯 가지만 본다:
#   · 차트 (캔들 + 이평 + 스토캐 3층 스택 + MACD + RSI)
#   · 스토캐 쌍바닥 / 쌍봉 검출
#   · RSI 과매도 / 과매수 진입
#   · MACD 골든 / 데드크로스, 0선 상향 / 하향
# 검출기는 기존 것을 그대로 쓴다(indicators/). 알람 패널만 신규(display/alarm_panel.py).
#
# 조립부만 담당한다. 선택한 탭만 실행하며 연구·검증 패널은 연결하지 않는다.
from typing import Optional

import pandas as pd
import streamlit as st

from charts.lw_builder import render_lw_chart
from charts.theme import CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT
from config.settings import STOCH_LAYERS, SUPPORTED_SYMBOLS, TIMEFRAMES
from data.binance import (
    clear_klines_cache, data_source_line, last_fetch_at, last_fetch_error,
    stale_caption,
)
from data.frames import load_frame
from data.processor import get_fetch_interval
from display.analysis_cache import upward_candidates, downward_candidates, structure_analysis
from display.alarm_copy_text import build_copy_text, render_copy_expander
from display.alarm_panel import DEFAULT_HISTORY_BARS, render_alarm_panel
from display.tf_radar_panel import render_tf_radar_section
from display.wave_basis_radar import render_basis_radar_section
from display.observation_tab import render_observation_tab
from display.code_version import render_code_version
from display.lw_gate_context import gate_label, struct_reference
from display.ma60_down_tracker import down_tracker_reference_lines, render_down_tracker_section
from display.ma60_turn_tracker import render_tracker_section, tracker_reference_lines
from display.trend_structure import render_structure_section, structure_markers
from display.tz_label import KST_LABEL, to_kst

# 레이어 선택 표시용 — "대(20,10,10)" 형태. 값은 STOCH_LAYERS의 label.
_ROLE_KO = {"Top": "대", "Mid": "중", "Bot": "소"}
_LAYER_CHOICES = {f"{_ROLE_KO.get(l['name'], l['name'])}{l['label']}": l["label"] for l in STOCH_LAYERS}

DEFAULT_INTERVAL = "1h"
# 사이드바 심볼·TF 위젯 key — scripts/alarm_cli.py 가 AppTest 에서 같은 위젯 값을 넣어 실행한다(화면 동작 불변).
SYMBOL_KEY = "sidebar_symbol"
INTERVAL_KEY = "sidebar_interval"

# "MACD 패널" 토글이 기본 꺼지는 TF. 15m 은 크로스 채터링이 가장 잦아 기본 꺼짐 — 켜면 다른 TF와
# 정의·동작이 같다(정의 차등 없음). 토글은 MACD 계산·알람·차트 패널을 함께 켜고 끈다.
MACD_PANEL_DEFAULT_OFF_INTERVALS = ("15m",)

# 차트 엔진: LW(lightweight-charts) 단일. 2단계(위임 §6)에서 기본을 LW 로 전환한 뒤 회귀 확인용으로
# 남겨 두던 Plotly 라디오·표시 모드·스토캐 표시 컨트롤을 걷어냈다 — main 은 plotly 패키지 없이 기동한다.
# charts/plotly_builder.py 는 파일로 남아 있으며(레거시·연구 패널 경로) main 에서는 import 하지 않는다.

# 본문 탭 — 첫 탭이 기본(차트). 큰 추세·고정 관찰 설명은 전용 탭에서 표시한다.
MAIN_TABS = ("차트", "알람", "추세·관찰")
ACTIVE_TAB_KEY = "main_active_tab"

# 게이트 문맥 라벨 — LW 렌더 함수의 필수 인자(main 8cdd4e5 원칙 승계). 공급원은 main 에서 체리픽한
# 정의 파일(analysis/wave_align_gate_forward 등)을 display/lw_gate_context 가 import 만 해서 라이브 계산한다.


def gate_context_for(symbol: str, interval: str) -> str:
    """LW 차트에 병기할 상위 게이트 상태 라벨 (F2-b, 마지막 닫힌 봉 asof)."""
    return gate_label(symbol, interval)


def macd_panel_default(interval: str) -> bool:
    """'MACD 패널' 토글 기본값 — 15m 만 꺼짐, 나머지 켬."""
    return interval not in MACD_PANEL_DEFAULT_OFF_INTERVALS


def open_guidance_chart(interval: str) -> None:
    """버튼 콜백에서 다음 실행 전에 사이드바와 선택 탭을 맞춘다."""
    st.session_state[INTERVAL_KEY] = interval
    st.session_state[ACTIVE_TAB_KEY] = "차트"


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


def load_error_message(symbol: str, interval: str, reason: Optional[str]) -> str:
    """적재 실패 오류 한 줄 — 원인(HTTP 상태 코드·시도한 주소)이 있으면 덧붙인다."""
    base = f"{symbol} {interval} 데이터를 불러오지 못했습니다."
    return f"{base} 원인: {reason}" if reason else base


def render_refresh_button() -> "st.delta_generator.DeltaGenerator":
    """사이드바 상단: 새로고침 버튼 + 신선도 캡션 자리(적재 뒤 main 이 채움) + 상태 초기화 고지."""
    if st.sidebar.button(REFRESH_BUTTON_LABEL, help="OHLCV 캐시를 비우고 최신 봉까지 다시 받습니다. 상위 게이트는 별도 캐시로 최대 15분간 유지됩니다."):
        clear_klines_cache()
    slot = st.sidebar.empty()
    st.sidebar.caption(REFRESH_RESET_NOTE)
    return slot


def render_sidebar() -> dict:
    """전역 필터만 사이드바에 둔다(본문은 메인 영역)."""
    freshness_slot = render_refresh_button()
    st.sidebar.header("대상")
    symbol = st.sidebar.selectbox("심볼", options=SUPPORTED_SYMBOLS, index=0, key=SYMBOL_KEY)
    interval = st.sidebar.selectbox(
        "타임프레임",
        options=TIMEFRAMES,
        index=TIMEFRAMES.index(DEFAULT_INTERVAL) if DEFAULT_INTERVAL in TIMEFRAMES else 0,
        key=INTERVAL_KEY,
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
    data_url_slot = st.sidebar.empty()   # 그 아래 한 줄: 현재 데이터 주소(적재 뒤 main 이 채움 — 대체 전환 반영)

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
        "data_url_slot": data_url_slot,
    }


def main():
    st.set_page_config(layout="wide", page_title="WaveEnergyHelper — 알람")
    cfg = render_sidebar()
    symbol, interval = cfg["symbol"], cfg["interval"]

    # 저장된 추세·관찰 설명은 선택한 차트의 데이터 적재와 독립적으로 연다.
    tab_chart, tab_alarm, tab_observation = st.tabs(MAIN_TABS, key=ACTIVE_TAB_KEY, on_change="rerun")
    if tab_observation.open:
        with tab_observation:
            render_observation_tab(symbol, on_open_chart=open_guidance_chart)
        cfg["data_url_slot"].caption(data_source_line())
        return

    with st.spinner(f"{symbol} {interval} 적재 중..."):
        df = load_frame(symbol, interval, with_macd=cfg["show_macd"])

    cfg["data_url_slot"].caption(data_source_line())
    if df is None or df.empty:
        with (tab_alarm if tab_alarm.open else tab_chart):
            st.error(load_error_message(symbol, interval, last_fetch_error(symbol, get_fetch_interval(interval))))
            if tab_alarm.open:
                render_tf_radar_section(symbol)
                render_basis_radar_section(symbol, on_open_chart=open_guidance_chart, show_observation=False)
            st.info("큰 추세와 관찰 설명은 ‘추세·관찰’ 탭에서 확인할 수 있습니다.")
        return
    cfg["freshness_slot"].caption(
        data_freshness_caption(last_fetch_at(symbol, get_fetch_interval(interval)), df.index[-1])
    )
    # 수신 실패로 저장본(data/cache)을 그리는 중이면 경고 한 줄 — 표시 전용(판정·알람 입력 불변, SPEC §12).
    stale = stale_caption(symbol, get_fetch_interval(interval))
    if stale:
        st.warning(stale)

    # 차트에서는 현재 TF 추적을 계산하고 전 TF 레이더는 알람 조회에서 실행한다.
    if tab_alarm.open:
        with tab_alarm:
            # TF 레이더 — 어느 TF에서 전투(레벨 이탈 에피소드)가 벌어지는지 교차 TF 요약 (표시 전용, SPEC §9).
            tf_radar_view = render_tf_radar_section(symbol)
            # 기준 TF 레이더 — 대파동 쌍바닥/쌍봉 후 60MA 전환 관찰이 열린 TF (표시 전용, SPEC §10).
            basis_radar_view = render_basis_radar_section(symbol, on_open_chart=open_guidance_chart, show_observation=False)
            alarm_view = render_alarm_panel(
                df, symbol, interval,
                history_bars=cfg["history_bars"],
                include_candidates=cfg["include_candidates"],
                layers=cfg["layers"] or None,
            )
            # 60MA 전환 추적 (미검증) — 별도 섹션. 검출은 tracking의 공용 계산을 캐시해 재사용.
            # 반환된 후보 표의 '대기 중' 저점·기준선을 LW 가격 pane 에 함께 그린다(알람 푸시 대상 아님). 기울기 목록은 복사용 텍스트로.
            tracker_frame, slope_rows = render_tracker_section(df, symbol, interval)
            # 60MA 하방 전환 추적 (미검증) — 상승 쪽의 거울상(대파동 쌍봉 → 20봉 안 60MA 하방 전환). 현물 보유 시 참고용 관측.
            # 차트 가격선·알람 푸시 연동 없음(표시 전용).
            down_frame = render_down_tracker_section(df, symbol, interval)
            # 추세 구조 추적 (미검증) — 고점·저점 연쇄(파동 번호 없음). 스윙 마커를 LW 가격 pane 에 함께 그린다.
            structure_result = render_structure_section(df, symbol, interval)
            # 전체 복사용 텍스트 (탭 맨 아래, 접힘) — 위 섹션들이 화면에 그린 값(반환값)만 마크다운 텍스트로 옮긴다(재계산 없음).
            render_copy_expander(build_copy_text(
                symbol, interval, tf_radar=tf_radar_view, basis_radar=basis_radar_view, alarm=alarm_view,
                tracker=tracker_frame, slope_rows=slope_rows, down=down_frame, structure=structure_result,
            ))

    if tab_chart.open:
        with tab_chart:
            tracker_frame = upward_candidates(df)
            down_frame = downward_candidates(df)
            structure_result = structure_analysis(df)
            # gate_context 는 필수 인자. struct_reference 는 적재된 LTF 프레임으로 라이브 계산
            # (미검출·퇴화 시 None → "기준선 없음" 폴백).
            render_lw_chart(
                df, symbol, interval, gate_context_for(symbol, interval),
                chart_height=cfg["chart_height"], struct_reference=struct_reference(df, symbol, interval),
                show_stochastic=cfg["show_stoch"], show_macd=cfg["show_macd"], show_rsi=cfg["show_rsi"],
                tracker_lines=tracker_reference_lines(tracker_frame),
                structure_markers=structure_markers(structure_result),
                down_tracker_lines=down_tracker_reference_lines(down_frame),   # 하방 추적 대기 후보 패턴 고점(구분 색, 표시 전용)
            )


if __name__ == "__main__":
    main()
