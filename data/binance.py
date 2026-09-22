# data/binance.py
import logging
import time

import requests
import streamlit as st

from config.settings import BINANCE_BASE_URL, BINANCE_FALLBACK_STATUS, BINANCE_FALLBACK_URL

logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
_PAGE_SLEEP_SEC = 0.2

# Binance kline interval → expected spacing (ms) for gap detection
_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "3h": 10_800_000, "4h": 14_400_000,
    "6h": 21_600_000, "8h": 28_800_000, "12h": 43_200_000,
    "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000,
}


@st.cache_data(ttl=600)
def get_auto_limit(interval: str) -> int:
    """Determines the appropriate Binance API limit for the requested interval."""
    limit_map = {
        "1m": 1000, "3m": 1000, "5m": 1000, "15m": 1000, "30m": 1000,
        "1h": 1000, "2h": 1000, "3h": 1000, "4h": 1000, "6h": 1000, "8h": 1000, "12h": 1000,
        "1d": 500, "3d": 500, "1w": 300, "1M": 240,
        "2d": 1000, "4d": 1000, "2w": 1000,
    }
    return limit_map.get(interval, 500)


# 마지막 실제 요청 시각 (symbol, interval) → epoch 초. cache_data 는 캐시 미스일 때만 함수 본문을 실행하므로
# 본문에서 기록하면 "캐시가 아니라 실제로 받은" 시각이 된다. 프로세스 전역(캐시와 같은 범위).
_LAST_FETCH_AT: dict = {}


def last_fetch_at(symbol: str, interval: str):
    """마지막으로 Binance 에서 실제 수신한 시각(epoch 초). 이 프로세스에서 받은 적 없으면 None."""
    return _LAST_FETCH_AT.get((symbol, interval))


def clear_klines_cache() -> None:
    """OHLCV 캐시(fetch_klines · fetch_klines_paginated)만 비운다 — 다음 호출이 최신 봉까지 다시 받는다.

    build_dataframe·지표 캐시는 입력(raw)으로 키가 잡혀 raw 가 바뀌면 자동으로 재계산되므로 건드리지 않는다.
    """
    fetch_klines.clear()
    fetch_klines_paginated.clear()


# ---------------------------------------------------------------------------
# 데이터 주소 자동 대체 (Streamlit Cloud 배포 대응)
# api.binance.com 이 451/403 을 주면 같은 요청을 data-api.binance.vision 으로 재시도하고, 한 번 대체되면
# 프로세스 동안은 대체 주소를 바로 쓴다(매 요청마다 차단 주소를 먼저 두드리지 않는다). 상태는 프로세스 전역
# (st.cache_data 와 같은 범위). 지표·검출 로직 무접촉 — 요청 URL 만 바뀌고 응답 스키마는 동일하다.
# ---------------------------------------------------------------------------
_DATA_URL = {"url": BINANCE_BASE_URL, "reason": None}
# 마지막 실패 사유 (symbol, interval) → "HTTP 451 https://..." 등. 화면 오류 메시지에 원인을 싣기 위함.
_LAST_ERROR: dict = {}


def active_data_url() -> str:
    """현재 사용 중인 klines 요청 주소(대체됐으면 대체 주소)."""
    return _DATA_URL["url"]


def fallback_reason():
    """대체 주소로 전환된 사유('api.binance.com HTTP 451'). 전환되지 않았으면 None."""
    return _DATA_URL["reason"]


def reset_data_url() -> None:
    """원래 주소로 되돌린다(테스트·수동 복구용). 실패 사유 기록도 비운다."""
    _DATA_URL["url"] = BINANCE_BASE_URL
    _DATA_URL["reason"] = None
    _LAST_ERROR.clear()


def last_fetch_error(symbol: str, interval: str):
    """마지막 fetch 실패 사유 문자열(HTTP 상태 코드·시도한 주소 포함). 성공했거나 시도한 적 없으면 None."""
    return _LAST_ERROR.get((symbol, interval))


def _host(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0]


def data_source_line() -> str:
    """사이드바 한 줄 — '데이터 주소 <host>' (+ 대체됐으면 사유)."""
    line = f"데이터 주소 {_host(active_data_url())}"
    reason = fallback_reason()
    return f"{line} (대체 — {reason})" if reason else line


def _request_klines(params: dict):
    """현재 주소로 GET. 원래 주소가 451/403 이면 대체 주소로 전환해 같은 요청을 1회 재시도한다.

    반환: (response, url) — response 는 raise_for_status 를 아직 부르지 않은 상태.
    """
    url = active_data_url()
    response = requests.get(url, params=params, timeout=10)
    status = getattr(response, "status_code", None)
    if url == BINANCE_BASE_URL and status in BINANCE_FALLBACK_STATUS:
        reason = f"{_host(url)} HTTP {status}"
        logger.warning("binance %s → fallback %s (same request retried)", reason, BINANCE_FALLBACK_URL)
        _DATA_URL["url"] = BINANCE_FALLBACK_URL
        _DATA_URL["reason"] = reason
        url = BINANCE_FALLBACK_URL
        response = requests.get(url, params=params, timeout=10)
    return response, url


def _describe_error(exc: Exception, url: str) -> str:
    """오류 메시지용 — 'HTTP <code> <url>' 또는 '<ExceptionType> <url>'."""
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if code is not None:
        return f"HTTP {code} {url}"
    return f"{type(exc).__name__} {url}"


@st.cache_data(ttl=600)
def fetch_klines(symbol: str, interval: str, limit: int):
    """Fetches raw OHLCV data from the Binance public API."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    url = active_data_url()
    try:
        response, url = _request_klines(params)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            _LAST_ERROR[(symbol, interval)] = f"빈/비정상 응답 {url}"
            return None
        _LAST_FETCH_AT[(symbol, interval)] = time.time()
        _LAST_ERROR.pop((symbol, interval), None)
        return data
    except Exception as exc:  # noqa: BLE001 — 실패는 None, 사유는 last_fetch_error 로 노출
        _LAST_ERROR[(symbol, interval)] = _describe_error(exc, url)
        logger.warning("fetch_klines failed for %s %s: %s", symbol, interval, _LAST_ERROR[(symbol, interval)])
        return None


def _fetch_klines_page(symbol: str, interval: str, limit: int, end_time=None):
    """Single-page kline request (uncached — pagination orchestrator calls this)."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time is not None:
        params["endTime"] = int(end_time)
    response, _ = _request_klines(params)
    response.raise_for_status()
    data = response.json()
    if not data:
        return []
    return data


def _merge_klines(rows, interval: str):
    """open_time 기준 정렬·중복 제거·단조 증가 assert·갭 경고."""
    if not rows:
        return []

    by_open = {}
    for row in rows:
        by_open[row[0]] = row
    merged = [by_open[k] for k in sorted(by_open)]

    opens = [r[0] for r in merged]
    for i in range(len(opens) - 1):
        if opens[i] >= opens[i + 1]:
            raise AssertionError(
                f"klines open_time not strictly increasing: {opens[i]} >= {opens[i + 1]}"
            )

    step = _INTERVAL_MS.get(interval)
    if step:
        for i in range(len(opens) - 1):
            gap = opens[i + 1] - opens[i]
            if gap > step * 1.5:
                logger.warning(
                    "klines gap detected: interval=%s between %s and %s (gap_ms=%s expected=%s)",
                    interval, opens[i], opens[i + 1], gap, step,
                )
    return merged


@st.cache_data(ttl=600)
def fetch_klines_paginated(symbol: str, interval: str, total_limit: int):
    """endTime 커서로 과거 페이지를 병합해 total_limit봉까지 수집한다.

    total_limit <= 1000이면 fetch_klines와 동일 경로.
    페이지 실패(1회 재시도 후) 시 부분 결과 반환 + 경고 로그. 갭 보간 없음.
    """
    if total_limit <= 0:
        return None
    if total_limit <= _PAGE_SIZE:
        return fetch_klines(symbol, interval, total_limit)

    collected = []
    end_time = None
    partial_reason = None

    while len(collected) < total_limit:
        batch_limit = min(_PAGE_SIZE, total_limit - len(collected))
        batch = None
        last_err = None
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(_PAGE_SLEEP_SEC)
                else:
                    time.sleep(_PAGE_SLEEP_SEC)
                batch = _fetch_klines_page(symbol, interval, batch_limit, end_time)
                break
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "pagination page attempt %s failed for %s %s: %s",
                    attempt + 1, symbol, interval, exc,
                )
        if batch is None:
            partial_reason = f"page failed after retry: {last_err}"
            logger.warning(
                "fetch_klines_paginated partial return for %s %s: %s (collected=%s)",
                symbol, interval, partial_reason, len(collected),
            )
            break
        if not batch:
            break

        collected = batch + collected
        end_time = batch[0][0] - 1

        if len(collected) >= total_limit:
            break

    if not collected:
        return None

    merged = _merge_klines(collected, interval)
    if len(merged) > total_limit:
        merged = merged[-total_limit:]
    if partial_reason:
        logger.warning(
            "fetch_klines_paginated returning %s/%s bars for %s %s (%s)",
            len(merged), total_limit, symbol, interval, partial_reason,
        )
    return merged
