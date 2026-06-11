"""Wave Generalization 테스트."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_branch_analysis import BRANCH_REQUIRED
from analysis.wave_generalization import (
    aggregate_cells,
    build_generalization,
    evaluate_cell_rules,
    expectancy_positive_rate,
    find_outlier_cells,
    generalization_score,
    heatmap_matrix,
    median_expectancy,
    rule_overall_variance,
    summarize_generalization,
)
from analysis.wave_candidate_rules import build_candidate_rules


def _sample_rows():
    rows = []
    exps = [2.0, 1.5, -1.0, 0.5, 3.0, -2.0, 1.0, 0.0, 2.5, -0.5, 1.8, 0.3]
    i = 0
    for sym in ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT"):
        for tf in ("1h", "4h", "1d"):
            for rule in ("RULE_A", "RULE_B", "RULE_C", "RULE_D", "RULE_SCORE_3"):
                exp = exps[i % len(exps)] if rule == "RULE_B" else exps[(i + 1) % len(exps)]
                rows.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": rule,
                    "count": 3,
                    "n": 2 if exp is not None else 0,
                    "win_rate": 50.0,
                    "expectancy": exp,
                    "profit_factor": 2.0,
                    "payoff_ratio": 1.5,
                    "avg_return": exp,
                    "avg_survival": 20.0,
                })
                i += 1
    return rows


def _sample_confluence():
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=6, freq="4h"),
        "branch": [BRANCH_REQUIRED] * 4 + ["WAVE3_COMPLETED"] * 2,
        "branch_label": [BRANCH_REQUIRED] * 4 + ["WAVE3_COMPLETED"] * 2,
        "return_pct": [3.0, 3.0, -3.0, 3.0, -3.0, -3.0],
        "success": [True, True, False, True, False, False],
        "MACD_ABOVE_ZERO": [True, True, False, True, False, True],
        "PRICE_ABOVE_60": [True, False, True, True, False, False],
        "rsi_bucket": ["60-70", "50-60", "40-50", "60-70", "30-40", "50-60"],
        "confluence_score": [4, 3, 2, 3, 1, 2],
    })


def test_cell_aggregation():
    conf = _sample_confluence()
    cells = evaluate_cell_rules(conf, "ETHUSDT", "4h")
    df = aggregate_cells(cells)
    assert len(df) == 5
    assert "RULE_B" in df["rule"].values
    rule_b = df[df["rule"] == "RULE_B"].iloc[0]
    assert rule_b["n"] >= 1


def test_generalization_score():
    rows = _sample_rows()
    rate = expectancy_positive_rate(rows, "RULE_B", total_cells=12)
    assert 0 <= rate <= 1
    med = median_expectancy(rows, "RULE_B")
    assert med is not None
    score = generalization_score(rows, "RULE_B", total_cells=12)
    assert score == rate * med


def test_variance_calculation():
    rows = _sample_rows()
    var = rule_overall_variance(rows, "RULE_B")
    assert var is not None
    assert var >= 0


def test_outlier_detection():
    rows = _sample_rows()
    best = find_outlier_cells(rows, "RULE_B", best=True)
    worst = find_outlier_cells(rows, "RULE_B", best=False)
    assert best is not None
    assert worst is not None
    assert best["expectancy"] >= worst["expectancy"]


def test_heatmap_data():
    rows = _sample_rows()
    hm = heatmap_matrix(rows, "RULE_B")
    assert "ETHUSDT" in hm
    assert "4h" in hm["ETHUSDT"]
    stats = summarize_generalization(rows)
    assert "heatmap_rules" in stats
    assert "RULE_B" in stats["heatmap_rules"]


def test_candidate_rules_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_candidate_rules_ETHUSDT_4h.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        build_generalization(symbols=("ETHUSDT",), timeframes=("4h",), live_build=False)
        after = pd.read_csv(path)
        assert len(before) == len(after)
        build_candidate_rules("ETHUSDT", "4h")
        after2 = pd.read_csv(path)
        assert len(before) == len(after2)
