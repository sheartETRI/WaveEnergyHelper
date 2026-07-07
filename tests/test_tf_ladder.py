"""TF 풀 + 인접(스펙 §1) + 데이터 충분성 회귀 테스트.

확정 규칙 (동결 스펙 §1):
- TF_POOL = ["15m","30m","1h","2h","4h","6h","8h","1d","4d","2w"] (12h 없음)
- upper/lower는 비율 규칙 ×3.5~×6 / ÷3.5~÷6, ×4·÷4 최근접 우선. 예외 없음, 대체 없음.
- 상·하위 각각 독립 계산 → 대칭 보장 안 함(예: upper(4h)=1d 이나 lower(1d)=6h).
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
    TF_POOL,
    assess_tf_data,
    lower,
    recommended_base_limit,
    upper,
    usable_core_ma_periods,
)
from data.processor import resample_timeframe


def test_pool_matches_spec_no_12h():
    # 9차 위임 B: "1M"(월봉) 추가 — 고립 TF(관측 전용).
    assert TF_POOL == ["15m", "30m", "1h", "2h", "4h", "6h", "8h", "1d", "4d", "2w", "1M"]
    assert "12h" not in TF_POOL
    assert "1M" in TF_POOL
    assert tf_ladder.TF_LADDER == TF_POOL   # 하위 호환 별칭
    assert tf_ladder.in_ladder("8h")
    assert not tf_ladder.in_ladder("12h")


def test_adjacency_table_matches_spec_section1():
    """스펙 §1 인접표 전수 고정 (비고 포함). 표를 그대로 단위 테스트로 박는다."""
    # (tf, expected_lower, expected_upper)
    table = [
        ("15m", None, "1h"),    # 하위 없음 → 카운팅 불가
        ("30m", None, "2h"),    # 하위 없음
        ("1h", "15m", "4h"),    # 6h(×6)보다 4h 우선
        ("2h", "30m", "8h"),
        ("4h", "1h", "1d"),     # upper 1d = ×6
        ("6h", "1h", "1d"),     # lower 1h = ÷6
        ("8h", "2h", None),     # 1d는 ×3 → 범위 밖. 상위 없음
        ("1d", "6h", "4d"),     # 4h(÷6)보다 6h 우선
        ("4d", "1d", "2w"),     # 2w = ×3.5(하한 포함)
        ("2w", "4d", None),     # 상위 없음 (1M은 ×2.14 → 인접 아님)
        ("1M", None, None),     # 9차 B: 고립 TF — 2w와 ×2.14(<3.5)라 상·하위 모두 없음
    ]
    for tf, lo, up in table:
        assert lower(tf) == lo, f"lower({tf}) = {lower(tf)}, 기대 {lo}"
        assert upper(tf) == up, f"upper({tf}) = {upper(tf)}, 기대 {up}"


def test_adjacency_asymmetry_is_by_design():
    # 스펙 §1 명시: upper(4h)=1d 이나 lower(1d)=6h (버그 아님, 규칙의 결과)
    assert upper("4h") == "1d"
    assert lower("1d") == "6h"


def test_upper_lower_edges_return_none_not_substitute():
    # 풀 최하단 15m은 하위 없음, 최상단 2w는 상위 없음 — 대체 금지
    assert lower("15m") is None
    assert upper("2w") is None
    # 8h는 상위 없음(고립 상단), 30m/15m은 하위 없음(고립 하단)
    assert upper("8h") is None
    assert lower("30m") is None
    # 풀 밖 TF(12h 포함)는 None
    assert upper("12h") is None
    assert lower("12h") is None


def test_1M_isolated_observation_tf():
    # 9차 위임 B: 1M은 풀에 있으나 고립(상·하위 없음). 통계·승격 아닌 관측 전용.
    assert tf_ladder.in_ladder("1M")
    assert tf_ladder.ladder_index("1M") == len(TF_POOL) - 1   # 풀 최상단
    assert upper("1M") is None and lower("1M") is None
    # 2w도 1M을 상위로 끌어오지 않는다(×2.14 < 3.5).
    assert upper("2w") is None
    # 히스토리 ~107개월: MA60까지만 usable, MA120/240 부족(부분집합).
    part = assess_tf_data(107, "1M")
    assert part.usable_ma_periods == [5, 10, 20, 60]
    assert part.missing_ma_periods == [120, 240]
    assert "부분집합" in part.note


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
    test_pool_matches_spec_no_12h()
    test_adjacency_table_matches_spec_section1()
    test_adjacency_asymmetry_is_by_design()
    test_upper_lower_edges_return_none_not_substitute()
    test_1M_isolated_observation_tf()
    test_recommended_base_limit_native_vs_resampled()
    test_usable_core_ma_subset()
    test_assess_tf_data_notes_and_flags()
    test_4d_2w_resample_produces_expected_bars()
    test_2d_resample_unchanged_guard()
    print("ALL TF LADDER TESTS PASSED")
