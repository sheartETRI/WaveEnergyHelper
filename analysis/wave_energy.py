# analysis/wave_energy.py
"""파동에너지(Wave Energy) 매매 철학 분석 모듈.

확정 규칙 (절대 변경 금지):
1) 기준 추세는 항상 '일봉(1d) 60MA'다. 현재 프레임이 1d가 아니면 일봉을 별도 로딩한다.
2) 1d의 상위 프레임은 4d다. 상위 프레임의 소파동이 기준 프레임의 대파동이 된다.
   레이어 매핑: Top (20,10,10)=대파동 / Mid (10,5,5)=중파동 / Bot (5,3,3)=소파동.
3) 쌍바닥/쌍봉은 가격이 아니라 스토캐스틱 %K 파동에서 판정한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from config.settings import (
    CUSTOM_INTERVALS,
    STOCH_LAYERS,
    TIMEFRAMES,
    UPPER_FRAME_MAP,
    WAVE_ENERGY_PARAMS,
    WAVE_LAYER_ROLES,
)
from analysis.dynamics_rules import DynamicsReport, evaluate_dynamics
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, resample_timeframe, get_fetch_interval
from indicators.moving_averages import add_moving_averages
from indicators.stochastic import add_stochastic_slow_layers


_UNIT_MINUTES = {"m": 1, "h": 60, "d": 1440, "w": 10080, "M": 43200}  # 1M은 30일 근사


def _interval_to_minutes(interval):
    if not interval or len(interval) < 2:
        return None
    unit = interval[-1]
    if unit not in _UNIT_MINUTES:
        return None
    try:
        value = int(interval[:-1])
    except ValueError:
        return None
    return value * _UNIT_MINUTES[unit]


def _find_timeframe_by_minutes(minutes):
    for tf in TIMEFRAMES:
        if _interval_to_minutes(tf) == minutes:
            return tf
    return None


def resolve_upper_frame(interval):
    """상위 프레임 해석: 명시 맵 → ×4(존재 시) → ×6(존재 시) → None."""
    if interval in UPPER_FRAME_MAP:
        return UPPER_FRAME_MAP[interval]
    minutes = _interval_to_minutes(interval)
    if minutes is None:
        return None
    upper4 = _find_timeframe_by_minutes(minutes * 4)
    if upper4 is not None:
        return upper4
    return _find_timeframe_by_minutes(minutes * 6)


def resolve_lower_frame(interval):
    """하위 프레임 해석: 역방향 맵 → ÷4(존재 시) → ÷6(존재 시) → None."""
    inverse = {upper: base for base, upper in UPPER_FRAME_MAP.items()}
    if interval in inverse:
        return inverse[interval]
    minutes = _interval_to_minutes(interval)
    if minutes is None:
        return None
    if minutes % 4 == 0:
        lower4 = _find_timeframe_by_minutes(minutes // 4)
        if lower4 is not None:
            return lower4
    if minutes % 6 == 0:
        return _find_timeframe_by_minutes(minutes // 6)
    return None


@dataclass
class TrendState:
    """일봉 60MA 기준 추세 상태."""
    direction: str = "검증불가"      # 상승 / 하락 / 횡보 / 검증불가
    slope_pct: float = 0.0
    price_above_ma: bool = False
    ma_value: float = 0.0
    valid: bool = False
    reason: str = ""


@dataclass
class WaveState:
    """단일 스토캐스틱 파동 상태."""
    label: str = ""
    direction: str = "검증불가"      # 상승(%K>%D) / 하락 / 검증불가
    k: float = 0.0
    d: float = 0.0
    zone: str = "중립"               # 과매도 / 과매수 / 중립
    double_bottom: str = "없음"       # 확정 / 후보 / 없음
    double_top: str = "없음"          # 확정 / 후보 / 없음
    db_kind: Optional[str] = None    # HL / LL / EQ (최근 쌍바닥 신호 기준)
    dt_kind: Optional[str] = None    # HH / LH / EQ (최근 쌍봉 신호 기준)
    triple_bottom: str = "없음"       # 확정 / 없음 (쓰리바닥은 후보 단계 없음)
    triple_top: str = "없음"          # 확정 / 없음
    tb_kind: Optional[str] = None    # HL / LL / EQ (바닥3 vs 바닥2)
    tt_kind: Optional[str] = None    # HH / LH / EQ (봉3 vs 봉2)
    valid: bool = False
    reason: str = ""


@dataclass
class WaveEnergyReport:
    """파동에너지 종합 분석 결과."""
    symbol: str
    interval: str
    trend: TrendState
    base_large: WaveState
    base_small: WaveState
    upper_interval: Optional[str]
    upper_small: WaveState
    mtf_agreement: str               # 일치 / 불일치 / 검증불가
    verdict: str
    notes: List[str] = field(default_factory=list)
    dynamics: Optional[DynamicsReport] = None


def _ensure_stochastic(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """스토캐스틱 컬럼이 없으면 계산해서 반환한다 (사이드바에서 끈 경우 대비)."""
    if df is None or df.empty:
        return df
    sample_suffix = STOCH_LAYERS[0]["label"]
    if f"stoch_k_{sample_suffix}" in df.columns:
        return df
    return add_stochastic_slow_layers(df.copy())


def _load_frame(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """main.py와 동일한 방식으로 한 프레임의 지표 포함 DataFrame을 로딩한다.

    실패 시 예외를 던지지 않고 None을 반환한다.
    """
    try:
        limit = get_auto_limit(interval)
        fetch_interval = get_fetch_interval(interval)
        raw = fetch_klines(symbol, fetch_interval, limit)
        if not raw:
            return None
        df = build_dataframe(raw)
        if df is None:
            return None
        if interval in CUSTOM_INTERVALS:
            df = resample_timeframe(df, interval)
        df = add_moving_averages(df)
        df = add_stochastic_slow_layers(df)
        return df
    except Exception:
        return None


def _pattern_status(df: pd.DataFrame, confirmed_col: str, candidate_col: str, recent_bars: int) -> str:
    """최근 recent_bars 봉 내 패턴 상태를 '확정/후보/없음'으로 보고한다."""
    if df is None or df.empty:
        return "없음"
    window = df.tail(max(int(recent_bars), 1))
    if confirmed_col in window.columns and window[confirmed_col].notna().any():
        return "확정"
    if candidate_col in window.columns and window[candidate_col].notna().any():
        return "후보"
    return "없음"


def _recent_kind(df: pd.DataFrame, confirmed_col: str, candidate_col: str, kind_col: str, recent_bars: int):
    """최근 recent_bars 내 패턴 kind를 읽는다 (확정 우선, 없으면 후보)."""
    if df is None or df.empty or kind_col not in df.columns:
        return None
    window = df.tail(max(int(recent_bars), 1))
    for signal_col in (confirmed_col, candidate_col):
        if signal_col not in window.columns:
            continue
        hits = window[window[signal_col].notna()]
        if hits.empty:
            continue
        value = hits[kind_col].iloc[-1]
        return None if pd.isna(value) else str(value)
    return None


def _wave_state(df: Optional[pd.DataFrame], suffix: str, label: str, params: dict) -> WaveState:
    """주어진 레이어(suffix)의 단일 파동 상태를 계산한다."""
    k_col = f"stoch_k_{suffix}"
    d_col = f"stoch_d_{suffix}"
    if df is None or df.empty or k_col not in df.columns or d_col not in df.columns:
        return WaveState(label=label, valid=False, reason="스토캐스틱 데이터 없음")

    k_series = df[k_col].dropna()
    d_series = df[d_col].dropna()
    if k_series.empty or d_series.empty:
        return WaveState(label=label, valid=False, reason="스토캐스틱 값 부족")

    k = float(k_series.iloc[-1])
    d = float(d_series.iloc[-1])
    direction = "상승" if k > d else "하락"

    oversold = params["oversold"]
    overbought = params["overbought"]
    if k < oversold:
        zone = "과매도"
    elif k > overbought:
        zone = "과매수"
    else:
        zone = "중립"

    recent = params["db_recent_bars"]
    double_bottom = _pattern_status(df, f"stoch_db_{suffix}", f"stoch_db_candidate_{suffix}", recent)
    double_top = _pattern_status(df, f"stoch_dt_{suffix}", f"stoch_dt_candidate_{suffix}", recent)
    db_kind = _recent_kind(df, f"stoch_db_{suffix}", f"stoch_db_candidate_{suffix}", f"stoch_db_kind_{suffix}", recent)
    dt_kind = _recent_kind(df, f"stoch_dt_{suffix}", f"stoch_dt_candidate_{suffix}", f"stoch_dt_kind_{suffix}", recent)

    # 쓰리바닥/쓰리봉은 후보 단계가 없으므로 확정 컬럼만 본다(candidate=confirmed 동일 전달).
    triple_bottom = _pattern_status(df, f"stoch_tb_{suffix}", f"stoch_tb_{suffix}", recent)
    triple_top = _pattern_status(df, f"stoch_tt_{suffix}", f"stoch_tt_{suffix}", recent)
    tb_kind = _recent_kind(df, f"stoch_tb_{suffix}", f"stoch_tb_{suffix}", f"stoch_tb_kind_{suffix}", recent)
    tt_kind = _recent_kind(df, f"stoch_tt_{suffix}", f"stoch_tt_{suffix}", f"stoch_tt_kind_{suffix}", recent)

    return WaveState(
        label=label,
        direction=direction,
        k=k,
        d=d,
        zone=zone,
        double_bottom=double_bottom,
        double_top=double_top,
        db_kind=db_kind,
        dt_kind=dt_kind,
        triple_bottom=triple_bottom,
        triple_top=triple_top,
        tb_kind=tb_kind,
        tt_kind=tt_kind,
        valid=True,
        reason="",
    )


def _trend_state(trend_df: Optional[pd.DataFrame], params: dict) -> TrendState:
    """일봉 60MA의 lookback 봉 대비 변화율(%)로 추세 방향을 판정한다."""
    ma_period = params["trend_ma"]
    lookback = max(int(params["trend_slope_lookback"]), 1)
    flat = params["trend_flat_band_pct"]
    ma_col = f"MA{ma_period}"

    if trend_df is None or trend_df.empty:
        return TrendState(valid=False, reason="일봉 데이터 로딩 실패")
    if ma_col not in trend_df.columns:
        return TrendState(valid=False, reason=f"{ma_col} 미계산")

    ma = trend_df[ma_col].dropna()
    if len(ma) <= lookback:
        return TrendState(valid=False, reason="60MA 추세 판정용 데이터 부족")

    cur = float(ma.iloc[-1])
    prev = float(ma.iloc[-1 - lookback])
    if prev == 0:
        return TrendState(valid=False, reason="기준 MA 값 0")

    slope_pct = (cur - prev) / abs(prev) * 100.0
    if slope_pct > flat:
        direction = "상승"
    elif slope_pct < -flat:
        direction = "하락"
    else:
        direction = "횡보"

    close = float(trend_df["close"].iloc[-1])
    return TrendState(
        direction=direction,
        slope_pct=slope_pct,
        price_above_ma=close > cur,
        ma_value=cur,
        valid=True,
        reason="",
    )


def _resolve_mtf(base_large: WaveState, upper_small: WaveState) -> str:
    """기준 대파동과 상위 프레임 소파동의 방향 일치 여부."""
    if not base_large.valid or not upper_small.valid:
        return "검증불가"
    return "일치" if base_large.direction == upper_small.direction else "불일치"


def _decide_verdict(trend: TrendState, base_large: WaveState, base_small: WaveState, mtf: str) -> str:
    """상승/하락 대칭 종합 판정 로직."""
    if not trend.valid or not base_large.valid or not base_small.valid:
        return "데이터 부족 — 판정 보류"

    if trend.direction == "횡보":
        return "⚖️ 60MA 횡보 — 추세 미형성, 관망"

    if trend.direction == "상승":
        if base_large.double_top == "확정":
            return "⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점"
        large_ok = base_large.direction == "상승" or base_large.double_bottom == "확정"
        timing_ok = base_small.zone == "과매도" or base_small.double_bottom in ("확정", "후보")
        if large_ok and mtf == "일치" and timing_ok:
            return "✅ 매수 관점 유효 (추세·대파동·타이밍 정렬)"
        if large_ok and mtf == "일치":
            return "🟡 매수 관점 — 소파동 타이밍 대기"
        if large_ok:
            return "🟠 대파동 상승 — 상위 프레임 검증 미충족"
        return "⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중"

    # 하락 추세 (상승과 완전 대칭). 단, 대파동 쌍바닥 확정이면 추세 전환 관찰을 우선한다.
    if base_large.double_bottom == "확정":
        return "⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰"
    large_ok = base_large.direction == "하락" or base_large.double_top == "확정"
    timing_ok = base_small.zone == "과매수" or base_small.double_top in ("확정", "후보")
    if large_ok and mtf == "일치" and timing_ok:
        return "✅ 매도 관점 유효 (추세·대파동·타이밍 정렬)"
    if large_ok and mtf == "일치":
        return "🟡 매도 관점 — 소파동 타이밍 대기"
    if large_ok:
        return "🟠 대파동 하락 — 상위 프레임 검증 미충족"
    return "⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중"


def analyze_wave_energy(df: pd.DataFrame, symbol: str, interval: str) -> WaveEnergyReport:
    """파동에너지 종합 분석을 수행한다.

    데이터 부족/로딩 실패는 예외 없이 valid=False + notes로 보고한다.
    """
    params = WAVE_ENERGY_PARAMS
    notes: List[str] = []

    layer_large = WAVE_LAYER_ROLES["large"]
    layer_small = WAVE_LAYER_ROLES["small"]

    base_df = _ensure_stochastic(df)
    base_large = _wave_state(base_df, layer_large, "대파동", params)
    base_small = _wave_state(base_df, layer_small, "소파동", params)
    if not base_large.valid:
        notes.append(f"기준 프레임 대파동 분석 불가: {base_large.reason}")
    if not base_small.valid:
        notes.append(f"기준 프레임 소파동 분석 불가: {base_small.reason}")

    # 확정 규칙 1: 추세는 항상 일봉 60MA
    trend_interval = params["trend_interval"]
    ma_col = f"MA{params['trend_ma']}"
    if interval == trend_interval:
        trend_df = base_df if (base_df is not None and ma_col in base_df.columns) else df
    else:
        trend_df = _load_frame(symbol, trend_interval)
        if trend_df is None:
            notes.append("일봉(1d) 추세 데이터 로딩 실패")
    trend = _trend_state(trend_df, params)
    if not trend.valid:
        notes.append(f"추세 분석 불가: {trend.reason}")

    # 확정 규칙 2: 상위 프레임의 소파동(Bot)을 읽어 MTF 검증
    upper_interval = resolve_upper_frame(interval)
    if upper_interval is None:
        upper_small = WaveState(label="상위 소파동", valid=False, reason="상위 프레임 없음")
        notes.append(f"'{interval}'의 상위 프레임 없음 (명시 맵·×4·×6 폴백 모두 불가)")
    else:
        upper_df = _load_frame(symbol, upper_interval)
        if upper_df is None:
            upper_small = WaveState(label="상위 소파동", valid=False, reason="상위 프레임 로딩 실패")
            notes.append(f"상위 프레임({upper_interval}) 로딩 실패")
        else:
            upper_small = _wave_state(upper_df, layer_small, "상위 소파동", params)

    mtf = _resolve_mtf(base_large, upper_small)
    verdict = _decide_verdict(trend, base_large, base_small, mtf)

    # 실전 역학관계(§6-①②): 기존 verdict와 별도로 산출한다.
    dynamics = evaluate_dynamics(base_df)

    return WaveEnergyReport(
        symbol=symbol,
        interval=interval,
        trend=trend,
        base_large=base_large,
        base_small=base_small,
        upper_interval=upper_interval,
        upper_small=upper_small,
        mtf_agreement=mtf,
        verdict=verdict,
        notes=notes,
        dynamics=dynamics,
    )
