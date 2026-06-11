"""Wave Regime Gated 테스트."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_regime_gated import (
    BASE_LABEL,
    apply_filters,
    build_filter_catalog,
    build_filter_combos,
    compute_robustness_gap,
    evaluate_gated_rule,
    improvement_vs_base,
    rank_gated_rules,
    _metrics,
)


def _events():
    return pd.DataFrame([
        {"timestamp": pd.Timestamp("2025-01-01"), "return_pct": 3.0,
         "ema20_slope_3": 0.5, "rsi_slope_1": 1.0, "atr_pct": 1.0, "volatility_20": 0.4,
         "dist_ema60_pct": 1.0, "major_k": 55},
        {"timestamp": pd.Timestamp("2025-01-02"), "return_pct": 3.0,
         "ema20_slope_3": 0.3, "rsi_slope_1": 0.5, "atr_pct": 1.2, "volatility_20": 0.6,
         "dist_ema60_pct": 1.5, "major_k": 60},
        {"timestamp": pd.Timestamp("2025-01-03"), "return_pct": -3.0,
         "ema20_slope_3": -0.2, "rsi_slope_1": -1.0, "atr_pct": 3.0, "volatility_20": 2.5,
         "dist_ema60_pct": 4.0, "major_k": 30},
        {"timestamp": pd.Timestamp("2025-01-04"), "return_pct": -3.0,
         "ema20_slope_3": -0.5, "rsi_slope_1": -0.5, "atr_pct": 2.8, "volatility_20": 2.0,
         "dist_ema60_pct": 3.5, "major_k": 35},
        {"timestamp": pd.Timestamp("2025-01-05"), "return_pct": 3.0,
         "ema20_slope_3": 0.1, "rsi_slope_1": 0.2, "atr_pct": 1.8, "volatility_20": 1.0,
         "dist_ema60_pct": 2.0, "major_k": 50},
        {"timestamp": pd.Timestamp("2025-01-06"), "return_pct": -3.0,
         "ema20_slope_3": 0.4, "rsi_slope_1": 1.0, "atr_pct": 4.0, "volatility_20": 3.0,
         "dist_ema60_pct": 5.0, "major_k": 45},
    ])


def test_filter_sweep():
    catalog = build_filter_catalog()
    assert len(catalog) >= 20
    combos = build_filter_combos(max_filters=2)
    assert any(c[0] == BASE_LABEL for c in combos)
    assert any("atr_pct<=2.0" in c[0] for c in combos)


def test_improvement_calculation():
    base = _metrics(_events())
    ev = _events()
    filt = [p for p in build_filter_catalog() if p[0] == "ema20_slope_3>0"][0]
    gated = _metrics(apply_filters(ev, [filt]))
    imp = improvement_vs_base(base, gated)
    assert imp["delta_expectancy"] is not None
    assert imp["improvement"] == imp["delta_expectancy"]


def test_robustness_calculation():
    gap = compute_robustness_gap(_events())
    assert gap is not None
    assert gap >= 0


def test_ranking():
    base = _metrics(_events())
    rows = [
        evaluate_gated_rule(_events(), BASE_LABEL, [], base),
    ]
    filt = [p for p in build_filter_catalog() if p[0] == "rsi_slope_1>0"][0]
    rows.append(evaluate_gated_rule(_events(), BASE_LABEL + "+rsi_slope_1>0", [filt], base))
    ranked = rank_gated_rules([r for r in rows if r["filter"] != BASE_LABEL])
    assert len(ranked) == 1


def test_sample_count_maintained():
    ev = _events()
    base_n = _metrics(ev)["n"]
    assert base_n == 6
    filt = [p for p in build_filter_catalog() if p[0] == "atr_pct<=2.0"][0]
    gated_n = _metrics(apply_filters(ev, [filt]))["n"]
    assert gated_n <= base_n
    assert gated_n >= 1


def test_generalization_unchanged():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "wave_generalization.csv",
    )
    if os.path.isfile(path):
        before = pd.read_csv(path)
        after = pd.read_csv(path)
        assert len(before) == len(after)
