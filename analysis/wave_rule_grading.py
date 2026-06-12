"""Wave Rule Grading — BASE_RULE 신뢰도 등급(A/B/C/D) 관측 검증.

Generalization/Regime/Confluence 산출물만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_candidate_rules import enrich_confluence_events
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_generalization import (
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
    load_cell_confluence,
)
from analysis.wave_regime_analysis import _load_pipeline, build_event_regimes
from analysis.wave_regime_gated import (
    BASE_RULE,
    apply_filters,
    compute_robustness_gap,
    _ge,
    _le,
)

BASE_LABEL = "BASE_RULE"
RULE_A = "RULE_A"
ALL_SYMBOL = "ALL"
ALL_TIMEFRAME = "ALL"

GRADE_ORDER = ("A", "B", "C", "D")

FilterFn = Callable[[pd.Series], bool]


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def grade_filter_defs() -> Dict[str, Tuple[str, List[Tuple[str, FilterFn]]]]:
    """Grade별 rule + filter 정의 (실험용, 추가 최적화 없음)."""
    return {
        "A": (BASE_RULE, [("major_k>=70", _ge("major_k", 70))]),
        "B": (BASE_RULE, [("dist_ema60_pct<=3.5", _le("dist_ema60_pct", 3.5))]),
        "C": (BASE_RULE, []),
        "D": (RULE_A, []),
    }


def collect_rule_events(rule: str) -> pd.DataFrame:
    """전 symbol×tf rule 이벤트 + regime + survival."""
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    parts: List[pd.DataFrame] = []

    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            key = (sym, tf)
            if key not in pipeline_cache:
                pipeline_cache[key] = _load_pipeline(sym, tf)
            conf = load_cell_confluence(sym, tf)
            if conf.empty:
                continue
            ev = build_event_regimes(
                sym, tf, rule,
                confluence=conf,
                pipeline=pipeline_cache[key],
            )
            if ev.empty:
                continue
            enriched = enrich_confluence_events(conf, sym, tf)
            if not enriched.empty and "survival_bars" in enriched.columns:
                surv = enriched.set_index("timestamp")["survival_bars"]
                ev = ev.copy()
                ev["survival_bars"] = ev["timestamp"].map(
                    lambda t: surv.get(pd.Timestamp(t), None)
                )
            parts.append(ev)

    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=["return_pct"])


def collect_base_events() -> pd.DataFrame:
    """RULE_B (BASE_RULE) 이벤트."""
    return collect_rule_events(BASE_RULE)


def events_for_grade(grade: str, base_events: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Grade 정의에 맞는 이벤트 subset."""
    defs = grade_filter_defs()
    if grade not in defs:
        return pd.DataFrame()
    rule, filters = defs[grade]
    if rule == BASE_RULE:
        events = base_events if base_events is not None else collect_base_events()
    else:
        events = collect_rule_events(rule)
    if events.empty:
        return events
    return apply_filters(events, filters)


def grade_metrics(df: pd.DataFrame) -> dict:
    """Grade 성과 지표."""
    linked = df.dropna(subset=["return_pct"])
    if linked.empty:
        return {
            "count": len(df),
            "n": 0,
            "win": 0,
            "win_rate": 0.0,
            "expectancy": None,
            "profit_factor": None,
            "payoff_ratio": None,
            "avg_return": None,
            "median_return": None,
            "avg_survival": None,
            "robustness_gap": None,
        }
    rets = linked["return_pct"].astype(float)
    m = compute_expectancy_metrics(rets)
    pf = m.get("profit_factor", 0.0)
    if pf == float("inf"):
        pf = 999.0
    pr = m.get("payoff_ratio", 0.0)
    if pr == float("inf"):
        pr = 999.0
    surv = linked["survival_bars"].dropna() if "survival_bars" in linked.columns else pd.Series(dtype=float)
    return {
        "count": len(df),
        "n": m.get("n", 0),
        "win": m.get("win", 0),
        "win_rate": m.get("win_rate", 0.0),
        "expectancy": m.get("expectancy"),
        "profit_factor": pf,
        "payoff_ratio": pr,
        "avg_return": m.get("avg_return"),
        "median_return": float(rets.median()),
        "avg_survival": float(surv.mean()) if len(surv) else None,
        "robustness_gap": compute_robustness_gap(linked),
    }


def compute_grade_summary(base_events: Optional[pd.DataFrame] = None) -> Dict[str, dict]:
    """Grade A/B/C/D 전체 요약."""
    if base_events is None:
        base_events = collect_base_events()
    return {g: grade_metrics(events_for_grade(g, base_events)) for g in GRADE_ORDER}


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def compute_grade_separation(summary: Dict[str, dict]) -> List[dict]:
    """A vs B, B vs C, C vs D separation."""
    pairs = [("A", "B"), ("B", "C"), ("C", "D")]
    rows = []
    for hi, lo in pairs:
        a = summary.get(hi, {})
        b = summary.get(lo, {})
        rows.append({
            "comparison": f"{hi} vs {lo}",
            "higher": hi,
            "lower": lo,
            "delta_expectancy": _delta(a.get("expectancy"), b.get("expectancy")),
            "delta_win_rate": _delta(a.get("win_rate"), b.get("win_rate")),
            "delta_profit_factor": _delta(a.get("profit_factor"), b.get("profit_factor")),
        })
    return rows


def check_monotonicity(summary: Dict[str, dict]) -> dict:
    """A > B > C > D monotonicity (win_rate, expectancy, PF)."""
    metrics = ("win_rate", "expectancy", "profit_factor")
    details = {}
    all_pass = True
    for metric in metrics:
        vals = [summary.get(g, {}).get(metric) for g in GRADE_ORDER]
        ok = all(
            vals[i] is not None and vals[i + 1] is not None and float(vals[i]) > float(vals[i + 1])
            for i in range(len(vals) - 1)
        )
        details[metric] = {
            "values": {g: summary.get(g, {}).get(metric) for g in GRADE_ORDER},
            "pass": ok,
        }
        if not ok:
            all_pass = False
    return {
        "pass": all_pass,
        "result": "PASS" if all_pass else "FAIL",
        "details": details,
    }


def compute_calibration(summary: Dict[str, dict]) -> List[dict]:
    """Grade별 실제 성공률 (win_rate)."""
    return [
        {"grade": g, "actual_win": summary[g].get("win_rate")}
        for g in GRADE_ORDER
        if g in summary
    ]


def compute_stability(
    base_events: Optional[pd.DataFrame] = None,
) -> Dict[str, dict]:
    """전반부/후반부 expectancy 및 robustness_gap."""
    if base_events is None:
        base_events = collect_base_events()
    out = {}
    for g in GRADE_ORDER:
        ev = events_for_grade(g, base_events)
        linked = ev.dropna(subset=["return_pct"]).sort_values("timestamp")
        if len(linked) < 4:
            out[g] = {
                "first_half_expectancy": None,
                "second_half_expectancy": None,
                "robustness_gap": None,
            }
            continue
        mid = len(linked) // 2
        a = linked.iloc[:mid]["return_pct"].astype(float)
        b = linked.iloc[mid:]["return_pct"].astype(float)
        exp_a = compute_expectancy_metrics(a)["expectancy"]
        exp_b = compute_expectancy_metrics(b)["expectancy"]
        out[g] = {
            "first_half_expectancy": exp_a,
            "second_half_expectancy": exp_b,
            "robustness_gap": abs(float(exp_a) - float(exp_b)) if exp_a is not None and exp_b is not None else None,
        }
    return out


def compute_cross_market(base_events: Optional[pd.DataFrame] = None) -> List[dict]:
    """심볼별 Grade expectancy."""
    if base_events is None:
        base_events = collect_base_events()
    rows = []
    for g in GRADE_ORDER:
        ev = events_for_grade(g, base_events)
        for sym in GENERALIZATION_SYMBOLS:
            sub = ev[ev["symbol"] == sym] if not ev.empty else pd.DataFrame()
            m = grade_metrics(sub)
            rows.append({
                "grade": g,
                "symbol": sym,
                "expectancy": m.get("expectancy"),
                "n": m.get("n", 0),
            })
    return rows


def build_grading_rows(base_events: Optional[pd.DataFrame] = None) -> List[dict]:
    """CSV용 행: ALL + symbol×timeframe."""
    if base_events is None:
        base_events = collect_base_events()
    rows: List[dict] = []

    for g in GRADE_ORDER:
        ev = events_for_grade(g, base_events)
        m = grade_metrics(ev)
        rows.append({
            "grade": g,
            "symbol": ALL_SYMBOL,
            "timeframe": ALL_TIMEFRAME,
            "count": m["count"],
            "win_rate": m["win_rate"],
            "expectancy": m["expectancy"],
            "profit_factor": m["profit_factor"],
            "avg_return": m["avg_return"],
            "avg_survival": m["avg_survival"],
            "robustness_gap": m["robustness_gap"],
        })

        for sym in GENERALIZATION_SYMBOLS:
            for tf in GENERALIZATION_TIMEFRAMES:
                sub = ev[(ev["symbol"] == sym) & (ev["timeframe"] == tf)] if not ev.empty else pd.DataFrame()
                cm = grade_metrics(sub)
                rows.append({
                    "grade": g,
                    "symbol": sym,
                    "timeframe": tf,
                    "count": cm["count"],
                    "win_rate": cm["win_rate"],
                    "expectancy": cm["expectancy"],
                    "profit_factor": cm["profit_factor"],
                    "avg_return": cm["avg_return"],
                    "avg_survival": cm["avg_survival"],
                    "robustness_gap": cm["robustness_gap"],
                })

    return rows


def build_grading_dataframe(base_events: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    rows = build_grading_rows(base_events)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def recommend_grade(summary: Dict[str, dict], monotonicity: dict) -> str:
    """데이터 기반 추천 등급 (관측용)."""
    if monotonicity.get("pass"):
        for g in GRADE_ORDER:
            n = summary.get(g, {}).get("n", 0)
            if n >= 10:
                return g
        return "C"
    best = max(
        GRADE_ORDER,
        key=lambda g: summary.get(g, {}).get("expectancy") or -999.0,
    )
    return best


def full_rule_grading_summary() -> dict:
    """전체 grading 분석 payload."""
    base_events = collect_base_events()
    summary = compute_grade_summary(base_events)
    separation = compute_grade_separation(summary)
    monotonicity = check_monotonicity(summary)
    calibration = compute_calibration(summary)
    stability = compute_stability(base_events)
    cross_market = compute_cross_market(base_events)
    dataframe = build_grading_dataframe(base_events)

    return {
        "summary": summary,
        "separation": separation,
        "monotonicity": monotonicity,
        "calibration": calibration,
        "stability": stability,
        "cross_market": cross_market,
        "recommended_grade": recommend_grade(summary, monotonicity),
        "base_events": base_events,
        "dataframe": dataframe,
    }
