"""패널 데이터 컨텍스트 (11차 위임 B·C) — 심볼·TF당 1회 로드, 패널이 공유.

main.py가 매 패널마다 재수집하던 구조를 해체한다. build_panel_context가 OHLCV·지표·분석을
한 번 산출해 PanelContext에 담고, 상세 분석 탭의 모든 패널이 이 컨텍스트에서 필요한 조각만
꺼내 쓴다(어댑터). 사전 계산이 필요한 4개 패널(안정성·트래커·확인·수명)은 build_ohlcv_cache를
'한 번' 만들어 공유한다(기존 main.py는 패널마다 별도 build_ohlcv_cache를 4번 호출했다).

분석 모듈은 무수정 — 이 파일은 순수 표시/조립 계층이며 기존 asof/analysis 헬퍼를 호출만 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from config.settings import CUSTOM_INTERVALS
from data.binance import fetch_klines, fetch_klines_paginated, get_auto_limit
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from indicators.moving_averages import add_moving_averages
from indicators.ma_patterns import add_ma_patterns
from indicators.ma_dispersion import add_ma_dispersion
from indicators.stochastic import add_stochastic_slow_layers
from indicators.oscillators import add_macd, add_rsi
from analysis.engine import get_ma_alignment
from analysis.wave_energy import analyze_wave_energy
from analysis.dynamics_rules import trace_transitions
from display.asof import (
    build_ohlcv_cache,
    format_as_of_banner,
    patch_load_frame_for_asof,
    truncate_to_asof,
)
from display.transition_radar import build_transition_radar, prepare_trace_dataframe


@dataclass(frozen=True)
class IndicatorFlags:
    """차트/지표 토글 (사이드바에서 수집). 컨텍스트가 df에 반영할 지표를 결정한다."""
    show_stoch: bool = True
    stochastic_view_mode: str = "Stacked"
    show_macd: bool = True
    show_rsi: bool = True
    show_ma_patterns: bool = False
    show_ma_dispersion: bool = False


@dataclass
class PanelContext:
    """심볼·TF당 1회 산출된 공유 데이터·분석 컨텍스트.

    df: 지표가 반영된 (as-of 절단 후) 프레임. ohlcv_bare_full: 지표 없는 전체 OHLCV
    (사전 계산 패널의 build_ohlcv_cache 입력). 사전 계산 타임라인은 지연 산출·캐시.
    """
    symbol: str
    interval: str
    as_of: Optional[pd.Timestamp]
    df: pd.DataFrame
    ohlcv_bare_full: pd.DataFrame
    alignment: str
    report: object
    radar_content: object
    indicator_flags: IndicatorFlags
    limit: int
    warnings: List[str] = field(default_factory=list)
    # 패널 토글(체크박스) 상태 — 컨텍스트 패널 어댑터가 참조(narration/사전계산/차트 오버레이).
    ui: Dict[str, object] = field(default_factory=dict)

    # --- 지연 캐시 (사전 계산 패널 공유) ---
    _ohlcv_cache: Optional[Dict[str, pd.DataFrame]] = field(default=None, repr=False)
    _stability_aligned: object = field(default=None, repr=False)
    _wave_tracker_aligned: object = field(default=None, repr=False)
    _confirmation_episodes: object = field(default=None, repr=False)
    _lifecycle_episodes: object = field(default=None, repr=False)
    _computed: Dict[str, bool] = field(default_factory=dict, repr=False)

    @property
    def as_of_iso(self) -> str:
        return self.as_of.isoformat() if self.as_of is not None else ""

    def ohlcv_cache(self) -> Dict[str, pd.DataFrame]:
        """기준·추세·상위 프레임 bare OHLCV 캐시 — 사전 계산 패널이 공유(1회 생성)."""
        if self._ohlcv_cache is None:
            extra = {"4h": self.limit} if self.interval == "4h" else {}
            self._ohlcv_cache = build_ohlcv_cache(
                self.symbol, self.interval, self.ohlcv_bare_full, extra_limits=extra,
            )
        return self._ohlcv_cache

    # --- 사전 계산 타임라인 (지연 산출) ---
    def stability_aligned(self):
        if not self._computed.get("stability"):
            from display.stability_verdict import (
                align_enriched_to_index,
                get_stability_enriched,
            )
            cache = self.ohlcv_cache()
            if self.as_of is not None:
                with patch_load_frame_for_asof(self.symbol, self.as_of, cache):
                    enriched = get_stability_enriched(
                        self.symbol, self.interval, self.df, cache, self.as_of_iso,
                    )
            else:
                enriched = get_stability_enriched(
                    self.symbol, self.interval, self.df, cache, self.as_of_iso,
                )
            self._stability_aligned = align_enriched_to_index(enriched, self.df.index)
            self._computed["stability"] = True
        return self._stability_aligned

    def wave_tracker_aligned(self):
        if not self._computed.get("wave_tracker"):
            from display.wave_tracker_ui import (
                align_timeline_to_index,
                get_wave_tracker_timeline,
            )
            cache = self.ohlcv_cache()
            if self.as_of is not None:
                with patch_load_frame_for_asof(self.symbol, self.as_of, cache):
                    tl = get_wave_tracker_timeline(
                        self.symbol, self.interval, self.df, cache, self.as_of_iso,
                    )
            else:
                tl = get_wave_tracker_timeline(
                    self.symbol, self.interval, self.df, cache, self.as_of_iso,
                )
            self._wave_tracker_aligned = align_timeline_to_index(tl, self.df.index)
            self._computed["wave_tracker"] = True
        return self._wave_tracker_aligned

    def confirmation_episodes(self):
        if not self._computed.get("confirmation"):
            from display.wave_confirmation_ui import get_confirmation_episodes
            cache = self.ohlcv_cache()
            if self.as_of is not None:
                with patch_load_frame_for_asof(self.symbol, self.as_of, cache):
                    ep = get_confirmation_episodes(
                        self.symbol, self.interval, self.df, cache, self.as_of_iso,
                    )
            else:
                ep = get_confirmation_episodes(
                    self.symbol, self.interval, self.df, cache, self.as_of_iso,
                )
            self._confirmation_episodes = ep
            self._computed["confirmation"] = True
        return self._confirmation_episodes

    def lifecycle_episodes(self):
        if not self._computed.get("lifecycle"):
            from display.wave_confirmation_lifecycle_ui import get_lifecycle_episodes
            cache = self.ohlcv_cache()
            if self.as_of is not None:
                with patch_load_frame_for_asof(self.symbol, self.as_of, cache):
                    ep = get_lifecycle_episodes(
                        self.symbol, self.interval, self.df, cache, self.as_of_iso,
                    )
            else:
                ep = get_lifecycle_episodes(
                    self.symbol, self.interval, self.df, cache, self.as_of_iso,
                )
            self._lifecycle_episodes = ep
            self._computed["lifecycle"] = True
        return self._lifecycle_episodes


def _fetch_base_frame(symbol: str, interval: str, limit: int, as_of: Optional[pd.Timestamp]) -> pd.DataFrame:
    """OHLCV fetch → DataFrame → (커스텀 인터벌) 리샘플. main.py 데이터 경로 이관."""
    fetch_interval = get_fetch_interval(interval)
    if as_of is not None and limit > 1000:
        raw_data = fetch_klines_paginated(symbol, fetch_interval, limit)
    else:
        raw_data = fetch_klines(symbol, fetch_interval, limit)
    if not raw_data:
        raise ValueError(f"Failed to fetch data for {symbol}.")
    df = build_dataframe(raw_data)
    if df is None or df.empty:
        raise ValueError("Failed to build DataFrame.")
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)
    return df


def compute_limit(symbol: str, interval: str, as_of: Optional[pd.Timestamp]) -> int:
    """auto-limit + as-of ETHUSDT/4h 특례 (main.py 이관)."""
    limit = get_auto_limit(interval)
    if as_of is not None and symbol == "ETHUSDT" and interval == "4h":
        limit = 1600
    return limit


def build_panel_context(
    symbol: str,
    interval: str,
    *,
    as_of: Optional[pd.Timestamp] = None,
    indicator_flags: Optional[IndicatorFlags] = None,
) -> PanelContext:
    """심볼·TF당 1회: OHLCV·지표·분석(정합·리포트·레이더)을 산출해 컨텍스트로 반환.

    main.py main()의 데이터/분석 블록을 그대로 이관(엔진 무수정). as-of·워밍업 부족은
    ValueError로 신호(호출 탭이 st.error로 표시).
    """
    flags = indicator_flags or IndicatorFlags()
    limit = compute_limit(symbol, interval, as_of)
    warnings: List[str] = []

    df = _fetch_base_frame(symbol, interval, limit, as_of)
    ohlcv_bare_full = df.copy()

    if as_of is not None:
        df = truncate_to_asof(df, as_of)
        if df is None or df.empty:
            raise ValueError("기준 시점 이전 데이터가 없습니다.")
        if len(df) < 240:
            raise ValueError("기준 시점 이전 봉이 240미만 — MA 워밍업 부족.")
        warnings.append(format_as_of_banner(as_of))

    # 지표 계산 (토글 반영, main.py와 동일 순서)
    df = add_moving_averages(df)
    if flags.show_ma_patterns:
        df = add_ma_patterns(df)
    if flags.show_stoch:
        df = add_stochastic_slow_layers(df)
    if flags.show_macd:
        df = add_macd(df)
    if flags.show_rsi:
        df = add_rsi(df)
    if flags.show_ma_dispersion:
        df = add_ma_dispersion(df)

    # 분석: MA 정합 + 파동에너지 리포트 + 변곡 레이더
    alignment = get_ma_alignment(df)
    if as_of is not None:
        extra = {"4h": limit} if interval == "4h" else {}
        cache = build_ohlcv_cache(symbol, interval, ohlcv_bare_full, extra_limits=extra)
        with patch_load_frame_for_asof(symbol, as_of, cache):
            report = analyze_wave_energy(df, symbol, interval)
        prebuilt_cache = cache
    else:
        report = analyze_wave_energy(df, symbol, interval)
        prebuilt_cache = None

    trace_df = prepare_trace_dataframe(df)
    radar_content = build_transition_radar(trace_df, trace_transitions(trace_df))

    ctx = PanelContext(
        symbol=symbol,
        interval=interval,
        as_of=as_of,
        df=df,
        ohlcv_bare_full=ohlcv_bare_full,
        alignment=alignment,
        report=report,
        radar_content=radar_content,
        indicator_flags=flags,
        limit=limit,
        warnings=warnings,
    )
    # as-of 리포트를 산출하며 만든 cache를 재사용(중복 fetch 방지).
    if prebuilt_cache is not None:
        ctx._ohlcv_cache = prebuilt_cache
    return ctx
