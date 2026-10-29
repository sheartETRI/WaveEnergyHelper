"""파동 에너지 관측용 마감 프레임. 4d는 기존 차트 그리드의 완성 일봉만 묶는다.

원본 수신은 호출자가 담당한다. 4d 차트와 같은 창을 비교하려면 그 차트와
같은 조회량의 1d 원본을 전달해야 한다. 기존 리샘플러나 지표 정의는 바꾸지 않는다.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from display.mtf_guidance import prepare_closed_frames
from display.mtf_guidance_model import _step


_DAY = pd.Timedelta(days=1)
_OHLC = ("open", "high", "low", "close")
_BASIS_4D = (
    "기존 4d 차트와 같은 일봉 조회창 시작 기준의 오른쪽 경계 그룹. "
    "연속 일봉 4개로 완성된 그룹만 사용하며 첫·끝 부분봉은 제외합니다. "
    "관측 인덱스는 실제 시작 시각이고 차트 라벨은 별도 보존합니다."
)


def _utc_naive(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp if stamp.tzinfo is None else stamp.tz_convert("UTC").tz_localize(None)


def _utc_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.copy() if index.tz is None else index.tz_convert("UTC").tz_localize(None)


def _normalise(raw: Optional[pd.DataFrame]) -> tuple[pd.DataFrame, str]:
    if raw is None or raw.empty:
        return pd.DataFrame(), "원본 봉 데이터 없음"
    if not isinstance(raw.index, pd.DatetimeIndex) or raw.index.hasnans:
        return pd.DataFrame(), "유효한 봉 시각 필요"
    if not raw.index.is_monotonic_increasing or not raw.index.is_unique:
        return pd.DataFrame(), "봉 시각 정렬·중복 확인 필요"
    if not set(_OHLC).issubset(raw.columns):
        return pd.DataFrame(), "OHLC 자료 부족"
    columns = [col for col in (*_OHLC, "volume") if col in raw]
    frame = raw.loc[:, columns].copy()
    frame.index = _utc_index(frame.index)
    frame.attrs = {}
    return frame, ""


def _finite_ohlc(frame: pd.DataFrame) -> bool:
    values = frame.loc[:, _OHLC].apply(pd.to_numeric, errors="coerce")
    return all(math.isfinite(value) for value in values.to_numpy(dtype=float, na_value=float("nan")).flat)


def _metadata(frame: pd.DataFrame, closes, labels, basis: str, issue: str = "") -> pd.DataFrame:
    frame.attrs.update({
        "energy_bar_closes": pd.DatetimeIndex(closes),
        "energy_chart_labels": pd.DatetimeIndex(labels),
        "energy_basis": basis,
        "energy_issue": issue,
    })
    return frame


def _hold(reason: str, basis: str = "") -> pd.DataFrame:
    return _metadata(pd.DataFrame(columns=[*_OHLC, "volume"]), [], [], basis, reason)


def _four_day_frame(raw: Optional[pd.DataFrame], asof) -> pd.DataFrame:
    daily, issue = _normalise(raw)
    if issue:
        return _hold(issue, _BASIS_4D)
    origin = daily.index[0]
    # 시계가 마감을 지나도 수신 당시의 마지막 값은 미완성일 수 있다.
    daily = daily.iloc[:-1]
    daily = daily.loc[daily.index + _DAY <= _utc_naive(asof)]
    if daily.empty:
        return _hold("최종값을 확인한 마감 일봉 없음", _BASIS_4D)
    if len(daily) > 1 and not (daily.index[1:] - daily.index[:-1] == _DAY).all():
        return _hold("일봉 누락·간격 불일치: 4d 연속 관측 보류", _BASIS_4D)
    if not _finite_ohlc(daily):
        return _hold("일봉 OHLC 결측·비정상 값: 4d 관측 보류", _BASIS_4D)

    rows, starts, closes, labels = [], [], [], []
    grouped = daily.resample("4D", label="right", closed="right", origin=origin)
    for label, group in grouped:
        expected = pd.date_range(label - 3 * _DAY, periods=4, freq="1D")
        if len(group) != 4 or not group.index.equals(expected):
            continue
        rows.append({"open": group["open"].iloc[0], "high": group["high"].max(),
                     "low": group["low"].min(), "close": group["close"].iloc[-1],
                     "volume": group["volume"].sum() if "volume" in group else 0.0})
        starts.append(group.index[0])
        closes.append(group.index[-1] + _DAY)
        labels.append(label)
    if not rows:
        return _hold("연속 일봉 4개로 완성된 4d 봉 없음", _BASIS_4D)

    from indicators.moving_averages import add_moving_averages
    from indicators.stochastic import add_stochastic_slow_layers

    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(starts, name=raw.index.name))
    frame = add_stochastic_slow_layers(add_moving_averages(frame))
    frame = _metadata(frame, closes, labels, _BASIS_4D)
    frame.attrs["energy_origin"] = origin
    return frame


def prepare_energy_frames(raw_frames: dict[str, Optional[pd.DataFrame]], asof) -> dict[str, pd.DataFrame]:
    """수신된 원본만 사용해 native와 4d 에너지 관측 프레임을 만든다.

    모든 결과의 인덱스·메타 시각은 naive UTC다. 빈 프레임의 energy_issue는
    단순 무신호와 자료 보류를 구분한다. 중간 누락 봉을 삭제한 채 압축해
    지표를 이어 계산하지 않으며, 새로 수신된 연속 원본으로 복구해야 한다.
    """
    normalised, failures = {}, {}
    for interval, raw in raw_frames.items():
        if interval == "4d":
            continue
        frame, issue = _normalise(raw)
        if issue:
            failures[interval] = _hold(issue)
        else:
            normalised[interval] = frame
    prepared = prepare_closed_frames(normalised, asof)
    result = {}
    for interval in raw_frames:
        if interval == "4d":
            continue
        if interval in failures:
            result[interval] = failures[interval]
            continue
        frame = prepared[interval]
        step = _step(interval)
        if frame is None or frame.empty:
            result[interval] = _hold((frame.attrs.get("guidance_issue") if frame is not None else None)
                                    or "마감봉 데이터 없음")
        elif step is None:
            result[interval] = _hold("봉 시작·마감 경계 미지원")
        elif not _finite_ohlc(frame):
            result[interval] = _hold("OHLC 결측·비정상 값: 에너지 관측 보류")
        elif len(frame) > 1 and not (frame.index[:-1] + step == frame.index[1:]).all():
            result[interval] = _hold("봉 누락·간격 불일치: 연속 에너지 관측 보류")
        else:
            result[interval] = _metadata(frame, frame.index + step, frame.index,
                                          "수신 원본의 후속 봉으로 최종값을 확인한 마감봉")
    result["4d"] = _four_day_frame(raw_frames.get("1d"), asof)
    return result
