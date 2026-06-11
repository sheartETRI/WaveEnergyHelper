"""실전 역학관계 공식 ①② (F6-1a~1d, F6-2a~2d) 테스트.

실행: `python -m pytest tests/test_dynamics_rules.py` 또는 `python tests/test_dynamics_rules.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WAVE_LAYER_ROLES
from analysis.dynamics_rules import (
    RULE_TABLE,
    RuleHit,
    evaluate_rule,
    evaluate_dynamics,
    _select_headline,
)

SMALL = WAVE_LAYER_ROLES["small"]   # (5,3,3)
MID = WAVE_LAYER_ROLES["mid"]       # (10,5,5)


# ---------- (a) 판정표 순수 함수 테스트 ----------

def test_eight_formulas_exact():
    assert evaluate_rule("UP", "ABOVE_MA20", "small", "db", None) == ("F6-1a", True)
    assert evaluate_rule("UP", "MA20_MA60_BAND", "small", "db", "LL") == ("F6-1b", False)
    assert evaluate_rule("UP", "MA20_MA60_BAND", "small", "db", "HL") == ("F6-1c", True)
    assert evaluate_rule("UP", "MA20_MA60_BAND", "mid", "db", None) == ("F6-1d", True)
    assert evaluate_rule("DOWN", "BELOW_MA20", "small", "dt", None) == ("F6-2a", True)
    assert evaluate_rule("DOWN", "MA20_MA60_BAND", "small", "dt", "HH") == ("F6-2b", False)
    assert evaluate_rule("DOWN", "MA20_MA60_BAND", "small", "dt", "LH") == ("F6-2c", True)
    assert evaluate_rule("DOWN", "MA20_MA60_BAND", "mid", "dt", None) == ("F6-2d", True)


def test_table_has_eight_unique_ids():
    ids = [row[5] for row in RULE_TABLE]
    assert ids == ["F6-1a", "F6-1b", "F6-1c", "F6-1d", "F6-2a", "F6-2b", "F6-2c", "F6-2d"]
    assert len(set(ids)) == 8


def test_wildcard_kind_agnostic():
    # F6-1a는 kind 무관 -> LL 입력도 매칭
    assert evaluate_rule("UP", "ABOVE_MA20", "small", "db", "LL") == ("F6-1a", True)
    assert evaluate_rule("UP", "ABOVE_MA20", "small", "db", "HL") == ("F6-1a", True)
    # F6-2a도 kind 무관
    assert evaluate_rule("DOWN", "BELOW_MA20", "small", "dt", "HH") == ("F6-2a", True)


def test_undefined_combinations_return_none():
    assert evaluate_rule("UP", "OUT_OF_SCOPE", "small", "db", None) is None
    assert evaluate_rule("UP", "ABOVE_MA20", "small", "dt", None) is None     # UP + dt
    assert evaluate_rule("UP", "ABOVE_MA20", "small", "db", "EQ") is None     # EQ 보류
    assert evaluate_rule("UP", "MA20_MA60_BAND", "small", "db", "EQ") is None
    assert evaluate_rule("DOWN", "ABOVE_MA20", "small", "dt", None) is None   # DOWN + ABOVE_MA20 미정의
    assert evaluate_rule("판단불가", "MA20_MA60_BAND", "small", "db", "HL") is None


def test_headline_priority_mid_over_small():
    ts = pd.Timestamp("2024-01-10")
    small_block = RuleHit("F6-1b", "small", "db", "LL", False, ts, "소파동 LL 불가")
    mid_allow = RuleHit("F6-1d", "mid", "db", None, True, ts, "중파동 가능")
    head = _select_headline([small_block, mid_allow], [])
    assert head.rule_id == "F6-1d"
    assert head.allowed is True


# ---------- (b)(c) 통합 테스트 (합성 df) ----------

def _make_df(n=20, regime="UP"):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame(index=idx)
    df["close"] = 50.0
    df["MA20"] = 60.0
    df["MA60"] = 40.0
    if regime == "UP":
        df["MA120"] = 110.0
        df["MA240"] = 100.0
    else:  # DOWN: MA20/MA60 대칭 배치 (BAND = MA20 <= close < MA60)
        df["MA20"] = 40.0
        df["MA60"] = 60.0
        df["MA120"] = 100.0
        df["MA240"] = 110.0
    return df


def _put_signal(df, suffix, pattern, kind, pos):
    df[f"stoch_{pattern}_{suffix}"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[f"stoch_{pattern}_kind_{suffix}"] = pd.Series(pd.NA, index=df.index, dtype="object")
    df.iloc[pos, df.columns.get_loc(f"stoch_{pattern}_{suffix}")] = 50.0
    df.iloc[pos, df.columns.get_loc(f"stoch_{pattern}_kind_{suffix}")] = kind
    return df


def test_integration_up_F6_1c():
    df = _make_df(regime="UP")               # close=50, MA20=60, MA60=40 -> BAND, MA120>MA240 -> UP
    df = _put_signal(df, SMALL, "db", "HL", pos=19)
    rep = evaluate_dynamics(df)
    assert rep.regime == "UP"
    assert rep.candle_zone == "MA20_MA60_BAND"
    assert any(h.rule_id == "F6-1c" for h in rep.hits)
    assert rep.headline is not None and rep.headline.rule_id == "F6-1c" and rep.headline.allowed is True


def test_integration_down_F6_2c():
    df = _make_df(regime="DOWN")             # close=50, MA20=40, MA60=60 -> BAND, MA120<MA240 -> DOWN
    df = _put_signal(df, SMALL, "dt", "LH", pos=18)
    rep = evaluate_dynamics(df)
    assert rep.regime == "DOWN"
    assert rep.candle_zone == "MA20_MA60_BAND"
    assert rep.headline is not None and rep.headline.rule_id == "F6-2c" and rep.headline.allowed is True


def test_evaluation_at_confirm_bar_not_last_bar():
    # 확정 봉(15)은 BAND, 마지막 봉(19)은 ABOVE_MA20 -> rule_id는 확정 봉 기준 F6-1c
    df = _make_df(regime="UP")
    df.iloc[19, df.columns.get_loc("close")] = 200.0   # 마지막 봉만 MA20 위
    df = _put_signal(df, SMALL, "db", "HL", pos=15)
    rep = evaluate_dynamics(df)
    assert rep.candle_zone == "ABOVE_MA20"             # 헤더(마지막 봉)는 ABOVE
    assert len(rep.hits) == 1
    assert rep.hits[0].rule_id == "F6-1c"              # 확정 봉(BAND) 기준
    assert rep.headline.rule_id == "F6-1c"


def test_mid_beats_small_in_report():
    df = _make_df(regime="UP")
    df = _put_signal(df, SMALL, "db", "LL", pos=18)    # F6-1b 불가
    df = _put_signal(df, MID, "db", "LL", pos=19)      # F6-1d 가능 (kind 무관)
    rep = evaluate_dynamics(df)
    ids = {h.rule_id for h in rep.hits}
    assert {"F6-1b", "F6-1d"}.issubset(ids)
    assert rep.headline.rule_id == "F6-1d" and rep.headline.allowed is True


def test_no_pattern_means_no_hits():
    df = _make_df(regime="UP")
    rep = evaluate_dynamics(df)
    assert rep.hits == [] and rep.headline is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL DYNAMICS RULES TESTS PASSED")
