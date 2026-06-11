"""Wave Regime Gated — RULE_B + Regime Filter 관측 검증.

Generalization/Regime/Confluence 산출물만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
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
from analysis.wave_regime_analysis import (
    _load_pipeline,
    build_event_regimes,
)

BASE_RULE = "RULE_B"
BASE_LABEL = "BASE_RULE"

ATR_THRESHOLDS = (1.0, 1.5, 2.0, 2.5, 3.0)
VOL_THRESHOLDS = (0.5, 1.0, 1.5, 2.0, 3.0)
DIST_THRESHOLDS = (1.5, 2.5, 3.5, 5.0)
MAJOR_K_THRESHOLDS = (40, 50, 60, 70)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


FilterFn = Callable[[pd.Series], bool]


def _gt0(col: str) -> FilterFn:
    def _fn(row: pd.Series) -> bool:
        v = row.get(col)
        return v is not None and not (isinstance(v, float) and np.isnan(v)) and float(v) > 0
    return _fn


def _le(col: str, thr: float) -> FilterFn:
    def _fn(row: pd.Series) -> bool:
        v = row.get(col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return False
        return float(v) <= thr
    return _fn


def _ge(col: str, thr: float) -> FilterFn:
    def _fn(row: pd.Series) -> bool:
        v = row.get(col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return False
        return float(v) >= thr
    return _fn


def build_filter_catalog() -> List[Tuple[str, FilterFn]]:
    """Filter 후보 A~F."""
    catalog: List[Tuple[str, FilterFn]] = [
        ("ema20_slope_3>0", _gt0("ema20_slope_3")),
        ("rsi_slope_1>0", _gt0("rsi_slope_1")),
    ]
    for t in ATR_THRESHOLDS:
        catalog.append((f"atr_pct<={t}", _le("atr_pct", t)))
    for t in VOL_THRESHOLDS:
        catalog.append((f"volatility_20<={t}", _le("volatility_20", t)))
    for t in DIST_THRESHOLDS:
        catalog.append((f"dist_ema60_pct<={t}", _le("dist_ema60_pct", t)))
    for t in MAJOR_K_THRESHOLDS:
        catalog.append((f"major_k>={t}", _ge("major_k", t)))
    return catalog


def build_filter_combos(max_filters: int = 2) -> List[Tuple[str, List[Tuple[str, FilterFn]]]]:
    """BASE + 0~max_filters 조합."""
    catalog = build_filter_catalog()
    combos: List[Tuple[str, List[Tuple[str, FilterFn]]]] = [(BASE_LABEL, [])]
    for n in range(1, max_filters + 1):
        for picks in combinations(catalog, n):
            label = BASE_LABEL + "+" + "+".join(p[0] for p in picks)
            combos.append((label, list(picks)))
    return combos


def apply_filters(df: pd.DataFrame, filters: List[Tuple[str, FilterFn]]) -> pd.DataFrame:
    if df.empty or not filters:
        return df
    mask = pd.Series(True, index=df.index)
    for _, fn in filters:
        mask &= df.apply(fn, axis=1)
    return df[mask]


def _metrics(df: pd.DataFrame) -> dict:
    linked = df.dropna(subset=["return_pct"])
    if linked.empty:
        return {
            "count": len(df),
            "n": 0,
            "win_rate": 0.0,
            "expectancy": None,
            "profit_factor": None,
            "payoff_ratio": None,
            "avg_return": None,
            "avg_survival": None,
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
        "win_rate": m.get("win_rate", 0.0),
        "expectancy": m.get("expectancy"),
        "profit_factor": pf,
        "payoff_ratio": pr,
        "avg_return": m.get("avg_return"),
        "avg_survival": float(surv.mean()) if len(surv) else None,
    }


def compute_robustness_gap(df: pd.DataFrame) -> Optional[float]:
    linked = df.dropna(subset=["return_pct"]).sort_values("timestamp")
    if len(linked) < 4:
        return None
    mid = len(linked) // 2
    a = linked.iloc[:mid]["return_pct"].astype(float)
    b = linked.iloc[mid:]["return_pct"].astype(float)
    if a.empty or b.empty:
        return None
    exp_a = compute_expectancy_metrics(a)["expectancy"]
    exp_b = compute_expectancy_metrics(b)["expectancy"]
    return abs(float(exp_a) - float(exp_b))


def improvement_vs_base(base: dict, gated: dict) -> dict:
    def _delta(a, b):
        if a is None or b is None:
            return None
        return float(b) - float(a)

    return {
        "delta_expectancy": _delta(base.get("expectancy"), gated.get("expectancy")),
        "delta_win_rate": _delta(base.get("win_rate"), gated.get("win_rate")),
        "delta_profit_factor": _delta(base.get("profit_factor"), gated.get("profit_factor")),
        "improvement": _delta(base.get("expectancy"), gated.get("expectancy")),
    }


def collect_base_events() -> pd.DataFrame:
    """전 symbol×tf RULE_B 이벤트 + regime + survival."""
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
                sym, tf, BASE_RULE,
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


def evaluate_gated_rule(
    events: pd.DataFrame,
    filter_label: str,
    filters: List[Tuple[str, FilterFn]],
    base_metrics: dict,
) -> dict:
    gated = apply_filters(events, filters)
    m = _metrics(gated)
    imp = improvement_vs_base(base_metrics, m)
    gap = compute_robustness_gap(gated)
    return {
        "rule": BASE_RULE,
        "filter": filter_label,
        **m,
        "robustness_gap": gap,
        **imp,
    }


def rank_gated_rules(rows: List[dict]) -> List[dict]:
    def _key(r: dict):
        imp = r.get("improvement")
        imp_val = imp if imp is not None else -999.0
        gap = r.get("robustness_gap")
        gap_val = gap if gap is not None else 999.0
        return (imp_val, -gap_val, r.get("n", 0))

    return sorted(rows, key=_key, reverse=True)


def build_regime_gated() -> pd.DataFrame:
    """전체 gated rule 평가."""
    events = collect_base_events()
    if events.empty:
        return pd.DataFrame()

    base_row = evaluate_gated_rule(events, BASE_LABEL, [], _metrics(events))
    base_metrics = {k: base_row[k] for k in (
        "count", "n", "win_rate", "expectancy", "profit_factor",
        "payoff_ratio", "avg_return", "avg_survival",
    )}

    rows = [base_row]
    for label, filters in build_filter_combos(max_filters=2):
        if label == BASE_LABEL:
            continue
        rows.append(evaluate_gated_rule(events, label, filters, base_metrics))

    gated_ranked = rank_gated_rules([r for r in rows if r["filter"] != BASE_LABEL])
    return pd.DataFrame([base_row] + gated_ranked)


def summarize_regime_gated(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    base = df[df["filter"] == BASE_LABEL]
    base_row = base.iloc[0].to_dict() if not base.empty else {}
    gated = df[df["filter"] != BASE_LABEL].copy()

    top_imp = gated.sort_values(
        "improvement", ascending=False, na_position="last",
    )
    top_robust = gated.dropna(subset=["robustness_gap"]).sort_values("robustness_gap")
    worst = gated.sort_values("improvement", ascending=True, na_position="last")

    best_gated_row = top_imp.iloc[0].to_dict() if not top_imp.empty else {}

    base_n = base_row.get("n", 0) or 0

    return {
        "base_rule": base_row,
        "top_improvements": top_imp.head(20).to_dict("records"),
        "top_robust": top_robust.head(20).to_dict("records"),
        "worst_filters": worst.head(20).to_dict("records"),
        "top_gated_rules": df[df["filter"] != BASE_LABEL].head(20).to_dict("records"),
        "delta_exp_top10": top_imp.head(10).to_dict("records"),
        "delta_win_top10": gated.sort_values(
            "delta_win_rate", ascending=False, na_position="last",
        ).head(10).to_dict("records"),
        "best_gated": best_gated_row,
        "base_n": base_n,
    }


def summarize_by_dimension(events: pd.DataFrame, df: pd.DataFrame) -> dict:
    """ETH/BTC/SOL/BNB 및 TF별 BASE vs best filter 비교."""
    if events.empty or df.empty:
        return {"symbol": {}, "timeframe": {}}

    gated = df[df["filter"] != BASE_LABEL]
    best_filter = gated.iloc[0]["filter"] if not gated.empty else BASE_LABEL
    best_filters = []
    for combo_label, combo_filters in build_filter_combos(max_filters=2):
        if combo_label == best_filter:
            best_filters = combo_filters
            break

    def _eval_subset(sub: pd.DataFrame) -> dict:
        base_m = _metrics(sub)
        gated_m = _metrics(apply_filters(sub, best_filters))
        return {
            "base_n": base_m["n"],
            "base_expectancy": base_m.get("expectancy"),
            "gated_n": gated_m["n"],
            "gated_expectancy": gated_m.get("expectancy"),
            "delta_expectancy": (
                None if base_m.get("expectancy") is None or gated_m.get("expectancy") is None
                else float(gated_m["expectancy"]) - float(base_m["expectancy"])
            ),
            "sample_reduction_pct": (
                (1.0 - gated_m["n"] / base_m["n"]) * 100.0
                if base_m["n"] else None
            ),
        }

    sym_cmp = {sym: _eval_subset(events[events["symbol"] == sym]) for sym in GENERALIZATION_SYMBOLS}
    tf_cmp = {tf: _eval_subset(events[events["timeframe"] == tf]) for tf in GENERALIZATION_TIMEFRAMES}
    return {"symbol": sym_cmp, "timeframe": tf_cmp, "best_filter": best_filter}


def full_regime_gated_summary() -> dict:
    events = collect_base_events()
    df = build_regime_gated()
    stats = summarize_regime_gated(df)
    stats["dimension"] = summarize_by_dimension(events, df)
    stats["events"] = events
    stats["dataframe"] = df

    base_n = stats.get("base_rule", {}).get("n", 0)
    for row in stats.get("top_improvements", []):
        n = row.get("n", 0)
        row["sample_reduction_pct"] = (
            (1.0 - n / base_n) * 100.0 if base_n else None
        )
    best = stats.get("best_gated", {})
    if best and base_n:
        best["sample_reduction_pct"] = (
            (1.0 - best.get("n", 0) / base_n) * 100.0
        )
    return stats
