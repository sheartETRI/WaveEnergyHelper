"""TF 사다리 + 데이터 충분성 회귀 테스트.

확정 규칙:
- TF_LADDER = ["15m","1h","4h","1d","4d","2w"] (하위→상위)
- upper/lower는 인덱스 ±1, 경계는 None (대체하지 않는다)
- 4d/2w 리샘플은 기존 resample_timeframe 그대로 (2d 동작 불변 보증)
- 데이터 충분성: available_bars >= p + min_detect_bars 인 CORE_MA만 usable

실행: `python -m pytest tests/test_tf_ladder.py` 또는 `python tests/test_tf_ladder.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import tf_ladder
from analysis.tf_ladder import (
    TF_LADDER,
    assess_tf_data,
    lower,
    recommended_base_limit,
    upper,
    usable_core_ma_periods,
)
from data.processor import resample_timeframe


def test_ladder_order_and_membership():
    assert TF_LADDER == ["15m", "1h", "4h", "1d", "4d", "2w"]
    assert tf_ladder.in_ladder("4h")
    assert not tf_ladder.in_ladder("30m")


def test_upper_lower_interior():
    assert upper("15m") == "1h"
    assert upper("1d") == "4d"
    assert lower("2w") == "4d"
    assert lower("4h") == "1h"


def test_upper_lower_edges_return_none_not_substitute():
    # 최하단 15m은 하위 없음, 최상단 2w는 상위 없음 — 대체 금지
    assert lower("15m") is None
    assert upper("2w") is None
    # 사다리 밖 TF
    assert upper("30m") is None
    assert lower("30m") is None
    assert tf_ladder.ladder_index("1M") is None


def test_recommended_base_limit_native_vs_resampled():
    # 네이티브 TF는 target 그대로
    assert recommended_base_limit("1h", 500) == 500
    # 4d는 4× + 여유, 2w는 14× + 여유
    assert recommended_base_limit("4d", 100) == 100 * 4 + 4
    assert recommended_base_limit("2w", 100) == 100 * 14 + 14


def test_usable_core_ma_subset():
    # 300봉이면 전 구간(MA240까지) 검출 가능
    assert usable_core_ma_periods(300) == [5, 10, 20, 60, 120, 240]
    # 73봉(≈2w from 1000×1d): MA5~20만, MA60(60+20=80) 이상 불가
    assert usable_core_ma_periods(73) == [5, 10, 20]
    # 극단적으로 적으면 빈 리스트
    assert usable_core_ma_periods(10) == []


def test_assess_tf_data_notes_and_flags():
    full = assess_tf_data(300, "1d")
    assert full.ma240_ok is True
    assert full.missing_ma_periods == []
    assert "전 구간" in full.note

    partial = assess_tf_data(73, "2w")
    assert partial.ma240_ok is False
    assert partial.usable_ma_periods == [5, 10, 20]
    assert 60 in partial.missing_ma_periods
    assert "부분집합" in partial.note

    empty = assess_tf_data(10, "2w")
    assert empty.usable_ma_periods == []
    assert "부족" in empty.note


def _make_1d(periods):
    idx = pd.date_range("2016-01-01", periods=periods, freq="1D")
    base = pd.Series(range(periods), dtype=float)
    return pd.DataFrame(
        {
            "open": base.values,
            "high": (base + 1).values,
            "low": (base - 1).values,
            "close": (base + 0.5).values,
            "volume": 1.0,
        },
        index=idx,
    )


def test_4d_2w_resample_produces_expected_bars():
    df = _make_1d(1000)
    out_4d = resample_timeframe(df, "4d")
    out_2w = resample_timeframe(df, "2w")
    # 1000 1d → 250개 4d (1000/4), 2주 격자로 ~72~73개 2w
    assert 249 <= len(out_4d) <= 251
    assert 71 <= len(out_2w) <= 74
    # OHLCV 집계 정합 (첫 4d 봉)
    first = out_4d.iloc[0]
    assert first["high"] >= first["low"]


def test_2d_resample_unchanged_guard():
    # 2d/4d/2w 동작 불변 보증 (기존 규칙 label/closed=right, origin=start)
    df = _make_1d(10)
    expected = df.resample("2D", label="right", closed="right", origin="start").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    pd.testing.assert_frame_equal(resample_timeframe(df, "2d"), expected)


if __name__ == "__main__":
    test_ladder_order_and_membership()
    test_upper_lower_interior()
    test_upper_lower_edges_return_none_not_substitute()
    test_recommended_base_limit_native_vs_resampled()
    test_usable_core_ma_subset()
    test_assess_tf_data_notes_and_flags()
    test_4d_2w_resample_produces_expected_bars()
    test_2d_resample_unchanged_guard()
    print("ALL TF LADDER TESTS PASSED")
