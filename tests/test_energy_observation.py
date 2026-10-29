"""에너지 관측의 설명·4d 연결·저장 결과 재생 계약."""
from copy import deepcopy

import pandas as pd
from streamlit.testing.v1 import AppTest

from display.energy_frames import prepare_energy_frames
from display.energy_observation import TITLE, build_energy_view
from test_page_render_smoke import _synthetic_klines, app


def test_actual_indicator_disagreement_is_preserved_in_the_energy_table():
    from indicators.moving_averages import add_moving_averages
    from indicators.stochastic import add_stochastic_slow_layers

    close = pd.Series(range(100, 200), dtype=float)
    frame = pd.DataFrame({"open": close, "high": close+1, "low": close-1, "close": close})
    frame.loc[99, "high"] = 299
    frame.index = pd.date_range("2026-01-01", periods=100, freq="1h")
    frame = add_stochastic_slow_layers(add_moving_averages(frame))
    frame.attrs["energy_bar_closes"] = frame.index + pd.Timedelta(hours=1)
    frame.attrs["energy_issue"] = ""
    view = build_energy_view({"1h": frame}, frame.index[-1] + pd.Timedelta(hours=1))
    row = view["table"].iloc[0]
    assert row["대파동 K"] == "하락" and row["MA10"] == "상승"
    assert row["대파동·MA10"] == "방향 불일치"


def test_energy_view_contains_safe_four_day_observation_with_actual_closes():
    from data.processor import build_dataframe

    raw = build_dataframe(_synthetic_klines("1d", 1000))
    asof = pd.Timestamp.now(tz="UTC")
    frames = prepare_energy_frames({"1d": raw}, asof)
    view = build_energy_view(frames, asof)
    assert "4d" in set(view["table"]["TF"])
    last = frames["4d"].attrs["energy_bar_closes"][-1]
    assert view["readings"]["4d"]["last_close"] == last
    assert view["readings"]["4d"]["next_close"] == last.tz_localize("UTC") + pd.Timedelta(days=4)


def test_saved_energy_replay_is_independent_of_chart_tf_and_holds_expired_condition():
    source = """
import streamlit as st
from display.energy_observation import render_saved_energy_observation
render_saved_energy_observation('BTCUSDT')
"""
    past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)
    card = {"interval": "4d", "title": "4d 파동 에너지 관찰", "related": {}, "next_check_at": past,
            "items": [("선정 이유", "대파동 하락·소파동 쌍바닥 대기"), ("다음 확인", "이전 비교 종가 100")],
            "snapshot": {"phase": "WAIT_SMALL"}}
    saved = {"asof": past, "card": card, "table": pd.DataFrame([{"TF": "4d", "관찰 상태": "소파동 반전 근거 대기"}])}
    at = AppTest.from_string(source)
    at.session_state["wave_energy_observation:BTCUSDT"] = deepcopy(saved)
    at.run()
    assert not at.exception
    shown = "\n".join(item.value for item in at.markdown)
    assert "대파동 하락·소파동 쌍바닥 대기" in shown
    assert "이전 비교 종가 100" not in shown and "확인 시각이 지났" in shown
    for tf in ("1h", "4h"):
        at.session_state["sidebar_interval"] = tf
        at.run()
        assert not at.exception
        assert "대파동 하락·소파동 쌍바닥 대기" in "\n".join(item.value for item in at.markdown)
        stored = at.session_state["wave_energy_observation:BTCUSDT"]
        assert stored["card"] == card


def test_observation_tab_energy_table_matches_alarm_copy_with_four_day_observation(app):
    assert not any("대파동·MA10" in item.value.columns for item in app.dataframe)
    copied = app.code[0].value
    assert TITLE in copied
    app.session_state["main_active_tab"] = "추세·관찰"
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    tables = [item.value for item in app.tabs[2].dataframe if "대파동·MA10" in item.value.columns]
    assert len(tables) == 1 and "4d" in set(tables[0]["TF"])
    from display.alarm_copy_text import text_table
    assert text_table(tables[0]) in copied
