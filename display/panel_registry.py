"""패널 레지스트리 (v2) — 45패널을 데이터로 선언, 루프 렌더 (§6).

main.py의 직접 import·나열("직접 import 신전")을 데이터 선언으로 해체한다. 기존 패널은
삭제하지 않고 "상세 분석" 탭에서 이 레지스트리로 재조립한다.

Type A 패널(symbol, interval 시그니처)만 데이터로 선언한다 — 대다수가 이 형태다.
Type B/C(사전 계산 상태 주입)는 main.py가 직접 다루므로 레지스트리 밖에 둔다.
render 함수는 지연 import(문자열 경로)로 참조해 임포트 폭발을 피한다.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class PanelSpec:
    key: str            # 세션/체크박스 키 (예: "show_wave_survival")
    label: str          # 사이드바 라벨
    module: str         # display.* 모듈 경로
    func: str           # 렌더 함수명 (symbol, interval)
    group: str = "상세 분석"

    def resolve(self) -> Callable:
        return getattr(importlib.import_module(self.module), self.func)


# Type A 패널 선언 (규칙=데이터). main.py의 render_xxx_panel(symbol, interval) 매핑.
TYPE_A_PANELS: List[PanelSpec] = [
    PanelSpec("show_wave_survival", "Wave Survival", "display.wave_survival_ui", "render_wave_survival_panel"),
    PanelSpec("show_wave_outcome", "Wave Outcome", "display.wave_outcome_ui", "render_wave_outcome_panel"),
    PanelSpec("show_wave_exit", "Wave Exit", "display.wave_exit_ui", "render_wave_exit_panel"),
    PanelSpec("show_wave_segmentation", "Wave Segmentation", "display.wave_segmentation_ui", "render_wave_segmentation_panel"),
    PanelSpec("show_wave_expectancy", "Wave Expectancy", "display.wave_expectancy_ui", "render_wave_expectancy_panel"),
    PanelSpec("show_wave_paths", "Wave Paths", "display.wave_paths_ui", "render_wave_paths_panel"),
    PanelSpec("show_wave_branch", "Wave Branch", "display.wave_branch_ui", "render_wave_branch_panel"),
    PanelSpec("show_wave_confluence", "Wave Confluence", "display.wave_confluence_ui", "render_wave_confluence_panel"),
    PanelSpec("show_candidate_rules", "Candidate Rules", "display.wave_candidate_rules_ui", "render_wave_candidate_rules_panel"),
    PanelSpec("show_generalization", "Generalization", "display.wave_generalization_ui", "render_wave_generalization_panel"),
    PanelSpec("show_regime_gated", "Regime Gated", "display.wave_regime_gated_ui", "render_wave_regime_gated_panel"),
    PanelSpec("show_rule_grading", "Rule Grading", "display.wave_rule_grading_ui", "render_wave_rule_grading_panel"),
    PanelSpec("show_grade_origin", "Grade Origin", "display.wave_grade_origin_ui", "render_wave_grade_origin_panel"),
    PanelSpec("show_grade_early_warning", "Grade Early Warning", "display.wave_grade_early_warning_ui", "render_wave_grade_early_warning_panel"),
    PanelSpec("show_grade_failure", "Grade Failure", "display.wave_grade_failure_ui", "render_wave_grade_failure_panel"),
    PanelSpec("show_confirmation_gate", "Confirmation Gate", "display.wave_confirmation_gate_ui", "render_wave_confirmation_gate_panel"),
    PanelSpec("show_watchlist_tracker", "Watchlist Tracker", "display.wave_watchlist_tracker_ui", "render_wave_watchlist_tracker_panel"),
    PanelSpec("show_grade_post_event", "Grade Post Event", "display.wave_grade_post_event_ui", "render_wave_grade_post_event_panel"),
    PanelSpec("show_volume_energy", "Volume Energy", "display.wave_volume_energy_ui", "render_wave_volume_energy_panel"),
    PanelSpec("show_energy_divergence", "Energy Divergence", "display.wave_energy_divergence_ui", "render_wave_energy_divergence_panel"),
    PanelSpec("show_money_flow", "Money Flow", "display.wave_money_flow_ui", "render_wave_money_flow_panel"),
    PanelSpec("show_structure_confirmation", "Structure Confirmation", "display.wave_structure_confirmation_ui", "render_wave_structure_confirmation_panel"),
    PanelSpec("show_structure_lte", "Structure LTE", "display.wave_structure_lte_ui", "render_wave_structure_lte_panel"),
    PanelSpec("show_quality_score", "Quality Score", "display.wave_quality_score_ui", "render_wave_quality_score_panel"),
    PanelSpec("show_quality_ruleset", "Quality Rule Set", "display.wave_quality_ruleset_ui", "render_wave_quality_ruleset_panel"),
    PanelSpec("show_ruleset_robustness", "Rule Set Robustness", "display.wave_ruleset_robustness_ui", "render_wave_ruleset_robustness_panel"),
    PanelSpec("show_cross_market", "Cross Market Validation", "display.wave_cross_market_validation_ui", "render_wave_cross_market_validation_panel"),
    PanelSpec("show_live_watchlist", "Live Watchlist", "display.wave_live_watchlist_ui", "render_wave_live_watchlist_panel"),
    PanelSpec("show_live_forward_journal", "Live Forward Journal", "display.wave_live_forward_journal_ui", "render_wave_live_forward_journal_panel"),
    PanelSpec("show_symbol_segmentation", "Symbol Segmentation", "display.wave_symbol_segmentation_ui", "render_wave_symbol_segmentation_panel"),
    PanelSpec("show_regime_segmentation", "Regime Segmentation", "display.wave_regime_segmentation_ui", "render_wave_regime_segmentation_panel"),
    PanelSpec("show_survival_segmentation", "Survival Segmentation", "display.wave_survival_segmentation_ui", "render_wave_survival_segmentation_panel"),
    PanelSpec("show_failure_trigger_validation", "Failure Trigger Validation", "display.wave_failure_trigger_validation_ui", "render_wave_failure_trigger_validation_panel"),
    PanelSpec("show_exit_policy_simulation", "Exit Policy Simulation", "display.wave_exit_policy_simulation_ui", "render_wave_exit_policy_simulation_panel"),
    PanelSpec("show_entry_filter_refinement", "Entry Filter Refinement", "display.wave_entry_filter_refinement_ui", "render_wave_entry_filter_refinement_panel"),
    PanelSpec("show_robustness_validation", "Robustness Validation", "display.wave_robustness_validation_ui", "render_wave_robustness_validation_panel"),
    PanelSpec("show_final_synthesis", "Final Synthesis", "display.wave_final_synthesis_ui", "render_wave_final_synthesis_panel"),
    PanelSpec("show_forward_observation", "Forward Observation", "display.wave_forward_observation_ui", "render_wave_forward_observation_panel"),
]


def render_type_a_panels(
    flags: dict,
    symbol: str,
    interval: str,
    registry: Optional[List[PanelSpec]] = None,
) -> List[str]:
    """flags[spec.key]가 True인 패널을 순서대로 렌더. 렌더된 키 목록 반환.

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
