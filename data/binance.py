# data/binance.py
import logging
import time

import requests
import streamlit as st

from config.settings import BINANCE_BASE_URL

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


@st.cache_data(ttl=600)
def fetch_klines(symbol: str, interval: str, limit: int):
    """Fetches raw OHLCV data from the Binance public API."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(BINANCE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            return None
        _LAST_FETCH_AT[(symbol, interval)] = time.time()
        return data
    except Exception:
        return None


def _fetch_klines_page(symbol: str, interval: str, limit: int, end_time=None):
    """Single-page kline request (uncached — pagination orchestrator calls this)."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time is not None:
        params["endTime"] = int(end_time)
    response = requests.get(BINANCE_BASE_URL, params=params, timeout=10)
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
