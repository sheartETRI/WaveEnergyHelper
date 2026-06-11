# indicators/oscillators.py
import pandas as pd
import streamlit as st
from config.settings import MACD_PARAMS, RSI_PARAMS, RSI_PIVOT_PARAMS
from indicators.stochastic import (
    compute_stochastic_pivots,
    detect_double_bottom_patterns,
    detect_double_top_patterns,
)

@st.cache_data(ttl=600)
def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Adds traditional MACD columns."""
    if df is None or df.empty:
        return df

    fast = MACD_PARAMS["fast"]
    slow = MACD_PARAMS["slow"]
    signal = MACD_PARAMS["signal"]

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df['macd_hist_prev'] = df['macd_hist'].shift(1)

    return df


def detect_rsi_bottom_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detects RSI double bottoms using higher pivot lows and neckline breaks."""
    return detect_double_bottom_patterns(
        df,
        "rsi",
        "rsi_pivot_low",
        "rsi_db",
        "rsi_db_candidate",
        "rsi_neckline",
    )


def detect_rsi_top_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detects RSI double tops using lower pivot highs and neckline breaks."""
    return detect_double_top_patterns(
        df,
        "rsi",
        "rsi_pivot_high",
        "rsi_dt",
        "rsi_dt_candidate",
        "rsi_dt_neckline",
    )


@st.cache_data(ttl=600)
def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """Adds RSI and zone-related columns."""
    if df is None or df.empty:
        return df

    length = RSI_PARAMS["length"]
    overbought = RSI_PARAMS["overbought"]
    oversold = RSI_PARAMS["oversold"]
    smoothing_length = RSI_PARAMS["smoothing_length"]
    smoothing_type = RSI_PARAMS["smoothing_type"]

    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    raw_rsi = 100 - (100 / (1 + rs))
    raw_rsi = raw_rsi.fillna(100)

    if smoothing_type == "EMA":
        rsi = raw_rsi.ewm(span=smoothing_length, adjust=False, min_periods=smoothing_length).mean()
    else:
        rsi = raw_rsi.rolling(window=smoothing_length, min_periods=smoothing_length).mean()

    df['rsi_raw'] = raw_rsi
    df['rsi'] = rsi
    df['rsi_above_ob'] = df['rsi'].where(df['rsi'] > overbought)
    df['rsi_below_os'] = df['rsi'].where(df['rsi'] < oversold)
    df['rsi_overbought_flag'] = df['rsi'] > overbought
    df['rsi_oversold_flag'] = df['rsi'] < oversold

    pivot_low, pivot_high = compute_stochastic_pivots(
        rsi,
        lookback=RSI_PIVOT_PARAMS["lookback"],
        middle_zone=RSI_PIVOT_PARAMS["middle_zone"],
        min_gap=RSI_PIVOT_PARAMS["min_gap"],
        min_delta=RSI_PIVOT_PARAMS["min_delta"],
    )
    df['rsi_pivot_low'] = pivot_low
    df['rsi_pivot_high'] = pivot_high
    df = detect_rsi_bottom_patterns(df)
    df = detect_rsi_top_patterns(df)

    return df
