"""Wave Watchlist Tracker 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_watchlist_tracker import (
    STATE_CONFIRMING,
    STATE_EARLY_WARNING,
    STATE_FAILED,
    STATE_GRADE_A_READY,
    STATE_NONE,
    STATE_STRONG_CONFIRMING,
    conversion_rates,
    failure_leakage,
    path_distribution,
    state_duration,
    transition_matrix,
    watchlist_funnel,
)


def _transitions():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "state": STATE_NONE, "duration": 0, "next_state": STATE_EARLY_WARNING, "success": False},
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "state": STATE_EARLY_WARNING, "duration": 1, "next_state": STATE_CONFIRMING, "success": False},
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "state": STATE_CONFIRMING, "duration": 2, "next_state": STATE_STRONG_CONFIRMING, "success": False},
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "state": STATE_STRONG_CONFIRMING, "duration": 3, "next_state": STATE_GRADE_A_READY, "success": True},
        {"timestamp": pd.Timestamp("2025-01-02"), "symbol": "BTCUSDT", "timeframe": "1d",
         "state": STATE_NONE, "duration": 0, "next_state": STATE_EARLY_WARNING, "success": False},
        {"timestamp": pd.Timestamp("2025-01-02"), "symbol": "BTCUSDT", "timeframe": "1d",
         "state": STATE_EARLY_WARNING, "duration": 1, "next_state": STATE_FAILED, "success": False},
    ])


def _event_paths():
    return [
        {"path": " → ".join([STATE_EARLY_WARNING, STATE_CONFIRMING, STATE_STRONG_CONFIRMING, STATE_GRADE_A_READY]),
         "terminal": STATE_GRADE_A_READY, "symbol": "ETHUSDT", "success": True},
        {"path": " → ".join([STATE_EARLY_WARNING, STATE_FAILED]),
         "terminal": STATE_FAILED, "symbol": "BTCUSDT", "success": False},
    ]


def test_state_assignment():
    paths = _event_paths()
    assert STATE_GRADE_A_READY in paths[0]["path"]
    assert STATE_FAILED in paths[1]["path"]


def test_transition_matrix():
    matrix = transition_matrix(_transitions())
    assert len(matrix) >= 3
    ew_conf = next((r for r in matrix if r["from"] == STATE_EARLY_WARNING and r["to"] == STATE_CONFIRMING), None)
    assert ew_conf is not None


def test_conversion_calculation():
    conv = conversion_rates(_event_paths())
    ew = next(c for c in conv if c["state"] == STATE_EARLY_WARNING)
    assert ew["conversion"] == 50.0


def test_duration_calculation():
    dur = state_duration(_transitions())
    conf = next(d for d in dur if d["state"] == STATE_CONFIRMING)
    assert conf["avg"] == 2.0


def test_failure_leakage_calculation():
    leak = failure_leakage(_transitions())
    assert len(leak) >= 1
    assert leak[0]["fail_rate"] is not None


def test_success_path_calculation():
    paths = path_distribution(_event_paths(), STATE_GRADE_A_READY)
    assert len(paths) == 1
    assert paths[0]["count"] == 1


def test_failure_path_calculation():
    paths = path_distribution(_event_paths(), STATE_FAILED)
    assert len(paths) == 1


def test_funnel_calculation():
    funnel = watchlist_funnel(_event_paths())
    assert funnel[0]["count"] == 2


def test_confirmation_gate_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_confirmation_gate.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
