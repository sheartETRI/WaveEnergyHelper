"""월봉 맥락 레코드 — 사이클 위치(상태)를 월별 시계열로 기록한다 (기록 전용).

월봉은 이벤트 TF 가 아니다: Donchian 60봉 워밍업이 5년이라 이벤트 표본이 성립하지
않고, 확정 지연이 최대 2개월이며, 월봉용 파라미터 완화는 "전 TF 동일 파라미터"
동결 원칙 위반이라 하지 않는다. 대신 열람 시 이벤트(스윕·합류·니어미스)를 월봉
위상으로 층화하기 위한 조인 키를 남긴다. docs/SPEC_SWEEP_RECLAIM.md §8 동결 스펙.

기록 필드(월별): close, 대파동 %K(STOCH_LAYERS large (20,10,10) 공식 동일)와
전월 대비 방향, MA20 과 기울기(%), 직전 band_months 개월(당월 포함) 고저 밴드와
그 안의 종가 위치(%). 상태 스냅숏이라(마지막 행은 진행 중인 달일 수 있음) 확정 봉
규율은 적용하지 않는다 — 이벤트 판정에 쓰지 않는다.

순수 pandas, streamlit 무의존 — 테스트 가능. 검출기·지표 모듈 무수정
(스토캐 공식은 indicators/stochastic.py 와 동일하게 재기술, 상수는 STOCH_LAYERS
large 층에서 가져와 중복 정의를 피한다).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import MONTHLY_CONTEXT_PARAMS, STOCH_LAYERS

# 대파동 층 — label "(20,10,10)". 공식 상수의 단일 출처.
_LARGE = STOCH_LAYERS[0]

_FRAME_COLUMNS = [
    "close", "large_k", "large_k_dir", "ma20", "ma20_slope_pct",
    "band_low", "band_high", "band_pos_pct",
]


def _merged_params(params: Optional[dict]) -> dict:
    merged = dict(MONTHLY_CONTEXT_PARAMS)
    if params:
        merged.update(params)
    return merged


def _slow_k(df: pd.DataFrame) -> pd.Series:
    """대파동 slow %K — indicators/stochastic.add_stochastic_slow_layers 와 동일 공식."""
    k_len = int(_LARGE["k_len"])
    k_smooth = int(_LARGE["k_smooth"])
    lowest_low = df["low"].rolling(window=k_len, min_periods=k_len).min()
    highest_high = df["high"].rolling(window=k_len, min_periods=k_len).max()
    denominator = highest_high - lowest_low
    fast_k = ((df["close"] - lowest_low) / denominator.where(denominator != 0)) * 100.0
    fast_k = fast_k.where(denominator != 0, 0.0)
    return fast_k.rolling(window=k_smooth, min_periods=k_smooth).mean()


def monthly_context_frame(
    df: pd.DataFrame, params: Optional[dict] = None
) -> pd.DataFrame:
    """월봉 OHLC 프레임 -> 월별 맥락 시계열.

    필요한 컬럼: high/low/close. 워밍업 구간은 NaN 으로 남는다(자르지 않음 —
    조인 키로 쓰이므로 인덱스를 보존한다). 컬럼이 없거나 df 가 비면 빈 프레임.
    """
    if df is None or df.empty or not {"high", "low", "close"}.issubset(df.columns):
        return pd.DataFrame(columns=_FRAME_COLUMNS)

    p = _merged_params(params)
    band_n = int(p["band_months"])
    ma_n = int(p["ma_n"])

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    large_k = _slow_k(df)
    diff = large_k.diff()
    large_k_dir = pd.Series(
        pd.NA, index=df.index, dtype="object"
    ).mask(diff > 0, "up").mask(diff < 0, "down").mask(diff == 0, "flat")

    ma20 = close.rolling(window=ma_n, min_periods=ma_n).mean()
    ma20_slope_pct = ma20.pct_change(fill_method=None) * 100.0

    band_low = low.rolling(window=band_n, min_periods=band_n).min()
    band_high = high.rolling(window=band_n, min_periods=band_n).max()
    band_range = band_high - band_low
    band_pos_pct = ((close - band_low) / band_range.where(band_range != 0)) * 100.0

    return pd.DataFrame(
        {
            "close": close,
            "large_k": large_k,
            "large_k_dir": large_k_dir,
            "ma20": ma20,
            "ma20_slope_pct": ma20_slope_pct,
            "band_low": band_low,
            "band_high": band_high,
            "band_pos_pct": band_pos_pct,
        },
        index=df.index,
    )[_FRAME_COLUMNS]
