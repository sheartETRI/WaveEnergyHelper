"""Wave Exit 분석 테스트."""

import os

import sys



import pandas as pd



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from analysis.wave_exit import (

    POLICY_A,

    POLICY_RULES,

    RULE_K_CROSS,

    RULE_K_TURN,

    RULE_SL3,

    RULE_TIMEOUT20,

    RULE_TP3,

    _cross_down_at,

    _hits_at_bar,

    _k_turn_down_at,

    _resolve_policy_hit,

    evaluate_policy,

)

from analysis.wave_outcome import build_outcomes_from_lifecycle





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





def _pipeline(n, k_vals, d_vals):

    idx = pd.date_range("2026-01-01", periods=n, freq="4h")

    return pd.DataFrame({

        f"stoch_k_(20,10,10)": k_vals,

        f"stoch_d_(20,10,10)": d_vals,

    }, index=idx)





def _zeros(n):

    return pd.Series([False] * n)





def test_tp3_hit():

    ohlcv = _ohlcv([100.0] * 10, highs=[100, 100, 100, 104, 100, 100, 100, 100, 100, 100])

    k = pd.Series([50.0] * 10)

    d = pd.Series([55.0] * 10)

    hits = _hits_at_bar(3, 0, 100.0, ohlcv, k, d, _zeros(10), _zeros(10))

    assert RULE_TP3 in hits





def test_sl3_hit():

    ohlcv = _ohlcv([100.0] * 10, lows=[100, 100, 100, 96, 100, 100, 100, 100, 100, 100])

    k = pd.Series([50.0] * 10)

    d = pd.Series([55.0] * 10)

    hits = _hits_at_bar(3, 0, 100.0, ohlcv, k, d, _zeros(10), _zeros(10))

    assert RULE_SL3 in hits





def test_same_bar_tp_sl_sl_wins():

    hits = [RULE_TP3, RULE_SL3]

    chosen = _resolve_policy_hit(hits, POLICY_RULES[POLICY_A])

    assert chosen == RULE_SL3





def test_timeout20():

    ohlcv = _ohlcv([100.0] * 30)

    k = pd.Series([50.0] * 30)

    d = pd.Series([55.0] * 30)

    pipe = _pipeline(30, k, d)

    k_s, d_s, os_s, ll_s = pipe.iloc[:, 0], pipe.iloc[:, 1], _zeros(30), _zeros(30)

    result = evaluate_policy(0, 100.0, ohlcv, k_s, d_s, os_s, ll_s, POLICY_RULES[POLICY_A])

    assert result is not None

    assert result["exit_reason"] == RULE_TIMEOUT20

    assert result["bars_held"] == 20





def test_k_turn_down():

    k = pd.Series([40.0, 41.0, 41.0, 39.0])

    assert _k_turn_down_at(k, 3)





def test_k_cross_down():

    k = pd.Series([50.0, 55.0, 54.0])

    d = pd.Series([56.0, 55.0, 55.0])

    assert _cross_down_at(k, d, 2)





def test_policy_priority_tp_before_timeout():

    ohlcv = _ohlcv([100.0] * 30, highs=[100.0] * 5 + [106.0] + [100.0] * 24)

    k = pd.Series([50.0] * 30)

    d = pd.Series([55.0] * 30)

    os_s, ll_s = _zeros(30), _zeros(30)

    result = evaluate_policy(0, 100.0, ohlcv, k, d, os_s, ll_s, POLICY_RULES[POLICY_A])

    assert result["exit_reason"] == RULE_TP3





def test_outcome_unchanged():

    closes = [100.0 + i * 0.5 for i in range(30)]

    ohlcv = _ohlcv(closes)

    lc = pd.DataFrame([{

        "timestamp": ohlcv.index[5],

        "initial_outcome": "SLOPE_CONFIRMED",

        "post_outcome": "HELD",

        "bars_until_initial": 0,

        "bars_until_post": 20,

        "bars_held_after_initial": 20,

    }])

    out = build_outcomes_from_lifecycle(lc, ohlcv)

    assert out.iloc[0]["return_20"] is not None


