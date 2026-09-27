"""스윕/합류 알람 행 승계 테스트 — 알람 스캔에 확정 이벤트가 행으로 실리는 계약.

검출 정의 자체는 test_sweep_reclaim / test_sweep_confluence 가 고정한다. 여기서는
승계(라벨·방향·레이어 이름·값·비고)와 기존 프레임(스토캐 전용) 무영향만 본다.
기본 파라미터(donchian 60) 그대로 쓰므로 워밍업 65봉 합성 프레임을 만든다.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.alarm_signals import SEV_CONFIRMED, scan_alarm_signals
from analysis.sweep_confluence import KIND_CONFLUENCE_BULL
from analysis.sweep_reclaim import KIND_SWEEP_LOW_RECLAIM
from config.settings import WAVE_LAYER_ROLES

LARGE = WAVE_LAYER_ROLES["large"]

# 워밍업 65봉(하단 100) + 봉내 스윕 + 확정 봉 — 스윕 확정 위치 = 66.
ROWS = [(105.0, 100.0, 103.0)] * 65 + [(104, 98, 101), (104, 100, 102), (104, 101, 103)]


def _ohlc_frame():
    idx = pd.date_range("2026-01-01", periods=len(ROWS), freq="6h")
    return pd.DataFrame(
        {
            "open": [float(r[2]) for r in ROWS],
            "high": [float(r[0]) for r in ROWS],
            "low": [float(r[1]) for r in ROWS],
            "close": [float(r[2]) for r in ROWS],
        },
        index=idx,
    )


def test_sweep_row_carried_into_alarm_scan():
    df = _ohlc_frame()
    rows = [s for s in scan_alarm_signals(df) if s.kind == KIND_SWEEP_LOW_RECLAIM]
    assert len(rows) == 1
    s = rows[0]
    assert s.label == "하단 스윕 재탈환"
    assert s.direction == "bull"
    assert s.severity == SEV_CONFIRMED
    assert s.timestamp == df.index[66]
    assert s.layer is None
    assert s.layer_name == "스윕"          # _KIND_METRIC 승계 — RSI 로 새지 않는다
    assert s.metric_name == "레벨"
    assert s.value == pytest.approx(100.0)
    assert "체류 0봉" in s.detail


def test_confluence_row_when_stoch_columns_present():
    df = _ohlc_frame()
    vals = pd.Series(pd.NA, index=df.index, dtype="Float64")
    vals.iloc[66] = 25.0                    # 스윕 확정 봉과 gap 0
    df[f"stoch_db_{LARGE}"] = vals
    rows = [s for s in scan_alarm_signals(df) if s.kind == KIND_CONFLUENCE_BULL]
    assert len(rows) == 1
    s = rows[0]
    assert s.label == "스윕·쌍바닥 합류"
    assert s.layer_name == "합류"
    assert "gap +0봉" in s.detail


def test_stoch_only_frames_unaffected():
    """high/low/close 없는 기존 스타일 프레임 -> 스윕/합류 행 없음 (하위 호환)."""
    idx = pd.date_range("2026-01-01", periods=10, freq="h")
    df = pd.DataFrame({f"stoch_k_{LARGE}": range(10)}, index=idx, dtype=float)
    kinds = {s.kind for s in scan_alarm_signals(df)}
    assert not any(k.startswith("sweep_") for k in kinds)
