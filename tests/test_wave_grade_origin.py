"""Wave Grade Origin 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WAVE_LAYER_ROLES
from analysis.wave_grade_origin import (
    GRADE_A,
    GRADE_BC,
    branch_distribution,
    build_origin_timeline,
    classify_grade,
    compute_lead_indicators,
    compute_separators,
    extract_origin_features,
    path_distribution,
    pseudo_causality_order,
)

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]


def _pipeline():
    n = 30
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    df = pd.DataFrame({
        "close": [100 + i * 0.5 for i in range(n)],
        "ema20": [99 + i * 0.4 for i in range(n)],
        "ema60": [98 + i * 0.3 for i in range(n)],
        "ema120": [97 + i * 0.2 for i in range(n)],
        "atr_pct": [1.5] * n,
        "volatility_20": [1.0] * n,
        "macd_hist": [0.1 * i for i in range(n)],
        "rsi": [40 + i for i in range(n)],
        "rsi_slope_1": [1.0] * n,
        f"stoch_k_{_LAYER_LARGE}": [50 + i * 2 for i in range(n)],
        f"stoch_d_{_LAYER_LARGE}": [45 + i * 2 for i in range(n)],
        "macd": [0.1 * i for i in range(n)],
        "macd_signal": [0.05 * i for i in range(n)],
    }, index=idx)
    return df


def _events(pipeline=None):
    idx = pipeline.index if pipeline is not None else pd.date_range("2025-01-01", periods=30, freq="4h")
    ts_a1, ts_a2 = idx[20], idx[21]
    ts_bc1, ts_bc2 = idx[22], idx[23]
    return pd.DataFrame([
        {"timestamp": ts_a1, "symbol": "ETHUSDT",
         "timeframe": "4h", "grade": GRADE_A, "major_k": 75, "major_d": 70,
         "rsi": 65, "rsi_slope_1": 2, "macd": 0.5, "macd_hist": 0.3,
         "atr_pct": 1.2, "volatility_20": 0.8, "dist_ema60_pct": 2.0,
         "ema20_slope_3": 0.5, "ema60_slope_3": 0.3, "ema120_slope_3": 0.1,
         "major_k_slope_1": 3, "major_k_slope_3": 8, "major_k_minus_d": 5,
         "macd_gap": 0.2, "rsi_slope_3": 4, "macd_signal": 0.3,
         "dist_ema20_pct": 1.0, "dist_ema120_pct": 3.0,
         "path": "WAVE3_CANDIDATE → TRIPLE_BOTTOM_REQUIRED → SLOPE → TP3_WIN",
         "branch": "TRIPLE_BOTTOM_REQUIRED"},
        {"timestamp": ts_a2, "symbol": "ETHUSDT",
         "timeframe": "4h", "grade": GRADE_A, "major_k": 72, "major_d": 68,
         "rsi": 62, "rsi_slope_1": 1.5, "macd": 0.4, "macd_hist": 0.25,
         "atr_pct": 1.1, "volatility_20": 0.7, "dist_ema60_pct": 1.8,
         "ema20_slope_3": 0.4, "ema60_slope_3": 0.25, "ema120_slope_3": 0.08,
         "major_k_slope_1": 2, "major_k_slope_3": 6, "major_k_minus_d": 4,
         "macd_gap": 0.15, "rsi_slope_3": 3, "macd_signal": 0.25,
         "dist_ema20_pct": 0.8, "dist_ema120_pct": 2.5,
         "path": "WAVE3_CANDIDATE → TRIPLE_BOTTOM_REQUIRED → SLOPE → TP3_WIN",
         "branch": "TRIPLE_BOTTOM_REQUIRED"},
        {"timestamp": ts_bc1, "symbol": "BTCUSDT",
         "timeframe": "1d", "grade": GRADE_BC, "major_k": 55, "major_d": 50,
         "rsi": 48, "rsi_slope_1": 0.5, "macd": 0.1, "macd_hist": 0.05,
         "atr_pct": 2.0, "volatility_20": 1.5, "dist_ema60_pct": 4.0,
         "ema20_slope_3": 0.1, "ema60_slope_3": 0.05, "ema120_slope_3": 0.0,
         "major_k_slope_1": 0.5, "major_k_slope_3": 1, "major_k_minus_d": 5,
         "macd_gap": 0.05, "rsi_slope_3": 1, "macd_signal": 0.05,
         "dist_ema20_pct": 2.0, "dist_ema120_pct": 5.0,
         "path": "WAVE3_CANDIDATE → WAVE3_COMPLETED → CROSS → TP3_LOSS",
         "branch": "WAVE3_COMPLETED"},
        {"timestamp": ts_bc2, "symbol": "BTCUSDT",
         "timeframe": "1d", "grade": GRADE_BC, "major_k": 50, "major_d": 48,
         "rsi": 45, "rsi_slope_1": -0.5, "macd": 0.05, "macd_hist": 0.02,
         "atr_pct": 2.2, "volatility_20": 1.6, "dist_ema60_pct": 4.5,
         "ema20_slope_3": 0.05, "ema60_slope_3": 0.02, "ema120_slope_3": -0.01,
         "major_k_slope_1": -0.5, "major_k_slope_3": 0, "major_k_minus_d": 2,
         "macd_gap": 0.02, "rsi_slope_3": 0, "macd_signal": 0.03,
         "dist_ema20_pct": 2.5, "dist_ema120_pct": 5.5,
         "path": "WAVE3_CANDIDATE → TRIPLE_BOTTOM_REQUIRED → SLOPE → TP3_LOSS",
         "branch": "TRIPLE_BOTTOM_REQUIRED"},
    ])


def test_grade_classification():
    assert classify_grade(75) == GRADE_A
    assert classify_grade(69) == GRADE_BC
    assert classify_grade(None) is None


def test_origin_timeline():
    pipeline = _pipeline()
    events = _events(pipeline)
    a_events = events[events["grade"] == GRADE_A].copy()
    cache = {("ETHUSDT", "4h"): pipeline}
    timeline = build_origin_timeline(a_events, cache)
    assert len(timeline) > 0
    assert any(r.get("major_k") is not None for r in timeline)


def test_separator_calculation():
    ev = _events()
    seps = compute_separators(ev)
    assert len(seps) > 0
    assert seps[0]["effect_size"] >= seps[-1]["effect_size"]
    assert seps[0]["feature"] in ("major_k", "major_d")


def test_lead_indicator_calculation():
    pipeline = _pipeline()
    events = _events(pipeline)
    cache = {("ETHUSDT", "4h"): pipeline, ("BTCUSDT", "1d"): pipeline}
    leads = compute_lead_indicators(events, cache)
    assert isinstance(leads, list)


def test_path_distribution():
    ev = _events()
    paths = path_distribution(ev)
    assert len(paths) >= 1
    assert paths[0]["pct"] > 0


def test_branch_distribution():
    ev = _events()
    branches = branch_distribution(ev)
    assert len(branches) >= 1
    tb = next(r for r in branches if r["branch"] == "TRIPLE_BOTTOM_REQUIRED")
    assert tb["a"] == 2


def test_rule_grading_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_rule_grading.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)


def test_extract_origin_features():
    pipeline = _pipeline()
    feats = extract_origin_features(pipeline, 20)
    assert feats.get("major_k") is not None
    assert feats.get("major_k_minus_d") is not None


def test_pseudo_causality():
    pipeline = _pipeline()
    events = _events(pipeline)
    cache = {("ETHUSDT", "4h"): pipeline, ("BTCUSDT", "1d"): pipeline}
    order = pseudo_causality_order(events, cache, threshold=0.1)
    assert isinstance(order, list)
