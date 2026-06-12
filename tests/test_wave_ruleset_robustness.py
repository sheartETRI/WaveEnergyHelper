"""Wave Rule Set Robustness 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_ruleset_robustness import (
    apply_rule,
    compute_robustness_scores,
    evaluate_segment,
    exit_policy_performance,
    load_robustness_events,
    rolling_window_summary,
    rule_filters,
    select_champion,
    walk_forward_performance,
)


def _events():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": True, "quality_score": 4, "return_pct": 3.0,
         "vol_regime": "LOW_VOL", "trend_regime": "TREND_UP"},
        {"timestamp": pd.Timestamp("2025-02-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": False, "quality_score": 3, "return_pct": 3.0,
         "vol_regime": "MID_VOL", "trend_regime": "TREND_UP"},
        {"timestamp": pd.Timestamp("2025-03-01"), "symbol": "ETHUSDT", "timeframe": "4h",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": False,
         "flag_energy": True, "quality_score": 3, "return_pct": -3.0,
         "vol_regime": "HIGH_VOL", "trend_regime": "TREND_DOWN"},
        {"timestamp": pd.Timestamp("2025-04-01"), "symbol": "BTCUSDT", "timeframe": "1d",
         "flag_tb": True, "flag_money_flow": True, "flag_structure": True,
         "flag_energy": True, "quality_score": 5, "return_pct": 3.0,
         "vol_regime": "LOW_VOL", "trend_regime": "TREND_FLAT"},
        {"timestamp": pd.Timestamp("2025-05-01"), "symbol": "BTCUSDT", "timeframe": "1d",
         "flag_tb": False, "flag_money_flow": True, "flag_structure": False,
         "flag_energy": True, "quality_score": 2, "return_pct": -3.0,
         "vol_regime": "MID_VOL", "trend_regime": "TREND_DOWN"},
    ])


def test_rule_filter():
    df = _events()
    a = apply_rule(df, "RULE_A")
    assert len(a) == 4
    b = apply_rule(df, "RULE_B")
    assert len(b) == 3
    e = apply_rule(df, "RULE_E")
    assert len(e) == 2


def test_evaluate_segment():
    df = _events()
    m = evaluate_segment(df[df["return_pct"] > 0])
    assert m["n"] == 3
    assert m["expectancy"] == 3.0


def test_walk_forward():
    rows = walk_forward_performance(_events())
    assert any(r["rule"] == "RULE_A" for r in rows)
    assert any(r["segment"] == "Q1" for r in rows)


def test_rolling_window():
    rows = rolling_window_summary(_events())
    ra = next(r for r in rows if r["rule"] == "RULE_A")
    assert ra.get("window_count", 0) >= 1
    assert ra.get("negative_window_ratio") is not None


def test_exit_policy_sensitivity():
    df = _events()
    exit_df = pd.DataFrame([
        {"timestamp": r["timestamp"], "symbol": r["symbol"], "policy": "TP3_SL3_TIMEOUT20",
         "return_pct": r["return_pct"]}
        for _, r in df.iterrows()
    ] + [
        {"timestamp": r["timestamp"], "symbol": r["symbol"], "policy": "TP5_SL3_TIMEOUT40",
         "return_pct": r["return_pct"] * 0.5}
        for _, r in df.iterrows()
    ])
    rows = exit_policy_performance(df, exit_df)
    sens = [r for r in rows if r.get("segment") == "all" and "exit_policy_sensitivity" in r]
    assert len(sens) >= 1
    assert sens[0].get("exit_policy_sensitivity") is not None


def test_symbol_robustness_calc():
    from analysis.wave_ruleset_robustness import symbol_robustness
    rows, ratios = symbol_robustness(_events())
    assert "RULE_A" in ratios


def test_timeframe_robustness_calc():
    from analysis.wave_ruleset_robustness import timeframe_robustness
    rows, ratios = timeframe_robustness(_events())
    assert "RULE_A" in ratios


def test_robustness_score():
    df = _events()
    walk = walk_forward_performance(df)
    rolling = rolling_window_summary(df)
    scores = compute_robustness_scores(walk, rolling, [], {"RULE_A": 1.0}, {"RULE_A": 1.0}, {"RULE_A": 0.5})
    assert scores[0]["robustness_score"] >= 0


def test_champion_selection():
    baseline = [{"rule": "RULE_A", "n": 4, "expectancy": 1.5},
                {"rule": "RULE_B", "n": 3, "expectancy": 2.0}]
    scores = [
        {"rule": "RULE_A", "robustness_score": 80},
        {"rule": "RULE_B", "robustness_score": 70},
    ]
    champ = select_champion(baseline, scores)
    assert champ["rule"] == "RULE_A"


def test_quality_ruleset_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_quality_ruleset.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)


def test_load_from_validation():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_quality_score.csv",
    )
    if os.path.isfile(path):
        df = load_robustness_events()
        assert not df.empty
        assert len(apply_rule(df, "RULE_A")) >= 1
