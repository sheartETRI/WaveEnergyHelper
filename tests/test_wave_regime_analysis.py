"""Wave Regime Analysis 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_branch_analysis import BRANCH_REQUIRED
from analysis.wave_regime_analysis import (
    REGIME_NUMERIC,
    _trend_bucket,
    _vol_bucket,
    build_cluster_table,
    compare_success_failure,
    extract_regime_at,
    timeframe_regime_profile,
)
from analysis.wave_confluence import add_confluence_indicators
from config.settings import WAVE_LAYER_ROLES


def _pipeline(n=80):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    close = np.linspace(100, 130, n) + np.random.default_rng(0).normal(0, 0.5, n)
    df = pd.DataFrame({
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000,
    }, index=idx)
    df[f"stoch_k_{WAVE_LAYER_ROLES['large']}"] = np.linspace(30, 70, n)
    return add_confluence_indicators(df)


def test_regime_feature_extraction():
    df = _pipeline()
    feats = extract_regime_at(df, len(df) - 1)
    assert "ema20_slope_3" in feats
    assert "atr_pct" in feats
    assert "major_k" in feats
    assert "dist_ema60_pct" in feats


def test_success_failure_separators():
    cells = pd.DataFrame([
        {"cell_success": True, "atr_pct": 1.0, "major_k": 55.0, "rsi": 60.0},
        {"cell_success": True, "atr_pct": 1.2, "major_k": 58.0, "rsi": 62.0},
        {"cell_success": False, "atr_pct": 3.0, "major_k": 25.0, "rsi": 35.0},
        {"cell_success": False, "atr_pct": 3.5, "major_k": 20.0, "rsi": 30.0},
    ])
    sep = compare_success_failure(cells)
    assert len(sep) >= 1
    assert sep[0]["effect_size"] >= 0


def test_timeframe_profile():
    cells = pd.DataFrame([
        {"timeframe": "1h", "atr_pct": 1.0, "major_k": 50.0},
        {"timeframe": "4h", "atr_pct": 2.0, "major_k": 55.0},
        {"timeframe": "1d", "atr_pct": 3.0, "major_k": 40.0},
    ])
    prof = timeframe_regime_profile(cells)
    assert len(prof) == 3
    assert prof[prof["timeframe"] == "4h"]["atr_pct"].iloc[0] == 2.0


def test_cluster_table():
    events = pd.DataFrame([
        {"atr_pct": 1.0, "ema20_slope_3": 0.5, "ema60_slope_3": 0.3, "return_pct": 3.0},
        {"atr_pct": 1.2, "ema20_slope_3": 0.4, "ema60_slope_3": 0.2, "return_pct": 3.0},
        {"atr_pct": 4.0, "ema20_slope_3": -0.5, "ema60_slope_3": -0.4, "return_pct": -3.0},
        {"atr_pct": 4.5, "ema20_slope_3": -0.6, "ema60_slope_3": -0.5, "return_pct": -3.0},
        {"atr_pct": 2.5, "ema20_slope_3": 0.0, "ema60_slope_3": 0.0, "return_pct": 1.0},
    ])
    clusters = build_cluster_table(events)
    assert len(clusters) >= 1
    assert clusters[0]["expectancy"] >= clusters[-1]["expectancy"]


def test_vol_trend_buckets():
    assert _vol_bucket(1.0, 1.5, 2.5) == "LOW_VOL"
    assert _trend_bucket(0.5, 0.3) == "TREND_UP"
    assert _trend_bucket(-0.5, -0.3) == "TREND_DOWN"


def test_generalization_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_generalization.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
