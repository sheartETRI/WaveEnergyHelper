"""차트 색 토큰 (표시 계층 전용). 값 조정은 여기 한 줄로 끝나게 한다 — 빌더는 참조만.

MACD 히스토그램 4색 규칙 (기준: 직전 봉 대비 hist 증감, 부호가 1차 · 증감이 2차):
    hist ≥ 0 & hist > prev → pos_rising  (진한 적색)
    hist ≥ 0 & hist ≤ prev → pos_falling (옅은 적색 — 같은 색상, 명도만 낮춤)
    hist < 0 & hist < prev → neg_falling (진한 청색)
    hist < 0 & hist ≥ prev → neg_rising  (옅은 청색, "하늘색")
    첫 봉(prev 결측) → 부호의 진한 색.
진한 색은 기존 MACD 히스토그램 토큰(#FF4D4D / #2F6BFF)을 그대로 쓴다.
"""

MACD_HIST_COLORS = {
    "pos_rising": "#FF4D4D",    # 진한 적색 — 기존 상승색 토큰
    "pos_falling": "#F7B6B6",   # 옅은 적색
    "neg_falling": "#2F6BFF",   # 진한 청색 — 기존 하락색 토큰
    "neg_rising": "#AFC6FF",    # 옅은 청색 (하늘색)
}

# 과매수·과매도 영역 음영 — plotly_builder 의 add_masked_fill_segments 호출값 그대로 (색·투명도).
# 스토캐: 각 층 K 가 20 아래 / 80 위인 구간을 임계선과 K 사이로 채움. RSI: 30 아래 / 70 위.
ZONE_FILL_COLORS = {
    "stoch_overbought": "rgba(255, 0, 0, 0.22)",
    "stoch_oversold": "rgba(0, 0, 255, 0.22)",
    "rsi_overbought": "rgba(255, 0, 0, 0.35)",
    "rsi_oversold": "rgba(0, 0, 255, 0.35)",
}

# --- 공통 색·창 토큰 (LW·Plotly 두 빌더가 함께 참조) ---
# 원래 charts/plotly_builder.py 에 있던 값을 그대로 옮겼다(값 변경 없음). main 의 기본 경로가 LW 로
# 넘어간 뒤 lw_builder 가 plotly_builder 를 import 하지 않도록 이곳이 단일 공급원이 된다.
COLOR_BULL = "#ff0000"          # 한국 관례: 상승 적
COLOR_BEAR = "#0000ff"          # 하락 청
TV_BACKGROUND = "#ffffff"
TV_TEXT = "#191c24"
TV_GRID = "rgba(42, 46, 57, 0.12)"
RECENT_WINDOW = 150             # 초기 표시 창(봉 수)

# 차트 전체 높이(px): Streamlit 은 뷰포트 높이를 읽지 못하므로 사이드바 선택식.
CHART_HEIGHT_OPTIONS = (600, 800, 1000, 1200)
DEFAULT_CHART_HEIGHT = 1000

# 스토캐 참조선: 레이어당 20/80 두 줄만.
STOCH_GUIDES = (20, 80)

# MACD 알람 이벤트 마커 — 스토캐 DB/DT(원, 초록/빨강)·TB/TT(마름모) 관례를 그대로 잇는다.
# (라벨, 마커 모양, 색, 텍스트 위치). x 는 확정 봉(교차 봉 +1, 알람 발화 시점) — 교차 봉에
# 찍으면 사후에 마커가 생기는 표시가 된다. y 는 확정 봉의 macd 값.
from analysis.alarm_signals import (  # noqa: E402  (표시 토큰의 키만 빌린다 — 검출 로직 무접촉)
    KIND_MACD_DEAD,
    KIND_MACD_GOLDEN,
    KIND_MACD_ZERO_DOWN,
    KIND_MACD_ZERO_UP,
)

MACD_EVENT_STYLE = {
    KIND_MACD_GOLDEN: ("GC", "circle", "#0B8F45", "top center"),
    KIND_MACD_DEAD: ("DC", "circle", "#C62828", "bottom center"),
    KIND_MACD_ZERO_UP: ("0↑", "diamond", "#1565C0", "top center"),
    KIND_MACD_ZERO_DOWN: ("0↓", "diamond", "#AD1457", "bottom center"),
}
