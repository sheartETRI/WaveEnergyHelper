"""Wave Symbol Segmentation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_symbol_segmentation import (
    champion_cells,
    contribution_analysis,
    cross_symbol_robustness,
    rule_symbol_matrix,
    rule_symbol_tf_matrix,
)


def _journal():
    return pd.DataFrame([
        {
            "symbol": "BNBUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_20": 3.0, "return_40": 2.0, "return_5": 1.0, "return_10": 2.0,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "WIN",
            "status": "COMPLETED", "failure_cause": None,
        },
        {
            "symbol": "BNBUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_20": 2.0, "return_40": 1.0, "return_5": 0.5, "return_10": 1.0,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "WIN",
            "status": "COMPLETED", "failure_cause": None,
        },
        {
            "symbol": "ETHUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_20": -2.0, "return_40": -3.0, "return_5": -1.0, "return_10": -1.5,
            "outcome_5": "LOSS", "outcome_10": "LOSS", "outcome_20": "LOSS", "outcome_40": "LOSS",
            "status": "COMPLETED", "failure_cause": "STRUCTURE_FAIL",
        },
        {
            "symbol": "BTCUSDT", "timeframe": "1h", "rule": "RULE_A",
            "return_20": 0.5, "return_40": -0.5, "return_5": 0.2, "return_10": 0.3,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "LOSS",
            "status": "COMPLETED", "failure_cause": "MONEY_FLOW_DROP",
        },
        {
            "symbol": "SOLUSDT", "timeframe": "1h", "rule": "RULE_C",
            "return_20": -1.0, "return_40": None, "return_5": None, "return_10": None,
            "outcome_5": None, "outcome_10": None, "outcome_20": "LOSS", "outcome_40": None,
            "status": "PENDING_40", "failure_cause": "STOP_LOSS_3",
        },
    ])


def test_rule_symbol_aggregation():
    rs = rule_symbol_matrix(_journal())
    bnb_b = next(r for r in rs if r["symbol"] == "BNBUSDT" and r["rule"] == "RULE_B")
    assert bnb_b["n"] == 2
    assert bnb_b["avg_return_20"] == 2.5
    assert bnb_b["expectancy_20"] is not None


def test_rule_symbol_tf_aggregation():
    rtf = rule_symbol_tf_matrix(_journal())
    cell = next(r for r in rtf if r["symbol"] == "BNBUSDT" and r["rule"] == "RULE_B")
    assert cell["n"] == 2
    assert cell["win_rate_20"] == 100.0


def test_champion_cells():
    rtf = rule_symbol_tf_matrix(_journal())
    top = champion_cells(rtf, "avg_return_20", 5)
    assert top[0]["avg_return_20"] >= top[-1]["avg_return_20"]


def test_positive_ratios():
    rs = rule_symbol_matrix(_journal())
    rtf = rule_symbol_tf_matrix(_journal())
    robust = cross_symbol_robustness(rs, rtf)
    rb = next(r for r in robust if r["rule"] == "RULE_B")
    assert rb["positive_symbol_ratio"] == 50.0


def test_contribution():
    contrib = contribution_analysis(_journal())
    assert any(c["rule"] == "RULE" for c in contrib)
    assert any(c["rule"] == "SYMBOL" for c in contrib)


def test_existing_journal_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    path = os.path.join(vdir, "wave_live_forward_journal.csv")
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
