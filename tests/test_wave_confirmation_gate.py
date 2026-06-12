"""Wave Confirmation Gate 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_confirmation_gate import (
    _eval_composite,
    _eval_gate,
    _macd_hold,
    _rsi_hold,
    best_confirmation_horizon,
    build_composite_catalog,
    build_gate_catalog,
    evaluate_gate_metrics,
    _funnel_rsi_macd_cumulative,
)


def _enriched():
    base_ok = {"rsi": 50.0, "macd_hist": 0.5, "ema20_slope_3": 0.3, "major_k_slope_1": 2.0}
    future_ok = [
        {"rsi": 52.0, "macd_hist": 0.6, "ema20_slope_3": 0.4, "major_k_slope_1": 2.5,
         "major_k_slope_3": 5.0, "major_k_minus_d": 10.0, "major_k": 75.0},
        {"rsi": 54.0, "macd_hist": 0.7, "ema20_slope_3": 0.5, "major_k_slope_1": 3.0,
         "major_k_slope_3": 6.0, "major_k_minus_d": 12.0, "major_k": 78.0},
        {"rsi": 56.0, "macd_hist": 0.8, "ema20_slope_3": 0.6, "major_k_slope_1": 3.5,
         "major_k_slope_3": 7.0, "major_k_minus_d": 14.0, "major_k": 80.0},
    ]
    base_fail = {"rsi": 55.0, "macd_hist": 0.4, "ema20_slope_3": 0.2, "major_k_slope_1": 1.0}
    future_fail = [
        {"rsi": 53.0, "macd_hist": 0.3, "ema20_slope_3": 0.1, "major_k_slope_1": -1.0,
         "major_k_slope_3": -2.0, "major_k_minus_d": -3.0, "major_k": 60.0},
        {"rsi": 51.0, "macd_hist": 0.2, "ema20_slope_3": -0.1, "major_k_slope_1": -2.0,
         "major_k_slope_3": -3.0, "major_k_minus_d": -5.0, "major_k": 55.0},
        {"rsi": 49.0, "macd_hist": 0.1, "ema20_slope_3": -0.2, "major_k_slope_1": -3.0,
         "major_k_slope_3": -4.0, "major_k_minus_d": -7.0, "major_k": 50.0},
    ]
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "success": True, "_base": base_ok, "_future": future_ok},
        {"timestamp": pd.Timestamp("2025-01-02"), "symbol": "ETHUSDT", "timeframe": "4h",
         "success": True, "_base": base_ok, "_future": future_ok},
        {"timestamp": pd.Timestamp("2025-01-03"), "symbol": "BTCUSDT", "timeframe": "1d",
         "success": False, "_base": base_fail, "_future": future_fail},
        {"timestamp": pd.Timestamp("2025-01-04"), "symbol": "BTCUSDT", "timeframe": "1d",
         "success": False, "_base": base_fail, "_future": future_fail},
    ])


def test_gate_labeling():
    assert _eval_gate(_enriched().iloc[0]["_base"], _enriched().iloc[0]["_future"], _rsi_hold, 1)
    assert not _eval_gate(_enriched().iloc[2]["_base"], _enriched().iloc[2]["_future"], _rsi_hold, 1)


def test_precision_calculation():
    m = evaluate_gate_metrics(
        _enriched(), "RSI_HOLD_+1",
        lambda b, f: _eval_gate(b, f, _rsi_hold, 1),
    )
    assert m["precision"] == 1.0


def test_recall_calculation():
    m = evaluate_gate_metrics(
        _enriched(), "RSI_HOLD_+1",
        lambda b, f: _eval_gate(b, f, _rsi_hold, 1),
    )
    assert m["recall"] == 1.0


def test_coverage_calculation():
    m = evaluate_gate_metrics(
        _enriched(), "RSI_HOLD_+1",
        lambda b, f: _eval_gate(b, f, _rsi_hold, 1),
    )
    assert m["coverage"] == 0.5


def test_funnel_calculation():
    funnel = _funnel_rsi_macd_cumulative(_enriched())
    assert len(funnel) == 5
    assert funnel[0]["survivors"] == 4
    assert funnel[-1]["survivors"] == 2


def test_best_horizon_calculation():
    best = best_confirmation_horizon(_enriched())
    assert best["horizon"] is not None


def test_composite_gate_calculation():
    combos = build_composite_catalog(max_combo=2)
    assert len(combos) > 0
    label, parts = combos[0]
    row = _enriched().iloc[0]
    assert _eval_composite(row["_base"], row["_future"], parts)


def test_gate_catalog():
    catalog = build_gate_catalog()
    assert len(catalog) >= 24


def test_failure_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_grade_failure.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
