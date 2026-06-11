"""Wave Expectancy 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_expectancy import (

    MIN_SAMPLE,

    _combo_expectancy,

    build_expectancy,

    compute_expectancy_metrics,

    summarize_expectancy,

)





def test_expectancy_calculation():

    # win 2 @ +3%, loss 1 @ -3% => win_rate=2/3, avg_win=3, avg_loss=3

    # exp = 2/3*3 - 1/3*3 = 1.0

    m = compute_expectancy_metrics(pd.Series([3.0, 3.0, -3.0]))

    assert abs(m["expectancy"] - 1.0) < 0.01

    assert abs(m["win_rate"] - 66.67) < 0.1





def test_profit_factor():

    m = compute_expectancy_metrics(pd.Series([4.0, 2.0, -2.0]))

    # total profit 6, total loss 2 => PF=3

    assert abs(m["profit_factor"] - 3.0) < 0.01





def test_payoff_ratio():

    m = compute_expectancy_metrics(pd.Series([6.0, -2.0]))

    # avg_win=6, avg_loss=2 => payoff=3

    assert abs(m["payoff_ratio"] - 3.0) < 0.01





def test_min_sample_filter():

    rows = [{"return_pct": 1.0, "initial_type": "SLOPE", "state": "OTHER",

             "family": "NEUTRAL", "stable_family": "NEUTRAL",

             "survival_bucket": "20-39", "verdict": "v"}] * 4

    combos = _combo_expectancy(pd.DataFrame(rows))

    assert len(combos) == 0





def test_condition_combo():

    rows = []

    for i in range(6):

        rows.append({

            "return_pct": 3.0 if i < 4 else -3.0,

            "initial_type": "SLOPE",

            "survival_bucket": "20-39",

            "state": "TRIPLE_BOTTOM_REQUIRED",

            "family": "BUY_FAMILY",

            "stable_family": "BUY_FAMILY",

            "verdict": "v1",

            "success": i < 4,

        })

    combos = _combo_expectancy(pd.DataFrame(rows))

    assert any(c["n"] >= MIN_SAMPLE for c in combos)

    assert all(c["n"] >= MIN_SAMPLE for c in combos)





def test_top_worst_sort():

    df = pd.DataFrame([

        {"return_pct": 3.0, "initial_type": "SLOPE", "state": "A",

         "family": "BUY_FAMILY", "stable_family": "BUY_FAMILY",

         "survival_bucket": "20-39", "verdict": "v", "success": True},

    ] * 6 + [

        {"return_pct": -3.0, "initial_type": "TB", "state": "B",

         "family": "SELL_FAMILY", "stable_family": "SELL_FAMILY",

         "survival_bucket": "<10", "verdict": "w", "success": False},

    ] * 6)

    stats = summarize_expectancy(df)

    assert stats["top_expectancy"][0]["expectancy"] > stats["worst_expectancy"][0]["expectancy"]





def test_segmentation_unchanged():

    path = os.path.join(

        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

        "validation", "wave_segmentation_ETHUSDT_4h.csv",

    )

    if os.path.isfile(path):

        before = pd.read_csv(path)

        build_expectancy("ETHUSDT", "4h")

        after = pd.read_csv(path)

        assert len(before) == len(after)

        assert list(before.columns) == list(after.columns)


