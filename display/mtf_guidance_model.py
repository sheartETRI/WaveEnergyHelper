"""마감봉을 근거로 관찰 이유와 다음 확인 조건을 설명한다.

선정 순위나 기존 신호를 변경하지 않는 순수 표시 모델이다. 한국어 문구와
시각 변환은 표시 계층에만 두며, 데이터·검출·기록 계층의 시각을 바꾸지 않는다. 호출자는 OHLC를
``closed_frame``으로 자른 뒤 지표와 기존 후보를 다시 계산해야 한다. 미마감
봉으로 확정된 피봇을 남기지 않도록 완성된 지표 프레임을 단순 절단하지 않는다.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from config.settings import TIMEFRAMES, UPPER_FRAME_MAP
from tracking.signals import OBS_BARS
from utils.time_display import to_kst

_CUSTOM_RIGHT = {"2d", "4d", "2w"}
_UNITS = {"m": 1, "h": 60, "d": 1440, "w": 10080, "M": 43200}


def _utc(value) -> pd.Timestamp:
    value = pd.Timestamp(value)
    return value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC")


def _step(interval: str):
    if interval == "1M":
        return pd.DateOffset(months=1)
    if interval in _CUSTOM_RIGHT or interval not in TIMEFRAMES:
        return None
    return pd.Timedelta(minutes=int(interval[:-1]) * _UNITS[interval[-1]])


def _kst(value) -> str:
    return f"{to_kst(value):%Y-%m-%d %H:%M} (KST)"


def _empty(df, reason: str) -> pd.DataFrame:
    result = df.iloc[:0].copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    result.attrs["guidance_issue"] = reason
    return result


def closed_frame(df: Optional[pd.DataFrame], interval: str, asof) -> pd.DataFrame:
    """open_time+기간<=asof인 행의 사본. naive 시각은 UTC로 해석한다.

    우측 라벨의 기존 커스텀 봉은 시작·마감 의미가 불명확하므로 보류한다.
    불연속 행은 남기되 이후 조건 계산에서 연속성을 검사한다.
    """
    step = _step(interval)
    if step is None:
        return _empty(df, "이 TF의 봉 시작·마감 경계를 확인할 수 없어 설명을 보류합니다")
    if df is None or df.empty:
        return _empty(df, "마감봉 데이터 없음")
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.hasnans:
        return _empty(df, "봉 시각이 유효하지 않아 설명을 보류합니다")
    if not df.index.is_monotonic_increasing or not df.index.is_unique:
        return _empty(df, "봉 시각의 정렬·중복을 확인해야 합니다")
    index = pd.DatetimeIndex([_utc(t) for t in df.index])
    result = df.loc[index + step <= _utc(asof)].copy()
    result.attrs.pop("guidance_issue", None)
    return result


def _minutes(interval: str) -> int:
    return int(interval[:-1]) * _UNITS[interval[-1]]


def _adjacent(interval: str, up: bool) -> Optional[str]:
    """v1 resolve_upper_frame/resolve_lower_frame의 config 기반 해석과 동일."""
    mapping = UPPER_FRAME_MAP if up else {v: k for k, v in UPPER_FRAME_MAP.items()}
    if interval in mapping:
        return mapping[interval]
    if interval not in TIMEFRAMES:
        return None
    base = _minutes(interval)
    for ratio in (4, 6):
        if not up and base % ratio:
            continue
        target = base * ratio if up else base // ratio
        for tf in TIMEFRAMES:
            if _minutes(tf) == target:
                return tf
    return None


def _valid_tail(df: pd.DataFrame, interval: str, count: int) -> bool:
    if len(df) < count or "close" not in df or _step(interval) is None:
        return False
    tail = df.tail(count)
    values = pd.to_numeric(tail["close"], errors="coerce")
    if not all(math.isfinite(v) for v in values.to_numpy(dtype=float, na_value=float("nan"))):
        return False
    if not isinstance(tail.index, pd.DatetimeIndex) or tail.index.hasnans or not tail.index.is_unique:
        return False
    index = pd.DatetimeIndex([_utc(t) for t in tail.index])
    return bool((index[:-1] + _step(interval) == index[1:]).all())


def _direction(df: Optional[pd.DataFrame], interval: str) -> str:
    if df is None or df.empty:
        return "자료 없음"
    if not _valid_tail(df, interval, 61):
        return "판단 보류(연속 유효 종가 61봉 필요)"
    delta = float(df["close"].iloc[-1]) - float(df["close"].iloc[-61])
    return "상승" if delta > 0 else "하락" if delta < 0 else "평탄"


def _data_status(df: Optional[pd.DataFrame], interval: str, asof) -> str:
    if _step(interval) is None:
        return "이 TF의 봉 시작·마감 경계를 확인할 수 없어 설명을 보류합니다"
    if df is None or df.empty:
        return (df.attrs.get("guidance_issue") if df is not None else None) or "마감봉 데이터 없음"
    if not _valid_tail(df, interval, 60):
        return "봉 누락·종가 결측 또는 연속 유효 종가 60봉 미만: 비교 조건 보류"
    if _utc(df.index[-1]) + _step(interval) * 2 <= _utc(asof):
        return "마감봉 갱신 지연: 데이터 새로고침 필요"
    return "마감봉 기준"


def _candidate(frame: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    if frame is None or frame.empty or "상태" not in frame:
        return None
    for status in ("대기 중", "전환 발생", "해당 없음 (이미 상방)", "해당 없음 (이미 하방)", "소멸", "MA60 미산출"):
        selected = frame[frame["상태"] == status]
        if len(selected):
            if "_known_pos" in selected:
                selected = selected.sort_values("_known_pos", ascending=False, kind="mergesort")
            return selected.iloc[0]
    return None


def _candidate_text(row: Optional[pd.Series], direction: str, df: pd.DataFrame, interval: str) -> tuple[str, str, str]:
    if row is None:
        return "", "", ""
    pattern = "대파동 스토캐스틱 쌍바닥" if direction == "상방" else "대파동 스토캐스틱 쌍봉"
    status = str(row.get("상태", ""))
    confirm = row.get("확정 시각", pd.NaT)
    identity = "" if pd.isna(confirm) else _utc(confirm).isoformat()
    timing = "" if pd.isna(confirm) else f" · 확정봉 마감 {_kst(_utc(confirm) + _step(interval))}"
    known = row.get("_known_pos")
    duration = ""
    if known is not None and pd.notna(known) and 0 <= int(known) < len(df):
        known = int(known)
        known_time = _utc(df.index[known])
        timing += f" · 가용봉 마감 {_kst(known_time + _step(interval))}"
        identity += f"|known={known_time.isoformat()}"
        if status == "대기 중":
            remaining = max(0, known + OBS_BARS - (len(df) - 1))
            if _valid_tail(df, interval, 60) and _valid_tail(df, interval, len(df) - known):
                until = known_time + _step(interval) * (OBS_BARS + 1)
                delta_hours = (until - (_utc(df.index[-1]) + _step(interval))).total_seconds() / 3600
                duration = f"{direction} 관찰 창 잔여 {remaining}봉(약 {delta_hours:g}시간) · 종료봉 마감 {_kst(until)}"
            else:
                duration = f"{direction} 관찰 창 잔여 봉·시간 계산 보류(봉 간격·종가 점검 필요)"
    tail = " · 진행 추세 관찰" if status.startswith("해당 없음 (이미") else ""
    return f"{pattern} → MA60 {direction}: {status}{tail}{timing}", duration, f"{identity}|{status}"


def _relation(direction: str, quality: str, current: str, owner_quality: str, active: list, upper: bool) -> str:
    if quality != "마감봉 기준" or owner_quality != "마감봉 기준":
        return "자료 지연·부족을 해소한 뒤 방향 관계를 확인합니다"
    if direction not in ("상승", "하락", "평탄"):
        return "MA60 방향 자료가 부족해 방향 관계 판단 보류"
    if upper:
        observations = [d for d, enabled in zip(("상방", "하방"), active) if enabled]
        if not observations:
            return "활성 전환 후보가 없어 관찰 방향과의 관계 판단 보류"
        if direction == "평탄":
            return "상위 MA60이 평탄하여 활성 관찰 방향과의 일치·반대를 구분하지 않습니다"
        same = "상방" if direction == "상승" else "하방"
        return " / ".join(f"{d} 관찰과 {'같은' if d == same else '반대'} 방향" for d in observations)
    if current not in ("상승", "하락", "평탄"):
        return "기준 TF의 MA60 방향 자료가 부족해 방향 관계 판단 보류"
    if "평탄" in (current, direction):
        return "기준·하위 MA60 중 평탄한 방향이 있어 일치·반대를 구분하지 않습니다"
    return f"기준 TF MA60과 {'같은' if current == direction else '반대'} 방향"


def build_guidance(interval: str, frames: dict, candidates: dict, asof) -> dict:
    """외부에서 선정한 TF의 설명 view. snapshot에는 의미 변화만 담는다.

    items는 (라벨, 한국어 설명) 목록이고 화면과 복사가 함께 소비한다.
    candidate identity는 이동하는 행 위치 대신 확정봉 UTC 시각을 사용한다.
    """
    df = frames.get(interval)
    status = _data_status(df, interval, asof)
    current = _direction(df, interval)
    upper, lower = _adjacent(interval, True), _adjacent(interval, False)
    texts, durations, ids = [], [], []
    up_frame, down_frame = candidates.get(interval, (None, None))
    chosen = [_candidate(up_frame), _candidate(down_frame)]
    for row, direction in zip(chosen, ("상방", "하방")):
        if df is not None and not df.empty and _step(interval) is not None:
            text, duration, identity = _candidate_text(row, direction, df, interval)
            if text:
                texts.append(text)
            if duration:
                durations.append(duration)
            ids.append(identity)
        else:
            ids.append("")
    active = [r is not None and r.get("상태") in ("대기 중", "전환 발생") for r in chosen]
    if texts:
        reason = " / ".join(texts)
    elif df is None or df.empty or not _valid_tail(df, interval, 60):
        reason = "마감봉 자료가 부족하거나 유효하지 않아 패턴 후보 유무 판단을 보류합니다"
    else:
        reason = "마감 기준 대파동 패턴 후보 없음 · 선택한 TF의 추세만 관찰합니다"
    if all(active):
        reason += " · 상방·하방 관찰이 함께 있어 한 방향으로 단정할 수 없습니다"
    items = [("선정 이유", reason), ("현재 판단", f"{interval} MA60 1봉 변화: {current}")]
    context_states = []
    for label, tf, role in (("상위 환경", upper, "큰 추세의 환경"), ("하위 진행", lower, "기준 TF 안의 진행")):
        if tf is None:
            text, state = "기존 TF 연결 규칙에 해당 TF 없음", "연결 없음"
        elif tf not in frames:
            text, state = f"{tf} 미적재 · 추가 차트에서 확인", "미적재"
        else:
            direction = _direction(frames[tf], tf)
            quality = _data_status(frames[tf], tf, asof)
            state = f"{direction}|{quality}"
            relation = _relation(direction, quality, current, status, active, label == "상위 환경")
            text = f"{tf} MA60 1봉 변화: {direction} · {role} · {relation} · {quality}"
        if label == "하위 진행":
            text += " · 하위 TF의 변화만으로 기준 TF 전환을 확정하지 않습니다"
        context_states.append(state)
        items.append((label, text))
    next_text = "레이더를 다시 조회해 데이터를 새로고침한 뒤 다음 확인 조건을 계산합니다"
    next_check_at = None
    if status == "마감봉 기준":
        next_close = _utc(df.index[-1]) + _step(interval) * 2
        next_check_at = next_close
        reference = float(df["close"].iloc[-60])
        reference_text = f"{reference:,.0f}" if reference.is_integer() else f"{reference:,}"
        next_text = (f"다음 {interval} 봉 마감 {_kst(next_close)} · 그 봉 종가가 {reference_text}보다 높으면 "
                     "MA60 상승, 낮으면 하락, 같으면 평탄 · 비교값은 매 봉 갱신됩니다")
    duration_text = " / ".join(durations) or "현재 열려 있는 전환 관찰 창 없음"
    if durations and "지연" in status:
        duration_text = f"마지막 적재 마감봉 기준: {duration_text} · 갱신 후 현재 잔여 창 확인"
    items += [("다음 확인", next_text), ("관찰 기간", duration_text)]
    if df is not None and not df.empty and _step(interval) is not None:
        status_text = f"{status} · 마지막 마감 {_kst(_utc(df.index[-1]) + _step(interval))}"
    else:
        status_text = status
    items += [("자료 기준", status_text),
              ("해석 범위", "MA60 방향 조건은 단순이평의 수학적 관계입니다. 패턴 후 전환 가능성은 미검증이며 비교값은 목표가·예측이 아닙니다. 기존 전환 상태는 별도 관찰 창 규칙을 따릅니다.")]
    return {"interval": interval, "title": f"{interval} 관찰 설명", "items": items,
            "next_check_at": next_check_at,
            "related": {"upper": upper, "lower": lower},
            "snapshot": {"interval": interval, "up": ids[0], "down": ids[1], "ma60": current,
                         "upper": context_states[0], "lower": context_states[1], "data": status}}
