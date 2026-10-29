"""4d MA10과 일봉 MA60을 먼저 확인하는 사용자 추세 해석 정책의 표시."""
from __future__ import annotations

from copy import deepcopy

import pandas as pd

from analysis.trend_context import classify_trend_move
from config.settings import MACD_PARAMS
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
TURNING_LABELS = ("4d 변곡 준비", "4d MA10 기울기", "4d MA5·MA10", "4d MACD·시그널", "변곡 다음 확인")
TURNING_STATE = {
    "BEARISH_PREP": "상승 추세 내 하락 변곡 준비 — MA10 하락 전환은 아직 미확인",
    "DOWNSIDE_EVIDENCE": "MA10 상승 중 MA5·MACD 하방 근거 유지 — 기울기 둔화 동시 충족은 아님",
    "SLOWING": "MA10 상승 기울기 둔화 — MA5·MACD 하방 근거의 동시 충족을 확인",
    "MA10_DOWN": "MA10 하락 관측 — 상승 중 변곡 준비 단계와 구분",
    "NO_PREP": "세 조건이 함께 나타나는 하락 변곡 준비 근거 없음",
    "HOLD": "변곡 준비 판단 보류 — 마감 자료·계산 이력 확인 필요",
}


def turning_summary(context: dict) -> str:
    turning = context.get("turning", {})
    state = turning.get("state", "HOLD")
    text = TURNING_STATE.get(state, TURNING_STATE["HOLD"])
    if state == "HOLD" and turning.get("issue") == "INSUFFICIENT_BARS":
        minimum = MACD_PARAMS["slow"] + MACD_PARAMS["signal"]
        text += f"(MACD 계산에 완성 4d 봉 {minimum}개 이상 필요)"
    return text


def trend_interpretation(code: str, context: dict) -> str:
    text = INTERPRETATION[code]
    if context.get("turning", {}).get("state") == "BEARISH_PREP" and code != "HOLD":
        text += " · 4d 하락 변곡 준비 근거 동반: 상승 방향이 유지돼도 조정 지속·확대와 MA10 하향 전환을 함께 확인"
    return text


def _time(value) -> str:
    return "미확인" if value is None or pd.isna(value) else f"{to_kst(value):%Y-%m-%d %H:%M} (KST)"


def _utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _number(value) -> str:
    return "미확인" if value is None else f"{float(value):,.12g}"


def _cross_text(event) -> str:
    if not event:
        return "교차 발생 시각 미확인"
    kind = "데드크로스" if event["kind"] == "dead" else "골든크로스"
    age = "이번 마감봉" if event["bars_ago"] == 0 else f"{event['bars_ago']}봉 전"
    return f"마지막 {kind} {_time(event['time'])}({age})"


def _turning_items(context: dict) -> list:
    turning = context.get("turning", {})
    held = turning.get("state", "HOLD") == "HOLD"
    slowing = turning.get("ma10_slowing")
    slope = f"직전 {_number(turning.get('ma10_prev_delta'))} → 현재 {_number(turning.get('ma10_delta'))}(가격/4d 봉)"
    slope += " · 상승 기울기 둔화" if slowing else " · 상승 기울기 둔화 조건 미충족" if slowing is False else " · 확인 보류"
    relations = {"above": "위", "below": "아래", "equal": "동일", "unknown": "미확인"}
    ma = (f"MA5 {_number(turning.get('ma5_value'))} · MA10 {_number(turning.get('ma10_value'))}"
          f" · MA5가 MA10 {relations.get(turning.get('ma_relation'), '미확인')}"
          f" · {_cross_text(turning.get('ma_cross'))}")
    macd = (f"MACD선 {_number(turning.get('macd_value'))} · 시그널선 {_number(turning.get('signal_value'))}"
            f" · MACD선이 시그널선 {relations.get(turning.get('macd_relation'), '미확인')}"
            f" · {_cross_text(turning.get('macd_cross'))}")
    params = ",".join(str(MACD_PARAMS[key]) for key in ("fast", "slow", "signal"))
    macd += f" · MACD({params})"
    if turning.get("macd_basis") == "chart_seed":
        macd += " · 기존 4d 차트와 같은 초기 계산 이력"
    elif turning.get("macd_basis") == "closed_only":
        macd += " · 완성 4d 봉의 계산 이력(차트 초기값 미확인)"
    next_text = (
        f"다음 4d 마감 {_time(turning.get('next_close'))}: MA10 변화량이 음수로 바뀌는지 확인. "
        "MA5·MACD의 재상향 교차 또는 MA10 재가속으로 세 조건이 깨지면 준비 상태를 해제합니다. "
        "세 조건의 결합은 관찰 근거이며 하락 확률이나 전환 확정을 뜻하지 않습니다."
    )
    if held:
        slope = ma = macd = next_text = "마감 자료·연속 봉·MACD 계산 이력 확인 후 다시 관찰"
    return list(zip(TURNING_LABELS, (turning_summary(context), slope, ma, macd, next_text)))


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
        *_turning_items(context),
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
             ("4d 변곡 준비", turning_summary(context)),
             ("추세 안의 해석", f"{tf} MA{period} {DIRECTION.get(local_direction, '보류')}: {trend_interpretation(code, context)}")]
    observation = []
    for direction in result.get("observation_directions", []):
        candidate = classify_trend_move(tf, direction if local_ready else "unknown", context, period=period)
        observation.append(f"{DIRECTION[direction]} 전환 관찰: {trend_interpretation(candidate['code'], context)}")
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
        view["items"] = [(label, "조회 기준 만료 — 큰 추세·변곡 근거 재확인 필요" if label in ("큰 추세 판정", "다음 추세 확인", *TURNING_LABELS)
                           else value) for label, value in view["items"]]
    render_trend_context(view)
