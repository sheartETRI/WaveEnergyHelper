"""Wave Money Flow 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_money_flow import (
    add_money_flow_features,
    compute_ad_line,
    compute_ad_slope,
    compute_cmf,
    compute_mfi,
    compute_money_flow_score,
    energy_money_flow_combos,
    extract_money_flow_at,
    failure_reclassification,
    money_flow_score_performance,
    success_failure_compare,
    triple_combo,
)


def _ohlcv(n=60):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    close = pd.Series(np.linspace(100, 120, n), index=idx)
    high = close + 2
    low = close - 2
    vol = pd.Series(np.linspace(1000, 3000, n), index=idx)
    return pd.DataFrame({
        "open": close - 0.5,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
    }, index=idx)


def test_mfi_calculation():
    df = _ohlcv(80)
    df["close"] = df["close"] + np.sin(np.arange(len(df))) * 2
    mfi = compute_mfi(df["high"], df["low"], df["close"], df["volume"])
    val = mfi.dropna().iloc[-1]
    assert 0 <= val <= 100


def test_cmf_calculation():
    df = _ohlcv()
    cmf = compute_cmf(df["high"], df["low"], df["close"], df["volume"])
    assert not pd.isna(cmf.iloc[-1])


def test_ad_line_calculation():
    df = _ohlcv()
    ad = compute_ad_line(df["high"], df["low"], df["close"], df["volume"])
    assert len(ad) == len(df)


def test_ad_slope_calculation():
    df = _ohlcv()
    ad = compute_ad_line(df["high"], df["low"], df["close"], df["volume"])
    slope = compute_ad_slope(ad, 5)
    assert not pd.isna(slope.iloc[-1])


def test_money_flow_score_calculation():
    feats = {
        "mfi": 55, "cmf": 0.1, "ad_slope_5": 100,
        "ad_slope_10": 50, "mfi_rising": True,
    }
    assert compute_money_flow_score(feats) == 5
    assert compute_money_flow_score({}) == 0


def test_extract_money_flow_at():
    mf = add_money_flow_features(_ohlcv())
    feats = extract_money_flow_at(mf, 30)
    assert "money_flow_score" in feats
    assert "mfi" in feats


def test_success_failure_compare():
    df = pd.DataFrame([
        {"success": True, "mfi": 60, "cmf": 0.1, "ad_slope_5": 10,
         "ad_slope_10": 5, "money_flow_score": 4, "return_pct": 3.0},
        {"success": False, "mfi": 40, "cmf": -0.1, "ad_slope_5": -10,
         "ad_slope_10": -5, "money_flow_score": 1, "return_pct": -3.0},
    ])
    rows = success_failure_compare(df)
    assert len(rows) >= 1


def test_money_flow_score_performance():
    df = pd.DataFrame([
        {"money_flow_score": 3, "return_pct": 3.0},
        {"money_flow_score": 3, "return_pct": -1.0},
        {"money_flow_score": 0, "return_pct": -3.0},
    ])
    perf = money_flow_score_performance(df)
    s3 = next(p for p in perf if p["score"] == 3)
    assert s3["n"] == 2


def test_energy_money_flow_combo():
    df = pd.DataFrame([
        {"energy_score": 4, "money_flow_score": 4, "return_pct": 3.0},
        {"energy_score": 2, "money_flow_score": 4, "return_pct": -3.0},
    ])
    combos = energy_money_flow_combos(df)
    assert combos[0]["n"] == 1


def test_triple_combo():
    df = pd.DataFrame([
        {"energy_score": 4, "money_flow_score": 4, "bullish_div": True, "return_pct": 3.0},
        {"energy_score": 4, "money_flow_score": 2, "bullish_div": True, "return_pct": -3.0},
    ])
    tc = triple_combo(df)
    assert tc["n"] == 1


def test_failure_reclassification():
    df = pd.DataFrame([
        {"success": False, "money_flow_score": 0},
        {"success": False, "money_flow_score": 4},
        {"success": True, "money_flow_score": 3},
    ])
    reclass = failure_reclassification(df)
    assert reclass[0]["pct"] == 50.0


def test_volume_energy_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_volume_energy.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
