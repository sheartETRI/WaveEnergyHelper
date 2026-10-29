"""같은 TF 안의 대·소파동 반전 근거와 실제 MA10 방향을 함께 표시한다."""
from __future__ import annotations

from copy import deepcopy

import pandas as pd
import streamlit as st

from analysis.wave_energy_relation import analyze_energy_relation
from analysis.trend_context import build_trend_context, classify_trend_move
from config.settings import WAVE_LAYER_ROLES
from display.mtf_guidance import render_guidance
from display.trend_context import TURNING_LABELS, apply_trend_context, build_trend_view, render_trend_context, trend_interpretation
from utils.time_display import to_kst


TITLE = "파동 에너지 관찰 — 대·소파동과 MA10"
CAPTION = (
    "60MA 전환 후보와 별도로, 같은 TF의 대파동 방향 구간 안에서 소파동 쌍바닥·쌍봉을 확인합니다. "
    "대파동 K와 MA10은 각각 측정하며, 미확정 패턴만으로 하락·상승 지속을 보장하지 않습니다."
    " 4일봉 MA10·일봉 MA60을 먼저 확인해 시간봉의 역방향 움직임은 반등·조정으로 해석합니다. "
    "관찰 순서는 확인 단계가 진행된 TF부터, 동률이면 큰 TF부터이며 성공 확률이 아닙니다."
)
DIRECTION = {"up": "상승", "down": "하락", "flat": "평탄", "unknown": "보류"}
STATE = {
    "INSUFFICIENT": "자료 부족", "FLAT": "대파동 평탄", "HISTORY_PARTIAL": "구간 시작 미확인",
    "WAIT_SMALL": "소파동 반전 근거 대기", "SMALL_FORMING": "소파동 반전 후보",
    "SMALL_CONFIRMED": "소파동 확정·대파동 반전 대기", "LARGE_REVERSED": "대파동 방향 변화 관측",
    "REASSESS": "소파동 선행 확정 없는 방향 변화",
}
PATTERN = {"db": "쌍바닥", "dt": "쌍봉"}


@st.cache_data(show_spinner=False, ttl=600, max_entries=64)
def _relation(frame: pd.DataFrame) -> dict:
    return analyze_energy_relation(frame)


def _reading(frame) -> dict:
    if frame is None or frame.empty:
        return analyze_energy_relation(None)
    columns = ["close", *(f"stoch_k_{WAVE_LAYER_ROLES[role]}" for role in ("large", "mid", "small"))]
    return _relation(frame.loc[:, [c for c in columns if c in frame]])


def _time(value) -> str:
    return f"{to_kst(value):%Y-%m-%d %H:%M} (KST)"


def build_energy_view(frames: dict, asof) -> dict:
    """관찰 순서는 확인 단계·TF 크기 순. 성과나 확률 점수가 아니다."""
    from display.mtf_guidance_model import _step, _utc

    context = build_trend_context(frames, asof)
    rows, readings = [], {}
    for tf, frame in frames.items():
        reading = _reading(frame)
        issue = "마감 자료 없음" if frame is None else frame.attrs.get("energy_issue", "")
        closes = None if frame is None else frame.attrs.get("energy_bar_closes")
        last_close = closes[-1] if closes is not None and len(closes) else None
        step = pd.Timedelta(days=4) if tf == "4d" else _step(tf)
        next_close = _utc(last_close) + step if last_close is not None and step is not None else None
        if next_close is not None and next_close <= _utc(asof):
            issue = "마감 자료 갱신 지연"
        state = STATE.get(reading["state"], reading["state"])
        if issue:
            state = f"판단 보류: {issue}"
        pattern = PATTERN.get(reading.get("small_pattern"), "반전 패턴")
        small_status = {"waiting": "미확정", "forming": "형성 중", "confirmed": "확정", "unknown": "보류"}.get(reading.get("small_status"), "보류")
        ma10 = DIRECTION.get(reading.get("ma10_direction"), "보류")
        large = DIRECTION.get(reading.get("large_direction"), "보류")
        relation = {"same": "동행", "opposed": "방향 불일치", "flat": "평탄 포함", "unknown": "보류"}.get(reading.get("alignment"), "보류")
        next_text = f"소파동 {pattern} 확정 → 대파동 K 방향 변화 → MA10 방향을 차례로 확인"
        if reading["state"] == "SMALL_CONFIRMED":
            next_text = "소파동 근거 발생. 대파동 K 반전과 실제 MA10 방향을 확인"
        if reading["state"] in ("LARGE_REVERSED", "REASSESS"):
            next_text = "대파동 방향 변화가 관측됨. 실제 MA10 동행 여부와 새로운 구간을 재확인"
        if issue or reading["state"] in ("INSUFFICIENT", "HISTORY_PARTIAL", "FLAT"):
            next_text = "자료·구간 시작을 확인한 후 다시 관찰"
        trend_move = classify_trend_move(tf, reading.get("ma10_direction") if not issue else "unknown", context)
        rows.append({"TF": tf, "관찰 상태": state, "대파동 K": large,
                     "중파동 K": DIRECTION.get(reading.get("mid_direction"), "보류"),
                     "소파동": f"{pattern} {small_status}", "MA10": ma10,
                     "대파동·MA10": relation, "추세 안의 해석": trend_interpretation(trend_move["code"], context), "다음 확인": next_text})
        readings[tf] = {"reading": reading, "issue": issue, "next_close": next_close, "last_close": last_close}
    # 기존 MA60 레이더의 선정·점수를 바꾸지 않는 별도의 관찰 순서다.
    priority = {"SMALL_CONFIRMED": 4, "LARGE_REVERSED": 4, "SMALL_FORMING": 3, "REASSESS": 2, "WAIT_SMALL": 1}
    def minutes(tf):
        return int(tf[:-1]) * {"m": 1, "h": 60, "d": 1440, "w": 10080, "M": 43200}[tf[-1]]
    available = [tf for tf, value in readings.items() if not value["issue"] and value["reading"]["state"] in priority]
    available.sort(key=lambda tf: (-priority[readings[tf]["reading"]["state"]], -minutes(tf)))
    rows.sort(key=lambda row: -minutes(row["TF"]))
    card = None
    if available:
        tf = available[0]
        value, row = readings[tf], next(row for row in rows if row["TF"] == tf)
        reading = value["reading"]
        reason = f"대파동 K {row['대파동 K']} · 소파동 {row['소파동']} · {row['관찰 상태']}"
        event = reading.get("reversal_event")
        if reading["state"] in ("LARGE_REVERSED", "REASSESS") and event:
            previous_pattern = PATTERN[event["small_pattern"]]
            timing = "같은 봉에서" if event.get("small_confirmation_timing") == "same_bar" else "먼저"
            evidence = f"소파동 {previous_pattern}이 {timing} 확정됨" if event["small_confirmed"] else f"소파동 {previous_pattern} 선행 확정 없음"
            reason = f"대파동 K {row['대파동 K']} 전환 관측 · {evidence} · {row['관찰 상태']}"
        next_text = row["다음 확인"]
        level = reading.get("small_candidate_level")
        if level is not None:
            next_text += f" · 현재 소파동 후보 확인선 {float(level):g}(기존 폭 조건도 충족해야 확정)"
        reference = reading.get("ma10_next_reference")
        if reference is not None:
            next_text += f" · 다음 종가가 {float(reference):,}보다 높으면 MA10 상승, 같으면 평탄, 낮으면 하락"
        if value["next_close"] is not None:
            next_text = f"다음 {tf} 마감 {_time(value['next_close'])} · " + next_text
        frame = frames[tf]
        basis = frame.attrs.get("energy_basis", "마감봉 기준")
        leg_text = f"대파동 방향 구간 시작 {_time(reading['leg_start_time'])}"
        if tf == "4d":
            basis += f" · 일봉 집계 기준 시작 {_time(frame.attrs['energy_origin'])}"
            label = frame.attrs["energy_chart_labels"][reading["leg_start_pos"]]
            leg_text += f" · 해당 봉의 차트 라벨 {_time(label)}"
        items = [
            ("선정 이유", reason),
            ("현재 판단", f"MA10 {row['MA10']} · 대파동과 {row['대파동·MA10']} · 중파동 K {row['중파동 K']}"),
            ("관계 근거", "소파동 반전 근거를 먼저 관찰하고 대파동 K·MA10 방향을 따로 확인합니다. 대파동 하락과 MA10 하락은 동치가 아닙니다."),
            ("다음 확인", next_text),
            ("관찰 구간", leg_text),
            ("자료 기준", f"{basis} · 마지막 마감 {_time(value['last_close'])}"),
            ("해석 범위", "반전 근거가 아직 없다는 관측입니다. 쌍바닥 전까지 반드시 하락한다는 예측·매매 신호는 아니며, 대파동·MA10이 엇갈리면 해석을 재검토합니다."),
        ]
        card = {"interval": tf, "title": f"{tf} 파동 에너지 관찰", "items": items,
                "related": {}, "next_check_at": value["next_close"],
                "snapshot": {"phase": reading["state"], "large": reading["large_direction"],
                             "small": f"{reading.get('small_status')}|{reading.get('small_confirm_time')}",
                             "ma10": reading.get("ma10_direction"),
                             "leg": str(reading.get("leg_start_time")), "data": value["issue"],
                             "grid": str(frame.attrs.get("energy_origin", "native"))}}
        card = apply_trend_context(card, context, reading.get("ma10_direction", "unknown"), period=10)
    return {"table": pd.DataFrame(rows), "card": card, "asof": pd.Timestamp(asof), "readings": readings,
            "trend": build_trend_view(context)}


def prepare_energy_view(symbol: str, raw_frames: dict, asof) -> dict:
    """차트와 같은 원본·조회 시각에서 큰 추세와 에너지 관측을 함께 준비한다."""
    from data.binance import fetch_klines, get_auto_limit
    from data.processor import build_dataframe
    from display.energy_frames import prepare_energy_frames

    energy_raw = dict(raw_frames)
    # 4d 차트와 동일한 일봉 조회 길이·리샘플 위상을 공유한다.
    daily = fetch_klines(symbol, "1d", get_auto_limit("4d"))
    energy_raw["1d"] = build_dataframe(daily) if daily else None
    return build_energy_view(prepare_energy_frames(energy_raw, asof), asof)


def render_energy_observation(
    symbol: str, raw_frames: dict, asof, on_open_chart=None, prepared_view=None, *, show_observation: bool = True,
) -> dict:
    """명시적 조회의 view를 종목별로 저장하고 선택적으로 표시한다."""
    view = prepared_view if prepared_view is not None else prepare_energy_view(symbol, raw_frames, asof)
    if show_observation and prepared_view is None:
        render_trend_context(view["trend"])
    if show_observation:
        st.markdown(f"### {TITLE}")
        st.caption(CAPTION)
    if view["card"] is not None:
        guide = render_guidance(view["card"], symbol=symbol, scope="energy_radar", on_open_chart=on_open_chart,
                                show_card=show_observation)
        view["card"] = guide["card"]
        text = guide["text"]
        view.update(change=guide["change"], changed=guide["changed"])
    else:
        text = "현재 해석 가능한 파동 에너지 관찰 대상이 없습니다. 표에서 자료 상태를 확인하세요."
        view.update(change="", changed=False)
        if show_observation:
            st.info(text)
    if show_observation:
        st.dataframe(view["table"], hide_index=True, width="stretch")
    view["text"] = f"### {TITLE}\n\n{CAPTION}\n\n{text}"
    st.session_state[f"wave_energy_observation:{symbol}"] = deepcopy(view)
    return view


def render_saved_energy_observation(symbol: str, on_open_chart=None) -> None:
    """차트 시간봉과 독립적으로 마지막 에너지 레이더 결과를 유지한다."""
    from display.mtf_guidance import _draw_guidance

    saved = st.session_state.get(f"wave_energy_observation:{symbol}")
    if saved is None:
        return
    with st.expander(TITLE, expanded=False):
        st.caption(f"레이더 조회 기준: {_time(saved['asof'])}")
        card = deepcopy(saved["card"])
        if card is not None:
            now, next_check = pd.Timestamp.now(tz="UTC"), card.get("next_check_at")
            if next_check is not None and now >= pd.Timestamp(next_check):
                card["items"] = [(label, "확인 시각이 지났습니다. 큰 추세를 다시 조회한 뒤 해석하세요."
                                  if label in ("다음 확인", "추세 안의 해석", "관찰 방향 해석", *TURNING_LABELS) else value)
                                 for label, value in card["items"]]
            _draw_guidance(card, symbol=symbol, scope="saved_energy", change="마지막 에너지 관찰 결과입니다.",
                           changed=False, on_open_chart=on_open_chart)
        table = saved["table"].copy()
        deadline = saved.get("trend", {}).get("context", {}).get("next_check_at")
        if deadline is not None:
            stamp = pd.Timestamp(deadline)
            stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
            if pd.Timestamp.now(tz="UTC") >= stamp and "추세 안의 해석" in table:
                table["추세 안의 해석"] = "조회 기준 만료 — 큰 추세 재확인 필요"
        st.dataframe(table, hide_index=True, width="stretch")
