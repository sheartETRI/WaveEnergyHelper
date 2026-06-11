# indicators/ma_dispersion.py
"""이평선 이격도 수렴 지표 — CORE 6개 MA 간 평균 정규화 이격 합.

dispersion_t = (Σ_{i<j} |MA_i − MA_j|) / (C(6,2) × close_t)
표시·관측 전용. ④⑤/①② 게이트에 연결하지 않는다.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from config.settings import CORE_MA_PERIODS, DISPERSION_TYPE_PARAMS, MA_PATTERN_PARAMS
from indicators.ma_patterns import compute_series_pivots

# 피봇 검출은 MA_PATTERN_PARAMS 재사용 (lookback/min_gap/rel_tolerance).
# dispersion 전용 추가 파라미터 없음 — MA_DISPERSION_PARAMS 별칭으로 문서화.
MA_DISPERSION_PARAMS = MA_PATTERN_PARAMS

_N_PAIRS = len(CORE_MA_PERIODS) * (len(CORE_MA_PERIODS) - 1) // 2  # C(6,2)=15
_MA_COLS = [f"MA{p}" for p in CORE_MA_PERIODS]


def compute_ma_dispersion_series(df: pd.DataFrame) -> pd.Series:
    """ma_dispersion 시리즈만 계산 (테스트·관측용 순수 함수)."""
    out = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if df is None or df.empty:
        return out

    missing = [c for c in _MA_COLS if c not in df.columns]
    if missing:
        return out

    ma = df[_MA_COLS].astype("float64")
    close = df["close"].astype("float64")

    any_ma_nan = ma.isna().any(axis=1)
    close_nan = close.isna()
    invalid = any_ma_nan | close_nan | (close == 0)

    spread_sum = pd.Series(0.0, index=df.index, dtype="float64")
    for i, ci in enumerate(_MA_COLS):
        for cj in _MA_COLS[i + 1:]:
            spread_sum = spread_sum + (ma[ci] - ma[cj]).abs()

    valid = ~invalid
    out.loc[valid] = spread_sum.loc[valid] / (_N_PAIRS * close.loc[valid])
    return out.astype("Float64")


def dispersion_percentile_rank(df: pd.DataFrame, pos: int) -> Optional[float]:
    """형성 봉 ma_dispersion의 전역 rank 백분위 (0~100).

    유효 ma_dispersion 값 중 해당 봉 값 이하인 비율 ×100 (rank 기반, ties 포함).
    """
    if "ma_dispersion" not in df.columns:
        return None
    s = df["ma_dispersion"].dropna()
    if s.empty:
        return None
    v = df.iloc[pos]["ma_dispersion"]
    if v is None or pd.isna(v):
        return None
    return float((s <= v).sum() / len(s) * 100.0)


def classify_dispersion_type(pct: Optional[float]) -> Optional[str]:
    """백분위 → 응축형/과이격형/중간 (표기 전용, 게이트 아님)."""
    if pct is None:
        return None
    compress = DISPERSION_TYPE_PARAMS["compress_pct"]
    stretch = DISPERSION_TYPE_PARAMS["stretch_pct"]
    if pct <= compress:
        return "응축형"
    if pct >= stretch:
        return "과이격형"
    return "중간"


@st.cache_data(ttl=600)
def add_ma_dispersion(df: pd.DataFrame) -> pd.DataFrame:
    """ma_dispersion + 수렴/발산 피봇 컬럼 추가."""
    if df is None or df.empty:
        return df

    df["ma_dispersion"] = compute_ma_dispersion_series(df)

    params = MA_DISPERSION_PARAMS
    pivot_low, pivot_high = compute_series_pivots(
        df["ma_dispersion"],
        lookback=params["lookback"],
        min_gap=params["min_gap"],
        rel_tolerance=params["rel_tolerance"],
    )
    df["ma_dispersion_pivot_low"] = pivot_low
    df["ma_dispersion_pivot_high"] = pivot_high
    return df
