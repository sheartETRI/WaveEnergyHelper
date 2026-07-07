"""기법0 추세 레이어 회귀 테스트 (6차 위임 C → 7차 위임 A 스펙 교정) — 관측 전용.

스펙 §2 (docs/기법0_추세레이어_동결스펙.md) 원문 기준:
- slope(MA,N) = sign(MA[t]−MA[t−N]), N=TREND_SLOPE_N=5. flat 밴드 없음(순수 부호).
- T0 slope(60)<0 / T3 slope(60)>0 / T4 MA60>MA120 & slope(120)>0(=완연상승) /
  T2 계단식 GC(MA10×MA20 → MA20×MA60) / T1 급3(MA10)쌍바닥 + 60MA 하락기울기 약화.
- 스토캐 4층(40,20,20)은 관측 전용 — 엔진 STOCH_LAYERS/ALL_SUFFIXES에 절대 들어가지 않는다.
- bottom_width = 두 바닥 피봇 간 봉수. MACD 쌍봉 = MACD선 LH 단독.
- 전부 관측·저널·표시 전용 — 캠페인 필터/승격에 사용하지 않는다.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_state_machine import ALL_SUFFIXES
from analysis.trend_layer import (
    TREND_STOCH_SUFFIX,
    add_macd_line_patterns,
    add_trend_stoch_layer,
    ma_slope,
    slope_sign,
    stepwise_gc_at,
    trend_state_at,
)
from config.settings import STOCH_LAYERS


def test_engine_invariant_4th_layer_not_in_engine():
    # ★ 4층은 엔진 소비 목록에 없어야 한다(상태 기계 무영향).
    assert TREND_STOCH_SUFFIX == "(40,20,20)"
    assert TREND_STOCH_SUFFIX not in ALL_SUFFIXES
    assert TREND_STOCH_SUFFIX not in [layer["label"] for layer in STOCH_LAYERS]


def _df(cols: dict):
    n = len(next(iter(cols.values())))
    idx = pd.date_range("2020-01-01", periods=n, freq="1D")
    return pd.DataFrame(cols, index=idx)


# ---------------------------------------------------------------- slope (스펙 §2 부호)
def test_slope_sign_pure_sign():
    # 스펙 §2: 부호만. 기본 flat_pct=0.0 → 아주 작은 양수도 up, 아주 작은 음수도 down.
    assert slope_sign(0.02) == "up"
    assert slope_sign(-0.02) == "down"
    assert slope_sign(0.0005) == "up"     # PHASE6 즉흥본에선 flat이었으나 스펙은 부호만 → up
    assert slope_sign(-0.0005) == "down"
    assert slope_sign(0.0) == "flat"      # 정확한 tie만 flat
    assert slope_sign(None) == "flat"


def test_ma_slope_normalized_sign_preserving():
    df = _df({"MA60": [100, 100, 100, 100, 100, 110], "MA120": [1] * 6})  # 100→110 over 5봉
    s = ma_slope(df, 5, 60, n=5)
    assert abs(s - 0.10) < 1e-9   # (110-100)/100, 부호 보존


# ---------------------------------------------------------------- 상태 분류 (스펙 §2)
def test_T0_downtrend_slope_only():
    # T0 = slope(60)<0. 배열(MA60 vs MA120) 무관 — MA60>MA120 이라도 slope60<0 이면 T0.
    df = _df({"MA60": [120 - i for i in range(20)], "MA120": [90] * 20})  # MA60>MA120 이지만 하락
    # slope120=flat(고정) → T4 아님. slope60<0 → T0.
    assert trend_state_at(df, 19) == "T0"


def test_T3_uptrend_slope_only():
    # T3 = slope(60)>0. MA60<MA120 이라도 slope60>0 이면 T3 (PHASE6 즉흥본은 배열 요구 → 교정).
    df = _df({"MA60": [80 + i for i in range(20)], "MA120": [200] * 20})  # 상승 중이나 아직 MA60<MA120
    assert trend_state_at(df, 19) == "T3"


def test_T4_strong_uptrend():
    # T4 = MA60>MA120 & slope(120)>0 (완연한 상승). 슬로프 둘 다 상승·정배열.
    df = _df({"MA60": [100 + 2 * i for i in range(20)], "MA120": [90 + i for i in range(20)]})
    assert trend_state_at(df, 19) == "T4"


def test_T2_stepwise_gc():
    # 스펙 §2 T2: ②MA20×MA60 상향교차 봉 & ①MA10>MA20 성립. slope60은 아직 미상승.
    # MA60 평평(하락도 상승도 아닌 tie는 flat) → T3 아님. MA20이 MA60 상향돌파하는 봉.
    ma10 = [100, 101, 102, 103, 104, 107, 108]
    ma20 = [95, 96, 97, 98, 99, 100, 106]    # 마지막 봉에서 MA60(105) 상향 돌파, MA10>MA20 유지
    ma60 = [105] * 7
    ma120 = [130] * 7
    df = _df({"MA10": ma10, "MA20": ma20, "MA60": ma60, "MA120": ma120})
    assert stepwise_gc_at(df, 6) is True
    assert trend_state_at(df, 6) == "T2"
    assert stepwise_gc_at(df, 5) is False


def test_T2_requires_ma10_above_ma20():
    # ① 미성립(MA10<MA20)이면 ②교차만으로 T2 아님.
    df = _df({
        "MA10": [90] * 7,                       # MA10 < MA20 (① 불성립)
        "MA20": [95, 96, 97, 98, 99, 100, 111],
        "MA60": [105] * 7, "MA120": [130] * 7,
    })
    assert stepwise_gc_at(df, 6) is False


def test_T1_bottoming_requires_ma10_db_and_weakening():
    # T1 = slope60<0 & 급3(MA10)쌍바닥 최근 확정 & 하락기울기 약화.
    # 하락하되 기울기 완만해지는 MA60(감쇠) + ma10_db 확정 봉 주입.
    vals = [100, 96, 93, 91, 90.0, 89.5, 89.2, 89.0, 88.9, 88.85, 88.83, 88.82]
    df = _df({"MA60": vals, "MA120": [130] * len(vals), "MA10": vals, "MA20": vals})
    df["ma10_db"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[10, df.columns.get_loc("ma10_db")] = 88.83   # 최근봉 쌍바닥 확정
    assert trend_state_at(df, 11) == "T1"
    # ma10_db 없으면(관측창 밖) T0.
    df2 = df.copy()
    df2["ma10_db"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    assert trend_state_at(df2, 11) == "T0"


# ---------------------------------------------------------------- 관측 계기 컬럼
def _ohlc(n=120):
    idx = pd.date_range("2020-01-01", periods=n, freq="1h")
    import math
    close = [100 + 10 * math.sin(i / 6.0) for i in range(n)]
    return pd.DataFrame(
        {"open": close, "high": [c + 1 for c in close], "low": [c - 1 for c in close],
         "close": close, "volume": 1.0}, index=idx,
    )


def test_add_trend_stoch_layer_columns():
    df = add_trend_stoch_layer(_ohlc())
    sfx = TREND_STOCH_SUFFIX
    for c in (f"stoch_k_{sfx}", f"stoch_d_{sfx}", f"stoch_db_{sfx}",
              f"stoch_dt_{sfx}", f"stoch_tb_{sfx}", f"stoch_tt_{sfx}"):
        assert c in df.columns


def test_add_macd_line_patterns_kind_column():
    df = _ohlc()
    df["macd"] = df["close"] - df["close"].rolling(10, min_periods=1).mean()
    df = add_macd_line_patterns(df)
    # 스펙 LH 필터를 위해 kind 컬럼이 있어야 한다.
    assert "macd_pivot_low" in df.columns and "macd_dt" in df.columns
    assert "macd_dt_kind" in df.columns


if __name__ == "__main__":
    test_engine_invariant_4th_layer_not_in_engine()
    test_slope_sign_pure_sign()
    test_ma_slope_normalized_sign_preserving()
    test_T0_downtrend_slope_only()
    test_T3_uptrend_slope_only()
    test_T4_strong_uptrend()
    test_T2_stepwise_gc()
    test_T2_requires_ma10_above_ma20()
    test_T1_bottoming_requires_ma10_db_and_weakening()
    test_add_trend_stoch_layer_columns()
    test_add_macd_line_patterns_kind_column()
    print("ALL TREND LAYER TESTS PASSED")
