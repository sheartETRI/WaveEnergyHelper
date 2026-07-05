"""L2 승격 + 동시 확정 충돌 규칙 회귀 테스트 (§3).

시나리오 중심:
- 승격 게이트: clean 이평선 쌍바닥/쌍봉만 승격, candidate/스토캐/삼중 불가
- 동시 확정: 상위 TF 우선, 하위는 SUPPRESSED_BY_UPPER(기각 아님)
- 비동시(윈도 밖) 하위 확정은 억제되지 않음
- 반대 방향 상위 TF 충돌 감지

실행: `python -m pytest tests/test_campaign_promotion.py` 또는 직접 실행
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_promotion import (
    PROMOTED,
    SUPPRESSED_BY_UPPER,
    is_opposing_upper_conflict,
    is_promotable,
    resolve_promotions,
)
from analysis.pattern_scanner import PatternEvent


def _ev(symbol, tf, pattern, direction, bar, *, source="ma", layer="MA10",
        kind="HL", clean="clean"):
    return PatternEvent(
        symbol=symbol, tf=tf, kind_pattern=pattern, ma_or_layer=layer,
        direction=direction, confirmed_bar=pd.Timestamp(bar),
        neckline_price=100.0, kind=kind, source=source, clean=clean,
        confirmed_pos=0, price_at_confirm=100.0, strength=1.0,
    )


def test_promotion_gate_only_clean_ma_double():
    ma_clean = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-01")
    ma_dirty = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-01", clean="not-clean")
    stoch = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-01", source="stoch", layer="(5,3,3)")
    triple = _ev("BTCUSDT", "4h", "triple_bottom", "long", "2026-05-01", clean="n/a")
    assert is_promotable(ma_clean)
    assert not is_promotable(ma_dirty)
    assert not is_promotable(stoch)
    assert not is_promotable(triple)


def test_single_tf_promotes():
    evs = [_ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-01")]
    out = resolve_promotions(evs)
    assert len(out) == 1
    assert out[0].status == PROMOTED
    assert out[0].base_tf == "4h" and out[0].direction == "long"
    assert out[0].suppressed_by is None


def test_concurrent_upper_suppresses_lower():
    # 4h 쌍바닥(20:00)과 1d 쌍바닥(같은 날 00:00) 동시 → 1d 우선, 4h 억제
    lower = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-02 20:00")
    upper = _ev("BTCUSDT", "1d", "double_bottom", "long", "2026-05-02 00:00")
    out = {s.base_tf: s for s in resolve_promotions([lower, upper])}
    assert out["1d"].status == PROMOTED
    assert out["4h"].status == SUPPRESSED_BY_UPPER
    assert out["4h"].suppressed_by == "1d"


def test_non_concurrent_lower_not_suppressed():
    # 4h 확정이 1d 확정보다 3일 뒤 → 1d 1봉(24h) 윈도 밖 → 억제 안 됨
    upper = _ev("BTCUSDT", "1d", "double_bottom", "long", "2026-05-02 00:00")
    lower = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-05 20:00")
    out = {s.base_tf: s for s in resolve_promotions([lower, upper])}
    assert out["4h"].status == PROMOTED
    assert out["1d"].status == PROMOTED


def test_suppression_only_within_same_symbol():
    # 다른 심볼은 서로 억제하지 않는다
    a = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-02 20:00")
    b = _ev("ETHUSDT", "1d", "double_bottom", "long", "2026-05-02 00:00")
    out = {(s.symbol, s.base_tf): s for s in resolve_promotions([a, b])}
    assert out[("BTCUSDT", "4h")].status == PROMOTED
    assert out[("ETHUSDT", "1d")].status == PROMOTED


def test_opposing_direction_upper_still_suppresses_via_hierarchy():
    # [F1] 힘의 위계: 방향 무관하게 상위 TF 동시 확정이 하위를 억제
    lower = _ev("BTCUSDT", "4h", "double_bottom", "long", "2026-05-02 20:00")
    upper = _ev("BTCUSDT", "1d", "double_top", "short", "2026-05-02 00:00")
    out = {s.base_tf: s for s in resolve_promotions([lower, upper])}
    assert out["4h"].status == SUPPRESSED_BY_UPPER and out["4h"].suppressed_by == "1d"
    assert out["1d"].status == PROMOTED


def test_opposing_upper_conflict_detection():
    # 진행 중 4h 매수 캠페인 + 상위 1d 쌍봉 확정 → CONFLICT
    upper_top = _ev("BTCUSDT", "1d", "double_top", "short", "2026-05-10")
    assert is_opposing_upper_conflict("4h", "long", upper_top)
    # 같은 방향 상위 확정은 충돌 아님
    upper_bottom = _ev("BTCUSDT", "1d", "double_bottom", "long", "2026-05-10")
    assert not is_opposing_upper_conflict("4h", "long", upper_bottom)
    # 하위 TF 반대 확정은 상위 충돌 아님 (동일/하위는 상태 기계 소관)
    lower_top = _ev("BTCUSDT", "1h", "double_top", "short", "2026-05-10")
    assert not is_opposing_upper_conflict("4h", "long", lower_top)


if __name__ == "__main__":
    test_promotion_gate_only_clean_ma_double()
    test_single_tf_promotes()
    test_concurrent_upper_suppresses_lower()
    test_non_concurrent_lower_not_suppressed()
    test_suppression_only_within_same_symbol()
    test_opposing_direction_upper_still_suppresses_via_hierarchy()
    test_opposing_upper_conflict_detection()
    print("ALL CAMPAIGN PROMOTION TESTS PASSED")
