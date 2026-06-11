"""as-of verdict 백트레이스·룩어헤드 회귀 테스트.

실행: python -m pytest tests/test_verdict_asof.py
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.asof import (
    analyze_wave_energy_asof,
    build_ohlcv_cache,
    fetch_ohlcv_bare,
    parse_as_of,
    truncate_to_asof,
)
from validation.verdict_categories import verdict_category
from validation.verdict_sweep import sweep_symbol_interval, state_transitions


def test_sweep_bar_matches_isolated_asof_recompute():
    """임의 봉 t: 스윕 행 == t 절단 단독 재계산 (lookahead 스팟 체크)."""
    symbol, interval, lim = "ETHUSDT", "4h", 400
    bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=False)
    if bare is None or len(bare) < 50:
        pytest.skip("network/data unavailable")
    cache = build_ohlcv_cache(symbol, interval, bare, extra_limits={"4h": lim})

    timeline = sweep_symbol_interval(symbol, interval, cache, bare, stride=10)
    assert not timeline.empty

    row = timeline.iloc[len(timeline) // 2]
    ts = pd.Timestamp(row["timestamp"])
    isolated = analyze_wave_energy_asof(symbol, interval, ts, cache)
    assert isolated.verdict == row["verdict"]
    assert verdict_category(isolated.verdict) == row["category"]


def test_truncate_to_asof_no_future_bars():
    idx = pd.date_range("2024-01-01", periods=10, freq="4h")
    df = pd.DataFrame({"close": range(10)}, index=idx)
    cut = truncate_to_asof(df, idx[5])
    assert len(cut) == 6
    assert cut.index[-1] == idx[5]


def test_parse_as_of_empty():
    assert parse_as_of("") is None
    assert parse_as_of("  ") is None
    ts = parse_as_of("2026-01-15 12:00")
    assert ts is not None


def test_verdict_category_mapping_exact():
    from validation.verdict_categories import VERDICT_CATEGORY_TABLE

    for verdict, cat in VERDICT_CATEGORY_TABLE:
        assert verdict_category(verdict) == cat


def test_state_transitions_detects_change():
    tl = pd.DataFrame([
        {"timestamp": pd.Timestamp("2024-01-01"), "category": "관망/혼조", "verdict": "a"},
        {"timestamp": pd.Timestamp("2024-01-02"), "category": "관망/혼조", "verdict": "a"},
        {"timestamp": pd.Timestamp("2024-01-03"), "category": "매수대기", "verdict": "b"},
    ])
    trans = state_transitions(tl)
    assert len(trans) == 1
    assert trans.iloc[0]["to_category"] == "매수대기"
