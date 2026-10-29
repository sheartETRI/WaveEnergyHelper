"""HT1: 4d MA10을 우선 보고 일봉 MA60으로 전체 추세를 교차 확인한다.

이 모듈은 사용자가 정한 해석 정책이다. 방향의 성공 확률이나 매매 조건을
정하지 않는다. 입력은 같은 판단 시점에 최종값을 확인한 마감 프레임이며,
시각은 naive UTC로 취급한다. aware 입력도 같은 UTC 순간으로 정규화한다.
MA 방향은 각 TF의 직전 봉 대비 1봉 변화이며 기존 추세 정의를 바꾸지 않는다.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd


RULE_VERSION = "HT1"
_DAY = pd.Timedelta(days=1)
_PRIMARY_MINUTES = 4 * 1440
_PRIMARY_SPAN = _PRIMARY_MINUTES * 10
_UNITS = {"m": 1, "h": 60, "d": 1440, "w": 10080, "M": 43200}


def _utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("invalid timestamp")
    offset = stamp.utcoffset()
    return stamp if offset is None else stamp.tz_localize(None) - offset


def _index(values) -> pd.DatetimeIndex:
    if not isinstance(values, pd.DatetimeIndex):
        raise ValueError("datetime index required")
    if values.hasnans:
        raise ValueError("invalid datetime index")
    return pd.DatetimeIndex([_utc(value) for value in values])


def _observation(frame: Optional[pd.DataFrame], interval: str, period: int, asof: pd.Timestamp) -> dict:
    step = _DAY * (4 if interval == "4d" else 1)
    result = {
        "interval": interval, "period": period, "direction": "unknown",
        "ma_value": None, "ma_delta": None, "close_price": None,
        "price_position": "unknown", "last_close": None, "next_close": None,
        "issue": "NO_DATA", "issue_detail": "", "chart_label": None, "grid_origin": None,
    }
    if frame is None:
        return result
    origin = frame.attrs.get("energy_origin")
    if origin is not None:
        try:
            result["grid_origin"] = _utc(origin)
        except (TypeError, ValueError):
            result["issue"] = "INVALID_GRID_ORIGIN"
            return result
    upstream = frame.attrs.get("energy_issue", "")
    if upstream:
        result.update(issue="UPSTREAM_ISSUE", issue_detail=str(upstream))
        return result
    if frame.empty:
        return result
    if "close" not in frame:
        result["issue"] = "MISSING_CLOSE"
        return result
    try:
        index = _index(frame.index)
    except (TypeError, ValueError):
        result["issue"] = "INVALID_INDEX"
        return result
    if not index.is_monotonic_increasing or not index.is_unique:
        result["issue"] = "INVALID_INDEX"
        return result
    try:
        closes = _index(frame.attrs.get("energy_bar_closes"))
    except (TypeError, ValueError):
        result["issue"] = "MISSING_CLOSE_METADATA"
        return result
    if len(closes) != len(frame) or not closes.is_unique or not closes.is_monotonic_increasing:
        result["issue"] = "INVALID_CLOSE_METADATA"
        return result
    if not (closes == index + step).all():
        result["issue"] = "INVALID_CLOSE_METADATA"
        return result
    result.update(last_close=closes[-1], next_close=closes[-1] + step)
    labels = frame.attrs.get("energy_chart_labels")
    if labels is not None:
        try:
            labels = _index(labels)
            if len(labels) != len(frame):
                raise ValueError("unaligned labels")
            result["chart_label"] = labels[-1]
        except (TypeError, ValueError):
            result["issue"] = "INVALID_CHART_LABELS"
            return result
    if closes[-1] > asof:
        result["issue"] = "UNCONFIRMED_BAR"
        return result
    if result["next_close"] <= asof:
        result["issue"] = "STALE"
        return result
    if len(frame) < period + 1:
        result["issue"] = "INSUFFICIENT_BARS"
        return result
    if not (index[-period:] - index[-period-1:-1] == step).all():
        result["issue"] = "MISSING_BARS"
        return result
    values = pd.to_numeric(frame["close"].iloc[-period-1:], errors="coerce")
    numeric = values.to_numpy(dtype=float, na_value=float("nan"))
    if not all(math.isfinite(value) for value in numeric):
        result["issue"] = "NONFINITE_CLOSE"
        return result
    current, previous = float(numeric[-1]), float(numeric[0])
    mean = math.fsum(float(value) for value in numeric[1:]) / period
    # 종가가 모두 같을 때 누적 오차만으로 MA 위/아래가 되지 않도록 차이를 합한다.
    distance = math.fsum(current - float(value) for value in numeric[1:])
    delta = (current - previous) / period
    result.update(
        direction="up" if current > previous else "down" if current < previous else "flat",
        ma_value=mean, ma_delta=delta, close_price=current,
        price_position="above" if distance > 0 else "below" if distance < 0 else "equal",
        issue="",
    )
    return result


def build_trend_context(frames: dict, asof) -> dict:
    """동일 asof의 서로 다른 두 마감 기준을 읽는다. 다른 갱신 주기를 허용한다."""
    try:
        at = _utc(asof)
    except (TypeError, ValueError):
        raise ValueError("asof must be a valid UTC instant") from None
    primary = _observation(frames.get("4d"), "4d", 10, at)
    reference = _observation(frames.get("1d"), "1d", 60, at)
    valid_primary, valid_reference = not primary["issue"], not reference["issue"]
    direction = "unknown"
    if valid_primary and valid_reference:
        if "flat" in (primary["direction"], reference["direction"]):
            status = "FLAT"
        elif primary["direction"] == reference["direction"]:
            status, direction = "ALIGNED", primary["direction"]
        else:
            status = "CONFLICT"
    elif valid_primary or valid_reference:
        status = "PARTIAL"
    else:
        status = "UNAVAILABLE"
    # 유효 시각이 과거여도 남긴다. 표시 계층이 즉시 재조회 필요를 알 수 있다.
    checks = [item["next_close"] for item in (primary, reference) if item["next_close"] is not None]
    snapshot = {
        "primary_direction": primary["direction"], "reference_direction": reference["direction"],
        "status": status, "primary_issue": primary["issue"], "reference_issue": reference["issue"],
        "grid_origin": str(primary["grid_origin"]) if primary["grid_origin"] is not None else "",
    }
    return {"version": RULE_VERSION, "primary": primary, "reference": reference,
            "status": status, "direction": direction,
            "next_check_at": min(checks) if checks else None, "snapshot": snapshot}


def _minutes(interval: str) -> Optional[int]:
    if not isinstance(interval, str) or len(interval) < 2 or interval[-1] not in _UNITS:
        return None
    try:
        number = int(interval[:-1])
    except ValueError:
        return None
    return number * _UNITS[interval[-1]] if number > 0 else None


def classify_trend_move(interval: str, local_direction: str, context: dict, period: int = 10) -> dict:
    """짧은 관측 범위의 움직임만 상위 기준의 순행/반등/조정으로 분류한다."""
    result = {"code": "HOLD", "interval": interval, "period": period,
              "local_direction": local_direction, "trend_direction": context.get("direction", "unknown"),
              "context_status": context.get("status", "UNAVAILABLE"), "reason_code": "INVALID_LOCAL_INPUT"}
    minutes = _minutes(interval)
    if minutes is None or not isinstance(period, int) or period <= 0:
        return result
    if minutes >= _PRIMARY_MINUTES or minutes * period >= _PRIMARY_SPAN:
        result.update(code="REFERENCE_OR_HIGHER", reason_code="NOT_A_SMALLER_OBSERVATION")
        return result
    if context.get("status") == "CONFLICT":
        result.update(code="CONFLICT", reason_code="REFERENCE_DIRECTIONS_CONFLICT")
        return result
    if context.get("status") != "ALIGNED" or local_direction not in ("up", "down"):
        result["reason_code"] = "DIRECTION_NOT_CONFIRMED"
        return result
    trend = context.get("direction")
    if trend not in ("up", "down"):
        result["reason_code"] = "DIRECTION_NOT_CONFIRMED"
        return result
    code = "WITH_TREND" if local_direction == trend else "COUNTER_RALLY" if trend == "down" else "COUNTER_PULLBACK"
    result.update(code=code, reason_code="OBSERVED_DIRECTION_RELATION")
    return result
