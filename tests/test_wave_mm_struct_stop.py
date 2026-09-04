"""SPEC_WAVE_MM_STRUCT_STOP 테스트 — 구조 손절 정의·asof·관문."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_mm_simulator import EXIT_STOP, EXIT_TIME, STOP_PCT, simulate
from analysis.wave_mm_struct_stop import (
    BUFFER,
    DETECT_MIN,
    DIVERGE_MIN,
    DIVERGE_PP,
    FALLBACK_PCT,
    REASON_DEGENERATE,
    REASON_NO_LOW,
    REASON_OK,
    detection_gate,
    mechanism,
    struct_stop_map,
    struct_stops,
)
from analysis.wave_structure_confirmation import PIVOT


def _bars(lows, closes=None, opens=None, freq="6h", start="2026-01-01"):
    n = len(lows)
    closes = closes if closes is not None else [100.0] * n
    opens = opens if opens is not None else closes
    df = pd.DataFrame({
        "open": opens, "high": [c * 1.02 for c in closes], "low": lows,
        "close": closes, "volume": [1.0] * n,
    }, index=pd.date_range(start, periods=n, freq=freq))
    df.index.name = "open_time"
    return df


def _ramp(n, step=0.1, base=100.0):
    """동률 pivot 을 피하는 단조 증가 저가 baseline.

    기존 find_swing_lows 는 `val <= before.min()` 이라 평탄 구간에서는 모든 봉이
    pivot 이 된다. 의도한 저점만 잡히도록 램프를 쓴다.
    """
    return [base + i * step for i in range(n)]


def _ev(ts, event_id="E0", symbol="BTCUSDT", ltf="6h"):
    return pd.DataFrame({"event_id": [event_id], "timestamp": [ts],
                         "symbol": [symbol], "ltf": [ltf], "pair": ["PAIR_C"]})


# ------------------------------------------------------------ 파라미터 동결
def test_constants_are_frozen():
    assert BUFFER == 0.005
    assert FALLBACK_PCT == STOP_PCT == 3.0
    assert (DETECT_MIN, DIVERGE_MIN, DIVERGE_PP) == (0.80, 0.30, 1.0)


# ------------------------------------------------------------ 손절선 계산
def test_stop_is_last_confirmed_swing_low_minus_buffer():
    lows = _ramp(30)
    lows[5] = 90.0                     # swing low
    bars = _bars(lows)
    out = struct_stops(_ev(bars.index[20]), {("BTCUSDT", "6h"): bars})
    row = out.iloc[0]
    assert row["reason"] == REASON_OK
    assert row["reference_low"] == pytest.approx(90.0)
    assert row["stop_price"] == pytest.approx(90.0 * (1 - BUFFER))
    entry = row["entry_price"]
    assert row["stop_pct"] == pytest.approx((entry - 90.0 * (1 - BUFFER)) / entry * 100)


def test_uses_the_most_recent_confirmed_low():
    lows = _ramp(40)
    lows[5], lows[15] = 90.0, 95.0
    bars = _bars(lows)
    out = struct_stops(_ev(bars.index[30]), {("BTCUSDT", "6h"): bars})
    assert out.iloc[0]["reference_low"] == pytest.approx(95.0)


# ------------------------------------------------------------ asof (룩어헤드)
def test_low_is_not_used_before_it_is_confirmed():
    """저점은 PIVOT 봉이 더 지나야 확정된다 — 그 전에는 참조하지 않는다."""
    lows = _ramp(40)
    lows[10] = 90.0
    bars = _bars(lows)
    # 신호봉 10+PIVOT-1 → 아직 미확정
    early = struct_stops(_ev(bars.index[10 + PIVOT - 1]), {("BTCUSDT", "6h"): bars}).iloc[0]
    assert early["reference_low"] != pytest.approx(90.0)
    # 신호봉 10+PIVOT → 확정
    late = struct_stops(_ev(bars.index[10 + PIVOT]), {("BTCUSDT", "6h"): bars}).iloc[0]
    assert late["reference_low"] == pytest.approx(90.0)


def test_future_lows_are_never_referenced():
    lows = _ramp(40)
    lows[30] = 50.0                    # 신호 이후의 깊은 저점
    lows[5] = 90.0
    bars = _bars(lows)
    out = struct_stops(_ev(bars.index[20]), {("BTCUSDT", "6h"): bars})
    assert out.iloc[0]["reference_low"] == pytest.approx(90.0)


# ------------------------------------------------------------ 예외 케이스
def test_no_confirmed_low_falls_back_to_base():
    bars = _bars(_ramp(30))             # 단조 증가 — 확정 저점 없음
    out = struct_stops(_ev(bars.index[3]), {("BTCUSDT", "6h"): bars})
    row = out.iloc[0]
    assert row["reason"] == REASON_NO_LOW
    assert row["detected"] is False or row["detected"] == False  # noqa: E712
    assert row["stop_pct"] == pytest.approx(FALLBACK_PCT)


def test_degenerate_stop_above_entry_falls_back_to_base():
    """저점이 진입가에 근접·상회하면 BASE 로 떨어진다."""
    lows = _ramp(30, base=101.0)
    lows[5] = 99.9                      # 저점이 진입가보다 위 → 손절선도 위
    bars = _bars(lows, closes=[100.0] * 30, opens=[99.0] * 30)  # 진입가 99
    out = struct_stops(_ev(bars.index[20]), {("BTCUSDT", "6h"): bars})
    row = out.iloc[0]
    assert row["reason"] == REASON_DEGENERATE
    assert row["stop_pct"] == pytest.approx(FALLBACK_PCT)
    assert row["applied_struct"] is False or row["applied_struct"] == False  # noqa: E712


# ------------------------------------------------- 시뮬레이터 연동
def test_struct_map_drives_the_simulator_stop_price():
    lows = _ramp(30)
    lows[5] = 90.0
    lows[12] = 80.0                     # 진입 후 구조 손절선 관통
    bars = _bars(lows, opens=[100.0] * 30)
    ev = _ev(bars.index[9])
    smap = struct_stop_map(struct_stops(ev, {("BTCUSDT", "6h"): bars}))
    tr = simulate(ev, {("BTCUSDT", "6h"): bars}, stop_pct=smap, apply_cost=False)
    row = tr.iloc[0]
    assert row["exit_reason"] == EXIT_STOP
    # 손절 체결가는 구조 손절선(90×0.995)에 슬리피지가 붙은 값
    assert row["exit_price"] < 90.0


def test_deep_struct_stop_is_not_triggered_by_shallow_dips():
    lows = _ramp(30)
    lows[5] = 70.0                      # 매우 깊은 저점 → 손절선도 깊다
    for i in range(10, 26):
        lows[i] = 96.0                  # −4% 하락은 있으나 구조선 미도달
    bars = _bars(lows, opens=[100.0] * 30)
    ev = _ev(bars.index[9])
    smap = struct_stop_map(struct_stops(ev, {("BTCUSDT", "6h"): bars}))
    tr = simulate(ev, {("BTCUSDT", "6h"): bars}, stop_pct=smap, apply_cost=False)
    assert tr.iloc[0]["exit_reason"] == EXIT_TIME
    # 같은 구간에서 고정 −3% 는 손절된다 — 계열이 실제로 다르다
    base = simulate(ev, {("BTCUSDT", "6h"): bars}, apply_cost=False)
    assert base.iloc[0]["exit_reason"] == EXIT_STOP


# ------------------------------------------------------------ §2 관문
def _gate_frame(n, applied_pct, detected=True):
    return pd.DataFrame({
        "event_id": [f"E{i}" for i in range(n)],
        "detected": [detected] * n,
        "applied_struct": [True] * n,
        "reason": [REASON_OK] * n,
        "struct_pct": applied_pct,
        "stop_pct": applied_pct,
    })


def test_gate_passes_with_detection_and_divergence():
    pcts = [1.0] * 40 + [3.2] * 60      # 40% 가 −3% 와 1%p 초과 이격
    g = detection_gate(_gate_frame(100, pcts))
    assert g["detect_rate"] == 1.0
    assert g["diverge_share"] == pytest.approx(0.40)
    assert g["go"] is True


def test_gate_blocks_when_distances_hug_three_percent():
    g = detection_gate(_gate_frame(100, [3.1] * 100))
    assert g["diverge_share"] == 0.0
    assert g["cond_diverge"] is False
    assert g["go"] is False


def test_gate_blocks_on_low_detection():
    df = _gate_frame(100, [1.0] * 100)
    df.loc[:79, "detected"] = False     # 검출률 20%
    g = detection_gate(df)
    assert g["cond_detect"] is False
    assert g["go"] is False


# ------------------------------------------------------------ §4-1 메커니즘
def test_mechanism_measures_the_realized_vs_counterfactual_gap():
    struct = pd.DataFrame({
        "event_id": ["A", "B"], "exit_reason": [EXIT_STOP, EXIT_TIME],
        "net_ret": [-0.05, 0.02],
    })
    nostop = pd.DataFrame({
        "event_id": ["A", "B"], "exit_reason": [EXIT_TIME, EXIT_TIME],
        "net_ret": [-0.01, 0.02],
    })
    m = mechanism(struct, nostop)
    assert m["stopped"] == 1
    assert m["realized_mean_pct"] == pytest.approx(-5.0)
    assert m["counterfactual_mean_pct"] == pytest.approx(-1.0)
    assert m["gap_pp"] == pytest.approx(-4.0)
    assert m["would_be_positive"] == 0
