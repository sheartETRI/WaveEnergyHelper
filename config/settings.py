# config/settings.py

# --- Binance API Settings ---
BINANCE_BASE_URL = "https://api.binance.com/api/v3/klines"
SUPPORTED_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "USDT.D",
    "BTC.D",
    "ETH.D",
]
TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "3h", "4h", "6h", "8h", "12h",
    "1d", "2d", "3d", "4d",
    "1w", "2w",
    "1M"
]

# 커스텀 인터벌: {표시 인터벌: fetch할 베이스 인터벌}
# 바이낸스가 네이티브로 주지 않는 인터벌을 베이스 인터벌에서 리샘플한다.
CUSTOM_INTERVAL_BASE = {
    "3h": "1h",
    "2d": "1d",
    "4d": "1d",
    "2w": "1d",
}
CUSTOM_INTERVALS = list(CUSTOM_INTERVAL_BASE)  # 하위 호환 유지

# --- Moving Average Settings ---
# MA_PERIODS: 표시·계산용 전체 이평 (40·80은 사용자가 보조로 추가한 표시 전용 보조선).
MA_PERIODS = [5, 10, 20, 40, 60, 80, 120, 240]

# CORE_MA_PERIODS: 판정(공식)용 이평 체계 — 책의 6개. 40·80은 표시 전용이라 제외한다.
# 앞으로 모든 공식 판정 코드는 이 목록만 사용한다 (정배열/역배열, §6 공식 등).
CORE_MA_PERIODS = [5, 10, 20, 60, 120, 240]

MA_COLORS = {
    5:   "#3B3F4C",  # Dark Gray
    10:  "#FFA000",  # Orange
    20:  "#FF5252",  # Red
    40:  "#FF5252",  # Red
    60:  "#3867F2",  # Blue
    80:  "#3867F2",  # Blue
    120: "#4CAF50",  # Green
    240: "#B0B4BE",  # Light Gray
    480: "#7ED6DF",  # Light Blue
    960: "#C58AD9",  # Purple
}

MA_LINE_WIDTHS = {
    5:   1.0,
    10:  1.0,
    20:  1.2,
    40:  1.2,
    60:  1.4,
    80:  1.4,
    120: 1.6,
    240: 1.8,
    480: 1.8,
    960: 1.8,
}

# --- Stochastic Settings ---
STOCH_LAYERS = [
    {"name": "Top", "label": "(20,10,10)", "k_len": 20, "k_smooth": 10, "d_len": 10, "k_color": "#00FFFF", "d_color": "#000000", "offset": 220.0},
    {"name": "Mid", "label": "(10,5,5)",  "k_len": 10, "k_smooth": 5,  "d_len": 5,  "k_color": "#800080", "d_color": "#000000", "offset": 110.0},
    {"name": "Bot", "label": "(5,3,3)",   "k_len": 5,  "k_smooth": 3,  "d_len": 3,  "k_color": "#FF0000", "d_color": "#000000", "offset": 0.0},
]
STOCH_BAND = 100.0
STOCH_GAP = 10.0
STOCH_MAX_Y = STOCH_BAND * 3 + STOCH_GAP * 2
STOCH_PIVOT_PARAMS = {
    "lookback": 2,
    "middle_zone": 50.0,
    "min_gap": 4,
    "min_delta": 4.0,
}

# --- MACD Settings ---
MACD_PARAMS = {
    "fast": 12,
    "slow": 26,
    "signal": 9
}

# --- RSI Settings ---
RSI_PARAMS = {
    "length": 14,
    "overbought": 70,
    "oversold": 30,
    "midline": 50,
    "smoothing_length": 2,
    "smoothing_type": "SMA"
}
RSI_PIVOT_PARAMS = {
    "lookback": 2,
    "middle_zone": 50.0,
    "min_gap": 4,
    "min_delta": 4.0,
}

# --- Wave Energy (파동에너지) Settings ---
# 확정 규칙은 코드 흐름에서 강제되며, 아래 값 중 조정 가능한 것만 기본값으로 둔다.
WAVE_ENERGY_PARAMS = {
    "trend_interval": "1d",        # 확정 규칙: 추세 기준은 항상 일봉
    "trend_ma": 60,                # 확정 규칙: 60MA
    "trend_slope_lookback": 5,     # 기울기 판정 봉 수 (조정 가능)
    "trend_flat_band_pct": 0.15,   # 기울기 ±0.15% 이내면 횡보 (조정 가능)
    "oversold": 20.0,
    "overbought": 80.0,
    "db_recent_bars": 12,          # 최근 N봉 이내 패턴만 유효 (조정 가능)
    # 변곡점 전환(§6-④⑤)용 윈도. 복합 패턴(쌍봉+쓰리봉 등)은 구성 신호가 시차를 두고
    # 확정되므로 단일 패턴보다 더 긴 윈도가 필요하다는 가정 하에 db_recent_bars의 2배로 둔다.
    "transition_recent_bars": 24,
    # MA 원자 변곡 공식(F6-4c-a/b, F6-5c-a/b) 전용 윈도 (파동-파동은 transition_recent_bars 유지).
    "transition_recent_bars_ma": 96,
}

# 상위 프레임 매핑. "1d" -> "4d"만 확정 규칙, 나머지는 ×4/×6 근사 추정값.
# 이 맵에 없는 프레임은 ×4(존재 시) → ×6(존재 시) 순으로 TIMEFRAMES에서 해석한다(명시 맵 우선).
UPPER_FRAME_MAP = {
    "15m": "1h", "1h": "4h", "4h": "1d",
    "1d": "4d",
    "4d": "2w", "2w": "1M",
}

# 파동 역할 -> STOCH_LAYERS의 label 매핑.
WAVE_LAYER_ROLES = {"large": "(20,10,10)", "mid": "(10,5,5)", "small": "(5,3,3)"}

# --- MA Pattern (이평선 쌍바닥/쌍봉) Settings ---
# 이평선 시계열 자체의 W/M 패턴 검출 파라미터. 가격 스케일이므로 스케일 프리로 동작한다.
MA_PATTERN_PARAMS = {
    "lookback": 3,           # 피봇(중심 극값) 판정 시 좌우로 볼 봉 수
    "min_gap": 3,            # 같은 종류 피봇 사이 최소 간격(봉)
    "rel_tolerance": 0.02,   # 극값 허용오차 = rel_tolerance × (윈도우 max-min). 절대값 아님
    "decline_lookback": 5,   # [F3] 첫 바닥 이전 '하락하던 이평' 판정용 기울기 봉 수
}

# 변곡 hit 이격도 유형 주석(표기 전용, 게이트 아님).
DISPERSION_TYPE_PARAMS = {
    "compress_pct": 25.0,   # pct ≤ 25 → 응축형
    "stretch_pct": 75.0,    # pct ≥ 75 → 과이격형
}

# --- AI 해설 (cursor_llm_narration.md) ---
# OpenAI 호환 HTTP 단일 경로 — 프로바이더 교체는 base_url·model·api_key_env 값만 변경.
# 예: SGLang 로컬 Qwen → base_url="http://127.0.0.1:30000/v1", model="Qwen/...", api_key_env="OPENAI_API_KEY"
# Gemini 무료 티어: 입력이 Google 모델 개선에 사용될 수 있음 (ai.google.dev 약관).
# 공식 OpenAI 호환 엔드포인트: https://ai.google.dev/gemini-api/docs/openai
#
# enabled (마스터): False → 사이드바 "AI 해설" 체크박스 숨김, 해설·LLM·캐시 경로 전부 미진입.
# enabled True → 체크박스 표시(기본 해제). 사용자가 체크할 때만 generate_narration 호출(옵트인).
NARRATION_CONFIG = {
    "enabled": True,
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "model": "gemini-2.5-flash",
    "api_key_env": "GEMINI_API_KEY",
    "temperature": 0.0,
    # gemini-2.5-flash: 내부 reasoning 토큰이 max_tokens 예산을 함께 소비한다.
    # 600 이하이면 본문이 잘리거나 빈 응답 → 검증 실패 → 조용한 폴백 반복 위험.
    "max_tokens": 2000,
    "timeout_sec": 20,
}

NARRATION_DISCLAIMER = (
    "해설 생성에 외부 AI(Gemini 무료 티어)가 사용되며 "
    "입력 데이터가 제공사 정책에 따라 활용될 수 있습니다"
)
NARRATION_RATE_LIMIT_CAPTION = "한도 도달 — 기본 요약 표시"
