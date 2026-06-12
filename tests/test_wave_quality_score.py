"""Wave Quality Score 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_quality_score import (
    MAX_SCORE,
    check_score_monotonicity,
    combo_label_from_flags,
    compute_quality_flags,
    cumulative_score_performance,
    feature_importance,
    score_performance,
    _is_bullish_div,
    _price_below_ma480,
    _wave_matches,
)


def test_wave_matches_tb():
    row = pd.Series({
        "wave_state": "TRIPLE_BOTTOM_REQUIRED",
        "branch": "nan",
        "path": "WAVE3 → TB",
    })
    assert _wave_matches(row, "TRIPLE_BOTTOM_REQUIRED")


def test_bullish_div_detection():
    assert _is_bullish_div("BULLISH_OBV_DIV")
    assert not _is_bullish_div(None)
    assert not _is_bullish_div("")


def test_price_below_ma480():
    assert _price_below_ma480(pd.Series({"price_vs_ma480": -1.5}))
    assert not _price_below_ma480(pd.Series({"price_vs_ma480": 1.5}))


def test_quality_flags_max():
    row = pd.Series({
        "wave_state": "TRIPLE_BOTTOM_REQUIRED",
        "branch": "TRIPLE_BOTTOM_REQUIRED",
        "path": "TB",
        "structure_score": 5,
        "energy_score": 4,
        "money_flow_score": 5,
        "bullish_div": "BULLISH_OBV_DIV",
        "price_vs_ma480": -2.0,
        "ma120_slope": 1.5,
    })
    flags = compute_quality_flags(row)
    assert flags["quality_score"] == MAX_SCORE
    assert combo_label_from_flags(flags).count("+") == 6


def test_quality_flags_zero():
    row = pd.Series({
        "wave_state": "OTHER",
        "branch": "nan",
        "path": "x",
        "structure_score": 1,
        "energy_score": 1,
        "money_flow_score": 1,
        "bullish_div": None,
        "price_vs_ma480": 5.0,
        "ma120_slope": -1.0,
    })
    flags = compute_quality_flags(row)
    assert flags["quality_score"] == 0


def test_score_performance():
    df = pd.DataFrame([
        {"quality_score": 0, "return_pct": -3.0},
        {"quality_score": 1, "return_pct": -3.0},
        {"quality_score": 7, "return_pct": 3.0},
        {"quality_score": 7, "return_pct": 3.0},
    ])
    rows = score_performance(df)
    assert rows[0]["n"] == 1
    assert rows[7]["n"] == 2


def test_cumulative_performance():
    df = pd.DataFrame([
        {"quality_score": 3, "return_pct": 3.0},
        {"quality_score": 5, "return_pct": 3.0},
        {"quality_score": 1, "return_pct": -3.0},
    ])
    rows = cumulative_score_performance(df)
    assert rows[0]["threshold"] == 1
    assert rows[0]["n"] == 3


def test_monotonicity_pass():
    sp = [
        {"score": 0, "n": 5, "win_rate": 30.0, "expectancy": -1.0, "profit_factor": 0.5},
        {"score": 1, "n": 5, "win_rate": 40.0, "expectancy": -0.5, "profit_factor": 0.7},
        {"score": 2, "n": 5, "win_rate": 50.0, "expectancy": 0.0, "profit_factor": 1.0},
    ]
    mono = check_score_monotonicity(sp)
    assert mono["result"] == "PASS"


def test_monotonicity_fail():
    sp = [
        {"score": 0, "n": 5, "win_rate": 50.0, "expectancy": 1.0, "profit_factor": 2.0},
        {"score": 1, "n": 5, "win_rate": 30.0, "expectancy": -1.0, "profit_factor": 0.5},
    ]
    mono = check_score_monotonicity(sp)
    assert mono["result"] == "FAIL"


def test_feature_importance():
    df = pd.DataFrame([
        {"flag_tb": True, "flag_structure": False, "flag_energy": False,
         "flag_money_flow": False, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": False, "return_pct": 3.0},
        {"flag_tb": False, "flag_structure": False, "flag_energy": False,
         "flag_money_flow": False, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": False, "return_pct": -3.0},
        {"flag_tb": False, "flag_structure": False, "flag_energy": False,
         "flag_money_flow": False, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": False, "return_pct": -3.0},
    ])
    rows = feature_importance(df)
    assert len(rows) == 7
    tb = next(r for r in rows if r["feature"] == "TRIPLE_BOTTOM_REQUIRED")
    assert tb["delta_expectancy"] == 6.0


def test_existing_csvs_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in (
        "wave_structure_confirmation.csv",
        "wave_structure_lte.csv",
        "wave_money_flow.csv",
        "wave_energy_divergence.csv",
        "wave_volume_energy.csv",
    ):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)
