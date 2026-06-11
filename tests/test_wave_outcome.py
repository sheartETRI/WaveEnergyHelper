"""Wave Outcome 분석 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_outcome import (

    INITIAL_SLOPE,

    OUTCOME_HORIZONS,

    build_outcomes_from_lifecycle,

    compute_episode_outcome,

    summarize_outcomes,

    _forward_return,

    _mfe,

    _mae,

)

from analysis.wave_survival import (

    INITIAL_CROSS,

    build_survival_from_lifecycle,

    survival_rate_at,

)





def _ohlcv(closes, highs=None, lows=None):

    n = len(closes)

    idx = pd.date_range("2026-01-01", periods=n, freq="4h")

    return pd.DataFrame({

        "open": closes,

        "high": highs or closes,

        "low": lows or closes,

        "close": closes,

        "volume": [1.0] * n,

    }, index=idx)





def test_forward_return():

    close = pd.Series([100.0, 105.0, 110.0, 115.0])

    assert abs(_forward_return(close, 0, 2) - 0.10) < 1e-9





def test_mfe_calculation():

    high = pd.Series([100.0, 105.0, 118.0, 110.0])

    assert abs(_mfe(high, 0, 2, 100.0) - 0.18) < 1e-9





def test_mae_calculation():

    low = pd.Series([100.0, 98.0, 92.0, 95.0])

    assert abs(_mae(low, 0, 2, 100.0) - (-0.08)) < 1e-9





def test_win_rate_in_summary():

    closes = [100.0] * 30

    for i in range(10, 30):

        closes[i] = 110.0

    ohlcv = _ohlcv(closes)

    lc = pd.DataFrame([{

        "timestamp": ohlcv.index[5],

        "initial_outcome": INITIAL_SLOPE,

        "post_outcome": "HELD",

        "bars_until_initial": 0,

        "bars_until_post": 25,

        "bars_held_after_initial": 20,

    }])

    out = build_outcomes_from_lifecycle(lc, ohlcv)

    stats = summarize_outcomes(out)

    assert stats["by_type"][INITIAL_SLOPE]["win_20"] == 100.0





def test_survival_filter_in_summary():

    rows = []

    for i, held in enumerate([10, 50]):

        rows.append({

            "timestamp": pd.Timestamp(f"2026-01-{2+i*5}"),

            "initial_outcome": INITIAL_SLOPE,

            "post_outcome": "LATER_RE_OVERSOLD",

            "bars_until_initial": 0,

            "bars_until_post": held,

            "bars_held_after_initial": held,

        })

    closes = [100.0 + j * 0.5 for j in range(80)]

    ohlcv = _ohlcv(closes)

    ohlcv.index = pd.date_range("2026-01-01", periods=80, freq="4h")

    rows[0]["timestamp"] = ohlcv.index[5]

    rows[1]["timestamp"] = ohlcv.index[10]

    out = build_outcomes_from_lifecycle(pd.DataFrame(rows), ohlcv)

    stats = summarize_outcomes(out)

    sc40 = stats["by_type"][INITIAL_SLOPE]["survival_cond"][40]

    assert sc40["count"] == 1





def test_survival_unchanged():

    lc = pd.DataFrame([{

        "timestamp": "2026-01-01",

        "initial_outcome": INITIAL_CROSS,

        "post_outcome": "LATER_RE_OVERSOLD",

        "bars_until_initial": 1,

        "bars_until_post": 10,

        "bars_held_after_initial": 9,

    }])

    sv = build_survival_from_lifecycle(lc)

    assert sv.iloc[0]["survival_bars"] == 9

    assert survival_rate_at(sv, 5, INITIAL_CROSS) == 100.0


