"""as-of(기준 시점) 절단 — 표시·validation 공용 (엔진 무수정, 호출부 패치만)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Optional

import pandas as pd

from analysis import wave_energy as wave_energy_mod
from analysis.wave_energy import resolve_upper_frame
from config.settings import CUSTOM_INTERVALS, MA_PERIODS, WAVE_ENERGY_PARAMS
from data.binance import fetch_klines, fetch_klines_paginated, get_auto_limit
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from indicators.ma_dispersion import add_ma_dispersion
from indicators.ma_patterns import add_ma_patterns
from indicators.moving_averages import add_moving_averages
from indicators.stochastic import add_stochastic_slow_layers


def parse_as_of(text: Optional[str]) -> Optional[pd.Timestamp]:
    """사이드바 입력 → Timestamp. 빈값/파싱 실패 → None."""
    if text is None or not str(text).strip():
        return None
    try:
        return pd.Timestamp(str(text).strip())
    except (ValueError, TypeError):
        return None


def format_as_of_banner(as_of: pd.Timestamp) -> str:
    try:
        label = as_of.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        label = str(as_of)
    return f"백트레이스 모드: {label} 기준"


def truncate_to_asof(df: Optional[pd.DataFrame], as_of: pd.Timestamp) -> Optional[pd.DataFrame]:
    """timestamp ≤ as_of 로 OHLCV 절단 (인디케이터 전·후 모두 사용)."""
    if df is None or df.empty or as_of is None:
        return df
    cut = df.loc[df.index <= as_of]
    if cut.empty:
        return cut
    return cut.copy()


def ohlcv_from_raw(raw, interval: str) -> Optional[pd.DataFrame]:
    if not raw:
        return None
    df = build_dataframe(raw)
    if df is None or df.empty:
        return None
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)
    return df


def fetch_ohlcv_bare(
    symbol: str,
    interval: str,
    limit: Optional[int] = None,
    *,
    paginated: bool = False,
) -> Optional[pd.DataFrame]:
    """지표 없이 OHLCV만 로딩 (fetch 1회용)."""
    lim = limit if limit is not None else get_auto_limit(interval)
    fetch_iv = get_fetch_interval(interval)
    if paginated and lim > 1000:
        raw = fetch_klines_paginated(symbol, fetch_iv, lim)
    else:
        raw = fetch_klines(symbol, fetch_iv, lim)
    return ohlcv_from_raw(raw, interval)


def _coerce_ma_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """pd.NA → NaN (짧은 상위 프레임 등 MA 워밍업 부족 시 ma_patterns 호환)."""
    out = df.copy()
    for w in MA_PERIODS:
        col = f"MA{w}"
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def run_indicator_pipeline(df: pd.DataFrame, *, include_dispersion: bool = True) -> pd.DataFrame:
    """절단본마다 전체 재계산 (룩어헤드 방지)."""
    out = add_moving_averages(df.copy())
    out = _coerce_ma_numeric(out)
    out = add_ma_patterns(out)
    out = add_stochastic_slow_layers(out)
    if include_dispersion:
        out = add_ma_dispersion(out)
    return out


def build_ohlcv_cache(
    symbol: str,
    interval: str,
    base_bare: pd.DataFrame,
    *,
    extra_limits: Optional[Dict[str, int]] = None,
) -> Dict[str, pd.DataFrame]:
    """기준·1d 추세·상위 프레임 bare OHLCV (메모리 절단용)."""
    cache: Dict[str, pd.DataFrame] = {interval: base_bare}
    limits = extra_limits or {}
    trend_iv = WAVE_ENERGY_PARAMS["trend_interval"]
    if trend_iv not in cache:
        lim = limits.get(trend_iv, get_auto_limit(trend_iv))
        bare = fetch_ohlcv_bare(symbol, trend_iv, lim, paginated=lim > 1000)
        if bare is not None:
            cache[trend_iv] = bare
    upper_iv = resolve_upper_frame(interval)
    if upper_iv and upper_iv not in cache:
        lim = limits.get(upper_iv, get_auto_limit(upper_iv))
        bare = fetch_ohlcv_bare(symbol, upper_iv, lim, paginated=lim > 1000)
        if bare is not None:
            cache[upper_iv] = bare
    return cache


@contextmanager
def patch_load_frame_for_asof(symbol: str, as_of: pd.Timestamp, ohlcv_cache: Dict[str, pd.DataFrame]):
    """analyze_wave_energy 내부 _load_frame → as-of 절단 + 파이프라인 재계산."""
    original = wave_energy_mod._load_frame

    def _patched(sym: str, iv: str):
        if sym != symbol:
            return original(sym, iv)
        bare = ohlcv_cache.get(iv)
        if bare is None:
            return None
        cut = truncate_to_asof(bare, as_of)
        if cut is None or cut.empty:
            return None
        return run_indicator_pipeline(cut)

    wave_energy_mod._load_frame = _patched
    try:
        yield
    finally:
        wave_energy_mod._load_frame = original


def analyze_wave_energy_asof(
    symbol: str,
    interval: str,
    as_of: pd.Timestamp,
    ohlcv_cache: Dict[str, pd.DataFrame],
):
    """시점 as_of 기준 verdict (절단 + 파이프라인 재계산, 룩어헤드 없음)."""
    from analysis.wave_energy import analyze_wave_energy

    bare = ohlcv_cache.get(interval)
    if bare is None:
        raise ValueError(f"ohlcv_cache missing interval {interval}")
    cut = truncate_to_asof(bare, as_of)
    if cut is None or cut.empty:
        raise ValueError("as-of 절단 결과 empty")
    base_df = run_indicator_pipeline(cut)
    with patch_load_frame_for_asof(symbol, as_of, ohlcv_cache):
        return analyze_wave_energy(base_df, symbol, interval)
