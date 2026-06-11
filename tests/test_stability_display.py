"""Stability Verdict 표시 레이어 테스트."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.verdict_stability import enrich_timeline_stability
from display.stability_verdict import (
    STABLE_COL,
    align_enriched_to_index,
    build_transition_log,
    count_transitions,
    duration_at,
    longest_spell,
    spell_summary,
)


def test_align_enriched_to_index():
    enriched = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="4h"),
        "family": ["BUY_FAMILY", "BUY_FAMILY", "NEUTRAL"],
        STABLE_COL: ["BUY_FAMILY", "BUY_FAMILY", "NEUTRAL"],
        "category": ["매수유효"] * 3,
    })
    idx = pd.date_range("2026-01-01", periods=4, freq="4h")
    aligned = align_enriched_to_index(enriched, idx)
    assert len(aligned) == 4
    assert pd.isna(aligned["family"].iloc[-1])


def test_spell_summary_and_transitions():
    seq = ["A", "A", "B", "B", "A"]
    assert count_transitions(seq) == 2
    st = spell_summary(seq)
    assert st["max"] == 2
    assert duration_at(seq, 3) == 2


def test_build_transition_log():
    ts = pd.date_range("2026-04-01", periods=5, freq="D")
    stable = ["NEUTRAL", "NEUTRAL", "BUY_FAMILY", "BUY_FAMILY", "NEUTRAL"]
    log = build_transition_log(ts.tolist(), stable)
    assert len(log) == 2
    assert log[0]["to_family"] == "NEUTRAL"


def test_longest_buy_spell():
    seq = ["NEUTRAL", "BUY_FAMILY", "BUY_FAMILY", "SELL_FAMILY"]
    assert longest_spell(seq, "BUY_FAMILY") == 2


def test_enrich_adds_family_columns():
    tl = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=6, freq="4h"),
        "category": [
            "매수유효", "매수유효", "매수계열기타", "매수유효", "매수유효", "매수유효",
        ],
        "verdict": ["v"] * 6,
    })
    out = enrich_timeline_stability(tl)
    assert "family" in out.columns
    assert STABLE_COL in out.columns
    assert out["family"].iloc[0] == "BUY_FAMILY"
