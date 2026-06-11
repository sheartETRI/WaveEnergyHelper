"""Wave Branch Analysis 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_branch_analysis import (

    BRANCH_COMPLETED,

    BRANCH_REQUIRED,

    build_branch_analysis,

    categorical_lift,

    effect_size,

    extract_double_bottom_events,

    resolve_branch,

    summarize_branch_analysis,

)





def _tracker():

    ts = pd.date_range("2025-01-01", periods=8, freq="4h")

    states = [

        "WAVE3_ACTIVE",

        "DOUBLE_BOTTOM_CANDIDATE",

        "DOUBLE_BOTTOM_CANDIDATE",

        "WAVE3_COMPLETED",

        "WAVE3_COMPLETED",

        "WAVE3_ACTIVE",

        "DOUBLE_BOTTOM_CANDIDATE",

        "TRIPLE_BOTTOM_REQUIRED",

    ]

    return pd.DataFrame({"timestamp": ts, "state": states})





def test_double_bottom_extraction():

    ev = extract_double_bottom_events(_tracker())

    assert len(ev) == 2





def test_branch_labeling():

    tr = _tracker()

    assert resolve_branch(tr, 1) == BRANCH_COMPLETED

    assert resolve_branch(tr, 6) == BRANCH_REQUIRED





def test_numeric_feature_effect_size():

    a = pd.Series([10.0, 12.0, 11.0])

    b = pd.Series([20.0, 22.0, 21.0])

    assert effect_size(a, b) > 0





def test_categorical_lift():

    df = pd.DataFrame([

        {"branch": BRANCH_REQUIRED, "major_k_level_bucket": "20-40"},

        {"branch": BRANCH_REQUIRED, "major_k_level_bucket": "20-40"},

        {"branch": BRANCH_COMPLETED, "major_k_level_bucket": "60-80"},

        {"branch": BRANCH_COMPLETED, "major_k_level_bucket": "60-80"},

    ])

    lifts = categorical_lift(df, "major_k_level_bucket")

    assert any(x["lift"] > 1 for x in lifts)





def test_branch_performance():

    df = pd.DataFrame([

        {"branch": BRANCH_REQUIRED, "return_pct": 3.0, "major_k": 30},

        {"branch": BRANCH_REQUIRED, "return_pct": 3.0, "major_k": 32},

        {"branch": BRANCH_COMPLETED, "return_pct": -3.0, "major_k": 70},

        {"branch": BRANCH_COMPLETED, "return_pct": -3.0, "major_k": 72},

    ])

    stats = summarize_branch_analysis(df)

    assert stats["branch_performance"][BRANCH_REQUIRED]["expectancy"] > 0

    assert stats["branch_performance"][BRANCH_COMPLETED]["expectancy"] < 0





def test_top_bottom_sort():
    rows = []
    for i in range(5):
        rows.append({
            "branch": BRANCH_REQUIRED, "return_pct": 3.0,
            "major_k": 20.0 + i, "major_k_level_bucket": "20-40",
        })
        rows.append({
            "branch": BRANCH_COMPLETED, "return_pct": -3.0,
            "major_k": 70.0 + i, "major_k_level_bucket": "60-80",
        })
    stats = summarize_branch_analysis(pd.DataFrame(rows))
    assert stats["top_numeric_separators"][0]["effect_size"] > 0





def test_paths_unchanged():

    path = os.path.join(

        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

        "validation", "wave_paths_ETHUSDT_4h.csv",

    )

    if os.path.isfile(path):

        before = pd.read_csv(path)

        build_branch_analysis("ETHUSDT", "4h", pd.DataFrame(), None)

        after = pd.read_csv(path)

        assert len(before) == len(after)


