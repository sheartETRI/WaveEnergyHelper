# data/binance.py
import functools
import logging
import os
import time

import requests
import streamlit as st

from config.settings import (
    BINANCE_BASE_URL, BINANCE_FALLBACK_STATUS, BINANCE_FALLBACK_URL, OHLCV_STORE_PARAMS,
)
from data import ohlcv_store

logger = logging.getLogger(__name__)

_PAGE_SLEEP_SEC = 0.2
_PAGE_ATTEMPTS = 2      # fetch_klines_paginated 페이지당 시도 횟수 (1회 재시도)


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
    """현재 주소로 GET. 원래 주소가 451/403 응답이거나 연결 자체가 실패하면 대체 주소로 전환해
    같은 요청을 1회 재시도한다.

    반환: (response, url) — response 는 raise_for_status 를 아직 부르지 않은 상태.
    연결 단계 실패(ConnectionError·Timeout 등)는 응답 상태가 없어 451/403 분기로 못 잡으므로
    여기서 예외를 잡아 대체 주소로 넘긴다(standalone 스캔 스크립트와 동일한 태도). 이미 대체
    주소를 쓰는 중이면 재시도 없이 원래 예외를 올린다.
    """
    url = active_data_url()
    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.exceptions.RequestException as exc:
        if url != BINANCE_BASE_URL:
            raise
        reason = f"{_host(url)} {type(exc).__name__}"
        logger.warning("binance %s → fallback %s (connect retry)", reason, BINANCE_FALLBACK_URL)
        _DATA_URL["url"] = BINANCE_FALLBACK_URL
        _DATA_URL["reason"] = reason
        return requests.get(BINANCE_FALLBACK_URL, params=params, timeout=10), BINANCE_FALLBACK_URL
    status = getattr(response, "status_code", None)
    if url == BINANCE_BASE_URL and status in BINANCE_FALLBACK_STATUS:
        reason = f"{_host(url)} HTTP {status}"
        logger.warning("binance %s → fallback %s (same request retried)", reason, BINANCE_FALLBACK_URL)
        _DATA_URL["url"] = BINANCE_FALLBACK_URL
        _DATA_URL["reason"] = reason
        url = BINANCE_FALLBACK_URL
        response = requests.get(url, params=params, timeout=10)
    return response, url


class _BadPayload(ValueError):
    """HTTP 200 이지만 list 가 아닌 응답(오류 JSON 등)."""


def _describe_error(exc: Exception, url: str) -> str:
    """오류 메시지용 — 'HTTP <code> <url>' 또는 '<ExceptionType> <url>' (비정상 응답은 '빈/비정상 응답 <url>')."""
    if isinstance(exc, _BadPayload):
        return f"빈/비정상 응답 {url}"
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if code is not None:
        return f"HTTP {code} {url}"
    return f"{type(exc).__name__} {url}"


# ---------------------------------------------------------------------------
# OHLCV 로컬 저장소 (data/ohlcv_store.py, SPEC §12) — TF 별 raw kline CSV 를 두고 꼬리만 받는다.
# 스캔 스크립트(scripts/sweep_scan_report.py)와 같은 파일을 쓴다 — 경로는 ohlcv_store.resolve_store_dir()
# (환경변수 WEH_OHLCV_STORE_DIR 최우선, 없으면 settings). 호출자가 받는 것은 종전과 같다(바이낸스
# 응답 모양의 행, open_time 오름차순, 길이 ≤ limit) → build_dataframe 이후 판정·지표 입력 동일.
# 수신 실패: 저장본이 있으면 저장본 + stale 표시(캡션 전용), 없으면 종전처럼 None + last_fetch_error.
# ---------------------------------------------------------------------------
# 마지막 실제 저장소 갱신 상태 (symbol, interval) → dict. _LAST_FETCH_AT 처럼 캐시 미스일 때만 기록된다(표시용).
_STORE_STATUS: dict = {}


def _store_dir() -> str:
    """저장소 경로 — 호출 시점에 읽는다(테스트는 conftest 가 WEH_OHLCV_STORE_DIR 를 임시 폴더로 바꾼다)."""
    return ohlcv_store.resolve_store_dir()


def _fetch_klines_page(symbol: str, interval: str, limit: int, start_time=None, end_time=None, tried=None):
    """단일 요청(캐시 없음) — 저장소에 주입하는 전송 계층. startTime/endTime 은 바이낸스 규약(open_time ms).

    tried(dict) 가 있으면 시도한 주소(대체 전환 반영)와 실패 사유를 남긴다 — 화면 오류 문구가 종전과 같도록.
    """
    params = {"symbol": symbol, "interval": interval, "limit": int(limit)}
    if start_time is not None:
        params["startTime"] = int(start_time)
    if end_time is not None:
        params["endTime"] = int(end_time)
    url = active_data_url()
    try:
        response, url = _request_klines(params)
        response.raise_for_status()
        data = response.json()
        if data and not isinstance(data, list):
            raise _BadPayload(f"{type(data).__name__} 응답")
    except Exception as exc:
        if tried is not None:
            tried["url"], tried["error"] = url, _describe_error(exc, url)
        raise
    if tried is not None:
        tried["url"] = url
    return data or []


def _fetch_page_with_retry(symbol: str, interval: str, limit: int, start_time=None, end_time=None):
    """fetch_klines_paginated 의 전송 계층 — 페이지마다 대기 후 요청, 실패 시 1회 재시도 (종전 페이지 루프 그대로)."""
    last_err = None
    for attempt in range(_PAGE_ATTEMPTS):
        time.sleep(_PAGE_SLEEP_SEC)
        try:
            return _fetch_klines_page(symbol, interval, limit, start_time=start_time, end_time=end_time)
        except Exception as exc:  # noqa: BLE001 — 재시도 후에도 실패면 저장소가 진행분으로 버틴다
            last_err = exc
            logger.warning(
                "pagination page attempt %s failed for %s %s: %s",
                attempt + 1, symbol, interval, exc,
            )
    raise last_err


def _refresh_store(symbol: str, interval: str, min_bars: int, fetch_page) -> ohlcv_store.RefreshResult:
    """저장소 갱신 + 상태 기록. 저장본 없이 수신 실패면 예외가 그대로 올라온다."""
    p = OHLCV_STORE_PARAMS
    res = ohlcv_store.refresh(symbol, interval, fetch_page, min_bars, base_dir=_store_dir(),
                              page_limit=p["page_limit"], max_gap_requests=p["max_gap_requests"])
    _STORE_STATUS[(symbol, interval)] = {
        "stale": res.stale, "error": res.error, "fetched": res.fetched,
        "last_success_ms": res.last_success_ms, "last_open_time": res.last_open_time,
        "added": res.added, "requests": res.requests, "gaps": len(res.gaps), "bars": len(res.rows),
        "path": res.path,
    }
    return res


def store_status(symbol: str, interval: str):
    """마지막 실제 저장소 갱신 상태(dict: requests·added·stale 등). 캐시 히트는 갱신하지 않는다. 없으면 None."""
    return _STORE_STATUS.get((symbol, interval))


def stale_age(symbol: str, interval: str):
    """저장본 표시 중이면 마지막 수신 후 경과('12분 전', 모르면 '?'), 아니면 None."""
    status = store_status(symbol, interval)
    if not status or not status["stale"]:
        return None
    if status["last_success_ms"] is None:
        return "?"
    return f"{max(0.0, time.time() * 1000 - status['last_success_ms']) / 60_000:.0f}분 전"


def stale_caption(symbol: str, interval: str):
    """메인 차트 경고 한 줄 — stale 일 때만. 끝 봉 시각은 사이드바 신선도 캡션이 이미 보여준다(시각 표기는 표시 계층 몫)."""
    age = stale_age(symbol, interval)
    if age is None:
        return None
    return f"바이낸스 수신 실패 — 저장본 표시 · 마지막 수신 {age}"


@st.cache_data(ttl=OHLCV_STORE_PARAMS["ttl_sec"])
def fetch_klines(symbol: str, interval: str, limit: int):
    """Binance OHLCV raw 행 — 로컬 저장소 경유(꼬리만 수신), 마지막 limit 봉.

    수신 실패 시 저장본이 있으면 저장본(stale_caption 으로 표시), 없으면 None + last_fetch_error (종전 경로).
    """
    tried = {"url": active_data_url(), "error": None}
    try:
        res = _refresh_store(symbol, interval, limit, functools.partial(_fetch_klines_page, tried=tried))
    except ohlcv_store.RealStoreWriteError:
        raise                   # 테스트 격리 위반(트립와이어)은 수신 실패로 삼키지 않는다
    except Exception as exc:  # noqa: BLE001 — 실패는 None, 사유는 last_fetch_error 로 노출
        _LAST_ERROR[(symbol, interval)] = tried["error"] or _describe_error(exc, tried["url"])
        logger.warning("fetch_klines failed for %s %s: %s", symbol, interval, _LAST_ERROR[(symbol, interval)])
        return None
    if not res.rows:
        _LAST_ERROR[(symbol, interval)] = f"빈/비정상 응답 {tried['url']}"
        return None
    if res.stale:
        _LAST_ERROR[(symbol, interval)] = tried["error"] or res.error
        logger.warning("fetch_klines %s %s: 수신 실패 (%s) → 저장본 %s봉 표시",
                       symbol, interval, _LAST_ERROR[(symbol, interval)], len(res.rows))
    else:
        _LAST_FETCH_AT[(symbol, interval)] = time.time()
        _LAST_ERROR.pop((symbol, interval), None)
    return ohlcv_store.tail(res.rows, limit)


@st.cache_data(ttl=OHLCV_STORE_PARAMS["ttl_sec"])
def fetch_klines_paginated(symbol: str, interval: str, total_limit: int):
    """total_limit봉까지 — 저장소가 모자란 과거만 endTime 커서로 페이지를 받아 채운다(충분하면 꼬리만).

    total_limit <= 1000이면 fetch_klines와 동일 경로.
    페이지 실패(1회 재시도 후) 시 진행분 반환 + 경고 로그. 저장본 없이 첫 페이지부터 실패하면 None.
    """
    if total_limit <= 0:
        return None
    if total_limit <= OHLCV_STORE_PARAMS["page_limit"]:
        return fetch_klines(symbol, interval, total_limit)
    try:
        res = _refresh_store(symbol, interval, total_limit, _fetch_page_with_retry)
    except ohlcv_store.RealStoreWriteError:
        raise                   # 테스트 격리 위반(트립와이어)은 수신 실패로 삼키지 않는다
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_klines_paginated failed for %s %s: %s", symbol, interval, exc)
        return None
    if not res.rows:
        return None
    rows = ohlcv_store.tail(res.rows, total_limit)
    if res.error:
        logger.warning(
            "fetch_klines_paginated partial return for %s %s: %s (%s/%s bars%s)",
            symbol, interval, res.error, len(rows), total_limit, ", stale" if res.stale else "",
        )
    if res.gaps:
        logger.warning("klines gap detected: interval=%s %s gaps (first %s)", interval, len(res.gaps), res.gaps[0])
    return rows
