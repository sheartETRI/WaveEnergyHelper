"""Wave Cross Market Validation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_cross_market_validation import (
    apply_rule,
    drift_analysis,
    positive_cell_ratio,
    rule_filters,
    select_champion_v2,
    symbol_independence,
    train_test_split,
)


def _events():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": True, "quality_score": 4, "return_pct": 3.0},
        {"timestamp": pd.Timestamp("2025-02-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": False, "quality_score": 3, "return_pct": 3.0},
        {"timestamp": pd.Timestamp("2025-03-01"), "symbol": "SOLUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": False,
         "flag_energy": True, "quality_score": 3, "return_pct": -3.0},
        {"timestamp": pd.Timestamp("2025-04-01"), "symbol": "SOLUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": True, "quality_score": 5, "return_pct": 3.0},
        {"timestamp": pd.Timestamp("2025-05-01"), "symbol": "BNBUSDT", "timeframe": "4h",
         "flag_tb": False, "flag_money_flow": True, "flag_structure": False,
         "flag_energy": True, "quality_score": 2, "return_pct": -3.0},
    ])


def test_train_test_split():
    df = _events()
    train, test = train_test_split(df)
    assert len(train) == 3
    assert len(test) == 2


def test_rule_filter():
    df = _events()
    assert len(apply_rule(df, "RULE_A")) == 4
    assert len(apply_rule(df, "RULE_B")) == 3


def test_positive_ratio():
    matrix = [
        {"rule": "RULE_A", "symbol": "ETHUSDT", "timeframe": "4h", "n": 2, "expectancy": 3.0, "positive": True},
        {"rule": "RULE_A", "symbol": "SOLUSDT", "timeframe": "4h", "n": 2, "expectancy": 0.0, "positive": False},
    ]
    rows = positive_cell_ratio(matrix)
    ra = next(r for r in rows if r["rule"] == "RULE_A")
    assert ra["positive_cells"] == 1
    assert ra["total_cells"] == 2


def test_drift_calculation():
    rows = drift_analysis([
        {"rule": "RULE_A", "symbol": "ETHUSDT", "timeframe": "4h", "dataset": "TRAIN",
         "n": 2, "expectancy": 3.0, "win_rate": 100.0},
        {"rule": "RULE_A", "symbol": "ETHUSDT", "timeframe": "4h", "dataset": "TEST",
         "n": 1, "expectancy": 1.0, "win_rate": 50.0},
    ])
    assert rows[0]["expectancy_drift"] == -2.0


def test_symbol_independence():
    matrix = [
        {"rule": "RULE_A", "symbol": "ETHUSDT", "timeframe": "4h", "n": 2, "expectancy": 3.0, "positive": True},
        {"rule": "RULE_A", "symbol": "SOLUSDT", "timeframe": "4h", "n": 2, "expectancy": 1.0, "positive": True},
    ]
    rows = symbol_independence(matrix)
    wo = next(r for r in rows if r["rule"] == "RULE_A" and r["scope"] == "WITHOUT_ETH")
    assert wo["positive_cells"] == 1


def test_champion_selection():
    champ = select_champion_v2(
        [{"rule": "RULE_A", "positive_ratio": 0.6}, {"rule": "RULE_B", "positive_ratio": 0.8}],
        [{"rule": "RULE_A", "survival_market_count": 2}, {"rule": "RULE_B", "survival_market_count": 3}],
        [{"rule": "RULE_A", "variance": 1.0}, {"rule": "RULE_B", "variance": 0.5}],
        {"RULE_A": 1.0, "RULE_B": 2.0},
    )
    assert champ["rule"] == "RULE_B"


def test_existing_csvs_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in ("wave_quality_score.csv", "wave_generalization.csv", "wave_ruleset_robustness.csv"):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)
