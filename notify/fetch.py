"""스캐너 전용 데이터 소스 — data-api.binance.vision (Actions 러너에서 200 확인, 응답 형식 api.binance.com 과 동일).

로컬 앱·전방 추적이 쓰는 data/binance.py(api.binance.com) 는 건드리지 않는다. 이 모듈만 다른 호스트를 본다.
프레임 변환은 앱과 같은 ``data.processor.build_dataframe`` 를 소비한다(index = open_time, naive UTC).

**닫힌 봉만** 돌려준다: kline 의 close_time(ms) 이 now 이후이면 진행 중 봉이므로 버린다.
"""
from __future__ import annotations

import time
from typing import Callable, List, Optional

import pandas as pd
import requests

from data.processor import build_dataframe

VISION_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
FETCH_LIMIT = 1000          # 바이낸스 1회 최대. MA240·스토캐(20,10,10) 워밍업 + 추적 창에 충분
TIMEOUT_SEC = 20
CLOSE_TIME_COL = 6          # kline 배열: [open_time, o, h, l, c, v, close_time, ...]


def closed_only(raw: List[list], now_ms: Optional[int] = None) -> List[list]:
    """진행 중 봉 제거 — close_time < now 인 봉만. (바이낸스 close_time 은 다음 open_time − 1ms)"""
    if not raw:
        return []
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    return [row for row in raw if int(row[CLOSE_TIME_COL]) < now]


def fetch_klines_vision(symbol: str, interval: str, limit: int = FETCH_LIMIT,
                        get: Callable = requests.get) -> List[list]:
    """원시 kline 배열(진행 중 봉 포함). 실패 시 예외."""
    r = get(VISION_KLINES_URL, params={"symbol": symbol, "interval": interval, "limit": int(limit)},
            timeout=TIMEOUT_SEC)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"empty klines: {symbol} {interval}")
    return data


def fetch_closed_bars(symbol: str, interval: str, limit: int = FETCH_LIMIT,
                      get: Callable = requests.get, now_ms: Optional[int] = None) -> pd.DataFrame:
    """닫힌 봉만의 bare OHLCV 프레임 (index open_time naive UTC, open/high/low/close/volume)."""
    raw = closed_only(fetch_klines_vision(symbol, interval, limit, get=get), now_ms)
    df = build_dataframe(raw)
    if df is None or df.empty:
        raise RuntimeError(f"no closed bars: {symbol} {interval}")
    return df
