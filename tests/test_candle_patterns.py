"""캔들 쌍바닥/쌍봉 검출기 회귀 테스트 (4차 위임 E-1).

확정 규칙:
- 쌍바닥 = 정확히 4봉 음→양→음→양 + HL(3번봉 low ≥ 1번봉 low). 확정=4번봉.
- 쌍봉 = 양→음→양→음 + LH(3번봉 high ≤ 1번봉 high).
- 도지(시가=종가)는 교대 파괴(DOJI_BREAKS_ALTERNATION=True) → 패턴 무효.
- source="candle" → is_promotable False (승격 소스 아님).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_promotion import is_promotable
from analysis.candle_patterns import scan_candle_patterns


def _df(bars):
    """bars: list of (open, high, low, close)."""
    idx = pd.date_range("2020-01-01", periods=len(bars), freq="1h")
    return pd.DataFrame(
        {"open": [b[0] for b in bars], "high": [b[1] for b in bars],
         "low": [b[2] for b in bars], "close": [b[3] for b in bars], "volume": 1.0},
        index=idx,
    )


def test_candle_double_bottom_hl():
    # 음(10→9), 양(9→11), 음(10.5→9.5 low=9.2 ≥ 첫 저점 9.0), 양(9.5→12) → 쌍바닥 HL
    bars = [
        (10, 10.2, 9.0, 9.0),     # b1 음, low 9.0
        (9.0, 11.2, 8.9, 11.0),   # b2 양 (넥라인 high 11.2)
        (10.5, 10.6, 9.2, 9.5),   # b3 음, low 9.2 ≥ 9.0 (HL)
        (9.5, 12.0, 9.4, 12.0),   # b4 양 확정
    ]
    evs = scan_candle_patterns(_df(bars), "X", "1h")
    assert len(evs) == 1
    e = evs[0]
    assert e.kind_pattern == "double_bottom" and e.direction == "long" and e.kind == "HL"
    assert e.source == "candle" and e.confirmed_pos == 3
    assert e.neckline_price == 11.2   # 2번봉 high
    assert not is_promotable(e)        # 캔들은 승격 소스 아님


def test_candle_double_bottom_rejected_when_lower_low():
    # 3번봉 low(8.5) < 1번봉 low(9.0) → HL 위반 → 패턴 아님
    bars = [
        (10, 10.2, 9.0, 9.0),
        (9.0, 11.2, 8.9, 11.0),
        (10.5, 10.6, 8.5, 9.5),   # low 8.5 < 9.0
        (9.5, 12.0, 9.4, 12.0),
    ]
    assert scan_candle_patterns(_df(bars), "X", "1h") == []


def test_candle_double_top_lh():
    # 양,음,양(high ≤ 첫 고점),음 → 쌍봉 LH
    bars = [
        (9.0, 12.0, 8.9, 11.5),   # b1 양, high 12.0
        (11.5, 11.6, 9.0, 9.2),   # b2 음 (넥라인 low 9.0)
        (9.2, 11.8, 9.1, 11.0),   # b3 양, high 11.8 ≤ 12.0 (LH)
        (11.0, 11.2, 8.5, 8.8),   # b4 음 확정
    ]
    evs = scan_candle_patterns(_df(bars), "X", "1h")
    assert len(evs) == 1
    e = evs[0]
    assert e.kind_pattern == "double_top" and e.direction == "short" and e.kind == "LH"
    assert e.neckline_price == 9.0    # 2번봉 low


def test_doji_breaks_pattern():
    # 2번봉이 도지(open==close) → 교대 파괴 → 패턴 무효
    bars = [
        (10, 10.2, 9.0, 9.0),
        (9.0, 11.2, 8.9, 9.0),    # 도지 (open==close==9.0)
        (10.5, 10.6, 9.2, 9.5),
        (9.5, 12.0, 9.4, 12.0),
    ]
    assert scan_candle_patterns(_df(bars), "X", "1h") == []
    # 도지 완화(doji_breaks=False)면 색이 doji라 여전히 음양음양 시퀀스 불성립 → 무효(안전)
    assert scan_candle_patterns(_df(bars), "X", "1h", doji_breaks=False) == []


if __name__ == "__main__":
    test_candle_double_bottom_hl()
    test_candle_double_bottom_rejected_when_lower_low()
    test_candle_double_top_lh()
    test_doji_breaks_pattern()
    print("ALL CANDLE TESTS PASSED")
