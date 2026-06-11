"""Wave Segmentation 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_segmentation import (

    MIN_SAMPLE,

    _combo_conditions,

    classify_success,

    survival_bucket,

    summarize_segmentation,

)

from analysis.wave_exit import POLICY_A





def test_success_classification():

    assert classify_success(1.0) == (True, False, False)

    assert classify_success(-1.0) == (False, False, False)

    assert classify_success(0.0) == (False, False, False)





def test_strong_success():

    assert classify_success(3.5)[1] is True





def test_strong_failure():

    assert classify_success(-3.5)[2] is True





def test_survival_bucket():

    assert survival_bucket(5) == "<10"

    assert survival_bucket(15) == "10-19"

    assert survival_bucket(25) == "20-39"

    assert survival_bucket(50) == "40+"





def test_condition_combo_min_sample():

    rows = []

    for i in range(6):

        rows.append({

            "initial_type": "SLOPE",

            "survival_bucket": "20-39",

            "state": "WAVE3_ACTIVE",

            "family": "BUY_FAMILY",

            "stable_family": "BUY_FAMILY",

            "category": "매수유효",

            "survival_bars": 25,

            "success": i < 4,

        })

    for i in range(3):

        rows.append({

            "initial_type": "CROSS",

            "survival_bucket": "<10",

            "state": "OTHER",

            "family": "NEUTRAL",

            "stable_family": "NEUTRAL",

            "category": "관망/혼조",

            "survival_bars": 5,

            "success": False,

        })

    df = pd.DataFrame(rows)

    combos = _combo_conditions(df)

    assert any(c["n"] >= MIN_SAMPLE for c in combos)

    assert all(c["n"] >= MIN_SAMPLE for c in combos)





def test_min_sample_filter_top_factors():

    df = pd.DataFrame([

        {"initial_type": "SLOPE", "success": True, "failure_rate": 0,

         "success_rate": 100, "n": 3, "label": "x"},

    ])

    stats = summarize_segmentation(pd.DataFrame([

        {"initial_type": "SLOPE", "state": "WAVE3_ACTIVE", "survival_bucket": "20-39",

         "category": "매수유효", "family": "BUY_FAMILY", "stable_family": "BUY_FAMILY",

         "survival_bars": 25, "success": True, "strong_success": False,

         "strong_failure": False, "return_pct": 1.0},

    ] * 6))

    assert len(stats["top_success"]) >= 1





def test_exit_unchanged():

    path = os.path.join(

        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

        "validation", "wave_exit_ETHUSDT_4h.csv",

    )

    if os.path.isfile(path):

        df = pd.read_csv(path)

        tp3 = df[df["policy"] == POLICY_A]

        assert len(tp3) > 0

        assert "return_pct" in tp3.columns


