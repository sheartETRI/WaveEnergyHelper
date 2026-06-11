"""스토캐스틱 쌍바닥/쌍봉 kind·delta 기록 + 골든(기존 결과 불변) 테스트 (작업 1).

실행: `python -m pytest tests/test_stoch_kind.py` 또는 `python tests/test_stoch_kind.py`
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import STOCH_LAYERS
from indicators.stochastic import (
    add_stochastic_slow_layers,
    classify_pattern_kind,
    detect_double_bottom_patterns,
    _INVERT_KIND_MAP,
)

_GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_golden_stoch.json")


def _reflect_ohlc(df):
    M = df["high"].max() + df["low"].max() + 10.0
    out = pd.DataFrame(index=df.index)
    out["open"] = M - df["open"]
    out["close"] = M - df["close"]
    out["high"] = M - df["low"]
    out["low"] = M - df["high"]
    out["volume"] = df["volume"]
    return out


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


def test_classifier_and_mapping():
    assert classify_pattern_kind(1.0, 2.0) == ("HL", 1.0)
    assert classify_pattern_kind(2.0, 1.0) == ("LL", -1.0)
    assert classify_pattern_kind(1.0, 1.0) == ("EQ", 0.0)
    # 반전 매핑: 바닥 HL/LL <-> 봉 LH/HH
    assert _INVERT_KIND_MAP == {"HL": "LH", "LL": "HH", "EQ": "EQ"}


def test_golden_recording_does_not_change_base_columns():
    """kind/delta 기록 분기가 db/candidate/neckline 결과를 바꾸지 않음을 고정."""
    df = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())
    s = STOCH_LAYERS[0]["label"]

    base = pd.DataFrame(index=df.index)
    base[f"stoch_k_{s}"] = df[f"stoch_k_{s}"]
    base[f"stoch_pivot_low_{s}"] = df[f"stoch_pivot_low_{s}"]

    no_kind = detect_double_bottom_patterns(
        base.copy(), f"stoch_k_{s}", f"stoch_pivot_low_{s}", "db", "cand", "neck"
    )
    with_kind = detect_double_bottom_patterns(
        base.copy(), f"stoch_k_{s}", f"stoch_pivot_low_{s}", "db", "cand", "neck",
        kind_col="k", delta_col="d",
    )

    for col in ("db", "cand", "neck"):
        assert no_kind[col].equals(with_kind[col]), f"base column {col} changed by kind recording"
    # kind 컬럼은 with_kind에만 존재
    assert "k" in with_kind.columns and "k" not in no_kind.columns


def test_stochastic_kind_matches_computed_delta():
    """기록된 kind가 '계산된' delta 부호와 일치하는지 검증 (상수 기록이 아님을 보장).

    주의: 특정 값(예: 항상 'HL')을 단정하지 않는다. db kind/delta는
    second_bottom_value - first_bottom_value 계산 결과여야 한다.
    """
    df = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())

    found_db = found_dt = 0
    for layer in STOCH_LAYERS:
        s = layer["label"]

        db = df[df[f"stoch_db_{s}"].notna()]
        for i in range(len(db)):
            kind = db[f"stoch_db_kind_{s}"].iloc[i]
            delta = float(db[f"stoch_db_delta_{s}"].iloc[i])
            expected = "HL" if delta > 0 else "LL" if delta < 0 else "EQ"
            assert kind == expected, f"db kind {kind} != computed {expected} (delta={delta})"
            found_db += 1

        dt = df[df[f"stoch_dt_{s}"].notna()]
        for i in range(len(dt)):
            kind = dt[f"stoch_dt_kind_{s}"].iloc[i]
            delta = float(dt[f"stoch_dt_delta_{s}"].iloc[i])
            # dt_delta = peak2 - peak1 (원공간): 낮아지면 LH, 높아지면 HH
            expected = "LH" if delta < 0 else "HH" if delta > 0 else "EQ"
            assert kind == expected, f"dt kind {kind} != computed {expected} (delta={delta})"
            found_dt += 1

    assert found_db > 0 and found_dt > 0


def test_golden_prepatch_HL_preserved():
    """패치 전(HL 전용) 확정되던 모든 db/dt가 패치 후에도 동일 봉에서 확정되어야 한다.

    LL/HH는 '추가'만 허용 (기존 확정은 손실 금지).
    """
    with open(_GOLDEN_PATH, encoding="utf-8") as fh:
        golden = json.load(fh)

    for seed_str, per_layer in golden.items():
        df = add_stochastic_slow_layers(_make_walk(400, int(seed_str)).copy())
        for s, cols in per_layer.items():
            db_now = set(np.where(df[f"stoch_db_{s}"].notna().values)[0].tolist())
            dt_now = set(np.where(df[f"stoch_dt_{s}"].notna().values)[0].tolist())
            assert set(cols["db"]).issubset(db_now), f"seed{seed_str} {s}: db 손실 {set(cols['db'])-db_now}"
            assert set(cols["dt"]).issubset(dt_now), f"seed{seed_str} {s}: dt 손실 {set(cols['dt'])-dt_now}"
            for pos in cols["db"]:
                assert df[f"stoch_db_kind_{s}"].iloc[pos] == "HL"
            for pos in cols["dt"]:
                assert df[f"stoch_dt_kind_{s}"].iloc[pos] == "LH"


def test_db_first_pos_matches_first_bottom():
    """확정 시 first_pos == 패턴 1번 바닥 iloc."""
    k = [80, 70, 55, 40, 25, 15, 15, 15, 15, 15,
         30, 45, 60,
         35, 8, 8,
         30, 55, 70, 85]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, index=idx, dtype="float64")})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[7] = 15.0
    pl.iloc[14] = 8.0
    df["pl"] = pl

    out = detect_double_bottom_patterns(
        df, "k", "pl", "db", "cand", "neck",
        kind_col="kind", delta_col="delta", first_pos_col="fp",
    )
    hits = out[out["db"].notna()]
    assert len(hits) == 1
    assert int(hits["fp"].iloc[0]) == 7


def test_first_pos_golden_base_columns_unchanged():
    """first_pos 기록이 db/candidate/neckline/kind/delta를 바꾸지 않음."""
    df = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())
    s = STOCH_LAYERS[0]["label"]
    base_cols = [f"stoch_db_{s}", f"stoch_db_candidate_{s}", f"stoch_neckline_{s}",
                 f"stoch_db_kind_{s}", f"stoch_db_delta_{s}",
                 f"stoch_dt_{s}", f"stoch_dt_kind_{s}", f"stoch_dt_delta_{s}"]
    before = df[base_cols].copy()
    after = add_stochastic_slow_layers(_make_walk(400, seed=7).copy())
    for col in base_cols:
        assert before[col].equals(after[col]), f"golden column changed: {col}"


def test_reversal_first_pos_symmetry():
    """상하 반전: db first_pos(반전) == dt first_pos(원본) — 위치 반전 매핑 없음."""
    base = _make_walk(500, seed=7)
    refl = _reflect_ohlc(base)
    do = add_stochastic_slow_layers(base.copy())
    dr = add_stochastic_slow_layers(refl.copy())
    for layer in STOCH_LAYERS:
        s = layer["label"]
        db_fp = dr[f"stoch_db_first_pos_{s}"]
        dt_fp = do[f"stoch_dt_first_pos_{s}"]
        assert db_fp.equals(dt_fp), f"first_pos symmetry broken for layer {s}"


def test_LL_double_bottom_confirmed():
    """첫 침체 길고 얕음(K≈15) + 두 번째 짧고 깊음(K≈8) + 넥라인 돌파 -> kind="LL" 확정."""
    k = [80, 70, 55, 40, 25, 15, 15, 15, 15, 15,
         30, 45, 60,
         35, 8, 8,
         30, 55, 70, 85]
    idx = pd.date_range("2024-01-01", periods=len(k), freq="D")
    df = pd.DataFrame({"k": pd.Series(k, index=idx, dtype="float64")})
    pl = pd.Series(pd.NA, index=idx, dtype="Float64")
    pl.iloc[7] = 15.0    # 첫 바닥(얕음)
    pl.iloc[14] = 8.0    # 두 번째 바닥(더 깊음)
    df["pl"] = pl

    out = detect_double_bottom_patterns(
        df, "k", "pl", "db", "cand", "neck", kind_col="kind", delta_col="delta"
    )
    hits = out[out["db"].notna()]
    assert len(hits) == 1, f"db 확정 1건 기대, 실제 {len(hits)}"
    assert hits["kind"].iloc[0] == "LL"
    assert float(hits["delta"].iloc[0]) < 0  # second(8) - first(15) < 0


def test_reversal_symmetry_includes_HH():
    """가격 상하 반전 시 db(반전) 마스크 == dt(원본) 마스크. LL 도입으로 HH(dt)도 나타난다."""
    base = _make_walk(500, seed=7)
    refl = _reflect_ohlc(base)
    do = add_stochastic_slow_layers(base.copy())
    dr = add_stochastic_slow_layers(refl.copy())

    seen_kinds = set()
    for layer in STOCH_LAYERS:
        s = layer["label"]
        db_refl = dr[f"stoch_db_{s}"].notna().values
        dt_orig = do[f"stoch_dt_{s}"].notna().values
        assert np.array_equal(db_refl, dt_orig)
        dt_kinds = do.loc[do[f"stoch_dt_{s}"].notna(), f"stoch_dt_kind_{s}"]
        seen_kinds.update(dt_kinds.tolist())

    assert "HH" in seen_kinds and "LH" in seen_kinds, f"observed dt kinds={seen_kinds}"


if __name__ == "__main__":
    test_classifier_and_mapping()
    test_golden_recording_does_not_change_base_columns()
    test_stochastic_kind_matches_computed_delta()
    test_golden_prepatch_HL_preserved()
    test_db_first_pos_matches_first_bottom()
    test_first_pos_golden_base_columns_unchanged()
    test_reversal_first_pos_symmetry()
    test_LL_double_bottom_confirmed()
    test_reversal_symmetry_includes_HH()
    print("ALL STOCH KIND TESTS PASSED")
