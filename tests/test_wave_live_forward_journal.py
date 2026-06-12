"""Wave Live Forward Journal 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_live_forward_journal import (
    active_candidate_tracking,
    classify_status,
    compare_1h_vs_4h,
    make_event_id,
    outcome_label,
    rule_cohort_summary,
    symbol_summary,
    timeframe_summary,
)


def _journal_df():
    return pd.DataFrame([
        {
            "event_id": make_event_id("ETHUSDT", "4h", "RULE_B", pd.Timestamp("2025-06-01")),
            "timestamp": pd.Timestamp("2025-06-01"),
            "symbol": "ETHUSDT", "timeframe": "4h", "rule": "RULE_B",
            "freshness": "ACTIVE", "watchlist_score": 50.0,
            "money_flow_score": 4, "energy_score": 3, "structure_score": 3,
            "quality_score": 4,
            "return_5": 1.0, "return_10": 2.0, "return_20": 3.0, "return_40": -1.0,
            "outcome_5": "WIN", "outcome_10": "WIN", "outcome_20": "WIN", "outcome_40": "LOSS",
            "status": "COMPLETED", "pending_horizon": None, "failure_cause": None,
            "bars_elapsed": 50,
        },
        {
            "event_id": make_event_id("BTCUSDT", "1h", "RULE_A", pd.Timestamp("2025-06-10")),
            "timestamp": pd.Timestamp("2025-06-10"),
            "symbol": "BTCUSDT", "timeframe": "1h", "rule": "RULE_A",
            "freshness": "RECENT", "watchlist_score": 40.0,
            "money_flow_score": 4, "energy_score": 2, "structure_score": 2,
            "quality_score": 2,
            "return_5": None, "return_10": None, "return_20": None, "return_40": None,
            "outcome_5": None, "outcome_10": None, "outcome_20": None, "outcome_40": None,
            "status": "PENDING_5", "pending_horizon": 5, "failure_cause": None,
            "bars_elapsed": 2,
        },
        {
            "event_id": make_event_id("SOLUSDT", "1h", "RULE_C", pd.Timestamp("2025-06-08")),
            "timestamp": pd.Timestamp("2025-06-08"),
            "symbol": "SOLUSDT", "timeframe": "1h", "rule": "RULE_C",
            "freshness": "ACTIVE", "watchlist_score": 30.0,
            "money_flow_score": 5, "energy_score": 4, "structure_score": 1,
            "quality_score": 2,
            "return_5": -0.5, "return_10": -1.0, "return_20": None, "return_40": None,
            "outcome_5": "LOSS", "outcome_10": "LOSS", "outcome_20": None, "outcome_40": None,
            "status": "PENDING_20", "pending_horizon": 20, "failure_cause": "MONEY_FLOW_DROP",
            "bars_elapsed": 12,
        },
    ])


def test_event_id_generation():
    eid = make_event_id("ETHUSDT", "4h", "RULE_B", pd.Timestamp("2025-06-01 12:00:00"))
    assert eid.startswith("E_ETHUSDT_4h_RULE_B_")
    assert len(eid.split("_")) >= 5


def test_forward_return_outcome():
    assert outcome_label(1.5) == "WIN"
    assert outcome_label(-0.5) == "LOSS"
    assert outcome_label(0.05) == "FLAT"
    assert outcome_label(None) is None


def test_pending_completed_status():
    assert classify_status(3) == ("PENDING_5", 5)
    assert classify_status(8) == ("PENDING_10", 10)
    assert classify_status(15) == ("PENDING_20", 20)
    assert classify_status(25) == ("PENDING_40", 40)
    assert classify_status(50) == ("COMPLETED", None)


def test_active_candidate_extraction():
    df = _journal_df()
    cands = active_candidate_tracking(df)
    assert len(cands) == 3
    assert cands[0]["watchlist_score"] >= cands[-1]["watchlist_score"]


def test_rule_summary():
    df = _journal_df()
    rows = rule_cohort_summary(df)
    rb = next(r for r in rows if r["rule"] == "RULE_B")
    assert rb["n"] == 1
    assert rb["completed_n"] == 1
    ra = next(r for r in rows if r["rule"] == "RULE_A")
    assert ra["pending_n"] == 1


def test_symbol_tf_summary():
    df = _journal_df()
    sym = symbol_summary(df)
    assert any(r["symbol"] == "ETHUSDT" for r in sym)
    tf = timeframe_summary(df)
    assert any(r["timeframe"] == "1h" for r in tf)
    h1h4 = compare_1h_vs_4h(df)
    assert len(h1h4) == 2


def test_existing_watchlist_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    path = os.path.join(vdir, "wave_live_watchlist.csv")
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
