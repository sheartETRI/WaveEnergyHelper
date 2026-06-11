"""구간별 배열 판정기 테스트 (작업 1) — §6-④⑤ 선행 인프라.

실행: `python -m pytest tests/test_structure.py` 또는 `python tests/test_structure.py`
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.structure import (
    STRUCTURE_STATES,
    classify_structure_at,
    is_chain_ordered,
)


def _row_df(values: dict) -> pd.DataFrame:
    """단일 봉 DataFrame을 만든다. keys: close, MA5/10/20/60/120/240."""
    return pd.DataFrame([values])


# 6개 상태 각각이 '성립'하는 합성 봉
_STATE_ROWS = {
    # U1: close>5>10>20>60 (정배열) + 60<120<240 (역배열)
    "U1": {"close": 100, "MA5": 90, "MA10": 80, "MA20": 70, "MA60": 60, "MA120": 65, "MA240": 70},
    # U2: close>5>10>20>60>120 + 120<240
    "U2": {"close": 130, "MA5": 120, "MA10": 110, "MA20": 100, "MA60": 90, "MA120": 80, "MA240": 85},
    # U3: 완전 정배열 close>5>10>20>60>120>240
    "U3": {"close": 140, "MA5": 120, "MA10": 100, "MA20": 80, "MA60": 60, "MA120": 40, "MA240": 20},
    # D1: 60>120>240 (정배열) + close<5<10<20<60 (역배열)
    "D1": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 45, "MA240": 40},
    # D2: 120>240 + close<5<10<20<60<120
    "D2": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 60, "MA240": 55},
    # D3: 완전 역배열 close<5<10<20<60<120<240
    "D3": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 60, "MA240": 70},
}


def test_is_chain_ordered_basics():
    row = pd.Series({"close": 100, "MA5": 90, "MA10": 80, "MA60": 60})
    assert is_chain_ordered(row, ["close", 5, 10, 60], descending=True) is True
    assert is_chain_ordered(row, ["close", 5, 10, 60], descending=False) is False
    # 빈 체인은 항상 True (U3/D3의 공집합 체인)
    assert is_chain_ordered(row, [], descending=True) is True
    # NaN -> None
    row_nan = pd.Series({"close": 100, "MA5": np.nan})
    assert is_chain_ordered(row_nan, ["close", 5], descending=True) is None


def test_each_state_classifies_correctly():
    for label, values in _STATE_ROWS.items():
        df = _row_df(values)
        assert classify_structure_at(df, 0) == label, f"{label} 합성 봉이 {label}로 분류되지 않음"


def test_equal_boundary_breaks_chain():
    # U1이 될 뻔하지만 MA60 == MA120 -> 60<120 불성립 (엄격 부등호)
    values = {"close": 100, "MA5": 90, "MA10": 80, "MA20": 70, "MA60": 65, "MA120": 65, "MA240": 70}
    assert classify_structure_at(_row_df(values), 0) is None


def test_nan_returns_none():
    values = dict(_STATE_ROWS["U3"])
    values["MA240"] = np.nan
    assert classify_structure_at(_row_df(values), 0) is None


def test_mixed_arrangement_returns_none():
    values = {"close": 50, "MA5": 60, "MA10": 40, "MA20": 70, "MA60": 30, "MA120": 90, "MA240": 20}
    assert classify_structure_at(_row_df(values), 0) is None


def test_mutual_exclusivity():
    """6개 상태의 성립 row를 교차 검사 — 어떤 row도 2개 이상 상태에 동시 성립하지 않는다."""
    for expected, values in _STATE_ROWS.items():
        row = pd.Series(values)
        matches = []
        for label, normal_chain, inverse_chain in STRUCTURE_STATES:
            normal_ok = is_chain_ordered(row, normal_chain, descending=True)
            inverse_ok = is_chain_ordered(row, inverse_chain, descending=False)
            if normal_ok and inverse_ok:
                matches.append(label)
        assert matches == [expected], f"{expected} row가 {matches}에 동시 성립 (상호 배타성 위반)"


def test_table_has_six_states():
    labels = [s[0] for s in STRUCTURE_STATES]
    assert labels == ["U1", "U2", "U3", "D1", "D2", "D3"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL STRUCTURE TESTS PASSED")
