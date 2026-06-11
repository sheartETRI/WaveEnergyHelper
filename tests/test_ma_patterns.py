"""이평선 쌍바닥/쌍봉 검출기 테스트 (작업 3).

실행: `python -m pytest tests/test_ma_patterns.py` 또는 `python tests/test_ma_patterns.py`
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import MA_PATTERN_PARAMS
from indicators.ma_patterns import (
    compute_series_pivots,
    _detect_series_double_bottom,
    _detect_series_double_top,
)

P = MA_PATTERN_PARAMS


def _w_series(low1, low2):
    """하락 -> 저점1 -> 넥라인(40) -> 저점2 -> 돌파 형태의 W 시계열."""
    seg = []
    seg += list(np.linspace(100, low1, 9))
    seg += list(np.linspace(low1, 40, 5))[1:]
    seg += list(np.linspace(40, low2, 5))[1:]
    seg += list(np.linspace(low2, 55, 6))[1:]
    return np.array(seg, dtype=float)


def _rising_w():
    """상승 추세 중 형성된 W (하락 전제 위반)."""
    seg = []
    seg += list(np.linspace(0, 30, 9))
    seg += [27, 24, 27]
    seg += list(np.linspace(27, 45, 4))[1:]
    seg += list(np.linspace(45, 26, 4))[1:]
    seg += [29, 32]
    seg += [44, 50, 55]
    return np.array(seg, dtype=float)


def _frame(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    df = pd.DataFrame({"MA5": pd.Series(values, index=idx)})
    pl, ph = compute_series_pivots(df["MA5"], P["lookback"], P["min_gap"], P["rel_tolerance"])
    df["pl"] = pl
    df["ph"] = ph
    return df


def _run_bottom(values, with_first_pos=False):
    df = _frame(values)
    fp = "db_fp" if with_first_pos else None
    return _detect_series_double_bottom(
        df, "MA5", "pl", "ph", "db", "db_kind", P["decline_lookback"], first_pos_col=fp,
    )


def test_ma_db_first_pos_matches_first_pivot():
    df = _run_bottom(_w_series(10, 20), with_first_pos=True)
    hits = df[df["db"].notna()]
    assert len(hits) == 1
    low_pos = [i for i, v in enumerate(df["pl"].notna().values) if v][0]
    assert int(hits["db_fp"].iloc[0]) == low_pos


def test_double_bottom_HL():
    df = _run_bottom(_w_series(10, 20))
    hits = df[df["db"].notna()]
    assert len(hits) == 1
    assert hits["db_kind"].iloc[0] == "HL"


def test_double_bottom_LL():
    df = _run_bottom(_w_series(10, 5))
    hits = df[df["db"].notna()]
    assert len(hits) == 1
    assert hits["db_kind"].iloc[0] == "LL"


def test_decline_precondition_violation():
    df = _run_bottom(_rising_w())
    assert df["db"].notna().sum() == 0


def test_double_top_reflection_symmetry():
    for low2, expected_dt_kind in [(20, "LH"), (5, "HH")]:
        v = _w_series(10, low2)
        idx = pd.date_range("2024-01-01", periods=len(v), freq="D")
        M = v.max() + v.min() + 10.0

        b = _run_bottom(v)
        r = pd.DataFrame({"MA5": pd.Series(M - v, index=idx)})
        r = _detect_series_double_top(r, "MA5", "unused", "dt", P)

        db_mask = b["db"].notna().values
        dt_mask = r["dt"].notna().values
        assert np.array_equal(db_mask, dt_mask)

        db_kind = b.loc[b["db"].notna(), "db_kind"].iloc[0]
        dt_kind = r.loc[r["dt"].notna(), "dt_kind"].iloc[0]
        # 바닥 HL/LL <-> 봉 LH/HH 매핑 확인
        assert {"HL": "LH", "LL": "HH"}[db_kind] == dt_kind == expected_dt_kind


def test_scale_invariance():
    v = _w_series(10, 20)
    base = _run_bottom(v)
    scaled = _run_bottom(v * 1000.0)
    assert np.array_equal(base["db"].notna().values, scaled["db"].notna().values)
    assert (
        base.loc[base["db"].notna(), "db_kind"].iloc[0]
        == scaled.loc[scaled["db"].notna(), "db_kind"].iloc[0]
    )


if __name__ == "__main__":
    test_double_bottom_HL()
    test_double_bottom_LL()
    test_decline_precondition_violation()
    test_double_top_reflection_symmetry()
    test_scale_invariance()
    print("ALL MA PATTERN TESTS PASSED")
