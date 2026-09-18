"""데이터 새로고침 버튼(signal-alarm) — 캐시 무효화·수신 시각 기록·캡션 형식. 네트워크·런타임 없이 돈다."""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data.binance as B
import main as M


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_records_real_receive_time_only_on_success(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return _Resp([[1, "1", "2", "0.5", "1.5", "10", 2, "0", 1, "0", "0", "0"]] if params["symbol"] != "BAD" else [])

    monkeypatch.setattr(B.requests, "get", fake_get)
    B.fetch_klines.clear()
    B._LAST_FETCH_AT.clear()
    assert B.last_fetch_at("TESTUSDT", "1h") is None
    t0 = time.time()
    assert B.fetch_klines("TESTUSDT", "1h", 5)
    t1 = B.last_fetch_at("TESTUSDT", "1h")
    assert t1 is not None and t0 <= t1 <= time.time()
    # 캐시 히트: 요청도 시각 갱신도 없다
    assert B.fetch_klines("TESTUSDT", "1h", 5) and len(calls) == 1 and B.last_fetch_at("TESTUSDT", "1h") == t1
    # 캐시를 비우면 다시 받고 시각이 갱신된다
    B.clear_klines_cache()
    time.sleep(0.01)
    assert B.fetch_klines("TESTUSDT", "1h", 5) and len(calls) == 2 and B.last_fetch_at("TESTUSDT", "1h") > t1
    # 빈 응답(실패)은 None 이고 시각을 기록하지 않는다
    assert B.fetch_klines("BAD", "1h", 5) is None and B.last_fetch_at("BAD", "1h") is None


def test_clear_klines_cache_clears_only_fetch_functions(monkeypatch):
    cleared = []
    monkeypatch.setattr(B.fetch_klines, "clear", lambda: cleared.append("fetch_klines"))
    monkeypatch.setattr(B.fetch_klines_paginated, "clear", lambda: cleared.append("fetch_klines_paginated"))
    B.clear_klines_cache()
    assert cleared == ["fetch_klines", "fetch_klines_paginated"]


def test_freshness_caption_format():
    ts = time.mktime((2026, 9, 19, 6, 30, 12, 0, 0, -1))
    assert M.data_freshness_caption(ts, pd.Timestamp("2026-09-19 06:00")) == "마지막 로드 2026-09-19 06:30:12 · 마지막 봉 09-19 06:00"
    assert M.data_freshness_caption(None, None) == "마지막 로드 — · 마지막 봉 —"


def test_main_wires_refresh_button_without_autorefresh():
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert M.REFRESH_BUTTON_LABEL == "🔄 데이터 새로고침"
    assert M.REFRESH_RESET_NOTE == "새로고침 시 차트 줌·확대 상태가 초기화됩니다."
    # 클릭 → 데이터 계층 캐시만 비움(st.cache_data.clear 전체 삭제 아님), rerun 은 버튼 클릭 자체
    assert "if st.sidebar.button(REFRESH_BUTTON_LABEL" in body and "clear_klines_cache()" in body
    assert "st.cache_data.clear()" not in body and "st.rerun()" not in body
    # 사이드바 상단(대상 헤더 앞), 캡션은 적재 뒤 채움
    assert body.index("freshness_slot = render_refresh_button()") < body.index('st.sidebar.header("대상")')
    assert 'cfg["freshness_slot"].caption(' in body and "last_fetch_at(symbol, get_fetch_interval(interval))" in body
    # 자동 주기 갱신 없음
    assert "autorefresh" not in body.lower() and "st_autorefresh" not in body
