"""변곡점 트레이스(trace_transitions) 관측 단위 테스트.

실행: `python -m pytest tests/test_transition_trace.py` 또는 `python tests/test_transition_trace.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import WAVE_LAYER_ROLES
from analysis.dynamics_rules import (
    trace_transitions,
    evaluate_transitions,
    structure_distribution,
)

# test_transition_rules.py와 동일한 합성 도우미를 재사용한다.
from tests.test_transition_rules import (
    _struct_df,
    _inject_wave,
    _scenario_F6_4a,
    IDX,
)


def test_trace_hit_matches_completion():
    """(a) HIT 케이스: result='HIT', completion_bar가 evaluate_transitions와 일치."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)   # mid dt @20 + small tt @22 -> 완성 봉 22

    traces = trace_transitions(df)
    tr = next(t for t in traces if t.rule_id == "F6-4a")
    assert tr.result == "HIT"
    assert tr.completion_bar == IDX[22]
    assert tr.structure_actual == "U1"
    # first_pos 미주입 시 확정봉 폴백 → formation = min(20,22)=20
    assert tr.formation_bar == IDX[20]

    # evaluate_transitions의 완성 봉과 동일해야 한다 (HIT 경로 일치)
    hit = next(h for h in evaluate_transitions(df) if h.rule_id == "F6-4a")
    assert hit.bar_index == tr.completion_bar
    assert hit.formation_bar == tr.formation_bar


def test_trace_window_blocked_records_outside_bar():
    """(b) 윈도 밖 신호: WINDOW_BLOCKED 라벨 + 윈도 밖 봉 기록."""
    df = _struct_df("U1")
    _inject_wave(df, "mid", "dt", 0)    # transition_recent_bars(24) 밖 (N=30)
    _inject_wave(df, "small", "tt", 25) # 윈도 안

    traces = trace_transitions(df)
    tr = next(t for t in traces if t.rule_id == "F6-4a")

    assert tr.result == "WINDOW_BLOCKED:중파동 쌍봉"
    blocked_atom = next(a for a in tr.atoms if a.atom == "중파동 쌍봉")
    assert blocked_atom.satisfied is False
    assert blocked_atom.block_reason == "WINDOW_BLOCKED"
    assert blocked_atom.last_outside_bar == IDX[0]

    # 다른 원자(소파동 쓰리봉)는 윈도 안이라 충족
    ok_atom = next(a for a in tr.atoms if a.atom == "소파동 쓰리봉")
    assert ok_atom.satisfied is True


def test_evaluate_transitions_unchanged_by_trace():
    """trace 호출이 evaluate_transitions 결과를 바꾸지 않음(부수효과 없음)."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    before = [(h.rule_id, h.bar_index, h.bullish) for h in evaluate_transitions(df)]
    _ = trace_transitions(df)
    after = [(h.rule_id, h.bar_index, h.bullish) for h in evaluate_transitions(df)]
    assert before == after


def test_structure_distribution_counts():
    df = _struct_df("U1")   # 모든 봉이 U1 배열
    dist = structure_distribution(df)
    assert dist["U1"] == len(df)
    assert sum(dist.values()) == len(df)
    assert None in dist


if __name__ == "__main__":
    test_trace_hit_matches_completion()
    test_trace_window_blocked_records_outside_bar()
    test_evaluate_transitions_unchanged_by_trace()
    test_structure_distribution_counts()
    print("ALL TRANSITION TRACE TESTS PASSED")
