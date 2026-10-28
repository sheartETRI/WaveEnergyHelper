"""푸시용 마감 봉 적재·합성. 앱의 표시용 봉과 구분되는 기존 계약을 유지한다."""
from __future__ import annotations
from typing import Callable, Optional
import pandas as pd
from config.settings import CUSTOM_INTERVALS
from data.binance import clear_klines_cache, fetch_klines, get_auto_limit, store_status
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from indicators.moving_averages import add_moving_averages
from indicators.stochastic import add_stochastic_slow_layers

__all__ = ['interval_delta', 'closed_frame', 'resample_factor', 'align_base_frame', 'resample_closed', 'load_closed_frame', 'served_from_stale_store', 'default_fetch_frame']

_UNIT_KW = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}

_EPOCH = pd.Timestamp("1970-01-01")


def interval_delta(interval: str) -> pd.Timedelta:
    """Binance 네이티브 간격 문자열 → Timedelta ("1h","2h","4h","6h","12h","1d","1w" 등). 커스텀 TF(2d·4d·2w)는 미지원."""
    unit, n = interval[-1], int(interval[:-1])
    if interval in CUSTOM_INTERVALS or unit not in _UNIT_KW:
        # 커스텀 TF 는 리샘플 라벨(right/left)이 섞여 있어 open_time + 간격으로 닫힘을 판정할 수 없다 → 베이스 TF 에서 판정
        raise ValueError(f"지원하지 않는 간격: {interval}")
    return pd.Timedelta(**{_UNIT_KW[unit]: n})


def closed_frame(df: Optional[pd.DataFrame], interval: str, now: Optional[pd.Timestamp] = None) -> Optional[pd.DataFrame]:
    """마지막 봉이 아직 열려 있으면(open_time + 간격 > now) 그 봉을 뺀 프레임. now 는 naive UTC(df 인덱스와 같은 기준)."""
    if df is None or df.empty:
        return df
    if now is None:
        now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    last_open = pd.Timestamp(df.index[-1])
    if last_open + interval_delta(interval) > now:
        return df.iloc[:-1]
    return df


def resample_factor(interval: str) -> int:
    """'Nd' 커스텀 TF 의 베이스(1d) 봉 수. 그 외 커스텀(3h·2w)은 이 폴러의 대상이 아니다."""
    if interval in CUSTOM_INTERVALS and interval.endswith("d") and get_fetch_interval(interval) == "1d":
        return int(interval[:-1])
    raise ValueError(f"리샘플 대상이 아닌 간격: {interval}")


def align_base_frame(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """config 리샘플 규칙(origin=start)은 첫 봉을 기준으로 묶으므로 fetch 창이 하루씩 밀리면 2d 짝이 바뀐다.
    첫 1d 봉의 epoch 일수를 factor 의 배수에 맞춰(앞 봉 최대 factor−1 개 버림) 창과 무관하게 같은 짝을 만든다."""
    factor = resample_factor(interval)
    if df is None or df.empty:
        return df
    days = (pd.Timestamp(df.index[0]).normalize() - _EPOCH).days
    drop = (-days) % factor
    return df.iloc[drop:]


def resample_closed(df_base_closed: pd.DataFrame, interval: str) -> pd.DataFrame:
    """닫힌 1d 봉 → 커스텀 'Nd' 봉 (config 규칙 그대로) — 정렬 뒤, 베이스 봉이 factor 개 안 찬 봉(첫 홀·마지막 진행분)은 뺀다."""
    factor = resample_factor(interval)
    aligned = align_base_frame(df_base_closed, interval)
    if aligned is None or aligned.empty:
        return aligned
    out = resample_timeframe(aligned, interval)
    # 봉당 베이스 봉 수 — resample_timeframe 과 같은 파라미터(data.processor 의 2d/4d 규칙: right/right/origin=start)
    counts = aligned["close"].resample(f"{factor}D", label="right", closed="right", origin="start").size()
    full = counts[counts >= factor].index
    return out.loc[out.index.isin(full)]


def load_closed_frame(symbol: str, interval: str, now: Optional[pd.Timestamp] = None,
                      fetch: Callable = fetch_klines) -> Optional[pd.DataFrame]:
    """앱과 같은 데이터 경로(data/binance → build_dataframe → 리샘플)로 **닫힌 봉만** 담은 지표 프레임.

    지표는 추적 모듈이 필요로 하는 MA·스토캐 층만(앱 load_frame 에서 MACD·RSI 를 뺀 것 — 알림 종류가 쓰지 않음).
    """
    base = get_fetch_interval(interval)
    raw = fetch(symbol, base, get_auto_limit(interval))
    df = build_dataframe(raw)
    if df is None or df.empty:
        return None
    df = closed_frame(df, base, now)
    if interval != base:
        df = resample_closed(df, interval)
    if df is None or df.empty:
        return None
    df = add_moving_averages(df.copy())
    return add_stochastic_slow_layers(df)


def served_from_stale_store(symbol: str, interval: str) -> bool:
    """방금 적재가 수신 실패로 저장본(data/cache)을 돌려받은 것인지 (SPEC §12).

    저장본의 마지막 봉은 저장 시점의 미완성 값일 수 있어 닫힌 봉 판정·발송에 쓰지 않는다 — 종전처럼
    수신 실패 = 데이터 없음으로 그 셀(대상)을 이번 순회에서 건너뛴다.
    """
    status = store_status(symbol, get_fetch_interval(interval))
    return bool(status and status["stale"])


def default_fetch_frame(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """순회마다 OHLCV 캐시를 비워 최신 봉까지 받는다(data.binance cache_data ttl=600 우회). 저장본이면 None."""
    clear_klines_cache()
    frame = load_closed_frame(symbol, interval)
    return None if served_from_stale_store(symbol, interval) else frame
