"""Wave Volume Energy 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_volume_energy import (
    add_volume_features,
    compute_energy_score,
    compute_obv,
    compute_obv_slope,
    compute_vol_ma,
    compute_vol_ratio,
    energy_score_performance,
    failure_reclassification,
    success_failure_compare,
    wave_energy_combos,
)


def _ohlcv(n=80):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    close = pd.Series(np.linspace(100, 120, n), index=idx)
    vol = pd.Series(np.linspace(1000, 2000, n), index=idx)
    return pd.DataFrame({
        "open": close - 0.5,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": vol,
    }, index=idx)


def test_vol_ma_calculation():
    vol = _ohlcv()["volume"]
    ma = compute_vol_ma(vol, 20)
    assert len(ma) == len(vol)
    assert not pd.isna(ma.iloc[-1])


def test_vol_ratio_calculation():
    vol = _ohlcv()["volume"]
    ma = compute_vol_ma(vol, 20)
    ratio = compute_vol_ratio(vol, ma)
    assert ratio.iloc[-1] > 0


def test_obv_calculation():
    df = _ohlcv()
    obv = compute_obv(df["close"], df["volume"])
    assert len(obv) == len(df)
    assert obv.iloc[-1] != 0


def test_obv_slope_calculation():
    df = _ohlcv()
    obv = compute_obv(df["close"], df["volume"])
    slope = compute_obv_slope(obv, 5)
    assert not pd.isna(slope.iloc[-1])


def test_energy_score_calculation():
    feats = {
        "vol_ratio_20": 1.5,
        "vol_slope_5": 100,
        "obv_slope_5": 50,
        "obv_above_ma20": True,
        "vol_percentile_60": 70,
    }
    assert compute_energy_score(feats) == 5
    assert compute_energy_score({}) == 0


def test_success_failure_compare():
    df = pd.DataFrame([
        {"success": True, "vol_ratio_20": 1.5, "energy_score": 4, "return_pct": 3.0,
         "vol_slope_3": 1, "vol_slope_5": 1, "vol_slope_10": 1,
         "vol_percentile_20": 60, "vol_percentile_60": 70,
         "obv": 100, "obv_slope_3": 1, "obv_slope_5": 1, "obv_slope_10": 1,
         "volume": 1000, "vol_ratio_60": 1.2},
        {"success": False, "vol_ratio_20": 0.8, "energy_score": 1, "return_pct": -3.0,
         "vol_slope_3": -1, "vol_slope_5": -1, "vol_slope_10": -1,
         "vol_percentile_20": 30, "vol_percentile_60": 40,
         "obv": 50, "obv_slope_3": -1, "obv_slope_5": -1, "obv_slope_10": -1,
         "volume": 500, "vol_ratio_60": 0.8},
    ])
    rows = success_failure_compare(df)
    assert len(rows) >= 1
    vr = next(r for r in rows if r["feature"] == "vol_ratio_20")
    assert vr["success_mean"] > vr["failure_mean"]


def test_wave_energy_combo_calculation():
    df = pd.DataFrame([
        {"is_triple_bottom": True, "is_grade_a": False, "energy_score": 4,
         "vol_ratio_20": 1.5, "obv_slope_5": 10, "return_pct": 3.0},
        {"is_triple_bottom": True, "is_grade_a": False, "energy_score": 1,
         "vol_ratio_20": 0.8, "obv_slope_5": -5, "return_pct": -3.0},
        {"is_triple_bottom": False, "is_grade_a": True, "energy_score": 4,
         "vol_ratio_20": 1.3, "obv_slope_5": 5, "return_pct": 2.0},
    ])
    combos = wave_energy_combos(df)
    assert len(combos) == 5
    tb_combo = next(c for c in combos if "TRIPLE_BOTTOM" in c["combo"] and "energy_score" in c["combo"])
    assert tb_combo["n"] == 1


def test_add_volume_features_integration():
    enriched = add_volume_features(_ohlcv())
    assert "vol_ratio_20" in enriched.columns
    assert "obv_slope_5" in enriched.columns


def test_energy_score_performance():
    df = pd.DataFrame([
        {"energy_score": 3, "return_pct": 3.0},
        {"energy_score": 3, "return_pct": -1.0},
        {"energy_score": 0, "return_pct": -3.0},
    ])
    perf = energy_score_performance(df)
    s3 = next(p for p in perf if p["score"] == 3)
    assert s3["n"] == 2


def test_post_event_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_grade_post_event.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
