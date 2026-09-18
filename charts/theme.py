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
