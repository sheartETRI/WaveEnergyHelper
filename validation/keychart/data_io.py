"""OHLCV 수집·캐시 (§8). 기존 data/ 모듈을 호출만 하고 수정하지 않는다."""
from __future__ import annotations

import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests  # noqa: E402

from config.settings import BINANCE_BASE_URL, CUSTOM_INTERVAL_BASE, TIMEFRAMES  # noqa: E402
from data.processor import build_dataframe, resample_timeframe  # noqa: E402

from validation.keychart import params_v0 as P  # noqa: E402

CACHE_DIR = os.path.join(HERE, "_ohlcv_cache")

# 프레임 1봉의 길이(분). "1M"은 가변이라 별도 취급한다.
FRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "3h": 180, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "2d": 2880, "3d": 4320, "4d": 5760,
    "1w": 10080, "2w": 20160,
    "1M": 43200,   # 근사(정렬·정렬용 순서 부여 목적)
}
SUBHOUR = [f for f in TIMEFRAMES if FRAME_MINUTES[f] < 60]

# 커스텀(리샘플) 프레임의 라벨 규약 → 봉 마감 시각 산출용.
#   3h  : label=left(=open time)      → close = label + 3h
#   2d/4d/2w : label=right, closed=right → label이 블록 마지막 일봉의 open time
#              → close = label + 1d
_RESAMPLE_CLOSE_DELTA = {
    "3h": pd.Timedelta("3h"),
    "2d": pd.Timedelta("1d"),
    "4d": pd.Timedelta("1d"),
    "2w": pd.Timedelta("1d"),
}


def bar_close_times(frame: str, open_times: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """봉 마감 시각. 이 시각이 되어야 해당 봉의 판정이 '알 수 있게' 된다."""
    if frame in _RESAMPLE_CLOSE_DELTA:
        return open_times + _RESAMPLE_CLOSE_DELTA[frame]
    if frame == "1M":
        return open_times + pd.offsets.MonthBegin(1)
    return open_times + pd.Timedelta(minutes=FRAME_MINUTES[frame])


def _cache_path(symbol: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}_{interval}.parquet")


def _fetch_backwards(symbol: str, interval: str, start: pd.Timestamp,
                     sleep_sec: float = 0.05, verbose: bool = True) -> pd.DataFrame:
    """endTime 커서로 start까지 과거 페이지를 모아 DataFrame으로 만든다.

    data.binance.fetch_klines_paginated와 동일한 endTime 커서 방식이지만 (a) 페이지마다
    DataFrame으로 변환해 붙이고 (b) requests.Session으로 커넥션을 재사용한다. 1m 3년
    (≈158만봉 = 1578페이지)을 받아야 하므로 매 페이지 TLS 핸드셰이크(≈0.9s)를 감당할 수 없다.
    수집 전용이며 판정 로직은 전혀 포함하지 않는다.
    """
    start_ms = int(start.value // 1_000_000)
    build = getattr(build_dataframe, "__wrapped__", build_dataframe)
    session = requests.Session()
    pages: list[pd.DataFrame] = []
    end_time = None
    total = 0
    while True:
        params = {"symbol": symbol, "interval": interval, "limit": 1000}
        if end_time is not None:
            params["endTime"] = int(end_time)
        raw = None
        for attempt in range(4):
            try:
                resp = session.get(BINANCE_BASE_URL, params=params, timeout=20)
                resp.raise_for_status()
                raw = resp.json()
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 3:
                    raise
                print(f"    retry {symbol} {interval}: {exc}", flush=True)
                time.sleep(2.0 * (attempt + 1))
        if not raw:
            break
        page = build(raw)
        if page is None or page.empty:
            break
        pages.append(page)
        total += len(page)
        oldest_ms = raw[0][0]
        if verbose and len(pages) % 50 == 0:
            print(f"    {symbol} {interval}: {total} bars, oldest={page.index[0]}", flush=True)
        if oldest_ms <= start_ms or len(raw) < 1000:
            break
        end_time = oldest_ms - 1
        time.sleep(sleep_sec)

    if not pages:
        return pd.DataFrame()
    df = pd.concat(pages).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def collect(symbol: str, sleep_sec: float = 0.05, verbose: bool = True) -> None:
    """심볼의 네이티브 프레임 전부를 캐시에 채운다(커스텀 프레임은 베이스에서 리샘플)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    native = [f for f in TIMEFRAMES if f not in CUSTOM_INTERVAL_BASE]
    for interval in native:
        path = _cache_path(symbol, interval)
        if os.path.exists(path):
            if verbose:
                print(f"  cached {symbol} {interval}", flush=True)
            continue
        if interval in SUBHOUR:
            warm = pd.Timedelta(minutes=FRAME_MINUTES[interval] * P.SUBHOUR_WARMUP_BARS)
            start = P.PRIMARY_START - warm
        else:
            start = P.EXPLORE_START - pd.Timedelta(days=30)
        if verbose:
            print(f"  fetch {symbol} {interval} from {start}", flush=True)
        df = _fetch_backwards(symbol, interval, start, sleep_sec=sleep_sec, verbose=verbose)
        if df.empty:
            print(f"  !! empty {symbol} {interval}", flush=True)
            continue
        df.to_parquet(path)
        print(f"  saved {symbol} {interval}: {len(df)} bars {df.index[0]}..{df.index[-1]}", flush=True)


def load(symbol: str, frame: str) -> pd.DataFrame:
    """분석용 OHLCV. 커스텀 프레임은 기존 resample_timeframe로 만든다."""
    base = CUSTOM_INTERVAL_BASE.get(frame, frame)
    path = _cache_path(symbol, base)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    if frame in CUSTOM_INTERVAL_BASE:
        rs = getattr(resample_timeframe, "__wrapped__", resample_timeframe)
        df = rs(df, frame)
    return df.astype(float)


if __name__ == "__main__":
    args = sys.argv[1:]
    syms = args if args else P.SYMBOLS
    for s in syms:
        print(f"== {s}", flush=True)
        collect(s)
