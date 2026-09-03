"""Wave HTF Gate 테스트 (SPEC_WAVE_HTF_GATE §6).

- asof lookahead 차단 (§3.4)
- 게이트 조인 파리티 (이벤트 수 보존, gate 플래그 결측 0)
- G_BOTH ⊆ G_ALIGN ∩ G_WAVE 불변식
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_htf_gate import (
    G_WAVE_STATES,
    MIN_CELL_N,
    SYMBOLS,
    TRIGGER_QUALITY,
    TRIGGER_RULE,
    attach_htf_gates,
    bootstrap_delta,
    cell_counts,
    calibration_verdict,
    close_time_of,
    delta_expectancy,
    expectancy_20,
    gate_mask,
    gate_table,
    half_split_deltas,
    interval_delta,
    is_bullish_alignment,
    is_wave_bottom_state,
    judge,
    trigger_events,
)

HTF = "1d"
LTF = "4h"


def _states(symbol="BTCUSDT", n=40, htf=HTF, seed=0):
    """합성 HTF 상태 시계열 (닫힌 봉 기준)."""
    rng = np.random.default_rng(seed)
    opens = pd.date_range("2026-01-01", periods=n, freq="1D")
    states = rng.choice(
        list(G_WAVE_STATES) + ["NONE", "WAVE3_ACTIVE", "INVALIDATED"], size=n,
    )
    aligns = rng.choice(
        ["Bullish Alignment (정배열) 🚀", "Mixed / Consolidation (혼조세) ⚖️",
         "Bearish Alignment (역배열) 📉"], size=n,
    )
    df = pd.DataFrame({
        "symbol": symbol,
        "htf": htf,
        "htf_open_time": opens,
        "htf_close_time": close_time_of(opens, htf).to_numpy(),
        "htf_state": states,
        "htf_alignment": aligns,
    })
    df["g_align"] = df["htf_alignment"].map(is_bullish_alignment)
    df["g_wave"] = df["htf_state"].map(is_wave_bottom_state)
    df["g_both"] = df["g_align"] & df["g_wave"]
    return df


def _events(states, per_symbol=30, ltf=LTF, seed=1):
    """합성 LTF 이벤트 (HTF 구간 안에서 무작위 시각)."""
    rng = np.random.default_rng(seed)
    rows = []
    for sym in states["symbol"].unique():
        sub = states[states["symbol"] == sym]
        lo = sub["htf_open_time"].min() + pd.Timedelta(days=2)
        hi = sub["htf_open_time"].max()
        span = int((hi - lo) / pd.Timedelta(hours=4))
        for i in range(per_symbol):
            ts = lo + pd.Timedelta(hours=4 * int(rng.integers(0, max(span, 1))))
            rows.append({
                "event_id": f"E_{sym}_{i}",
                "timestamp": ts,
                "symbol": sym,
                "timeframe": ltf,
                "rule": rng.choice(["RULE_A", "RULE_B", "RULE_C"]),
                "quality_score": int(rng.integers(2, 5)),
                "return_20": float(rng.normal(0.5, 3.0)),
                "return_40": float(rng.normal(0.5, 4.0)),
                "survival_label": "SURVIVED_20",
            })
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


# ------------------------------------------------------------- §3.4 asof
def test_close_time_is_binance_convention():
    opens = pd.Series([pd.Timestamp("2026-01-01")])
    assert close_time_of(opens, "1d").iloc[0] == pd.Timestamp("2026-01-01 23:59:59.999")
    assert close_time_of(opens, "4h").iloc[0] == pd.Timestamp("2026-01-01 03:59:59.999")
    assert interval_delta("1d") == pd.Timedelta(days=1)


def test_asof_uses_only_bars_closed_before_event():
    """임의 이벤트 20개 표본: 사용된 마지막 HTF 봉의 close_time < t (§3.4)."""
    states = _states()
    events = _events(states, per_symbol=40)
    joined = attach_htf_gates(events, states, HTF)
    sample = joined.dropna(subset=["htf_close_time"]).head(20)
    assert len(sample) == 20
    for _, row in sample.iterrows():
        assert row["htf_close_time"] < row["timestamp"], row["event_id"]
        assert row["htf_open_time"] + interval_delta(HTF) <= row["timestamp"]


def test_asof_picks_latest_closed_bar_not_an_older_one():
    states = _states()
    events = _events(states, per_symbol=40)
    joined = attach_htf_gates(events, states, HTF)
    for _, row in joined.dropna(subset=["htf_close_time"]).iterrows():
        eligible = states[states["htf_close_time"] < row["timestamp"]]
        assert row["htf_close_time"] == eligible["htf_close_time"].max()


def test_event_exactly_on_htf_boundary_excludes_unclosed_bar():
    states = _states()
    ts = pd.Timestamp("2026-01-10 00:00:00")  # 1d 봉 경계
    events = pd.DataFrame([{
        "event_id": "E_boundary", "timestamp": ts, "symbol": "BTCUSDT",
        "timeframe": LTF, "rule": "RULE_C", "quality_score": 3,
        "return_20": 1.0, "return_40": 1.0, "survival_label": "SURVIVED_20",
    }])
    joined = attach_htf_gates(events, states, HTF)
    row = joined.iloc[0]
    # 2026-01-10 봉은 아직 마감 전 → 2026-01-09 봉이 선택되어야 한다
    assert row["htf_open_time"] == pd.Timestamp("2026-01-09")
    assert row["htf_close_time"] < ts


# --------------------------------------------------------- 조인 파리티
def test_join_preserves_event_count_and_has_no_missing_gate_flags():
    states = pd.concat([_states(s, seed=i) for i, s in enumerate(SYMBOLS)], ignore_index=True)
    events = _events(states, per_symbol=25)
    joined = attach_htf_gates(events, states, HTF)
    assert len(joined) == len(events)
    assert set(joined["event_id"]) == set(events["event_id"])
    for col in ("g_align", "g_wave", "g_both"):
        assert joined[col].isna().sum() == 0
        assert joined[col].dtype == bool


def test_join_without_states_marks_all_gates_false():
    events = _events(_states(), per_symbol=5)
    joined = attach_htf_gates(events, pd.DataFrame(), HTF)
    assert len(joined) == len(events)
    assert not joined["g_align"].any()
    assert not joined["g_both"].any()


def test_symbols_do_not_cross_join():
    states = pd.concat([_states("BTCUSDT", seed=1), _states("ETHUSDT", seed=2)], ignore_index=True)
    events = _events(states, per_symbol=20)
    joined = attach_htf_gates(events, states, HTF)
    for _, row in joined.dropna(subset=["htf_close_time"]).iterrows():
        own = states[(states["symbol"] == row["symbol"])
                     & (states["htf_close_time"] == row["htf_close_time"])]
        assert len(own) == 1
        assert own.iloc[0]["htf_state"] == row["htf_state"]


# ------------------------------------------------------------- 불변식
def test_g_both_is_subset_of_align_and_wave():
    states = pd.concat([_states(s, seed=i) for i, s in enumerate(SYMBOLS)], ignore_index=True)
    events = _events(states, per_symbol=30)
    joined = attach_htf_gates(events, states, HTF)
    both = gate_mask(joined, "G_BOTH")
    align = gate_mask(joined, "G_ALIGN")
    wave = gate_mask(joined, "G_WAVE")
    assert (both & ~(align & wave)).sum() == 0
    assert both.sum() == (align & wave).sum()


def test_gate_state_membership_matches_spec():
    assert is_wave_bottom_state("DOUBLE_BOTTOM_CANDIDATE")
    assert is_wave_bottom_state("WAVE3_COMPLETED")
    assert is_wave_bottom_state("TRIPLE_BOTTOM_CONFIRMED")
    assert not is_wave_bottom_state("TRIPLE_BOTTOM_REQUIRED")
    assert not is_wave_bottom_state("WAVE3_ACTIVE")
    assert not is_wave_bottom_state("NONE")
    assert is_bullish_alignment("Bullish Alignment (정배열) 🚀")
    assert not is_bullish_alignment("Bearish Alignment (역배열) 📉")
    assert not is_bullish_alignment("Mixed / Consolidation (혼조세) ⚖️")
    assert not is_bullish_alignment(None)


# --------------------------------------------------------- 트리거 정의
def test_trigger_is_rule_c_union_quality4():
    journal = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-01-02"), "symbol": "BTCUSDT", "timeframe": "4h",
         "rule": "RULE_C", "quality_score": 2, "return_20": 1.0},
        {"timestamp": pd.Timestamp("2026-01-03"), "symbol": "BTCUSDT", "timeframe": "4h",
         "rule": "RULE_A", "quality_score": 4, "return_20": 1.0},
        {"timestamp": pd.Timestamp("2026-01-04"), "symbol": "BTCUSDT", "timeframe": "4h",
         "rule": "RULE_A", "quality_score": 3, "return_20": 1.0},
        {"timestamp": pd.Timestamp("2026-01-05"), "symbol": "SOLUSDT", "timeframe": "4h",
         "rule": "RULE_C", "quality_score": 4, "return_20": 1.0},
        {"timestamp": pd.Timestamp("2026-01-06"), "symbol": "BTCUSDT", "timeframe": "1h",
         "rule": "RULE_C", "quality_score": 4, "return_20": 1.0},
    ])
    got = trigger_events(journal, "4h")
    assert len(got) == 2  # RULE_C(q2) + RULE_A(q4), SOL 제외(대상 심볼 아님), 1h 제외
    assert set(got["rule"]) == {TRIGGER_RULE, "RULE_A"}
    assert got["quality_score"].max() >= TRIGGER_QUALITY
    assert "survival_label" in got.columns


# ------------------------------------------------------------- 판정 로직
def test_expectancy_and_delta_are_finite_and_consistent():
    states = pd.concat([_states(s, seed=i) for i, s in enumerate(SYMBOLS)], ignore_index=True)
    events = _events(states, per_symbol=40)
    joined = attach_htf_gates(events, states, HTF)
    joined["pair"] = "PAIR_A"
    e_all = expectancy_20(joined)
    e_both = expectancy_20(joined[gate_mask(joined, "G_BOTH")])
    assert e_all is not None and e_both is not None
    assert delta_expectancy(joined) == round(
        e_both - expectancy_20(joined[gate_mask(joined, "G_ALIGN")]), 4,
    )


def test_bootstrap_ci_brackets_point_estimate():
    states = pd.concat([_states(s, seed=i) for i, s in enumerate(SYMBOLS)], ignore_index=True)
    events = _events(states, per_symbol=60)
    joined = attach_htf_gates(events, states, HTF)
    boot = bootstrap_delta(joined, n_boot=300)
    assert boot["n_boot"] > 0
    assert boot["ci_low"] <= boot["ci_high"]
    assert boot["n_both"] <= boot["n_align"]


def test_gate_table_has_four_rows_in_spec_order():
    states = _states()
    joined = attach_htf_gates(_events(states, per_symbol=20), states, HTF)
    rows = gate_table(joined, "T")
    assert [r["gate"] for r in rows] == ["NO_GATE", "G_ALIGN", "G_WAVE", "G_BOTH"]
    assert rows[0]["n"] >= rows[1]["n"] >= rows[3]["n"]


def test_judge_rejects_when_sample_too_small():
    states = _states()
    joined = attach_htf_gates(_events(states, per_symbol=12), states, HTF)
    joined["pair"] = "PAIR_A"
    result = judge(joined)
    assert result["verdict"] == "REJECT"
    c2 = next(c for c in result["criteria"] if c["id"] == 2)
    assert not c2["passed"]
    assert len(result["criteria"]) == 4


def test_half_split_covers_all_events():
    states = _states()
    joined = attach_htf_gates(_events(states, per_symbol=41), states, HTF)
    halves = half_split_deltas(joined)
    assert len(halves) == 2
    assert halves[0]["n"] + halves[1]["n"] == len(joined)
    assert halves[0]["ts_max"] <= halves[1]["ts_min"]


def test_cell_counts_report_pair_and_pair_symbol_levels():
    states = pd.concat([_states(s, seed=i) for i, s in enumerate(SYMBOLS)], ignore_index=True)
    joined = attach_htf_gates(_events(states, per_symbol=30), states, HTF)
    joined["pair"] = "PAIR_A"
    cells = cell_counts(joined)
    assert [c["level"] for c in cells].count("pair") == 1
    assert [c["level"] for c in cells].count("pair_symbol") == len(SYMBOLS)
    pair_row = next(c for c in cells if c["level"] == "pair")
    assert pair_row["n_both"] == sum(
        c["n_both"] for c in cells if c["level"] == "pair_symbol"
    )
    assert MIN_CELL_N == 30


def test_calibration_verdict_threshold():
    assert calibration_verdict([{"corr": 0.95}, {"corr": 0.91}])["keep_pair"]
    assert not calibration_verdict([{"corr": 0.95}, {"corr": 0.80}])["keep_pair"]
    assert calibration_verdict([])["mean_corr"] is None


# ------------------------------------- alignment 타임라인 lookahead 회귀
def test_alignment_timeline_matches_truncated_recompute():
    """전체 프레임 1회 계산 == 봉별 절단 재계산 (MA는 인과적 rolling)."""
    from display.asof import run_indicator_pipeline

    from analysis.wave_htf_gate import alignment_timeline
    from analysis.engine import get_ma_alignment

    rng = np.random.default_rng(7)
    n = 320
    idx = pd.date_range("2025-01-01", periods=n, freq="1D")
    close = 100 + np.cumsum(rng.normal(0, 1.5, n))
    bare = pd.DataFrame({
        "open": close, "high": close + 1.0, "low": close - 1.0,
        "close": close, "volume": rng.uniform(1, 10, n),
    }, index=idx)
    bare.index.name = "open_time"

    full = run_indicator_pipeline(bare)
    timeline = alignment_timeline(full)
    assert len(timeline) == n

    for i in (250, 280, 300, n - 1):
        truncated = run_indicator_pipeline(bare.iloc[: i + 1])
        assert timeline[i] == get_ma_alignment(truncated), i


def test_bnb_core_overlap_counts():
    from analysis.wave_htf_gate import bnb_core_overlap

    df = pd.DataFrame([
        # BNB, CORE(mf>=5,struct>=5) & G_BOTH
        {"symbol": "BNBUSDT", "money_flow_score": 5, "structure_score": 5,
         "g_align": True, "g_wave": True, "g_both": True, "return_20": 2.0},
        # BNB, CORE only
        {"symbol": "BNBUSDT", "money_flow_score": 5, "structure_score": 5,
         "g_align": True, "g_wave": False, "g_both": False, "return_20": 1.0},
        # BNB, G_BOTH only
        {"symbol": "BNBUSDT", "money_flow_score": 2, "structure_score": 2,
         "g_align": True, "g_wave": True, "g_both": True, "return_20": -1.0},
        # BNB, neither
        {"symbol": "BNBUSDT", "money_flow_score": 1, "structure_score": 1,
         "g_align": False, "g_wave": False, "g_both": False, "return_20": 0.5},
        # 다른 심볼은 제외되어야 한다
        {"symbol": "BTCUSDT", "money_flow_score": 5, "structure_score": 5,
         "g_align": True, "g_wave": True, "g_both": True, "return_20": 9.0},
    ])
    o = bnb_core_overlap(df)
    assert o["n_bnb"] == 4
    assert o["n_bnb_core"] == 2
    assert o["n_g_both"] == 2
    assert o["n_intersection"] == 1
    assert o["jaccard"] == round(1 / 3, 4)
    assert o["p_core_given_both"] == 0.5
    assert o["p_both_given_core"] == 0.5


def test_bnb_core_overlap_empty():
    from analysis.wave_htf_gate import bnb_core_overlap

    assert bnb_core_overlap(pd.DataFrame({"symbol": ["BTCUSDT"]}))["n_bnb"] == 0


def test_gate_availability_reports_window_counts(tmp_path, monkeypatch):
    import analysis.wave_htf_gate as G

    states = {("BTCUSDT", HTF): _states("BTCUSDT", n=40, seed=3)}
    monkeypatch.setattr(G, "load_htf_states",
                        lambda s, h, build=False: states.get((s, h), pd.DataFrame()))
    events = pd.DataFrame({"timestamp": [pd.Timestamp("2026-01-20"), pd.Timestamp("2026-01-25")]})
    rows = G.gate_availability(HTF, events, symbols=("BTCUSDT", "ETHUSDT"))
    btc = rows[0]
    assert btc["bars"] == 40
    assert btc["bars_align"] == int(states[("BTCUSDT", HTF)]["g_align"].sum())
    assert btc["win_bars"] <= btc["bars"]
    assert btc["win_both"] <= btc["win_align"]
    assert rows[1]["bars"] == 0  # 캐시 없는 심볼
