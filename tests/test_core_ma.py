"""판정용 이평 체계 분리 테스트 (작업 2): 40·80은 배열 판정에 영향 없음.

실행: `python -m pytest tests/test_core_ma.py` 또는 `python tests/test_core_ma.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CORE_MA_PERIODS, MA_PERIODS
from analysis.engine import get_ma_alignment


def _one_row_df(ma_values: dict) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=1, freq="D")
    return pd.DataFrame({f"MA{p}": [v] for p, v in ma_values.items()}, index=idx)


def test_core_periods_definition():
    assert CORE_MA_PERIODS == [5, 10, 20, 60, 120, 240]
    # 40·80은 표시 전용으로 MA_PERIODS에는 남아있어야 한다
    assert 40 in MA_PERIODS and 80 in MA_PERIODS


def test_40_80_do_not_affect_alignment_bullish():
    # 코어 6개는 완전 정배열(MA5 최상단), MA40/MA80만 순서를 어긋나게 둔다.
    ma = {5: 60, 10: 50, 20: 40, 60: 30, 120: 20, 240: 10}
    ma[40] = 999  # 어긋남
    ma[80] = -999  # 어긋남
    df = _one_row_df(ma)
    assert "정배열" in get_ma_alignment(df)


def test_40_80_do_not_affect_alignment_bearish():
    # 코어 6개는 완전 역배열(MA5 최하단), MA40/MA80만 어긋남.
    ma = {5: 10, 10: 20, 20: 30, 60: 40, 120: 50, 240: 60}
    ma[40] = -999
    ma[80] = 999
    df = _one_row_df(ma)
    assert "역배열" in get_ma_alignment(df)


if __name__ == "__main__":
    test_core_periods_definition()
    test_40_80_do_not_affect_alignment_bullish()
    test_40_80_do_not_affect_alignment_bearish()
    print("ALL CORE MA TESTS PASSED")
