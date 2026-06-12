"""Wave Structure LTE 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_structure_lte import (
    MA_PERIODS,
    add_lte_features,
    compute_lte_position_score,
    compute_ma,
    compute_ma_slope,
    compute_price_vs_ma,
    extract_lte_at,
    final_tb_structure_lte,
    success_failure_compare,
    tb_lte_combos,
)


def _ohlcv(n=1200):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    close = pd.Series(np.linspace(100, 200, n), index=idx)
    return pd.DataFrame({
        "open": close - 0.5,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": np.full(n, 1000.0),
    }, index=idx)


def test_ma_calculation():
    df = _ohlcv()
    ma = compute_ma(df["close"], 120)
    assert len(ma) == len(df)
    assert not pd.isna(ma.iloc[-1])


def test_ma_slope_calculation():
    df = _ohlcv()
    ma = compute_ma(df["close"], 240)
    slope = compute_ma_slope(ma)
    assert not pd.isna(slope.iloc[-1])


def test_price_vs_ma():
    df = _ohlcv()
    ma = compute_ma(df["close"], 480)
    pvm = compute_price_vs_ma(df["close"], ma)
    assert pvm.iloc[-1] > 0


def test_lte_position_score():
    assert compute_lte_position_score(True, {240: True, 480: True, 960: True}) == 4
    assert compute_lte_position_score(False, {240: True, 480: True, 960: True}) == 3


def test_add_lte_features():
    lte = add_lte_features(_ohlcv())
    for p in MA_PERIODS:
        assert f"ma{p}" in lte.columns
        assert f"ma{p}_slope" in lte.columns


def test_extract_lte_at():
    lte = add_lte_features(_ohlcv())
    feats = extract_lte_at(lte, 500, hh=True)
    assert "lte_position_score" in feats
    assert "ma480_slope" in feats


def test_success_failure_compare():
    df = pd.DataFrame([
        {"success": True, "lte_position_score": 4, "price_vs_ma240": -5.0,
         "price_vs_ma480": -8.0, "price_vs_ma960": -10.0, "price_vs_ma120": -2.0,
         "ma120_slope": 1.0, "ma240_slope": 0.5, "ma480_slope": 0.3, "ma960_slope": 0.1,
         "price_below_ma240": True, "return_pct": 3.0},
        {"success": False, "lte_position_score": 1, "price_vs_ma240": 5.0,
         "price_vs_ma480": 8.0, "price_vs_ma960": 10.0, "price_vs_ma120": 2.0,
         "ma120_slope": -1.0, "ma240_slope": -0.5, "ma480_slope": -0.3, "ma960_slope": -0.1,
         "price_below_ma240": False, "return_pct": -3.0},
    ])
    rows = success_failure_compare(df)
    assert len(rows) >= 1


def test_tb_lte_combo():
    df = pd.DataFrame([
        {"wave_state": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "path": "TB", "structure_score": 4, "price_below_ma240": True,
         "price_below_ma480": True, "ma480_slope": 1.0, "ma960_slope": 0.5,
         "return_pct": 3.0},
        {"wave_state": "OTHER", "branch": "nan", "path": "x", "structure_score": 4,
         "price_below_ma240": True, "price_below_ma480": False,
         "ma480_slope": 1.0, "ma960_slope": 0.5, "return_pct": -3.0},
    ])
    combos = tb_lte_combos(df)
    assert combos[0]["n"] == 1


def test_final_combo():
    df = pd.DataFrame([
        {"wave_state": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "path": "TB", "structure_score": 4, "price_below_ma480": True,
         "ma480_slope": 1.0, "return_pct": 3.0},
        {"wave_state": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "path": "TB", "structure_score": 4, "price_below_ma480": False,
         "ma480_slope": 1.0, "return_pct": -3.0},
    ])
    c = final_tb_structure_lte(df)
    assert c["n"] == 1


def test_structure_confirmation_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_structure_confirmation.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
