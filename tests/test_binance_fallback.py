"""바이낸스 데이터 주소 자동 대체 — api.binance.com 451/403 → data-api.binance.vision 재시도. 네트워크·런타임 없음.

- 451(또는 403) 이면 같은 params 로 대체 주소에 재시도하고, 이후 요청은 대체 주소로 바로 간다(프로세스 동안 고정).
- 정상(200) 이면 원래 주소 유지, 요청 1회.
- 두 주소의 응답은 같은 파서(build_dataframe)를 지나 동일 DataFrame 이 된다.
- 실패 시 last_fetch_error 에 HTTP 상태 코드·시도한 주소가 남고, 화면 오류 메시지에 그대로 실린다.
"""
import os
import sys

import pandas as pd
import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data.binance as B  # noqa: E402
import main as M  # noqa: E402
from config.settings import BINANCE_BASE_URL, BINANCE_FALLBACK_URL  # noqa: E402
from data.processor import build_dataframe  # noqa: E402

ROW = [1_700_000_000_000, "1", "2", "0.5", "1.5", "10", 1_700_003_599_999, "0", 1, "0", "0", "0"]
ROW2 = [1_700_003_600_000, "1.5", "2.5", "1", "2", "12", 1_700_007_199_999, "0", 1, "0", "0", "0"]
PAYLOAD = [ROW, ROW2]


class _Resp:
    def __init__(self, status, payload=None, url=""):
        self.status_code = status
        self._payload = payload
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} for url: {self.url}")
            err.response = self
            raise err

    def json(self):
        return self._payload


def _install(monkeypatch, status_by_url):
    """url → HTTP 상태. 호출 기록 [(url, params)] 을 돌려준다. 200 이면 PAYLOAD 를 준다."""
    calls = []

    def fake_get(url, params=None, timeout=None, **kw):
        calls.append((url, dict(params)))
        status = status_by_url[url]
        return _Resp(status, PAYLOAD if status == 200 else {"code": -1, "msg": "blocked"}, url)

    monkeypatch.setattr(B.requests, "get", fake_get)
    return calls


@pytest.fixture(autouse=True)
def _fresh_state():
    B.reset_data_url()
    B.fetch_klines.clear()
    B.fetch_klines_paginated.clear()
    B._LAST_FETCH_AT.clear()
    yield
    B.reset_data_url()
    B.fetch_klines.clear()
    B.fetch_klines_paginated.clear()


@pytest.mark.parametrize("blocked", [451, 403])
def test_blocked_primary_switches_to_fallback_and_stays(monkeypatch, blocked):
    calls = _install(monkeypatch, {BINANCE_BASE_URL: blocked, BINANCE_FALLBACK_URL: 200})

    assert B.fetch_klines("BTCUSDT", "1h", 5) == PAYLOAD
    # 원래 주소 1회 → 같은 params 로 대체 주소 1회
    assert [u for u, _ in calls] == [BINANCE_BASE_URL, BINANCE_FALLBACK_URL]
    assert calls[0][1] == calls[1][1] == {"symbol": "BTCUSDT", "interval": "1h", "limit": 5}
    assert B.active_data_url() == BINANCE_FALLBACK_URL
    assert B.fallback_reason() == f"api.binance.com HTTP {blocked}"
    assert B.last_fetch_error("BTCUSDT", "1h") is None

    # 이후 요청(다른 키 → 캐시 미스)은 대체 주소로 바로 간다 — 원래 주소를 다시 두드리지 않는다
    assert B.fetch_klines("ETHUSDT", "4h", 7) == PAYLOAD
    assert [u for u, _ in calls][2:] == [BINANCE_FALLBACK_URL]
    assert B.data_source_line() == f"데이터 주소 data-api.binance.vision (대체 — api.binance.com HTTP {blocked})"


def test_ok_primary_keeps_original_url(monkeypatch):
    calls = _install(monkeypatch, {BINANCE_BASE_URL: 200, BINANCE_FALLBACK_URL: 200})

    assert B.fetch_klines("BTCUSDT", "1h", 5) == PAYLOAD
    assert [u for u, _ in calls] == [BINANCE_BASE_URL]
    assert B.active_data_url() == BINANCE_BASE_URL
    assert B.fallback_reason() is None
    assert B.data_source_line() == "데이터 주소 api.binance.com"


def test_both_urls_parse_identically(monkeypatch):
    _install(monkeypatch, {BINANCE_BASE_URL: 200, BINANCE_FALLBACK_URL: 200})
    df_primary = build_dataframe(B.fetch_klines("BTCUSDT", "1h", 5))

    B.reset_data_url()
    B.fetch_klines.clear()
    _install(monkeypatch, {BINANCE_BASE_URL: 451, BINANCE_FALLBACK_URL: 200})
    df_fallback = build_dataframe(B.fetch_klines("BTCUSDT", "1h", 5))

    assert B.active_data_url() == BINANCE_FALLBACK_URL
    pd.testing.assert_frame_equal(df_primary, df_fallback)


def test_pagination_page_also_falls_back(monkeypatch):
    calls = _install(monkeypatch, {BINANCE_BASE_URL: 451, BINANCE_FALLBACK_URL: 200})
    assert B._fetch_klines_page("BTCUSDT", "1h", 5, end_time=123) == PAYLOAD
    assert [u for u, _ in calls] == [BINANCE_BASE_URL, BINANCE_FALLBACK_URL]
    assert calls[1][1]["endTime"] == 123
    assert B.active_data_url() == BINANCE_FALLBACK_URL


def test_non_blocking_http_error_is_reported_not_switched(monkeypatch):
    """500 은 대체 대상이 아니다 — None 을 주되 사유(상태 코드·주소)를 남긴다."""
    calls = _install(monkeypatch, {BINANCE_BASE_URL: 500, BINANCE_FALLBACK_URL: 200})
    assert B.fetch_klines("BTCUSDT", "1h", 5) is None
    assert [u for u, _ in calls] == [BINANCE_BASE_URL]
    assert B.active_data_url() == BINANCE_BASE_URL
    assert B.last_fetch_error("BTCUSDT", "1h") == f"HTTP 500 {BINANCE_BASE_URL}"


def test_fallback_also_blocked_reports_fallback_url(monkeypatch):
    _install(monkeypatch, {BINANCE_BASE_URL: 451, BINANCE_FALLBACK_URL: 451})
    assert B.fetch_klines("BTCUSDT", "1h", 5) is None
    assert B.last_fetch_error("BTCUSDT", "1h") == f"HTTP 451 {BINANCE_FALLBACK_URL}"


def test_connection_error_reports_type_and_url(monkeypatch):
    def boom(url, params=None, timeout=None, **kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(B.requests, "get", boom)
    assert B.fetch_klines("BTCUSDT", "1h", 5) is None
    assert B.last_fetch_error("BTCUSDT", "1h") == f"ConnectionError {BINANCE_BASE_URL}"


def test_screen_error_message_includes_reason():
    assert M.load_error_message("BTCUSDT", "1h", None) == "BTCUSDT 1h 데이터를 불러오지 못했습니다."
    msg = M.load_error_message("BTCUSDT", "1h", f"HTTP 451 {BINANCE_BASE_URL}")
    assert msg == f"BTCUSDT 1h 데이터를 불러오지 못했습니다. 원인: HTTP 451 {BINANCE_BASE_URL}"


def test_main_wires_error_reason_and_sidebar_line():
    body = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"), encoding="utf-8").read()
    assert "load_error_message(symbol, interval, last_fetch_error(symbol, get_fetch_interval(interval)))" in body
    assert 'cfg["data_url_slot"].caption(data_source_line())' in body
    # 사이드바: 코드 버전 위젯 바로 아래에 자리를 잡는다
    assert body.index("render_code_version()") < body.index("data_url_slot = st.sidebar.empty()")
