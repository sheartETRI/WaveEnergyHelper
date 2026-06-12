"""Wave Forward Observation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_forward_observation import (
    RESEARCH_BASELINE,
    build_observation_journal,
    classify_observation_tier,
    drift_detection,
    forward_status,
    full_forward_observation_summary,
    match_filter_bnb_core,
    rolling_performance,
    tier_dashboard,
)


def _row(**kw):
    base = {
        "event_id": "E1", "timestamp": pd.Timestamp("2025-06-01"),
        "symbol": "BNBUSDT", "timeframe": "4h", "rule": "RULE_A",
        "regime": "BULL", "money_flow_score": 5, "structure_score": 5,
        "energy_score": 3, "quality_score": 4, "bars_elapsed": 25,
        "return_20": 5.0, "survival_label": "SURVIVED_20", "freshness": "ACTIVE",
        "status": "COMPLETED",
    }
    base.update(kw)
    return pd.Series(base)


def test_tier1_bnb_core():
    assert match_filter_bnb_core(_row())
    tier, f = classify_observation_tier(_row())
    assert tier == "TIER_1"
    assert f == "Filter_BNB_CORE"


def test_tier2_quality():
    tier, f = classify_observation_tier(_row(symbol="BTCUSDT", money_flow_score=3, structure_score=3))
    assert tier == "TIER_2"
    assert f == "quality>=4"


def test_tier3_rule_c():
    tier, f = classify_observation_tier(
        _row(symbol="ETHUSDT", rule="RULE_C", quality_score=2, money_flow_score=3, structure_score=3)
    )
    assert tier == "TIER_3"


def test_forward_status():
    assert forward_status(_row(bars_elapsed=3)) == "PENDING"
    assert forward_status(_row(bars_elapsed=20)) == "+20_COMPLETE"


def test_observation_journal():
    df = pd.DataFrame([_row().to_dict(), _row(symbol="ETHUSDT", rule="RULE_C", quality_score=2).to_dict()])
    obs = build_observation_journal(df)
    assert len(obs) == 2
    assert "observation_tier" in obs.columns


def test_tier_dashboard():
    obs = build_observation_journal(pd.DataFrame([_row().to_dict()]))
    rows = tier_dashboard(obs)
    t1 = next(r for r in rows if r["observation_tier"] == "TIER_1")
    assert t1["n"] == 1


def test_rolling_performance():
    obs = build_observation_journal(pd.DataFrame([_row().to_dict()]))
    rows = rolling_performance(obs)
    assert any(r["window_days"] == 30 for r in rows)


def test_drift_detection():
    obs = build_observation_journal(pd.DataFrame([_row().to_dict()]))
    rolling = rolling_performance(obs)
    drift = drift_detection(obs, rolling)
    assert any(d["drift_metric"] == "expectancy" for d in drift)


def test_research_baseline():
    assert RESEARCH_BASELINE["TIER_1"]["expectancy"] == 3.02


def test_existing_journal_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_live_forward_journal.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "event_id" in df.columns
    assert len(df) > 0


def test_full_summary_runs():
    stats = full_forward_observation_summary()
    assert "export_df" in stats
    assert "maintenance" in stats
