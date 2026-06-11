"""Wave Paths 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_path_analysis import (

    PATH_SEP,

    aggregate_paths,

    build_path_rows,

    compress_path,

    compute_transitions,

    extract_state_sequence,

    summarize_paths,

)

from analysis.wave_segmentation import MIN_SAMPLE





def _tracker_df():

    ts = pd.date_range("2025-01-01", periods=12, freq="4h")

    states = [

        "NONE", "WAVE3_CANDIDATE", "WAVE3_ACTIVE", "DOUBLE_BOTTOM_CANDIDATE",

        "TRIPLE_BOTTOM_REQUIRED", "TRIPLE_BOTTOM_REQUIRED",

        "WAVE3_COMPLETED", "WAVE3_COMPLETED", "NONE", "WAVE3_ACTIVE",

        "DOUBLE_BOTTOM_CANDIDATE", "WAVE3_COMPLETED",

    ]

    return pd.DataFrame({"timestamp": ts, "state": states})





def test_path_generation():

    tr = _tracker_df()

    db = pd.Timestamp("2025-01-01 16:00:00")

    seq = extract_state_sequence(tr, db, 0)

    assert "DOUBLE_BOTTOM" in seq

    path = compress_path(seq, "SLOPE", True)

    assert "SLOPE" in path

    assert "TP3_WIN" in path





def test_path_compression():

    df = pd.DataFrame([

        {"path": "A → B → SLOPE → TP3_WIN", "return_pct": 3.0,

         "survival_bars": 10, "wave_states": "A → B"},

        {"path": "A → B → SLOPE → TP3_LOSS", "return_pct": -3.0,

         "survival_bars": 12, "wave_states": "A → B"},

    ])

    agg = aggregate_paths(df)

    assert len(agg) == 2





def test_transition_calculation():

    df = pd.DataFrame([

        {"wave_states": "WAVE3_ACTIVE → DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRED"},

        {"wave_states": "WAVE3_ACTIVE → DOUBLE_BOTTOM → WAVE3_COMPLETED"},

        {"wave_states": "WAVE3_ACTIVE → DOUBLE_BOTTOM → WAVE3_COMPLETED"},

    ])

    trans, _ = compute_transitions(df)

    assert any(t["from"] == "DOUBLE_BOTTOM" for t in trans)





def test_expectancy_aggregation():

    rows = []

    for ret in [3.0, 3.0, 3.0, -3.0, -3.0]:

        rows.append({

            "path": "WAVE3_ACTIVE → DOUBLE_BOTTOM → SLOPE → TP3_WIN"

            if ret > 0 else

            "WAVE3_ACTIVE → WAVE3_COMPLETED → SLOPE → TP3_LOSS",

            "return_pct": ret,

            "survival_bars": 20,

            "wave_states": "WAVE3_ACTIVE → DOUBLE_BOTTOM",

        })

    stats = summarize_paths(pd.DataFrame(rows))

    win = next(

        p for p in stats["by_path"]

        if "TP3_WIN" in p["path"]

    )

    assert win["expectancy"] > 0





def test_top_bottom_sort():

    rows = []

    for _ in range(6):

        rows.append({

            "path": "GOOD → SLOPE → TP3_WIN",

            "return_pct": 3.0, "survival_bars": 10,

            "wave_states": "GOOD",

        })

    for _ in range(6):

        rows.append({

            "path": "BAD → SLOPE → TP3_LOSS",

            "return_pct": -3.0, "survival_bars": 5,

            "wave_states": "BAD",

        })

    stats = summarize_paths(pd.DataFrame(rows))

    assert stats["top_winning_paths"][0]["expectancy"] > 0

    assert stats["top_losing_paths"][0]["expectancy"] < 0





def test_min_sample_filter():

    rows = [{"path": "X → SLOPE → TP3_WIN", "return_pct": 1.0,

             "survival_bars": 1, "wave_states": "X"}] * 3

    stats = summarize_paths(pd.DataFrame(rows))

    assert len(stats["top_winning_paths"]) == 0





def test_expectancy_unchanged():

    path = os.path.join(

        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

        "validation", "wave_expectancy_ETHUSDT_4h.csv",

    )

    if os.path.isfile(path):

        before = pd.read_csv(path)

        build_path_rows("ETHUSDT", "4h")

        after = pd.read_csv(path)

        assert len(before) == len(after)

        assert list(before.columns) == list(after.columns)


