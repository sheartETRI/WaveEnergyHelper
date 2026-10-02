"""data/binance ↔ OHLCV 저장소 연결 — 요청 수·반환 모양·stale·종전 오류 경로 (SPEC §12). 네트워크·런타임 없음.

가짜 _request_klines 를 주입한다(폴백 로직 바깥). 저장소 경로는 conftest 가 테스트마다 임시 폴더로 돌린다
(WEH_OHLCV_STORE_DIR — 앱·스캔 스크립트·푸시 폴러 공용 해석).
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data.binance as B  # noqa: E402
from config.settings import BINANCE_BASE_URL  # noqa: E402
from data import ohlcv_store  # noqa: E402

H = 3_600_000
T0 = 1_699_999_200_000          # 정시 (UTC 2023-11-14 22:00)


class _Resp:
    def __init__(self, payload):
        self.status_code, self._payload = 200, payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeKlines:
    """_request_klines 대체 — 바이낸스 /klines 규약: startTime 은 그 이후 첫 limit 봉, endTime 만 있으면 그 이전 최신 limit 봉."""

    def __init__(self, n_bars, step=H):
        self.step = step
        self.bars = {T0 + i * step: self._row(T0 + i * step) for i in range(n_bars)}
        self.calls = []
        self.fail = None            # 예외 인스턴스면 던진다

    def _row(self, t, close="100.0"):
        return [t, "100.0", "101.0", "99.0", close, "10.0", t + self.step - 1, "1000.0", 5, "5.0", "500.0", "0"]

    def advance(self, n):
        last = max(self.bars)
        self.bars[last] = self._row(last, close="105.5")        # 미완성이던 마지막 봉의 종가가 바뀜
        for i in range(1, n + 1):
            self.bars[last + i * self.step] = self._row(last + i * self.step)

    def page(self, params):
        start, end, limit = params.get("startTime"), params.get("endTime"), params["limit"]
        keys = sorted(k for k in self.bars if (start is None or k >= start) and (end is None or k <= end))
        keys = keys[:limit] if start is not None else keys[-limit:]
        return [list(self.bars[k]) for k in keys]

    def __call__(self, params):
        self.calls.append(dict(params))
        if self.fail is not None:
            raise self.fail
        return _Resp(self.page(params)), BINANCE_BASE_URL


@pytest.fixture
def ex(monkeypatch):
    fake = FakeKlines(3500)
    monkeypatch.setattr(B, "_request_klines", fake)
    monkeypatch.setattr(B, "_PAGE_SLEEP_SEC", 0)
    B.reset_data_url()
    B._LAST_FETCH_AT.clear()
    yield fake
    B.reset_data_url()


def test_first_fetch_is_one_request_and_creates_store_file(ex):
    rows = B.fetch_klines("BTCUSDT", "1h", 1000)
    assert ex.calls == [{"symbol": "BTCUSDT", "interval": "1h", "limit": 1000}]
    opens = [r[0] for r in rows]
    assert len(rows) == 1000 and opens == sorted(opens) and opens[-1] == max(ex.bars)
    assert len(rows[0]) == 12 and isinstance(rows[0][0], int) and isinstance(rows[0][4], str)
    path = ohlcv_store.store_path("BTCUSDT", "1h", B._store_dir())
    assert os.path.basename(path) == "ohlcv_BTCUSDT_1h.csv" and os.path.exists(path)
    assert B._store_dir() == os.path.normpath(os.environ[ohlcv_store.STORE_DIR_ENV])  # 임시 폴더 (작업 트리 아님)
    assert os.path.normcase(B._store_dir()) != os.path.normcase(os.path.normpath(ohlcv_store.REAL_STORE_DIR))
    assert B.store_status("BTCUSDT", "1h")["requests"] == 1
    assert B.stale_caption("BTCUSDT", "1h") is None


def test_after_cache_expiry_only_the_tail_is_requested(ex):
    B.fetch_klines("BTCUSDT", "1h", 1000)
    B.fetch_klines("BTCUSDT", "1h", 1000)
    assert len(ex.calls) == 1                                               # 캐시 히트 — 요청 없음
    last_open = max(ex.bars)
    ex.advance(3)
    B.fetch_klines.clear()                                                  # TTL 만료와 같다
    rows = B.fetch_klines("BTCUSDT", "1h", 1000)
    assert len(ex.calls) == 2 and ex.calls[1]["startTime"] == last_open - H  # 꼬리 1회 — 끝에서 두 번째(확정) 봉부터
    status = B.store_status("BTCUSDT", "1h")
    assert status["requests"] == 1 and status["added"] == 3 and status["bars"] == 1003
    assert len(rows) == 1000 and rows[-1][0] == max(ex.bars)
    assert next(r for r in rows if r[0] == last_open)[4] == "105.5"        # 미완성 봉 덮어쓰기


def test_paginated_first_load_is_three_pages(ex):
    rows = B.fetch_klines_paginated("BTCUSDT", "1h", 2500)
    assert len(ex.calls) == 3 and "endTime" not in ex.calls[0]
    assert ex.calls[1]["endTime"] == T0 + 2500 * H - 1                     # 첫 저장 봉 − 1
    assert len(rows) == 2500 and rows[-1][0] == max(ex.bars)
    assert all(b[0] - a[0] == H for a, b in zip(rows, rows[1:]))
    B.fetch_klines.clear()
    B.fetch_klines("BTCUSDT", "1h", 1000)                                   # 같은 저장본을 앱 경로가 이어 쓴다
    assert len(ex.calls) == 4 and "startTime" in ex.calls[3]


def test_failure_with_store_returns_stored_copy_marked_stale(ex):
    first = B.fetch_klines("BTCUSDT", "1h", 1000)
    received_at = B.last_fetch_at("BTCUSDT", "1h")
    ex.fail = requests.ConnectionError("offline")
    B.fetch_klines.clear()
    rows = B.fetch_klines("BTCUSDT", "1h", 1000)
    assert rows == first
    status = B.store_status("BTCUSDT", "1h")
    assert status["stale"] is True and status["fetched"] is False
    caption = B.stale_caption("BTCUSDT", "1h")
    assert "저장본 표시" in caption and "마지막 수신 0분 전" in caption
    assert B.stale_age("BTCUSDT", "1h") == "0분 전"
    assert B.last_fetch_at("BTCUSDT", "1h") == received_at                 # 실제 수신 시각은 그대로
    assert B.last_fetch_error("BTCUSDT", "1h") == f"ConnectionError {BINANCE_BASE_URL}"


def test_failure_without_store_keeps_previous_error_path(ex):
    ex.fail = requests.ConnectionError("offline")
    assert B.fetch_klines("BTCUSDT", "1h", 1000) is None                   # 종전과 같이 None (예외 아님)
    assert B.last_fetch_error("BTCUSDT", "1h") == f"ConnectionError {BINANCE_BASE_URL}"
    assert B.stale_caption("BTCUSDT", "1h") is None
    assert not os.path.exists(ohlcv_store.store_path("BTCUSDT", "1h", B._store_dir()))
    assert B.fetch_klines_paginated("BTCUSDT", "1h", 2500) is None


def test_returned_length_equals_limit_even_when_store_is_deeper(ex):
    B.fetch_klines_paginated("BTCUSDT", "1h", 3000)
    for limit in (240, 500, 1000):
        rows = B.fetch_klines("BTCUSDT", "1h", limit)
        assert len(rows) == limit and rows[-1][0] == max(ex.bars)


def test_monthly_interval_uses_1mo_file(ex):
    B.fetch_klines("BTCUSDT", "1M", 240)
    assert os.path.basename(B.store_status("BTCUSDT", "1M")["path"]) == "ohlcv_BTCUSDT_1mo.csv"


def test_push_poller_does_not_judge_on_stale_store(ex):
    """apolo 폴러: 수신 실패로 저장본만 있으면 그 셀을 건너뛴다 — 저장본 마지막 봉은 미완성 값일 수 있다."""
    from scripts import push_alarms as P

    assert P.default_fetch_frame("BTCUSDT", "1h") is not None
    ex.fail = requests.ConnectionError("offline")
    assert P.default_fetch_frame("BTCUSDT", "1h") is None
    ex.fail = None
    assert P.default_fetch_frame("BTCUSDT", "1h") is not None


def test_app_renders_chart_with_warning_from_store_when_offline(monkeypatch):
    """앱: 저장본이 있으면 네트워크가 끊겨도 오류 화면 대신 차트 + 경고 (main.py 를 AppTest 로 실제 실행)."""
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    from test_page_render_smoke import _Resp as SynResp, _synthetic_klines

    online = {"ok": True}

    def fake_get(url, params=None, timeout=None, **kw):
        if not online["ok"]:
            raise requests.ConnectionError("offline")
        params = params or {}
        return SynResp(_synthetic_klines(params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)))

    monkeypatch.setattr(B.requests, "get", fake_get)
    B.reset_data_url()
    main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    at = AppTest.from_file(main_path, default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not [w.value for w in at.warning if "저장본 표시" in w.value]

    online["ok"] = False
    B.clear_klines_cache()
    at = AppTest.from_file(main_path, default_timeout=180)
    at.run()
    B.reset_data_url()
    assert not at.exception, [e.value for e in at.exception]
    assert not [e.value for e in at.error if "불러오지 못했습니다" in e.value]
    assert [w.value for w in at.warning if w.value.startswith("바이낸스 수신 실패 — 저장본 표시 · 마지막 수신 ")]
    assert [c.value for c in at.caption if c.value.startswith("저장본 표시: 1w(")]      # TF 레이더 한 줄


def test_scan_script_deep_rerun_requests_at_most_two_pages(monkeypatch, tmp_path):
    """스캔 스크립트: 두 번째 --deep 실행은 꼬리 + 상장 시작 확인 ≤ 2회, 결과는 마지막 봉 빼고 동일."""
    from scripts import sweep_scan_report as S

    fake = FakeKlines(1500)

    def page(symbol, interval, limit, start_time=None, end_time=None):
        params = {"limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        fake.calls.append(params)
        return fake.page(params)

    monkeypatch.setattr(S, "_fetch_page", page)
    monkeypatch.setenv(ohlcv_store.STORE_DIR_ENV, str(tmp_path / "store"))
    monkeypatch.setitem(S.DEEP_LIMITS, "1h", 2000)                          # 상장 이후 전체(1500)보다 큼
    first = S.fetch_history("BTCUSDT", "1h", 1000, deep=True)
    assert len(first) == 1500 and len(fake.calls) == 2
    fake.advance(2)
    second = S.fetch_history("BTCUSDT", "1h", 1000, deep=True)
    assert len(fake.calls) - 2 <= 2
    assert len(second) == 1502 and second[:1499] == first[:1499]
    assert os.path.exists(os.path.join(str(tmp_path / "store"), "ohlcv_BTCUSDT_1h.csv"))


def test_app_scan_script_and_poller_share_one_store_dir(ex, monkeypatch, tmp_path):
    """저장 경로 해석은 한 곳 — WEH_OHLCV_STORE_DIR 하나로 앱·스캔 스크립트·푸시 폴러가 같은 폴더를 쓴다."""
    from scripts import push_alarms as P
    from scripts import sweep_scan_report as S

    shared = str(tmp_path / "shared_store")
    monkeypatch.setenv(ohlcv_store.STORE_DIR_ENV, shared)
    monkeypatch.setattr(S, "_fetch_page", lambda symbol, interval, limit, start_time=None, end_time=None:
                        ex.page({"limit": limit, "startTime": start_time, "endTime": end_time}))
    B.fetch_klines("BTCUSDT", "1h", 1000)                                   # 앱
    S.fetch_history("ETHUSDT", "1h", 1000, deep=False)                      # 스캔 스크립트
    assert P.default_fetch_frame("SOLUSDT", "1h") is not None               # 푸시 폴러 (data/binance 경유)
    assert {"ohlcv_BTCUSDT_1h.csv", "ohlcv_ETHUSDT_1h.csv", "ohlcv_SOLUSDT_1h.csv"} <= set(os.listdir(shared))
    assert os.path.dirname(B.store_status("SOLUSDT", "1h")["path"]) == os.path.normpath(shared)


def test_tripwire_is_not_swallowed_by_app_fetch(ex, monkeypatch):
    """pytest 중 실제 data/cache 로 향하면 fetch_klines 가 '수신 실패(None)'로 삼키지 않고 RuntimeError 를 올린다."""
    monkeypatch.setenv(ohlcv_store.STORE_DIR_ENV, ohlcv_store.REAL_STORE_DIR)
    path = ohlcv_store.store_path("TRIPWIREUSDT", "1h")
    assert not os.path.exists(path)                                         # 실제 저장소에 없는 심볼 — 읽을 것도 없다
    try:
        with pytest.raises(RuntimeError, match="실제 OHLCV 저장소"):
            B.fetch_klines("TRIPWIREUSDT", "1h", 1000)
        with pytest.raises(RuntimeError, match="실제 OHLCV 저장소"):
            B.fetch_klines_paginated("TRIPWIREUSDT", "1h", 2500)
        assert not os.path.exists(path)
    finally:                                                                # 트립와이어가 고장 났을 때만 남는 흔적
        if os.path.exists(path):
            os.remove(path)
