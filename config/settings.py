# config/settings.py

# --- Binance API Settings ---
BINANCE_BASE_URL = "https://api.binance.com/api/v3/klines"
# api.binance.com 이 451/403(지역 차단 — Streamlit Cloud 등 미국 리전)을 주면 같은 요청을 이 주소로 재시도한다.
# data-api.binance.vision 은 바이낸스가 공개 시장 데이터(klines 등)용으로 제공하는 동일 스키마 엔드포인트.
BINANCE_FALLBACK_URL = "https://data-api.binance.vision/api/v3/klines"
BINANCE_FALLBACK_STATUS = (451, 403)
SUPPORTED_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
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
# 스토캐 쌍바닥/쌍봉 정의 파라미터 (김박사 정의, 2026-09-22 — indicators/stochastic.py 모듈 주석 참조).
#   쌍봉: 과매수권(K ≥ overbought)에 들어간 첫 봉우리가 과매수권을 벗어난 뒤 두 번째 봉우리를 만들되,
#         두 번째 봉우리의 폭이 첫 번째보다 짧아야 한다. 쌍바닥은 대칭(K ≤ oversold).
#   width_drop: 봉우리 폭(정점 전후 대칭 폭)을 재는 높이 — 정점에서 이 값만큼 내려온 높이 위에 머문 봉 수.
#   김박사 조정 대상. 피봇(STOCH_PIVOT_PARAMS)은 쌍바닥/쌍봉 검출에 더는 쓰이지 않고 쓰리바닥·기록용으로만 남는다.
STOCH_DOUBLE_PARAMS = {
    "overbought": 80.0,
    "oversold": 20.0,
    "width_drop": 10.0,
}

# --- 알람 Pushbullet 푸시 (scripts/push_alarms.py) — 김박사 조정 대상 ---
# 감시 목록: 심볼 × TF 전부 순회. TF 는 Binance 네이티브 간격만(커스텀 2d·4d·2w 는 닫힌 봉 판정 미지원).
PUSH_WATCHLIST = {
    "symbols": ["BTCUSDT"],
    "intervals": ["1h", "2h", "4h", "6h", "1d"],
}
PUSH_PARAMS = {
    "include_candidates": False,          # 후보(미확정) 신호 전송 여부 — 기본 확정만
    "lookback_bars": 3,                   # 전송 이력이 없는 첫 실행에서 볼 최근 닫힌 봉 수(과거 알람 폭주 방지)
    "token_file": "token.txt",            # 저장소 홈, Pushbullet Access Token 한 줄 (.gitignore)
    "state_file": "pushbullet_state.json",  # 전송 이력(중복 방지·따라잡기), 저장소 홈 (.gitignore)
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

# --- v2 array_context (이평선 배열 맥락) 관측 태그 파라미터 (4차 위임 C) ---
# 게이트 아님 — 저널 컬럼 관측 전용. 김박사 조정 대상(초기값 보수적).
# 규칙 형식화: "정배열이다가 모일 때 쌍봉 / 역배열이다가 모일 때 쌍바닥"이 정방향 맥락.
ARRAY_CONTEXT_PARAMS = {
    "core_ma": [5, 10, 20, 60],      # 배열 판정 대상 CORE_MA (순서=정배열 기준)
    "converge_window": 10,           # 스프레드 축소 추세 판정 창(봉)
    "converge_spread_max": 0.03,     # 정규화 스프레드(max-min)/close 상한 — 이하이면 '모임' 후보
    "converge_shrink_ratio": 0.8,    # 현재 스프레드 ≤ (window 전 스프레드 × 이 값) 이면 축소 추세
}

# --- v2 기법0 추세 레이어 관측 계기 파라미터 (6차 위임 C → 7차 위임 A 스펙 교정) ---
# ★ 관측·표시·저널 전용 — 게이트·필터·승격·판정 사용 금지. v3 게이트는 이 위임에서 정하지 않는다.
# 7차 위임 A: 동결 스펙(docs/기법0_추세레이어_동결스펙.md) 확보 → PHASE6 즉흥 정의를 스펙 우선 교정.
#   · slope = 부호만(스펙 §2) → slope_flat_pct=0.0 (순수 부호, flat 밴드는 스펙 외였음).
#   · TREND_SLOPE_N=5 는 스펙 초기값 제안과 일치(김박사 조정 대상).
TREND_LAYER_PARAMS = {
    # 스토캐 4층 (40,20,20) — 엔진 STOCH_LAYERS에 넣지 않는다(관측 전용 별도 suffix). 스펙 §1 상응 4층.
    "stoch_layer": {"label": "(40,20,20)", "k_len": 40, "k_smooth": 20, "d_len": 20},
    "TREND_SLOPE_N": 5,        # slope 판정 봉수 (스펙 §2, MA60/MA120 공통)
    "slope_flat_pct": 0.0,     # 스펙 §2: slope는 부호만. 0.0=순수 부호(정확한 tie만 flat).
    "trend_ma_fast": 60,       # 추세 기준 MA (스펙 §0: 추세의 기준은 60MA)
    "trend_ma_slow": 120,      # T4 완연상승 판정 MA (스펙 §2: MA60×MA120 GC + slope120>0)
}

# --- v2 캔들 패턴 검출 + 상응 합치(concordance) 파라미터 (4차 위임 E) ---
# 관측 전용 — 게이트·필터·승격 소스 아님. 김박사 조정 대상.
# [F1] 상응 구조: MA10↔대파동, MA5↔중파동, 캔들↔소파동. 급 내 가격계>오실레이터.
CANDLE_PATTERN_PARAMS = {
    # 도지(시가=종가)를 음/양 교대의 '파괴'로 간주(보수적 기본값). False면 도지는 방향 없는
    # 통과로 처리하지 않고 여전히 교대를 깨뜨리지 않는 완화 해석 — 초기값 True 권장.
    "DOJI_BREAKS_ALTERNATION": True,
}
CONCORDANCE_PARAMS = {
    "window_bars": 12,   # 상응 스토캐 층에서 같은 방향 패턴을 탐색하는 창(봉). WAVE db_recent_bars와 정합.
    "min_cell_n": 20,    # 교차표(맥락×합치) 셀 판단 보류 임계 — n<이 값이면 '판단 보류' 표기.
}

# --- v2 캠페인 채점 파라미터 ---
# 채점 단위 = 캠페인(T1: ENTRY-1→EXIT-1, T2: ENTRY-2→S7). 합산 = (1+T1)(1+T2)-1 − 수수료.
# fee_per_fill: 체결 1회당 수수료(0.1% 가정). §10 미결 — 김박사 실계좌 기준 조정 대상.
V2_CAMPAIGN_PARAMS = {
    "fee_per_fill": 0.001,
}

# --- v2 관측 계기판 파라미터 (9차 위임 — 표시·저널 전용, 판정/게이트/추천 아님) ---
# ★ 관측 전용. slope 계기판·월봉 대파동 위치·전조 채널 디스패처 표시 상수.
OBSERVATORY_PARAMS = {
    # C: |정규화 slope| 히스토리 하위 pctile 이하 = 평탄(횡보). 8차 검증 부가기록 정의 재사용.
    "slope_flat_pctile": 0.20,
    "slope_dash_tfs": ["1d", "4d"],   # C 병렬 표시 대상 TF (각 60MA slope)
    # B: 월봉 대파동(스토캐 4층 40,20,20) 위치 구간 경계. WAVE oversold/overbought와 정합.
    "stoch_bottom_zone": 20.0,
    "stoch_top_zone": 80.0,
    "monthly_tf": "1M",
    # 관측 저널 누적 경로(표시 시점 상태 기록).
    "journal_path": "validation/observatory_journal.csv",
}

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

# 스윕 재탈환 검출기 (analysis/sweep_reclaim.py) — 기록 전용 관측.
#   레벨 = Donchian(donchian_n) 경계(당봉 제외, shift 1). 이탈 후 종가 기준 체류가
#   reclaim_max_bars 초과면 진짜 이탈(붕괴/돌파 지속), 이내 재탈환 + t+1 유지면 스윕.
#   docs/SPEC_SWEEP_RECLAIM.md 동결 스펙 — 값 변경은 문서 개정으로만.
SWEEP_RECLAIM_PARAMS = {
    "donchian_n": 60,
    "touch_tol_pct": 0.005,
    "reclaim_max_bars": 3,
    "vol_ma_n": 20,
}
