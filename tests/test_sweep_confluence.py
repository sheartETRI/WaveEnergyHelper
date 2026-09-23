"""스윕×쌍바닥 합류 테스트 — SPEC_SWEEP_RECLAIM §6 판정 규칙 계약.

스토캐 검출 컬럼은 확정 봉에만 값이 있는 출력 모사(검출기 무수정 계약과 동일)로
만들고, 스윕 쪽은 test_sweep_reclaim 과 같은 합성 봉을 쓴다.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.sweep_confluence import (
    KIND_CONFLUENCE_BEAR,
    KIND_CONFLUENCE_BULL,
    _FRAME_COLUMNS,
    confluence_to_frame,
    scan_confluence_events,
)
from analysis.sweep_reclaim import scan_sweep_events
from config.settings import SWEEP_CONFLUENCE_PARAMS, WAVE_LAYER_ROLES

LARGE = WAVE_LAYER_ROLES["large"]

# 스윕 쪽 축소 파라미터 (test_sweep_reclaim 과 동일).
P_SWEEP = {"donchian_n": 4, "reclaim_max_bars": 3, "vol_ma_n": 3, "touch_tol_pct": 0.005}
WARM = [(105.0, 100.0, 103.0)] * 6

# 봉내 스윕 → pos 7 에서 sweep_low_reclaim 확정.
SPRING = WARM + [(104, 98, 101), (104, 100, 102), (104, 101, 103)]
# 상단 페이크 돌파 → pos 7 에서 sweep_high_reclaim 확정.
FAKE_HIGH = WARM + [(107, 100, 104), (105, 100, 104), (105, 100, 103)]
# 하단 붕괴 → pos 9 에서 breakdown (합류 비참여 확인용).
BREAKDOWN = WARM + [
    (104, 97, 99), (103, 96, 98.5), (102, 95, 98), (101, 94, 97),
    (99, 92, 92.5), (98, 91, 91.5),
]


def _frame(rows):
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(
        {
            "open": [float(r[2]) for r in rows],
            "high": [float(r[0]) for r in rows],
            "low": [float(r[1]) for r in rows],
            "close": [float(r[2]) for r in rows],
        },
        index=idx,
    )


def _with_stoch(df, prefix, positions, kinds=None, suffix=LARGE):
    """확정 봉에만 값이 있는 검출기 출력 모사 컬럼을 붙인다."""
    vals = pd.Series(pd.NA, index=df.index, dtype="Float64")
    for pos in positions:
        vals.iloc[pos] = 25.0
    df[f"{prefix}_{suffix}"] = vals
    kind_series = pd.Series([None] * len(df), index=df.index, dtype="object")
    for pos, kind in (kinds or {}).items():
        kind_series.iloc[pos] = kind
    df[f"{prefix}_kind_{suffix}"] = kind_series
    return df


def test_params_contract():
    assert {"max_gap_bars", "layer_roles"} <= set(SWEEP_CONFLUENCE_PARAMS)


def test_bull_confluence_basic():
    """스윕 확정(pos 7) × 쌍바닥 확정(pos 5) — timestamp 는 나중 봉, gap 은 부호 있음."""
    df = _with_stoch(_frame(SPRING), "stoch_db", [5], kinds={5: "HL"})
    events = scan_confluence_events(df, sweep_params=P_SWEEP)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_CONFLUENCE_BULL
    assert e.layer == LARGE
    assert e.timestamp == df.index[7]
    assert e.sweep_ts == df.index[7]
    assert e.stoch_ts == df.index[5]
    assert e.gap_bars == -2                 # 쌍바닥이 먼저
    assert e.db_kind == "HL"
    assert e.level == pytest.approx(100.0)
    assert e.dwell_bars == 0


def test_gap_limit_excludes():
    """|gap| > max_gap_bars 이면 합류 아님."""
    df = _with_stoch(_frame(SPRING), "stoch_db", [5])
    assert scan_confluence_events(df, params={"max_gap_bars": 1}, sweep_params=P_SWEEP) == []


def test_nearest_confirmation_wins():
    """창 내 쌍바닥 확정이 여럿이면 |gap| 최소를 짝짓는다."""
    df = _with_stoch(_frame(SPRING), "stoch_db", [5, 8])
    events = scan_confluence_events(df, sweep_params=P_SWEEP)
    assert len(events) == 1
    e = events[0]
    assert e.stoch_ts == df.index[8]        # |+1| < |-2|
    assert e.gap_bars == 1
    assert e.timestamp == df.index[8]       # 나중 봉


def test_bear_mirror():
    """상단 페이크 돌파 × 쌍봉 — bear 합류."""
    df = _with_stoch(_frame(FAKE_HIGH), "stoch_dt", [7], kinds={7: "LH"})
    events = scan_confluence_events(df, sweep_params=P_SWEEP)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_CONFLUENCE_BEAR
    assert e.gap_bars == 0
    assert e.db_kind == "LH"
    assert e.timestamp == df.index[7]


def test_breakdown_does_not_join():
    """붕괴 지속 이벤트는 근처에 쌍바닥 확정이 있어도 합류하지 않는다."""
    df = _with_stoch(_frame(BREAKDOWN), "stoch_db", [8])
    sweeps = scan_sweep_events(df, P_SWEEP)
    assert len(sweeps) == 1                 # breakdown 1건뿐
    assert scan_confluence_events(df, sweep_events=sweeps) == []


def test_missing_stoch_columns_quiet():
    """스토캐 컬럼이 없으면 조용히 빈 목록."""
    assert scan_confluence_events(_frame(SPRING), sweep_params=P_SWEEP) == []


def test_precomputed_sweep_events_reused():
    """사전 계산한 sweep_events 를 넘겨도 같은 결과."""
    df = _with_stoch(_frame(SPRING), "stoch_db", [5])
    sweeps = scan_sweep_events(df, P_SWEEP)
    a = scan_confluence_events(df, sweep_events=sweeps)
    b = scan_confluence_events(df, sweep_params=P_SWEEP)
    assert a == b and len(a) == 1


def test_confluence_to_frame_shape():
    df = _with_stoch(_frame(SPRING), "stoch_db", [5], kinds={5: "HL"})
    frame = confluence_to_frame(scan_confluence_events(df, sweep_params=P_SWEEP))
    assert list(frame.columns) == _FRAME_COLUMNS
    assert len(frame) == 1

    empty = confluence_to_frame([])
    assert list(empty.columns) == _FRAME_COLUMNS
    assert empty.empty
