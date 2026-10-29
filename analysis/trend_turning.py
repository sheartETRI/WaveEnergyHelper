"""TP1: 4일봉 상승 추세 안의 하락 변곡 준비를 관측한다.

HT1의 MA10 방향을 바꾸지 않는다. MA10의 양의 1봉 기울기가 직전보다
작아지고 MA5와 MACD선이 각각 MA10과 시그널선 아래에 있으면 준비로
표시한다. 교차 사건의 시각과 현재 선의 위치는 별개이며 같은 봉에서
두 교차가 발생할 필요는 없다. 성공 확률이나 매매 신호를 정하지 않는다.

입력은 최종값을 확인한 연속 마감 4일봉이다. MACD는 기존 차트와 같은
설정과 adjust=False EMA를 사용한다. 관측 최소 길이는 slow+signal
(현재 26+9=35봉)이며, 이는 초기 EMA의 영향을 완전히 제거한다는 뜻은
아니다. 이전 마감이 35봉 미만인 구간의 MACD 교차 시각은 표시하지 않는다.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from config.settings import MACD_PARAMS


RULE_VERSION = "TP1"
_STEP = pd.Timedelta(days=4)


def _utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("invalid timestamp")
    offset = stamp.utcoffset()
    return stamp if offset is None else stamp.tz_localize(None) - offset


def _index(values) -> pd.DatetimeIndex:
    if not isinstance(values, pd.DatetimeIndex) or values.hasnans:
        raise ValueError("datetime index required")
    return pd.DatetimeIndex([_utc(value) for value in values])


def _relation(gap: float) -> str:
    return "above" if gap > 0 else "below" if gap < 0 else "equal"


def _last_cross(gaps: list[float], closes: pd.DatetimeIndex, first: int) -> Optional[dict]:
    for pos in range(len(gaps) - 1, max(first, 1) - 1, -1):
        previous, current = gaps[pos - 1], gaps[pos]
        if not math.isfinite(previous) or not math.isfinite(current):
            continue
        kind = "dead" if previous >= 0 and current < 0 else "golden" if previous <= 0 and current > 0 else None
        if kind:
            return {"kind": kind, "time": closes[pos], "bars_ago": len(gaps) - 1 - pos}
    return None


def _finish(result: dict, issue: str = "") -> dict:
    if issue:
        result.update(state="HOLD", issue=issue)
    result["snapshot"] = {
        key: result[key] for key in ("version", "state", "issue", "ma10_slowing", "ma_relation", "macd_relation", "macd_basis")
    }
    for key in ("ma_cross", "macd_cross"):
        cross = result[key]
        result["snapshot"][key] = None if cross is None else {"kind": cross["kind"], "time": str(cross["time"])}
    return result


def build_turning_context(frame: Optional[pd.DataFrame], primary: dict) -> dict:
    """검증된 HT1 주 기준과 같은 4d 마감 자료에서 별도 준비 상태를 만든다.

    energy_macd_seed가 있으면 첫 완성봉 직전 차트 부분봉의 종가 한 개를
    EMA 초기값으로만 사용한다. 최소 관측 봉수와 교차 검색에는 포함하지
    않는다. attrs가 없으면 완성 마감봉만으로 EMA를 초기화한다.
    """
    fast, slow, signal = (MACD_PARAMS[key] for key in ("fast", "slow", "signal"))
    minimum = max(12, slow + signal)
    result = {
        "version": RULE_VERSION, "state": "HOLD", "issue": "",
        "ma10_delta": None, "ma10_prev_delta": None, "ma10_slowing": None,
        "ma5_value": None, "ma10_value": None, "ma_relation": "unknown", "ma_cross": None,
        "macd_value": None, "signal_value": None, "macd_relation": "unknown", "macd_cross": None,
        "macd_basis": "closed_only", "minimum_bars": minimum,
        "last_close": primary.get("last_close"), "next_close": primary.get("next_close"),
        "snapshot": {},
    }
    if primary.get("issue"):
        return _finish(result, primary["issue"])
    if frame is None or frame.empty:
        return _finish(result, "NO_DATA")
    if frame.attrs.get("energy_issue"):
        return _finish(result, "UPSTREAM_ISSUE")
    if "close" not in frame:
        return _finish(result, "MISSING_CLOSE")
    try:
        index = _index(frame.index)
    except (TypeError, ValueError):
        return _finish(result, "INVALID_INDEX")
    if not index.is_unique or not index.is_monotonic_increasing:
        return _finish(result, "INVALID_INDEX")
    if len(index) > 1 and not (index[1:] - index[:-1] == _STEP).all():
        return _finish(result, "MISSING_BARS")
    try:
        closes = _index(frame.attrs.get("energy_bar_closes"))
    except (TypeError, ValueError):
        return _finish(result, "MISSING_CLOSE_METADATA")
    if len(closes) != len(frame) or not (closes == index + _STEP).all():
        return _finish(result, "INVALID_CLOSE_METADATA")
    try:
        if _utc(primary.get("last_close")) != closes[-1] or _utc(primary.get("next_close")) != closes[-1] + _STEP:
            return _finish(result, "PRIMARY_FRAME_MISMATCH")
    except (TypeError, ValueError):
        return _finish(result, "PRIMARY_FRAME_MISMATCH")
    result.update(last_close=closes[-1], next_close=closes[-1] + _STEP)
    numeric = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float, na_value=float("nan"))
    if not all(math.isfinite(value) for value in numeric):
        return _finish(result, "NONFINITE_CLOSE")

    values = [float(value) for value in numeric]
    seed = frame.attrs.get("energy_macd_seed")
    ema_values = values
    if seed is not None:
        try:
            seed_value = float(seed["close"])
            seed_time = _utc(seed["close_time"])
            if not math.isfinite(seed_value) or seed_time != closes[0] - _STEP:
                raise ValueError("invalid chart seed")
        except (KeyError, TypeError, ValueError, OverflowError):
            return _finish(result, "INVALID_MACD_SEED")
        ema_values = [seed_value] + values
        result["macd_basis"] = "chart_seed"
    if len(values) < minimum:
        return _finish(result, "INSUFFICIENT_BARS")

    now = (values[-1] - values[-11]) / 10
    previous = (values[-2] - values[-12]) / 10
    slowing = 0 < now < previous
    # MA5-MA10 = (최근 5봉 합 - 그 직전 5봉 합)/10.
    # 대응하는 종가의 차이를 합해 상수 소수의 반올림만으로 위/아래를 정하지 않는다.
    ma_gaps = [float("nan")] * 9 + [
        math.fsum(values[j] - values[j - 5] for j in range(pos - 4, pos + 1)) / 10
        for pos in range(9, len(values))
    ]
    ema_series = pd.Series(ema_values, dtype=float)
    macd = ema_series.ewm(span=fast, adjust=False).mean() - ema_series.ewm(span=slow, adjust=False).mean()
    sig = macd.ewm(span=signal, adjust=False).mean()
    gaps = (macd - sig).iloc[-len(values):].tolist()
    ma_relation, macd_relation = _relation(ma_gaps[-1]), _relation(gaps[-1])
    if now < 0:
        state = "MA10_DOWN"
    elif now > 0 and ma_relation == macd_relation == "below":
        state = "BEARISH_PREP" if slowing else "DOWNSIDE_EVIDENCE"
    elif slowing:
        state = "SLOWING"
    else:
        state = "NO_PREP"
    result.update(
        state=state, ma10_delta=now, ma10_prev_delta=previous, ma10_slowing=slowing,
        ma5_value=math.fsum(values[-5:]) / 5, ma10_value=math.fsum(values[-10:]) / 10,
        ma_relation=ma_relation, ma_cross=_last_cross(ma_gaps, closes, 10),
        macd_value=float(macd.iloc[-1]), signal_value=float(sig.iloc[-1]), macd_relation=macd_relation,
        macd_cross=_last_cross(gaps, closes, minimum),
    )
    return _finish(result)
