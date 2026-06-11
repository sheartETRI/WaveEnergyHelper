"""Wave Confluence 테스트."""

import os

import sys



import numpy as np

import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_confluence import (

    BRANCH_REQUIRED,

    _rsi_bucket,

    add_confluence_indicators,

    build_confluence,

    confluence_score,

    extract_confluence_at,

    summarize_confluence,

)

from analysis.wave_segmentation import MIN_SAMPLE





def _ohlcv(n=80):

    idx = pd.date_range("2025-01-01", periods=n, freq="4h")

    close = np.linspace(100, 130, n) + np.random.default_rng(0).normal(0, 1, n)

    return pd.DataFrame({

        "open": close,

        "high": close + 2,

        "low": close - 2,

        "close": close,

        "volume": 1000,

    }, index=idx)





def test_macd_calculation():

    df = add_confluence_indicators(_ohlcv())

    assert "macd" in df.columns

    assert "macd_signal" in df.columns

    assert "macd_hist" in df.columns

    assert "macd_gap" in df.columns





def test_rsi_bucket():

    assert _rsi_bucket(25) == "<30"

    assert _rsi_bucket(45) == "40-50"

    assert _rsi_bucket(75) == "70+"





def test_ema_state():

    df = add_confluence_indicators(_ohlcv())

    feats = extract_confluence_at(df, len(df) - 1)

    assert "EMA20_GT_60" in feats

    assert "PRICE_ABOVE_60" in feats





def test_lift_calculation():

    df = pd.DataFrame({

        "success": [True, True, False, False, False],

        "return_pct": [3, 3, -3, -3, -3],

        "MACD_GC_RECENT": [True, True, False, False, False],

        "cohort": ["SUCCESS"] * 2 + ["FAILURE"] * 3,

        "confluence_score": [3, 3, 1, 1, 0],

        "branch": [BRANCH_REQUIRED] * 2 + ["WAVE3_COMPLETED"] * 3,

        "branch_label": [BRANCH_REQUIRED] * 2 + ["WAVE3_COMPLETED"] * 3,

        "rsi_bucket": ["40-50"] * 5,

        "RSI_RECOVERING": [True, False, False, False, False],

    })

    stats = summarize_confluence(df, "ETHUSDT")

    assert any(f.get("lift", 0) > 1 for f in stats["categorical_lift"])





def test_bundle_calculation():

    rows = []

    for i in range(6):

        rows.append({

            "return_pct": 3.0 if i < 4 else -3.0,

            "success": i < 4,

            "branch_label": BRANCH_REQUIRED,

            "MACD_GC_RECENT": True,

            "RSI_RECOVERING": True,

            "cohort": "SUCCESS" if i < 4 else "FAILURE",

            "confluence_score": 4,

            "rsi_bucket": "40-50",

        })

    stats = summarize_confluence(pd.DataFrame(rows), "ETHUSDT")

    assert any(b["n"] >= MIN_SAMPLE for b in stats["top_confluence_bundles"])





def test_score_calculation():

    row = pd.Series({

        "MACD_GC_RECENT": True,

        "RSI_RECOVERING": True,

        "EMA20_GT_60": False,

        "PRICE_ABOVE_60": True,

        "branch": BRANCH_REQUIRED,

    })

    assert confluence_score(row) == 4





def test_branch_unchanged():

    path = os.path.join(

        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

        "validation", "wave_branch_ETHUSDT_4h.csv",

    )

    if os.path.isfile(path):

        before = pd.read_csv(path)

        build_confluence("ETHUSDT", "4h", pd.DataFrame(), None)

        after = pd.read_csv(path)

        assert len(before) == len(after)


