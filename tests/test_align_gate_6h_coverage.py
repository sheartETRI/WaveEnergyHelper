"""PAIR_C(1d→6h) 전방 추적 커버리지 — 6h 스캔 추가의 독립성 검증.

승격은 PAIR_B + PAIR_C 통합 Δ′ 로 받았는데 라이브 스캔이 1h/4h/1d 뿐이라
PAIR_C 가 전방 추적에서 빠지던 문제를 메운다. 이 테스트가 보장하는 것:

(i)   6h 이벤트가 실제로 생성된다
(ii)  6h 추가가 1h/4h/1d 이벤트 생성 결과를 바꾸지 않는다
(iii) 6h 이벤트의 gate_align 은 1d HTF 상태를 참조하며 lookahead 가 없다
"""
import hashlib
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import wave_live_watchlist as WATCH
from analysis.wave_align_gate_forward import (
    PROMOTED_LTF_TO_HTF,
    annotate_gate_align,
    gate_states,
)
from analysis.wave_htf_gate import close_time_of, interval_delta
from analysis.wave_htf_gate_v2 import SYMBOLS_V2

FIX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SIDECAR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation", "wave_align_gate_forward.csv",
)


@pytest.fixture(scope="module")
def frozen_ohlcv():
    path = os.path.join(FIX_DIR, "align_gate_ohlcv_BTCUSDT_4h.csv")
    bare = pd.read_csv(path, index_col=0, parse_dates=True)
    bare.index.name = "open_time"
    return bare


def _scan_hash(symbol, tf, bare, pipe) -> str:
    scan = WATCH.scan_cell(symbol, tf, ohlcv=bare, pipeline=pipe, scan_bars=len(bare))
    events = WATCH.extract_rule_events(scan)
    payload = events.to_csv(index=False) if not events.empty else ""
    return hashlib.sha256(payload.encode()).hexdigest()


# ------------------------------------------------------------------- (i)
def test_6h_is_in_the_live_scan_timeframes():
    assert "6h" in WATCH.TIMEFRAMES
    assert set(WATCH.TIMEFRAMES) >= {"1h", "4h", "6h", "1d"}


def test_6h_events_exist_in_the_sidecar():
    """6h 이벤트가 실제 생성되어 PAIR_C 로 기록된다."""
    if not os.path.isfile(SIDECAR):
        pytest.skip("사이드카 없음 — --annotate 미실행")
    sc = pd.read_csv(SIDECAR, parse_dates=["timestamp"])
    six = sc[sc["timeframe"] == "6h"]
    assert len(six) > 0, "6h 이벤트가 없다 — 스캔 추가가 반영되지 않았다"
    promoted = six[six["gate_scope"] == "PROMOTED"]
    assert len(promoted) > 0
    assert set(promoted["gate_htf"].unique()) == {"1d"}, "PAIR_C 의 HTF 는 1d 여야 한다"


# ------------------------------------------------------------------ (ii)
def test_adding_6h_does_not_change_other_timeframe_event_generation(
    frozen_ohlcv, monkeypatch,
):
    """동일 입력에 대해 TIMEFRAMES 에 6h 가 있든 없든 4h 이벤트 산출이 같아야 한다.

    이벤트 생성은 (symbol, tf) 셀 단위로 닫혀 있으므로 TIMEFRAMES 멤버십과 무관해야 한다.
    """
    from analysis.wave_confluence import add_confluence_indicators
    from display.asof import run_indicator_pipeline

    pipe = add_confluence_indicators(run_indicator_pipeline(frozen_ohlcv))

    monkeypatch.setattr(WATCH, "TIMEFRAMES", ("1h", "4h", "1d"))
    without_6h = _scan_hash("BTCUSDT", "4h", frozen_ohlcv, pipe)

    monkeypatch.setattr(WATCH, "TIMEFRAMES", ("1h", "4h", "6h", "1d"))
    with_6h = _scan_hash("BTCUSDT", "4h", frozen_ohlcv, pipe)

    assert without_6h == with_6h, (
        "6h 추가가 4h 이벤트 생성을 바꿨다 — 셀 독립성이 깨졌다"
    )


def test_event_generation_does_not_read_the_timeframes_constant(frozen_ohlcv, monkeypatch):
    """TIMEFRAMES 를 비워도 명시된 tf 의 이벤트 생성은 그대로다 (읽지 않는다는 증명)."""
    from analysis.wave_confluence import add_confluence_indicators
    from display.asof import run_indicator_pipeline

    pipe = add_confluence_indicators(run_indicator_pipeline(frozen_ohlcv))
    monkeypatch.setattr(WATCH, "TIMEFRAMES", ("1h", "4h", "6h", "1d"))
    normal = _scan_hash("BTCUSDT", "4h", frozen_ohlcv, pipe)
    monkeypatch.setattr(WATCH, "TIMEFRAMES", ())
    emptied = _scan_hash("BTCUSDT", "4h", frozen_ohlcv, pipe)
    assert normal == emptied


# ----------------------------------------------------------------- (iii)
def test_6h_gate_align_uses_closed_1d_bars_without_lookahead():
    """6h 이벤트의 게이트는 1d HTF 상태를 참조하고 close_time < t 를 지킨다."""
    if not os.path.isfile(SIDECAR):
        pytest.skip("사이드카 없음 — --annotate 미실행")
    sc = pd.read_csv(
        SIDECAR, parse_dates=["timestamp", "gate_htf_open_time", "gate_htf_close_time"],
    )
    six = sc[(sc["timeframe"] == "6h") & (sc["gate_scope"] == "PROMOTED")]
    assert len(six) > 0
    evaluated = six.dropna(subset=["gate_htf_close_time"])
    assert len(evaluated) > 0
    assert (evaluated["gate_htf_close_time"] < evaluated["timestamp"]).all(), (
        "6h 이벤트가 마감되지 않은 1d 봉의 게이트 상태를 참조했다 (lookahead)"
    )
    # 참조 봉은 1d 봉 경계에 정렬돼 있어야 한다
    opens = evaluated["gate_htf_open_time"]
    assert (opens == opens.dt.normalize()).all()
    assert (opens + interval_delta("1d") <= evaluated["timestamp"]).all()


def test_6h_gate_join_is_reproducible_from_1d_states():
    """합성 1d 상태로 6h 이벤트를 조인해도 동일 asof 규칙이 적용된다."""
    opens = pd.date_range("2026-09-01", periods=10, freq="1D")
    pipe = pd.DataFrame(
        {"MA60": range(10), "MA120": range(10), "MA240": range(10)}, index=opens,
    )
    states = gate_states("BTCUSDT", "1d", pipe)
    assert list(states["htf_close_time"]) == list(close_time_of(opens, "1d"))

    events = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "timestamp": [pd.Timestamp("2026-09-05 06:00"), pd.Timestamp("2026-09-05 00:00")],
        "symbol": ["BTCUSDT", "BTCUSDT"],
        "timeframe": ["6h", "6h"],
        "rule": ["RULE_C", "RULE_C"],
        "quality_score": [4, 4],
        "return_20": [1.0, 2.0],
    })
    out = annotate_gate_align(events, {("BTCUSDT", "1d"): states})
    assert set(out["gate_htf"]) == {"1d"}
    for _, row in out.iterrows():
        assert row["gate_htf_close_time"] < row["timestamp"]
    # 1d 봉 경계에 놓인 이벤트는 아직 마감되지 않은 당일 봉을 쓰지 않는다
    boundary = out[out["timestamp"] == pd.Timestamp("2026-09-05 00:00")].iloc[0]
    assert boundary["gate_htf_open_time"] == pd.Timestamp("2026-09-04")


# ------------------------------------------- 표본 손실 방지 (감사 불변식)
def test_sidecar_preserves_every_journal_event():
    """사이드카는 저널의 모든 이벤트를 보존한다 — 조용한 누락은 감사를 무력화한다."""
    if not os.path.isfile(SIDECAR):
        pytest.skip("사이드카 없음")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    journal = pd.read_csv(os.path.join(root, "validation", "wave_live_forward_journal.csv"))
    sc = pd.read_csv(SIDECAR)
    assert len(sc) == len(journal)
    assert set(sc["event_id"]) == set(journal["event_id"])


def test_out_of_scope_symbols_are_recorded_not_dropped():
    """승격 심볼 밖 이벤트는 평가되지 않되 범위 밖으로 기록된다."""
    events = pd.DataFrame({
        "event_id": ["IN", "OUT"],
        "timestamp": [pd.Timestamp("2026-09-10"), pd.Timestamp("2026-09-10")],
        "symbol": ["BTCUSDT", "SOLUSDT"],
        "timeframe": ["6h", "6h"],
        "rule": ["RULE_C", "RULE_C"],
        "quality_score": [4, 4],
        "return_20": [1.0, 2.0],
    })
    opens = pd.date_range("2026-09-01", periods=12, freq="1D")
    pipe = pd.DataFrame(
        {"MA60": range(12), "MA120": range(12), "MA240": range(12)}, index=opens,
    )
    out = annotate_gate_align(events, {("BTCUSDT", "1d"): gate_states("BTCUSDT", "1d", pipe)})
    assert len(out) == 2
    scopes = dict(zip(out["event_id"], out["gate_scope"]))
    assert scopes["IN"] == "PROMOTED"
    assert scopes["OUT"] == "OUT_OF_SCOPE_SYMBOL"
    assert pd.isna(out[out["event_id"] == "OUT"]["gate_align"].iloc[0])
    assert "SOLUSDT" not in SYMBOLS_V2


def test_promoted_map_still_covers_both_pairs():
    assert PROMOTED_LTF_TO_HTF == {"1h": "4h", "6h": "1d"}
