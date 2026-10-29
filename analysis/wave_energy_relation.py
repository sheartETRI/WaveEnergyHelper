"""같은 시간봉의 대·소파동 관계를 관측한다. 성과·진입 판정은 하지 않는다.

ER1 규칙: 대파동 K의 1봉 차분 부호가 바뀌면 새 방향 구간을 연다.
차분 0은 구간을 유지하지만 현재 방향은 flat으로 따로 보고한다. 현재 구간의
시작점부터 기존 폭 비교 검출기를 다시 실행하므로 구간 이전의 첫 바닥이나
전체 이력에서 나중에 취소된 후보를 재활용하지 않는다. 확정에는 별도의 피봇
지연을 더하지 않는다. MA10의 방향은 종가 차분으로 독립적으로 관측한다.

WAIT_SMALL / SMALL_FORMING / SMALL_CONFIRMED는 현재 구간의 반대 패턴 상태다.
현재 봉에서 대파동 방향이 바뀌면 직전 구간의 소반대패턴을 reversal_event에
기록하고 LARGE_REVERSED 또는 REASSESS로 사건을 표시한다. 이때 small_status는
새 구간의 관측이므로 사건의 소파동 근거는 reversal_event에서 읽어야 한다.
전환봉에 소패턴이 함께 확정될 수 있어 선행과 동시를 별도 필드로 구분한다.
HISTORY_PARTIAL은 구간 시작을 관측하지 못해 패턴 부재를 단정할 수 없다는 뜻이다.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config.settings import WAVE_LAYER_ROLES
from indicators.stochastic import (
    detect_stochastic_bottom_patterns,
    detect_stochastic_top_patterns,
)


RULE_VERSION = "ER1"
_LARGE = WAVE_LAYER_ROLES["large"]
_MID = WAVE_LAYER_ROLES["mid"]
_SMALL = WAVE_LAYER_ROLES["small"]


def _values(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame:
        return np.full(len(frame), np.nan)
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)


def _direction(values: np.ndarray) -> str:
    if len(values) < 2 or not np.isfinite(values[-2:]).all():
        return "unknown"
    return "up" if values[-1] > values[-2] else "down" if values[-1] < values[-2] else "flat"


def _pattern(direction: str) -> str:
    return "db" if direction == "down" else "dt"


def _small_evidence(frame: pd.DataFrame, pattern: str, offset: int) -> dict:
    values = _values(frame, f"stoch_k_{_SMALL}")
    empty = {"status": "unknown", "confirm_pos": None, "confirm_time": None,
             "first_pos": None, "candidate_level": None}
    if not len(values) or not np.isfinite(values).all():
        return empty
    # 검출기의 후행 메타·후보 취소를 포함하여 해당 구간의 현재 prefix만 소비한다.
    work = pd.DataFrame({f"stoch_k_{_SMALL}": values}, index=frame.index)
    detect = detect_stochastic_bottom_patterns if pattern == "db" else detect_stochastic_top_patterns
    work = detect(work, _SMALL)
    confirmed = np.flatnonzero(work[f"stoch_{pattern}_{_SMALL}"].notna().to_numpy())
    neckline = f"stoch_neckline_{_SMALL}" if pattern == "db" else f"stoch_dt_neckline_{_SMALL}"
    candidate_level = None
    # 과거 둘째 극점에 후보 표시가 남아 있어도 현재 기준선이 없으면 활성 후보가 아니다.
    last_confirmed = bool(work[f"stoch_{pattern}_{_SMALL}"].notna().iloc[-1])
    if not last_confirmed and pd.notna(work[neckline].iloc[-1]):
        candidate_level = float(work[neckline].iloc[-1])
    if len(confirmed):
        pos = int(confirmed[-1])
        first_pos = work[f"stoch_{pattern}_first_pos_{_SMALL}"].iloc[pos]
        return {"status": "confirmed", "confirm_pos": offset + pos,
                "confirm_time": frame.index[pos],
                "first_pos": offset + int(first_pos) if pd.notna(first_pos) else None,
                "candidate_level": candidate_level}
    return {**empty, "status": "forming" if candidate_level is not None else "waiting",
            "candidate_level": candidate_level}


def _legs(values: np.ndarray) -> Optional[list[dict]]:
    finite = np.flatnonzero(np.isfinite(values))
    if len(finite) < 2:
        return None
    first = int(finite[0])
    if not np.isfinite(values[first:]).all():
        return None
    legs = []
    direction = None
    for pos in range(first + 1, len(values)):
        delta = values[pos] - values[pos - 1]
        if delta == 0:
            continue
        new_direction = "up" if delta > 0 else "down"
        if new_direction != direction:
            legs.append({"start": pos - 1, "turn": pos, "direction": new_direction,
                         "complete": bool(legs)})
            direction = new_direction
    return legs


def analyze_energy_relation(df: Optional[pd.DataFrame]) -> dict:
    """마감·시간 연속성을 확인한 지표 프레임의 현재 관측을 반환한다.

    모든 위치는 입력 프레임의 iloc이고, 시각은 입력 인덱스를 그대로 사용한다.
    화면용 방향과 구간 방향을 구분하며, 1봉의 현재 방향만으로 미래를 예측하지 않는다.
    """
    result = {
        "version": RULE_VERSION, "state": "INSUFFICIENT", "reason_code": "NO_DATA",
        "large_direction": "unknown", "mid_direction": "unknown", "small_direction": "unknown",
        "ma10_direction": "unknown", "ma10_delta": None, "ma10_next_reference": None,
        "leg_direction": "unknown", "leg_start_pos": None, "leg_start_time": None,
        "leg_history_complete": False, "small_pattern": None, "small_status": "unknown",
        "small_confirm_pos": None, "small_confirm_time": None, "small_first_pos": None,
        "small_candidate_level": None, "alignment": "unknown", "reversal_event": None,
    }
    if df is None or df.empty:
        return result
    close = _values(df, "close")
    large = _values(df, f"stoch_k_{_LARGE}")
    mid = _values(df, f"stoch_k_{_MID}")
    small = _values(df, f"stoch_k_{_SMALL}")
    result.update(large_direction=_direction(large), mid_direction=_direction(mid),
                  small_direction=_direction(small))
    if len(close) >= 10 and np.isfinite(close[-10:]).all():
        result["ma10_next_reference"] = float(close[-10])
    if len(close) < 11 or not np.isfinite(close[-11:]).all():
        result["reason_code"] = "MA10_INSUFFICIENT"
        return result
    delta = float(close[-1]) - float(close[-11])
    result["ma10_delta"] = delta / 10.0
    result["ma10_direction"] = "up" if delta > 0 else "down" if delta < 0 else "flat"
    large_direction = result["large_direction"]
    if large_direction == "flat" or result["ma10_direction"] == "flat":
        result["alignment"] = "flat"
    elif large_direction in ("up", "down"):
        result["alignment"] = "same" if large_direction == result["ma10_direction"] else "opposed"
    legs = _legs(large)
    if legs is None:
        result["reason_code"] = "LARGE_INSUFFICIENT"
        return result
    if not legs:
        result.update(state="FLAT", reason_code="LARGE_FLAT")
        return result
    leg = legs[-1]
    start = leg["start"]
    pattern = _pattern(leg["direction"])
    evidence = _small_evidence(df.iloc[start:].copy(), pattern, start)
    result.update(leg_direction=leg["direction"], leg_start_pos=start,
                  leg_start_time=df.index[start], leg_history_complete=leg["complete"],
                  small_pattern=pattern, small_status=evidence["status"],
                  small_confirm_pos=evidence["confirm_pos"], small_confirm_time=evidence["confirm_time"],
                  small_first_pos=evidence["first_pos"], small_candidate_level=evidence["candidate_level"])
    if evidence["status"] == "unknown":
        result["reason_code"] = "SMALL_INSUFFICIENT"
        return result
    if not leg["complete"] and evidence["status"] == "waiting":
        result.update(state="HISTORY_PARTIAL", small_status="unknown", reason_code="LEG_START_UNOBSERVED")
    else:
        state = {"waiting": "WAIT_SMALL", "forming": "SMALL_FORMING", "confirmed": "SMALL_CONFIRMED"}
        result.update(state=state[evidence["status"]], reason_code="OBSERVED")

    # 가장 최근 방향 전환의 근거는 전환봉까지의 자료만 사용해 별도 보존한다.
    if len(legs) >= 2:
        previous, turn = legs[-2], leg["turn"]
        previous_pattern = _pattern(previous["direction"])
        before = _small_evidence(df.iloc[previous["start"]:turn + 1].copy(),
                                 previous_pattern, previous["start"])
        supported = before["status"] == "confirmed"
        absence_known = previous["complete"] and before["status"] != "unknown"
        event = {"time": df.index[turn], "pos": turn, "from_direction": previous["direction"],
                 "to_direction": leg["direction"], "small_pattern": previous_pattern,
                 "small_confirmed": True if supported else False if absence_known else None,
                 "small_confirm_time": before["confirm_time"],
                 "small_confirmation_timing": ("same_bar" if before["confirm_pos"] == turn else "before")
                 if supported else None,
                 "leg_history_complete": previous["complete"]}
        result["reversal_event"] = event
        if turn == len(df) - 1:
            if supported:
                result.update(state="LARGE_REVERSED", reason_code="SMALL_WITH_LARGE_REVERSAL")
            elif absence_known:
                result.update(state="REASSESS", reason_code="LARGE_REVERSED_WITHOUT_SMALL_CONFIRMATION")
            else:
                result.update(state="HISTORY_PARTIAL", reason_code="PREVIOUS_LEG_UNOBSERVED")
    return result
