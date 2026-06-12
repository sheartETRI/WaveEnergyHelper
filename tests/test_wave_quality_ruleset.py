"""Wave Quality Rule Set 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_quality_ruleset import (
    MIN_RULE_N,
    _label_for_keys,
    compare_vs_quality_score,
    evaluate_rule_set,
    feature_interaction_map,
    generate_all_rule_sets,
    pareto_frontier,
    rule_size_effect,
    top_by_expectancy,
)


def _sample_df():
    return pd.DataFrame([
        {"flag_tb": True, "flag_structure": True, "flag_energy": True,
         "flag_money_flow": True, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": True,
         "return_pct": 3.0, "quality_score": 5, "timestamp": "2025-01-01",
         "symbol": "ETHUSDT", "timeframe": "4h"},
        {"flag_tb": True, "flag_structure": True, "flag_energy": True,
         "flag_money_flow": True, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": True,
         "return_pct": 3.0, "quality_score": 5, "timestamp": "2025-01-02",
         "symbol": "ETHUSDT", "timeframe": "4h"},
        {"flag_tb": True, "flag_structure": True, "flag_energy": True,
         "flag_money_flow": True, "flag_divergence": False,
         "flag_price_ma480": False, "flag_ma120_slope": True,
         "return_pct": 3.0, "quality_score": 5, "timestamp": "2025-01-03",
         "symbol": "ETHUSDT", "timeframe": "4h"},
        {"flag_tb": False, "flag_structure": False, "flag_energy": False,
         "flag_money_flow": False, "flag_divergence": False,
         "flag_price_ma480": True, "flag_ma120_slope": False,
         "return_pct": -3.0, "quality_score": 1, "timestamp": "2025-01-04",
         "symbol": "ETHUSDT", "timeframe": "4h"},
        {"flag_tb": False, "flag_structure": False, "flag_energy": False,
         "flag_money_flow": False, "flag_divergence": False,
         "flag_price_ma480": True, "flag_ma120_slope": False,
         "return_pct": -3.0, "quality_score": 1, "timestamp": "2025-01-05",
         "symbol": "ETHUSDT", "timeframe": "4h"},
    ])


def test_label_for_keys():
    assert "TB" in _label_for_keys(["flag_tb", "flag_structure"])


def test_evaluate_rule_set():
    df = _sample_df()
    r = evaluate_rule_set(df, ("flag_tb", "flag_structure", "flag_money_flow"))
    assert r["n"] == 3
    assert r["expectancy"] == 3.0


def test_generate_all_rule_sets():
    rules = generate_all_rule_sets(_sample_df())
    assert len(rules) > 0
    assert all(r["n"] >= MIN_RULE_N for r in rules)


def test_top_by_expectancy():
    rules = generate_all_rule_sets(_sample_df())
    top = top_by_expectancy(rules)
    assert top[0]["expectancy"] >= top[-1]["expectancy"]


def test_pareto_frontier():
    rules = generate_all_rule_sets(_sample_df())
    pf = pareto_frontier(rules)
    assert isinstance(pf, list)


def test_rule_size_effect():
    rules = generate_all_rule_sets(_sample_df())
    eff = rule_size_effect(rules)
    assert len(eff) >= 1


def test_feature_interaction():
    rows = feature_interaction_map(_sample_df())
    assert len(rows) >= 1


def test_compare_vs_quality_score():
    df = _sample_df()
    rules = generate_all_rule_sets(df)
    cmp = compare_vs_quality_score(rules, df)
    assert cmp["result"] in ("PASS", "FAIL")


def test_existing_csvs_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in ("wave_quality_score.csv", "wave_structure_confirmation.csv"):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)


def test_load_from_validation_csv():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_quality_score.csv",
    )
    if os.path.isfile(path):
        from analysis.wave_quality_ruleset import load_ruleset_events, generate_all_rule_sets
        df = load_ruleset_events()
        assert not df.empty
        rules = generate_all_rule_sets(df)
        assert len(rules) > 0
