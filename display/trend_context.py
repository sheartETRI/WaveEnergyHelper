"""4d MA10과 일봉 MA60을 먼저 확인하는 사용자 추세 해석 정책의 표시."""
from __future__ import annotations

from copy import deepcopy

import pandas as pd

from analysis.trend_context import classify_trend_move
from utils.time_display import to_kst


TITLE = "큰 추세 먼저 보기 — 4일봉 MA10 · 일봉 MA60"
DIRECTION = {"up": "상승", "down": "하락", "flat": "평탄", "unknown": "보류"}
STATUS = {
    "ALIGNED": "주 기준과 전체 추세 방향 일치", "CONFLICT": "추세 기준 충돌 — 하위 TF 해석 보류",
    "FLAT": "평탄한 기준 포함 — 방향 해석 보류", "PARTIAL": "추세 교차 확인 자료 부족",
    "UNAVAILABLE": "추세 자료 확인 필요",
}
INTERPRETATION = {
    "WITH_TREND": "큰 추세와 같은 방향의 움직임",
    "COUNTER_RALLY": "하락 추세 내 반등 관찰(역추세) — 상위 추세 전환은 아직 미확인",
    "COUNTER_PULLBACK": "상승 추세 내 조정 관찰(역추세) — 상위 추세 전환은 아직 미확인",
    "CONFLICT": "4일봉 MA10·일봉 MA60 방향 충돌 — 추세 안의 해석 보류",
    "HOLD": "추세 또는 해당 TF 방향 미확인 — 해석 보류",
    "REFERENCE_OR_HIGHER": "기준과 같거나 더 큰 시간 범위 — 하위 TF 반등·조정으로 분류하지 않음",
}
POLICY_NOTE = (
    "사용자 해석 기준: 4일봉 MA10을 먼저 보고 일봉 MA60으로 전체 추세를 교차 확인합니다. "
    "두 기준과 반대인 시간봉 움직임은 반등·조정으로 우선 해석하며 추세 전환을 확정하지 않습니다. "
    "방향은 각 기준 MA의 1봉 변화로 측정합니다. 높은 TF의 성공 확률을 수치로 보장하는 규칙은 아닙니다."
)


def _time(value) -> str:
    return "미확인" if value is None or pd.isna(value) else f"{to_kst(value):%Y-%m-%d %H:%M} (KST)"


def _utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _basis_line(basis: dict) -> str:
    direction = DIRECTION.get(basis.get("direction"), "보류")
    text = direction
    if basis.get("ma_value") is not None:
        text += f" · MA {float(basis['ma_value']):,}"
    if basis.get("price_position") in ("above", "below", "equal"):
        position = {"above": "위", "below": "아래", "equal": "동일"}[basis["price_position"]]
        text += f" · 종가는 MA {position}(MA 방향과 별도)"
    text += f" · 마지막 마감 {_time(basis.get('last_close'))}"
    if basis.get("interval") == "4d" and basis.get("grid_origin") is not None:
        text += f" · 4d 집계 기준 시작 {_time(basis['grid_origin'])}"
    if basis.get("issue"):
        issues = {"NO_DATA": "자료 없음", "STALE": "마감 자료 갱신 지연", "UPSTREAM_ISSUE": basis.get("issue_detail", "원본 확인 필요"),
                  "INSUFFICIENT_BARS": "유효 봉 부족", "NONFINITE_CLOSE": "종가 결측", "MISSING_BARS": "봉 누락",
                  "UNCONFIRMED_BAR": "미마감 봉 포함"}
        text += " · 자료 확인 필요: " + issues.get(basis["issue"], "시각·마감 자료 확인 필요")
    return text


def build_trend_view(context: dict) -> dict:
    items = [
        ("주 추세 기준 · 4d MA10", _basis_line(context["primary"])),
        ("전체 추세 참고 · 1d MA60", _basis_line(context["reference"])),
        ("큰 추세 판정", STATUS[context["status"]]),
        ("다음 추세 확인", _time(context.get("next_check_at"))),
        ("해석 원칙", POLICY_NOTE),
        ("40일 범위의 의미", "4일봉 MA10은 4일 간격 종가 10개의 평균입니다. 일봉 MA40과 값·갱신 주기가 다릅니다."),
    ]
    return {"title": TITLE, "items": items, "context": deepcopy(context),
            "text": "\n\n".join([f"### {TITLE}"] + [f"**{label}**: {value}" for label, value in items])}


def render_trend_context(view: dict) -> None:
    import streamlit as st

    with st.container(border=True):
        st.markdown(f"### {view['title']}")
        for label, value in view["items"]:
            st.markdown(f"**{label}**: {value}")


def apply_trend_context(card: dict, context: dict, local_direction: str, period: int = 10) -> dict:
    """같은 조회의 큰 추세를 카드에 붙인다. 가격·시각만의 변동은 변화 이벤트가 아니다."""
    result = deepcopy(card)
    tf = result["interval"]
    local_ready = result.get("local_data_status", "마감봉 기준") == "마감봉 기준"
    if not local_ready:
        local_direction = "unknown"
    interpretation = classify_trend_move(tf, local_direction, context, period=period)
    code = interpretation["code"]
    basis = f"주 기준 4d MA10 {DIRECTION.get(context['primary']['direction'], '보류')} · 전체 참고 1d MA60 {DIRECTION.get(context['reference']['direction'], '보류')}"
    extra = [("큰 추세 기준", basis),
             ("추세 안의 해석", f"{tf} MA{period} {DIRECTION.get(local_direction, '보류')}: {INTERPRETATION[code]}")]
    observation = []
    for direction in result.get("observation_directions", []):
        candidate = classify_trend_move(tf, direction if local_ready else "unknown", context, period=period)
        observation.append(f"{DIRECTION[direction]} 전환 관찰: {INTERPRETATION[candidate['code']]}")
    if observation:
        extra.append(("관찰 방향 해석", " / ".join(observation)))
    result["items"] = extra + result["items"]
    result["snapshot"]["trend"] = deepcopy(context["snapshot"])
    result["trend_context"] = deepcopy(context)
    times = [value for value in (result.get("next_check_at"), context.get("next_check_at")) if value is not None]
    result["next_check_at"] = min(_utc(value) for value in times) if times else None
    return result


def render_saved_trend_context(symbol: str) -> None:
    """차트 TF와 독립적인 마지막 레이더 조회의 추세만 표시한다."""
    import streamlit as st

    saved = st.session_state.get(f"wave_energy_observation:{symbol}")
    if not saved or not saved.get("trend"):
        return
    view = deepcopy(saved["trend"])
    st.caption(f"추세 조회 기준: {_time(saved.get('asof'))}")
    deadline = view["context"].get("next_check_at")
    if deadline is not None and pd.Timestamp.now(tz="UTC") >= _utc(deadline):
        st.warning("추세 확인 시각이 지났습니다. 레이더를 다시 조회한 뒤 하위 TF의 반등·조정을 해석하세요.")
        view["items"] = [(label, "조회 기준 만료 — 큰 추세 재확인 필요" if label in ("큰 추세 판정", "다음 추세 확인")
                           else value) for label, value in view["items"]]
    render_trend_context(view)
