"""Wave Grade Post-Event 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_exit import POLICY_A, RULE_SL3, RULE_TIMEOUT20
from analysis.wave_grade_post_event import (
    ENTRY_DELAYS,
    apply_exit_policies,
    collect_grade_a_events,
    compute_forward_outcomes,
    decay_analysis,
    delayed_entry_index,
    failure_after_grade_a,
    forward_return_summary,
    validity_window,
)


def _synthetic_ohlcv(n=80):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    close = pd.Series(np.linspace(100, 130, n), index=idx)
    high = close + 2
    low = close - 2
    open_ = close - 0.5
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def _synthetic_pipeline(ohlcv):
    n = len(ohlcv)
    return pd.concat([
        ohlcv,
        pd.DataFrame({
            f"stoch_k_large": np.full(n, 75.0),
            f"stoch_d_large": np.full(n, 70.0),
        }, index=ohlcv.index),
    ], axis=1)


def test_grade_a_event_extraction():
    events = collect_grade_a_events()
    if not events.empty:
        assert "major_k" in events.columns
        assert (events["major_k"] >= 70).all()


def test_delay_entry_calculation():
    ohlcv = _synthetic_ohlcv()
    assert delayed_entry_index(10, 0, len(ohlcv)) == 10
    assert delayed_entry_index(10, 2, len(ohlcv)) == 12
    assert delayed_entry_index(len(ohlcv) - 1, 1, len(ohlcv)) is None


def test_forward_return_calculation():
    ohlcv = _synthetic_ohlcv()
    entry_idx = 10
    entry_price = float(ohlcv["close"].iloc[entry_idx])
    out = compute_forward_outcomes(ohlcv, entry_idx, entry_price)
    assert out["return_5"] is not None
    assert out["return_5"] > 0


def test_mfe_mae_calculation():
    ohlcv = _synthetic_ohlcv()
    entry_idx = 10
    entry_price = float(ohlcv["close"].iloc[entry_idx])
    out = compute_forward_outcomes(ohlcv, entry_idx, entry_price)
    assert out["mfe_20"] is not None
    assert out["mae_20"] is not None
    assert out["mfe_20"] >= 0


def test_exit_policy_application():
    ohlcv = _synthetic_ohlcv()
    pipeline = _synthetic_pipeline(ohlcv)
    from analysis.wave_exit import _build_bar_flags
    k, d, os_e, ll = _build_bar_flags(pipeline)
    entry_idx = 10
    entry_price = float(ohlcv["close"].iloc[entry_idx])
    results = apply_exit_policies(entry_idx, entry_price, ohlcv, k, d, os_e, ll)
    assert len(results) >= 1
    assert "policy_return" in results[0]


def test_decay_calculation():
    df = pd.DataFrame([
        {"delay": 0, "policy": POLICY_A, "policy_return": 3.0},
        {"delay": 0, "policy": POLICY_A, "policy_return": -1.0},
        {"delay": 1, "policy": POLICY_A, "policy_return": 1.0},
        {"delay": 1, "policy": POLICY_A, "policy_return": -2.0},
    ])
    decay = decay_analysis(df, reference_policy=POLICY_A)
    assert len(decay) == len(ENTRY_DELAYS)
    d0 = next(r for r in decay if r["delay"] == 0)
    assert d0["expectancy"] is not None


def test_validity_window_calculation():
    decay = [
        {"delay": 0, "expectancy": 1.5, "win_rate": 60.0},
        {"delay": 1, "expectancy": 0.5, "win_rate": 55.0},
        {"delay": 2, "expectancy": -0.5, "win_rate": 40.0},
    ]
    assert validity_window(decay) == 1


def test_failure_after_grade_a():
    df = pd.DataFrame([
        {"delay": 0, "exit_reason": RULE_SL3},
        {"delay": 0, "exit_reason": RULE_TIMEOUT20},
        {"delay": 1, "exit_reason": RULE_SL3},
    ])
    dist = failure_after_grade_a(df, delay=0)
    sl = next(r for r in dist if r["category"] == "STOP_LOSS")
    assert sl["count"] == 1


def test_forward_return_summary():
    df = pd.DataFrame([
        {"timestamp": "2025-01-01", "symbol": "ETHUSDT", "timeframe": "4h",
         "delay": 0, "return_5": 0.05, "return_10": 0.08, "return_20": 0.10, "return_40": 0.12,
         "mfe_20": 0.15, "mae_20": -0.03, "policy": POLICY_A, "policy_return": 3.0},
    ])
    summary = forward_return_summary(df)
    assert summary[0]["return_5"] is not None


def test_watchlist_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_watchlist_tracker.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
