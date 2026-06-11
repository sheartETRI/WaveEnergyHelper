"""변곡 레이더 표시 헬퍼 테스트.

실행: python -m pytest tests/test_radar_display.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.transition_radar import (
    build_forming_item,
    build_transition_radar,
    extract_forming_items,
    find_most_recent_hit,
    format_environment_line,
    format_recent_hit_caption,
    is_forming_trace,
)
from analysis.dynamics_rules import (
    AtomTrace,
    RuleTrace,
    TRANSITION_RULE_TABLE,
    evaluate_transitions,
    parse_transition_row,
    trace_transitions,
)
from tests.test_dispersion_annotation import EXPECTED_ZONE_HITS
from tests.test_transition_rules import (
    IDX,
    _inject_ma,
    _inject_ma_first_pos,
    _inject_wave,
    _scenario_F6_4a,
    _scenario_F6_5c_b,
    _struct_df,
)
from validation.gt_trace import (
    SYMBOL,
    INTERVAL,
    evaluate_transition_in_zone,
    fmt_ts,
    load_df_gt,
    zone_ranges,
)


def test_forming_from_synthetic_trace_window_blocked():
    """원자 1/2 충족 → FORMING 항목, 누락 원자·경과 봉 정확."""
    df = _struct_df("U1")
    _inject_wave(df, "mid", "dt", 0)
    _inject_wave(df, "small", "tt", 25)

    traces = trace_transitions(df)
    tr = next(t for t in traces if t.rule_id == "F6-4a")
    assert is_forming_trace(tr)

    items = extract_forming_items(df, traces)
    assert len(items) == 1
    item = items[0]
    assert item.rule_id == "F6-4a"
    assert "소파동 쓰리봉 확정" in item.headline_html
    assert "중파동 쌍봉 대기" in item.detail
    assert "윈도 24봉 중 4봉 경과" in item.detail


def test_forming_structure_match_checkmark():
    """형성 피봇 구조 일치 → ✓."""
    df = _struct_df("D3")
    _inject_ma_first_pos(df, 10, "db", 25, 20)
    structure, atoms, _, _, window = parse_transition_row(
        next(r for r in TRANSITION_RULE_TABLE if r[2] == "F6-5c-b")
    )
    sat = AtomTrace("MA10 쌍바닥(LL)", True, [IDX[25]], None, None, False)
    pend = AtomTrace("대파동 쌍바닥(HL)", False, [], IDX[5], "WINDOW_BLOCKED")
    tr = RuleTrace(
        "F6-5c-b", [sat, pend], None, None, "D3", None,
        "WINDOW_BLOCKED:대파동 쌍바닥(HL)",
    )
    item = build_forming_item(df, tr, structure, atoms, window)
    assert "형성 피봇 구조 D3 ✓" in item.headline_html
    assert item.structure_match is True


def test_forming_structure_mismatch_gray():
    """형성 피봇 구조 불일치 → 회색 span, structure_match False."""
    df = _struct_df("U1")
    _inject_ma_first_pos(df, 10, "db", 25, 20)
    structure, atoms, _, _, window = parse_transition_row(
        next(r for r in TRANSITION_RULE_TABLE if r[2] == "F6-5c-b")
    )
    sat = AtomTrace("MA10 쌍바닥(LL)", True, [IDX[25]], None, None, False)
    pend = AtomTrace("대파동 쌍바닥(HL)", False, [], IDX[5], "WINDOW_BLOCKED")
    tr = RuleTrace(
        "F6-5c-b", [sat, pend], None, None, "D3", None,
        "WINDOW_BLOCKED:대파동 쌍바닥(HL)",
    )
    item = build_forming_item(df, tr, structure, atoms, window)
    assert "color:#888" in item.headline_html
    assert "형성 피봇 구조 U1" in item.headline_html
    assert item.structure_match is False


def test_forming_zero_shows_none_message():
    """FORMING 0건 → forming_items 빈 리스트."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    traces = trace_transitions(df)
    assert not any(is_forming_trace(t) for t in traces)
    content = build_transition_radar(df, traces)
    assert content.forming_items == []


def test_recent_hit_outside_current_window():
    """윈도 밖 hit → N봉 전 캡션."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    hit = find_most_recent_hit(df)
    assert hit is not None
    assert hit["rule_id"] == "F6-4a"
    caption = format_recent_hit_caption(df, hit)
    assert "F6-4a" in caption
    bars_ago = len(df) - 1 - hit["comp_pos"]
    assert f"{bars_ago}봉 전" in caption

    df2 = _struct_df("U1")
    _inject_wave(df2, "mid", "dt", 3)
    _inject_wave(df2, "small", "tt", 5)
    hit2 = find_most_recent_hit(df2)
    assert hit2["comp_pos"] == 5
    caption2 = format_recent_hit_caption(df2, hit2)
    assert f"{len(df2) - 1 - 5}봉 전" in caption2


def test_environment_line_nan_omitted():
    """이격도 NaN → environment_line None."""
    df = _struct_df("U1")
    df["ma_dispersion"] = pd.NA
    assert format_environment_line(df) is None
    df["ma_dispersion"] = np.linspace(0.01, 0.10, len(df))
    line = format_environment_line(df)
    assert line is not None
    assert line.startswith("변곡 환경: 이격도 P")


def test_forming_sort_structure_match_first():
    """구조 일치 행이 불일치보다 위."""
    df = _struct_df("D3")
    _inject_ma(df, 10, "db", 25, kind="LL")
    _inject_ma_first_pos(df, 10, "db", 25, 20)
    _inject_wave(df, "large", "db", 5, kind="HL")
    _inject_wave(df, "mid", "db", 25)
    _inject_wave(df, "small", "tb", 27)

    items = extract_forming_items(df, trace_transitions(df))
    forming_ids = [i.rule_id for i in items]
    if "F6-5a" in forming_ids and "F6-5c-b" in forming_ids:
        assert forming_ids.index("F6-5a") < forming_ids.index("F6-5c-b")


def test_gt_hit_snapshot_unchanged():
    """GT HIT 8건 스냅샷 불변 (표시 레이어 추가와 무관)."""
    df, _ = load_df_gt(SYMBOL, INTERVAL)
    zones = zone_ranges(df)
    found = set()
    for z in zones:
        _, events, _ = evaluate_transition_in_zone(df, z["buffer_pos"])
        for e in events:
            if e["mode"] != "HIT":
                continue
            found.add((
                z["id"],
                e["rule_id"],
                fmt_ts(e["form_ts"]),
                fmt_ts(e["comp_ts"]),
            ))
    assert found == EXPECTED_ZONE_HITS


def test_evaluate_transitions_unchanged_after_radar_helpers():
    """기존 evaluate_transitions hit 집합 무변동."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    before = {(h.rule_id, h.bar_index) for h in evaluate_transitions(df)}
    _ = build_transition_radar(df, trace_transitions(df))
    after = {(h.rule_id, h.bar_index) for h in evaluate_transitions(df)}
    assert before == after

    df2 = _struct_df("D3")
    _scenario_F6_5c_b(df2)
    keys = {(h.rule_id, h.formation_bar, h.bar_index) for h in evaluate_transitions(df2)}
    assert len(keys) == 1
