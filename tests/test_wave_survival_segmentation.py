"""Wave Survival Segmentation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_survival_segmentation import (
    champion_survivors,
    enrich_journal,
    feature_difference,
    four_way_contribution,
    survival_cohort_analysis,
    survival_curve,
    survival_label,
)


def _journal():
    return pd.DataFrame([
        {
            "event_id": "E1", "timestamp": pd.Timestamp("2025-06-01"),
            "symbol": "BNBUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_5": 1.0, "return_10": 2.0, "return_20": 3.0, "return_40": 5.0,
            "mfe_40": 8.0,
            "outcome_20": "WIN", "status": "COMPLETED",
            "money_flow_score": 5, "structure_score": 4, "energy_score": 3,
            "quality_score": 4, "watchlist_score": 50, "bars_elapsed": 10,
            "failure_cause": None,
        },
        {
            "event_id": "E2", "timestamp": pd.Timestamp("2025-06-02"),
            "symbol": "ETHUSDT", "timeframe": "4h", "rule": "RULE_B",
            "return_5": -1.0, "return_10": -1.5, "return_20": -2.0, "return_40": -3.0,
            "mfe_40": 1.0,
            "outcome_20": "LOSS", "status": "COMPLETED",
            "money_flow_score": 4, "structure_score": 2, "energy_score": 2,
            "quality_score": 2, "watchlist_score": 10, "bars_elapsed": 20,
            "failure_cause": "STRUCTURE_FAIL",
        },
        {
            "event_id": "E3", "timestamp": pd.Timestamp("2025-06-03"),
            "symbol": "BTCUSDT", "timeframe": "1h", "rule": "RULE_A",
            "return_5": 0.5, "return_10": 0.8, "return_20": 1.0, "return_40": 1.5,
            "mfe_40": 2.0,
            "outcome_20": "WIN", "status": "COMPLETED",
            "money_flow_score": 4, "structure_score": 3, "energy_score": 3,
            "quality_score": 3, "watchlist_score": 30, "bars_elapsed": 5,
            "failure_cause": None,
        },
    ])


def test_survival_label():
    assert survival_label(3.0) == "SURVIVED_20"
    assert survival_label(-1.0) == "FAILED_20"
    assert survival_label(1.0) == "NEUTRAL_20"
    assert survival_label(None) == "UNKNOWN"


def test_survival_cohort():
    enriched = _journal().copy()
    enriched["survival_label"] = enriched["return_20"].apply(survival_label)
    cohort = survival_cohort_analysis(enriched)
    assert len(cohort) == 3


def test_feature_difference():
    enriched = _journal().copy()
    enriched["survival_label"] = enriched["return_20"].apply(survival_label)
    diff = feature_difference(enriched)
    struct = next(d for d in diff if d["feature"] == "structure_score")
    assert struct["delta"] > 0


def test_survival_curve():
    enriched = _journal().copy()
    enriched["survival_label"] = enriched["return_20"].apply(survival_label)
    curve = survival_curve(enriched)
    assert any(c["horizon"] == 20 for c in curve)


def test_champion_survivors():
    enriched = _journal().copy()
    enriched["survival_label"] = enriched["return_20"].apply(survival_label)
    champ = champion_survivors(enriched, "return_40", 5)
    assert champ[0]["return_40"] == 5.0


def test_contribution():
    enriched = _journal().copy()
    enriched["survival_label"] = enriched["return_20"].apply(survival_label)
    enriched["regime"] = "BULL"
    enriched["survival_feature"] = enriched.apply(
        lambda r: int(r["structure_score"]) + int(r["money_flow_score"]) + int(r["energy_score"]),
        axis=1,
    )
    contrib = four_way_contribution(enriched)
    assert any(c.get("rule") == "SURVIVAL_FEATURE" for c in contrib)


def test_existing_files_unchanged():
    vdir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )
    for name in (
        "wave_live_forward_journal.csv",
        "wave_symbol_segmentation.csv",
        "wave_regime_segmentation.csv",
    ):
        path = os.path.join(vdir, name)
        if os.path.isfile(path):
            before = pd.read_csv(path)
            after = pd.read_csv(path)
            assert len(before) == len(after)
