"""상세 분석 탭 (11차 위임 A [탭2]) — 45패널을 카테고리 그룹으로 레지스트리 루프 렌더.

main.py의 45개 개별 호출을 데이터(레지스트리) 루프로 대체한다. 데이터는 심볼·TF당 1회
build_panel_context로 로드하고 모든 패널이 그 컨텍스트를 공유한다. 사이드바 토글은
카테고리 그룹으로 묶고, 레거시는 접힌 expander로 격리한다.

전 구간 관측 라벨 — 판정/추천/등급 없음. 분석 모듈 무수정(어댑터·조립만).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from display.asof import parse_as_of
from display.core_panels import is_narration_ui_available
from display.panel_context import IndicatorFlags, build_panel_context
from display.panel_registry import (
    CAT_CHART,
    CAT_CORE,
    CAT_LEGACY,
    CATEGORY_ORDER,
    panels_in_category,
    render_panel_safe,
    should_render,
)
from config.settings import CUSTOM_INTERVALS, TIMEFRAMES


@dataclass
class DetailConfig:
    interval: str
    as_of: Optional[pd.Timestamp]
    indicator_flags: IndicatorFlags
    ui_flags: Dict[str, object] = field(default_factory=dict)


def _category_toggles(category: str, ui: Dict[str, object], *, default: bool = False) -> None:
    """한 카테고리의 (always 아닌) 패널 체크박스를 사이드바에 렌더, ui에 기록."""
    for spec in panels_in_category(category):
        if spec.always:
            continue
        ui[spec.key] = st.sidebar.checkbox(
            spec.label, value=default, key=f"tgl_{spec.key}",
            help=spec.help or None,
        )


def render_detail_sidebar() -> DetailConfig:
    """상세 분석 탭 사이드바 — TF·기준시점·지표·패널 토글(카테고리 그룹). 설정 dict 반환."""
    ui: Dict[str, object] = {}
    st.sidebar.header("상세 분석 설정")
    interval = st.sidebar.selectbox(
        "Timeframe", options=TIMEFRAMES, index=TIMEFRAMES.index("1d"), key="detail_interval",
    )
    as_of_text = st.sidebar.text_input(
        "기준 시점 (백트레이스)", value="", placeholder="YYYY-MM-DD HH:MM",
        help="비우면 실시간. 설정 시 해당 시각 이하 데이터만 사용.", key="detail_asof",
    )
    as_of = parse_as_of(as_of_text)

    # 차트 지표
    st.sidebar.subheader("차트 지표")
    show_stoch = st.sidebar.checkbox("Stochastic Slow", value=True, key="ind_stoch")
    view_mode = st.sidebar.radio(
        "Stochastic View", options=["Stacked", "Separated"], index=0,
        disabled=not show_stoch, key="ind_stoch_view",
    )
    show_macd = st.sidebar.checkbox("MACD", value=True, key="ind_macd")
    show_rsi = st.sidebar.checkbox("RSI", value=True, key="ind_rsi")
    show_ma_patterns = st.sidebar.checkbox("MA Patterns", value=False, key="ind_ma_patterns")
    show_ma_dispersion = st.sidebar.checkbox("MA Dispersion", value=False, key="ind_ma_disp")
    indicator_flags = IndicatorFlags(
        show_stoch=show_stoch, stochastic_view_mode=view_mode, show_macd=show_macd,
        show_rsi=show_rsi, show_ma_patterns=show_ma_patterns, show_ma_dispersion=show_ma_dispersion,
    )

    # 핵심 분석 (요약·레이더는 always; 해설/디버그만 토글)
    st.sidebar.subheader(CAT_CORE)
    for spec in panels_in_category(CAT_CORE):
        if spec.always:
            continue
        if spec.key == "show_ai_narration" and not is_narration_ui_available():
            ui[spec.key] = False
            continue
        ui[spec.key] = st.sidebar.checkbox(
            spec.label, value=False, key=f"tgl_{spec.key}", help=spec.help or None,
        )

    # 나머지 라이브 카테고리 (차트/레거시/핵심 제외)
    for cat in CATEGORY_ORDER:
        if cat in (CAT_CORE, CAT_CHART, CAT_LEGACY):
            continue
        specs = [s for s in panels_in_category(cat) if not s.always]
        if not specs:
            continue
        st.sidebar.subheader(cat)
        _category_toggles(cat, ui)

    # 레거시 — 접힌 expander로 격리
    legacy_specs = panels_in_category(CAT_LEGACY)
    if legacy_specs:
        with st.sidebar.expander(f"{CAT_LEGACY} (격리 · 전역 스윕/대체됨)", expanded=False):
            for spec in legacy_specs:
                ui[spec.key] = st.checkbox(
                    spec.label, value=False, key=f"tgl_{spec.key}", help=spec.help or None,
                )

    return DetailConfig(
        interval=interval, as_of=as_of, indicator_flags=indicator_flags, ui_flags=ui,
    )


def _render_category(category: str, ctx) -> int:
    """한 카테고리에서 렌더 대상 패널을 렌더. 렌더 시도 수 반환."""
    specs = [s for s in panels_in_category(category) if should_render(s, ctx.ui)]
    if not specs:
        return 0
    # 핵심 분석/차트는 헤더 없이 인라인(각 패널이 자체 subheader/차트를 가짐).
    if category == CAT_LEGACY:
        with st.expander(f"{CAT_LEGACY} — 전역 스윕(현재 심볼/TF 무시)·신패널 대체본, 참조용", expanded=False):
            for spec in specs:
                render_panel_safe(spec, ctx)
        return len(specs)
    if category not in (CAT_CORE, CAT_CHART):
        st.markdown(f"## {category}")
    for spec in specs:
        render_panel_safe(spec, ctx)
    return len(specs)


def render_detail_tab(symbol: str, cfg: DetailConfig) -> None:
    """[탭2] 상세 분석 — 컨텍스트 1회 로드 후 카테고리 루프 렌더."""
    st.subheader(f"상세 분석 · {symbol} · {cfg.interval}")
    st.caption("45패널 레지스트리 루프(관측 라벨) · 데이터는 심볼·TF당 1회 로드·공유")

    try:
        with st.spinner(f"Loading {symbol} {cfg.interval} data..."):
            ctx = build_panel_context(
                symbol, cfg.interval, as_of=cfg.as_of, indicator_flags=cfg.indicator_flags,
            )
    except Exception as exc:  # noqa: BLE001 — 로드 실패 시 탭만 비활성, 앱 계속
        st.error(f"데이터 로드 실패: {exc}")
        return

    ctx.ui = cfg.ui_flags
    for w in ctx.warnings:
        st.warning(w)

    for cat in CATEGORY_ORDER:
        _render_category(cat, ctx)
