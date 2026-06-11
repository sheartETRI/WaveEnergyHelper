"""쓰리바닥/쓰리봉 검출 테스트 (작업 2) — §6-④⑤ 선행 인프라.

실행: `python -m pytest tests/test_triple_patterns.py` 또는 `python tests/test_triple_patterns.py`
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import STOCH_LAYERS
from indicators.stochastic import (
    add_stochastic_slow_layers,
    detect_double_bottom_patterns,
    detect_triple_bottom_patterns,
    detect_stochastic_triple_bottom_patterns,
    detect_stochastic_triple_top_patterns,
    detect_stochastic_bottom_patterns,
    detect_stochastic_top_patterns,
)


def _make_walk(n, seed):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 1.0, n))
    close = np.maximum(close, 1.0)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    high = close + np.abs(rng.normal(0, 0.5, n))
    low = close - np.abs(rng.normal(0, 0.5, n))
    high = np.maximum.reduce([high, close, low + 0.01])
    low = np.minimum(low, close)
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0}, index=idx
    )


def _triple_bottom_df():
    """침체권 바닥 3개(15,12,18) + 넥라인(45) 상향 돌파(pos12) 합성 파동."""
    k = [50, 30, 15, 30, 45, 30, 12, 30, 40, 25, 18, 35, 50, 60]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, index=idx, dtype="float64")})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[2] = 15.0    # 바닥1
    pl.iloc[6] = 12.0    # 바닥2
    pl.iloc[10] = 18.0   # 바닥3
    df["pl"] = pl
    return df, idx


def test_triple_bottom_confirmed_with_db_coexistence():
    df, idx = _triple_bottom_df()

    tb = detect_triple_bottom_patterns(
        df.copy(), "k", "pl", "tb", "tb_kind", "tb_delta", oversold_level=20.0
    )
    hits = tb[tb["tb"].notna()]
    assert len(hits) == 1, f"쓰리바닥 1건 기대, 실제 {len(hits)}"
    assert hits.index[0] == idx[12]
    assert hits["tb_kind"].iloc[0] == "HL"          # 바닥3(18) > 바닥2(12)
    assert float(hits["tb_delta"].iloc[0]) > 0

    # 공존: 같은 데이터에서 db도 기록 유지 (쓰리바닥이 쌍바닥을 소급 제거하지 않음)
    db = detect_double_bottom_patterns(df.copy(), "k", "pl", "db", "cand", "neck")
    assert db["db"].notna().any(), "동일 데이터에서 db도 기록되어야 한다 (공존)"


def test_only_two_bottoms_no_triple():
    k = [50, 30, 15, 30, 45, 30, 12, 40, 55, 65]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, index=idx, dtype="float64")})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[2] = 15.0
    pl.iloc[6] = 12.0
    df["pl"] = pl

    tb = detect_triple_bottom_patterns(
        df.copy(), "k", "pl", "tb", "tb_kind", "tb_delta", oversold_level=20.0
    )
    assert tb["tb"].notna().sum() == 0, "바닥 2개뿐이면 쓰리바닥 미검출"

    db = detect_double_bottom_patterns(df.copy(), "k", "pl", "db", "cand", "neck")
    assert db["db"].notna().any(), "쌍바닥은 정상 검출"


def test_reversal_symmetry_tb_tt():
    """반전 대칭: tt(반전 입력) 마스크 == tb(원본) 마스크, kind HL->LH, delta 부호 반전."""
    s = STOCH_LAYERS[2]["label"]   # 임의 suffix 하나
    df, idx = _triple_bottom_df()

    orig = pd.DataFrame(index=idx)
    orig[f"stoch_k_{s}"] = df["k"].astype("float64")
    orig[f"stoch_pivot_low_{s}"] = df["pl"]
    orig[f"stoch_pivot_high_{s}"] = pd.Series(pd.NA, index=idx, dtype="Float64")

    tb = detect_stochastic_triple_bottom_patterns(orig.copy(), s, oversold_level=20.0)

    # 가격 상하 반전: k -> 100-k, pivot low/high 교환
    refl = pd.DataFrame(index=idx)
    refl[f"stoch_k_{s}"] = 100.0 - orig[f"stoch_k_{s}"]
    refl[f"stoch_pivot_low_{s}"] = 100.0 - orig[f"stoch_pivot_high_{s}"]
    refl[f"stoch_pivot_high_{s}"] = 100.0 - orig[f"stoch_pivot_low_{s}"]

    tt = detect_stochastic_triple_top_patterns(refl.copy(), s, overbought_level=80.0)

    tb_mask = tb[f"stoch_tb_{s}"].notna().values
    tt_mask = tt[f"stoch_tt_{s}"].notna().values
    assert np.array_equal(tb_mask, tt_mask), "tt 마스크가 tb 마스크와 대칭이 아님"

    pos = int(np.where(tb_mask)[0][0])
    assert tb[f"stoch_tb_kind_{s}"].iloc[pos] == "HL"
    assert tt[f"stoch_tt_kind_{s}"].iloc[pos] == "LH"            # HL -> LH 매핑
    assert float(tt[f"stoch_tt_delta_{s}"].iloc[pos]) == -float(tb[f"stoch_tb_delta_{s}"].iloc[pos])


def test_full_pipeline_symmetry_three_layers():
    """전체 파이프라인에서도 tt(원본) 마스크 == tb(반전 OHLC) 마스크 (3개 레이어)."""
    base = _make_walk(500, seed=11)
    M = base["high"].max() + base["low"].max() + 10.0
    refl = pd.DataFrame(index=base.index)
    refl["open"] = M - base["open"]
    refl["close"] = M - base["close"]
    refl["high"] = M - base["low"]
    refl["low"] = M - base["high"]
    refl["volume"] = base["volume"]

    do = add_stochastic_slow_layers(base.copy())
    dr = add_stochastic_slow_layers(refl.copy())
    for layer in STOCH_LAYERS:
        s = layer["label"]
        assert np.array_equal(
            do[f"stoch_tt_{s}"].notna().values, dr[f"stoch_tb_{s}"].notna().values
        ), f"{s}: tt(원본) != tb(반전)"


def test_golden_db_dt_columns_unchanged_by_triple():
    """골든: 쓰리 패턴 추가가 기존 db/dt 전 컬럼을 바꾸지 않음을 고정.

    전체 파이프라인 결과의 db/dt 컬럼이, 동일 피봇에 대해 db/dt 검출기를 다시 돌린
    결과와 완전히 동일해야 한다 (triple 함수가 db/dt에 손대지 않음).
    """
    full = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())

    db_cols = ["stoch_db_{s}", "stoch_db_candidate_{s}", "stoch_neckline_{s}",
               "stoch_db_kind_{s}", "stoch_db_delta_{s}"]
    dt_cols = ["stoch_dt_{s}", "stoch_dt_candidate_{s}", "stoch_dt_neckline_{s}",
               "stoch_dt_kind_{s}", "stoch_dt_delta_{s}"]

    for layer in STOCH_LAYERS:
        s = layer["label"]
        base = pd.DataFrame(index=full.index)
        base[f"stoch_k_{s}"] = full[f"stoch_k_{s}"]
        base[f"stoch_pivot_low_{s}"] = full[f"stoch_pivot_low_{s}"]
        base[f"stoch_pivot_high_{s}"] = full[f"stoch_pivot_high_{s}"]

        redo_db = detect_stochastic_bottom_patterns(base.copy(), s)
        redo_dt = detect_stochastic_top_patterns(base.copy(), s)

        for tmpl in db_cols:
            col = tmpl.format(s=s)
            assert full[col].equals(redo_db[col]), f"{col} 변경됨 (triple이 db에 영향)"
        for tmpl in dt_cols:
            col = tmpl.format(s=s)
            assert full[col].equals(redo_dt[col]), f"{col} 변경됨 (triple이 dt에 영향)"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL TRIPLE PATTERN TESTS PASSED")
