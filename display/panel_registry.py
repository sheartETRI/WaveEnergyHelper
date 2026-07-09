"""패널 레지스트리 (v2, 11차 위임 B) — 45패널을 데이터로 선언, 카테고리 루프 렌더 (§6).

main.py의 직접 import·나열("직접 import 신전")을 데이터 선언으로 해체한다. 기존 패널은
삭제하지 않고 "상세 분석" 탭에서 이 레지스트리로 재조립한다.

두 종류의 패널:
  · Type A — render_xxx_panel(symbol, interval) 시그니처(38개). module/func 문자열로 지연 참조.
  · 컨텍스트 패널 — 사전 계산 상태·분석 결과가 필요(핵심 요약/레이더/해설/차트/사전계산 4종).
    시그니처가 제각각이라 display 쪽 얇은 어댑터(PanelContext → 패널별 인자)로 통일한다.
    분석 모듈은 무수정 — 어댑터가 컨텍스트에서 필요한 조각만 꺼내 기존 렌더 함수를 호출.

레거시: 전역 스윕(현재 symbol/interval 무시)이거나 신패널로 대체된 v1 검증 시각화는 삭제하지
않고 category="레거시"로 격리한다(무엇을 격리했는지는 REPORT_APP_RESTRUCTURE.md 참조).

전 구간 관측 라벨 — 등급/추천/판정 문구 없음.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, List, Optional

# --- 카테고리 표시 순서 (상세 분석 탭 렌더 순서). 차트는 항상 마지막(기존 main.py 동작 보존). ---
CAT_CORE = "핵심 분석"
CAT_WAVE = "파동 구조·추적"
CAT_INDICATOR = "관측 지표"
CAT_SEGMENT = "세그먼트"
CAT_ROBUST = "검증·강건성"
CAT_SIM = "시뮬·정제"
CAT_LIVE = "라이브·포워드·종합"
CAT_PRECOMPUTED = "파동 상태 (사전계산)"
CAT_LEGACY = "레거시"
CAT_CHART = "차트"

CATEGORY_ORDER = [
    CAT_CORE,
    CAT_WAVE,
    CAT_INDICATOR,
    CAT_SEGMENT,
    CAT_ROBUST,
    CAT_SIM,
    CAT_LIVE,
    CAT_PRECOMPUTED,
    CAT_LEGACY,
    CAT_CHART,
]


@dataclass(frozen=True)
class PanelSpec:
    key: str                       # 세션/체크박스 키 (예: "show_wave_survival")
    label: str                     # 사이드바 라벨
    module: str = ""               # Type A: display.* 모듈 경로 (컨텍스트 패널은 "")
    func: str = ""                 # Type A: 렌더 함수명 (symbol, interval)
    category: str = "상세 분석"     # 카테고리 그룹
    adapter: Optional[Callable] = None  # 컨텍스트 패널: adapter(ctx) 호출(있으면 func 대신)
    always: bool = False           # 플래그와 무관하게 렌더(핵심 요약/레이더/차트)
    legacy: bool = False           # 레거시 격리 대상(표시하되 접힘/하단)
    help: str = ""                 # 사이드바 툴팁

    def resolve(self) -> Callable:
        return getattr(importlib.import_module(self.module), self.func)

    def render(self, ctx) -> None:
        """어댑터가 있으면 컨텍스트로, 없으면 (symbol, interval)로 렌더."""
        if self.adapter is not None:
            self.adapter(ctx)
        else:
            self.resolve()(ctx.symbol, ctx.interval)


# ============================================================ 컨텍스트 패널 어댑터
# PanelContext에서 필요한 조각만 꺼내 기존 렌더 함수를 호출한다(분석 모듈 무수정).
# 지연 import로 임포트 폭발/순환을 피한다.

def _adapt_wave_summary(ctx) -> None:
    from display.core_panels import render_wave_summary
    render_wave_summary(ctx.report, ctx.alignment)


def _adapt_transition_radar(ctx) -> None:
    from display.core_panels import render_transition_radar_content
    render_transition_radar_content(ctx.radar_content)


def _adapt_narration(ctx) -> None:
    from display.core_panels import render_wave_narration_if_enabled
    render_wave_narration_if_enabled(
        bool(ctx.ui.get("show_ai_narration")),
        ctx.report, ctx.alignment, ctx.df, ctx.radar_content,
    )


def _adapt_dynamics_trace(ctx) -> None:
    from display.core_panels import render_dynamics_trace
    render_dynamics_trace(ctx.df)


def _adapt_stability(ctx) -> None:
    from display.stability_verdict import render_stability_verdict_panel
    render_stability_verdict_panel(ctx.stability_aligned())


def _adapt_wave_tracker(ctx) -> None:
    from display.wave_tracker_ui import render_wave_tracker_panel
    render_wave_tracker_panel(ctx.wave_tracker_aligned())


def _adapt_wave_confirmation(ctx) -> None:
    from display.wave_confirmation_ui import render_wave_confirmation_panel
    render_wave_confirmation_panel(ctx.confirmation_episodes())


def _adapt_wave_lifecycle(ctx) -> None:
    from display.wave_confirmation_lifecycle_ui import render_wave_lifecycle_panel
    render_wave_lifecycle_panel(ctx.lifecycle_episodes())


def _adapt_chart(ctx) -> None:
    from charts.plotly_builder import render_chart
    f = ctx.indicator_flags
    show_stab = bool(ctx.ui.get("show_stability_verdict"))
    show_wt = bool(ctx.ui.get("show_wave_tracker"))
    render_chart(
        ctx.df, ctx.symbol, ctx.interval,
        show_stochastic=f.show_stoch,
        stochastic_view_mode=f.stochastic_view_mode,
        show_stoch_fill=f.show_stoch,
        show_macd=f.show_macd,
        show_rsi=f.show_rsi,
        show_rsi_fill=f.show_rsi,
        show_ma_patterns=f.show_ma_patterns,
        show_ma_dispersion=f.show_ma_dispersion,
        show_stability=show_stab,
        stability_aligned=ctx.stability_aligned() if show_stab else None,
        show_wave_tracker=show_wt,
        wave_tracker_aligned=ctx.wave_tracker_aligned() if show_wt else None,
    )


# 컨텍스트 패널(핵심 요약/레이더/해설/디버그/사전계산 4종/차트). always=핵심 요약·레이더·차트.
CONTEXT_PANELS: List[PanelSpec] = [
    PanelSpec("core_wave_summary", "파동에너지 요약", category=CAT_CORE, adapter=_adapt_wave_summary, always=True),
    PanelSpec("core_transition_radar", "변곡 레이더", category=CAT_CORE, adapter=_adapt_transition_radar, always=True),
    PanelSpec("show_ai_narration", "AI 해설", category=CAT_CORE, adapter=_adapt_narration,
              help="옵트인 시에만 외부 AI 호출(관측 보조)"),
    PanelSpec("debug_dynamics_trace", "Debug: Dynamics Trace", category=CAT_CORE, adapter=_adapt_dynamics_trace,
              help="§6-④⑤ 변곡점 트레이스 + 구조 분포(관측 전용)"),
    PanelSpec("show_stability_verdict", "Stability Verdict", category=CAT_PRECOMPUTED, adapter=_adapt_stability,
              help="안정화 verdict 타임라인(사전 계산)"),
    PanelSpec("show_wave_tracker", "Wave Tracker", category=CAT_PRECOMPUTED, adapter=_adapt_wave_tracker,
              help="파동 카운팅 타임라인(사전 계산)"),
    PanelSpec("show_wave_confirmation", "Wave Confirmation", category=CAT_PRECOMPUTED, adapter=_adapt_wave_confirmation,
              help="확인 에피소드(사전 계산)"),
    PanelSpec("show_wave_lifecycle", "Wave Lifecycle", category=CAT_PRECOMPUTED, adapter=_adapt_wave_lifecycle,
              help="확인 수명 에피소드(사전 계산)"),
    PanelSpec("core_chart", "메인 차트", category=CAT_CHART, adapter=_adapt_chart, always=True),
]


# ============================================================ Type A 패널 (규칙=데이터)
# render_xxx_panel(symbol, interval). category/legacy는 11차 위임 조사(Explore 맵) 기준.
TYPE_A_PANELS: List[PanelSpec] = [
    # --- 파동 구조·추적 (per-symbol CSV) ---
    PanelSpec("show_wave_survival", "Wave Survival", "display.wave_survival_ui", "render_wave_survival_panel", category=CAT_WAVE),
    PanelSpec("show_wave_outcome", "Wave Outcome", "display.wave_outcome_ui", "render_wave_outcome_panel", category=CAT_WAVE,
              help="CSV 우선; CSV 부재 시 OHLCV fetch 폴백(네트워크)"),
    PanelSpec("show_wave_exit", "Wave Exit", "display.wave_exit_ui", "render_wave_exit_panel", category=CAT_WAVE),
    PanelSpec("show_wave_expectancy", "Wave Expectancy", "display.wave_expectancy_ui", "render_wave_expectancy_panel", category=CAT_WAVE),
    PanelSpec("show_wave_paths", "Wave Paths", "display.wave_paths_ui", "render_wave_paths_panel", category=CAT_WAVE),
    PanelSpec("show_wave_branch", "Wave Branch", "display.wave_branch_ui", "render_wave_branch_panel", category=CAT_WAVE),
    PanelSpec("show_wave_confluence", "Wave Confluence", "display.wave_confluence_ui", "render_wave_confluence_panel", category=CAT_WAVE),
    PanelSpec("show_candidate_rules", "Candidate Rules", "display.wave_candidate_rules_ui", "render_wave_candidate_rules_panel", category=CAT_WAVE),
    # --- 관측 지표 (per-symbol 현재값 관측) ---
    PanelSpec("show_volume_energy", "Volume Energy", "display.wave_volume_energy_ui", "render_wave_volume_energy_panel", category=CAT_INDICATOR),
    PanelSpec("show_energy_divergence", "Energy Divergence", "display.wave_energy_divergence_ui", "render_wave_energy_divergence_panel", category=CAT_INDICATOR),
    PanelSpec("show_money_flow", "Money Flow", "display.wave_money_flow_ui", "render_wave_money_flow_panel", category=CAT_INDICATOR),
    PanelSpec("show_structure_confirmation", "Structure Confirmation", "display.wave_structure_confirmation_ui", "render_wave_structure_confirmation_panel", category=CAT_INDICATOR),
    PanelSpec("show_structure_lte", "Structure LTE", "display.wave_structure_lte_ui", "render_wave_structure_lte_panel", category=CAT_INDICATOR),
    PanelSpec("show_quality_score", "Quality Score", "display.wave_quality_score_ui", "render_wave_quality_score_panel", category=CAT_INDICATOR),
    PanelSpec("show_quality_ruleset", "Quality Rule Set", "display.wave_quality_ruleset_ui", "render_wave_quality_ruleset_panel", category=CAT_INDICATOR),
    # --- 세그먼트 ---
    PanelSpec("show_wave_segmentation", "Wave Segmentation", "display.wave_segmentation_ui", "render_wave_segmentation_panel", category=CAT_SEGMENT),
    PanelSpec("show_symbol_segmentation", "Symbol Segmentation", "display.wave_symbol_segmentation_ui", "render_wave_symbol_segmentation_panel", category=CAT_SEGMENT),
    PanelSpec("show_regime_segmentation", "Regime Segmentation", "display.wave_regime_segmentation_ui", "render_wave_regime_segmentation_panel", category=CAT_SEGMENT),
    PanelSpec("show_survival_segmentation", "Survival Segmentation", "display.wave_survival_segmentation_ui", "render_wave_survival_segmentation_panel", category=CAT_SEGMENT),
    # --- 검증·강건성 ---
    PanelSpec("show_ruleset_robustness", "Rule Set Robustness", "display.wave_ruleset_robustness_ui", "render_wave_ruleset_robustness_panel", category=CAT_ROBUST),
    PanelSpec("show_cross_market", "Cross Market Validation", "display.wave_cross_market_validation_ui", "render_wave_cross_market_validation_panel", category=CAT_ROBUST),
    PanelSpec("show_failure_trigger_validation", "Failure Trigger Validation", "display.wave_failure_trigger_validation_ui", "render_wave_failure_trigger_validation_panel", category=CAT_ROBUST),
    PanelSpec("show_robustness_validation", "Robustness Validation", "display.wave_robustness_validation_ui", "render_wave_robustness_validation_panel", category=CAT_ROBUST),
    # --- 시뮬·정제 ---
    PanelSpec("show_exit_policy_simulation", "Exit Policy Simulation", "display.wave_exit_policy_simulation_ui", "render_wave_exit_policy_simulation_panel", category=CAT_SIM),
    PanelSpec("show_entry_filter_refinement", "Entry Filter Refinement", "display.wave_entry_filter_refinement_ui", "render_wave_entry_filter_refinement_panel", category=CAT_SIM),
    # --- 라이브·포워드·종합 ---
    PanelSpec("show_live_watchlist", "Live Watchlist", "display.wave_live_watchlist_ui", "render_wave_live_watchlist_panel", category=CAT_LIVE),
    PanelSpec("show_live_forward_journal", "Live Forward Journal", "display.wave_live_forward_journal_ui", "render_wave_live_forward_journal_panel", category=CAT_LIVE),
    PanelSpec("show_forward_observation", "Forward Observation", "display.wave_forward_observation_ui", "render_wave_forward_observation_panel", category=CAT_LIVE),
    PanelSpec("show_final_synthesis", "Final Synthesis", "display.wave_final_synthesis_ui", "render_wave_final_synthesis_panel", category=CAT_LIVE),
    # --- 레거시 (전역 스윕·대체됨 — 격리, 삭제 아님) ---
    PanelSpec("show_generalization", "Generalization", "display.wave_generalization_ui", "render_wave_generalization_panel", category=CAT_LEGACY, legacy=True,
              help="전역 12셀 스윕(symbol/interval 무시) · robustness_validation이 대체"),
    PanelSpec("show_regime_gated", "Regime Gated", "display.wave_regime_gated_ui", "render_wave_regime_gated_panel", category=CAT_LEGACY, legacy=True,
              help="전역 레짐 필터 스윕 · regime_segmentation+robustness가 대체"),
    PanelSpec("show_rule_grading", "Rule Grading", "display.wave_rule_grading_ui", "render_wave_rule_grading_panel", category=CAT_LEGACY, legacy=True,
              help="ALL_SYMBOL/ALL_TF 전역 캘리브레이션 · quality_score가 대체"),
    PanelSpec("show_grade_origin", "Grade Origin", "display.wave_grade_origin_ui", "render_wave_grade_origin_panel", category=CAT_LEGACY, legacy=True,
              help="1회성 리포트-파싱 스윕(symbol/interval 무시)"),
    PanelSpec("show_grade_early_warning", "Grade Early Warning", "display.wave_grade_early_warning_ui", "render_wave_grade_early_warning_panel", category=CAT_LEGACY, legacy=True,
              help="1회성 조기경보 스윕(symbol/interval 무시)"),
    PanelSpec("show_grade_failure", "Grade Failure", "display.wave_grade_failure_ui", "render_wave_grade_failure_panel", category=CAT_LEGACY, legacy=True,
              help="1회성 실패원인 스윕(symbol/interval 무시)"),
    PanelSpec("show_grade_post_event", "Grade Post Event", "display.wave_grade_post_event_ui", "render_wave_grade_post_event_panel", category=CAT_LEGACY, legacy=True,
              help="대부분 전역 지연 스윕(per-symbol 최소)"),
    PanelSpec("show_confirmation_gate", "Confirmation Gate", "display.wave_confirmation_gate_ui", "render_wave_confirmation_gate_panel", category=CAT_LEGACY, legacy=True,
              help="전역 게이트 P/R 스윕 · entry_filter_refinement가 대체"),
    PanelSpec("show_watchlist_tracker", "Watchlist Tracker", "display.wave_watchlist_tracker_ui", "render_wave_watchlist_tracker_panel", category=CAT_LEGACY, legacy=True,
              help="전역 상태전이 스윕(코드 주석: 실시간 상태머신 아님) · live_watchlist가 대체"),
]


# ============================================================ 레지스트리 뷰/헬퍼
def all_panels() -> List[PanelSpec]:
    """컨텍스트 패널 + Type A 전체(45개 안팎). 카테고리 그룹핑 입력."""
    return CONTEXT_PANELS + TYPE_A_PANELS


def panels_in_category(category: str, registry: Optional[List[PanelSpec]] = None) -> List[PanelSpec]:
    reg = registry if registry is not None else all_panels()
    return [p for p in reg if p.category == category]


def should_render(spec: PanelSpec, flags: dict) -> bool:
    """always 패널은 항상, 그 외는 flags[key]가 True일 때만."""
    return bool(spec.always) or bool(flags.get(spec.key))


def render_panel_safe(spec: PanelSpec, ctx) -> bool:
    """패널 1개 렌더(예외 격리). 렌더 성공/시도 여부 반환."""
    try:
        spec.render(ctx)
        return True
    except Exception as exc:  # noqa: BLE001 — 개별 패널 격리(관측 UI 안정성)
        import streamlit as st
        st.warning(f"패널 {spec.label} 렌더 실패: {exc}")
        return False


def render_type_a_panels(
    flags: dict,
    symbol: str,
    interval: str,
    registry: Optional[List[PanelSpec]] = None,
) -> List[str]:
    """[하위 호환] flags[spec.key]가 True인 Type A 패널을 순서대로 렌더. 렌더된 키 목록 반환.

    한 패널 렌더 실패가 전체를 막지 않도록 예외를 격리한다(관측 UI 안정성).
    """
    reg = registry if registry is not None else TYPE_A_PANELS
    rendered: List[str] = []
    for spec in reg:
        if not flags.get(spec.key):
            continue
        try:
            spec.resolve()(symbol, interval)
            rendered.append(spec.key)
        except Exception as exc:  # noqa: BLE001 — 개별 패널 격리
            import streamlit as st
            st.warning(f"패널 {spec.label} 렌더 실패: {exc}")
    return rendered
