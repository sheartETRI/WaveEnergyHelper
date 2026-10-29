"""추세·관찰 탭은 저장된 판단을 재생하고 명시적 조회에서만 새로 스캔한다."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

import data.binance as binance
import data.frames as frames
import main
from test_page_render_smoke import _Resp, _synthetic_klines


def _new_app():
    at = AppTest.from_file(str(Path(main.__file__)), default_timeout=180)
    at.session_state[main.ACTIVE_TAB_KEY] = "추세·관찰"
    return at


def _check(at):
    at.run()
    assert not at.exception, [entry.value for entry in at.exception]
    assert [tab.label for tab in at.tabs] == list(main.MAIN_TABS)
    return at


def _screen(at):
    return "\n".join(entry.value for kind in (at.markdown, at.caption, at.info, at.warning) for entry in kind)


def _forbid_data_load(monkeypatch):
    def no_data(*_args, **_kwargs):
        raise AssertionError("관찰 탭 재생은 차트 적재나 네트워크 조회를 하면 안 됩니다")

    monkeypatch.setattr(frames, "load_frame", no_data)
    monkeypatch.setattr(binance.requests, "get", no_data)


def test_unscanned_observation_tab_is_available_without_any_data_load(monkeypatch):
    _forbid_data_load(monkeypatch)
    at = _check(_new_app())
    assert at.button(key="observation_scan:BTCUSDT").label == "관찰 TF 찾기"
    assert "아직 레이더를 조회하지 않았습니다" in _screen(at)
    assert not at.dataframe and not at.code


def test_saved_observation_replay_keeps_the_owner_across_chart_tf_and_symbol_changes(monkeypatch):
    from display.trend_context import build_trend_view
    from test_trend_context_ui import _context

    _forbid_data_load(monkeypatch)
    at = _new_app()
    card = {
        "interval": "4h", "title": "4h 관찰 설명", "related": {},
        "items": [("선정 이유", "저장된 4h 대파동 쌍바닥으로 MA60 전환 관찰")],
        "next_check_at": pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4),
        "snapshot": {"up": "대기 중"},
    }
    now = pd.Timestamp.now(tz="UTC")
    saved_radar = {"asof": now, "view": {"card": card}, "empty_reason": ""}
    saved_energy = {
        "asof": now, "card": None, "trend": build_trend_view(_context()),
        "table": pd.DataFrame([{"TF": "4h", "추세 안의 해석": "하락 추세 내 반등 관찰"}]),
    }
    at.session_state["mtf_radar_observation:BTCUSDT"] = deepcopy(saved_radar)
    at.session_state["wave_energy_observation:BTCUSDT"] = deepcopy(saved_energy)
    _check(at)
    shown = _screen(at)
    assert card["items"][0][1] in shown
    assert at.button(key="observation_scan:BTCUSDT").label == "레이더 다시 조회"
    for interval in ("1h", "4d"):
        at.selectbox(key=main.INTERVAL_KEY).select(interval)
        _check(at)
        assert _screen(at) == shown
        assert at.session_state["mtf_radar_observation:BTCUSDT"] == saved_radar
        pd.testing.assert_frame_equal(at.session_state["wave_energy_observation:BTCUSDT"]["table"], saved_energy["table"])
        assert at.session_state["wave_energy_observation:BTCUSDT"]["trend"]["items"] == saved_energy["trend"]["items"]

    at.selectbox(key=main.SYMBOL_KEY).select("ETHUSDT")
    _check(at)
    assert card["items"][0][1] not in _screen(at)
    assert at.button(key="observation_scan:ETHUSDT").label == "관찰 TF 찾기"
    at.selectbox(key=main.SYMBOL_KEY).select("BTCUSDT")
    _check(at)
    assert _screen(at) == shown


def test_explicit_scan_runs_in_observation_tab_and_subsequent_replays_do_not_scan(monkeypatch):
    import display.observation_tab as observation
    import display.wave_basis_radar as basis
    from display.analysis_cache import clear_analysis_cache

    calls, clears, requests, responses = [], [], [], {}
    original_scan, original_clear = basis.render_basis_radar_section, binance.clear_klines_cache

    def no_chart(*_args, **_kwargs):
        raise AssertionError("관찰 조회에 선택된 차트 TF 적재는 필요하지 않습니다")

    def get(_url, params=None, **_kwargs):
        params = params or {}
        interval, limit = params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)
        requests.append((interval, limit))
        return _Resp(responses.setdefault((interval, limit), _synthetic_klines(interval, limit+2)[-limit:]))

    def scan(*args, **kwargs):
        calls.append(kwargs)
        return original_scan(*args, **kwargs)

    def clear():
        clears.append(True)
        original_clear()

    monkeypatch.setattr(frames, "load_frame", no_chart)
    monkeypatch.setattr(binance.requests, "get", get)
    monkeypatch.setattr(observation, "clear_klines_cache", clear)
    monkeypatch.setattr(observation, "render_basis_radar_section", scan)
    clear_analysis_cache()
    at = _check(_new_app())
    assert not requests and not calls and not clears
    at.button(key="observation_scan:BTCUSDT").click()
    _check(at)
    assert at.session_state[main.ACTIVE_TAB_KEY] == "추세·관찰"
    assert len(calls) == len(clears) == 1
    assert calls[0]["show_observation"] is False and calls[0]["show_radar"] is False
    assert requests and "mtf_radar_observation:BTCUSDT" in at.session_state
    assert "wave_energy_observation:BTCUSDT" in at.session_state
    assert "큰 추세 먼저 보기" in _screen(at)
    assert at.button(key="observation_scan:BTCUSDT").label == "레이더 다시 조회"
    request_count = len(requests)
    saved_radar = deepcopy(at.session_state["mtf_radar_observation:BTCUSDT"])
    at.selectbox(key=main.INTERVAL_KEY).select("4d")
    _check(at)
    assert len(calls) == len(clears) == 1 and len(requests) == request_count
    assert at.session_state["mtf_radar_observation:BTCUSDT"] == saved_radar


def test_chart_load_failure_does_not_hide_the_observation_tab(monkeypatch):
    loads = []

    def missing(*args, **_kwargs):
        loads.append(args)
        return None

    monkeypatch.setattr(frames, "load_frame", missing)
    at = AppTest.from_file(str(Path(main.__file__)), default_timeout=30)
    _check(at)
    assert at.error and len(loads) == 1
    at.session_state[main.ACTIVE_TAB_KEY] = "추세·관찰"
    _check(at)
    assert len(loads) == 1
    assert at.button(key="observation_scan:BTCUSDT").label == "관찰 TF 찾기"


def test_hidden_radar_builds_the_same_export_and_saved_views_without_rendering_explanations(monkeypatch):
    import display.wave_basis_radar as basis
    from display.analysis_cache import clear_analysis_cache

    fixed_asof = pd.Timestamp.now(tz="UTC")
    responses = {}

    class Clock:
        @staticmethod
        def now(**_kwargs):
            return fixed_asof

    def get(_url, params=None, **_kwargs):
        params = params or {}
        interval, limit = params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)
        return _Resp(responses.setdefault((interval, limit), _synthetic_klines(interval, limit+2)[-limit:]))

    monkeypatch.setattr(binance.requests, "get", get)
    monkeypatch.setattr(basis, "pd", SimpleNamespace(Timestamp=Clock, DataFrame=pd.DataFrame))
    clear_analysis_cache()
    source = """
import streamlit as st
from display.wave_basis_radar import render_basis_radar_section
visible = st.session_state['visible']
st.session_state['result'] = render_basis_radar_section(
    'BTCUSDT', show_observation=visible, show_radar=visible,
)
"""
    shown, hidden = (AppTest.from_string(source, default_timeout=180) for _ in range(2))
    shown.session_state["visible"] = True
    hidden.session_state["visible"] = False
    for at in (shown, hidden):
        at.run()
        assert not at.exception, [entry.value for entry in at.exception]
        assert "mtf_radar_observation:BTCUSDT" in at.session_state
        assert "wave_energy_observation:BTCUSDT" in at.session_state
    assert shown.markdown and shown.dataframe
    assert not hidden.markdown and not hidden.subheader and not hidden.caption and not hidden.dataframe and not hidden.info
    first, second = shown.session_state["result"], hidden.session_state["result"]
    assert first["headline"] == second["headline"]
    assert first["guidance"]["text"] == second["guidance"]["text"]
    assert first["energy"]["text"] == second["energy"]["text"]
    assert first["energy"]["trend"]["text"] == second["energy"]["trend"]["text"]
    pd.testing.assert_frame_equal(first["table"], second["table"])
    pd.testing.assert_frame_equal(first["energy"]["table"], second["energy"]["table"])
