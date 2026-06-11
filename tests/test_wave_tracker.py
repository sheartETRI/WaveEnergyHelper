"""Wave Tracker 상태 머신 테스트."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_tracker import (
    DOUBLE_BOTTOM_CANDIDATE,
    INVALIDATED,
    NONE,
    TRIPLE_BOTTOM_REQUIRED,
    WAVE3_ACTIVE,
    WAVE3_CANDIDATE,
    WAVE3_COMPLETED,
    _BarSignals,
    _MachineContext,
    step_tracker,
)


def _sig(**kwargs) -> _BarSignals:
    base = _BarSignals()
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_none_to_candidate_on_2nd_oversold_ll():
    ctx = _MachineContext()
    ts = pd.Timestamp("2026-01-01")
    step_tracker(ctx, _sig(oversold_entry=True), ts, 0)
    snap = step_tracker(
        ctx,
        _sig(oversold_entry=True, major_ll=True),
        ts + pd.Timedelta(hours=4),
        1,
    )
    assert snap.state == WAVE3_CANDIDATE
    assert "2nd Oversold" in snap.reason


def test_candidate_to_active_on_k_falling():
    ctx = _MachineContext(state=WAVE3_CANDIDATE, state_start_ts=pd.Timestamp("2026-01-01"), state_start_idx=1)
    ctx.reason = "2nd Oversold + LL"
    ctx.oversold_count = 2
    snap = step_tracker(
        ctx,
        _sig(major_k_falling=True, major_k=10.0),
        pd.Timestamp("2026-01-01 08:00"),
        2,
    )
    assert snap.state == WAVE3_ACTIVE


def test_active_to_db_candidate():
    ctx = _MachineContext(state=WAVE3_ACTIVE, state_start_ts=pd.Timestamp("2026-01-01"), state_start_idx=2)
    ctx.reason = "Major K falling"
    snap = step_tracker(
        ctx,
        _sig(small_db=True),
        pd.Timestamp("2026-01-02"),
        5,
    )
    assert snap.state == DOUBLE_BOTTOM_CANDIDATE


def test_db_to_completed_on_k_rising():
    ctx = _MachineContext(
        state=DOUBLE_BOTTOM_CANDIDATE,
        state_start_ts=pd.Timestamp("2026-01-02"),
        state_start_idx=5,
    )
    snap = step_tracker(
        ctx,
        _sig(major_k_rising=True, major_k=25.0),
        pd.Timestamp("2026-01-03"),
        8,
    )
    assert snap.state == WAVE3_COMPLETED
    assert "K turned upward" in snap.reason


def test_db_to_triple_required_on_k_falling():
    ctx = _MachineContext(
        state=DOUBLE_BOTTOM_CANDIDATE,
        state_start_ts=pd.Timestamp("2026-01-02"),
        state_start_idx=5,
    )
    snap = step_tracker(
        ctx,
        _sig(major_k_falling=True, major_k=8.0),
        pd.Timestamp("2026-01-03"),
        8,
    )
    assert snap.state == TRIPLE_BOTTOM_REQUIRED


def test_invalidation_on_new_ll():
    ctx = _MachineContext(
        state=WAVE3_ACTIVE,
        state_start_ts=pd.Timestamp("2026-01-01"),
        state_start_idx=2,
        oversold_count=2,
        oversold_at_candidate=2,
    )
    snap = step_tracker(
        ctx,
        _sig(major_ll_new=True),
        pd.Timestamp("2026-01-04"),
        10,
    )
    assert snap.state == INVALIDATED
    assert snap.invalidated
