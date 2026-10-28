"""마감 기준 TF 설명의 공용 준비·표시. 외부 발송 없이 세션 내 변화를 비교한다."""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, Optional

import pandas as pd

from display.mtf_guidance_model import closed_frame


METHOD_NOTE = (
    "스토캐스틱 대파동 패턴은 관찰 계기, 해당 TF의 MA60은 추세 확인 대상입니다. "
    "상위 TF는 큰 추세의 환경, 하위 TF는 내부 진행을 설명합니다. "
    "상하위 연결은 프로젝트의 기존 연결 규칙이며, 관찰 순서는 성공 확률을 뜻하지 않습니다."
)
MATH_NOTE = (
    "MA60은 종가의 단순이평입니다. 이번 MA60 변화량 = "
    "(이번 종가 − 같은 TF의 60봉 전 종가) ÷ 60. "
    "다음 봉 종가가 비교 종가보다 높으면 상승, 같으면 평평, 낮으면 하락입니다. "
    "비교 종가는 봉마다 바뀌며 목표가나 가격 예측이 아닙니다. "
    "이 설명의 1봉 차분과 기존 전환 추적기의 전환 확정 조건은 구분합니다."
)
REFRESH_NOTE = (
    "관찰 TF와 선정 이유는 현재 차트의 시간봉 선택과 독립적입니다. 다음 마감 후 레이더를 다시 조회하세요. "
    "레이더 조회 시 관찰 대상·전환 상태·MA60 방향·자료 상태의 변화를 이 세션에서 비교합니다."
)


def prepare_closed_frames(
    raw_frames: dict[str, Optional[pd.DataFrame]], asof,
) -> dict[str, Optional[pd.DataFrame]]:
    """OHLCV를 먼저 마감 시각으로 자른 후 지표를 다시 계산한다.

    미마감 봉이 피봇 확정에 참여한 흔적을 남기지 않는다. 이미 받은 프레임만
    사용하므로 차트 첫 화면에서 상하위 TF나 전체 레이더를 추가 수신하지 않는다.
    """
    from indicators.moving_averages import add_moving_averages
    from indicators.stochastic import add_stochastic_slow_layers

    frames = {}
    for interval, raw in raw_frames.items():
        if raw is None:
            frames[interval] = None
            continue
        columns = [c for c in ("open", "high", "low", "close", "volume") if c in raw]
        # raw 스냅샷의 마지막 봉은 수신 당시 진행 중이었을 수 있다. 시계만
        # 마감을 지나도 최종값을 수신했다는 뜻은 아니므로, 후속 원본 봉이
        # 있는 구간까지만 확정 설명에 쓴다. 추가 수신 시 자연스럽게 전진한다.
        frame = closed_frame(raw.loc[:, columns].iloc[:-1], interval, asof)
        if not frame.empty:
            try:
                attrs = dict(frame.attrs)
                frame = add_stochastic_slow_layers(add_moving_averages(frame))
                frame.attrs.update(attrs)
            except (KeyError, TypeError, ValueError) as exc:
                frame = frame.iloc[:0].copy()
                frame.attrs["guidance_issue"] = f"지표 계산 보류: {type(exc).__name__}"
        frames[interval] = frame
    return frames


def candidate_frames(frames: dict[str, Optional[pd.DataFrame]]) -> dict[str, tuple]:
    """마감 기준 추적 결과를 화면 캐시에서 한 번 가져온다."""
    from display.analysis_cache import downward_candidates, upward_candidates

    return {
        interval: (pd.DataFrame(), pd.DataFrame()) if frame is None or frame.empty
        else (upward_candidates(frame), downward_candidates(frame))
        for interval, frame in frames.items()
    }


def render_guidance(
    card: dict, *, symbol: str, scope: str,
    on_open_chart: Optional[Callable[[str], None]] = None,
) -> dict:
    """동일 카드의 화면·복사 view. 가격·시각 표시는 의미 변화 비교에서 제외한다."""
    import streamlit as st
    from data.binance import stale_age
    from data.processor import get_fetch_interval

    interval = card["interval"]
    # 수신 실패 저장본은 마지막 봉이 아직 최근이어도 정상 수신과 구분한다.
    card = deepcopy(card)
    related = card.get("related", {})
    loaded = [interval] + [related[role] for role in ("upper", "lower")
                           if related.get(role) and card["snapshot"].get(role) not in ("미적재", "연결 없음")]
    sources = {tf: stale_age(symbol, get_fetch_interval(tf)) for tf in dict.fromkeys(loaded)}
    stale = [f"{tf}({age})" for tf, age in sources.items() if age]
    if stale:
        card["items"].append(("수신 상태", "수신 실패로 저장본 표시: " + ", ".join(stale)))
    card["snapshot"]["source"] = "|".join(tf for tf, age in sources.items() if age)
    state_key = f"mtf_guidance_seen:{scope}:{symbol}:{interval}"
    focus_key = f"mtf_guidance_focus:{scope}:{symbol}"
    snapshot = card["snapshot"]
    previous = st.session_state.get(state_key)
    previous_tf = st.session_state.get(focus_key)
    focus_changed = previous_tf is not None and previous_tf != interval
    changed_state = previous is not None and previous != snapshot
    if focus_changed:
        change = f"관찰 대상이 바뀌었습니다: {previous_tf} → {interval}. 새 대상의 선정 이유와 다음 확인 조건을 확인하세요."
    elif previous is None:
        change = "이 세션의 첫 관찰입니다. 다음 확인부터 상태 변화를 비교합니다."
    elif previous == snapshot:
        change = "이전 확인과 같은 관찰 상태입니다."
    else:
        labels = {"up": "상방 후보", "down": "하방 후보", "ma60": "MA60 방향",
                  "upper": "상위 환경", "lower": "하위 진행", "data": "자료 상태", "source": "수신 상태"}
        changed = [label for key, label in labels.items() if previous.get(key) != snapshot.get(key)]
        detail = ", ".join(changed) or "관찰 상태"
        change = f"관찰 상태가 바뀌었습니다: {detail}. 현재 설명에서 변경 내용을 확인하세요."
    st.session_state[state_key] = deepcopy(snapshot)
    st.session_state[focus_key] = interval

    return _draw_guidance(card, symbol=symbol, scope=scope, change=change,
                         changed=focus_changed or changed_state, on_open_chart=on_open_chart)


def _draw_guidance(card: dict, *, symbol: str, scope: str, change: str, changed: bool,
                   on_open_chart: Optional[Callable[[str], None]] = None) -> dict:
    """계산된 카드만 표시한다. 저장 결과 재생에서는 상태·수신 정보를 갱신하지 않는다."""
    import streamlit as st

    interval = card["interval"]
    title = f"{symbol} · {card['title']}"
    lines = [f"### {title}"] + [f"**{label}**: {value}" for label, value in card["items"]]
    with st.container(border=True):
        for line in lines:
            st.markdown(line)
        if changed:
            st.info(change)
        else:
            st.caption(change)
        st.caption(REFRESH_NOTE)
        if on_open_chart is not None:
            related = card.get("related", {})
            targets = [("관찰", interval), ("상위", related.get("upper")), ("하위", related.get("lower"))]
            targets = [(role, tf) for role, tf in targets if tf]
            for column, (role, tf) in zip(st.columns(len(targets)), targets):
                column.button(
                    f"{tf} {role} 차트 열기", key=f"mtf_open:{scope}:{symbol}:{interval}:{role}",
                    on_click=on_open_chart, args=(tf,),
                )
        with st.expander("지표와 TF를 연결한 근거", expanded=False):
            st.markdown(METHOD_NOTE)
            st.markdown(MATH_NOTE)
    return {"text": "\n\n".join(lines + [change, REFRESH_NOTE, METHOD_NOTE, MATH_NOTE]),
            "card": card, "change": change, "changed": changed}


def remember_radar_observation(symbol: str, view: Optional[dict], asof, *, empty_reason: str = "") -> None:
    """심볼별 마지막 레이더 조회 결과. 새 조회에 대상이 없으면 이전 대상을 지운다."""
    import streamlit as st

    st.session_state[f"mtf_radar_observation:{symbol}"] = {
        "view": deepcopy(view), "asof": pd.Timestamp(asof), "empty_reason": empty_reason,
    }


def render_saved_observation(
    symbol: str, *, on_open_chart: Optional[Callable[[str], None]] = None,
    on_scan: Optional[Callable[[], None]] = None,
) -> dict:
    """차트 TF를 입력받지 않고 마지막 레이더 결과를 읽기 전용으로 표시한다."""
    import streamlit as st
    from utils.time_display import to_kst

    saved = st.session_state.get(f"mtf_radar_observation:{symbol}")
    st.markdown("**레이더가 선정한 관찰 TF**")
    if saved is None:
        text = "아직 레이더를 조회하지 않았습니다. 관찰 TF 찾기로 지금 주목할 TF와 선정 이유를 확인하세요."
        st.info(text)
        view = {"text": text}
    else:
        stamp = f"레이더 조회 기준: {to_kst(saved['asof']):%Y-%m-%d %H:%M:%S} (KST)"
        st.caption(stamp)
        if saved["view"] is None:
            text = saved["empty_reason"] or "현재 레이더 기준으로 관찰할 TF가 없습니다."
            st.info(text)
            view = {"text": stamp + "\n\n" + text}
        else:
            card = deepcopy(saved["view"]["card"])
            next_check = card.get("next_check_at")
            now = pd.Timestamp.now(tz="UTC")
            if next_check is not None:
                next_check = pd.Timestamp(next_check)
                next_check = next_check.tz_localize("UTC") if next_check.tzinfo is None else next_check.tz_convert("UTC")
            if next_check is not None and now >= next_check:
                expired = "다음 확인 시각이 지났습니다. 레이더를 다시 조회해 현재 조건을 확인하세요."
                card["items"] = [(label, expired if label in ("다음 확인", "관찰 기간") else value)
                                 for label, value in card["items"]]
            card["items"] = [("조회 당시 수신 상태" if label == "수신 상태" else label, value)
                             for label, value in card["items"]]
            view = _draw_guidance(
                card, symbol=symbol, scope="saved_radar", changed=False, on_open_chart=on_open_chart,
                change="마지막 레이더 조회 결과입니다. 차트 TF를 바꿔도 이 관찰 대상은 유지됩니다.",
            )
            view["text"] = stamp + "\n\n" + view["text"]
    if on_scan is not None:
        st.button("관찰 TF 찾기" if saved is None else "레이더 다시 조회",
                  key=f"mtf_radar_scan:{symbol}", on_click=on_scan)
    return view
