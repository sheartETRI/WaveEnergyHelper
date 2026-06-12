"""Wave Exit Policy Simulation 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_exit_policy_simulation import (
    EXIT_POLICIES,
    _policy_exit,
    _summary_metrics,
    build_export,
    champion_policies,
    exit_timing,
    false_exit_analysis,
    policy_summary,
    saved_failure_analysis,
)


def _sim_df():
    rows = []
    for eid, label, base, ex_ret, bar in [
        ("E1", "SURVIVED_20", 5.0, 2.0, 8),
        ("E2", "FAILED_20", -3.0, -1.0, 5),
        ("E3", "FAILED_20", -5.0, -3.0, 3),
        ("E4", "SURVIVED_20", 4.0, 4.0, 20),
    ]:
        for pol in ("NO_EXIT", "POLICY_A", "POLICY_C"):
            rows.append({
                "event_id": eid,
                "policy": pol,
                "rule": "RULE_B",
                "symbol": "ETHUSDT",
                "timeframe": "4h",
                "regime": "BULL",
                "survival_label": label,
                "exit_bar": bar if pol != "NO_EXIT" else 20,
                "exit_reason": "STOP_LOSS_3" if pol == "POLICY_A" else "HOLD",
                "exit_return": ex_ret if pol != "NO_EXIT" else base,
                "baseline_return": base,
                "mfe": 2.0,
                "mae": -1.5,
            })
    return pd.DataFrame(rows)


def test_exit_policies_count():
    assert len(EXIT_POLICIES) == 10
    assert "NO_EXIT" in EXIT_POLICIES
    assert "POLICY_G" in EXIT_POLICIES


def test_policy_exit_logic():
    reason, streak = _policy_exit("POLICY_C", {"STOP_LOSS_3", "STRUCTURE_FAIL"}, 0)
    assert reason == "STOP_LOSS_3"
    reason, streak = _policy_exit("POLICY_F", {"STRUCTURE_FAIL"}, 1)
    assert reason == "STRUCTURE_FAIL_x2"
    reason, _ = _policy_exit("POLICY_G", {"STRUCTURE_FAIL", "MONEY_FLOW_DROP"}, 0)
    assert reason == "STRUCTURE_FAIL+MF_DROP"


def test_policy_summary():
    df = _sim_df()
    summary = policy_summary(df)
    assert len(summary) == 3
    no_exit = next(s for s in summary if s["policy"] == "NO_EXIT")
    assert no_exit["n"] == 4


def test_false_exit_analysis():
    df = _sim_df()
    rows = false_exit_analysis(df)
    pol_a = next(r for r in rows if r["policy"] == "POLICY_A")
    assert pol_a["false_exit_n"] >= 1
    assert pol_a["false_exit_rate"] > 0


def test_saved_failure_analysis():
    df = _sim_df()
    rows = saved_failure_analysis(df)
    pol_a = next(r for r in rows if r["policy"] == "POLICY_A")
    assert pol_a["saved_failure_n"] >= 1


def test_exit_timing():
    df = _sim_df()
    rows = exit_timing(df)
    assert any(r["policy"] == "POLICY_A" for r in rows)


def test_champion_policies():
    df = _sim_df()
    summary = policy_summary(df)
    false_ex = false_exit_analysis(df)
    saved = saved_failure_analysis(df)
    champs, worst = champion_policies(summary, false_ex, saved, 3)
    assert len(champs) <= 3
    assert champs[0]["rank"] == 1
    assert len(worst) <= 3


def test_build_export():
    rows = [{"section": "policy_summary", "policy": "POLICY_A", "expectancy": 0.5}]
    df = build_export(rows)
    assert "policy" in df.columns


def test_existing_trigger_csv_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_failure_trigger_validation.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "trigger_type" in df.columns
    assert len(df) > 0


def test_existing_survival_csv_unchanged():
    vdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation")
    path = os.path.join(vdir, "wave_survival_segmentation.csv")
    assert os.path.isfile(path)
    df = pd.read_csv(path)
    assert "survival_label" in df.columns
    assert len(df) > 0
