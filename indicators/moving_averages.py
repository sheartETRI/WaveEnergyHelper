# indicators/moving_averages.py
import pandas as pd
import streamlit as st
from config.settings import MA_PERIODS

@st.cache_data(ttl=600)
def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates MAs based on periods defined in settings."""
    if df is None:
        return None
    
    for w in MA_PERIODS:
        if len(df) >= w:
            df[f'MA{w}'] = df['close'].rolling(window=w).mean()
        else:
            df[f'MA{w}'] = pd.NA
    return df
