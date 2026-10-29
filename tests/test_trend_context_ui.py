"""큰 추세를 먼저 제시하고 하위 움직임 해석·저장 시점을 일치시킨다."""
from copy import deepcopy

import pandas as pd
from streamlit.testing.v1 import AppTest

from test_page_render_smoke import app


def _frames(primary="down", reference="down", asof=None):
    asof = pd.Timestamp(asof if asof is not None else pd.Timestamp.now(tz="UTC"))
    if asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    daily_close = asof.normalize()
    frames = {}
    for interval, direction, count, days, last_close in (
        ("4d", primary, 30, 4, daily_close - pd.Timedelta(days=1)),
        ("1d", reference, 80, 1, daily_close),
    ):
        closes = pd.date_range(end=last_close, periods=count, freq=f"{days}D")
        values = list(range(100, 100+count))
        if direction == "down":
            values.reverse()
        elif direction == "flat":
            values = [100] * count
        frame = pd.DataFrame({"close": values}, index=closes-pd.Timedelta(days=days))
        frame.attrs.update(energy_bar_closes=closes, energy_chart_labels=frame.index,
                           energy_issue="", energy_origin=frame.index[0])
        frames[interval] = frame
    return frames, asof


def _context(primary="down", reference="down", asof=None):
    from analysis.trend_context import build_trend_context

    frames, asof = _frames(primary, reference, asof)
    return build_trend_context(frames, asof)


def _card(interval="1h"):
    return {"interval": interval, "title": f"{interval} 관찰 설명", "related": {},
            "items": [("선정 이유", "소파동 쌍바닥 확정"), ("다음 확인", "다음 봉의 방향 확인")],
            "snapshot": {"phase": "SMALL_CONFIRMED"},
            "next_check_at": pd.Timestamp("2030-01-10T00:00:00Z")}


def _items(card):
    return dict(card["items"])


def test_lower_rise_is_a_countertrend_rally_and_lower_fall_a_pullback():
    from display.trend_context import apply_trend_context

    source = _card()
    original = deepcopy(source)
    down = _context(asof="2030-01-01T12:00:00Z")
    rally = apply_trend_context(source, down, "up", period=10)
    assert "하락 추세" in _items(rally)["추세 안의 해석"]
    assert "반등" in _items(rally)["추세 안의 해석"]
    assert source == original

    up = _context("up", "up", asof="2030-01-01T12:00:00Z")
    pullback = apply_trend_context(source, up, "down", period=10)
    assert "상승 추세" in _items(pullback)["추세 안의 해석"]
    assert "조정" in _items(pullback)["추세 안의 해석"]
    assert rally["snapshot"] != pullback["snapshot"]


def test_conflicting_or_missing_trend_avoids_a_countertrend_conclusion():
    from display.trend_context import apply_trend_context
    from analysis.trend_context import build_trend_context

    conflict = apply_trend_context(_card(), _context("down", "up"), "up", period=10)
    assert "충돌" in _items(conflict)["추세 안의 해석"]
    assert "하락 추세 내 반등" not in _items(conflict)["추세 안의 해석"]
    missing = apply_trend_context(_card(), build_trend_context({}, pd.Timestamp.now(tz="UTC")), "up", period=10)
    assert "확인" in _items(missing)["추세 안의 해석"]
    assert "하락 추세 내 반등" not in _items(missing)["추세 안의 해석"]


def test_current_with_trend_direction_and_countertrend_candidate_are_not_confused():
    from display.trend_context import apply_trend_context

    card = _card()
    card["observation_directions"] = ["up"]
    result = apply_trend_context(card, _context(), "down", period=60)
    assert "같은 방향" in _items(result)["추세 안의 해석"]
    assert "하락 추세 내 반등" in _items(result)["관찰 방향 해석"]


def test_larger_timeframe_is_not_called_a_lower_timeframe_rally():
    from display.trend_context import apply_trend_context

    higher = apply_trend_context(_card("1w"), _context(), "up", period=10)
    assert "하락 추세 내 반등" not in _items(higher)["추세 안의 해석"]
    assert any(word in _items(higher)["추세 안의 해석"] for word in ("상위", "큰", "별도"))


def test_stale_local_frame_does_not_receive_a_current_countertrend_label():
    from display.trend_context import apply_trend_context

    card = _card()
    card["local_data_status"] = "마감봉 갱신 지연: 데이터 새로고침 필요"
    card["observation_directions"] = ["up"]
    result = apply_trend_context(card, _context(), "up", period=60)
    assert "보류" in _items(result)["추세 안의 해석"]
    assert "하락 추세 내 반등" not in _items(result)["관찰 방향 해석"]


def test_card_recheck_time_includes_the_earliest_trend_reference_close():
    from display.trend_context import apply_trend_context

    context = _context(asof="2030-01-01T12:00:00Z")
    result = apply_trend_context(_card("1w"), context, "up", period=10)
    assert result["next_check_at"] == context["next_check_at"].tz_localize("UTC")
    source = _card()
    source["next_check_at"] = pd.Timestamp("2030-01-01T13:00:00Z")
    result = apply_trend_context(source, context, "up", period=10)
    assert result["next_check_at"] == source["next_check_at"]


_RENDER_APP = """
import streamlit as st
from display.trend_context import build_trend_view, render_trend_context
view = build_trend_view(st.session_state['context'])
render_trend_context(view)
st.code(view['text'])
"""


def test_trend_screen_and_copy_have_the_same_primary_and_reference_explanations():
    at = AppTest.from_string(_RENDER_APP)
    at.session_state["context"] = _context()
    at.run()
    assert not at.exception, [entry.value for entry in at.exception]
    from display.trend_context import build_trend_view
    view = build_trend_view(at.session_state["context"])
    rendered = "\n".join(entry.value for entry in at.markdown)
    copied = at.code[0].value
    for label, explanation in view["items"]:
        assert label in rendered and explanation in rendered
        assert label in copied and explanation in copied
    assert "4d" in copied and "MA10" in copied and "MA60" in copied


_SAVED_APP = """
import streamlit as st
from display.trend_context import render_saved_trend_context
render_saved_trend_context(st.session_state.get('symbol', 'BTCUSDT'))
"""


def _saved_app(context):
    from display.trend_context import build_trend_view

    at = AppTest.from_string(_SAVED_APP)
    at.session_state["wave_energy_observation:BTCUSDT"] = {
        "asof": pd.Timestamp.now(tz="UTC"), "trend": build_trend_view(context),
    }
    at.run()
    assert not at.exception, [entry.value for entry in at.exception]
    return at


def _screen(at):
    return "\n".join(entry.value for kind in (at.markdown, at.caption, at.info, at.warning) for entry in kind)


def test_saved_trend_is_readonly_and_symbol_specific(monkeypatch):
    from data import binance

    def unexpected_fetch(*_args, **_kwargs):
        raise AssertionError("저장 추세 재생에서 새 조회 금지")
    unexpected_fetch.clear = binance.fetch_klines.clear
    monkeypatch.setattr(binance, "fetch_klines", unexpected_fetch)
    at = _saved_app(_context())
    state = deepcopy(at.session_state.filtered_state)
    original = _screen(at)
    at.session_state["sidebar_interval"] = "1h"
    at.run()
    assert not at.exception and _screen(at) == original
    state["sidebar_interval"] = "1h"
    assert at.session_state.filtered_state == state
    at.session_state["symbol"] = "ETHUSDT"
    at.run()
    assert not at.exception and original not in _screen(at)
    at.session_state["symbol"] = "BTCUSDT"
    at.run()
    assert not at.exception and _screen(at) == original


def test_expired_saved_trend_requests_rechecking_instead_of_silent_reuse():
    at = _saved_app(_context(asof=pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)))
    shown = _screen(at)
    assert "재조회" in shown or "다시 조회" in shown
    assert "지났" in shown or "만료" in shown


def test_expired_reference_holds_saved_local_interpretation_even_before_local_close():
    from display.trend_context import apply_trend_context

    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)
    card = _card()
    card["next_check_at"] = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=7)
    annotated = apply_trend_context(card, _context(asof=past), "up", period=10)
    old_interpretation = _items(annotated)["추세 안의 해석"]
    assert "하락 추세 내 반등" in old_interpretation
    source = """
import streamlit as st
from display.mtf_guidance import render_saved_observation
view = render_saved_observation('BTCUSDT')
st.code(view['text'])
"""
    at = AppTest.from_string(source)
    at.session_state["mtf_radar_observation:BTCUSDT"] = {
        "asof": past, "view": {"card": annotated}, "empty_reason": "",
    }
    at.run()
    assert not at.exception, [entry.value for entry in at.exception]
    assert old_interpretation not in _screen(at)
    assert "추세 안의 해석" in _screen(at) and "다시 조회" in _screen(at)
    assert old_interpretation not in at.code[0].value


def test_observation_tab_presents_global_trend_before_local_guidance_and_alarm_copy_preserves_it(app):
    import main
    from display.trend_context import TITLE

    text = app.code[0].value
    assert not any(TITLE in entry.value for entry in app.tabs[1].markdown)
    assert not any(entry.value.startswith("**선정 이유**") for entry in app.tabs[1].markdown)
    app.session_state[main.ACTIVE_TAB_KEY] = "추세·관찰"
    app.run()
    assert not app.exception, [entry.value for entry in app.exception]
    visible = [entry.value for entry in app.tabs[2].markdown]
    trend_at = next(i for i, text in enumerate(visible) if TITLE in text)
    local = [i for i, text in enumerate(visible) if text.startswith("**선정 이유**")]
    assert local and trend_at < min(local)
    assert TITLE in text and "4d" in text and "MA10" in text and "MA60" in text
    for entry in visible[trend_at+1:]:
        if entry.startswith("**") and "추세" in entry:
            assert entry in text
            break
    tables = [entry.value for entry in app.dataframe if "추세 안의 해석" in entry.value.columns]
    assert tables
