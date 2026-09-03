"""Wave HTF Gate V2 테스트 (SPEC_WAVE_HTF_GATE_V2 §6).

- F2-b 게이트 단위 (경계: MA(t) == MA(t-1) → 게이트 닫힘)
- 기존 lookahead·파리티·불변식 테스트를 v2 게이트에 재적용 (§2.5)
- R0 기저율·n̂ 산식
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_htf_gate import (
    attach_htf_gates,
    close_time_of,
    gate_mask,
    interval_delta,
    is_wave_bottom_state,
)
from analysis.wave_htf_gate_v2 import (
    F2B_MA_PERIODS,
    F2B_SLOPE_BARS,
    GATE_VERSION_V1,
    GATE_VERSION_V2,
    PAIRS_V2,
    R0_MIN_EXPECTED_N,
    SYMBOLS_V2,
    WINDOW_MAIN,
    apply_gate_version,
    baseline_rates,
    event_rate,
    expected_sample,
    f2b_rising_flags,
    is_f2b_rising_at,
    r0_verdict,
    yearly_open_rates,
)

HTF = "4h"


def _ma_frame(series_by_period: dict, n=6):
    idx = pd.date_range("2026-01-01", periods=n, freq="4h")
    data = {f"MA{p}": vals for p, vals in series_by_period.items()}
    return pd.DataFrame(data, index=idx)


# ------------------------------------------------------------- F2-b 단위
def test_f2b_open_when_all_three_rising():
    df = _ma_frame({60: [1, 2, 3], 120: [1, 1.5, 2], 240: [1, 1.1, 1.2]}, n=3)
    flags = f2b_rising_flags(df)
    assert list(flags) == [False, True, True]  # 첫 봉은 직전 봉이 없어 닫힘
    assert is_f2b_rising_at(df, 2)


def test_f2b_closed_when_ma240_flat_boundary():
    """경계 조건: MA240(t) == MA240(t-1) 이면 '상승'이 아니므로 게이트 닫힘."""
    df = _ma_frame({60: [1, 2, 3], 120: [1, 1.5, 2], 240: [1.0, 1.0, 1.0]}, n=3)
    assert list(f2b_rising_flags(df)) == [False, False, False]
    assert not is_f2b_rising_at(df, 2)


def test_f2b_closed_when_any_one_falls():
    for falling in F2B_MA_PERIODS:
        vals = {p: [1.0, 2.0, 3.0] for p in F2B_MA_PERIODS}
        vals[falling] = [3.0, 2.0, 1.0]
        df = _ma_frame(vals, n=3)
        assert not is_f2b_rising_at(df, 2), falling
        assert not bool(f2b_rising_flags(df).iloc[2]), falling


def test_f2b_closed_on_nan_warmup():
    df = _ma_frame({60: [np.nan, 2, 3], 120: [1, 1.5, 2], 240: [1, 1.1, 1.2]}, n=3)
    assert not bool(f2b_rising_flags(df).iloc[1])
    assert not is_f2b_rising_at(df, 1)


def test_f2b_missing_column_closes_gate():
    df = pd.DataFrame({"MA60": [1.0, 2.0]}, index=pd.date_range("2026-01-01", periods=2))
    assert not f2b_rising_flags(df).any()
    assert not is_f2b_rising_at(df, 1)


def test_f2b_slope_window_is_one_bar():
    assert F2B_SLOPE_BARS == 1  # §2.2 — 자유 파라미터 금지


def test_f2b_series_and_scalar_agree():
    rng = np.random.default_rng(3)
    n = 60
    vals = {p: np.cumsum(rng.normal(0, 1, n)) + 100 for p in F2B_MA_PERIODS}
    df = _ma_frame({p: list(v) for p, v in vals.items()}, n=n)
    flags = f2b_rising_flags(df)
    for i in range(n):
        assert bool(flags.iloc[i]) == is_f2b_rising_at(df, i), i


def test_f2b_is_lookahead_free_under_truncation():
    """MA 는 인과적 rolling 이라 전체 계산 == 절단 재계산 (v2 게이트 lookahead 회귀)."""
    from display.asof import run_indicator_pipeline

    rng = np.random.default_rng(11)
    n = 320
    idx = pd.date_range("2025-01-01", periods=n, freq="1D")
    close = 100 + np.cumsum(rng.normal(0, 1.5, n))
    bare = pd.DataFrame({
        "open": close, "high": close + 1.0, "low": close - 1.0,
        "close": close, "volume": rng.uniform(1, 10, n),
    }, index=idx)
    bare.index.name = "open_time"

    full_flags = f2b_rising_flags(run_indicator_pipeline(bare))
    for i in (250, 280, 300, n - 1):
        trunc = run_indicator_pipeline(bare.iloc[: i + 1])
        assert bool(full_flags.iloc[i]) == bool(f2b_rising_flags(trunc).iloc[i]), i


# ------------------------------------------------- v2 상태 → 게이트 플래그
def _v2_states(symbol="BTCUSDT", n=40, htf=HTF, seed=0):
    rng = np.random.default_rng(seed)
    opens = pd.date_range("2026-01-01", periods=n, freq="4h")
    states = rng.choice(
        ["DOUBLE_BOTTOM_CANDIDATE", "WAVE3_COMPLETED", "TRIPLE_BOTTOM_CONFIRMED",
         "NONE", "WAVE3_ACTIVE", "TRIPLE_BOTTOM_REQUIRED"], size=n)
    df = pd.DataFrame({
        "symbol": symbol, "htf": htf, "htf_open_time": opens,
        "htf_close_time": close_time_of(opens, htf).to_numpy(),
        "htf_state": states,
        "htf_alignment": rng.choice(
            ["Bullish Alignment (정배열) 🚀", "Mixed / Consolidation (혼조세) ⚖️"], size=n),
        "align_v1": rng.random(n) < 0.15,
        "align_v2": rng.random(n) < 0.40,
    })
    df["g_wave"] = df["htf_state"].map(is_wave_bottom_state)
    return df


def test_apply_gate_version_selects_the_right_align_column():
    st = _v2_states()
    v2 = apply_gate_version(st, GATE_VERSION_V2)
    v1 = apply_gate_version(st, GATE_VERSION_V1)
    assert list(v2["g_align"]) == list(st["align_v2"])
    assert list(v1["g_align"]) == list(st["align_v1"])
    assert v2["gate_version"].unique().tolist() == [GATE_VERSION_V2]


def test_v2_g_both_subset_invariant():
    st = apply_gate_version(_v2_states(n=200, seed=5), GATE_VERSION_V2)
    assert (st["g_both"] & ~(st["g_align"] & st["g_wave"])).sum() == 0
    assert st["g_both"].sum() == (st["g_align"] & st["g_wave"]).sum()


def _events(states, per_symbol=30, ltf="1h", seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for sym in states["symbol"].unique():
        sub = states[states["symbol"] == sym]
        lo = sub["htf_open_time"].min() + pd.Timedelta(hours=8)
        hi = sub["htf_open_time"].max()
        span = max(int((hi - lo) / pd.Timedelta(hours=1)), 1)
        for i in range(per_symbol):
            rows.append({
                "event_id": f"E_{sym}_{i}",
                "timestamp": lo + pd.Timedelta(hours=int(rng.integers(0, span))),
                "symbol": sym, "timeframe": ltf,
                "rule": rng.choice(["RULE_A", "RULE_C"]),
                "quality_score": int(rng.integers(2, 5)),
                "return_20": float(rng.normal(0.5, 3.0)),
                "return_40": float(rng.normal(0.5, 4.0)),
                "survival_label": "SURVIVED_20",
            })
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def test_v2_asof_join_blocks_lookahead_and_preserves_events():
    """§2.5 — v1 의 asof·파리티·불변식 테스트를 v2 게이트에 그대로 재적용."""
    states = pd.concat(
        [apply_gate_version(_v2_states(s, n=120, seed=i), GATE_VERSION_V2)
         for i, s in enumerate(SYMBOLS_V2)],
        ignore_index=True,
    )
    events = _events(states, per_symbol=40)
    joined = attach_htf_gates(events, states, HTF)

    assert len(joined) == len(events)
    assert set(joined["event_id"]) == set(events["event_id"])
    for col in ("g_align", "g_wave", "g_both"):
        assert joined[col].isna().sum() == 0
        assert joined[col].dtype == bool

    sample = joined.dropna(subset=["htf_close_time"]).head(20)
    assert len(sample) == 20
    for _, row in sample.iterrows():
        assert row["htf_close_time"] < row["timestamp"], row["event_id"]
        assert row["htf_open_time"] + interval_delta(HTF) <= row["timestamp"]

    both = gate_mask(joined, "G_BOTH")
    assert (both & ~(gate_mask(joined, "G_ALIGN") & gate_mask(joined, "G_WAVE"))).sum() == 0


def test_v2_join_picks_latest_closed_bar_per_symbol():
    states = pd.concat(
        [apply_gate_version(_v2_states(s, n=90, seed=i), GATE_VERSION_V2)
         for i, s in enumerate(("BTCUSDT", "ETHUSDT"))],
        ignore_index=True,
    )
    joined = attach_htf_gates(_events(states, per_symbol=25), states, HTF)
    for _, row in joined.dropna(subset=["htf_close_time"]).iterrows():
        own = states[states["symbol"] == row["symbol"]]
        eligible = own[own["htf_close_time"] < row["timestamp"]]
        assert row["htf_close_time"] == eligible["htf_close_time"].max()
        assert row["htf_state"] == eligible.iloc[-1]["htf_state"]


# --------------------------------------------------------------- R0 산식
def test_event_rate_uses_r1_measurements():
    r1h = event_rate("1h", "BNBUSDT")
    assert r1h is not None and 0 < r1h < 1
    # 6h 는 4h 실측의 봉길이 비례 환산 (1.5배)
    assert event_rate("6h", "BNBUSDT") == event_rate("4h", "BNBUSDT") * 1.5
    assert event_rate("1h", "SOLUSDT") is None


def test_expected_sample_formula():
    rates = [
        {"pair": "PAIR_B", "symbol": "BTCUSDT", "bars": 100, "p_both": 0.10},
        {"pair": "PAIR_B", "symbol": "ETHUSDT", "bars": 100, "p_both": 0.00},
    ]
    got = expected_sample(rates, "2021-01-01", "2021-01-02",
                          pairs={"PAIR_B": ("4h", "1h")})
    assert len(got) == 1
    row = got[0]
    assert row["ltf_bars"] == 24
    expected = event_rate("1h", "BTCUSDT") * 24 * 0.10
    assert abs(row["n_hat"] - round(expected, 2)) < 0.01
    assert len(row["detail"]) == 2


def test_r0_verdict_go_and_short():
    exp = [{"pair": "PAIR_B", "n_hat": 40.0}, {"pair": "PAIR_C", "n_hat": 5.0}]
    assert r0_verdict(exp, ["PAIR_B"], "main")["verdict"] == "GO"
    assert r0_verdict(exp, ["PAIR_C"], "main")["verdict"] == "SHORT"
    v = r0_verdict(exp, ["PAIR_B", "PAIR_C"], "main")
    assert v["n_hat_total"] == 45.0
    assert v["threshold"] == R0_MIN_EXPECTED_N == 30


def test_baseline_and_yearly_rates_from_cache(monkeypatch):
    import analysis.wave_htf_gate_v2 as V2

    st = _v2_states("BTCUSDT", n=300, seed=9)
    monkeypatch.setattr(
        V2, "load_htf_states_v2",
        lambda s, h: st if (s, h) == ("BTCUSDT", "4h") else pd.DataFrame(),
    )
    rows = baseline_rates(pairs={"PAIR_B": ("4h", "1h")}, symbols=("BTCUSDT", "ETHUSDT"))
    btc = rows[0]
    assert btc["bars"] == 300
    assert abs(btc["p_both"] - btc["n_both"] / 300) < 1e-6  # p_* 는 6자리 반올림
    assert btc["p_both"] <= min(btc["p_align"], btc["p_wave"])
    assert rows[1]["bars"] == 0

    years = yearly_open_rates(pairs={"PAIR_B": ("4h", "1h")}, symbols=("BTCUSDT",))
    assert sum(y["bars"] for y in years) == 300


def test_spec_constants_are_frozen():
    assert PAIRS_V2 == {"PAIR_B": ("4h", "1h"), "PAIR_C": ("1d", "6h")}
    assert WINDOW_MAIN == ("2021-01-01", "2026-09-01")
    assert SYMBOLS_V2 == ("BTCUSDT", "ETHUSDT", "BNBUSDT")


# ------------------------------------------- 윈도 절단 러너 패리티 (느림)
def test_windowed_runner_matches_full_recompute():
    """run_state_timeline(window=W) == wave_tracker.run_timeline (상태열 완전 일치).

    W 는 판정 파라미터가 아니라 구현 파라미터다. O(N²) 재계산을 O(N·W) 로 줄이는
    대신, 무절단 계산과 상태열이 정확히 같아야만 쓸 수 있다.
    네트워크 + 수 분이 걸리므로 RUN_SLOW_PARITY=1 일 때만 실행한다.
    측정 기록(BTCUSDT 4h, 1000봉/warmup 700, 300봉 비교):
        W=None diffs=0 / W=600 diffs=0 / W=400 diffs=0
    """
    if os.environ.get("RUN_SLOW_PARITY") != "1":
        import pytest
        pytest.skip("set RUN_SLOW_PARITY=1 to run the full-recompute parity check")

    from analysis.wave_htf_gate_v2 import STATE_WINDOW_BARS, run_state_timeline
    from analysis.wave_tracker import run_timeline
    from display.asof import build_ohlcv_cache, fetch_ohlcv_bare

    symbol, interval, nbars, warmup = "BTCUSDT", "4h", 700, 500
    bare = fetch_ohlcv_bare(symbol, interval, 1000, paginated=False)
    if bare is None or len(bare) < nbars:
        import pytest
        pytest.skip("network/data unavailable")
    bare = bare.tail(nbars)
    cache = build_ohlcv_cache(symbol, interval, bare, extra_limits={interval: nbars})

    full = run_timeline(symbol, interval, bare, cache, warmup=warmup)
    win = run_state_timeline(
        symbol, interval, bare, cache, warmup=warmup, window=STATE_WINDOW_BARS,
    )
    assert len(full) == len(win)
    assert list(full["state"]) == list(win["state"])
