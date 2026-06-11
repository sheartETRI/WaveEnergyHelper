"""변곡점 추세전환 공식 §6-④⑤ (F6-4a~4c, F6-5a~5c) 테스트.

주입 컬럼 방식: 합성 df에 구조용 MA + 패턴/kind 컬럼을 직접 기록한다.
실행: `python -m pytest tests/test_transition_rules.py` 또는 `python tests/test_transition_rules.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES
from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    evaluate_transitions,
    evaluate_dynamics,
    parse_transition_row,
)

N = 30
IDX = pd.date_range("2024-01-01", periods=N, freq="D")

# 각 구조 라벨이 성립하는 배열 (test_structure.py와 동일 규칙)
STRUCT_ROWS = {
    "U1": {"close": 100, "MA5": 90, "MA10": 80, "MA20": 70, "MA60": 60, "MA120": 65, "MA240": 70},
    "U2": {"close": 130, "MA5": 120, "MA10": 110, "MA20": 100, "MA60": 90, "MA120": 80, "MA240": 85},
    "U3": {"close": 140, "MA5": 120, "MA10": 100, "MA20": 80, "MA60": 60, "MA120": 40, "MA240": 20},
    "D1": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 45, "MA240": 40},
    "D2": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 60, "MA240": 55},
    "D3": {"close": 10, "MA5": 20, "MA10": 30, "MA20": 40, "MA60": 50, "MA120": 60, "MA240": 70},
}


def _struct_df(label):
    df = pd.DataFrame(index=IDX)
    for col, val in STRUCT_ROWS[label].items():
        df[col] = float(val)
    return df


def _set_row(df, pos, values):
    for col, val in values.items():
        if col not in df.columns:
            df[col] = float("nan")
        df.iloc[pos, df.columns.get_loc(col)] = float(val)


def _inject_wave(df, layer, pattern, pos, kind=None):
    suffix = WAVE_LAYER_ROLES[layer]
    col = f"stoch_{pattern}_{suffix}"
    kcol = f"stoch_{pattern}_kind_{suffix}"
    if col not in df.columns:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if kcol not in df.columns:
        df[kcol] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.iloc[pos, df.columns.get_loc(col)] = 50.0
    if kind is not None:
        df.iloc[pos, df.columns.get_loc(kcol)] = kind


def _inject_ma(df, period, pattern, pos, kind=None):
    col = f"ma{period}_{pattern}"
    kcol = f"ma{period}_{pattern}_kind"
    if col not in df.columns:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if kcol not in df.columns:
        df[kcol] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.iloc[pos, df.columns.get_loc(col)] = 50.0
    if kind is not None:
        df.iloc[pos, df.columns.get_loc(kcol)] = kind


def _inject_wave_first_pos(df, layer, pattern, confirm_pos, pivot_pos):
    suffix = WAVE_LAYER_ROLES[layer]
    col = f"stoch_{pattern}_first_pos_{suffix}"
    if col not in df.columns:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[confirm_pos, df.columns.get_loc(col)] = float(pivot_pos)


def _inject_ma_first_pos(df, period, pattern, confirm_pos, pivot_pos):
    col = f"ma{period}_{pattern}_first_pos"
    if col not in df.columns:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df.iloc[confirm_pos, df.columns.get_loc(col)] = float(pivot_pos)


# 8개 공식 각각을 성립시키는 주입 시나리오 (구조 라벨, 주입 콜백, 기대 rule_id, bullish)
def _scenario_F6_4a(df):
    _inject_wave(df, "mid", "dt", 20)
    _inject_wave(df, "small", "tt", 22)

def _scenario_F6_4b(df):
    _inject_wave(df, "large", "dt", 20)
    _inject_wave(df, "mid", "tt", 22)

def _scenario_F6_4c_a(df):
    _inject_ma(df, 5, "dt", 20)
    _inject_wave(df, "large", "tt", 22)

def _scenario_F6_4c_b(df):
    _inject_ma(df, 10, "dt", 20, kind="HH")
    _inject_wave(df, "large", "dt", 22, kind="LH")

def _scenario_F6_5a(df):
    _inject_wave(df, "mid", "db", 20)
    _inject_wave(df, "small", "tb", 22)

def _scenario_F6_5b(df):
    _inject_wave(df, "large", "db", 20)
    _inject_wave(df, "mid", "tb", 22)

def _scenario_F6_5c_a(df):
    _inject_ma(df, 5, "db", 20)
    _inject_wave(df, "large", "tb", 22)

def _scenario_F6_5c_b(df):
    _inject_ma(df, 10, "db", 20, kind="LL")
    _inject_wave(df, "large", "db", 22, kind="HL")


_EIGHT = [
    ("U1", _scenario_F6_4a, "F6-4a", False),
    ("U2", _scenario_F6_4b, "F6-4b", False),
    ("U3", _scenario_F6_4c_a, "F6-4c-a", False),
    ("U3", _scenario_F6_4c_b, "F6-4c-b", False),
    ("D1", _scenario_F6_5a, "F6-5a", True),
    ("D2", _scenario_F6_5b, "F6-5b", True),
    ("D3", _scenario_F6_5c_a, "F6-5c-a", True),
    ("D3", _scenario_F6_5c_b, "F6-5c-b", True),
]


def test_eight_formulas_each_hit():
    for structure, scenario, rule_id, bullish in _EIGHT:
        df = _struct_df(structure)
        scenario(df)
        hits = evaluate_transitions(df)
        ids = {h.rule_id for h in hits}
        assert rule_id in ids, f"{rule_id} ({structure}) hit 누락, 실제 {ids}"
        hit = next(h for h in hits if h.rule_id == rule_id)
        assert hit.bullish is bullish
        assert hit.structure == structure


def test_table_eight_unique_ids():
    ids = [parse_transition_row(row)[2] for row in TRANSITION_RULE_TABLE]
    assert ids == ["F6-4a", "F6-4b", "F6-4c-a", "F6-4c-b", "F6-5a", "F6-5b", "F6-5c-a", "F6-5c-b"]
    assert len(set(ids)) == 8


def test_partial_condition_no_hit():
    # F6-4a: 두 조건 중 중파동 쌍봉만 존재 (소파동 쓰리봉 없음) -> hit 없음
    df = _struct_df("U1")
    _inject_wave(df, "mid", "dt", 20)
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-4a" for h in hits)


def test_structure_mismatch_no_hit():
    # 조건 2개 충족이지만 형성 봉 구조가 U2 (F6-4a 행은 U1 요구) -> hit 없음
    df = _struct_df("U2")
    _scenario_F6_4a(df)
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-4a" for h in hits)


def test_kind_mismatch_no_hit():
    # F6-4c-b: MA10 쌍봉 kind가 LH(요구 HH) -> hit 없음
    df = _struct_df("U3")
    _inject_ma(df, 10, "dt", 20, kind="LH")          # 요구는 HH
    _inject_wave(df, "large", "dt", 22, kind="LH")
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-4c-b" for h in hits)


def test_pivot_match_confirm_mismatch_hit():
    # 첫 피봇(10)=U1, 확정 봉(20·25)=비-U1 → hit (수정1 확정봉 기준이면 무HIT).
    df = _struct_df("U1")
    _set_row(df, 20, {"close": 50, "MA5": 60, "MA10": 40, "MA20": 70, "MA60": 30, "MA120": 90, "MA240": 20})
    _set_row(df, 25, {"close": 50, "MA5": 60, "MA10": 40, "MA20": 70, "MA60": 30, "MA120": 90, "MA240": 20})
    _inject_wave(df, "mid", "dt", 20)
    _inject_wave(df, "small", "tt", 25)
    _inject_wave_first_pos(df, "mid", "dt", 20, 10)
    _inject_wave_first_pos(df, "small", "tt", 25, 22)
    hits = evaluate_transitions(df)
    hit = next((h for h in hits if h.rule_id == "F6-4a"), None)
    assert hit is not None, "첫 피봇(10)에서 U1이므로 hit이어야 한다"
    assert hit.bar_index == IDX[25]
    assert hit.formation_bar == IDX[10]
    assert hit.structure_label == "U1"


def test_pivot_mismatch_confirm_match_no_hit():
    # 첫 피봇(20)=비-U1, 확정 봉=U1 → hit 없음.
    df = _struct_df("U1")
    _set_row(df, 20, {"close": 50, "MA5": 60, "MA10": 40, "MA20": 70, "MA60": 30, "MA120": 90, "MA240": 20})
    _inject_wave(df, "mid", "dt", 22)
    _inject_wave(df, "small", "tt", 25)
    _inject_wave_first_pos(df, "mid", "dt", 22, 20)
    _inject_wave_first_pos(df, "small", "tt", 25, 23)
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-4a" for h in hits)


def test_pivot_min_later_confirm_earlier_pivot():
    # 나중 확정 원자의 피봇이 더 이른 경우 → formation = 그 피봇.
    df = _struct_df("U1")
    _inject_wave(df, "mid", "dt", 20)
    _inject_wave(df, "small", "tt", 25)
    _inject_wave_first_pos(df, "mid", "dt", 20, 18)
    _inject_wave_first_pos(df, "small", "tt", 25, 12)  # tt 피봇이 더 이름
    hits = evaluate_transitions(df)
    hit = next((h for h in hits if h.rule_id == "F6-4a"), None)
    assert hit is not None
    assert hit.formation_bar == IDX[12]


def test_multi_pair_one_structure_match_hit():
    # 불일치 짝(피봇18) + 일치 짝(피봇12) 공존 → hit, 대표 completion=25.
    df = _struct_df("U1")
    _set_row(df, 18, {"close": 50, "MA5": 60, "MA10": 40, "MA20": 70, "MA60": 30, "MA120": 90, "MA240": 20})
    _inject_wave(df, "mid", "dt", 18)
    _inject_wave(df, "mid", "dt", 22)
    _inject_wave(df, "small", "tt", 20)
    _inject_wave(df, "small", "tt", 25)
    _inject_wave_first_pos(df, "mid", "dt", 18, 18)
    _inject_wave_first_pos(df, "mid", "dt", 22, 12)
    _inject_wave_first_pos(df, "small", "tt", 20, 19)
    _inject_wave_first_pos(df, "small", "tt", 25, 23)
    hits = evaluate_transitions(df)
    hit = next((h for h in hits if h.rule_id == "F6-4a"), None)
    assert hit is not None
    assert hit.bar_index == IDX[25]
    assert hit.formation_bar == IDX[12]


def test_per_rule_window_wave_miss_ma_hit():
    # 원자 간격 60봉: wave-wave(24) 미짝, MA(96) 짝.
    ma_win = WAVE_ENERGY_PARAMS["transition_recent_bars_ma"]
    wave_win = WAVE_ENERGY_PARAMS["transition_recent_bars"]
    n = 120
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame(index=idx)
    for col, val in STRUCT_ROWS["D3"].items():
        df[col] = float(val)
    _inject_wave(df, "mid", "db", 59)
    _inject_wave(df, "small", "tb", 119)
    _inject_ma(df, 5, "db", 59)
    _inject_ma_first_pos(df, 5, "db", 59, 59)
    _inject_wave(df, "large", "tb", 119)
    _inject_wave_first_pos(df, "large", "tb", 119, 119)
    assert n - 59 > wave_win
    assert n - 59 <= ma_win
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-5a" for h in hits)
    hit = next((h for h in hits if h.rule_id == "F6-5c-a"), None)
    assert hit is not None, "MA 윈도 96에서 60봉 간격 짝이 성립해야 한다"
    assert hit.bar_index == idx[119]


def test_window_boundary_no_hit():
    # 한 신호가 transition_recent_bars(24) 밖(pos 0) -> hit 없음
    recent = WAVE_ENERGY_PARAMS["transition_recent_bars"]
    assert N - 0 > recent  # pos 0은 마지막 24봉 밖
    df = _struct_df("U1")
    _inject_wave(df, "mid", "dt", 0)        # 윈도 밖
    _inject_wave(df, "small", "tt", 25)
    hits = evaluate_transitions(df)
    assert all(h.rule_id != "F6-4a" for h in hits)


def test_headline_prefers_transition_over_trend():
    """trend hit(①②)과 transition hit(④⑤)이 동시 존재하면 headline은 transition."""
    # D1 구조: 60>120>240 -> MA120>MA240 -> 레짐 UP, close<MA20 이므로 추세 규칙은 별개.
    # F6-5a(D1) transition을 만들고, 동시에 소파동 db(trend 후보)도 주입한다.
    df = _struct_df("D1")
    _scenario_F6_5a(df)                       # 중파동 db + 소파동 tb -> F6-5a
    _inject_wave(df, "small", "db", 21, kind="HL")  # trend 후보 신호

    report = evaluate_dynamics(df)
    assert report.transition_hits, "transition hit이 있어야 한다"
    assert report.headline is not None and hasattr(report.headline, "bullish"), "headline은 transition이어야 한다"
    assert report.headline.rule_id == "F6-5a"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL TRANSITION RULE TESTS PASSED")
