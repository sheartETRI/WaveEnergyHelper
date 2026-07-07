"""array_context 분류기 회귀 테스트 (4차 위임 C) — 관측 태그 전용.

확정 규칙:
- 정배열 MA5>MA10>MA20>MA60, 역배열 MA5<MA10<MA20<MA60, 그 외 mixed
- converging = 정규화 스프레드 상한 이하 AND window 전 대비 축소
- 정방향 정합: 역배열+모임+쌍바닥(long) / 정배열+모임+쌍봉(short)
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.array_context import (
    BEAR_ARRAY,
    BULL_ARRAY,
    MIXED,
    classify_array,
    context_aligned,
    context_at,
    tag_s0,
)


def test_classify_array_bull_bear_mixed():
    assert classify_array([10, 9, 8, 7]) == BULL_ARRAY
    assert classify_array([7, 8, 9, 10]) == BEAR_ARRAY
    assert classify_array([10, 8, 9, 7]) == MIXED


def _frame(rows):
    """rows: list of (ma5,ma10,ma20,ma60,close)."""
    idx = pd.date_range("2020-01-01", periods=len(rows), freq="1D")
    return pd.DataFrame(
        {
            "MA5": [r[0] for r in rows], "MA10": [r[1] for r in rows],
            "MA20": [r[2] for r in rows], "MA60": [r[3] for r in rows],
            "close": [r[4] for r in rows],
        },
        index=idx,
    )


def test_converging_detected_when_spread_shrinks():
    # 초기 넓은 역배열 → 끝에서 좁게 수렴(역배열 유지, 모임).
    rows = [(90, 95, 100, 110, 100)] * 10           # 넓은 스프레드(0.20)
    rows += [(99.0, 99.4, 99.8, 100.2, 100.0)]      # 좁은 스프레드(0.012), 축소
    df = _frame(rows)
    ctx = context_at(df, len(df) - 1)
    assert ctx.array == BEAR_ARRAY
    assert ctx.converging is True
    assert "converging" in ctx.label


def test_not_converging_when_spread_wide():
    rows = [(90, 95, 100, 110, 100)] * 12
    df = _frame(rows)
    ctx = context_at(df, len(df) - 1)
    assert ctx.converging is False   # 스프레드 상한 초과


def test_context_aligned_rules():
    rows = [(90, 95, 100, 110, 100)] * 10 + [(99.0, 99.4, 99.8, 100.2, 100.0)]
    df = _frame(rows)
    ctx = context_at(df, len(df) - 1)   # bear_array/converging
    assert context_aligned(ctx, "long") is True     # 역배열+모임+쌍바닥 = 정방향
    assert context_aligned(ctx, "short") is False    # 쌍봉엔 비정방향

    label, aligned = tag_s0(df, len(df) - 1, "long")
    assert aligned is True
    assert label == ctx.label


if __name__ == "__main__":
    test_classify_array_bull_bear_mixed()
    test_converging_detected_when_spread_shrinks()
    test_not_converging_when_spread_wide()
    test_context_aligned_rules()
    print("ALL ARRAY_CONTEXT TESTS PASSED")
