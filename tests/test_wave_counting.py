"""하위 TF 파동 카운팅 (관측 전용) 테스트 (§4 L3).

실행: `python -m pytest tests/test_wave_counting.py` 또는 직접 실행
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_counting import count_lower_waves, lower_wave_label_at
from config.settings import WAVE_LAYER_ROLES

_LARGE = WAVE_LAYER_ROLES["large"]
LOW = f"stoch_pivot_low_{_LARGE}"
HIGH = f"stoch_pivot_high_{_LARGE}"


def _frame(pivots):
    """pivots: {pos: ('L'|'H', value)} → 대파동 피봇 컬럼 프레임."""
    n = 20
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame(index=idx)
    df[LOW] = pd.array([pd.NA] * n, dtype="Float64")
    df[HIGH] = pd.array([pd.NA] * n, dtype="Float64")
    for pos, (kind, val) in pivots.items():
        col = LOW if kind == "L" else HIGH
        df.loc[idx[pos], col] = val
    return df, idx


def test_wave_progression_1_2_3():
    # 기점 저점@2 → 고점@5(1파) → 저점@8(2파) → 고점@11(3파)
    df, idx = _frame({2: ("L", 10), 5: ("H", 30), 8: ("L", 15), 11: ("H", 40)})
    start = idx[0]
    # 기점 직후, 고점 전 → 1파 진행
    assert lower_wave_label_at(df, start, idx[3], "15m") == "1파"
    # 1파 고점 후 → 2파 진행
    assert lower_wave_label_at(df, start, idx[6], "15m") == "2파"
    # 2파 저점 후 → 3파 진행
    assert lower_wave_label_at(df, start, idx[9], "15m") == "3파"
    # 3파 고점 후 → 연장
    assert lower_wave_label_at(df, start, idx[12], "15m") == "3파 이상(연장)"


def test_full_count_fields():
    df, idx = _frame({2: ("L", 10), 5: ("H", 30), 8: ("L", 15)})
    wc = count_lower_waves(df, idx[0], "15m")
    assert wc.origin_ts == idx[2]
    assert wc.forming_wave == 3        # 기점 이후 피봇 2개(+1)
    assert wc.forming_label == "3파"


def test_no_lower_tf_returns_impossible_not_substitute():
    # 하위 TF 없음(15m 하위) → "불가", 대체하지 않는다(§1)
    wc = count_lower_waves(None, pd.Timestamp("2026-01-01"), None)
    assert wc.forming_label == "불가"
    assert "하위 TF 없음" in wc.note


def test_no_pivots_impossible():
    df, idx = _frame({})
    wc = count_lower_waves(df, idx[0], "15m")
    assert wc.forming_label == "불가"


def test_origin_not_formed_when_only_high():
    # 저점 없이 고점만 → 기점 미형성 "미정"
    df, idx = _frame({3: ("H", 30)})
    wc = count_lower_waves(df, idx[0], "15m")
    assert wc.forming_label == "미정"


if __name__ == "__main__":
    test_wave_progression_1_2_3()
    test_full_count_fields()
    test_no_lower_tf_returns_impossible_not_substitute()
    test_no_pivots_impossible()
    test_origin_not_formed_when_only_high()
    print("ALL WAVE COUNTING TESTS PASSED")
