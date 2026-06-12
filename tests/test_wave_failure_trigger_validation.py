"""Wave Failure Trigger Validation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_failure_trigger_validation import (
    TRIGGER_TYPES,
    TRIGGER_COMBOS,
    _prf,
    best_triggers,
    build_export,
    combo_analysis,
    trigger_precision_recall,
)


def _event_df():
    return pd.DataFrame([
        {
            "event_id": "E1", "rule": "RULE_B", "symbol": "BNB", "timeframe": "4h",
            "regime": "BULL", "survival_label": "FAILED_20",
            "first_trigger": "STRUCTURE_FAIL", "first_trigger_bar": 3,
            "first_trigger_return": -1.0, "return_20": -2.0, "return_40": -3.0,
        },
        {
            "event_id": "E2", "rule": "RULE_C", "symbol": "ETH", "timeframe": "1d",
            "regime": "BEAR", "survival_label": "SURVIVED_20",
            "first_trigger": "MONEY_FLOW_DROP", "first_trigger_bar": 5,
            "first_trigger_return": 1.0, "return_20": 5.0, "return_40": 8.0,
        },
        {
            "event_id": "E3", "rule": "RULE_A", "symbol": "BTC", "timeframe": "4h",
            "regime": "SIDEWAYS", "survival_label": "NEUTRAL_20",
            "first_trigger": None, "first_trigger_bar": None,
            "first_trigger_return": None, "return_20": 1.0, "return_40": 2.0,
        },
    ])


def _detail_df():
    return pd.DataFrame([
        {"event_id": "E1", "trigger_type": "STRUCTURE_FAIL", "bars_to_trigger": 3},
        {"event_id": "E1", "trigger_type": "STOP_LOSS_3", "bars_to_trigger": 8},
        {"event_id": "E2", "trigger_type": "MONEY_FLOW_DROP", "bars_to_trigger": 5},
    ])


def test_trigger_types_count():
    assert len(TRIGGER_TYPES) == 9
    assert len(TRIGGER_COMBOS) == 4


def test_prf_metrics():
    y_true = pd.Series([True, True, False, False])
    y_pred = pd.Series([True, False, True, False])
    m = _prf(y_true, y_pred)
    assert m["precision"] == 50.0
    assert m["recall"] == 50.0
    assert m["f1"] == 50.0


def test_precision_recall():
    ev = _event_df()
    detail = _detail_df()
    rows = trigger_precision_recall(ev, detail)
    struct = next(r for r in rows if r["trigger_type"] == "STRUCTURE_FAIL")
    assert struct["n"] == 1
    assert struct["precision"] == 100.0


def test_combo_analysis():
    ev = _event_df()
    detail = _detail_df()
    combos = combo_analysis(ev, detail)
    assert len(combos) == 4
    assert any(c["combo"].startswith("STRUCTURE_FAIL") for c in combos)


def test_best_triggers():
    ev = _event_df()
    detail = _detail_df()
    pr = trigger_precision_recall(ev, detail)
    timing = [{"trigger_type": "STRUCTURE_FAIL", "early_trigger_ratio": 60.0, "avg_bars_to_trigger": 3.0}]
    best = best_triggers(pr, timing, 5)
    assert best[0]["rank"] == 1


def test_build_export_columns():
    rows = [{"section": "precision_recall", "trigger_type": "STOP_LOSS_3", "f1": 55.0}]
    df = build_export(rows)
    assert "section" in df.columns
    assert df.iloc[0]["trigger_type"] == "STOP_LOSS_3"


def test_existing_csv_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_live_forward_journal.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "event_id" in df.columns
    assert len(df) > 0
