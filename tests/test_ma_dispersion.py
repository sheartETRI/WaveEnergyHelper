"""MA dispersion 지표 테스트.

실행: python -m pytest tests/test_ma_dispersion.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CORE_MA_PERIODS, MA_PATTERN_PARAMS
from indicators.ma_dispersion import compute_ma_dispersion_series, add_ma_dispersion
from indicators.ma_patterns import compute_series_pivots


def _df_from_ma_close(ma_dict, close):
    idx = pd.date_range("2024-01-01", periods=len(close), freq="D")
    data = {"close": close}
    for p in CORE_MA_PERIODS:
        data[f"MA{p}"] = ma_dict[p]
    return pd.DataFrame(data, index=idx)


def test_converging_fan_monotone_decrease():
    """합성 수렴 부채 → dispersion 단조 감소."""
    n = 40
    t = np.arange(n, dtype=float)
    # 이평들이 선형 수렴: 간격이 줄어듦
    base = 100.0
    ma = {
        5: base + 20 * np.exp(-t / 8),
        10: base + 15 * np.exp(-t / 8),
        20: base + 10 * np.exp(-t / 8),
        60: base + 6 * np.exp(-t / 8),
        120: base + 3 * np.exp(-t / 8),
        240: base + 1 * np.exp(-t / 8),
    }
    close = np.full(n, base)
    df = _df_from_ma_close(ma, close)
    disp = compute_ma_dispersion_series(df).dropna()
    assert len(disp) >= 10
    diffs = disp.diff().dropna()
    assert (diffs <= 1e-12).all(), f"dispersion not monotone decreasing: {diffs[diffs > 0]}"


def test_all_ma_equal_dispersion_zero():
    n = 30
    v = 50.0
    ma = {p: np.full(n, v) for p in CORE_MA_PERIODS}
    close = np.full(n, 100.0)
    df = _df_from_ma_close(ma, close)
    disp = compute_ma_dispersion_series(df).dropna()
    assert (disp == 0.0).all()


def test_scale_invariance():
    """가격 ×1000 → dispersion 동일 (close 정규화)."""
    n = 25
    rng = np.linspace(90, 110, n)
    ma = {p: rng + p * 0.01 for p in CORE_MA_PERIODS}
    close = rng + 5
    df1 = _df_from_ma_close(ma, close)
    df2 = _df_from_ma_close({p: ma[p] * 1000 for p in CORE_MA_PERIODS}, close * 1000)
    d1 = compute_ma_dispersion_series(df1).dropna()
    d2 = compute_ma_dispersion_series(df2).dropna()
    np.testing.assert_allclose(d1.values, d2.values, rtol=1e-9, atol=1e-12)


def test_warmup_nan_preserved():
    n = 300
    ma = {p: np.full(n, np.nan) for p in CORE_MA_PERIODS}
    for p in CORE_MA_PERIODS:
        ma[p][p:] = 100.0 + p
    close = np.full(n, 100.0)
    df = _df_from_ma_close(ma, close)
    disp = compute_ma_dispersion_series(df)
    assert pd.isna(disp.iloc[100])
    assert not pd.isna(disp.iloc[-1])


def test_pivot_low_smoke_on_v_shape():
    """수렴 극점(pivot_low) V자 합성 스모크."""
    n = 30
    # V자 dispersion: 높음 → 낮음 → 높음
    v = np.concatenate([
        np.linspace(0.05, 0.01, 12),
        np.linspace(0.01, 0.04, 18),
    ])
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    s = pd.Series(v, index=idx, dtype="Float64")
    pl, ph = compute_series_pivots(
        s,
        lookback=MA_PATTERN_PARAMS["lookback"],
        min_gap=MA_PATTERN_PARAMS["min_gap"],
        rel_tolerance=MA_PATTERN_PARAMS["rel_tolerance"],
    )
    assert pl.notna().sum() >= 1, "pivot_low expected on V-shaped dispersion"
