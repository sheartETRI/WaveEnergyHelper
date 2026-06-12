"""Wave Final Synthesis — #1~#25 연구 통합 결론 (관측 전용).

기존 REPORT·CSV만 읽음. 재계산·기존 산출물 수정 없음.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)

REPORT_FINAL = "REPORT_WAVE_FINAL_SYNTHESIS.md"
PNG_FINAL = "wave_final_synthesis.png"

# #1~#25 연구 연대기 (기존 REPORT 기반 요약, 재계산 없음)
RESEARCH_TIMELINE: Tuple[dict, ...] = (
    {"step": 1, "name": "Wave Validation", "report": "REPORT_VERDICT.md", "finding": "Wave 경로·에너지 기본 검증"},
    {"step": 2, "name": "Multi-Indicator Validation", "report": "REPORT_WAVE_MONEY_FLOW.md", "finding": "Money Flow·Volume·Structure 지표 유효성 확인"},
    {"step": 3, "name": "Structure Confirmation", "report": "REPORT_WAVE_STRUCTURE_CONFIRMATION.md", "finding": "구조 확인 레이어 분리"},
    {"step": 4, "name": "Regime Analysis", "report": "REPORT_WAVE_REGIME.md", "finding": "BULL/BEAR/SIDEWAYS 레짐 분류"},
    {"step": 5, "name": "Outcome Analysis", "report": "REPORT_WAVE_OUTCOME.md", "finding": "+5/+10/+20/+40 forward return 체계"},
    {"step": 6, "name": "Expectancy Analysis", "report": "REPORT_WAVE_EXPECTANCY.md", "finding": "기대값·PF 프레임워크"},
    {"step": 7, "name": "Survival Analysis", "report": "REPORT_WAVE_SURVIVAL.md", "finding": "INITIAL 경로 생존율"},
    {"step": 8, "name": "Exit Analysis", "report": "REPORT_WAVE_EXIT.md", "finding": "청산 규칙 사후 검증"},
    {"step": 9, "name": "Segmentation", "report": "REPORT_WAVE_SEGMENTATION.md", "finding": "다차원 세그먼트 분해"},
    {"step": 10, "name": "Quality Score", "report": "REPORT_WAVE_QUALITY_SCORE.md", "finding": "품질 점수 체계"},
    {"step": 11, "name": "Rule Discovery", "report": "REPORT_WAVE_CANDIDATE_RULES.md", "finding": "RULE_A/B/C 후보 도출"},
    {"step": 12, "name": "Rule Grading", "report": "REPORT_WAVE_RULE_GRADING.md", "finding": "Rule 등급화"},
    {"step": 13, "name": "Ruleset Robustness", "report": "REPORT_WAVE_RULESET_ROBUSTNESS.md", "finding": "Rule 세트 견고성"},
    {"step": 14, "name": "Cross Market Validation", "report": "REPORT_WAVE_CROSS_MARKET_VALIDATION.md", "finding": "다시장 재현 검증"},
    {"step": 15, "name": "Generalization", "report": "REPORT_WAVE_GENERALIZATION.md", "finding": "일반화 한계 확인"},
    {"step": 16, "name": "Live Watchlist", "report": "REPORT_WAVE_LIVE_WATCHLIST.md", "finding": "500봉 실시간 스캔·ACTIVE 37"},
    {"step": 17, "name": "Live Forward Journal", "report": "REPORT_WAVE_LIVE_FORWARD_JOURNAL.md", "finding": "2,091 events forward 추적"},
    {"step": 18, "name": "Symbol Segmentation", "report": "REPORT_WAVE_SYMBOL_SEGMENTATION.md", "finding": "BNB 우위, SOL/ETH 약세"},
    {"step": 19, "name": "Regime Segmentation", "report": "REPORT_WAVE_REGIME_SEGMENTATION.md", "finding": "Regime 기여 0.57%"},
    {"step": 20, "name": "Survival Segmentation", "report": "REPORT_WAVE_SURVIVAL_SEGMENTATION.md", "finding": "RULE_C surv 28.37%, residual 96%"},
    {"step": 21, "name": "Failure Trigger Validation", "report": "REPORT_WAVE_FAILURE_TRIGGER_VALIDATION.md", "finding": "STOP_LOSS_3 균형, STRUCTURE F1 최고"},
    {"step": 22, "name": "Exit Policy Simulation", "report": "REPORT_WAVE_EXIT_POLICY_SIMULATION.md", "finding": "Exit는 손실방어, 수익 개선 제한"},
    {"step": 23, "name": "Entry Filter Refinement", "report": "REPORT_WAVE_ENTRY_FILTER_REFINEMENT.md", "finding": "BNB+고품질 feature 대폭 개선"},
    {"step": 24, "name": "Robustness Validation", "report": "REPORT_WAVE_ROBUSTNESS_VALIDATION.md", "finding": "Champion CONDITIONAL, Filter_BNB_CORE ROBUST"},
    {"step": 25, "name": "Final Synthesis", "report": REPORT_FINAL, "finding": "통합 결론 도출"},
)

HYPOTHESES: Tuple[dict, ...] = (
    {"id": "wave_solo", "name": "Wave 단독 가설", "verdict": "PARTIAL",
     "rationale": "Baseline expectancy +0.27, PF 1.14 — 약한 양(+)이나 residual 96%"},
    {"id": "triple_bottom", "name": "Triple Bottom 가설", "verdict": "PARTIAL",
     "rationale": "structure>=5 expectancy 0.78 — 단독 TB 신호만으로는 불충분"},
    {"id": "money_flow", "name": "Money Flow 가설", "verdict": "PARTIAL",
     "rationale": "mf>=5 expectancy 0.70; trigger로는 false exit 94%"},
    {"id": "structure", "name": "Structure 가설", "verdict": "PARTIAL",
     "rationale": "STRUCTURE_FAIL F1 72.55%; structure>=5 PF 1.40"},
    {"id": "rule_universal", "name": "Rule 범용성 가설", "verdict": "REJECTED",
     "rationale": "RULE_A exp 0.00 vs RULE_C 0.40; Rule contribution 0.03%"},
    {"id": "symbol", "name": "Symbol 가설", "verdict": "PARTIAL",
     "rationale": "BNB exp 1.56 vs SOL -1.06; Symbol contribution 1.89%"},
    {"id": "regime", "name": "Regime 가설", "verdict": "PARTIAL",
     "rationale": "BULL 0.53 vs BEAR -1.26; Regime contribution 0.57%"},
    {"id": "exit_improve", "name": "Exit 개선 가설", "verdict": "REJECTED",
     "rationale": "어떤 Exit Policy도 baseline expectancy 0.27 초과 못함"},
)

CONTRIBUTION = {
    "rule": 0.03,
    "symbol": 1.89,
    "regime": 0.57,
    "survival_feature": 1.13,
    "residual": 96.38,
}

CHAMPION_RULES = (
    {"rule": "RULE_A", "expectancy": 0.00, "survival_rate": 22.08, "verdict": "WEAK"},
    {"rule": "RULE_B", "expectancy": 0.34, "survival_rate": 22.93, "verdict": "CONDITIONAL"},
    {"rule": "RULE_C", "expectancy": 0.40, "survival_rate": 28.37, "verdict": "PROMISING"},
)

CHAMPION_FILTERS = (
    {"id": "CHAMPION", "label": "RULE_A+BNB+mf>=5+struct>=5",
     "n": 59, "expectancy": 4.09, "pf": 4.37, "survival": 42.37, "verdict": "CONDITIONAL"},
    {"id": "Filter_BNB_CORE", "label": "BNB+mf>=5+struct>=5",
     "n": 213, "expectancy": 3.02, "pf": None, "survival": 41.31, "verdict": "ROBUST"},
    {"id": "Filter_Q", "label": "quality>=4",
     "n": 750, "expectancy": 0.91, "pf": 1.70, "survival": 27.60, "verdict": "CONDITIONAL"},
)

CHAMPION_EXIT = (
    {"policy": "POLICY_A", "label": "STOP_LOSS_3", "expectancy": -0.01, "false_exit": 26.14, "saved_failure": 40.44},
    {"policy": "POLICY_B", "label": "STRUCTURE_FAIL", "expectancy": 0.17, "false_exit": 57.68, "saved_failure": 70.61},
    {"policy": "POLICY_H", "label": "RE_OVERSOLD", "expectancy": 0.28, "false_exit": 0.41, "saved_failure": 9.22},
)

FAILURE_CAUSES = (
    {"cause": "STRUCTURE_FAIL", "f1": 72.55, "false_exit": 58.92, "first_trigger_n": 268},
    {"cause": "MONEY_FLOW_DROP", "f1": 71.72, "false_exit": 94.19, "first_trigger_n": 154},
    {"cause": "STOP_LOSS_3", "f1": 70.10, "false_exit": 26.14, "first_trigger_n": 110},
)

OBSERVATION_MODEL = {
    "entry": "Filter_Q (quality>=4) 범용 / Filter_BNB_CORE (BNB) / RULE_C 단독 소폭 개선",
    "survival": "SURVIVED_20 >+2% at +20 bars; structure+mf+energy feature",
    "failure": "STRUCTURE_FAIL(고 recall) + STOP_LOSS_3(저 false exit) 조합 관측",
    "exit": "POLICY_H 수익 보존 / POLICY_A 균형 / POLICY_B 손실 회피",
}

CHAMPION_FRAMEWORK = {
    "entry_filter": "quality_score >= 4 (범용) | BNB + mf>=5 + struct>=5 (BNB)",
    "symbol_filter": "BNBUSDT 우선; SOL·BEAR 회피",
    "regime_filter": "BULL (exp 0.53); BEAR 회피 (exp -1.26)",
    "survival_condition": "return_20 > +2%; RULE_C survival 28.37%",
    "failure_trigger": "STOP_LOSS_3 (F1 70.10%, false exit 26.14%)",
    "exit_policy": "POLICY_H (baseline 수익 보존) 또는 POLICY_A (균형)",
}

LIMITATIONS = (
    "표본: Champion n=59 (LOW tier), 1d TF n=8 (UNSTABLE)",
    "BNB 편중: Champion은 BNB 외 0건",
    "Regime 편중: Champion BEAR 0건, SIDEWAYS n=4",
    "Residual 96.38%: 설명 변수 대부분 미포착",
    "과최적화: BNB+고품질 feature 조합에 성과 집중",
)

FUTURE_WORK = (
    "Out-of-Sample Validation (미래 데이터 홀드아웃)",
    "실시간 Forward Journal 누적 관측",
    "장기 Forward Tracking (+40/+80)",
    "Cross-symbol 확장 (BTC/ETH 조건부 필터)",
    "Regime 전환 시점 동적 필터",
)

VERDICT_CRITERIA = {
    "FAILED": "baseline 음수, robust champion 없음",
    "WEAK": "baseline ~0, 조건부 개선만 존재",
    "CONDITIONAL": "특정 Symbol/Feature/Regime에서만 유효",
    "PROMISING": "robust filter + 다중 split 양(+) consistency",
    "STRONG": "범용 양(+) expectancy, 다심볼·다레짐 재현",
}

FINAL_VERDICT = "CONDITIONAL"
FINAL_VERDICT_RATIONALE = (
    "파동에너지 이론은 baseline +0.27%로 약한 양(+) 신호를 보이나, "
    "유의미한 개선은 BNB + 고품질 feature(mf>=5, struct>=5, quality>=4) + BULL 레짐 + RULE_C/B 조건에서만 확인. "
    "범용 STRONG 판정 불가. Filter_BNB_CORE는 ROBUST(86.98)이나 BNB 전용."
)


def _validation_path(name: str) -> str:
    return os.path.join(VALIDATION_DIR, name)


def _report_exists(name: str) -> bool:
    return os.path.isfile(_validation_path(name))


def _read_report_snippet(name: str, max_lines: int = 5) -> str:
    path = _validation_path(name)
    if not os.path.isfile(path):
        return "—"
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()[:max_lines] if ln.strip()]
    return lines[-1] if lines else "—"


def verify_inputs_unchanged() -> dict:
    """기존 REPORT·CSV 존재 확인 (수정·재계산 없음)."""
    reports = [t["report"] for t in RESEARCH_TIMELINE if t["step"] < 25]
    csvs = (
        "wave_live_forward_journal.csv",
        "wave_entry_filter_refinement.csv",
        "wave_robustness_validation.csv",
        "wave_exit_policy_simulation.csv",
        "wave_failure_trigger_validation.csv",
        "wave_survival_segmentation.csv",
    )
    return {
        "reports_found": sum(1 for r in reports if _report_exists(r)),
        "reports_total": len(reports),
        "csvs_found": sum(1 for c in csvs if _report_exists(c)),
        "csvs_total": len(csvs),
        "all_present": all(_report_exists(r) for r in reports[:20]),
    }


def build_synthesis() -> dict:
    return {
        "timeline": list(RESEARCH_TIMELINE),
        "hypotheses": list(HYPOTHESES),
        "contribution": CONTRIBUTION,
        "champion_rules": list(CHAMPION_RULES),
        "champion_filters": list(CHAMPION_FILTERS),
        "champion_exit": list(CHAMPION_EXIT),
        "failure_causes": list(FAILURE_CAUSES),
        "observation_model": OBSERVATION_MODEL,
        "champion_framework": CHAMPION_FRAMEWORK,
        "limitations": list(LIMITATIONS),
        "future_work": list(FUTURE_WORK),
        "verdict_criteria": VERDICT_CRITERIA,
        "final_verdict": FINAL_VERDICT,
        "final_verdict_rationale": FINAL_VERDICT_RATIONALE,
        "baseline": {"n": 1890, "avg_return_20": 0.27, "expectancy": 0.27, "survival": 25.50, "pf": 1.14},
        "input_check": verify_inputs_unchanged(),
    }


def _fmt(v, pct=False):
    if v is None:
        return "—"
    if pct:
        return f"{v:.2f}%"
    return f"{v:.2f}"


def write_report(synthesis: dict, out_path: Optional[str] = None) -> str:
    path = out_path or _validation_path(REPORT_FINAL)
    bl = synthesis["baseline"]
    lines = [
        "# Wave Final Synthesis — Research Conclusion (#1~#25)",
        "",
        "## Executive Summary",
        "",
        f"- **Final Verdict: {synthesis['final_verdict']}**",
        f"- Baseline (n={bl['n']}): avg_return_20 {_fmt(bl['avg_return_20'], pct=True)}, "
        f"expectancy {_fmt(bl['expectancy'])}, survival {_fmt(bl['survival'], pct=True)}, PF {_fmt(bl['pf'])}",
        f"- Champion Filter (BNB): expectancy 4.09 (delta +3.82), verdict CONDITIONAL",
        f"- Robust Alternative: Filter_BNB_CORE (ROBUST, score 86.98)",
        f"- 범용 필터: Filter_Q quality>=4 (expectancy 0.91, n=750)",
        f"- Exit: baseline 유지(POLICY_H) 또는 손실방어(POLICY_A/B)",
        f"- {synthesis['final_verdict_rationale']}",
        "",
        "## Research Timeline (#1~#25)",
        "",
        "| # | 단계 | 핵심 발견 |",
        "|---:|---|---|",
    ]
    for t in synthesis["timeline"]:
        lines.append(f"| {t['step']} | {t['name']} | {t['finding']} |")

    lines.extend(["", "## Hypothesis Validation", ""])
    lines.append("| 가설 | 판정 | 근거 |")
    lines.append("|---|---|---|")
    for h in synthesis["hypotheses"]:
        lines.append(f"| {h['name']} | **{h['verdict']}** | {h['rationale']} |")

    c = synthesis["contribution"]
    lines.extend(["", "## Contribution Analysis", ""])
    lines.append("| 요인 | SS Contribution |")
    lines.append("|---|---:|")
    lines.append(f"| Rule | {_fmt(c['rule'], pct=True)} |")
    lines.append(f"| Symbol | {_fmt(c['symbol'], pct=True)} |")
    lines.append(f"| Regime | {_fmt(c['regime'], pct=True)} |")
    lines.append(f"| Survival Feature | {_fmt(c['survival_feature'], pct=True)} |")
    lines.append(f"| Residual | {_fmt(c['residual'], pct=True)} |")

    lines.extend(["", "## Champion Rules", ""])
    lines.append("| Rule | expectancy | survival | verdict |")
    lines.append("|---|---:|---:|---|")
    for r in synthesis["champion_rules"]:
        lines.append(
            f"| {r['rule']} | {_fmt(r['expectancy'])} | {_fmt(r['survival_rate'], pct=True)} | {r['verdict']} |"
        )

    lines.extend(["", "## Champion Filters", ""])
    lines.append("| Filter | n | expectancy | PF | survival | verdict |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for f in synthesis["champion_filters"]:
        lines.append(
            f"| {f['label']} | {f['n']} | {_fmt(f['expectancy'])} | "
            f"{_fmt(f['pf']) if f['pf'] else '—'} | {_fmt(f['survival'], pct=True)} | {f['verdict']} |"
        )

    lines.extend(["", "## Champion Exit Policies", ""])
    lines.append("| Policy | expectancy | false_exit | saved_failure |")
    lines.append("|---|---:|---:|---:|")
    for e in synthesis["champion_exit"]:
        lines.append(
            f"| {e['policy']} ({e['label']}) | {_fmt(e['expectancy'])} | "
            f"{_fmt(e['false_exit'], pct=True)} | {_fmt(e['saved_failure'], pct=True)} |"
        )

    lines.extend(["", "## Failure Analysis", ""])
    lines.append("| Cause | F1 | false_exit | first_trigger_n |")
    lines.append("|---|---:|---:|---:|")
    for fc in synthesis["failure_causes"]:
        lines.append(
            f"| {fc['cause']} | {_fmt(fc['f1'], pct=True)} | "
            f"{_fmt(fc['false_exit'], pct=True)} | {fc['first_trigger_n']} |"
        )

    lines.extend(["", "## Final Observation Model", ""])
    om = synthesis["observation_model"]
    for k, v in om.items():
        lines.append(f"- **{k.capitalize()}**: {v}")

    lines.extend(["", "## Final Champion Framework", ""])
    fw = synthesis["champion_framework"]
    for k, v in fw.items():
        lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")

    lines.extend(["", "## Limitations", ""])
    for lim in synthesis["limitations"]:
        lines.append(f"- {lim}")

    lines.extend(["", "## Future Work", ""])
    for fw in synthesis["future_work"]:
        lines.append(f"- {fw}")

    lines.extend(["", "## Final Verdict", ""])
    lines.append(f"### **{synthesis['final_verdict']}**")
    lines.append("")
    lines.append("판정 기준:")
    for k, v in synthesis["verdict_criteria"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append(synthesis["final_verdict_rationale"])
    lines.append("")
    lines.append(f"- Input check: {synthesis['input_check']['reports_found']}/{synthesis['input_check']['reports_total']} reports, "
                 f"{synthesis['input_check']['csvs_found']}/{synthesis['input_check']['csvs_total']} CSVs present")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_png(synthesis: dict, out_path: Optional[str] = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path = out_path or _validation_path(PNG_FINAL)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    steps = [t["step"] for t in synthesis["timeline"] if t["step"] <= 24]
    ax = axes[0, 0]
    ax.plot(steps, steps, "o-", color="#1565C0", markersize=4)
    ax.set_title("Research Flow (#1-#24)")
    ax.set_xlabel("Step")
    ax.set_ylabel("Phase")
    ax.set_xticks([1, 6, 12, 18, 24])

    c = synthesis["contribution"]
    ax = axes[0, 1]
    labels = ["Rule", "Symbol", "Regime", "Surv.Feat", "Residual"]
    vals = [c["rule"], c["symbol"], c["regime"], c["survival_feature"], c["residual"]]
    ax.barh(labels, vals, color=["#2E7D32", "#6A1B9A", "#EF6C00", "#00838F", "#9E9E9E"])
    ax.set_title("Contribution Summary (%)")

    ax = axes[1, 0]
    filters = synthesis["champion_filters"]
    names = [f["id"] for f in filters]
    exps = [f["expectancy"] for f in filters]
    ax.bar(names, exps, color=["#C62828", "#1565C0", "#2E7D32"])
    ax.axhline(synthesis["baseline"]["expectancy"], color="red", linestyle="--", label="baseline")
    ax.set_title("Champion Filter Expectancy")
    ax.legend()

    ax = axes[1, 1]
    verdict = synthesis["final_verdict"]
    colors = {"FAILED": "#C62828", "WEAK": "#EF6C00", "CONDITIONAL": "#F9A825",
              "PROMISING": "#2E7D32", "STRONG": "#1565C0"}
    ax.bar([verdict], [1], color=colors.get(verdict, "#9E9E9E"), width=0.4)
    ax.set_title(f"Final Verdict: {verdict}")
    ax.set_ylim(0, 1.2)
    ax.set_yticks([])

    fig.suptitle("Wave Energy Research — Final Synthesis", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def run_final_synthesis() -> dict:
    synthesis = build_synthesis()
    report_path = write_report(synthesis)
    png_path = write_png(synthesis)
    synthesis["report_path"] = report_path
    synthesis["png_path"] = png_path
    return synthesis
