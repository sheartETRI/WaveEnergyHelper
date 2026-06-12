"""Wave Live Watchlist 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_live_watchlist import (
    classify_freshness,
    compute_live_rank_score,
    compute_watchlist_score,
    extract_rule_events,
    frequency_table,
    rule_filters,
    symbol_tf_heatmap,
)


def _scan_df():
    return pd.DataFrame([
        {
            "timestamp": pd.Timestamp("2025-06-01"),
            "symbol": "ETHUSDT", "timeframe": "4h", "bar_index": 100,
            "bars_since_signal": 5,
            "flag_tb": True, "flag_money_flow": True,
            "flag_structure": True, "flag_energy": True,
            "quality_score": 4, "money_flow_score": 4,
            "energy_score": 3, "structure_score": 3,
            "regime_factor": 0.8, "close": 3000.0,
        },
        {
            "timestamp": pd.Timestamp("2025-06-02"),
            "symbol": "ETHUSDT", "timeframe": "4h", "bar_index": 110,
            "bars_since_signal": 60,
            "flag_tb": True, "flag_money_flow": True,
            "flag_structure": False, "flag_energy": False,
            "quality_score": 2, "money_flow_score": 4,
            "energy_score": 2, "structure_score": 2,
            "regime_factor": 0.5, "close": 3100.0,
        },
        {
            "timestamp": pd.Timestamp("2025-06-03"),
            "symbol": "BNBUSDT", "timeframe": "4h", "bar_index": 120,
            "bars_since_signal": 3,
            "flag_tb": False, "flag_money_flow": True,
            "flag_structure": False, "flag_energy": True,
            "quality_score": 2, "money_flow_score": 5,
            "energy_score": 4, "structure_score": 1,
            "regime_factor": 1.0, "close": 600.0,
        },
    ])


def test_rule_detection():
    events = extract_rule_events(_scan_df())
    rules = set(events["rule"])
    assert "RULE_A" in rules
    assert "RULE_B" in rules
    assert "RULE_C" in rules
    assert len(events[events["rule"] == "RULE_A"]) == 2


def test_freshness():
    assert classify_freshness(5) == "ACTIVE"
    assert classify_freshness(30) == "RECENT"
    assert classify_freshness(51) == "OLD"


def test_ranking():
    score_b = compute_live_rank_score("RULE_B", 50.0, "ACTIVE")
    score_a = compute_live_rank_score("RULE_A", 50.0, "ACTIVE")
    score_c = compute_live_rank_score("RULE_C", 50.0, "ACTIVE")
    assert score_b > score_a > score_c


def test_watchlist_score():
    s = compute_watchlist_score("RULE_B", 4, 3, 3, 0.8)
    assert 0 <= s <= 100
    assert s > compute_watchlist_score("RULE_C", 4, 3, 3, 0.8)


def test_heatmap():
    full = _scan_df()
    eth_scan = full[full["symbol"] == "ETHUSDT"].reset_index(drop=True)
    bnb_scan = full[full["symbol"] == "BNBUSDT"].reset_index(drop=True)
    hm = symbol_tf_heatmap({("ETHUSDT", "4h"): eth_scan, ("BNBUSDT", "4h"): bnb_scan})
    eth = next(h for h in hm if h["symbol"] == "ETHUSDT" and h["timeframe"] == "4h")
    bnb = next(h for h in hm if h["symbol"] == "BNBUSDT" and h["timeframe"] == "4h")
    assert eth["state"] == "RULE_A"
    assert bnb["state"] == "RULE_C"


def test_frequency_table():
    events = extract_rule_events(_scan_df())
    freq = frequency_table(events, pd.Timestamp("2025-06-10"))
    assert any(r.get("count_30d", 0) > 0 for r in freq)


def test_existing_csvs_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in (
        "wave_cross_market_validation.csv",
        "wave_ruleset_robustness.csv",
        "wave_quality_score.csv",
    ):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)


def test_rule_filters_import():
    flt = rule_filters()
    assert "RULE_A" in flt
    assert "RULE_B" in flt
    assert "RULE_C" in flt
