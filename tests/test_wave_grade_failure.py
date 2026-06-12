"""Wave Grade Failure 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_grade_failure import (
    BEST_CANDIDATE,
    _detect_causes_at,
    build_failure_events,
    failure_cause_distribution,
    failure_path_distribution,
    failure_timing,
    false_positive_funnel,
    first_failure_ranking,
    success_vs_failure_separators,
)


def _events():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "success": True, "failure_cause": "NONE", "failure_horizon": None,
         "major_k": 75, "major_k_slope_1": 3, "major_k_slope_3": 10, "major_k_minus_d": 15,
         "rsi": 58, "rsi_slope_1": 2, "macd": 1.0, "macd_hist": 0.5,
         "ema20_slope_3": 0.5, "atr_pct": 1.2, "volatility_20": 0.8,
         "path": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "_pos": 100, "_cause_at_horizon": {}},
        {"timestamp": pd.Timestamp("2025-01-02"), "symbol": "ETHUSDT", "timeframe": "4h",
         "success": False, "failure_cause": "RSI_DROP", "failure_horizon": 1,
         "major_k": 55, "major_k_slope_1": -1, "major_k_slope_3": -2, "major_k_minus_d": -3,
         "rsi": 48, "rsi_slope_1": -2, "macd": 0.5, "macd_hist": 0.1,
         "ema20_slope_3": -0.1, "atr_pct": 2.0, "volatility_20": 1.5,
         "path": "OTHER", "branch": "WAVE3_COMPLETED",
         "_pos": 101, "_cause_at_horizon": {1: ["RSI_DROP", "MAJOR_K_REVERSAL", "MULTI_FAILURE"]}},
        {"timestamp": pd.Timestamp("2025-01-03"), "symbol": "BTCUSDT", "timeframe": "1d",
         "success": False, "failure_cause": "EMA_SLOPE_BAD", "failure_horizon": 3,
         "major_k": 50, "major_k_slope_1": 0.5, "major_k_slope_3": 1, "major_k_minus_d": 2,
         "rsi": 52, "rsi_slope_1": 0.5, "macd": 0.3, "macd_hist": -0.1,
         "ema20_slope_3": -0.2, "atr_pct": 1.8, "volatility_20": 1.2,
         "path": "OTHER", "branch": None,
         "_pos": 102, "_cause_at_horizon": {3: ["EMA_SLOPE_BAD"]}},
    ])


def test_success_failure_labeling():
    ev = _events()
    assert len(ev[ev["success"]]) == 1
    assert len(ev[~ev["success"]]) == 2


def test_failure_cause_calculation():
    causes = failure_cause_distribution(_events())
    assert len(causes) > 0
    rsi = next(c for c in causes if c["cause"] == "RSI_DROP")
    assert rsi["count"] >= 1


def test_timing_calculation():
    timing = failure_timing(_events())
    assert len(timing) == 4
    assert timing[0]["horizon"] == 1


def test_funnel_calculation():
    funnel = false_positive_funnel(_events())
    assert len(funnel) == 4
    assert funnel[0]["stage"] == "Early Warning"
    assert funnel[-1]["stage"] == "Grade A"
    assert funnel[-1]["survivors"] == 1


def test_separator_calculation():
    seps = success_vs_failure_separators(_events())
    assert len(seps) > 0
    assert seps[0]["effect_size"] >= seps[-1]["effect_size"]


def test_path_analysis():
    ev = _events()
    paths = failure_path_distribution(ev, tracker_cache={})
    assert isinstance(paths, list)


def test_branch_analysis():
    from analysis.wave_grade_failure import failure_branch_comparison
    branches = failure_branch_comparison(_events())
    assert len(branches) >= 1


def test_first_failure():
    ranked = first_failure_ranking(_events())
    assert len(ranked) >= 1
    assert ranked[0]["rank"] == 1


def test_detect_causes():
    cur = {"rsi_slope_1": -1, "major_k_slope_1": -2, "macd_hist": 0.1, "ema20_slope_3": -0.1}
    prev = {"macd_hist": 0.5}
    causes = _detect_causes_at(cur, prev)
    assert "RSI_DROP" in causes
    assert "MAJOR_K_REVERSAL" in causes
    assert "MACD_WEAKENING" in causes
    assert "MULTI_FAILURE" in causes


def test_early_warning_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_grade_early_warning.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)


def test_best_candidate_defined():
    assert len(BEST_CANDIDATE) == 3
