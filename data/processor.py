# data/processor.py
import pandas as pd
import streamlit as st
from typing import Optional

from config.settings import CUSTOM_INTERVAL_BASE


def get_fetch_interval(interval: str) -> str:
    """커스텀 인터벌이면 fetch할 베이스 인터벌을, 아니면 인터벌 그대로 반환한다."""
    return CUSTOM_INTERVAL_BASE.get(interval, interval)

@st.cache_data(ttl=600)
def build_dataframe(raw_klines) -> Optional[pd.DataFrame]:
    """Converts raw klines into a processed pandas DataFrame."""
    if not raw_klines or not isinstance(raw_klines, list):
        return None
    try:
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
        ]
        df = pd.DataFrame(raw_klines, columns=columns)
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()

        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        return df
    except Exception:
        return None

@st.cache_data(ttl=600)
def resample_timeframe(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Resamples a DataFrame to a custom interval."""
    if df is None or df.empty:
        return df

    # 인터벌별 리샘플 파라미터.
    # 3h는 바이낸스 네이티브 캔들 경계(UTC 00/03/06...)와 라벨(open time)에 맞춰야
    # TradingView 등 표준 차트와 캔들 모양이 일치한다 -> label/closed=left, origin=epoch.
    # 2d/4d/2w는 기존 동작(label/closed=right, origin=start)을 그대로 보존한다.
    resample_config = {
        "3h": {"rule": "3h", "label": "left", "closed": "left", "origin": "epoch"},
        "2d": {"rule": "2D", "label": "right", "closed": "right", "origin": "start"},
        "4d": {"rule": "4D", "label": "right", "closed": "right", "origin": "start"},
        "2w": {"rule": "2W-MON", "label": "right", "closed": "right", "origin": "start"},
    }

    if interval not in resample_config:
        return df

    cfg = resample_config[interval]

    df_resampled = df.resample(
        cfg["rule"],
        label=cfg["label"],
        closed=cfg["closed"],
        origin=cfg["origin"],
    ).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    })

    return df_resampled.dropna()
