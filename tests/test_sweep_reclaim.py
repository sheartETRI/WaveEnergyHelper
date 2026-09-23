"""스윕 재탈환 검출기 테스트 — SPEC_SWEEP_RECLAIM 판정 규칙 계약.

합성 봉으로 각 판정 경로를 1건 이상 고정한다: 봉내 스윕·다봉 재탈환·왕복·붕괴·
보류(마지막 봉)·상단 미러·거래량 비율·입력 결측. donchian_n 은 테스트 축소용으로
params 덮어쓰기(검출 정의 자체는 파라미터 불변).
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.sweep_reclaim import (
    DIR_BEAR,
    DIR_BULL,
    KIND_SWEEP_HIGH_BREAKOUT,
    KIND_SWEEP_HIGH_RECLAIM,
    KIND_SWEEP_LOW_BREAKDOWN,
    KIND_SWEEP_LOW_RECLAIM,
    _FRAME_COLUMNS,
    events_to_frame,
    scan_sweep_events,
)
from config.settings import SWEEP_RECLAIM_PARAMS

# 테스트 축소 파라미터 — 레벨 창 4봉, 체류 허용 3봉, 거래량 SMA 3봉.
P = {"donchian_n": 4, "reclaim_max_bars": 3, "vol_ma_n": 3, "touch_tol_pct": 0.005}

# 워밍업 6봉 — 하단 100 / 상단 105 의 평평한 채널.
WARM = [(105.0, 100.0, 103.0)] * 6


def _frame(rows, volumes=None):
    """rows: (high, low, close) 목록 -> OHLC 프레임."""
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="D")
    df = pd.DataFrame(
        {
            "open": [float(r[2]) for r in rows],
            "high": [float(r[0]) for r in rows],
            "low": [float(r[1]) for r in rows],
            "close": [float(r[2]) for r in rows],
        },
        index=idx,
    )
    if volumes is not None:
        df["volume"] = [float(v) for v in volumes]
    return df


def test_params_contract():
    """사전등록 파라미터 4키가 settings 에 존재한다."""
    assert {"donchian_n", "touch_tol_pct", "reclaim_max_bars", "vol_ma_n"} <= set(
        SWEEP_RECLAIM_PARAMS
    )


def test_intrabar_spring_confirmed_next_bar():
    """봉내 스윕(꼬리 이탈 + 당봉 재탈환) — t+1 유지 봉에서 확정, dwell 0."""
    rows = WARM + [(104, 98, 101), (104, 100, 102), (104, 101, 103)]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_LOW_RECLAIM
    assert e.direction == DIR_BULL
    assert e.timestamp == df.index[7]          # 확정 봉 = 재탈환 봉 + 1
    assert e.start_ts == df.index[6]
    assert e.reclaim_ts == df.index[6]         # 봉내 스윕
    assert e.level == pytest.approx(100.0)
    assert e.dwell_bars == 0
    assert e.bars_from_start == 1
    assert e.depth_pct == pytest.approx(2.0)   # (100-98)/100
    assert e.touch_count == 4                  # 워밍업 창 4봉 전부 레벨 터치
    assert e.level_age_bars == 1
    assert e.detail == ""


def test_multibar_reclaim_counts_dwell():
    """종가 이탈 2봉 후 재탈환 — dwell 2, 깊이는 에피소드 최저가 기준."""
    rows = WARM + [(104, 97, 99), (103, 98, 99.5), (103, 99, 101), (104, 100, 102), (104, 101, 103)]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_LOW_RECLAIM
    assert e.timestamp == df.index[9]
    assert e.reclaim_ts == df.index[8]
    assert e.dwell_bars == 2
    assert e.bars_from_start == 3
    assert e.depth_pct == pytest.approx(3.0)


def test_breakdown_when_dwell_exceeds_limit():
    """체류가 reclaim_max_bars 초과 -> 붕괴 발화, 이후 broken 동안 신규 이벤트 없음."""
    rows = WARM + [
        (104, 97, 99), (103, 96, 98.5), (102, 95, 98), (101, 94, 97),
        (99, 92, 92.5), (98, 91, 91.5),
    ]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_LOW_BREAKDOWN
    assert e.direction == DIR_BEAR
    assert e.timestamp == df.index[9]          # dwell 4 가 되는 봉
    assert e.reclaim_ts is None
    assert e.dwell_bars == 4
    assert e.depth_pct == pytest.approx(6.0)   # (100-94)/100


def test_round_trip_rejection_then_confirm():
    """재탈환 직후 재이탈(왕복)은 발화하지 않고, 이후 확정 1건만 — 왕복 횟수 기록."""
    rows = WARM + [(104, 98, 101), (103, 98, 99), (103, 99, 101), (104, 100, 102)]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_LOW_RECLAIM
    assert e.timestamp == df.index[9]
    assert e.reclaim_ts == df.index[8]
    assert e.dwell_bars == 1
    assert e.detail == "왕복 1회"


def test_pending_at_last_bar_emits_nothing():
    """재탈환 봉이 마지막 봉이면 보류(lookahead 없음) — 체류 중 종료도 무발화."""
    assert scan_sweep_events(_frame(WARM + [(104, 98, 101)]), P) == []
    assert scan_sweep_events(_frame(WARM + [(104, 97, 99)]), P) == []


def test_high_side_fake_breakout_mirror():
    """상단 페이크 돌파 — 고점 스윕 후 회귀는 bear 이벤트."""
    rows = WARM + [(107, 100, 104), (105, 100, 104)]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_HIGH_RECLAIM
    assert e.direction == DIR_BEAR
    assert e.side == "high"
    assert e.timestamp == df.index[7]
    assert e.level == pytest.approx(105.0)
    assert e.depth_pct == pytest.approx((107 - 105) / 105 * 100)
    assert e.touch_count == 4


def test_high_side_true_breakout():
    """상단 돌파 지속 — 체류 초과 시 진성 돌파(bull)로 발화."""
    rows = WARM + [(107, 104, 106), (108, 105, 107), (109, 106, 108), (110, 107, 109)]
    df = _frame(rows)
    events = scan_sweep_events(df, P)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_SWEEP_HIGH_BREAKOUT
    assert e.direction == DIR_BULL
    assert e.timestamp == df.index[9]
    assert e.reclaim_ts is None
    assert e.depth_pct == pytest.approx((110 - 105) / 105 * 100)


def test_volume_ratios_recorded():
    """이탈 시작 봉 거래량 스파이크가 dev/reclaim 비율로 기록된다."""
    rows = WARM + [(104, 98, 101), (104, 100, 102), (104, 101, 103)]
    vols = [1000] * 6 + [3000, 1000, 1000]
    events = scan_sweep_events(_frame(rows, vols), P)
    assert len(events) == 1
    e = events[0]
    assert e.dev_vol_ratio == pytest.approx(3.0)
    assert e.reclaim_vol_ratio == pytest.approx(3.0)   # 봉내 스윕 — 같은 봉


def test_missing_volume_and_columns_are_quiet():
    """volume 없음 -> 비율 None. 필수 컬럼 없음·빈 df -> 빈 목록."""
    rows = WARM + [(104, 98, 101), (104, 100, 102), (104, 101, 103)]
    events = scan_sweep_events(_frame(rows), P)
    assert len(events) == 1
    assert events[0].dev_vol_ratio is None
    assert events[0].reclaim_vol_ratio is None

    df = _frame(rows).drop(columns=["low"])
    assert scan_sweep_events(df, P) == []
    assert scan_sweep_events(pd.DataFrame(), P) == []


def test_events_to_frame_shape():
    """평탄화 프레임 — 컬럼 계약과 빈 목록 처리."""
    rows = WARM + [(104, 97, 99), (103, 98, 99.5), (103, 99, 101), (104, 100, 102), (104, 101, 103)]
    frame = events_to_frame(scan_sweep_events(_frame(rows), P))
    assert list(frame.columns) == _FRAME_COLUMNS
    assert len(frame) == 1

    empty = events_to_frame([])
    assert list(empty.columns) == _FRAME_COLUMNS
    assert empty.empty
