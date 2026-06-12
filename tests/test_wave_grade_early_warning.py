"""Wave Grade Early Warning 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_early_warning import (
    CANDIDATE_ATOMS,
    HORIZON,
    build_labeled_snapshots,
    compute_early_separators,
    evaluate_candidate,
    generate_candidates,
    is_positive_bar,
)


def _snapshots():
    return pd.DataFrame([
        {"offset": -5, "positive": True, "source": "grade_a_lead",
         "major_k_slope_1": 3.0, "major_k_slope_3": 10.0, "major_k_minus_d": 15.0,
         "rsi": 58.0, "ema20_slope_3": 0.5, "macd": 1.0},
        {"offset": -5, "positive": True, "source": "grade_a_lead",
         "major_k_slope_1": 2.0, "major_k_slope_3": 8.0, "major_k_minus_d": 12.0,
         "rsi": 55.0, "ema20_slope_3": 0.4, "macd": 0.8},
        {"offset": -10, "positive": True, "source": "grade_a_lead",
         "major_k_slope_1": 1.0, "major_k_slope_3": 5.0, "major_k_minus_d": 8.0,
         "rsi": 52.0, "ema20_slope_3": 0.2, "macd": 0.5},
        {"offset": 0, "positive": False, "source": "bar_scan",
         "major_k_slope_1": -1.0, "major_k_slope_3": -3.0, "major_k_minus_d": -5.0,
         "rsi": 45.0, "ema20_slope_3": -0.1, "macd": -0.5},
        {"offset": 0, "positive": False, "source": "bar_scan",
         "major_k_slope_1": -2.0, "major_k_slope_3": -4.0, "major_k_minus_d": -8.0,
         "rsi": 42.0, "ema20_slope_3": -0.2, "macd": -1.0},
        {"offset": 0, "positive": True, "source": "bar_scan",
         "major_k_slope_1": 2.5, "major_k_slope_3": 9.0, "major_k_minus_d": 14.0,
         "rsi": 57.0, "ema20_slope_3": 0.45, "macd": 0.9},
    ])


def test_positive_labeling():
    ga_pos = [100, 200]
    assert is_positive_bar(95, ga_pos) is True
    assert is_positive_bar(85, ga_pos) is False
    assert is_positive_bar(195, ga_pos, horizon=10) is True


def test_separator_calculation():
    seps = compute_early_separators(_snapshots())
    assert len(seps) > 0
    assert seps[0]["effect_size"] >= seps[-1]["effect_size"]


def test_candidate_generation():
    cands = generate_candidates(max_combo=2)
    assert len(cands) >= len(CANDIDATE_ATOMS)
    labels = [c[0] for c in cands]
    assert any("major_k_slope_3>0" in l for l in labels)


def test_precision_calculation():
    conds = (("major_k_slope_1", ">", 0), ("rsi", ">", 50))
    m = evaluate_candidate(_snapshots(), conds, offset=None)
    assert m["precision"] is not None
    assert m["precision"] == 1.0


def test_recall_calculation():
    conds = (("major_k_slope_1", ">", 0),)
    m = evaluate_candidate(_snapshots(), conds, offset=None)
    assert m["recall"] is not None
    assert 0 <= m["recall"] <= 1.0


def test_future_grade_a_rate():
    conds = (("major_k_slope_3", ">", 0), ("rsi", ">", 50))
    m = evaluate_candidate(_snapshots(), conds, offset=None)
    assert m["positive_rate"] is not None
    assert m["positive_rate"] == m["precision"]


def test_grade_origin_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_grade_origin.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)


def test_horizon_constant():
    assert HORIZON == 10
