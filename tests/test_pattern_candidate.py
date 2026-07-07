"""candidate 2단계 노출 + 적시성(lead-bars) 회귀 테스트 (4차 위임 B).

확정 규칙:
- PatternEvent.stage 기본 = 'confirmed'. scan_dataframe은 confirmed만 방출(기존 동작 불변).
- candidate = 두 번째 극점 확정 + 넥라인 미돌파. 승격 불가(is_promotable stage 가드).
- lead_bars = confirm_pos − (두번째극점 pb + lookback). 넥라인 확정의 후행성 계측.

검출기 무수정: 아래는 합성 MA 시계열로 피봇 컬럼을 만들어 스캐너 candidate 로직만 검증한다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_promotion import is_promotable
from analysis.pattern_scanner import (
    STAGE_CANDIDATE,
    STAGE_CONFIRMED,
    PatternEvent,
    candidate_lead_bars,
    ma_first_pivot_pos,
    scan_ma_candidates,
)
from indicators.ma_patterns import add_ma_patterns


def _frame_from_ma5(ma5_values):
    """MA5 시계열을 직접 주입한 프레임 + add_ma_patterns 산출 피봇/확정 컬럼.

    add_ma_patterns는 MA{n} 컬럼을 소비하므로 MA5를 직접 세팅한다(검출기 무수정).
    """
    n = len(ma5_values)
    idx = pd.date_range("2020-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": ma5_values, "high": np.array(ma5_values) + 0.1,
        "low": np.array(ma5_values) - 0.1, "close": ma5_values, "volume": 1.0,
        "MA5": ma5_values,
    }, index=idx)
    return add_ma_patterns(df)


def _double_bottom_series(break_at_end: bool):
    """하락→저점1→반등(넥라인)→저점2→(돌파 or 미돌파) W 형태 MA5."""
    down = list(np.linspace(120, 100, 8))          # 하락 전제
    v1 = [100, 101, 103, 106, 108]                 # 저점1 후 반등(넥라인 ~108)
    mid = [108, 107]
    v2 = [104, 101, 100.5, 101, 103]               # 저점2 (저점1 부근)
    tail = [106, 109, 112] if break_at_end else [106, 107, 106.5]  # 돌파 vs 미돌파
    return down + v1 + mid + v2 + tail


def test_confirmed_stage_default():
    ev = PatternEvent(
        symbol="X", tf="1h", kind_pattern="double_bottom", ma_or_layer="MA5",
        direction="long", confirmed_bar=pd.Timestamp("2020-01-01"), neckline_price=1.0,
        kind="HL", source="ma", clean="clean", confirmed_pos=0, price_at_confirm=1.0,
        strength=1.0,
    )
    assert ev.stage == STAGE_CONFIRMED
    assert is_promotable(ev)   # confirmed + clean + ma double_bottom


def test_candidate_not_promotable():
    ev = PatternEvent(
        symbol="X", tf="1h", kind_pattern="double_bottom", ma_or_layer="MA5",
        direction="long", confirmed_bar=pd.Timestamp("2020-01-01"), neckline_price=1.0,
        kind="HL", source="ma", clean="indeterminate", confirmed_pos=0, price_at_confirm=1.0,
        strength=None, stage=STAGE_CANDIDATE,
    )
    assert not is_promotable(ev)   # candidate는 승격 불가


def test_candidate_emitted_when_neckline_not_broken():
    df = _frame_from_ma5(_double_bottom_series(break_at_end=False))
    cands = scan_ma_candidates(df, "X", "1h", periods=[5])
    assert len(cands) == 1
    c = cands[0]
    assert c.stage == STAGE_CANDIDATE
    assert c.kind_pattern == "double_bottom"
    assert c.strength is None
    assert c.neckline_price is not None


def test_candidate_absent_after_breakout_becomes_confirmed():
    # 넥라인 돌파가 일어나면 그 구조는 confirmed 영역 → candidate 아님.
    df = _frame_from_ma5(_double_bottom_series(break_at_end=True))
    cands = scan_ma_candidates(df, "X", "1h", periods=[5])
    # 돌파된 구조는 candidate로 방출되지 않는다(같은 구조가 confirmed로 이동).
    assert all(c.confirmed_pos is not None for c in cands)
    # 확정 이벤트에 대한 lead_bars가 계측된다.
    leads = candidate_lead_bars(df, "X", "1h", periods=[5])
    assert leads, "돌파 확정이 있으면 lead_bars가 산출돼야 함"
    for r in leads:
        assert r["lead_bars"] == r["confirm_pos"] - r["candidate_onset_pos"]


def test_ma_first_pivot_pos_anchor():
    # 5차 위임 앵커: 확정 봉의 첫 바닥 피봇 위치 = ma{p}_db_first_pos 값.
    df = _frame_from_ma5(_double_bottom_series(break_at_end=True))
    # 확정 봉(db non-NA) 찾기
    sig = df["ma5_db"]
    conf_pos = next(i for i in range(len(df)) if not pd.isna(sig.iloc[i]))
    fp = ma_first_pivot_pos(df, 5, "db", conf_pos)
    assert fp is not None and 0 <= fp < conf_pos   # 첫 바닥은 확정봉보다 앞
    assert fp == int(df["ma5_db_first_pos"].iloc[conf_pos])
    # 컬럼 없으면 None
    assert ma_first_pivot_pos(df, 999, "db", conf_pos) is None


if __name__ == "__main__":
    test_confirmed_stage_default()
    test_candidate_not_promotable()
    test_candidate_emitted_when_neckline_not_broken()
    test_candidate_absent_after_breakout_becomes_confirmed()
    test_ma_first_pivot_pos_anchor()
    print("ALL CANDIDATE TESTS PASSED")
