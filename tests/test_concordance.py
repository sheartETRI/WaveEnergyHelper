"""상응 합치(concordance) 태그 회귀 테스트 (4차 위임 E-2).

확정 규칙:
- MA10↔대파동(20,10,10), MA5↔중파동(10,5,5), 캔들↔소파동(5,3,3).
- 방향만 같으면 진행 중(candidate)도 인정. 우선순위 confirmed > in_progress > none.
- 상응 없는 급(MA20)은 n/a. 창 밖 신호는 무시.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.concordance import (
    CONFIRMED,
    IN_PROGRESS,
    NA,
    NONE,
    concordance_at,
)
from config.settings import WAVE_LAYER_ROLES

_LARGE = WAVE_LAYER_ROLES["large"]


def _df(n=30):
    idx = pd.date_range("2020-01-01", periods=n, freq="1h")
    return pd.DataFrame({"close": range(n)}, index=idx)


def test_confirmed_when_large_db_in_window():
    df = _df()
    df[f"stoch_db_{_LARGE}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[20, df.columns.get_loc(f"stoch_db_{_LARGE}")] = 12.0   # 확정 @20
    assert concordance_at(df, "MA10", "long", 25, window=12) == CONFIRMED
    # 창 밖(pos=40 없음; pos=25 window 12 → [14,25] 포함). pos=10이면 창 [0,10] 미포함 → none.
    assert concordance_at(df, "MA10", "long", 10, window=12) == NONE


def test_in_progress_when_only_candidate():
    df = _df()
    df[f"stoch_db_candidate_{_LARGE}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[22, df.columns.get_loc(f"stoch_db_candidate_{_LARGE}")] = 11.0  # 후보 @22
    assert concordance_at(df, "MA10", "long", 24, window=12) == IN_PROGRESS


def test_confirmed_beats_in_progress():
    df = _df()
    df[f"stoch_db_{_LARGE}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[f"stoch_db_candidate_{_LARGE}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[20, df.columns.get_loc(f"stoch_db_{_LARGE}")] = 12.0
    df.iloc[22, df.columns.get_loc(f"stoch_db_candidate_{_LARGE}")] = 11.0
    assert concordance_at(df, "MA10", "long", 24, window=12) == CONFIRMED


def test_direction_and_layer_mapping():
    df = _df()
    # long은 db를 보고, short은 dt를 본다. 상응 없는 급은 n/a.
    assert concordance_at(df, "MA20", "long", 25) == NA
    # dt 확정이 있으면 short에서 confirmed, long에선 무시(none).
    df[f"stoch_dt_{_LARGE}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[20, df.columns.get_loc(f"stoch_dt_{_LARGE}")] = 88.0
    assert concordance_at(df, "MA10", "short", 25, window=12) == CONFIRMED
    assert concordance_at(df, "MA10", "long", 25, window=12) == NONE


if __name__ == "__main__":
    test_confirmed_when_large_db_in_window()
    test_in_progress_when_only_candidate()
    test_confirmed_beats_in_progress()
    test_direction_and_layer_mapping()
    print("ALL CONCORDANCE TESTS PASSED")
