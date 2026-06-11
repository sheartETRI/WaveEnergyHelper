"""verdict_stability 관측 레이어 테스트."""
from analysis.verdict_stability import (
    enrich_timeline_stability,
    map_verdict_family,
    smooth_verdict,
)
from validation.verdict_categories import verdict_category


def test_smooth_verdict_single_spike():
    seq = ["A", "A", "B", "A", "A"]
    assert smooth_verdict(seq, 3) == ["A", "A", "A", "A", "A"]


def test_smooth_verdict_confirmed_run_kept():
    seq = ["A", "A", "B", "B", "B", "A"]
    assert smooth_verdict(seq, 3) == ["A", "A", "B", "B", "B", "A"]


def test_smooth_verdict_confirm_2():
    seq = ["A", "B", "B", "A"]
    assert smooth_verdict(seq, 2) == ["A", "B", "B", "A"]
    seq2 = ["A", "B", "A"]
    assert smooth_verdict(seq2, 2) == ["A", "A", "A"]


def test_map_verdict_family():
    assert map_verdict_family("매수유효") == "BUY_FAMILY"
    assert map_verdict_family("매수대기") == "BUY_FAMILY"
    assert map_verdict_family("매수계열기타") == "BUY_FAMILY"
    assert map_verdict_family("매도유효") == "SELL_FAMILY"
    assert map_verdict_family("매도대기") == "SELL_FAMILY"
    assert map_verdict_family("하락지속") == "SELL_FAMILY"
    assert map_verdict_family("관망/혼조") == "NEUTRAL"
    assert map_verdict_family("기술적반등") == "NEUTRAL"
    assert map_verdict_family("판단불가") == "NEUTRAL"


def test_enrich_does_not_mutate_category_column():
    import pandas as pd

    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="4h"),
        "category": ["매수유효", "매수유효", "매수계열기타", "매수유효", "매수유효"],
        "verdict": ["v"] * 5,
    })
    orig_cats = df["category"].tolist()
    enriched = enrich_timeline_stability(df)
    assert df["category"].tolist() == orig_cats
    assert "verdict_smoothed_3" in enriched.columns
    assert "family_smoothed_3" in enriched.columns
    assert enriched["family"].iloc[0] == "BUY_FAMILY"


def test_original_verdict_category_table_unchanged():
    v = "✅ 매수 관점 유효 (추세·대파동·타이밍 정렬)"
    assert verdict_category(v) == "매수유효"
