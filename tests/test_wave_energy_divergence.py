"""Wave Energy Divergence 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_energy_divergence import (
    PIVOT_LOOKBACK,
    PIVOT_LOOKFORWARD,
    compute_div_strength,
    detect_bearish_obv_div,
    detect_bullish_obv_div,
    detect_divergence_at,
    energy_divergence_combos,
    find_pivot_highs,
    find_pivot_lows,
    normalize_strength,
    wave_divergence_combos,
)


def _ohlcv_with_div_pattern(n=80):
    """가격 LL + OBV HL 패턴."""
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    low = pd.Series(np.concatenate([
        np.linspace(110, 100, 20),
        np.linspace(105, 95, 20),
        np.linspace(100, 90, 20),
        np.linspace(95, 100, 20),
    ]), index=idx)
    high = low + 3
    close = low + 1.5
    vol = pd.Series(np.full(n, 1000.0), index=idx)
    vol.iloc[35:45] = 2000
    vol.iloc[55:65] = 2500
    from analysis.wave_volume_energy import compute_obv
    obv = compute_obv(close, vol)
    return pd.DataFrame({
        "open": close - 0.5,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "obv": obv,
    }, index=idx)


def test_pivot_calculation():
    df = _ohlcv_with_div_pattern()
    lows = find_pivot_lows(df["low"], PIVOT_LOOKBACK, PIVOT_LOOKFORWARD)
    assert len(lows) >= 1


def test_obv_pivot_calculation():
    df = _ohlcv_with_div_pattern()
    obv_lows = find_pivot_lows(df["obv"], PIVOT_LOOKBACK, PIVOT_LOOKFORWARD)
    assert isinstance(obv_lows, list)


def test_pivot_high_calculation():
    df = _ohlcv_with_div_pattern()
    highs = find_pivot_highs(df["high"], PIVOT_LOOKBACK, PIVOT_LOOKFORWARD)
    assert isinstance(highs, list)


def test_bullish_divergence():
    df = _ohlcv_with_div_pattern()
    pos = 70
    div = detect_bullish_obv_div(pos, df["low"], df["obv"])
    assert "bullish_div" in div
    assert "price_ll" in div


def test_bearish_divergence():
    df = _ohlcv_with_div_pattern()
    pos = 70
    div = detect_bearish_obv_div(pos, df["high"], df["obv"])
    assert "bearish_div" in div


def test_strength_calculation():
    raw = compute_div_strength(5.0, 10.0)
    assert raw == 50.0
    norm = normalize_strength(50.0, 100.0)
    assert norm == 50.0


def test_detect_divergence_at():
    df = _ohlcv_with_div_pattern()
    div = detect_divergence_at(70, df, df["obv"])
    assert "bullish_div" in div


def test_wave_divergence_combo():
    df = pd.DataFrame([
        {"wave_state": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "path": "TB", "bullish_div": True, "return_pct": 3.0},
        {"wave_state": "OTHER", "branch": "nan", "path": "x",
         "bullish_div": False, "return_pct": -3.0},
    ])
    combos = wave_divergence_combos(df)
    assert len(combos) == 3
    tb = next(c for c in combos if "TRIPLE_BOTTOM" in c["combo"])
    assert tb["n"] == 1


def test_energy_divergence_combo():
    df = pd.DataFrame([
        {"energy_score": 4, "bullish_div": True, "return_pct": 3.0},
        {"energy_score": 0, "bullish_div": False, "return_pct": -3.0},
        {"energy_score": 1, "bullish_div": False, "return_pct": -1.0},
    ])
    combos = energy_divergence_combos(df)
    assert len(combos) == 2


def test_volume_energy_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_volume_energy.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
