"""키 차트(기준 타임프레임) 선정 가설 검증 — v0 동결 파라미터.

명세 §2-2: 이 파일의 값은 **실행 전에 동결**한다. 결과를 본 뒤 바꾸지 않는다.
바꿔야 한다면 params_v1.py를 새로 만들고 v0 결과도 보존한다.

§4.3의 값은 그대로 옮겼고, 명세가 수치를 지정하지 않은 실행 설계값(분석 창, 지평,
시드 수, 블록 길이 등)은 아래 "실행 설계 동결값"에 함께 박아 동일한 동결 규칙을 적용한다.
"""
from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------- §4.3 동결 상수
DB_RECENT_BARS = 12     # WAVE_ENERGY_PARAMS["db_recent_bars"]와 동일값
SYM_SCALE = 20.0        # 스토캐스틱 0~100 스케일
GAP_CENTER = 20         # (20,10,10)의 k_len
GAP_WIDTH = 15
BREAK_SCALE = 15.0
OVERSOLD = 20.0         # WAVE_ENERGY_PARAMS와 동일
OVERBOUGHT = 80.0
EXTREME_SCALE = 20.0
MA_WARMUP_BARS = 240

# ---------------------------------------------------------------- 실행 설계 동결값
# §4.2가 정의하지 않은 부분을 v0에서 확정한 값들. 전부 사전 등록(결과 관측 전 확정)이다.

# c5(배열 강도). v0 게이트는 U3/D3만 통과시키므로 상수 1.0 (§4.2 명시).
# §7 민감도(G1을 U2/D2까지 완화)에서만 변별력을 갖는다.
C5_FULL = 1.0     # U3 / D3
C5_PARTIAL = 0.5  # U2 / D2 — 민감도 분석 전용

# 쓰리바닥/쓰리봉에 대한 §4.2 대리지표 적용 규칙(명세는 "두 극값"만 정의 → v0 확정).
#   c1/c2: 마지막 두 극값(바닥2·바닥3 / 봉2·봉3) — 검출기 kind/delta 기준과 동일
#   c3   : 넥라인 = 극값1~극값3 사이 %K 최고(쌍바닥은 검출기 기록 컬럼 사용)
#   c4   : 세 극값 중 최저(쌍바닥 대칭)
TRIPLE_USES_LAST_TWO = True

# 같은 봉에서 쌍/쓰리 패턴이 동시 확정될 때의 우선순위(결정적, 점수 최대화 아님).
PATTERN_PRIORITY = ("db", "tb", "dt", "tt")

# 피봇 안정화 지연(봉). compute_stochastic_pivots는 lookback=2 중심창으로 피봇을 잡고
# _apply_min_gap(min_gap=4)이 나중 후보로 앞 피봇을 소급 삭제할 수 있다. 따라서 위치 p의
# 피봇 집합은 p+lookback+min_gap 봉에서야 확정된다. 확정 시점 c의 패턴은
# max(c, 마지막 극값 위치 + 이 값) 봉 마감에 '알 수 있게' 된다. §6 테스트로 검증한다.
PIVOT_STABILITY_LAG = 6   # = STOCH_PIVOT_PARAMS["lookback"](2) + ["min_gap"](4)

# 분석 창(주). 19개 프레임 전체가 공통으로 존재하는 구간으로 통일한다.
# (1m을 상장 이후 전체로 잡으면 프레임별 가용 구간이 달라져 팔 비교에 교란이 생긴다.)
PRIMARY_START = pd.Timestamp("2023-08-31")
PRIMARY_END = pd.Timestamp("2026-08-31")

# 탐색적 보조 창(§7.4 탐색적 — 유의성 주장 금지). 1h 이상 프레임만, 상장 이후 전체.
EXPLORE_START = pd.Timestamp("2017-08-17")
EXPLORE_END = PRIMARY_END
EXPLORE_MIN_FRAME_MINUTES = 60

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

# 서브 1h 프레임 수집 상한(분석 창 + 워밍업 여유). 1h 이상은 상장 이후 전체를 받는다.
SUBHOUR_WARMUP_BARS = 5000

# §7.1 벽시계 지평
HORIZONS = {"h24": pd.Timedelta("24h"), "h72": pd.Timedelta("72h"),
            "d7": pd.Timedelta("7d"), "d30": pd.Timedelta("30d")}
HORIZON_DAYS = {"h24": 1.0, "h72": 3.0, "d7": 7.0, "d30": 30.0}

# §7.4 주 결론용 사전 지정 (단 하나)
PRIMARY_COMPARISON = ("B", "C2")
PRIMARY_HORIZON = "d7"
PRIMARY_METRIC = "ret_norm"   # ATR 정규화 수익률

# 변동성 정규화: 1일봉 Wilder ATR(14) / close 를 진입 시점 as-of로 취해
#   ret_norm = ret / (atr_pct * sqrt(지평 일수))
# 프레임과 무관한 단일 척도라 팔 간 비교가 성립한다(프레임별 ATR을 쓰면 성립하지 않는다).
ATR_PERIOD = 14
ATR_FRAME = "1d"

# §5 귀무 팔 반복
NULL_SEEDS = 200
SEED_BASE = 20260831

# §7.3 블록 부트스트랩 (블록 길이 ≥ 최장 지평 30d)
BLOCK_DAYS = 90
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 12345

# §9-5 민감도
SENSITIVITY_DB_RECENT_BARS = (8, 12, 16)
