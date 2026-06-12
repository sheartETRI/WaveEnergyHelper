"""Wave Entry Filter Refinement 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_entry_filter_refinement import (
    BASELINE_LABEL,
    FILTER_RULES,
    _apply_mask,
    _perf,
    active_candidate_overlay,
    champion_filters,
    false_discovery_analysis,
    generate_all_filters,
    robustness_analysis,
    rule_filter_analysis,
)


def _df():
    return pd.DataFrame([
        {
            "event_id": "E1", "rule": "RULE_B", "symbol": "BNBUSDT", "timeframe": "4h",
            "regime": "BULL", "survival_label": "SURVIVED_20", "status": "COMPLETED",
            "return_20": 5.0, "return_40": 8.0,
            "structure_score": 4, "money_flow_score": 5, "energy_score": 3,
            "quality_score": 4, "watchlist_score": 40,
        },
        {
            "event_id": "E2", "rule": "RULE_C", "symbol": "ETHUSDT", "timeframe": "1d",
            "regime": "BEAR", "survival_label": "FAILED_20", "status": "COMPLETED",
            "return_20": -3.0, "return_40": -5.0,
            "structure_score": 2, "money_flow_score": 3, "energy_score": 2,
            "quality_score": 2, "watchlist_score": 10,
        },
        {
            "event_id": "E3", "rule": "RULE_A", "symbol": "BTCUSDT", "timeframe": "4h",
            "regime": "BULL", "survival_label": "SURVIVED_20", "status": "COMPLETED",
            "return_20": 2.5, "return_40": 4.0,
            "structure_score": 3, "money_flow_score": 4, "energy_score": 3,
            "quality_score": 3, "watchlist_score": 25,
        },
        {
            "event_id": "E4", "rule": "RULE_B", "symbol": "BNBUSDT", "timeframe": "1h",
            "regime": "SIDEWAYS", "survival_label": "NEUTRAL_20", "status": "COMPLETED",
            "return_20": 1.0, "return_40": 2.0,
            "structure_score": 5, "money_flow_score": 5, "energy_score": 4,
            "quality_score": 4, "watchlist_score": 35,
        },
    ] * 5)


def test_generate_filters():
    filters = generate_all_filters()
    assert len(filters) > 100
    assert any(f["filter_id"] == BASELINE_LABEL for f in filters)


def test_apply_mask():
    df = _df()
    sub = _apply_mask(df, "RULE_B", "BNBUSDT", "ALL", {"structure_score": 4})
    assert len(sub) >= 1
    assert all(sub["rule"] == "RULE_B")


def test_perf_metrics():
    df = _df()
    m = _perf(df)
    assert m["n"] == 20
    assert "expectancy" in m
    assert "profit_factor" in m


def test_rule_filter_analysis():
    df = _df()
    baseline = _perf(df)
    rows = rule_filter_analysis(df, baseline)
    assert len(rows) == len(FILTER_RULES)


def test_champion_filters():
    df = _df()
    baseline = _perf(df)
    from analysis.wave_entry_filter_refinement import filter_performance, generate_all_filters
    filters = generate_all_filters()
    perf = filter_performance(df, filters[:200], baseline)
    champs, worst = champion_filters(perf, 5)
    assert isinstance(champs, list)
    assert isinstance(worst, list)


def test_robustness():
    df = _df()
    baseline = _perf(df)
    from analysis.wave_entry_filter_refinement import filter_performance, generate_all_filters
    perf = filter_performance(df, generate_all_filters()[:100], baseline)
    champs, _ = champion_filters(perf, 3)
    if champs:
        rob = robustness_analysis(df, champs)
        assert rob[0].get("positive_cell_ratio") is not None


def test_false_discovery():
    champs = [{"filter_id": "test", "rank": 1, "n": 20, "expectancy": 0.5, "score": 1.0}]
    rob = [{"filter_id": "test", "positive_cell_ratio": 60, "positive_symbol_ratio": 50, "positive_regime_ratio": 40}]
    rows = false_discovery_analysis(champs, rob)
    assert rows[0]["confidence_score"] > 0


def test_active_overlay_no_candidates():
    enriched = _df()
    rows = active_candidate_overlay(enriched, [])
    assert rows == []


def test_existing_exit_csv_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_exit_policy_simulation.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "policy" in df.columns
    assert len(df) > 0


def test_existing_survival_csv_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_survival_segmentation.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "survival_label" in df.columns
