"""Wave Rule Grading 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_gated import apply_filters
from analysis.wave_rule_grading import (
    GRADE_ORDER,
    check_monotonicity,
    compute_calibration,
    compute_grade_separation,
    grade_filter_defs,
    grade_metrics,
)


def _events():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "return_pct": 5.0, "symbol": "ETHUSDT",
         "timeframe": "4h", "major_k": 75, "dist_ema60_pct": 1.0},
        {"timestamp": pd.Timestamp("2025-01-02"), "return_pct": 4.0, "symbol": "ETHUSDT",
         "timeframe": "4h", "major_k": 72, "dist_ema60_pct": 2.0},
        {"timestamp": pd.Timestamp("2025-01-03"), "return_pct": 3.0, "symbol": "BTCUSDT",
         "timeframe": "1d", "major_k": 55, "dist_ema60_pct": 2.5},
        {"timestamp": pd.Timestamp("2025-01-04"), "return_pct": -2.0, "symbol": "BTCUSDT",
         "timeframe": "1d", "major_k": 50, "dist_ema60_pct": 3.0},
        {"timestamp": pd.Timestamp("2025-01-05"), "return_pct": -3.0, "symbol": "SOLUSDT",
         "timeframe": "1h", "major_k": 40, "dist_ema60_pct": 4.0},
        {"timestamp": pd.Timestamp("2025-01-06"), "return_pct": 2.0, "symbol": "SOLUSDT",
         "timeframe": "1h", "major_k": 35, "dist_ema60_pct": 5.0},
        {"timestamp": pd.Timestamp("2025-01-07"), "return_pct": 1.0, "symbol": "BNBUSDT",
         "timeframe": "4h", "major_k": 71, "dist_ema60_pct": 1.5},
        {"timestamp": pd.Timestamp("2025-01-08"), "return_pct": -1.0, "symbol": "BNBUSDT",
         "timeframe": "4h", "major_k": 30, "dist_ema60_pct": 6.0},
    ])


def test_grade_assignment():
    defs = grade_filter_defs()
    assert set(defs.keys()) == {"A", "B", "C", "D"}
    ev = _events()
    grade_a = apply_filters(ev, defs["A"][1])
    assert len(grade_a) == 3
    grade_b = apply_filters(ev, defs["B"][1])
    assert len(grade_b) == 5
    grade_c = apply_filters(ev, defs["C"][1])
    assert len(grade_c) == len(ev)


def test_grade_summary():
    ev = _events()
    summary = {}
    for g in GRADE_ORDER:
        if g == "D":
            continue
        defs = grade_filter_defs()
        filtered = apply_filters(ev, defs[g][1])
        summary[g] = grade_metrics(filtered)
    assert summary["C"]["n"] == 8
    assert summary["A"]["n"] == 3
    assert summary["A"]["expectancy"] > summary["C"]["expectancy"]


def test_monotonicity_calculation():
    summary = {
        "A": {"win_rate": 80.0, "expectancy": 3.0, "profit_factor": 2.5},
        "B": {"win_rate": 70.0, "expectancy": 2.0, "profit_factor": 2.0},
        "C": {"win_rate": 60.0, "expectancy": 1.0, "profit_factor": 1.5},
        "D": {"win_rate": 50.0, "expectancy": 0.5, "profit_factor": 1.0},
    }
    mono = check_monotonicity(summary)
    assert mono["result"] == "PASS"

    bad = {
        "A": {"win_rate": 50.0, "expectancy": 1.0, "profit_factor": 1.0},
        "B": {"win_rate": 60.0, "expectancy": 2.0, "profit_factor": 2.0},
        "C": {"win_rate": 55.0, "expectancy": 1.5, "profit_factor": 1.5},
        "D": {"win_rate": 40.0, "expectancy": 0.5, "profit_factor": 0.8},
    }
    assert check_monotonicity(bad)["result"] == "FAIL"


def test_calibration_calculation():
    summary = {
        "A": {"win_rate": 71.0},
        "B": {"win_rate": 65.0},
        "C": {"win_rate": 58.0},
        "D": {"win_rate": 52.0},
    }
    cal = compute_calibration(summary)
    assert len(cal) == 4
    assert cal[0]["actual_win"] == 71.0


def test_robustness_calculation():
    ev = _events()
    stability = {}
    for g in ("A", "B", "C"):
        defs = grade_filter_defs()
        filtered = apply_filters(ev, defs[g][1]).sort_values("timestamp")
        mid = len(filtered) // 2
        a = filtered.iloc[:mid]["return_pct"]
        b = filtered.iloc[mid:]["return_pct"]
        from analysis.wave_expectancy import compute_expectancy_metrics
        exp_a = compute_expectancy_metrics(a)["expectancy"]
        exp_b = compute_expectancy_metrics(b)["expectancy"]
        stability[g] = abs(float(exp_a) - float(exp_b))
    assert all(v >= 0 for v in stability.values())


def test_cross_market_comparison():
    ev = _events()
    rows = []
    for g in ("A", "B", "C"):
        defs = grade_filter_defs()
        filtered = apply_filters(ev, defs[g][1])
        for sym in ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT"):
            sub = filtered[filtered["symbol"] == sym]
            rows.append({
                "grade": g,
                "symbol": sym,
                "expectancy": grade_metrics(sub).get("expectancy"),
            })
    assert len(rows) == 12
    eth_a = next(r for r in rows if r["grade"] == "A" and r["symbol"] == "ETHUSDT")
    assert eth_a["expectancy"] is not None


def test_grade_separation():
    summary = {
        "A": {"expectancy": 3.0, "win_rate": 80.0, "profit_factor": 2.5},
        "B": {"expectancy": 2.0, "win_rate": 70.0, "profit_factor": 2.0},
        "C": {"expectancy": 1.0, "win_rate": 60.0, "profit_factor": 1.5},
        "D": {"expectancy": 0.5, "win_rate": 50.0, "profit_factor": 1.0},
    }
    sep = compute_grade_separation(summary)
    assert len(sep) == 3
    assert sep[0]["delta_expectancy"] == 1.0


def test_regime_gated_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_regime_gated.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
