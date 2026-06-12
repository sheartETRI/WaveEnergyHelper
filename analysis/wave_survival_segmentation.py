"""Wave Survival Segmentation — 생존 vs 실패 이벤트 분해.

wave_live_forward_journal.csv + regime + OHLCV만 소비. 엔진 변경 없음.

생존 정의 (+20봉, return_20 기준):
- SURVIVED_20: return_20 > +2.0%
- FAILED_20: return_20 <= 0
- NEUTRAL_20: 0 < return_20 <= +2.0%
- UNKNOWN: return_20 결측 (pending)
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_live_watchlist import WATCH_RULES
from analysis.wave_regime_segmentation import REGIMES, assign_event_regimes
from analysis.wave_symbol_segmentation import load_forward_journal

SURVIVED_THRESHOLD = 2.0
SURVIVAL_LABELS = ("SURVIVED_20", "NEUTRAL_20", "FAILED_20", "UNKNOWN")
SURVIVAL_CURVE_HORIZONS = (5, 10, 20, 40)
CURVE_SURVIVED_THRESHOLD = 2.0
FEATURE_COLS = (
    "money_flow_score", "energy_score", "structure_score",
    "quality_score", "watchlist_score", "bars_elapsed",
)
FAILURE_FOCUS = ("STRUCTURE_FAIL", "MONEY_FLOW_DROP", "STOP_LOSS_3")

CSV_EXPORT_COLS = (
    "section", "event_id", "rule", "symbol", "timeframe", "regime",
    "survival_label", "rank", "n",
    "survival_rate", "failure_rate", "neutral_rate",
    "avg_return_5", "avg_return_10", "avg_return_20", "avg_return_40",
    "mfe_40", "survived_mean", "failed_mean", "delta",
    "horizon", "feature",
    "rule_contribution", "symbol_contribution", "regime_contribution",
    "survival_feature_contribution", "residual",
    "historical_survival_rate", "historical_failure_rate", "survival_rank",
    "watchlist_score", "failure_cause", "avg_bars_elapsed", "cause_pct",
    "value",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def survival_label(return_20: Optional[float]) -> str:
    if return_20 is None or (isinstance(return_20, float) and np.isnan(return_20)):
        return "UNKNOWN"
    r = float(return_20)
    if r > SURVIVED_THRESHOLD:
        return "SURVIVED_20"
    if r <= 0:
        return "FAILED_20"
    return "NEUTRAL_20"


def survival_feature_score(row: pd.Series) -> int:
    """관측용 생존 feature 합 (structure + mf + energy)."""
    return (
        int(row.get("structure_score", 0) or 0)
        + int(row.get("money_flow_score", 0) or 0)
        + int(row.get("energy_score", 0) or 0)
    )


def _avg_col(sub: pd.DataFrame, col: str) -> Optional[float]:
    if col not in sub.columns:
        return None
    vals = sub[col].dropna().astype(float)
    if vals.empty:
        return None
    return round(float(vals.mean()), 4)


def enrich_journal(journal: pd.DataFrame) -> pd.DataFrame:
    if journal.empty:
        return journal
    out = assign_event_regimes(journal)
    out["survival_label"] = out["return_20"].apply(survival_label)
    out["survival_feature"] = out.apply(survival_feature_score, axis=1)
    return out


def event_survival_rows(enriched: pd.DataFrame) -> List[dict]:
    return [
        {
            "section": "event_survival",
            "event_id": row["event_id"],
            "rule": row["rule"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "regime": row.get("regime", ""),
            "survival_label": row["survival_label"],
        }
        for _, row in enriched.iterrows()
    ]


def survival_cohort_analysis(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for label in ("SURVIVED_20", "FAILED_20", "NEUTRAL_20"):
        sub = enriched[enriched["survival_label"] == label]
        if sub.empty:
            continue
        rows.append({
            "section": "survival_cohort",
            "survival_label": label,
            "n": len(sub),
            "avg_return_5": _avg_col(sub, "return_5"),
            "avg_return_10": _avg_col(sub, "return_10"),
            "avg_return_20": _avg_col(sub, "return_20"),
            "avg_return_40": _avg_col(sub, "return_40"),
        })
    return rows


def feature_difference(enriched: pd.DataFrame) -> List[dict]:
    survived = enriched[enriched["survival_label"] == "SURVIVED_20"]
    failed = enriched[enriched["survival_label"] == "FAILED_20"]
    rows = []
    for feat in FEATURE_COLS:
        if feat not in enriched.columns:
            continue
        s_vals = survived[feat].dropna().astype(float)
        f_vals = failed[feat].dropna().astype(float)
        s_mean = float(s_vals.mean()) if len(s_vals) else None
        f_mean = float(f_vals.mean()) if len(f_vals) else None
        delta = round(s_mean - f_mean, 4) if s_mean is not None and f_mean is not None else None
        rows.append({
            "section": "feature_diff",
            "feature": feat,
            "survived_mean": round(s_mean, 4) if s_mean is not None else None,
            "failed_mean": round(f_mean, 4) if f_mean is not None else None,
            "delta": delta,
            "n": len(s_vals) + len(f_vals),
        })
    return rows


def _rates(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"survival_rate": None, "failure_rate": None, "neutral_rate": None, "n": 0}
    labeled = sub[sub["survival_label"] != "UNKNOWN"]
    n = len(labeled)
    if n == 0:
        return {"survival_rate": None, "failure_rate": None, "neutral_rate": None, "n": 0}
    return {
        "n": n,
        "survival_rate": round((labeled["survival_label"] == "SURVIVED_20").sum() / n * 100.0, 2),
        "failure_rate": round((labeled["survival_label"] == "FAILED_20").sum() / n * 100.0, 2),
        "neutral_rate": round((labeled["survival_label"] == "NEUTRAL_20").sum() / n * 100.0, 2),
    }


def rule_survival_analysis(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        sub = enriched[enriched["rule"] == rule]
        r = _rates(sub)
        rows.append({"section": "rule_survival", "rule": rule, **r})
    return rows


def symbol_survival_analysis(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in sorted(enriched["symbol"].unique()):
        sub = enriched[enriched["symbol"] == sym]
        r = _rates(sub)
        rows.append({
            "section": "symbol_survival",
            "symbol": sym,
            **r,
            "avg_return_20": _avg_col(sub, "return_20"),
            "avg_return_40": _avg_col(sub, "return_40"),
        })
    return rows


def regime_survival_analysis(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for regime in REGIMES:
        sub = enriched[enriched["regime"] == regime]
        if sub.empty:
            continue
        r = _rates(sub)
        rows.append({
            "section": "regime_survival",
            "regime": regime,
            **r,
            "avg_return_20": _avg_col(sub, "return_20"),
            "avg_return_40": _avg_col(sub, "return_40"),
        })
    return rows


def failure_cause_survival(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    fail = enriched[enriched["failure_cause"].notna()]
    total = len(fail)
    for cause in FAILURE_FOCUS:
        sub = fail[fail["failure_cause"] == cause]
        if sub.empty:
            continue
        rows.append({
            "section": "failure_cause",
            "failure_cause": cause,
            "n": len(sub),
            "cause_pct": round(len(sub) / total * 100.0, 1) if total else 0.0,
            "avg_return_20": _avg_col(sub, "return_20"),
            "avg_return_40": _avg_col(sub, "return_40"),
            "avg_bars_elapsed": _avg_col(sub, "bars_elapsed"),
        })
    return rows


def survival_curve(enriched: pd.DataFrame) -> List[dict]:
    """Horizon별 return > threshold 비율 (Kaplan-Meier 유사)."""
    rows = []
    for h in SURVIVAL_CURVE_HORIZONS:
        col = f"return_{h}"
        if col not in enriched.columns:
            continue
        vals = enriched[col].dropna().astype(float)
        if vals.empty:
            continue
        survived = (vals > CURVE_SURVIVED_THRESHOLD).sum()
        rows.append({
            "section": "survival_curve",
            "horizon": h,
            "n": len(vals),
            "survival_rate": round(float(survived / len(vals) * 100.0), 2),
        })
    return rows


def champion_survivors(enriched: pd.DataFrame, key: str, top_n: int = 20) -> List[dict]:
    sub = enriched[enriched["survival_label"] == "SURVIVED_20"].copy()
    if sub.empty or key not in sub.columns:
        return []
    sub = sub[sub[key].notna()].sort_values(key, ascending=False).head(top_n)
    rows = []
    for i, (_, row) in enumerate(sub.iterrows(), start=1):
        rows.append({
            "section": f"champion_{key}",
            "rank": i,
            "event_id": row["event_id"],
            "rule": row["rule"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "regime": row.get("regime", ""),
            key: float(row[key]),
            "avg_return_40": float(row["return_40"]) if pd.notna(row.get("return_40")) else None,
            "mfe_40": float(row["mfe_40"]) if pd.notna(row.get("mfe_40")) else None,
        })
    return rows


def four_way_contribution(enriched: pd.DataFrame) -> List[dict]:
    """Rule / Symbol / Regime / Survival Feature SS 분해."""
    sub = enriched[enriched["return_20"].notna()].copy()
    if sub.empty:
        return []
    sub["return_20"] = sub["return_20"].astype(float)
    grand = float(sub["return_20"].mean())
    total_ss = float(((sub["return_20"] - grand) ** 2).sum())
    if total_ss == 0:
        return []

    def _group_ss(col: str) -> float:
        ss = 0.0
        for _, grp in sub.groupby(col):
            ss += len(grp) * (float(grp["return_20"].mean()) - grand) ** 2
        return ss

    rule_ss = _group_ss("rule")
    sym_ss = _group_ss("symbol")
    reg_ss = _group_ss("regime")
    sf_ss = _group_ss("survival_feature")
    residual = max(0.0, total_ss - rule_ss - sym_ss - reg_ss - sf_ss)

    return [
        {"section": "contribution", "rule": "RULE", "rule_contribution": round(rule_ss / total_ss * 100, 2), "n": len(sub)},
        {"section": "contribution", "rule": "SYMBOL", "symbol_contribution": round(sym_ss / total_ss * 100, 2)},
        {"section": "contribution", "rule": "REGIME", "regime_contribution": round(reg_ss / total_ss * 100, 2)},
        {"section": "contribution", "rule": "SURVIVAL_FEATURE", "survival_feature_contribution": round(sf_ss / total_ss * 100, 2)},
        {"section": "contribution", "rule": "RESIDUAL", "residual": round(residual / total_ss * 100, 2)},
    ]


def _hist_rates(enriched: pd.DataFrame, rule: str, symbol: str) -> Tuple[Optional[float], Optional[float]]:
    sub = enriched[(enriched["rule"] == rule) & (enriched["symbol"] == symbol)]
    sub = sub[sub["survival_label"] != "UNKNOWN"]
    if sub.empty:
        return None, None
    n = len(sub)
    surv = (sub["survival_label"] == "SURVIVED_20").sum() / n * 100.0
    fail = (sub["survival_label"] == "FAILED_20").sum() / n * 100.0
    return round(surv, 2), round(fail, 2)


def active_candidate_survival_overlay(enriched: pd.DataFrame) -> List[dict]:
    cands = active_candidate_tracking(enriched)
    rows = []
    for c in cands:
        surv, fail = _hist_rates(enriched, c["rule"], c["symbol"])
        rows.append({
            "section": "active_candidate",
            "symbol": c["symbol"],
            "timeframe": c["timeframe"],
            "rule": c["rule"],
            "watchlist_score": c.get("watchlist_score"),
            "historical_survival_rate": surv,
            "historical_failure_rate": fail,
            "freshness": c.get("freshness"),
            "status": c.get("status"),
        })
    ranked = sorted(
        rows,
        key=lambda r: (
            r.get("historical_survival_rate") if r.get("historical_survival_rate") is not None else -999,
            -(r.get("historical_failure_rate") or 999),
        ),
        reverse=True,
    )
    for i, r in enumerate(ranked, start=1):
        r["survival_rank"] = i
    return ranked


def observation_priority(active: List[dict]) -> List[dict]:
    return [
        {
            "section": "observation_priority",
            "rank": r.get("survival_rank"),
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "rule": r["rule"],
            "historical_survival_rate": r.get("historical_survival_rate"),
            "historical_failure_rate": r.get("historical_failure_rate"),
            "watchlist_score": r.get("watchlist_score"),
        }
        for r in active[:12]
    ]


def build_export(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CSV_EXPORT_COLS))
    df = pd.DataFrame(rows)
    for col in CSV_EXPORT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[[c for c in CSV_EXPORT_COLS if c in df.columns]]


def full_survival_segmentation_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)

    events = event_survival_rows(enriched)
    cohort = survival_cohort_analysis(enriched)
    feat_diff = feature_difference(enriched)
    rule_surv = rule_survival_analysis(enriched)
    sym_surv = symbol_survival_analysis(enriched)
    reg_surv = regime_survival_analysis(enriched)
    fail_cause = failure_cause_survival(enriched)
    curve = survival_curve(enriched)
    champ_ret40 = champion_survivors(enriched, "return_40", 20)
    champ_mfe40 = champion_survivors(enriched, "mfe_40", 20)
    contrib = four_way_contribution(enriched)
    active = active_candidate_survival_overlay(enriched)
    priority = observation_priority(active)

    all_rows = (
        events + cohort + feat_diff + rule_surv + sym_surv + reg_surv
        + fail_cause + curve + champ_ret40 + champ_mfe40 + contrib + active + priority
    )
    return {
        "enriched": enriched,
        "survival_cohort": cohort,
        "feature_diff": feat_diff,
        "rule_survival": rule_surv,
        "symbol_survival": sym_surv,
        "regime_survival": reg_surv,
        "failure_cause": fail_cause,
        "survival_curve": curve,
        "champion_return_40": champ_ret40,
        "champion_mfe_40": champ_mfe40,
        "contribution": contrib,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": build_export(all_rows),
        "survival_definition": (
            f"SURVIVED_20: return_20 > {SURVIVED_THRESHOLD}%; "
            f"FAILED_20: return_20 <= 0%; "
            f"NEUTRAL_20: 0 < return_20 <= {SURVIVED_THRESHOLD}%"
        ),
    }
