"""Wave Candidate Rules 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_branch_analysis import BRANCH_REQUIRED
from analysis.wave_candidate_rules import (
    RULE_IDS,
    _classify_failure_reason,
    build_candidate_rules,
    compute_robustness,
    enrich_confluence_events,
    evaluate_rule,
    rank_rules,
    rule_mask,
    stability_score,
)
from analysis.wave_expectancy import compute_expectancy_metrics


def _sample_confluence():
    rows = []
    tb_buckets = {"0": "50-60", "3": "60-70", "6": "40-50", "9": "50-60"}
    for i in range(12):
        tb = i in (0, 3, 6, 9)
        rows.append({
            "timestamp": pd.Timestamp("2025-01-01") + pd.Timedelta(hours=4 * i),
            "branch": BRANCH_REQUIRED if tb else "WAVE3_COMPLETED",
            "branch_label": BRANCH_REQUIRED if tb else "WAVE3_COMPLETED",
            "return_pct": 3.0 if i % 2 == 0 else -3.0,
            "success": i % 2 == 0,
            "MACD_ABOVE_ZERO": i % 2 == 0,
            "PRICE_ABOVE_60": i >= 4,
            "rsi_bucket": tb_buckets.get(str(i), "30-40"),
            "confluence_score": 3 if i % 3 == 0 else 1,
        })
    return pd.DataFrame(rows)


def test_rule_filtering():
    df = _sample_confluence()
    assert rule_mask(df, "RULE_A").sum() == 4
    assert rule_mask(df, "RULE_B").sum() >= 1
    assert rule_mask(df, "RULE_C").sum() >= 1
    assert rule_mask(df, "RULE_SCORE_3").sum() == 4


def test_expectancy_calculation():
    df = _sample_confluence()
    mask = rule_mask(df, "RULE_A")
    linked = df[mask].dropna(subset=["return_pct"])
    m = compute_expectancy_metrics(linked["return_pct"])
    assert m["n"] == 4
    assert "expectancy" in m


def test_robustness_calculation():
    df = _sample_confluence()
    linked = df.dropna(subset=["return_pct"])
    rob = compute_robustness(linked, "ETHUSDT")
    assert "robustness_gap" in rob
    assert rob["window_a_n"] + rob["window_b_n"] == len(linked)


def test_stability_score_calculation():
    assert stability_score(3.0, 0.0) == 3.0
    assert stability_score(3.0, 1.0) == 0.0
    assert stability_score(2.0, 0.5) == 1.0


def test_rule_ranking():
    results = [
        {"rule": "RULE_A", "stability_score": 1.0, "expectancy": 1.0, "n": 5},
        {"rule": "RULE_B", "stability_score": 2.0, "expectancy": 0.5, "n": 3},
        {"rule": "RULE_C", "stability_score": 2.0, "expectancy": 1.5, "n": 4},
    ]
    ranked = rank_rules(results)
    assert ranked[0]["rule"] == "RULE_C"
    assert ranked[1]["rule"] == "RULE_B"


def test_failure_analysis():
    assert _classify_failure_reason("STOP_LOSS_3") == "STOP_LOSS"
    assert _classify_failure_reason("TIMEOUT_20") == "TIMEOUT"
    assert _classify_failure_reason("RE_OVERSOLD_EXIT") == "RE_OVERSOLD"
    assert _classify_failure_reason("NEW_LL_EXIT") == "NEW_LL"
    df = _sample_confluence()
    df["failure_category"] = df["exit_reason"].map(_classify_failure_reason) if "exit_reason" in df.columns else "기타"
    r = evaluate_rule(df, "RULE_A", "ETHUSDT")
    assert "failure_distribution" in r


def test_confluence_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_confluence_ETHUSDT_4h.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        build_candidate_rules("ETHUSDT", "4h")
        after = pd.read_csv(path)
        assert len(before) == len(after)
