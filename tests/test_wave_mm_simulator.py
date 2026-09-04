"""SPEC_WAVE_MM_STOP_AUDIT §2 검증 — 판정 전 필수 통과 항목.

1. 무손절·무비용·항상체결 설정이 저널 expectancy_20 을 재현하는가
2. 손절 체결의 봉 내 순서 가정 (low 우선, 동시 충족 시 손절 우선)
3. 1포지션 건너뜀 — 보유 구간과 겹치는 이벤트가 정확히 제외되는가
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_mm_simulator import (
    COST_ROUNDTRIP_PCT,
    EXIT_STOP,
    EXIT_TIME,
    STOP_PCT,
    STOP_SLIPPAGE_PCT,
    TIME_EXIT_BARS,
    TRANCHE_PCT,
    counterfactual_stopped,
    exposure_rate,
    growth,
    load_bars,
    load_gate_events,
    max_drawdown,
    monthly_returns,
    simulate,
    trade_metrics,
)

REPRO_TOLERANCE_PCT = 0.01   # 저널 return_20 재현 허용 오차 (퍼센트포인트)


def _bars(closes, lows=None, highs=None, opens=None, freq="1h", start="2026-01-01"):
    n = len(closes)
    idx = pd.date_range(start, periods=n, freq=freq)
    df = pd.DataFrame({
        "open": opens if opens is not None else closes,
        "high": highs if highs is not None else [c * 1.001 for c in closes],
        "low": lows if lows is not None else [c * 0.999 for c in closes],
        "close": closes,
        "volume": [1.0] * n,
    }, index=idx)
    df.index.name = "open_time"
    return df


def _events(ts_list, symbol="BTCUSDT", ltf="1h", pair="PAIR_B"):
    return pd.DataFrame({
        "event_id": [f"E{i}" for i in range(len(ts_list))],
        "timestamp": pd.to_datetime(ts_list),
        "symbol": symbol, "ltf": ltf, "pair": pair,
    })


# ------------------------------------------------- 2. 손절 체결 순서 가정
def test_stop_fires_when_low_touches_and_fills_at_stop_with_slippage():
    closes = [100.0] * 25
    lows = list(closes)
    lows[3] = 96.0                      # 진입 후 3봉째에 -4% 저가
    bars = _bars(closes, lows=lows, opens=closes)
    ev = _events([bars.index[0]])
    tr = simulate(ev, {("BTCUSDT", "1h"): bars}, apply_cost=False)
    assert len(tr) == 1
    row = tr.iloc[0]
    assert row["exit_reason"] == EXIT_STOP
    entry = row["entry_price"]
    expected = entry * (1 - STOP_PCT / 100) * (1 - STOP_SLIPPAGE_PCT / 100)
    assert row["exit_price"] == pytest.approx(expected)
    assert row["gross_ret"] == pytest.approx((expected - entry) / entry)


def test_stop_not_fired_when_low_stays_above_threshold():
    closes = [100.0] * 25
    lows = [97.5] * 25                  # -2.5% 까지만 — -3% 미도달
    bars = _bars(closes, lows=lows, opens=closes)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars}, apply_cost=False)
    assert tr.iloc[0]["exit_reason"] == EXIT_TIME


def test_stop_boundary_exact_touch_counts_as_hit():
    """low == 기준가×0.97 은 체결로 본다 (<= 비교)."""
    closes = [100.0] * 25
    lows = list(closes)
    lows[5] = 100.0 * (1 - STOP_PCT / 100)
    bars = _bars(closes, lows=lows, opens=closes)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars}, apply_cost=False)
    assert tr.iloc[0]["exit_reason"] == EXIT_STOP


def test_stop_takes_priority_when_same_bar_is_also_the_time_exit():
    """동시 충족 봉은 손절 우선 (보수적)."""
    n = TIME_EXIT_BARS + 2
    closes = [100.0] * n
    lows = list(closes)
    lows[TIME_EXIT_BARS] = 90.0         # 시간 청산 봉에서 저가가 손절선을 관통
    bars = _bars(closes, lows=lows, opens=closes)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars}, apply_cost=False)
    row = tr.iloc[0]
    assert row["exit_reason"] == EXIT_STOP
    assert row["exit_price"] < 100.0


def test_stop_uses_the_first_touching_bar():
    closes = [100.0] * 25
    lows = list(closes)
    lows[4], lows[9] = 96.0, 90.0
    bars = _bars(closes, lows=lows, opens=closes)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars}, apply_cost=False)
    assert tr.iloc[0]["exit_ts"] == bars.index[4]


def test_nostop_ignores_lows_entirely():
    closes = [100.0] * 25
    lows = [50.0] * 25
    bars = _bars(closes, lows=lows, opens=closes)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars},
                  use_stop=False, apply_cost=False)
    assert tr.iloc[0]["exit_reason"] == EXIT_TIME


# ------------------------------------------------ 체결 모형 · 시간 청산 지평
def test_entry_is_next_bar_open_and_time_exit_matches_horizon():
    closes = [100.0 + i for i in range(30)]
    opens = [c - 0.5 for c in closes]
    bars = _bars(closes, lows=[c * 0.999 for c in closes], opens=opens)
    tr = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars},
                  use_stop=False, apply_cost=False)
    row = tr.iloc[0]
    assert row["entry_ts"] == bars.index[1]
    assert row["entry_price"] == pytest.approx(opens[1])
    # 시간 청산은 신호봉 i 기준 i+20 종가 (expectancy_20 과 같은 지평)
    assert row["exit_ts"] == bars.index[TIME_EXIT_BARS]
    assert row["exit_price"] == pytest.approx(closes[TIME_EXIT_BARS])


def test_cost_is_subtracted_once_round_trip():
    closes = [100.0] * 30
    bars = _bars(closes, opens=closes)
    with_cost = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars},
                         use_stop=False, apply_cost=True).iloc[0]
    without = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars},
                       use_stop=False, apply_cost=False).iloc[0]
    assert without["net_ret"] - with_cost["net_ret"] == pytest.approx(COST_ROUNDTRIP_PCT / 100)


def test_log_growth_uses_the_tranche_weight():
    closes = [100.0] * 21 + [110.0] * 10
    bars = _bars(closes, opens=closes)
    row = simulate(_events([bars.index[0]]), {("BTCUSDT", "1h"): bars},
                   use_stop=False, apply_cost=False).iloc[0]
    assert row["log_growth"] == pytest.approx(
        np.log1p(TRANCHE_PCT / 100 * row["net_ret"]))


# ------------------------------------------------- 3. 1포지션 건너뜀 로직
def test_one_position_skips_events_inside_the_holding_window():
    closes = [100.0] * 60
    bars = _bars(closes, opens=closes)
    # 0봉 신호로 진입(1봉) → 20봉 종가 청산. 그 사이 신호 5·10·19 는 전부 건너뜀.
    ev = _events([bars.index[i] for i in (0, 5, 10, 19, 25)])
    tr = simulate(ev, {("BTCUSDT", "1h"): bars}, use_stop=False, apply_cost=False)
    assert list(tr["event_id"]) == ["E0", "E4"]
    assert tr.iloc[0]["exit_ts"] == bars.index[TIME_EXIT_BARS]


def test_event_exactly_at_exit_bar_is_taken():
    """보유 종료 시각과 같은 시각의 신호는 건너뛰지 않는다 (< 비교)."""
    closes = [100.0] * 60
    bars = _bars(closes, opens=closes)
    ev = _events([bars.index[0], bars.index[TIME_EXIT_BARS]])
    tr = simulate(ev, {("BTCUSDT", "1h"): bars}, use_stop=False, apply_cost=False)
    assert list(tr["event_id"]) == ["E0", "E1"]


def test_one_position_disabled_takes_every_event():
    closes = [100.0] * 60
    bars = _bars(closes, opens=closes)
    ev = _events([bars.index[i] for i in (0, 5, 10)])
    tr = simulate(ev, {("BTCUSDT", "1h"): bars}, use_stop=False,
                  apply_cost=False, one_position=False)
    assert len(tr) == 3


def test_one_position_holds_across_symbols():
    """동시 1포지션은 심볼을 가리지 않는다."""
    closes = [100.0] * 60
    bars = _bars(closes, opens=closes)
    ev = pd.concat([
        _events([bars.index[0]], symbol="BTCUSDT"),
        _events([bars.index[3]], symbol="ETHUSDT"),
    ], ignore_index=True)
    ev["event_id"] = ["A", "B"]
    tr = simulate(ev, {("BTCUSDT", "1h"): bars, ("ETHUSDT", "1h"): bars},
                  use_stop=False, apply_cost=False)
    assert list(tr["event_id"]) == ["A"]


# ------------------------------------------------------------ 지표 계산
def test_metrics_on_a_known_series():
    closes = [100.0] * 60
    bars = _bars(closes, opens=closes)
    tr = simulate(_events([bars.index[0], bars.index[TIME_EXIT_BARS]]),
                  {("BTCUSDT", "1h"): bars}, use_stop=False, apply_cost=False)
    m = trade_metrics(tr)
    assert m["trades"] == 2
    assert m["stop_rate"] == 0.0
    assert growth(tr) == pytest.approx(0.0, abs=1e-9)
    assert max_drawdown(tr) == pytest.approx(0.0, abs=1e-9)
    assert 0.0 <= exposure_rate(tr) <= 1.0
    assert len(monthly_returns(tr)) >= 1


def test_counterfactual_pairs_only_common_events():
    closes = [100.0] * 30
    lows = list(closes)
    lows[2] = 90.0
    bars = _bars(closes, lows=lows, opens=closes)
    ev = _events([bars.index[0]])
    base = simulate(ev, {("BTCUSDT", "1h"): bars}, apply_cost=False)
    nostop = simulate(ev, {("BTCUSDT", "1h"): bars}, use_stop=False, apply_cost=False)
    cf = counterfactual_stopped(base, nostop)
    assert cf["paired"] == 1
    assert cf["stopped"] == 1
    # 손절 없었으면 20봉 뒤 종가는 진입가와 같아 0 → 양수 아님
    assert cf["would_be_positive"] == 0


# ------------------------- 1. 저널 expectancy_20 재현 (실데이터, 캐시 필요)
def test_reproduces_journal_return_20_without_stop_or_cost():
    """검증 모드(event_close·무손절·무비용·항상체결)가 저널 return_20 을 재현한다."""
    events = load_gate_events()
    if events.empty:
        pytest.skip("게이트 이벤트 캐시 없음")
    keys = {(s, l) for s, l in zip(events["symbol"], events["ltf"])}
    bars = {k: load_bars(*k) for k in keys}
    if any(b.empty for b in bars.values()):
        pytest.skip("OHLCV 캐시 없음 — MM-R0 sweep 선행 필요")

    tr = simulate(events, bars, use_stop=False, apply_cost=False,
                  one_position=False, entry_mode="event_close")
    assert len(tr) > 1000

    merged = tr.merge(events[["event_id", "return_20"]], on="event_id", how="inner")
    merged = merged[merged["return_20"].notna()]
    assert len(merged) > 1000
    diff = (merged["gross_ret"] * 100 - merged["return_20"]).abs()
    within = float((diff <= REPRO_TOLERANCE_PCT).mean())
    assert within >= 0.99, (
        f"저널 재현 실패: 허용오차 {REPRO_TOLERANCE_PCT}%p 이내 비율 {within:.4f}, "
        f"최대 편차 {diff.max():.6f}%p"
    )


def test_spec_constants_are_frozen():
    assert (STOP_PCT, STOP_SLIPPAGE_PCT, COST_ROUNDTRIP_PCT) == (3.0, 0.05, 0.2)
    assert (TIME_EXIT_BARS, TRANCHE_PCT) == (20, 5.0)
