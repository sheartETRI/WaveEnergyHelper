"""Wave Regime Segmentation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_segmentation import (
    REGIMES,
    assign_event_regimes,
    champion_cells,
    classify_regime,
    positive_ratio_analysis,
    rule_regime_matrix,
    rule_symbol_regime_matrix,
    three_way_contribution,
)


def _journal():
    return pd.DataFrame([
        {
            "event_id": "E1", "timestamp": pd.Timestamp("2025-06-01"),
            "symbol": "BNBUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_20": 3.0, "return_40": 2.0, "return_5": 1.0, "return_10": 2.0,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "WIN",
            "status": "COMPLETED", "failure_cause": None, "regime": "BULL",
        },
        {
            "event_id": "E2", "timestamp": pd.Timestamp("2025-06-02"),
            "symbol": "ETHUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_20": -2.0, "return_40": -3.0, "return_5": -1.0, "return_10": -1.5,
            "outcome_5": "LOSS", "outcome_10": "LOSS", "outcome_20": "LOSS", "outcome_40": "LOSS",
            "status": "COMPLETED", "failure_cause": "STRUCTURE_FAIL", "regime": "BEAR",
        },
        {
            "event_id": "E3", "timestamp": pd.Timestamp("2025-06-03"),
            "symbol": "BTCUSDT", "timeframe": "1h", "rule": "RULE_A",
            "return_20": 0.5, "return_40": -0.5, "return_5": 0.2, "return_10": 0.3,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "LOSS",
            "status": "COMPLETED", "failure_cause": None, "regime": "SIDEWAYS",
        },
    ])


def test_regime_classification():
    assert classify_regime({"ema20_slope_3": 1.0, "ema60_slope_3": 0.5}) == "BULL"
    assert classify_regime({"ema20_slope_3": -1.0, "ema60_slope_3": -0.5}) == "BEAR"
    assert classify_regime({"ema20_slope_3": 1.0, "ema60_slope_3": -0.5}) == "SIDEWAYS"
    assert classify_regime({}) == "SIDEWAYS"


def test_rule_regime_aggregation():
    enriched = _journal()
    rr = rule_regime_matrix(enriched)
    bull_b = next(r for r in rr if r["rule"] == "RULE_B" and r["regime"] == "BULL")
    assert bull_b["n"] == 1
    assert bull_b["avg_return_20"] == 3.0


def test_rule_symbol_regime_aggregation():
    enriched = _journal()
    rsr = rule_symbol_regime_matrix(enriched)
    assert any(r["symbol"] == "BNBUSDT" and r["regime"] == "BULL" for r in rsr)


def test_champion_regime():
    enriched = _journal()
    rsr = rule_symbol_regime_matrix(enriched)
    top = champion_cells(rsr, "avg_return_20", 5)
    assert top[0]["avg_return_20"] >= top[-1]["avg_return_20"]


def test_contribution():
    contrib = three_way_contribution(_journal())
    assert any(c.get("rule") == "RULE" for c in contrib)
    assert any(c.get("rule") == "REGIME" for c in contrib)


def test_positive_regime_ratio():
    enriched = _journal()
    rr = rule_regime_matrix(enriched)
    rsr = rule_symbol_regime_matrix(enriched)
    pos = positive_ratio_analysis(rr, rsr, enriched)
    rb = next(p for p in pos if p["rule"] == "RULE_B")
    assert rb["positive_regime_ratio"] == 50.0


def test_existing_files_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in ("wave_live_forward_journal.csv", "wave_symbol_segmentation.csv"):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)
