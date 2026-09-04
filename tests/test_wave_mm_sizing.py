"""SPEC_WAVE_MM_SIZING 테스트 — 사이징 공식·룩어헤드·판정 산식."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_mm_simulator import TRANCHE_PCT, simulate
from analysis.wave_mm_sizing import (
    ATR_PERIOD,
    BOOTSTRAP_SEED,
    DISPERSION_MIN,
    MIN_ACTIVE_MONTHS,
    MIN_TRADES,
    REDUCED_SHARE_MIN,
    REF_WINDOW_DAYS,
    SIZE_CAP_PCT,
    _ref_median,
    bootstrap_delta_sharpe,
    delta_sharpe,
    dispersion_gate,
    event_atrp,
    half_split,
    monthly_log_series,
    paired_months,
    sharpe,
    skew_diagnostic,
    volsize_map,
)


def _bars(n=60, price=100.0, freq="6h", start="2026-01-01"):
    idx = pd.date_range(start, periods=n, freq=freq)
    df = pd.DataFrame({
        "open": price, "high": price * 1.01, "low": price * 0.99,
        "close": price, "volume": 1.0,
    }, index=idx)
    df.index.name = "open_time"
    return df


# ------------------------------------------------------- 파라미터 동결
def test_sizing_constants_are_frozen():
    assert (ATR_PERIOD, REF_WINDOW_DAYS, SIZE_CAP_PCT) == (14, 180, TRANCHE_PCT)
    assert (DISPERSION_MIN, REDUCED_SHARE_MIN) == (1.5, 0.20)
    assert (MIN_TRADES, MIN_ACTIVE_MONTHS) == (100, 40)


# ------------------------------------------------------- ref 룩어헤드 금지
def test_ref_median_excludes_the_signal_bar_and_the_future():
    idx = pd.date_range("2026-01-01", periods=10, freq="1D")
    s = pd.Series([1, 2, 3, 4, 5, 100, 100, 100, 100, 100], index=idx, dtype=float)
    ts = idx[5]
    # 이전 5개(1..5)의 중앙값 3 — 신호봉(100)과 이후 값은 배제
    assert _ref_median(s, ts) == 3.0


def test_ref_median_uses_only_the_reference_window():
    idx = pd.date_range("2026-01-01", periods=400, freq="1D")
    s = pd.Series([1.0] * 200 + [9.0] * 200, index=idx)
    ts = idx[399]
    # 이전 180일은 전부 9.0 구간
    assert _ref_median(s, ts) == 9.0


def test_ref_median_falls_back_to_all_history_when_short():
    idx = pd.date_range("2026-01-01", periods=5, freq="1D")
    s = pd.Series([2.0, 4.0, 6.0, 8.0, 99.0], index=idx)
    assert _ref_median(s, idx[4]) == 5.0     # 2,4,6,8 의 중앙값


def test_ref_median_returns_none_at_series_start():
    idx = pd.date_range("2026-01-01", periods=3, freq="1D")
    s = pd.Series([1.0, 2.0, 3.0], index=idx)
    assert _ref_median(s, idx[0]) is None


# ------------------------------------------------------- VOLSIZE 공식
def test_volsize_caps_at_five_percent_and_only_reduces(monkeypatch):
    import analysis.wave_mm_sizing as SZ

    bars = _bars(n=40)
    # atrp 시계열: 앞 20봉 0.01(참조), 이후 변동
    ser = pd.Series([0.01] * 20 + [0.02] * 10 + [0.005] * 10, index=bars.index)
    monkeypatch.setattr(SZ, "atrp_series", lambda s, l, build=False: ser)

    ev = pd.DataFrame({
        "event_id": ["HI", "LO"],
        "symbol": "BTCUSDT", "ltf": "6h",
        "timestamp": [bars.index[25], bars.index[35]],
    })
    out = SZ.event_atrp(ev, {("BTCUSDT", "6h"): bars})
    by = out.set_index("event_id")
    # 고변동(atrp 2배) → 사이즈 절반
    assert by.loc["HI", "size_pct"] == pytest.approx(SIZE_CAP_PCT * 0.5, rel=1e-6)
    # 저변동 → 상한에 걸려 5% 그대로 (늘어나지 않는다)
    assert by.loc["LO", "size_pct"] == pytest.approx(SIZE_CAP_PCT)
    assert (out["size_pct"] <= SIZE_CAP_PCT + 1e-12).all()


def test_volsize_uses_entry_price_not_signal_close(monkeypatch):
    import analysis.wave_mm_sizing as SZ

    bars = _bars(n=30)
    bars.loc[bars.index[21], "open"] = 200.0      # 진입가만 2배
    ser = pd.Series([0.01] * 30, index=bars.index)
    monkeypatch.setattr(SZ, "atrp_series", lambda s, l, build=False: ser)
    ev = pd.DataFrame({"event_id": ["E"], "symbol": "BTCUSDT", "ltf": "6h",
                       "timestamp": [bars.index[20]]})
    out = SZ.event_atrp(ev, {("BTCUSDT", "6h"): bars})
    # ATR14 = atrp*close = 1.0, 진입가 200 → atrp_i = 0.005 (참조 0.01의 절반)
    assert out.iloc[0]["atrp"] == pytest.approx(0.005)
    assert out.iloc[0]["size_pct"] == pytest.approx(SIZE_CAP_PCT)  # 상한


def test_volsize_map_feeds_the_simulator_size():
    bars = _bars(n=40)
    ev = pd.DataFrame({"event_id": ["E0"], "symbol": "BTCUSDT", "ltf": "6h",
                       "pair": "PAIR_C", "timestamp": [bars.index[0]]})
    tr = simulate(ev, {("BTCUSDT", "6h"): bars}, use_stop=False, apply_cost=False,
                  tranche_pct={"E0": 2.5})
    assert tr.iloc[0]["size_pct"] == pytest.approx(2.5)


def test_missing_event_in_size_map_falls_back_to_default():
    bars = _bars(n=40)
    ev = pd.DataFrame({"event_id": ["E0"], "symbol": "BTCUSDT", "ltf": "6h",
                       "pair": "PAIR_C", "timestamp": [bars.index[0]]})
    tr = simulate(ev, {("BTCUSDT", "6h"): bars}, use_stop=False, apply_cost=False,
                  tranche_pct={"OTHER": 1.0})
    assert tr.iloc[0]["size_pct"] == pytest.approx(TRANCHE_PCT)


# ------------------------------------------------------- §3 관문
def test_dispersion_gate_conditions():
    df = pd.DataFrame({
        "event_id": [f"E{i}" for i in range(100)],
        "atrp": np.linspace(0.01, 0.04, 100),
        "size_pct": [SIZE_CAP_PCT] * 70 + [2.0] * 30,
        "reduced": [False] * 70 + [True] * 30,
    })
    g = dispersion_gate(df)
    assert g["dispersion"] > DISPERSION_MIN
    assert g["reduced_share"] == pytest.approx(0.30)
    assert g["go"] is True


def test_dispersion_gate_blocks_when_flat():
    df = pd.DataFrame({
        "event_id": [f"E{i}" for i in range(50)],
        "atrp": [0.02] * 50,
        "size_pct": [SIZE_CAP_PCT] * 50,
        "reduced": [False] * 50,
    })
    g = dispersion_gate(df)
    assert g["dispersion"] == pytest.approx(1.0)
    assert g["go"] is False


# ------------------------------------------------------- §4 산식
def _trades(months, growths, ltf="6h"):
    rows = []
    for i, (m, g) in enumerate(zip(months, growths)):
        rows.append({"event_id": f"E{i}", "ltf": ltf, "symbol": "BTCUSDT",
                     "exit_ts": pd.Timestamp(m) + pd.Timedelta(days=1),
                     "log_growth": g, "net_ret": g * 20})
    return pd.DataFrame(rows)


def test_sharpe_is_scale_invariant():
    months = [f"2021-{m:02d}-01" for m in range(1, 13)]
    g = np.random.default_rng(0).normal(0.001, 0.01, 12)
    a = _trades(months, g)
    b = _trades(months, g * 3.0)
    assert sharpe(monthly_log_series(a)) == pytest.approx(sharpe(monthly_log_series(b)))


def test_monthly_series_zero_fills_the_paired_calendar():
    a = _trades(["2021-01-01", "2021-03-01"], [0.01, 0.02])
    b = _trades(["2021-02-01"], [0.03])
    months = paired_months(a, b)
    assert months == ["2021-01", "2021-02", "2021-03"]
    sa = monthly_log_series(a, months)
    assert list(sa.index) == months
    assert sa["2021-02"] == 0.0


def test_delta_sharpe_sign_matches_the_better_series():
    months = [f"2021-{m:02d}-01" for m in range(1, 13)]
    steady = [0.01] * 12
    noisy = [0.05, -0.04] * 6
    better = _trades(months, steady)
    worse = _trades(months, noisy)
    assert delta_sharpe(better, worse) > 0
    assert delta_sharpe(worse, better) < 0


def test_bootstrap_is_reproducible_and_brackets_the_point():
    months = [f"2021-{m:02d}-01" for m in range(1, 13)] + \
             [f"2022-{m:02d}-01" for m in range(1, 13)]
    rng = np.random.default_rng(3)
    a = _trades(months, rng.normal(0.004, 0.01, 24))
    b = _trades(months, rng.normal(0.001, 0.01, 24))
    r1 = bootstrap_delta_sharpe(a, b, n_boot=300, seed=BOOTSTRAP_SEED)
    r2 = bootstrap_delta_sharpe(a, b, n_boot=300, seed=BOOTSTRAP_SEED)
    assert (r1["ci_low"], r1["ci_high"]) == (r2["ci_low"], r2["ci_high"])
    assert r1["ci_low"] <= r1["ci_high"]
    assert r1["n_months"] == 24


def test_half_split_partitions_the_month_calendar():
    months = [f"2021-{m:02d}-01" for m in range(1, 13)]
    a = _trades(months, [0.01] * 12)
    b = _trades(months, [0.005] * 12)
    hs = half_split(a, b)
    assert [h["split"] for h in hs] == ["first_half", "second_half"]
    assert hs[0]["months"] + hs[1]["months"] == 12


def test_skew_diagnostic_flags_high_vol_winners():
    base = pd.DataFrame({
        "event_id": [f"E{i}" for i in range(100)],
        "net_ret": np.linspace(-0.05, 0.20, 100),
    })
    # 수익이 클수록 atrp 도 크게 — 큰 승리가 고변동에서 나오는 구성
    atrp = pd.DataFrame({
        "event_id": base["event_id"],
        "atrp": np.linspace(0.005, 0.05, 100),
        "size_pct": np.linspace(SIZE_CAP_PCT, 1.0, 100),
    })
    d = skew_diagnostic(base, atrp)
    assert d["top_atrp_quantile_mean"] > 0.9
    assert d["top_size_reduction_pct"] > d["all_size_reduction_pct"]
