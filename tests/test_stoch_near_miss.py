"""구역 니어미스 기록 테스트 — SPEC_SWEEP_RECLAIM §7 판정 계약."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.stoch_near_miss import (
    KIND_DB_NEAR,
    KIND_DT_NEAR,
    _FRAME_COLUMNS,
    near_miss_to_frame,
    scan_near_miss_events,
)
from config.settings import STOCH_NEAR_MISS_PARAMS, WAVE_LAYER_ROLES

LARGE = WAVE_LAYER_ROLES["large"]


def _frame(k_values):
    idx = pd.date_range("2026-01-01", periods=len(k_values), freq="6h")
    return pd.DataFrame({f"stoch_k_{LARGE}": [float(v) for v in k_values]}, index=idx)


def test_params_contract():
    assert {"near_band", "layer_roles"} <= set(STOCH_NEAR_MISS_PARAMS)


def test_db_near_miss_in_band():
    """침체선(20) 초과 ~ +5 이내 국소 극소 -> db 니어미스, 확정은 t+1."""
    df = _frame([50, 40, 30, 22, 24, 30])
    events = scan_near_miss_events(df)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_DB_NEAR
    assert e.extreme_ts == df.index[3]
    assert e.timestamp == df.index[4]
    assert e.k_extreme == pytest.approx(22.0)
    assert e.zone == pytest.approx(20.0)
    assert e.margin == pytest.approx(2.0)


def test_in_zone_trough_not_recorded():
    """K ≤ 침체선(구역 진입)은 본 검출기 영역 — 니어미스 아님."""
    assert scan_near_miss_events(_frame([50, 40, 30, 18, 24, 30])) == []


def test_above_band_trough_not_recorded():
    """경계 + near_band 초과 극소는 기록하지 않는다."""
    assert scan_near_miss_events(_frame([50, 40, 32, 27, 30, 35])) == []


def test_dt_near_miss_mirror():
    """과매수선(80) 미달 ~ −5 이내 국소 극대 -> dt 니어미스."""
    df = _frame([50, 60, 70, 78, 76, 70])
    events = scan_near_miss_events(df)
    assert len(events) == 1
    e = events[0]
    assert e.kind == KIND_DT_NEAR
    assert e.k_extreme == pytest.approx(78.0)
    assert e.margin == pytest.approx(2.0)


def test_in_zone_peak_not_recorded():
    """K ≥ 과매수선 극대는 본 검출기 영역 — 기록 안 함."""
    assert scan_near_miss_events(_frame([50, 60, 70, 85, 76, 70])) == []


def test_last_bar_extreme_held():
    """마지막 봉이 극소 후보면 보류(lookahead 없음)."""
    assert scan_near_miss_events(_frame([50, 40, 30, 22])) == []


def test_missing_column_quiet():
    idx = pd.date_range("2026-01-01", periods=5, freq="6h")
    df = pd.DataFrame({"close": [1.0] * 5}, index=idx)
    assert scan_near_miss_events(df) == []
    assert scan_near_miss_events(pd.DataFrame()) == []


def test_near_miss_to_frame_shape():
    df = _frame([50, 40, 30, 22, 24, 30])
    frame = near_miss_to_frame(scan_near_miss_events(df))
    assert list(frame.columns) == _FRAME_COLUMNS
    assert len(frame) == 1

    empty = near_miss_to_frame([])
    assert list(empty.columns) == _FRAME_COLUMNS
    assert empty.empty
