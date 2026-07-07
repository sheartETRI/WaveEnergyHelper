"""캔들 쌍바닥/쌍봉 검출기 (v2, 4차 위임 E-1) — 관측·표시·저널 전용.

확정 정의(김박사 확정):
- 쌍바닥 = **정확히 연속 4봉** 음→양→음→양. HL 필수: 3번봉(두 번째 음봉) low ≥ 1번봉 low.
  확정 봉 = 4번봉 마감. 넥라인 = 두 바닥 사이 반등 고점(2번봉 high, 표시용).
- 쌍봉 = 대칭 양→음→양→음. LH 필수: 3번봉 high ≤ 1번봉 high. 확정 봉 = 4번봉.
- 도지(시가=종가): 교대 파괴로 간주(보수적, config `DOJI_BREAKS_ALTERNATION`로 노출).
- 연속 4봉 엄격 정의 → 정밀도 높고 재현율 낮음(의도됨). 하급(타이밍) 신호.

★ 캔들 패턴은 **캠페인 승격(L2) 소스가 아니다** — is_promotable이 source=="ma"만 허용하므로
  source="candle" 이벤트는 자동으로 승격 대상에서 제외된다. 여기서도 스캔 진입점(scan_dataframe)에
  포함하지 않는다(백테스트 동작 불변). 별도 조회 전용.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from analysis.pattern_scanner import STAGE_CONFIRMED, PatternEvent
from config.settings import CANDLE_PATTERN_PARAMS

CANDLE_LAYER = "candle"
_LONG = "long"
_SHORT = "short"

_BULL = "bull"
_BEAR = "bear"
_DOJI = "doji"


def _bar_color(open_v: float, close_v: float) -> str:
    if pd.isna(open_v) or pd.isna(close_v):
        return _DOJI  # 결측은 교대 파괴로 취급(보수적)
    if close_v > open_v:
        return _BULL
    if close_v < open_v:
        return _BEAR
    return _DOJI


def scan_candle_patterns(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    *,
    doji_breaks: Optional[bool] = None,
) -> List[PatternEvent]:
    """OHLC에서 정확히 4봉 음양음양(쌍바닥)/양음양음(쌍봉) 패턴 → PatternEvent(source=candle)."""
    if full_df is None or len(full_df) < 4:
        return []
    need = {"open", "high", "low", "close"}
    if not need.issubset(full_df.columns):
        return []
    db = CANDLE_PATTERN_PARAMS["DOJI_BREAKS_ALTERNATION"] if doji_breaks is None else doji_breaks

    o = full_df["open"].to_numpy(dtype="float64")
    h = full_df["high"].to_numpy(dtype="float64")
    lo = full_df["low"].to_numpy(dtype="float64")
    c = full_df["close"].to_numpy(dtype="float64")
    idx = full_df.index
    n = len(full_df)
    events: List[PatternEvent] = []

    colors = [_bar_color(o[i], c[i]) for i in range(n)]

    for i in range(n - 3):
        b1, b2, b3, b4 = i, i + 1, i + 2, i + 3
        seq = colors[b1:b4 + 1]
        # 도지가 하나라도 있으면(보수적) 교대 파괴 → 패턴 아님.
        if db and _DOJI in seq:
            continue

        # 쌍바닥: 음→양→음→양 + HL(3번봉 low ≥ 1번봉 low)
        if seq == [_BEAR, _BULL, _BEAR, _BULL] and lo[b3] >= lo[b1]:
            events.append(_mk(symbol, tf, "double_bottom", _LONG, "HL",
                              ts=idx[b4], neckline=float(h[b2]), pos=b4, price=float(c[b4])))
            continue

        # 쌍봉: 양→음→양→음 + LH(3번봉 high ≤ 1번봉 high)
        if seq == [_BULL, _BEAR, _BULL, _BEAR] and h[b3] <= h[b1]:
            events.append(_mk(symbol, tf, "double_top", _SHORT, "LH",
                              ts=idx[b4], neckline=float(lo[b2]), pos=b4, price=float(c[b4])))

    return events


def _mk(symbol, tf, kind_pattern, direction, kind, *, ts, neckline, pos, price) -> PatternEvent:
    return PatternEvent(
        symbol=symbol, tf=tf, kind_pattern=kind_pattern, ma_or_layer=CANDLE_LAYER,
        direction=direction, confirmed_bar=pd.Timestamp(ts), neckline_price=neckline,
        kind=kind, source="candle", clean="n/a", confirmed_pos=int(pos),
        price_at_confirm=price, strength=None, stage=STAGE_CONFIRMED,
    )


def candle_distribution(full_df: pd.DataFrame, symbol: str, tf: str) -> dict:
    """TF별 캔들 패턴 검출 분포(리포트용): {db, dt, total}."""
    evs = scan_candle_patterns(full_df, symbol, tf)
    db = sum(1 for e in evs if e.direction == _LONG)
    dt = sum(1 for e in evs if e.direction == _SHORT)
    return {"db": db, "dt": dt, "total": len(evs)}
