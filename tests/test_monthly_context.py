"""월봉 맥락 레코드 테스트 — SPEC_SWEEP_RECLAIM §8 기록 계약."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.monthly_context import _FRAME_COLUMNS, monthly_context_frame
from config.settings import MONTHLY_CONTEXT_PARAMS


def _frame(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="MS")
    c = pd.Series([float(v) for v in closes], index=idx)
    return pd.DataFrame({"high": c * 1.05, "low": c * 0.95, "close": c}, index=idx)


def test_params_contract():
    assert {"band_months", "ma_n"} <= set(MONTHLY_CONTEXT_PARAMS)


def test_columns_and_index_preserved():
    """컬럼 계약 + 워밍업 NaN 보존(인덱스 자르지 않음 — 조인 키)."""
    df = _frame(np.linspace(100, 200, 40))
    ctx = monthly_context_frame(df)
    assert list(ctx.columns) == _FRAME_COLUMNS
    assert len(ctx) == len(df)
    assert ctx.index.equals(df.index)
    assert ctx["large_k"].iloc[:28].isna().all()      # k_len 20 + k_smooth 10 워밍업


def test_rising_series_reads_high():
    """단조 상승: 대파동 K 상단, 밴드 위치 상단, MA 기울기 양수.

    방향은 여기서 검사하지 않는다 — 등차 상승에서는 %K 비율이 서서히 하락하는 게
    수학적으로 맞다(절대 스텝 고정, 분모의 가격 비례 항 증가).
    """
    df = _frame(np.linspace(100, 300, 40))
    last = monthly_context_frame(df).iloc[-1]
    assert last["large_k"] > 80
    # 밴드 하단이 24개월 전 저가(0.95배)라 선형 상승에선 이론상 ≈89% — 85 기준.
    assert last["band_pos_pct"] > 85
    assert last["ma20_slope_pct"] > 0


def test_direction_labels():
    """하락 후 급반등 -> 말봉 방향 up, 상승 후 급락 -> down."""
    v_shape = list(np.linspace(300, 150, 30)) + list(np.linspace(160, 400, 10))
    assert monthly_context_frame(_frame(v_shape)).iloc[-1]["large_k_dir"] == "up"

    a_shape = list(np.linspace(150, 300, 30)) + list(np.linspace(290, 100, 10))
    assert monthly_context_frame(_frame(a_shape)).iloc[-1]["large_k_dir"] == "down"


def test_flat_series_is_safe():
    """완전 평탄: 분모 0 경로 — K 는 0 처리(지표 공식 동일), 밴드 위치는 NA."""
    idx = pd.date_range("2020-01-01", periods=40, freq="MS")
    df = pd.DataFrame({"high": [100.0] * 40, "low": [100.0] * 40, "close": [100.0] * 40}, index=idx)
    last = monthly_context_frame(df).iloc[-1]
    assert last["large_k"] == pytest.approx(0.0)
    assert pd.isna(last["band_pos_pct"])


def test_short_and_missing_inputs():
    """워밍업 미달은 NaN, 컬럼 결측·빈 df 는 빈 프레임."""
    ctx = monthly_context_frame(_frame([100, 110, 120]))
    assert len(ctx) == 3 and ctx["large_k"].isna().all()

    idx = pd.date_range("2020-01-01", periods=3, freq="MS")
    assert monthly_context_frame(pd.DataFrame({"close": [1.0] * 3}, index=idx)).empty
    assert monthly_context_frame(pd.DataFrame()).empty
