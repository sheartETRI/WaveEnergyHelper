"""기법0 추세 레이어 (v2 6차 위임 C 관측 계기 → 7차 위임 A 스펙 교정) — 관측·표시·저널 전용.

★ 게이트·필터·승격·판정에 사용 금지. trend_state로 캠페인 필터링/승격하지 않는다.
★ 엔진 무수정: 스토캐 4층(40,20,20)은 STOCH_LAYERS(엔진 소비)에 넣지 않고 별도 suffix로만
  산출한다. 상태 기계의 ALL_SUFFIXES/WAVE_LAYER_ROLES는 불변 → 전이 로직 영향 없음.

7차 위임 A — 동결 스펙(docs/기법0_추세레이어_동결스펙.md) 확보 후 PHASE6 즉흥 정의를 스펙 우선 교정.
스펙 §2 추세 상태 기계(확정 정의):
    T0 DOWNTREND : slope(60MA) < 0
    T1 BOTTOMING : 급3(MA10) 쌍바닥 확정 + 60MA 하락 기울기 약화(|slope| 축소)
    T2 TURNING   : 계단식 GC — ① MA10×MA20 GC → ② MA20×MA60 GC
    T3 UPTREND   : slope(60MA) > 0
    T4 STRONG    : MA60×MA120 GC + slope(120MA) > 0   ← 완연한 상승(스펙). PHASE6의 '천장형성' 폐기.
  slope(MA,N) = sign(MA[t] − MA[t−N]), N=TREND_SLOPE_N=5. (스펙 §2, 부호만.)

⚠ 모델링 결정(스펙 미지정 지점 — REPORT_V2_PHASE7 미결에 질문으로 명시. 임의 확정 아님):
  · 스펙은 이를 '상태 기계'(전이·파괴 트리거)로 서술하나, 저널 진입봉 1점 주석에는 상태 분류가
    필요 → 여기서는 **봉 단위 우선순위 분류기**(강도순 T4>T3>T2>T1>T0)로 실현. 순차 워크(파괴
    트리거 히스테리시스 포함) 여부는 김박사 확정 대상.
  · T1 '급3 쌍바닥 확정' 최근성 창 = WAVE_ENERGY_PARAMS.db_recent_bars(=12, 기존 상수 재사용,
    새 매직넘버 도입 회피). '약화'는 |slope60(pos)| < |slope60(pos−N)| 1창 비교로 실현.
  · T2는 ②MA20×MA60 상향교차 봉(①MA10>MA20 성립)에서만 성립하는 순간 이벤트로 실현.
  · T4는 slope60을 제약하지 않는다(스펙 문언). MA60>MA120 & slope120>0 이면 T4.
  → 위 미지정부는 B 판정(상승 T3+ vs 비상승)에 영향 없음: T0/T1/T2 경계 재조정과 무관하게
     T3 임계(slope60>0)·T4(배열+slope120)는 스펙 문언 그대로라 판정이 강건.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import (
    MA_PATTERN_PARAMS,
    STOCH_PIVOT_PARAMS,
    TREND_LAYER_PARAMS,
    WAVE_ENERGY_PARAMS,
)
from indicators.ma_patterns import _detect_series_double_top, compute_series_pivots
from indicators.stochastic import (
    compute_stochastic_pivots,
    detect_stochastic_bottom_patterns,
    detect_stochastic_top_patterns,
    detect_stochastic_triple_bottom_patterns,
    detect_stochastic_triple_top_patterns,
)

TREND_STOCH_SUFFIX = TREND_LAYER_PARAMS["stoch_layer"]["label"]   # "(40,20,20)"

# --- 스펙 §2 추세 상태 기계 (전이표 = 데이터 선언, 관측 전용) ---
# cond = 스펙 §2 원문 정의. arrange/slope 는 phase6.py 렌더 하위호환용 요약 토큰(정보성).
TREND_FLOW = [
    {"state": "T0", "label": "하락",     "cond": "slope(60)<0",
     "arrange": "—", "slope": "slope60<0"},
    {"state": "T1", "label": "바닥형성", "cond": "급3(MA10) 쌍바닥 확정 + 60MA 하락기울기 약화",
     "arrange": "급3쌍바닥", "slope": "slope60<0·약화"},
    {"state": "T2", "label": "상승전환", "cond": "계단식 GC: MA10×MA20 → MA20×MA60",
     "arrange": "MA10>MA20>MA60", "slope": "—"},
    {"state": "T3", "label": "상승",     "cond": "slope(60)>0",
     "arrange": "—", "slope": "slope60>0"},
    {"state": "T4", "label": "완연상승", "cond": "MA60×MA120 GC + slope(120)>0",
     "arrange": "MA60>MA120", "slope": "slope120>0"},
]
TREND_STATE_LABEL = {t["state"]: t["label"] for t in TREND_FLOW}
# B 판정용 그룹 (스펙: T3 이상 = 상승 상태).
UPTREND_STATES = {"T3", "T4"}
NON_UPTREND_STATES = {"T0", "T1", "T2"}


# ---------------------------------------------------------------- slope (스펙 §2)
def ma_slope(df: pd.DataFrame, pos: int, period: int, n: Optional[int] = None) -> Optional[float]:
    """MA{period}의 n봉 정규화 기울기 = (MA[t]−MA[t−n]) / |MA[t−n]|.

    스펙은 '부호'만 요구하나 정규화는 부호 보존(양수로 나눔) → 부호 동일. 크기는 T1 '약화' 비교용.
    """
    nn = TREND_LAYER_PARAMS["TREND_SLOPE_N"] if n is None else n
    col = f"MA{period}"
    if col not in df.columns or pos - nn < 0:
        return None
    cur, ref = df[col].iloc[pos], df[col].iloc[pos - nn]
    if pd.isna(cur) or pd.isna(ref) or float(ref) == 0.0:
        return None
    return (float(cur) - float(ref)) / abs(float(ref))


def slope_sign(slope: Optional[float], flat_pct: Optional[float] = None) -> str:
    """기울기 부호: up | down | flat. 스펙 §2 = 순수 부호(flat_pct 기본 0.0 → 정확한 tie만 flat)."""
    if slope is None:
        return "flat"
    thr = (TREND_LAYER_PARAMS["slope_flat_pct"] if flat_pct is None else flat_pct) / 100.0
    if slope > thr:
        return "up"
    if slope < -thr:
        return "down"
    return "flat"


# ---------------------------------------------------------------- 계단식 GC (스펙 §2 T2)
def _cross_up_at(df: pd.DataFrame, pos: int, fast_col: str, slow_col: str) -> bool:
    """fast가 slow를 이 봉에서 상향 교차(직전 fast ≤ slow, 현재 fast > slow). 봉 마감 as-of."""
    if fast_col not in df.columns or slow_col not in df.columns or pos < 1:
        return False
    f0, s0 = df[fast_col].iloc[pos], df[slow_col].iloc[pos]
    fp, sp = df[fast_col].iloc[pos - 1], df[slow_col].iloc[pos - 1]
    if any(pd.isna(x) for x in (f0, s0, fp, sp)):
        return False
    return bool(fp <= sp and f0 > s0)


def stepwise_gc_at(df: pd.DataFrame, pos: int) -> bool:
    """스펙 §2 T2 계단식 GC: ①MA10×MA20 GC → ②MA20×MA60 GC.

    봉 단위 실현: 이 봉에서 ②MA20×MA60 상향교차 성립 && ① 이미 성립(MA10>MA20 = 정배열 계단).
    (PHASE6 즉흥본은 MA60×MA120 교차였음 — 그것은 스펙상 T4. 여기서 스펙대로 교정.)
    """
    if not _cross_up_at(df, pos, "MA20", "MA60"):
        return False
    if "MA10" not in df.columns or "MA20" not in df.columns:
        return False
    m10, m20 = df["MA10"].iloc[pos], df["MA20"].iloc[pos]
    if pd.isna(m10) or pd.isna(m20):
        return False
    return bool(m10 > m20)


# ---------------------------------------------------------------- T1 보조 (스펙 §2)
def _recent_ma10_double_bottom(df: pd.DataFrame, pos: int, window: int) -> bool:
    """급3(MA10) 쌍바닥이 최근 window봉 이내에 확정되었는가. window=db_recent_bars(기존 상수)."""
    col = "ma10_db"
    if col not in df.columns:
        return False
    lo = max(0, pos - window + 1)
    return bool(df[col].iloc[lo:pos + 1].notna().any())


def _slope60_weakening(df: pd.DataFrame, pos: int) -> bool:
    """60MA 하락 기울기 약화: |slope60(pos)| < |slope60(pos−N)| (1창 비교, 스펙 '축소 추세' 실현)."""
    n = TREND_LAYER_PARAMS["TREND_SLOPE_N"]
    s_now = ma_slope(df, pos, TREND_LAYER_PARAMS["trend_ma_fast"])
    s_prev = ma_slope(df, pos - n, TREND_LAYER_PARAMS["trend_ma_fast"])
    if s_now is None or s_prev is None:
        return False
    return abs(s_now) < abs(s_prev)


# ---------------------------------------------------------------- 추세 상태 (스펙 §2)
def trend_state_at(df: pd.DataFrame, pos: int) -> Optional[str]:
    """봉 pos의 추세 상태 T0~T4 (스펙 §2). 봉 단위 우선순위 분류기(강도순 T4>T3>T2>T1>T0)."""
    fast = TREND_LAYER_PARAMS["trend_ma_fast"]     # 60
    slow = TREND_LAYER_PARAMS["trend_ma_slow"]     # 120
    fc, sc = f"MA{fast}", f"MA{slow}"
    if fc not in df.columns or sc not in df.columns or pos < 0 or pos >= len(df):
        return None
    m60, m120 = df[fc].iloc[pos], df[sc].iloc[pos]
    if pd.isna(m60):
        return None
    s60 = slope_sign(ma_slope(df, pos, fast))
    s120 = slope_sign(ma_slope(df, pos, slow))

    # T4 완연상승: MA60×MA120 GC(성립=MA60>MA120) + slope120>0. (스펙: slope60 미제약)
    if not pd.isna(m120) and m60 > m120 and s120 == "up":
        return "T4"
    # T3 상승: slope60>0
    if s60 == "up":
        return "T3"
    # T2 상승전환: 계단식 GC 봉
    if stepwise_gc_at(df, pos):
        return "T2"
    # T1 바닥형성: 급3 쌍바닥 최근 확정 + 하락기울기 약화 (하락 국면 한정)
    if s60 == "down" and _recent_ma10_double_bottom(
        df, pos, WAVE_ENERGY_PARAMS["db_recent_bars"]
    ) and _slope60_weakening(df, pos):
        return "T1"
    # T0 하락 (그 외 — slope60<0 또는 flat 잔여)
    return "T0"


def trend_state_label(state: Optional[str]) -> str:
    return TREND_STATE_LABEL.get(state, "미정") if state else "미정"


# ---------------------------------------------------------------- MACD 쌍봉 LH (스펙 §2)
def macd_double_top_lh_at(df: pd.DataFrame, pos: int) -> bool:
    """스펙 §2 MACD 쌍봉 = MACD선 고점 2개, 둘째<첫째(LH). add_macd_line_patterns 선행 필요.

    macd_dt(넥라인 하향 돌파 확정) 중 kind=='LH'만 스펙 쌍봉. HH/EQ 는 제외.
    """
    if "macd_dt" not in df.columns or pos < 0 or pos >= len(df):
        return False
    if pd.isna(df["macd_dt"].iloc[pos]):
        return False
    kcol = "macd_dt_kind"
    if kcol not in df.columns:
        return False
    return df[kcol].iloc[pos] == "LH"


# ---------------------------------------------------------------- bottom width (스펙 §2 T1)
def bottom_width(df: pd.DataFrame, period: int, pat: str, confirm_pos: int) -> Optional[int]:
    """급3 쌍바닥 폭 = 두 바닥 피봇 간 봉수(힘의 프록시, 스펙 §2 T1). 관측 전용(저널 컬럼)."""
    from analysis.pattern_scanner import _second_extreme_pos, ma_first_pivot_pos

    fp = ma_first_pivot_pos(df, period, pat, confirm_pos)
    if fp is None:
        return None
    pb = _second_extreme_pos(df, period, pat, fp, confirm_pos)
    if pb is None:
        return None
    return int(pb - fp)


# ---------------------------------------------------------------- C-1 stoch 4th layer
def add_trend_stoch_layer(df: pd.DataFrame) -> pd.DataFrame:
    """관측 전용 스토캐 4층 (40,20,20) + db/dt/tb/tt 패턴. STOCH_LAYERS 미변경(엔진 무영향)."""
    if df is None or df.empty:
        return df
    cfg = TREND_LAYER_PARAMS["stoch_layer"]
    suffix, k_len, k_smooth, d_len = cfg["label"], cfg["k_len"], cfg["k_smooth"], cfg["d_len"]

    lowest = df["low"].rolling(window=k_len, min_periods=k_len).min()
    highest = df["high"].rolling(window=k_len, min_periods=k_len).max()
    denom = highest - lowest
    fast_k = ((df["close"] - lowest) / denom.replace(0, pd.NA)) * 100.0
    fast_k = fast_k.where(denom != 0, 0.0)
    slow_k = fast_k.rolling(window=k_smooth, min_periods=k_smooth).mean()
    slow_d = slow_k.rolling(window=d_len, min_periods=d_len).mean()

    df[f"stoch_k_{suffix}"] = slow_k
    df[f"stoch_d_{suffix}"] = slow_d
    pl, ph = compute_stochastic_pivots(
        slow_k,
        lookback=STOCH_PIVOT_PARAMS["lookback"], middle_zone=STOCH_PIVOT_PARAMS["middle_zone"],
        min_gap=STOCH_PIVOT_PARAMS["min_gap"], min_delta=STOCH_PIVOT_PARAMS["min_delta"],
    )
    df[f"stoch_pivot_low_{suffix}"] = pl
    df[f"stoch_pivot_high_{suffix}"] = ph
    df = detect_stochastic_bottom_patterns(df, suffix)
    df = detect_stochastic_top_patterns(df, suffix)
    df = detect_stochastic_triple_bottom_patterns(df, suffix)
    df = detect_stochastic_triple_top_patterns(df, suffix)
    return df


# ---------------------------------------------------------------- C-3 MACD line patterns
def add_macd_line_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """MACD선 피봇 + 쌍봉(LH) 검출기 (스케일 프리 시계열 검출 재사용). 관측 전용.

    macd_dt_kind 컬럼에 LH/HH/EQ 기록 → 스펙 쌍봉(LH) 여부는 macd_double_top_lh_at 로 필터.
    """
    if df is None or df.empty or "macd" not in df.columns:
        return df
    params = MA_PATTERN_PARAMS
    pl, ph = compute_series_pivots(
        df["macd"], lookback=params["lookback"], min_gap=params["min_gap"],
        rel_tolerance=params["rel_tolerance"],
    )
    df["macd_pivot_low"] = pl
    df["macd_pivot_high"] = ph
    df = _detect_series_double_top(df, "macd", "macd_db", "macd_dt", params)
    return df


def add_trend_observation(df: pd.DataFrame) -> pd.DataFrame:
    """관측 계기 일괄 부착(스토캐 4층 + MACD선 패턴). 표시·저널용. 엔진 파이프라인과 분리."""
    df = add_trend_stoch_layer(df)
    df = add_macd_line_patterns(df)
    return df
