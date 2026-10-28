"""화면 전용 추적 결과 캐시. 계산 규칙은 tracking의 순수 함수에 위임한다.

OHLC·이평·스토캐 전체 입력과 인덱스를 키로 사용한다. MACD·RSI 표시 선택이
바뀌어도 동일한 추적은 재사용하고, 과거 봉을 포함한 입력 변경은 새로 계산한다.
원본 수신은 캐시하지 않아 데이터 계층의 새로고침·stale 안내를 유지한다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from tracking import ma60_down, ma60_turn, structure


def _tracking_input(df: pd.DataFrame) -> pd.DataFrame:
    columns = sorted(c for c in df.columns if c in {"open", "high", "low", "close"}
                     or c.startswith("MA") or c.startswith("stoch_"))
    return df.loc[:, columns]


@st.cache_data(show_spinner=False, ttl=600, max_entries=64)
def _upward(frame: pd.DataFrame, recent_bars: int) -> pd.DataFrame:
    return ma60_turn.track_candidates(frame, recent_bars=recent_bars)


@st.cache_data(show_spinner=False, ttl=600, max_entries=64)
def _downward(frame: pd.DataFrame, recent_bars: int) -> pd.DataFrame:
    return ma60_down.track_candidates(frame, recent_bars=recent_bars)


@st.cache_data(show_spinner=False, ttl=600, max_entries=64)
def _structure(frame: pd.DataFrame):
    return structure.analyze(frame)


def upward_candidates(df: pd.DataFrame, recent_bars: int = ma60_turn.RECENT_BARS) -> pd.DataFrame:
    return _upward(_tracking_input(df), recent_bars)


def downward_candidates(df: pd.DataFrame, recent_bars: int = ma60_down.RECENT_BARS) -> pd.DataFrame:
    return _downward(_tracking_input(df), recent_bars)


def structure_analysis(df: pd.DataFrame):
    return _structure(_tracking_input(df))


def clear_analysis_cache() -> None:
    """검증·수동 관리용. 일반 새로고침은 변경된 원본 입력으로 자동 무효화한다."""
    _upward.clear()
    _downward.clear()
    _structure.clear()
