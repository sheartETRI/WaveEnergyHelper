"""Wave Robustness Validation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_robustness_validation import (
    FILTER_DEFS,
    _apply_filter,
    _sample_tier,
    _temporal_subset,
    champion_verdict,
    leave_one_out_validation,
    minimum_sample_check,
    overfitting_risk,
    regime_robustness,
    symbol_robustness,
    temporal_split_validation,
    timeframe_robustness,
)


def _df():
    base_ts = pd.Timestamp("2025-01-01")
    rows = []
    for i in range(40):
        rows.append({
            "event_id": f"E{i}",
            "timestamp": base_ts + pd.Timedelta(days=i * 5),
            "rule": "RULE_A" if i % 3 == 0 else "RULE_C",
            "symbol": "BNBUSDT" if i % 2 == 0 else "BTCUSDT",
            "timeframe": ["1h", "4h", "1d"][i % 3],
            "regime": ["BULL", "SIDEWAYS", "BEAR"][i % 3],
            "survival_label": "SURVIVED_20" if i % 4 == 0 else "FAILED_20",
            "status": "COMPLETED",
            "return_20": 3.0 if i % 4 == 0 else -1.0,
            "return_40": 5.0 if i % 4 == 0 else -2.0,
            "structure_score": 5 if i % 2 == 0 else 3,
            "money_flow_score": 5 if i % 3 == 0 else 4,
            "energy_score": 3,
            "quality_score": 4 if i % 2 == 0 else 2,
            "watchlist_score": 30,
        })
    return pd.DataFrame(rows)


def test_filter_defs():
    assert "CHAMPION" in FILTER_DEFS
    assert FILTER_DEFS["CHAMPION"]["symbol"] == "BNBUSDT"


def test_temporal_split():
    df = _df()
    rows = temporal_split_validation(df, ("CHAMPION",))
    assert len(rows) == 5
    assert any(r["split"] == "first_half" for r in rows)


def test_timeframe_robustness():
    df = _df()
    rows = timeframe_robustness(df, ("Filter_Q",))
    assert len(rows) == 3


def test_symbol_robustness():
    df = _df()
    rows = symbol_robustness(df, ("CHAMPION",))
    assert any(r["symbol"] == "without_BNB" for r in rows)


def test_regime_robustness():
    df = _df()
    rows = regime_robustness(df, ("Filter_C",))
    assert len(rows) == 3


def test_leave_one_out():
    df = _df()
    rows = leave_one_out_validation(df, ("CHAMPION",))
    assert len(rows) == 8
    assert any(r["loo_condition"] == "remove_1h" for r in rows)


def test_sample_tier():
    assert _sample_tier(100) == "HIGH"
    assert _sample_tier(50) == "MEDIUM"
    assert _sample_tier(25) == "LOW"
    assert _sample_tier(10) == "UNSTABLE"


def test_minimum_sample():
    df = _df()
    temporal = temporal_split_validation(df, ("CHAMPION",))
    rows = minimum_sample_check(temporal)
    assert all("sample_tier" in r for r in rows)


def test_overfit_risk():
    df = _df()
    full = {"n": 30, "expectancy": 1.0}
    temporal = temporal_split_validation(df, ("CHAMPION",))
    tf = timeframe_robustness(df, ("CHAMPION",))
    reg = regime_robustness(df, ("CHAMPION",))
    sym = symbol_robustness(df, ("CHAMPION",))
    risk = overfitting_risk("CHAMPION", full, temporal, tf, reg, sym)
    assert "overfit_risk" in risk


def test_champion_verdict():
    comp = {"robustness_score": 50, "split_consistency_score": 40, "sample_score": 60}
    ov = {"overfit_risk": 2, "overfit_flags": "symbol_single_BNB,low_sample"}
    v = champion_verdict(comp, ov, "CHAMPION")
    assert v in ("ROBUST", "CONDITIONAL", "OVERFIT_RISK", "REJECTED")


def test_temporal_subset():
    df = _df()
    first = _temporal_subset(df, "first_half")
    second = _temporal_subset(df, "second_half")
    assert len(first) + len(second) == len(df)


def test_existing_entry_filter_csv():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_entry_filter_refinement.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "filter_id" in df.columns
    assert len(df) > 0


def test_existing_journal_csv():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_live_forward_journal.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "event_id" in df.columns
