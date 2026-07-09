"""Wilder RSI(14) 연구 지표 테스트 (12차 위임 A)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.rsi_wilder import (
    OVERSOLD_THRESHOLD,
    WILDER_RSI_PERIOD,
    oversold_downcross,
    wilder_rsi,
)


def _series(vals):
    idx = pd.date_range("2020-01-01", periods=len(vals), freq="D")
    return pd.Series(np.asarray(vals, dtype=float), index=idx)


def test_period_constant_frozen():
    assert WILDER_RSI_PERIOD == 14
    assert OVERSOLD_THRESHOLD == 30.0


def test_parity_with_existing_rsi_raw():
    """유효 구간에서 기존 oscillators.add_rsi의 rsi_raw와 동일해야(같은 Wilder 계산).

    워밍업만 다르다(본 모듈 NaN vs rsi_raw 100). 유효(notna) 구간에서 비트-동일 확인.
    """
    from indicators.oscillators import add_rsi

    rng = np.random.default_rng(20260709)
    close = _series(100 + np.cumsum(rng.normal(0, 1.5, 400)))
    mine = wilder_rsi(close)

    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close})
    raw = add_rsi(df.copy())["rsi_raw"]

    mask = mine.notna()
    assert mask.sum() > 300                       # 유효 구간이 충분한지
    diff = (mine[mask] - raw[mask]).abs()
    assert float(diff.max()) < 1e-9, f"유효 구간 rsi_raw 대비 최대 오차 {diff.max()}"


def test_monotonic_extremes():
    """단조 상승 → RSI 100 근처, 단조 하락 → 0 근처."""
    up = wilder_rsi(_series(np.arange(1, 60, dtype=float)))
    assert up.iloc[-1] == 100.0  # 손실 0 → RSI 100
    down = wilder_rsi(_series(np.arange(60, 1, -1, dtype=float)))
    assert down.iloc[-1] < 1.0


def test_warmup_nan_then_valid():
    close = _series(100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 80)))
    rsi = wilder_rsi(close)
    # 워밍업 구간(첫 period봉)은 NaN(순수 Wilder — 오검출 방지), 이후 유효(0~100).
    assert rsi.iloc[:WILDER_RSI_PERIOD].isna().all()
    valid = rsi.iloc[WILDER_RSI_PERIOD:]
    assert valid.notna().all()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_no_spurious_warmup_boundary_cross():
    """워밍업이 NaN이므로 경계에서 인위적 100→저값 교차가 생기지 않는다."""
    # 초반부터 하락 → 워밍업 직후 첫 유효 RSI가 낮아도, prev=NaN이라 교차 False.
    close = _series(np.linspace(100, 60, 40))
    rsi = wilder_rsi(close)
    ev = oversold_downcross(rsi)
    first_valid = rsi.notna().idxmax()
    pos = rsi.index.get_loc(first_valid)
    assert bool(ev.iloc[pos]) is False           # 경계 봉은 prev NaN → 교차 아님


def test_oversold_downcross_entry_bar_only():
    """상→하 교차 봉만 True. 연속 과매도 유지 구간은 최초 진입만."""
    # RSI를 직접 흉내낸 시퀀스로 교차 로직만 검증.
    rsi = _series([40, 35, 31, 29, 25, 28, 33, 29])  # 30을 idx3에서 하향 교차, idx7 재교차
    ev = oversold_downcross(rsi, 30.0)
    assert bool(ev.iloc[3]) is True          # 31 → 29 최초 진입
    assert bool(ev.iloc[4]) is False         # 29 → 25 연속 과매도(중복 아님)
    assert bool(ev.iloc[7]) is True          # 33 → 29 재진입
    assert bool(ev.iloc[0]) is False         # 첫 봉 직전값 없음
    assert int(ev.sum()) == 2


if __name__ == "__main__":
    test_period_constant_frozen()
    test_parity_with_existing_rsi_raw()
    test_monotonic_extremes()
    test_warmup_nan_then_valid()
    test_oversold_downcross_entry_bar_only()
    print("ALL WILDER RSI TESTS PASSED")
