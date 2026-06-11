"""[F7-a] 깔끔함 prev_opp 기록 + clean 관측 테스트.

실행: python -m pytest tests/test_pattern_clean.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import MA_PATTERN_PARAMS, STOCH_LAYERS
from indicators.stochastic import add_stochastic_slow_layers, detect_double_bottom_patterns
from indicators.ma_patterns import _detect_series_double_bottom, _detect_series_double_top
from indicators.pattern_clean import classify_clean
from tests.test_stoch_kind import _make_walk, _reflect_ohlc
from tests.test_ma_patterns import _w_series, _frame
from tests.test_dispersion_annotation import EXPECTED_ZONE_HITS
from validation.gt_trace import load_df_gt, zone_ranges, evaluate_transition_in_zone, SYMBOL, INTERVAL, fmt_ts

P = MA_PATTERN_PARAMS


def _synthetic_db_with_prev_opp():
    k = [70, 65, 55, 45, 35, 30, 25, 20, 18, 15,
         25, 35, 45,
         30, 18, 15,
         28, 40, 55, 70]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, dtype="float64", index=idx)})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    ph = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[9] = 15.0
    pl.iloc[15] = 15.0
    ph.iloc[4] = 35.0
    df["pl"] = pl
    df["ph"] = ph
    return df


def test_prev_opp_recorded_on_db_confirm():
    df = _synthetic_db_with_prev_opp()
    out = detect_double_bottom_patterns(
        df, "k", "pl", "db", "cand", "neck",
        kind_col="kind", pivot_high_col="ph", prev_opp_col="prev_opp",
    )
    hits = out[out["db"].notna()]
    assert len(hits) == 1
    assert float(hits["prev_opp"].iloc[0]) == 35.0


def test_prev_opp_nan_when_no_prior_opposite():
    k = [15, 18, 15, 18, 15, 18, 25, 35, 45, 55]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, dtype="float64", index=idx)})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    ph = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[2] = 15.0
    pl.iloc[4] = 15.0
    df["pl"] = pl
    df["ph"] = ph
    out = detect_double_bottom_patterns(
        df, "k", "pl", "db", "cand", "neck",
        pivot_high_col="ph", prev_opp_col="prev_opp",
    )
    hits = out[out["db"].notna()]
    if len(hits):
        assert pd.isna(hits["prev_opp"].iloc[0])


def test_stoch_reversal_prev_opp_100_minus_v():
    base = _make_walk(500, seed=11)
    refl = _reflect_ohlc(base)
    do = add_stochastic_slow_layers(base.copy())
    dr = add_stochastic_slow_layers(refl.copy())
    for layer in STOCH_LAYERS:
        s = layer["label"]
        db_po = dr[f"stoch_db_prev_opp_{s}"]
        dt_po = do[f"stoch_dt_prev_opp_{s}"]
        mask = db_po.notna() & dt_po.notna()
        if not mask.any():
            continue
        np.testing.assert_allclose(
            db_po[mask].astype(float).values,
            (100.0 - dt_po[mask].astype(float)).values,
            rtol=1e-9,
        )


def test_ma_reversal_prev_opp_sign():
    v = _w_series(10, 20)
    idx = pd.date_range("2024-01-01", periods=len(v), freq="D")
    M = v.max() + v.min() + 10.0
    b = _detect_series_double_bottom(
        _frame(v), "MA5", "pl", "ph", "db", "db_kind", P["decline_lookback"],
        prev_opp_col="db_prev_opp",
    )
    r = pd.DataFrame({"MA5": pd.Series(M - v, index=idx)})
    r = _detect_series_double_top(r, "MA5", "unused", "dt", P)
    db_mask = b["db"].notna().values
    if db_mask.any():
        inv_po = b.loc[b["db"].notna(), "db_prev_opp"].astype(float)
        dt_po = r.loc[r["dt"].notna(), "dt_prev_opp"].astype(float)
        np.testing.assert_allclose((-inv_po).values, dt_po.values, rtol=1e-9)


def test_golden_base_columns_unchanged():
    df = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())
    s = STOCH_LAYERS[0]["label"]
    base_cols = [
        f"stoch_db_{s}", f"stoch_db_candidate_{s}", f"stoch_neckline_{s}",
        f"stoch_db_kind_{s}", f"stoch_db_delta_{s}",
        f"stoch_dt_{s}", f"stoch_dt_candidate_{s}", f"stoch_dt_neckline_{s}",
        f"stoch_dt_kind_{s}", f"stoch_dt_delta_{s}",
        f"stoch_db_first_pos_{s}", f"stoch_dt_first_pos_{s}",
    ]
    before = df[base_cols].copy()
    after = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())
    for col in base_cols:
        assert before[col].equals(after[col]), f"golden column changed: {col}"


def test_zone_hit_snapshot_unchanged():
    df, _ = load_df_gt(SYMBOL, INTERVAL)
    zones = zone_ranges(df)
    found = set()
    for z in zones:
        _, events, _ = evaluate_transition_in_zone(df, z["buffer_pos"])
        for e in events:
            if e["mode"] != "HIT":
                continue
            found.add((
                z["id"], e["rule_id"], fmt_ts(e["form_ts"]), fmt_ts(e["comp_ts"]),
            ))
    assert found == EXPECTED_ZONE_HITS


def test_classify_clean_hl_lh():
    assert classify_clean("db", "HL", 50.0, 40.0) == "clean"
    assert classify_clean("db", "HL", 40.0, 50.0) == "not-clean"
    assert classify_clean("dt", "LH", 40.0, 50.0) == "clean"
    assert classify_clean("db", "HL", 50.0, None) == "indeterminate"
