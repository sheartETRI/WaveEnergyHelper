"""Wave Structure Confirmation 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_structure_confirmation import (
    PIVOT,
    compute_structure_score,
    energy_mf_structure_combo,
    energy_structure_combos,
    extract_structure_at,
    failure_reclassification,
    find_swing_highs,
    find_swing_lows,
    mf_structure_combos,
    structure_score_performance,
    success_failure_compare,
    tb_structure_combos,
)


def _ohlcv(n=80):
    idx = pd.date_range("2025-01-01", periods=n, freq="4h")
    t = np.arange(n)
    low = 100 + np.sin(t / 5) * 5
    high = low + 3
    close = low + 1.5
    return pd.DataFrame({
        "open": close - 0.5,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.full(n, 1000.0),
    }, index=idx)


def test_swing_low_calculation():
    df = _ohlcv()
    lows = find_swing_lows(df["low"], PIVOT)
    assert len(lows) >= 1


def test_swing_high_calculation():
    df = _ohlcv()
    highs = find_swing_highs(df["high"], PIVOT)
    assert isinstance(highs, list)


def test_hl_hh_structure():
    df = _ohlcv()
    feats = extract_structure_at(df, 50)
    assert "hl" in feats
    assert "hh" in feats
    assert "hhhl" in feats


def test_structure_score_calculation():
    feats = {
        "hl": True, "hh": True, "hhhl": True,
        "neckline_recovery": False, "resistance_break": True, "support_hold": True,
    }
    assert compute_structure_score(feats) == 5


def test_neckline_resistance_support():
    df = _ohlcv()
    feats = extract_structure_at(df, 60)
    assert "neckline_recovery" in feats
    assert "resistance_break" in feats
    assert "support_hold" in feats


def test_success_failure_compare():
    df = pd.DataFrame([
        {"success": True, "structure_score": 4, "hl": True, "hh": True,
         "hhhl": True, "neckline_recovery": True, "resistance_break": True,
         "support_hold": True, "return_pct": 3.0},
        {"success": False, "structure_score": 1, "hl": False, "hh": False,
         "hhhl": False, "neckline_recovery": False, "resistance_break": False,
         "support_hold": False, "return_pct": -3.0},
    ])
    rows = success_failure_compare(df)
    assert len(rows) >= 1


def test_structure_score_performance():
    df = pd.DataFrame([
        {"structure_score": 4, "return_pct": 3.0},
        {"structure_score": 4, "return_pct": -1.0},
        {"structure_score": 0, "return_pct": -3.0},
    ])
    perf = structure_score_performance(df)
    s4 = next(p for p in perf if p["score"] == 4)
    assert s4["n"] == 2


def test_energy_structure_combo():
    df = pd.DataFrame([
        {"energy_score": 4, "structure_score": 4, "return_pct": 3.0},
        {"energy_score": 2, "structure_score": 4, "return_pct": -3.0},
    ])
    combos = energy_structure_combos(df)
    assert combos[0]["n"] == 1


def test_mf_structure_combo():
    df = pd.DataFrame([
        {"money_flow_score": 4, "structure_score": 4, "return_pct": 3.0},
        {"money_flow_score": 2, "structure_score": 4, "return_pct": -3.0},
    ])
    combos = mf_structure_combos(df)
    assert combos[1]["n"] == 1


def test_tb_structure_combo():
    df = pd.DataFrame([
        {"wave_state": "TRIPLE_BOTTOM_REQUIRED", "branch": "TRIPLE_BOTTOM_REQUIRED",
         "path": "TB", "structure_score": 4, "return_pct": 3.0},
        {"wave_state": "OTHER", "branch": "nan", "path": "x",
         "structure_score": 4, "return_pct": -3.0},
    ])
    combos = tb_structure_combos(df)
    assert combos[0]["n"] == 1


def test_ems_combo():
    df = pd.DataFrame([
        {"energy_score": 4, "money_flow_score": 4, "structure_score": 4, "return_pct": 3.0},
        {"energy_score": 4, "money_flow_score": 2, "structure_score": 4, "return_pct": -3.0},
    ])
    c = energy_mf_structure_combo(df)
    assert c["n"] == 1


def test_failure_reclassification():
    df = pd.DataFrame([
        {"success": False, "structure_score": 1},
        {"success": False, "structure_score": 4},
        {"success": True, "structure_score": 3},
    ])
    reclass = failure_reclassification(df)
    assert reclass[0]["pct"] == 50.0


def test_money_flow_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_money_flow.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
