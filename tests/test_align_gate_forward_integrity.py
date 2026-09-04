"""SPEC_WAVE_ALIGN_GATE_FORWARD §3 — 무개입 회귀 테스트.

전방 추적 6개월 동안 게이트·트리거·asof 정의가 바뀌지 않았음을 **선언이 아니라 검증**으로
강제한다. 동결 fixture 를 현재 코드로 재계산해 해시가 같은지 본다.

이 테스트가 깨지면: 정의가 바뀐 것이다. 고칠 이유가 있었다면 추적을 리셋하고
그 사실을 보고에 남겨야 한다 (헌장 §3-5). 기준선을 조용히 갱신하지 않는다.
"""
import hashlib
import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_align_gate_forward import (
    INTEGRITY_FILES,
    PROMOTED_LTF_TO_HTF,
    REVIEW_DUE,
    TRACKING_MONTHS,
    TRACKING_START,
    gate_states,
)
from analysis.wave_htf_gate import (
    TRIGGER_QUALITY,
    TRIGGER_RULE,
    G_WAVE_STATES,
    attach_htf_gates,
    trigger_events,
)
from analysis.wave_htf_gate_v2 import (
    F2B_MA_PERIODS,
    F2B_SLOPE_BARS,
    PAIRS_V2,
    SYMBOLS_V2,
    f2b_rising_flags,
)
from config.settings import CORE_MA_PERIODS, MA_PERIODS, WAVE_LAYER_ROLES

FIX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _sha(items) -> str:
    return hashlib.sha256("\n".join(items).encode()).hexdigest()


@pytest.fixture(scope="module")
def baseline() -> dict:
    path = os.path.join(FIX_DIR, "align_gate_baseline.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def frozen_pipe(baseline):
    from display.asof import run_indicator_pipeline

    path = os.path.join(FIX_DIR, baseline["gate"]["ohlcv_fixture"])
    bare = pd.read_csv(path, index_col=0, parse_dates=True)
    bare.index.name = "open_time"
    return run_indicator_pipeline(bare)


# ------------------------------------------------------- 정의 상수 동결
def test_gate_definition_constants_are_frozen():
    """F2-b 게이트 정의 — 이평 조합과 기울기 창."""
    assert F2B_MA_PERIODS == (60, 120, 240)
    assert F2B_SLOPE_BARS == 1
    assert 60 in MA_PERIODS and 120 in MA_PERIODS and 240 in MA_PERIODS
    assert CORE_MA_PERIODS == [5, 10, 20, 60, 120, 240]
    assert WAVE_LAYER_ROLES == {
        "large": "(20,10,10)", "mid": "(10,5,5)", "small": "(5,3,3)",
    }


def test_trigger_definition_constants_are_frozen():
    """이벤트 트리거 — Filter_C ∪ Filter_Q."""
    assert TRIGGER_RULE == "RULE_C"
    assert TRIGGER_QUALITY == 4
    assert G_WAVE_STATES == (
        "DOUBLE_BOTTOM_CANDIDATE", "WAVE3_COMPLETED", "TRIPLE_BOTTOM_CONFIRMED",
    )


def test_promoted_pairs_are_frozen():
    assert PAIRS_V2 == {"PAIR_B": ("4h", "1h"), "PAIR_C": ("1d", "6h")}
    assert PROMOTED_LTF_TO_HTF == {"1h": "4h", "6h": "1d"}
    assert SYMBOLS_V2 == ("BTCUSDT", "ETHUSDT", "BNBUSDT")


def test_tracking_window_is_frozen():
    assert TRACKING_START == pd.Timestamp("2026-09-01")
    assert TRACKING_MONTHS == 6
    assert REVIEW_DUE == pd.Timestamp("2027-03-01")


def test_integrity_file_list_covers_the_definition_surface():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in INTEGRITY_FILES:
        assert os.path.isfile(os.path.join(root, rel)), rel
    for must in ("analysis/wave_htf_gate_v2.py", "analysis/wave_htf_gate.py",
                 "indicators/moving_averages.py", "config/settings.py"):
        assert must in INTEGRITY_FILES


# --------------------------------------------- 재계산 동치성 (핵심 회귀)
def test_gate_recomputation_matches_frozen_baseline(baseline, frozen_pipe):
    """동결 OHLCV → 현재 코드의 F2-b 플래그가 기준선과 비트 단위로 같아야 한다."""
    flags = f2b_rising_flags(frozen_pipe)
    flag_str = "".join("1" if v else "0" for v in flags)
    g = baseline["gate"]
    assert len(flags) == g["bars"]
    assert int(flags.sum()) == g["open_bars"]
    assert flag_str[-20:] == g["last_20"]
    assert hashlib.sha256(flag_str.encode()).hexdigest() == g["flag_sha256"], (
        "F2-b 게이트 산출물이 기준선과 다르다 — 게이트/MA 정의가 바뀌었다. "
        "헌장 §3 에 따라 추적은 무효이며 리셋 후 보고에 명기해야 한다."
    )


def test_trigger_recomputation_matches_frozen_baseline(baseline):
    """동결 저널 슬라이스 → 현재 코드의 트리거 코호트가 기준선과 같아야 한다."""
    t = baseline["trigger"]
    path = os.path.join(FIX_DIR, t["journal_fixture"])
    jslice = pd.read_csv(path, parse_dates=["timestamp"])
    assert len(jslice) == t["rows"]
    ev = trigger_events(jslice, "1h")
    assert len(ev) == t["event_count"]
    assert _sha(sorted(ev["event_id"].astype(str))) == t["event_ids_sha256"], (
        "트리거 코호트가 기준선과 다르다 — 이벤트 정의가 바뀌었다 (헌장 §3)."
    )


def test_asof_join_recomputation_matches_frozen_baseline(baseline, frozen_pipe):
    """동결 상태 + 동결 이벤트 → asof 조인 결과가 기준선과 같아야 한다."""
    a = baseline["asof"]
    jslice = pd.read_csv(
        os.path.join(FIX_DIR, baseline["trigger"]["journal_fixture"]),
        parse_dates=["timestamp"],
    )
    ev = trigger_events(jslice, "1h")
    btc = ev[ev["symbol"] == "BTCUSDT"]
    joined = attach_htf_gates(btc, gate_states("BTCUSDT", "4h", frozen_pipe), "4h")
    assert len(joined) == a["joined"]
    assert int(joined["g_align"].sum()) == a["align_true"]
    pairs = [
        f"{r.event_id}|"
        f"{pd.Timestamp(r.htf_open_time).isoformat() if pd.notna(r.htf_open_time) else 'NA'}|"
        f"{int(bool(r.g_align))}"
        for r in joined.itertuples()
    ]
    assert _sha(pairs) == a["pairs_sha256"], (
        "asof 조인 결과가 기준선과 다르다 — 조인 규칙 또는 게이트가 바뀌었다 (헌장 §3)."
    )


def test_asof_still_blocks_lookahead_on_frozen_data(baseline, frozen_pipe):
    """회귀 기준선과 별개로, asof 불변식 자체도 계속 성립해야 한다."""
    jslice = pd.read_csv(
        os.path.join(FIX_DIR, baseline["trigger"]["journal_fixture"]),
        parse_dates=["timestamp"],
    )
    ev = trigger_events(jslice, "1h")
    btc = ev[ev["symbol"] == "BTCUSDT"]
    joined = attach_htf_gates(btc, gate_states("BTCUSDT", "4h", frozen_pipe), "4h")
    sample = joined.dropna(subset=["htf_close_time"])
    assert len(sample) > 0
    assert (sample["htf_close_time"] < sample["timestamp"]).all()


# ---------------------------------------------- 재검토 트리거 (동결 규칙)
def test_review_trigger_opens_retraction_only_when_ci_upper_below_zero():
    from analysis.wave_align_gate_forward import RETRACT_REVIEW, review_decision

    d = review_decision({"delta": -0.4, "ci_low": -0.9, "ci_high": -0.1})
    assert d["decision"] == RETRACT_REVIEW


def test_review_trigger_extends_when_negative_but_ci_spans_zero():
    from analysis.wave_align_gate_forward import EXTEND, review_decision

    d = review_decision({"delta": -0.4, "ci_low": -0.9, "ci_high": 0.2})
    assert d["decision"] == EXTEND


def test_review_trigger_keeps_when_positive():
    from analysis.wave_align_gate_forward import KEEP, review_decision

    assert review_decision({"delta": 0.3, "ci_low": 0.1, "ci_high": 0.6})["decision"] == KEEP
    # 양수인데 CI 가 0 을 포함해도 회수 조건은 아니다
    assert review_decision({"delta": 0.3, "ci_low": -0.1, "ci_high": 0.6})["decision"] == KEEP


def test_review_trigger_extends_when_ci_unavailable():
    from analysis.wave_align_gate_forward import EXTEND, review_decision

    d = review_decision({"delta": None, "ci_low": None, "ci_high": None})
    assert d["decision"] == EXTEND


def test_review_trigger_boundary_ci_upper_exactly_zero_does_not_retract():
    """CI 상한이 정확히 0 이면 '0 미만'이 아니므로 회수 논의를 열지 않는다."""
    from analysis.wave_align_gate_forward import EXTEND, review_decision

    assert review_decision({"delta": -0.2, "ci_low": -0.5, "ci_high": 0.0})["decision"] == EXTEND


def test_review_rule_text_is_recorded_with_every_decision():
    from analysis.wave_align_gate_forward import REVIEW_RULE, review_decision

    for boot in ({"delta": -0.4, "ci_low": -0.9, "ci_high": -0.1},
                 {"delta": 0.3, "ci_low": 0.1, "ci_high": 0.6}):
        assert review_decision(boot)["rule"] == REVIEW_RULE


# ------------------------------------------------- 기록 전용 배선 불변식
def test_annotate_never_mutates_the_source_journal():
    from analysis.wave_align_gate_forward import annotate_gate_align

    journal = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "timestamp": [pd.Timestamp("2026-09-10 05:00"), pd.Timestamp("2026-09-10 06:00")],
        "symbol": ["BTCUSDT", "BTCUSDT"],
        "timeframe": ["1h", "1h"],
        "rule": ["RULE_C", "RULE_A"],
        "quality_score": [3, 4],
        "return_20": [1.0, -2.0],
    })
    before = journal.copy(deep=True)
    annotate_gate_align(journal, {})
    pd.testing.assert_frame_equal(journal, before)


def test_non_promoted_timeframes_are_recorded_as_not_evaluated():
    from analysis.wave_align_gate_forward import annotate_gate_align

    journal = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "timestamp": [pd.Timestamp("2026-09-10"), pd.Timestamp("2026-09-11")],
        "symbol": ["BTCUSDT", "BTCUSDT"],
        "timeframe": ["4h", "1d"],  # 승격 쌍의 LTF 가 아니다
        "rule": ["RULE_C", "RULE_C"],
        "quality_score": [4, 4],
        "return_20": [1.0, 2.0],
    })
    out = annotate_gate_align(journal, {})
    assert set(out["gate_scope"]) == {"NOT_PROMOTED"}
    assert out["gate_align"].isna().all()


def test_forward_slice_keeps_only_promoted_events_after_tracking_start():
    from analysis.wave_align_gate_forward import TRACKING_START, forward_slice

    sidecar = pd.DataFrame({
        "event_id": ["A", "B", "C"],
        "timestamp": [TRACKING_START - pd.Timedelta(days=1),
                      TRACKING_START + pd.Timedelta(days=1),
                      TRACKING_START + pd.Timedelta(days=2)],
        "gate_scope": ["PROMOTED", "PROMOTED", "NOT_PROMOTED"],
        "gate_align": [True, False, pd.NA],
    })
    out = forward_slice(sidecar)
    assert list(out["event_id"]) == ["B"]
