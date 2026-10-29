"""4d 변곡 준비를 큰 추세 방향과 구분하고 저장 화면에서도 같은 근거를 유지한다."""
from copy import deepcopy

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


TURNING_LABELS = (
    "4d 변곡 준비", "4d MA10 기울기", "4d MA5·MA10", "4d MACD·시그널", "변곡 다음 확인",
)


def _context(asof=None):
    from analysis.trend_context import build_trend_context

    stamp = pd.Timestamp.now(tz="UTC") if asof is None else pd.Timestamp(asof)
    stamp = stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo is not None else stamp
    last_daily_close = stamp.normalize()
    values = list(range(100, 188)) + [188, 190, 200, 210, 220, 212, 210, 208, 206, 204, 202, 200]
    frames = {}
    for interval, days, close_values, last_close in (
        ("4d", 4, values, last_daily_close - pd.Timedelta(days=1)),
        ("1d", 1, list(range(100, 180)), last_daily_close),
    ):
        closes = pd.date_range(end=last_close, periods=len(close_values), freq=f"{days}D")
        frame = pd.DataFrame({"close": close_values}, index=closes-pd.Timedelta(days=days))
        frame.attrs.update(energy_bar_closes=closes, energy_chart_labels=frame.index,
                           energy_issue="", energy_origin=frame.index[0])
        frames[interval] = frame
    return build_trend_context(frames, stamp)


def _card(interval="1h"):
    return {
        "interval": interval, "title": f"{interval} 관찰 설명", "related": {},
        "items": [("선정 이유", "소파동 쌍바닥 확정"), ("다음 확인", "다음 봉 방향 확인")],
        "snapshot": {"phase": "SMALL_CONFIRMED"}, "observation_directions": ["up", "down"],
        "next_check_at": pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=10),
    }


def _screen(at):
    return "\n".join(entry.value for kind in (at.markdown, at.caption, at.info, at.warning) for entry in kind)


def _run(source, state):
    at = AppTest.from_string(source)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, [entry.value for entry in at.exception]
    return at


_RENDER_APP = """
import streamlit as st
from display.trend_context import build_trend_view, render_trend_context
view = build_trend_view(st.session_state['context'])
render_trend_context(view)
st.code(view['text'])
"""


def test_bearish_preparation_does_not_change_the_rising_primary_or_agreed_trend():
    from display.trend_context import build_trend_view

    context = _context()
    assert context["turning"]["state"] == "BEARISH_PREP"
    assert context["primary"]["direction"] == context["direction"] == "up"
    assert context["status"] == "ALIGNED"
    view = build_trend_view(context)
    items = dict(view["items"])
    assert all(label in items for label in TURNING_LABELS)
    assert "변곡 준비" in items["4d 변곡 준비"]
    assert "상승" in items["4d 변곡 준비"]
    assert "둔화" in items["4d MA10 기울기"]
    assert "1.4" in items["4d MA10 기울기"]
    assert "207.2" in items["4d MA5·MA10"]
    assert "204" in items["4d MA5·MA10"]
    assert "MA10" in items["변곡 다음 확인"]
    assert any(word in items["변곡 다음 확인"] for word in ("재상향", "재교차", "회복"))


def test_turning_screen_and_copy_include_the_same_five_explanations():
    from display.trend_context import build_trend_view

    context = _context()
    view = build_trend_view(context)
    at = _run(_RENDER_APP, {"context": context})
    rendered, copied = _screen(at), at.code[0].value
    for label, text in view["items"]:
        assert f"**{label}**: {text}" in rendered
        assert f"**{label}**: {text}" in copied


def test_crosses_on_different_bars_show_each_actual_close_and_age():
    from display.trend_context import build_trend_view
    from utils.time_display import to_kst

    context = _context()
    turning = context["turning"]
    last_close = turning["last_close"]
    ma_time, macd_time = last_close-pd.Timedelta(days=4), last_close-pd.Timedelta(days=12)
    turning["ma_cross"] = {"kind": "dead", "time": ma_time, "bars_ago": 1}
    turning["macd_cross"] = {"kind": "dead", "time": macd_time, "bars_ago": 3}
    items = dict(build_trend_view(context)["items"])
    for label, stamp, age in (("4d MA5·MA10", ma_time, 1), ("4d MACD·시그널", macd_time, 3)):
        text = items[label]
        assert "데드크로스" in text
        assert f"{age}봉 전" in text
        assert f"{to_kst(stamp):%Y-%m-%d %H:%M}" in text
        assert "이번" not in text


def test_this_close_cross_is_distinguished_from_a_previous_close_cross():
    from display.trend_context import build_trend_view

    context = _context()
    past = dict(build_trend_view(context)["items"])["4d MA5·MA10"]
    assert "1봉 전" in past
    context["turning"]["ma_cross"] = {
        "kind": "dead", "time": context["turning"]["last_close"], "bars_ago": 0,
    }
    current = dict(build_trend_view(context)["items"])["4d MA5·MA10"]
    assert "이번" in current or "0봉 전" in current
    assert current != past


def test_local_card_keeps_its_owner_and_adds_preparation_to_current_and_candidate_context():
    from display.trend_context import apply_trend_context

    source, context = _card(), _context()
    original = deepcopy(source)
    result = apply_trend_context(source, context, "down", period=10)
    items = dict(result["items"])
    assert result["interval"] == source["interval"] == "1h"
    assert source == original
    assert "변곡 준비" in items["4d 변곡 준비"]
    assert "상승 추세" in items["추세 안의 해석"] and "조정" in items["추세 안의 해석"]
    assert "변곡 준비" in items["추세 안의 해석"]
    assert "변곡 준비" in items["관찰 방향 해석"]
    assert result["snapshot"]["trend"]["turning"] == context["snapshot"]["turning"]


def test_recovered_conditions_remove_the_previous_preparation_summary():
    from display.trend_context import build_trend_view

    context = _context()
    old = dict(build_trend_view(context)["items"])["4d 변곡 준비"]
    context["turning"].update(state="NO_PREP", ma10_slowing=False,
                              ma_relation="above", macd_relation="above")
    context["turning"]["ma_cross"] = {
        "kind": "golden", "time": context["turning"]["last_close"], "bars_ago": 0,
    }
    context["turning"]["macd_cross"] = context["turning"]["ma_cross"].copy()
    items = dict(build_trend_view(context)["items"])
    assert items["4d 변곡 준비"] != old
    assert "골든크로스" in items["4d MA5·MA10"]
    assert "골든크로스" in items["4d MACD·시그널"]


def test_older_context_without_turning_remains_renderable():
    from display.trend_context import apply_trend_context, build_trend_view

    context = _context()
    context.pop("turning")
    context["snapshot"].pop("turning", None)
    view = build_trend_view(context)
    assert "주 추세 기준 · 4d MA10" in dict(view["items"])
    interpretation = dict(apply_trend_context(_card(), context, "up")["items"])["추세 안의 해석"]
    assert "상승" in interpretation or "같은 방향" in interpretation
    at = _run(_RENDER_APP, {"context": context})
    assert "MA10" in at.code[0].value


_SAVED_TREND_APP = """
import streamlit as st
from display.trend_context import render_saved_trend_context
render_saved_trend_context(st.session_state.get('symbol', 'BTCUSDT'))
"""


def test_saved_preparation_is_readonly_and_does_not_follow_chart_tf(monkeypatch):
    from data import binance
    from display.trend_context import build_trend_view

    def no_fetch(*_args, **_kwargs):
        raise AssertionError("저장된 변곡 근거를 재생할 때 새 수신을 하면 안 됨")

    no_fetch.clear = binance.fetch_klines.clear
    monkeypatch.setattr(binance, "fetch_klines", no_fetch)
    saved = {"asof": pd.Timestamp.now(tz="UTC"), "trend": build_trend_view(_context())}
    at = _run(_SAVED_TREND_APP, {"wave_energy_observation:BTCUSDT": saved})
    before = deepcopy(at.session_state.filtered_state)
    shown = _screen(at)
    assert "변곡 준비" in shown
    at.session_state["sidebar_interval"] = "15m"
    at.run()
    assert not at.exception and _screen(at) == shown
    before["sidebar_interval"] = "15m"
    assert at.session_state.filtered_state == before
    at.session_state["symbol"] = "ETHUSDT"
    at.run()
    assert not at.exception and shown not in _screen(at)
    at.session_state["symbol"] = "BTCUSDT"
    at.run()
    assert not at.exception and _screen(at) == shown


@pytest.mark.parametrize("surface", ("trend", "radar", "energy"))
def test_expired_saved_surfaces_hold_preparation_and_keep_source_unchanged(surface):
    from display.trend_context import apply_trend_context, build_trend_view

    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)
    context = _context(past)
    trend = build_trend_view(context)
    card = apply_trend_context(_card(), context, "down", period=10)
    saved = {
        "asof": past, "trend": trend, "card": card,
        "table": pd.DataFrame([{"TF": "1h", "추세 안의 해석": "상승 추세 내 조정 관찰"}]),
    }
    key = "wave_energy_observation:BTCUSDT"
    state = {key: saved}
    old_summary = dict(card["items"])["4d 변곡 준비"]
    if surface == "trend":
        source = _SAVED_TREND_APP
        old_summary = dict(trend["items"])["4d 변곡 준비"]
    elif surface == "radar":
        source = """
import streamlit as st
from display.mtf_guidance import render_saved_observation
view = render_saved_observation('BTCUSDT')
st.code(view['text'])
"""
        state = {"mtf_radar_observation:BTCUSDT": {"asof": past, "view": {"card": card}}}
    else:
        source = """
from display.energy_observation import render_saved_energy_observation
render_saved_energy_observation('BTCUSDT')
"""
    at = _run(source, state)
    shown = _screen(at)
    assert old_summary not in shown
    assert any(word in shown for word in ("재조회", "다시 조회", "재확인"))
    assert any(word in shown for word in ("지났", "만료"))
    if surface == "radar":
        assert old_summary not in at.code[0].value
    if surface == "trend":
        assert at.session_state[key]["trend"]["items"] == saved["trend"]["items"]
    elif surface == "energy":
        assert at.session_state[key]["card"]["items"] == saved["card"]["items"]
        pd.testing.assert_frame_equal(at.session_state[key]["table"], saved["table"])
    else:
        assert at.session_state["mtf_radar_observation:BTCUSDT"]["view"]["card"]["items"] == card["items"]
