"""변곡 hit 이격도 유형 주석(응축형/과이격형) 테스트.

실행: python -m pytest tests/test_dispersion_annotation.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.ma_dispersion import (
    classify_dispersion_type,
    dispersion_percentile_rank,
)
from analysis.dynamics_rules import evaluate_transitions, trace_transitions
from validation.gt_trace import (
    load_df_gt,
    zone_ranges,
    evaluate_transition_in_zone,
    fmt_ts,
    SYMBOL,
    INTERVAL,
)
from tests.test_transition_rules import _struct_df, _scenario_F6_4a, IDX

# GT 정답 구간 HIT 스냅샷 (주석 도입 전후 동일해야 함)
EXPECTED_ZONE_HITS = {
    ("Z1", "F6-4a", "2026-01-03 00:00", "2026-01-19 04:00"),
    ("Z1", "F6-4a", "2026-01-03 00:00", "2026-01-19 12:00"),
    ("Z1", "F6-5b", "2026-01-30 00:00", "2026-02-02 16:00"),
    ("Z2", "F6-5c-b", "2026-02-06 00:00", "2026-02-26 08:00"),
    ("Z2", "F6-5c-b", "2026-02-06 00:00", "2026-02-26 12:00"),
    ("Z3", "F6-5a", "2026-04-29 20:00", "2026-05-10 20:00"),
    ("Z3", "F6-5a", "2026-04-29 20:00", "2026-05-13 08:00"),
    ("Z3", "F6-5a", "2026-04-29 20:00", "2026-05-14 16:00"),
}


def _dispersion_df(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"ma_dispersion": values}, index=idx)


def test_classify_compress_stretch_middle():
    """저/고/중간 백분위 → 응축형/과이격형/중간."""
    df = _dispersion_df(np.linspace(0.01, 0.10, 20))
    low_pct = dispersion_percentile_rank(df, 0)
    mid_pct = dispersion_percentile_rank(df, 9)
    high_pct = dispersion_percentile_rank(df, 19)

    assert low_pct == 5.0
    assert classify_dispersion_type(low_pct) == "응축형"

    assert high_pct == 100.0
    assert classify_dispersion_type(high_pct) == "과이격형"

    assert mid_pct == 50.0
    assert classify_dispersion_type(mid_pct) == "중간"


def test_percentile_rank_manual():
    """수작업 rank 백분위와 일치."""
    df = _dispersion_df([1.0, 2.0, 3.0, 4.0, 5.0])
    assert dispersion_percentile_rank(df, 0) == 20.0
    assert dispersion_percentile_rank(df, 2) == 60.0
    assert dispersion_percentile_rank(df, 4) == 100.0


def test_zone_hit_set_unchanged_with_annotation():
    """무게이트 회귀: GT 정답 구간 HIT 8건(Z2 F6-5c-b 2건) 집합 불변."""
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
    assert sum(1 for t in found if t[1] == "F6-5c-b") == 2


def test_hit_keys_unchanged_with_ma_dispersion_column():
    """ma_dispersion 유무와 무관하게 evaluate_transitions hit 집합 동일."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    keys_plain = {(h.rule_id, h.formation_bar, h.bar_index) for h in evaluate_transitions(df)}

    df2 = df.copy()
    df2["ma_dispersion"] = np.linspace(0.01, 0.05, len(df2))
    keys_with = {(h.rule_id, h.formation_bar, h.bar_index) for h in evaluate_transitions(df2)}

    assert keys_plain == keys_with
    assert len(keys_plain) == 1
    hit = next(h for h in evaluate_transitions(df2) if h.rule_id == "F6-4a")
    assert hit.dispersion_type in ("응축형", "과이격형", "중간")
    assert hit.dispersion_pct is not None


def test_trace_hit_records_dispersion_pct():
    """trace_transitions HIT 행에 pct·type 기록."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    df["ma_dispersion"] = 0.02
    tr = next(t for t in trace_transitions(df) if t.rule_id == "F6-4a")
    assert tr.result == "HIT"
    assert tr.dispersion_pct is not None
    assert tr.dispersion_type is not None


def test_nan_formation_dispersion_none():
    """형성 봉 dispersion NaN → pct/type None, 예외 없음."""
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    # 워밍업 구간: ma_dispersion 전부 NaN
    df["ma_dispersion"] = pd.NA
    hits = evaluate_transitions(df)
    hit = next(h for h in hits if h.rule_id == "F6-4a")
    assert hit.dispersion_pct is None
    assert hit.dispersion_type is None
