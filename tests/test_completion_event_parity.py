"""enumerate_completion_events 대표 짝 ↔ 엔진 HIT parity (Z2 F6-5c-b 회귀).

실행: python -m pytest tests/test_completion_event_parity.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    parse_transition_row,
    classify_structure_at,
    pair_formation_completion,
)
from validation.gt_trace import (
    load_df_gt,
    zone_ranges,
    z2_window_structure_cross,
    SYMBOL,
    INTERVAL,
)
from validation.sweep import atom_confirm_positions, enumerate_completion_events


def _engine_hit_pairs(df, buf, structure, atoms, window):
    a_pos = atom_confirm_positions(df, atoms[0])
    b_pos = atom_confirm_positions(df, atoms[1])
    hits = []
    for i in a_pos:
        for j in b_pos:
            if abs(i - j) > window - 1:
                continue
            form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
            if comp_pos not in buf:
                continue
            if classify_structure_at(df, form_pos) == structure:
                hits.append({"comp": comp_pos, "form": form_pos, "i": i, "j": j})
    return hits


def test_z2_f6_5cb_cross_matches_engine_hits():
    """4c w=96 form_is_d3 건수·formation ↔ B-path HIT 2건 일치."""
    df, _ = load_df_gt(SYMBOL, INTERVAL)
    zones = zone_ranges(df)
    z2 = next(z for z in zones if z["id"] == "Z2")
    buf = z2["buffer_pos"]

    row = next(r for r in TRANSITION_RULE_TABLE if parse_transition_row(r)[2] == "F6-5c-b")
    structure, atoms, _, _, window = parse_transition_row(row)

    hits = _engine_hit_pairs(df, buf, structure, atoms, window)
    assert len(hits) == 2

    ev = enumerate_completion_events(
        atom_confirm_positions(df, atoms[0]),
        atom_confirm_positions(df, atoms[1]),
        recent=window, df=df, atoms=atoms, structure=structure,
    )
    for h in hits:
        assert h["comp"] in ev
        early, comp = ev[h["comp"]]
        assert early == min(h["i"], h["j"])
        fp, _, _ = pair_formation_completion(df, atoms, h["i"], h["j"])
        assert fp == h["form"]
        assert classify_structure_at(df, fp) == structure

    cross = z2_window_structure_cross(df, z2["buffer_pos"])
    w96_rows = cross["per_rule"]["F6-5c-b"]["windows"][96]["events"]
    form_d3 = [r for r in w96_rows if r["form_is_d3"]]
    assert len(form_d3) == 2
    assert cross["w96_form_d3_by_rule"]["F6-5c-b"] == 2
    assert {r["comp_pos"] for r in form_d3} == {h["comp"] for h in hits}
