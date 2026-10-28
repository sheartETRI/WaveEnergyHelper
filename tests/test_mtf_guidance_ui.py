"""MTF 설명 카드의 화면·복사 일치와 세션 내 변화 안내를 검증한다."""
from copy import deepcopy
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest


_APP = """
import streamlit as st
from display.mtf_guidance import render_guidance

def open_chart(interval):
    st.session_state['opened_chart'] = interval

view = render_guidance(
    st.session_state['guide_card'],
    symbol=st.session_state.get('guide_symbol', 'BTCUSDT'),
    scope=st.session_state.get('guide_scope', 'test'),
    on_open_chart=open_chart if st.session_state.get('navigation', True) else None,
)
st.code(view['text'])
st.text(st.session_state.get('opened_chart', ''))
"""

_SAVED_APP = """
import streamlit as st
from display.mtf_guidance import remember_radar_observation, render_saved_observation

def open_chart(interval):
    st.session_state['opened_chart'] = interval

def scan():
    st.session_state['scan_requested'] = True

if 'save_payload' in st.session_state:
    payload = st.session_state.pop('save_payload')
    remember_radar_observation(
        payload['symbol'], payload['view'], payload['asof'],
        empty_reason=payload.get('empty_reason', ''),
    )
view = render_saved_observation(
    st.session_state.get('guide_symbol', 'BTCUSDT'),
    on_open_chart=open_chart, on_scan=scan,
)
if view:
    st.code(view['text'])
"""


def _card():
    return {
        "interval": "4h",
        "title": "4h 전환 관찰",
        "items": [
            ("선정 이유", "4h 대파동 쌍바닥 확정으로 MA60 전환을 관찰합니다."),
            ("현재 판단", "마지막 마감봉의 MA60은 하방입니다."),
            ("상위 환경", "1d MA60 하방: 큰 추세와 반등 방향이 다릅니다."),
            ("하위 진행", "1h 반등은 4h 전환 확정을 대신하지 않습니다."),
            ("다음 확인", "다음 4h 마감 종가가 100보다 높으면 MA60 상승입니다."),
            ("자료 기준", "2026-10-28 13:00 KST 마감 기준입니다."),
        ],
        "snapshot": {"lifecycle": "대기 중", "ma_direction": "하방"},
        "related": {"upper": "1d", "lower": "1h"},
        "next_check_at": pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4),
    }


def _app(card=None):
    app = AppTest.from_string(_APP, default_timeout=30)
    app.session_state["guide_card"] = deepcopy(card if card is not None else _card())
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    return app


def test_guidance_screen_and_copy_show_the_same_reason_context_and_condition():
    card = _card()
    app = _app(card)
    rendered = "\n".join(item.value for item in app.markdown)
    copied = app.code[0].value
    for label, content in card["items"]:
        assert label in rendered and content in rendered
        assert label in copied and content in copied


def test_custom_chart_reports_its_base_interval_stale_source(monkeypatch):
    from data import binance

    requested = []
    monkeypatch.setattr(binance, "stale_age", lambda symbol, interval:
                        requested.append(interval) or ("5분 전" if interval == "1h" else None))
    card = _card()
    card["interval"] = "3h"
    card["related"] = {}
    app = _app(card)
    assert requested == ["1h"]
    assert "수신 실패로 저장본 표시: 3h(5분 전)" in app.code[0].value


def test_only_semantic_change_announces_again_and_each_change_is_shown_once():
    app = _app()
    assert not app.info

    # 시각·비교 종가는 매 봉 바뀌어도 관찰 상태가 같으면 재안내하지 않는다.
    updated = _card()
    updated["items"][-1] = ("자료 기준", "2026-10-28 17:00 KST 마감 기준입니다.")
    updated["items"][-2] = ("다음 확인", "다음 4h 마감 종가가 101보다 높으면 MA60 상승입니다.")
    app.session_state["guide_card"] = updated
    app.run()
    assert not app.exception and not app.info

    updated = deepcopy(updated)
    updated["snapshot"] = {"lifecycle": "전환 발생", "ma_direction": "상방"}
    updated["items"][1] = ("현재 판단", "마지막 마감봉의 MA60이 상방으로 바뀌었습니다.")
    app.session_state["guide_card"] = updated
    app.run()
    assert not app.exception and app.info
    assert any(item.value in app.code[0].value for item in app.info)

    app.run()
    assert not app.exception and not app.info


def test_symbol_and_scope_have_independent_observation_history():
    app = _app()
    changed = _card()
    changed["snapshot"] = {"lifecycle": "전환 발생", "ma_direction": "상방"}
    app.session_state["guide_symbol"] = "ETHUSDT"
    app.session_state["guide_card"] = changed
    app.run()
    assert not app.exception and not app.info

    app.session_state["guide_symbol"] = "BTCUSDT"
    app.session_state["guide_card"] = _card()
    app.run()
    assert not app.exception and not app.info

    app.session_state["guide_scope"] = "chart"
    app.session_state["guide_card"] = changed
    app.run()
    assert not app.exception and not app.info


def test_changing_observed_timeframe_announces_new_owner_once():
    app = _app()
    other = _card()
    other["interval"] = "1d"
    other["title"] = "1d 전환 관찰"
    other["related"] = {"upper": "4d", "lower": "4h"}
    app.session_state["guide_card"] = other
    app.run()
    assert not app.exception and app.info
    notice = "\n".join(item.value for item in app.info)
    assert "4h" in notice and "1d" in notice
    assert notice in app.code[0].value

    app.run()
    assert not app.exception and not app.info


def test_chart_buttons_open_owner_upper_and_lower_timeframes():
    app = _app()
    for interval in ("4h", "1d", "1h"):
        button = next(item for item in app.button if interval in item.label)
        button.click().run()
        assert not app.exception
        assert app.session_state["opened_chart"] == interval

    app.session_state["navigation"] = False
    app.run()
    assert not app.exception and not app.button


def _raw_hourly_frame(n=1000):
    from data.processor import build_dataframe
    from test_page_render_smoke import _synthetic_klines

    frame = build_dataframe(_synthetic_klines("1h", n))
    frame.index = pd.date_range(end="2026-10-28 15:00", periods=n, freq="h")
    return frame


def test_cached_unfinished_tail_needs_successor_before_becoming_closed():
    """캐시의15시봉은16시가지나도 재수신 증거 없이 마감값으로 승격하지 않는다."""
    from display.mtf_guidance import prepare_closed_frames

    raw = _raw_hourly_frame(80)
    during = prepare_closed_frames({"1h": raw}, "2026-10-28 15:30Z")["1h"]
    after_clock_only = prepare_closed_frames({"1h": raw}, "2026-10-28 16:01Z")["1h"]
    assert during.index[-1] == pd.Timestamp("2026-10-28 14:00")
    assert after_clock_only.index[-1] == pd.Timestamp("2026-10-28 14:00")

    successor = raw.iloc[[-1]].copy()
    successor.index = pd.DatetimeIndex([pd.Timestamp("2026-10-28 16:00")])
    received = pd.concat([raw, successor])
    confirmed = prepare_closed_frames({"1h": received}, "2026-10-28 16:01Z")["1h"]
    assert confirmed.index[-1] == pd.Timestamp("2026-10-28 15:00")
    assert len(confirmed) == len(during) + 1


def test_unfinished_tail_cannot_change_closed_indicators_or_candidates():
    """미마감 꼬리를 급등락시켜도 마감 기준 피봇·후보에는 영향이 없어야 한다."""
    from display.mtf_guidance import candidate_frames, prepare_closed_frames

    raw = _raw_hourly_frame()
    changed = raw.copy()
    changed.loc[changed.index[-1], ["open", "high", "low", "close"]] = [10000, 20000, 1, 15000]
    original = prepare_closed_frames({"1h": raw}, "2026-10-28 15:30Z")
    altered = prepare_closed_frames({"1h": changed}, "2026-10-28 15:30Z")
    assert_frame_equal(original["1h"], altered["1h"])
    first, second = candidate_frames(original)["1h"], candidate_frames(altered)["1h"]
    assert any(not frame.empty for frame in first), "후보가 있는 합성 시계열이어야 비교가 유효함"
    for expected, actual in zip(first, second):
        assert_frame_equal(expected, actual)


def test_alarm_tab_copy_includes_closed_candle_guidance(monkeypatch):
    """합성 시세로 실제 알람 탭을 실행하여 설명이 복사 경로까지 연결됐는지 확인한다."""
    import data.binance as binance
    import main
    from display.analysis_cache import clear_analysis_cache
    from test_page_render_smoke import _Resp, _synthetic_klines

    responses = {}

    def get(_url, params=None, **_kwargs):
        params = params or {}
        interval = params.get("interval", "1h")
        limit = min(int(params.get("limit", 1000)), 1000)
        # 가용 지연까지 마친 실제 대기 후보가 마감 구간에 남도록 2봉 전진한 시계열을 쓴다.
        payload = responses.setdefault((interval, limit), _synthetic_klines(interval, limit + 2)[-limit:])
        return _Resp(payload)

    monkeypatch.setattr(binance.requests, "get", get)
    clear_analysis_cache()
    app = AppTest.from_file(str(Path(main.__file__)), default_timeout=180)
    app.session_state[main.ACTIVE_TAB_KEY] = "알람"
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    copied = "\n".join(item.value for item in app.code)
    for label in ("선정 이유", "다음 확인", "마감"):
        assert label in copied

    assert all(item.label != "설명할 TF" for item in app.selectbox)
    reason = next(item.value for item in app.markdown if item.value.startswith("**선정 이유**"))
    button = next(item for item in app.button if "관찰 차트 열기" in item.label)
    owner = button.label.split()[0]
    button.click().run()
    assert not app.exception, [item.value for item in app.exception]
    assert app.session_state[main.INTERVAL_KEY] == owner
    assert app.session_state[main.ACTIVE_TAB_KEY] == "차트"
    assert next(item for item in app.selectbox if item.label == "타임프레임").value == owner

    # 보고 있는 차트를 바꿔도 레이더가 고른 대상과 선정 이유는 고정한다.
    for interval in ("4h", "1h"):
        next(item for item in app.selectbox if item.label == "타임프레임").select(interval).run()
        assert not app.exception, [item.value for item in app.exception]
        assert reason in [item.value for item in app.markdown]
        assert any(item.label == f"{owner} 관찰 차트 열기" for item in app.button)
        assert not any(item.label == "설명할 TF" for item in app.selectbox)


def _saved_app(card=None, symbol="BTCUSDT"):
    app = AppTest.from_string(_SAVED_APP, default_timeout=30)
    if card is not None:
        app.session_state["save_payload"] = {
            "symbol": symbol,
            "asof": pd.Timestamp.now(tz="UTC"),
            "view": {"card": deepcopy(card), "text": "저장된 관찰 설명", "change": "첫 관찰", "changed": False},
        }
    app.session_state["guide_symbol"] = symbol
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    return app


def _screen_text(app):
    return "\n".join(item.value for group in (app.markdown, app.info, app.caption, app.warning) for item in group)


def test_initial_chart_observation_requires_a_radar_scan_instead_of_selected_tf_reason():
    app = _saved_app()
    assert "**선정 이유**:" not in _screen_text(app)
    assert app.button
    app.button[0].click().run()
    assert not app.exception and app.session_state["scan_requested"]


def test_empty_radar_result_replaces_old_observation_without_a_fallback_timeframe():
    card = _card()
    app = _saved_app(card)
    assert card["items"][0][1] in _screen_text(app)
    app.session_state["save_payload"] = {
        "symbol": "BTCUSDT", "view": None, "asof": pd.Timestamp.now(tz="UTC"),
        "empty_reason": "관찰 조건을 만족하는 TF 없음",
    }
    app.run()
    assert not app.exception
    assert "관찰 조건을 만족하는 TF 없음" in _screen_text(app)
    assert card["items"][0][1] not in _screen_text(app)
    assert not any("관찰 차트 열기" in item.label for item in app.button)


def test_saved_observation_is_symbol_specific_and_replay_does_not_refresh_source_or_history(monkeypatch):
    from data import binance

    def unexpected_source_check(*_args):
        raise AssertionError("저장 결과 재생은 새 수신 상태를 섞으면 안 됩니다")

    monkeypatch.setattr(binance, "stale_age", unexpected_source_check)
    card = _card()
    app = _saved_app(card)
    state = deepcopy(app.session_state.filtered_state)
    app.run()
    assert not app.exception
    assert app.session_state.filtered_state == state
    assert card["items"][0][1] in _screen_text(app)

    app.session_state["guide_symbol"] = "ETHUSDT"
    app.run()
    assert not app.exception
    assert card["items"][0][1] not in _screen_text(app)
    app.session_state["guide_symbol"] = "BTCUSDT"
    app.run()
    assert not app.exception and card["items"][0][1] in _screen_text(app)


def test_saved_past_confirmation_time_requests_a_new_scan_without_reusing_future_price_condition():
    card = _card()
    card["next_check_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=1)
    app = _saved_app(card)
    shown = _screen_text(app)
    assert card["items"][0][1] in shown
    assert card["items"][-2][1] not in shown
    assert "레이더" in shown and ("지났" in shown or "도래" in shown)
