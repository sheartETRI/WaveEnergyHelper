"""Wave Forward Observation — 실시간 Forward 관측 운영 모드 (#27).

기존 journal·watchlist·REPORT만 소비. 엔진·기존 산출물 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_survival_segmentation import SURVIVED_THRESHOLD, enrich_journal, survival_label
from analysis.wave_symbol_segmentation import load_forward_journal

ROLLING_WINDOWS = (30, 60, 90)
SURVIVAL_THRESHOLD = SURVIVED_THRESHOLD

RESEARCH_BASELINE = {
    "TIER_1": {"filter": "Filter_BNB_CORE", "expectancy": 3.02, "survival_rate": 41.31},
    "TIER_2": {"filter": "quality>=4", "expectancy": 0.91, "survival_rate": 27.60},
    "TIER_3": {"filter": "RULE_C", "expectancy": 0.40, "survival_rate": 28.37},
}

CSV_EXPORT_COLS = (
    "section", "event_id", "timestamp", "symbol", "timeframe", "rule", "regime",
    "money_flow_score", "structure_score", "energy_score", "quality_score",
    "filter_match", "observation_tier", "forward_status", "freshness",
    "return_5", "return_10", "return_20", "return_40",
    "n", "win_rate", "avg_return", "survival_rate", "failure_rate",
    "expectancy", "profit_factor", "month", "window_days",
    "drift_metric", "drift_value", "baseline_value", "drift_pct", "drift_flag",
    "alert_type", "alert_message", "rank", "priority_rank", "value",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def match_filter_bnb_core(row: pd.Series) -> bool:
    return (
        str(row.get("symbol")) == "BNBUSDT"
        and int(row.get("money_flow_score", 0) or 0) >= 5
        and int(row.get("structure_score", 0) or 0) >= 5
    )


def match_quality_tier(row: pd.Series) -> bool:
    return int(row.get("quality_score", 0) or 0) >= 4


def match_rule_c_tier(row: pd.Series) -> bool:
    return str(row.get("rule")) == "RULE_C"


def classify_observation_tier(row: pd.Series) -> Tuple[Optional[str], Optional[str]]:
    if match_filter_bnb_core(row):
        return "TIER_1", "Filter_BNB_CORE"
    if match_quality_tier(row):
        return "TIER_2", "quality>=4"
    if match_rule_c_tier(row):
        return "TIER_3", "RULE_C"
    return None, None


def forward_status(row: pd.Series) -> str:
    bars = int(row.get("bars_elapsed", 0) or 0)
    if bars >= 40:
        return "+40_COMPLETE"
    if bars >= 20:
        return "+20_COMPLETE"
    if bars >= 10:
        return "+10_COMPLETE"
    if bars >= 5:
        return "+5_COMPLETE"
    return "PENDING"


def _tier_perf(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0}
    rets = sub["return_20"].dropna().astype(float) if "return_20" in sub.columns else pd.Series(dtype=float)
    m = compute_expectancy_metrics(rets) if not rets.empty else {"n": 0}
    labeled = sub[sub["survival_label"].isin(["SURVIVED_20", "FAILED_20", "NEUTRAL_20"])] if "survival_label" in sub.columns else sub
    n_lab = len(labeled)
    surv = (labeled["survival_label"] == "SURVIVED_20").sum() / n_lab * 100 if n_lab else None
    fail = (labeled["survival_label"] == "FAILED_20").sum() / n_lab * 100 if n_lab else None
    pf = m.get("profit_factor", 0)
    return {
        "n": len(sub),
        "win_rate": round(m.get("win_rate", 0), 2) if rets.size else None,
        "avg_return": round(float(rets.mean()), 4) if not rets.empty else None,
        "expectancy": round(m.get("expectancy", 0), 4) if rets.size else None,
        "profit_factor": round(pf, 4) if pf not in (float("inf"),) else 999.0,
        "survival_rate": round(surv, 2) if surv is not None else None,
        "failure_rate": round(fail, 2) if fail is not None else None,
    }


def build_observation_journal(enriched: pd.DataFrame) -> pd.DataFrame:
    """Tier 1/2/3 매칭 이벤트만 추출."""
    if enriched.empty:
        return pd.DataFrame()

    rows = []
    for _, row in enriched.iterrows():
        tier, fmatch = classify_observation_tier(row)
        if not tier:
            continue
        rows.append({
            "section": "observation_event",
            "event_id": row.get("event_id"),
            "timestamp": row.get("timestamp"),
            "symbol": row.get("symbol"),
            "timeframe": row.get("timeframe"),
            "rule": row.get("rule"),
            "regime": row.get("regime", ""),
            "money_flow_score": row.get("money_flow_score"),
            "structure_score": row.get("structure_score"),
            "energy_score": row.get("energy_score"),
            "quality_score": row.get("quality_score"),
            "filter_match": fmatch,
            "observation_tier": tier,
            "forward_status": forward_status(row),
            "freshness": row.get("freshness"),
            "return_5": row.get("return_5"),
            "return_10": row.get("return_10"),
            "return_20": row.get("return_20"),
            "return_40": row.get("return_40"),
            "survival_label": row.get("survival_label"),
            "bars_elapsed": row.get("bars_elapsed"),
            "status": row.get("status"),
        })
    return pd.DataFrame(rows)


def tier_dashboard(obs: pd.DataFrame) -> List[dict]:
    rows = []
    for tier in ("TIER_1", "TIER_2", "TIER_3"):
        sub = obs[obs["observation_tier"] == tier]
        p = _tier_perf(sub)
        base = RESEARCH_BASELINE.get(tier, {})
        rows.append({
            "section": "tier_dashboard",
            "observation_tier": tier,
            "filter_match": base.get("filter"),
            **p,
            "baseline_expectancy": base.get("expectancy"),
            "baseline_survival_rate": base.get("survival_rate"),
        })
    return rows


def candidate_queue(enriched: pd.DataFrame) -> List[dict]:
    if "freshness" not in enriched.columns:
        return []
    cands = active_candidate_tracking(enriched)
    rows = []
    for c in cands:
        sub = enriched[
            (enriched["symbol"] == c["symbol"])
            & (enriched["timeframe"] == c["timeframe"])
            & (enriched["rule"] == c["rule"])
        ].sort_values("timestamp")
        if sub.empty:
            continue
        ev = sub.iloc[-1]
        tier, fmatch = classify_observation_tier(ev)
        if not tier:
            continue
        rows.append({
            "section": "candidate_queue",
            "event_id": ev.get("event_id"),
            "symbol": c["symbol"],
            "timeframe": c["timeframe"],
            "rule": c["rule"],
            "freshness": c.get("freshness"),
            "observation_tier": tier,
            "filter_match": fmatch,
            "forward_status": forward_status(ev),
            "money_flow_score": ev.get("money_flow_score"),
            "structure_score": ev.get("structure_score"),
            "quality_score": ev.get("quality_score"),
            "watchlist_score": c.get("watchlist_score"),
        })
    ranked = sorted(rows, key=lambda r: (r["observation_tier"], -(r.get("watchlist_score") or 0)))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def monthly_summary(obs: pd.DataFrame) -> List[dict]:
    if obs.empty or "timestamp" not in obs.columns:
        return []
    df = obs.copy()
    df["_ts"] = pd.to_datetime(df["timestamp"])
    df["_month"] = df["_ts"].dt.to_period("M").astype(str)
    rows = []
    for month in sorted(df["_month"].unique()):
        sub = df[df["_month"] == month]
        completed = sub[sub["forward_status"].isin(("+20_COMPLETE", "+40_COMPLETE"))]
        survived = completed[completed["survival_label"] == "SURVIVED_20"] if "survival_label" in completed.columns else pd.DataFrame()
        failed = completed[completed["survival_label"] == "FAILED_20"] if "survival_label" in completed.columns else pd.DataFrame()
        rows.append({
            "section": "monthly_summary",
            "month": month,
            "n": len(sub),
            "completed_20": len(completed),
            "survived_n": len(survived),
            "failed_n": len(failed),
            "survival_rate": round(len(survived) / len(completed) * 100, 2) if len(completed) else None,
            "avg_return_20": round(float(completed["return_20"].mean()), 4) if len(completed) and "return_20" in completed.columns else None,
        })
    return rows


def rolling_performance(obs: pd.DataFrame) -> List[dict]:
    if obs.empty or "timestamp" not in obs.columns:
        return []
    ts = pd.to_datetime(obs["timestamp"])
    max_ts = ts.max()
    rows = []
    for days in ROLLING_WINDOWS:
        cutoff = max_ts - pd.Timedelta(days=days)
        sub = obs[ts >= cutoff]
        for tier in ("TIER_1", "TIER_2", "TIER_3"):
            tsub = sub[sub["observation_tier"] == tier]
            p = _tier_perf(tsub)
            rows.append({
                "section": "rolling_performance",
                "window_days": days,
                "observation_tier": tier,
                **p,
            })
    return rows


def drift_detection(obs: pd.DataFrame, rolling: List[dict]) -> List[dict]:
    rows = []
    for tier in ("TIER_1", "TIER_2", "TIER_3"):
        base = RESEARCH_BASELINE[tier]
        tier_obs = obs[obs["observation_tier"] == tier] if not obs.empty else pd.DataFrame()
        live = _tier_perf(tier_obs)
        roll90 = next((r for r in rolling if r.get("window_days") == 90 and r.get("observation_tier") == tier), {})

        for metric, baseline_val in (("expectancy", base["expectancy"]), ("survival_rate", base["survival_rate"])):
            live_val = live.get(metric)
            roll_val = roll90.get(metric)
            check_val = roll_val if roll_val is not None else live_val
            if check_val is None or baseline_val is None:
                continue
            drift_pct = round((check_val - baseline_val) / abs(baseline_val) * 100, 2) if baseline_val else None
            flag = "STABLE"
            if drift_pct is not None:
                if metric == "expectancy" and drift_pct < -25:
                    flag = "DRIFT_DOWN"
                elif metric == "survival_rate" and drift_pct < -20:
                    flag = "DRIFT_DOWN"
                elif drift_pct > 25:
                    flag = "DRIFT_UP"
            rows.append({
                "section": "drift_detection",
                "observation_tier": tier,
                "filter_match": base["filter"],
                "drift_metric": metric,
                "drift_value": check_val,
                "baseline_value": baseline_val,
                "drift_pct": drift_pct,
                "drift_flag": flag,
            })

        failed = tier_obs[tier_obs["survival_label"] == "FAILED_20"] if not tier_obs.empty and "survival_label" in tier_obs.columns else pd.DataFrame()
        fail_rate = len(failed) / len(tier_obs) * 100 if len(tier_obs) else None
        if fail_rate is not None:
            rows.append({
                "section": "drift_detection",
                "observation_tier": tier,
                "filter_match": base["filter"],
                "drift_metric": "failure_rate",
                "drift_value": round(fail_rate, 2),
                "baseline_value": round(100 - base["survival_rate"], 2),
                "drift_pct": None,
                "drift_flag": "STABLE" if fail_rate < 60 else "DRIFT_UP",
            })
    return rows


def alert_layer(obs: pd.DataFrame, candidates: List[dict]) -> List[dict]:
    rows = []
    if not obs.empty and "timestamp" in obs.columns:
        ts = pd.to_datetime(obs["timestamp"])
        recent = obs[ts >= ts.max() - pd.Timedelta(days=7)]
        for tier, label, atype in (
            ("TIER_1", "Filter_BNB_CORE", "BNB_CORE_SIGNAL"),
            ("TIER_2", "quality>=4", "QUALITY_SIGNAL"),
            ("TIER_3", "RULE_C", "RULE_C_SIGNAL"),
        ):
            sub = recent[recent["observation_tier"] == tier]
            if not sub.empty:
                rows.append({
                    "section": "alert",
                    "alert_type": atype,
                    "observation_tier": tier,
                    "filter_match": label,
                    "n": len(sub),
                    "alert_message": f"{len(sub)} events in last 7d ({label})",
                })

    for c in candidates[:5]:
        if c.get("freshness") == "ACTIVE":
            rows.append({
                "section": "alert",
                "alert_type": "ACTIVE_CANDIDATE",
                "observation_tier": c.get("observation_tier"),
                "filter_match": c.get("filter_match"),
                "alert_message": f"ACTIVE {c['symbol']} {c['timeframe']} {c['rule']} ({c.get('filter_match')})",
                "symbol": c.get("symbol"),
                "timeframe": c.get("timeframe"),
                "rule": c.get("rule"),
            })
    return rows


def observation_priority(candidates: List[dict], drift: List[dict]) -> List[dict]:
    drift_map = {d["observation_tier"]: d.get("drift_flag") for d in drift if d.get("drift_metric") == "expectancy"}
    rows = []
    for c in candidates[:15]:
        tier = c.get("observation_tier")
        rows.append({
            "section": "observation_priority",
            "priority_rank": c.get("rank"),
            "symbol": c.get("symbol"),
            "timeframe": c.get("timeframe"),
            "rule": c.get("rule"),
            "observation_tier": tier,
            "filter_match": c.get("filter_match"),
            "forward_status": c.get("forward_status"),
            "drift_flag": drift_map.get(tier),
        })
    return rows


def maintenance_verdict(drift: List[dict], tier_rows: List[dict]) -> dict:
    """실시간 유지 여부 종합."""
    flags = [d.get("drift_flag") for d in drift if d.get("drift_metric") == "expectancy"]
    down = sum(1 for f in flags if f == "DRIFT_DOWN")
    t1 = next((t for t in tier_rows if t.get("observation_tier") == "TIER_1"), {})
    t1_n = t1.get("n", 0)
    if down >= 2:
        verdict = "NOT_MAINTAINED"
    elif down == 1:
        verdict = "PARTIAL"
    elif t1_n >= 5 and t1.get("expectancy") is not None and t1["expectancy"] >= 1.0:
        verdict = "MAINTAINED"
    else:
        verdict = "MONITORING"
    return {"verdict": verdict, "drift_down_count": down, "tier1_n": t1_n}


def build_export(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CSV_EXPORT_COLS))
    df = pd.DataFrame(rows)
    for col in CSV_EXPORT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[[c for c in CSV_EXPORT_COLS if c in df.columns]]


def full_forward_observation_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)
    obs = build_observation_journal(enriched)

    tier_rows = tier_dashboard(obs)
    cands = candidate_queue(enriched)
    monthly = monthly_summary(obs)
    rolling = rolling_performance(obs)
    drift = drift_detection(obs, rolling)
    alerts = alert_layer(obs, cands)
    priority = observation_priority(cands, drift)
    maintenance = maintenance_verdict(drift, tier_rows)

    summary_row = {
        "section": "observation_summary",
        "n": len(obs),
        "tier1_n": len(obs[obs["observation_tier"] == "TIER_1"]) if not obs.empty else 0,
        "tier2_n": len(obs[obs["observation_tier"] == "TIER_2"]) if not obs.empty else 0,
        "tier3_n": len(obs[obs["observation_tier"] == "TIER_3"]) if not obs.empty else 0,
        "active_candidates": len(cands),
        "maintenance_verdict": maintenance["verdict"],
    }

    event_rows = obs.to_dict("records") if not obs.empty else []
    all_rows = event_rows + tier_rows + cands + monthly + rolling + drift + alerts + priority + [summary_row, {
        "section": "maintenance_verdict",
        **maintenance,
    }]

    return {
        "observation_journal": obs,
        "tier_dashboard": tier_rows,
        "candidate_queue": cands,
        "monthly_summary": monthly,
        "rolling_performance": rolling,
        "drift_detection": drift,
        "alerts": alerts,
        "observation_priority": priority,
        "maintenance": maintenance,
        "export_df": build_export(all_rows),
    }
