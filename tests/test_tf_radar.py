"""TF 레이더 테스트 — 상태 스냅숏(current_sweep_state)과 우선순위 계약 (SPEC §9)."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.sweep_reclaim import current_sweep_state
from analysis.tf_radar import (
    STATUS_BATTLE,
    STATUS_FRESH,
    STATUS_NEAR,
    STATUS_NO_DATA,
    STATUS_QUIET,
    build_tf_radar,
    pick_focus,
)
from config.settings import TF_RADAR_PARAMS

# 기본 파라미터(donchian 60) 그대로 — 워밍업 65봉(하단 100/상단 105 채널).
WARM = [(105.0, 100.0, 103.0)] * 65


def _frame(rows):
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="6h")
    return pd.DataFrame(
        {
            "open": [float(r[2]) for r in rows],
            "high": [float(r[0]) for r in rows],
            "low": [float(r[1]) for r in rows],
            "close": [float(r[2]) for r in rows],
        },
        index=idx,
    )


BATTLE = _frame(WARM + [(104, 98, 99)])                                  # 이탈 진행 중 (종가 하회)
PENDING = _frame(WARM + [(104, 98, 101)])                                # 봉내 스윕 — 확정 대기
FRESH = _frame(WARM + [(104, 98, 101), (104, 100, 102), (104, 101, 103)])  # 확정 1봉 전
NEAR = _frame(WARM + [(104, 100.3, 100.5)])                              # 하단까지 0.5%
QUIET = _frame(WARM)


def test_params_contract():
    assert {"intervals", "near_level_pct", "fresh_bars"} <= set(TF_RADAR_PARAMS)


def test_current_state_snapshots():
    assert current_sweep_state(BATTLE)["low"]["state"] == "episode"
    assert current_sweep_state(BATTLE)["low"]["dwell_bars"] == 1

    pend = current_sweep_state(PENDING)["low"]
    assert pend["state"] == "episode" and pend["pending_confirm"] is True

    quiet = current_sweep_state(QUIET)
    assert quiet["low"]["state"] == "normal" and quiet["high"]["state"] == "normal"

    # 컬럼 결측 -> 양쪽 normal (조용히).
    empty = current_sweep_state(pd.DataFrame())
    assert empty["low"]["state"] == "normal"


def test_priority_ordering_and_focus():
    rows = build_tf_radar({"1d": QUIET, "6h": BATTLE, "4h": FRESH, "1h": NEAR})
    assert [r.interval for r in rows] == ["6h", "4h", "1h", "1d"]
    assert [r.status for r in rows] == [STATUS_BATTLE, STATUS_FRESH, STATUS_NEAR, STATUS_QUIET]

    focus = pick_focus(rows)
    assert focus.interval == "6h"
    assert focus.side == "하단"
    assert "체류 1봉" in focus.detail


def test_tie_prefers_higher_tf():
    rows = build_tf_radar({"1d": BATTLE, "6h": BATTLE})
    assert pick_focus(rows).interval == "1d"


def test_pending_confirm_shown():
    row = build_tf_radar({"6h": PENDING})[0]
    assert row.status == STATUS_BATTLE
    assert "재탈환 확정 대기" in row.detail


def test_fresh_event_row():
    row = build_tf_radar({"6h": FRESH})[0]
    assert row.status == STATUS_FRESH
    assert "하단 스윕 재탈환" in row.last_event
    assert "1봉 전" in row.last_event


def test_no_data_and_all_quiet():
    rows = build_tf_radar({"1d": None})
    assert rows[0].status == STATUS_NO_DATA
    assert pick_focus(rows) is None
    assert pick_focus(build_tf_radar({"1d": QUIET})) is None
