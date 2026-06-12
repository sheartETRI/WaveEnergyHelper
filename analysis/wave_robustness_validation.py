"""Wave Robustness Validation — Champion Filter 견고성 검증 (관측 전용).

wave_live_forward_journal.csv만 소비. 엔진·기존 산출물 변경 없음.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd

from analysis.wave_entry_filter_refinement import _apply_mask, _perf
from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_regime_segmentation import REGIMES
from analysis.wave_survival_segmentation import enrich_journal
from analysis.wave_symbol_segmentation import load_forward_journal

TIMEFRAMES = ("1h", "4h", "1d")
SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
TEMPORAL_SPLITS = ("first_half", "second_half", "recent_180d", "recent_90d", "recent_30d")
LOO_CONDITIONS = (
    "remove_1h", "remove_4h", "remove_1d",
    "remove_BULL", "remove_SIDEWAYS", "remove_BEAR",
    "remove_recent_30d", "remove_recent_90d",
)
ALTERNATIVE_FILTERS = (
    "Filter_Q", "Filter_C", "Filter_BNB", "Filter_STRUCT", "Filter_MF",
    "Filter_BNB_STRUCT", "Filter_BNB_MF", "Filter_BNB_CORE",
)

FILTER_DEFS: Dict[str, dict] = {
    "CHAMPION": {
        "rule": "RULE_A", "symbol": "BNBUSDT",
        "feats": {"money_flow_score": 5, "structure_score": 5},
        "label": "RULE_A+BNB+mf>=5+struct>=5",
    },
    "Filter_Q": {"rule": "ALL", "symbol": "ALL", "feats": {"quality_score": 4}, "label": "quality>=4"},
    "Filter_C": {"rule": "RULE_C", "symbol": "ALL", "feats": {}, "label": "RULE_C"},
    "Filter_BNB": {"rule": "ALL", "symbol": "BNBUSDT", "feats": {}, "label": "BNB"},
    "Filter_STRUCT": {"rule": "ALL", "symbol": "ALL", "feats": {"structure_score": 5}, "label": "struct>=5"},
    "Filter_MF": {"rule": "ALL", "symbol": "ALL", "feats": {"money_flow_score": 5}, "label": "mf>=5"},
    "Filter_BNB_CORE": {
        "rule": "ALL", "symbol": "BNBUSDT",
        "feats": {"money_flow_score": 5, "structure_score": 5},
        "label": "BNB+mf>=5+struct>=5",
    },
    "Filter_BNB_STRUCT": {
        "rule": "ALL", "symbol": "BNBUSDT",
        "feats": {"structure_score": 5}, "label": "BNB+struct>=5",
    },
    "Filter_BNB_MF": {
        "rule": "ALL", "symbol": "BNBUSDT",
        "feats": {"money_flow_score": 5}, "label": "BNB+mf>=5",
    },
}

CSV_EXPORT_COLS = (
    "section", "filter_id", "filter_name", "split", "timeframe", "symbol", "regime",
    "loo_condition", "n", "avg_return_20", "expectancy", "survival_rate", "profit_factor",
    "sample_tier", "expectancy_score", "survival_score", "profit_factor_score",
    "sample_score", "split_consistency_score", "regime_consistency_score",
    "tf_consistency_score", "robustness_score", "overfit_risk", "verdict",
    "rank", "event_id", "rule", "freshness",
    "robust_filter_match", "priority_rank", "value",
)


def _apply_filter(df: pd.DataFrame, fname: str) -> pd.DataFrame:
    f = FILTER_DEFS[fname]
    return _apply_mask(df, f["rule"], f["symbol"], "ALL", f["feats"])


def _sample_tier(n: int) -> str:
    if n >= 100:
        return "HIGH"
    if n >= 50:
        return "MEDIUM"
    if n >= 20:
        return "LOW"
    return "UNSTABLE"


def _temporal_subset(df: pd.DataFrame, split: str) -> pd.DataFrame:
    if df.empty or "timestamp" not in df.columns:
        return df
    ts = pd.to_datetime(df["timestamp"])
    sorted_df = df.assign(_ts=ts).sort_values("_ts")
    if split == "first_half":
        mid = len(sorted_df) // 2
        return sorted_df.iloc[:mid].drop(columns="_ts")
    if split == "second_half":
        mid = len(sorted_df) // 2
        return sorted_df.iloc[mid:].drop(columns="_ts")
    max_ts = ts.max()
    days = {"recent_180d": 180, "recent_90d": 90, "recent_30d": 30}.get(split)
    if days:
        cutoff = max_ts - pd.Timedelta(days=days)
        return sorted_df[sorted_df["_ts"] >= cutoff].drop(columns="_ts")
    return sorted_df.drop(columns="_ts")


def _loo_subset(df: pd.DataFrame, condition: str) -> pd.DataFrame:
    if df.empty:
        return df
    ts = pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else None
    if condition == "remove_1h":
        return df[df["timeframe"] != "1h"]
    if condition == "remove_4h":
        return df[df["timeframe"] != "4h"]
    if condition == "remove_1d":
        return df[df["timeframe"] != "1d"]
    if condition == "remove_BULL":
        return df[df["regime"] != "BULL"]
    if condition == "remove_SIDEWAYS":
        return df[df["regime"] != "SIDEWAYS"]
    if condition == "remove_BEAR":
        return df[df["regime"] != "BEAR"]
    if ts is not None and condition == "remove_recent_30d":
        cutoff = ts.max() - pd.Timedelta(days=30)
        return df[ts < cutoff]
    if ts is not None and condition == "remove_recent_90d":
        cutoff = ts.max() - pd.Timedelta(days=90)
        return df[ts < cutoff]
    return df


def temporal_split_validation(df: pd.DataFrame, filters: Tuple[str, ...]) -> List[dict]:
    rows = []
    for fname in filters:
        base = _apply_filter(df, fname)
        for split in TEMPORAL_SPLITS:
            sub = _temporal_subset(base, split)
            p = _perf(sub)
            rows.append({
                "section": "temporal_split",
                "filter_id": fname,
                "filter_name": FILTER_DEFS[fname]["label"],
                "split": split,
                **p,
                "sample_tier": _sample_tier(p.get("n", 0)),
            })
    return rows


def timeframe_robustness(df: pd.DataFrame, filters: Tuple[str, ...]) -> List[dict]:
    rows = []
    for fname in filters:
        base = _apply_filter(df, fname)
        for tf in TIMEFRAMES:
            sub = base[base["timeframe"] == tf]
            p = _perf(sub)
            rows.append({
                "section": "timeframe_robustness",
                "filter_id": fname,
                "filter_name": FILTER_DEFS[fname]["label"],
                "timeframe": tf,
                **p,
                "sample_tier": _sample_tier(p.get("n", 0)),
            })
    return rows


def symbol_robustness(df: pd.DataFrame, filters: Tuple[str, ...]) -> List[dict]:
    rows = []
    for fname in filters:
        base = _apply_filter(df, fname)
        for sym in SYMBOLS:
            sub = base[base["symbol"] == sym]
            p = _perf(sub)
            rows.append({
                "section": "symbol_robustness",
                "filter_id": fname,
                "filter_name": FILTER_DEFS[fname]["label"],
                "symbol": sym,
                **p,
            })

        p_all = _perf(base)
        rows.append({
            "section": "symbol_robustness",
            "filter_id": fname,
            "filter_name": FILTER_DEFS[fname]["label"],
            "symbol": "BNB_only" if fname in ("CHAMPION", "Filter_BNB_CORE", "Filter_BNB") else "with_BNB",
            **p_all,
        })

        non_bnb = df[df["symbol"] != "BNBUSDT"]
        fdef = FILTER_DEFS[fname]
        sub_no = _apply_mask(non_bnb, fdef["rule"], "ALL", "ALL", fdef["feats"])
        p_no = _perf(sub_no)
        rows.append({
            "section": "symbol_robustness",
            "filter_id": fname,
            "filter_name": FILTER_DEFS[fname]["label"],
            "symbol": "without_BNB",
            **p_no,
        })
    return rows


def regime_robustness(df: pd.DataFrame, filters: Tuple[str, ...]) -> List[dict]:
    rows = []
    for fname in filters:
        base = _apply_filter(df, fname)
        for regime in REGIMES:
            sub = base[base["regime"] == regime]
            p = _perf(sub)
            rows.append({
                "section": "regime_robustness",
                "filter_id": fname,
                "filter_name": FILTER_DEFS[fname]["label"],
                "regime": regime,
                **p,
                "sample_tier": _sample_tier(p.get("n", 0)),
            })
    return rows


def leave_one_out_validation(df: pd.DataFrame, filters: Tuple[str, ...]) -> List[dict]:
    rows = []
    for fname in filters:
        base = _apply_filter(df, fname)
        full = _perf(base)
        for cond in LOO_CONDITIONS:
            sub = _loo_subset(base, cond)
            p = _perf(sub)
            delta = round((p.get("expectancy") or 0) - (full.get("expectancy") or 0), 4)
            rows.append({
                "section": "leave_one_out",
                "filter_id": fname,
                "filter_name": FILTER_DEFS[fname]["label"],
                "loo_condition": cond,
                **p,
                "expectancy_delta": delta,
            })
    return rows


def minimum_sample_check(rows: List[dict]) -> List[dict]:
    out = []
    for r in rows:
        if r.get("section") not in (
            "temporal_split", "timeframe_robustness", "regime_robustness",
        ):
            continue
        out.append({
            "section": "minimum_sample",
            "filter_id": r.get("filter_id"),
            "filter_name": r.get("filter_name"),
            "split": r.get("split"),
            "timeframe": r.get("timeframe"),
            "regime": r.get("regime"),
            "n": r.get("n"),
            "sample_tier": _sample_tier(r.get("n", 0)),
            "expectancy": r.get("expectancy"),
        })
    return out


def _consistency_score(parts: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in parts if v is not None]
    if not vals:
        return None
    pos = sum(1 for v in vals if v > 0)
    return round(pos / len(vals) * 100, 2)


def _compute_robustness_components(
    fname: str,
    temporal: List[dict],
    tf_rows: List[dict],
    regime_rows: List[dict],
    full_perf: dict,
) -> dict:
    t_sub = [r for r in temporal if r.get("filter_id") == fname]
    tf_sub = [r for r in tf_rows if r.get("filter_id") == fname]
    reg_sub = [r for r in regime_rows if r.get("filter_id") == fname]

    exp = full_perf.get("expectancy") or 0
    surv = full_perf.get("survival_rate") or 0
    pf = full_perf.get("profit_factor") or 0
    if pf == 999.0:
        pf = 5.0
    n = full_perf.get("n") or 0

    exp_score = round(min(max(exp / 2.0, 0), 1) * 100, 2)
    surv_score = round(min(surv, 100), 2)
    pf_score = round(min(pf / 3.0, 1) * 100, 2)
    sample_score = round(min(n / 100, 1) * 100, 2)

    split_cons = _consistency_score([r.get("expectancy") for r in t_sub if (r.get("n") or 0) >= 5])
    tf_cons = _consistency_score([r.get("expectancy") for r in tf_sub if (r.get("n") or 0) >= 5])
    reg_cons = _consistency_score([r.get("expectancy") for r in reg_sub if (r.get("n") or 0) >= 5])

    robustness = round(
        exp_score * 0.2 + surv_score * 0.15 + pf_score * 0.15 + sample_score * 0.15
        + (split_cons or 0) * 0.15 + (reg_cons or 0) * 0.1 + (tf_cons or 0) * 0.1,
        2,
    )

    return {
        "expectancy_score": exp_score,
        "survival_score": surv_score,
        "profit_factor_score": pf_score,
        "sample_score": sample_score,
        "split_consistency_score": split_cons,
        "regime_consistency_score": reg_cons,
        "tf_consistency_score": tf_cons,
        "robustness_score": robustness,
    }


def overfitting_risk(
    fname: str,
    full_perf: dict,
    temporal: List[dict],
    tf_rows: List[dict],
    regime_rows: List[dict],
    symbol_rows: List[dict],
) -> dict:
    fdef = FILTER_DEFS[fname]
    risks = []
    n = full_perf.get("n", 0)

    if fdef["symbol"] == "BNBUSDT":
        risks.append("symbol_single_BNB")
    if n < 50:
        risks.append("low_sample")
    if n < 20:
        risks.append("unstable_sample")

    tf_sub = [r for r in tf_rows if r.get("filter_id") == fname and r.get("timeframe")]
    if tf_sub:
        counts = {r["timeframe"]: r.get("n", 0) for r in tf_sub}
        total = sum(counts.values()) or 1
        dominant = max(counts, key=counts.get)
        if counts[dominant] / total > 0.7:
            risks.append(f"tf_concentration_{dominant}")

    t_sub = [r for r in temporal if r.get("filter_id") == fname]
    pos_splits = sum(1 for r in t_sub if (r.get("expectancy") or 0) > 0 and (r.get("n") or 0) >= 5)
    valid_splits = sum(1 for r in t_sub if (r.get("n") or 0) >= 5)
    if valid_splits and pos_splits / valid_splits < 0.5:
        risks.append("temporal_inconsistency")

    reg_sub = [r for r in regime_rows if r.get("filter_id") == fname]
    neg_reg = sum(1 for r in reg_sub if (r.get("expectancy") or 0) < 0 and (r.get("n") or 0) >= 5)
    if neg_reg >= 2:
        risks.append("regime_dependency")

    without = next(
        (r for r in symbol_rows if r.get("filter_id") == fname and r.get("symbol") == "without_BNB"),
        {},
    )
    if fname == "CHAMPION" and (without.get("n") or 0) == 0:
        risks.append("zero_without_BNB")

    risk_score = len(risks)
    return {"overfit_risk": risk_score, "overfit_flags": ",".join(risks) if risks else "none"}


def champion_verdict(components: dict, overfit: dict, fname: str = "CHAMPION") -> str:
    score = components.get("robustness_score") or 0
    risk = overfit.get("overfit_risk") or 0
    split_cons = components.get("split_consistency_score") or 0
    sample = components.get("sample_score") or 0

    if risk >= 4 or sample < 20:
        return "REJECTED"
    if fname == "CHAMPION" and "symbol_single_BNB" in overfit.get("overfit_flags", ""):
        if risk >= 2 and split_cons < 60:
            return "OVERFIT_RISK"
        if score >= 55 and split_cons >= 50:
            return "CONDITIONAL"
        return "OVERFIT_RISK"
    if score >= 60 and risk <= 1:
        return "ROBUST"
    if score >= 45 and risk <= 2:
        return "CONDITIONAL"
    if risk >= 3:
        return "OVERFIT_RISK"
    return "CONDITIONAL"


def alternative_robust_filters(
    df: pd.DataFrame,
    temporal: List[dict],
    tf_rows: List[dict],
    regime_rows: List[dict],
    symbol_rows: List[dict],
) -> List[dict]:
    rows = []
    for fname in ALTERNATIVE_FILTERS:
        full = _perf(_apply_filter(df, fname))
        comp = _compute_robustness_components(fname, temporal, tf_rows, regime_rows, full)
        ov = overfitting_risk(fname, full, temporal, tf_rows, regime_rows, symbol_rows)
        verdict = champion_verdict(comp, ov, fname)
        rows.append({
            "section": "alternative_filter",
            "filter_id": fname,
            "filter_name": FILTER_DEFS[fname]["label"],
            **full,
            **comp,
            **ov,
            "verdict": verdict,
        })
    ranked = sorted(rows, key=lambda x: x.get("robustness_score", 0), reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def active_candidate_overlay(
    enriched: pd.DataFrame,
    alternatives: List[dict],
) -> List[dict]:
    if "freshness" not in enriched.columns:
        return []
    cands = active_candidate_tracking(enriched)
    if not cands:
        return []

    robust_filters = [a for a in alternatives if a.get("verdict") in ("ROBUST", "CONDITIONAL")]
    if not robust_filters:
        robust_filters = alternatives[:5]

    rows = []
    for c in cands:
        sym, tf, rule = c["symbol"], c["timeframe"], c["rule"]
        sub = enriched[
            (enriched["symbol"] == sym)
            & (enriched["timeframe"] == tf)
            & (enriched["rule"] == rule)
        ].sort_values("timestamp")
        ev = sub.iloc[-1] if not sub.empty else None

        matches = []
        for alt in robust_filters:
            fdef = FILTER_DEFS.get(alt["filter_id"], {})
            if ev is None:
                continue
            masked = _apply_mask(
                pd.DataFrame([ev]),
                fdef.get("rule", "ALL"),
                fdef.get("symbol", "ALL"),
                "ALL",
                fdef.get("feats", {}),
            )
            if not masked.empty:
                matches.append(alt)

        best = matches[0] if matches else {}
        rows.append({
            "section": "active_candidate",
            "event_id": f"{sym}_{tf}_{rule}",
            "symbol": sym,
            "timeframe": tf,
            "rule": rule,
            "freshness": c.get("freshness"),
            "robust_filter_match": best.get("filter_id", "none"),
            "robustness_score": best.get("robustness_score"),
            "overfit_risk": best.get("overfit_risk"),
            "expectancy": best.get("expectancy"),
        })

    ranked = sorted(rows, key=lambda r: (r.get("robustness_score") or 0), reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["priority_rank"] = i
    return ranked


def observation_priority(active: List[dict]) -> List[dict]:
    return [
        {
            "section": "observation_priority",
            "priority_rank": r.get("priority_rank"),
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "rule": r["rule"],
            "robust_filter_match": r.get("robust_filter_match"),
            "robustness_score": r.get("robustness_score"),
            "overfit_risk": r.get("overfit_risk"),
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


def full_robustness_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)
    completed = enriched[enriched["status"] == "COMPLETED"].copy()
    if completed.empty:
        return {"export_df": build_export([])}

    all_filters = tuple(FILTER_DEFS.keys())
    compare_filters = (
        "CHAMPION", "Filter_Q", "Filter_C", "Filter_BNB",
        "Filter_STRUCT", "Filter_MF", "Filter_BNB_CORE",
    )

    temporal = temporal_split_validation(completed, compare_filters)
    tf_rows = timeframe_robustness(completed, compare_filters)
    sym_rows = symbol_robustness(completed, compare_filters)
    reg_rows = regime_robustness(completed, compare_filters)
    loo = leave_one_out_validation(completed, compare_filters)
    min_sample = minimum_sample_check(temporal + tf_rows + reg_rows)

    champ_full = _perf(_apply_filter(completed, "CHAMPION"))
    champ_comp = _compute_robustness_components("CHAMPION", temporal, tf_rows, reg_rows, champ_full)
    champ_ov = overfitting_risk("CHAMPION", champ_full, temporal, tf_rows, reg_rows, sym_rows)
    champ_verdict = champion_verdict(champ_comp, champ_ov, "CHAMPION")

    champ_row = {
        "section": "champion_verdict",
        "filter_id": "CHAMPION",
        "filter_name": FILTER_DEFS["CHAMPION"]["label"],
        **champ_full,
        **champ_comp,
        **champ_ov,
        "verdict": champ_verdict,
    }

    robustness_scores = []
    for fname in compare_filters:
        full = _perf(_apply_filter(completed, fname))
        comp = _compute_robustness_components(fname, temporal, tf_rows, reg_rows, full)
        ov = overfitting_risk(fname, full, temporal, tf_rows, reg_rows, sym_rows)
        robustness_scores.append({
            "section": "robustness_score",
            "filter_id": fname,
            "filter_name": FILTER_DEFS[fname]["label"],
            **full,
            **comp,
            **ov,
            "verdict": champion_verdict(comp, ov, fname),
        })

    overfit_rows = [
        {
            "section": "overfitting_risk",
            "filter_id": r["filter_id"],
            "filter_name": r.get("filter_name"),
            "overfit_risk": r.get("overfit_risk"),
            "n": r.get("n"),
            "value": r.get("overfit_flags"),
        }
        for r in robustness_scores
    ]

    alternatives = alternative_robust_filters(completed, temporal, tf_rows, reg_rows, sym_rows)
    active = active_candidate_overlay(enriched, alternatives)
    priority = observation_priority(active)

    all_rows = (
        temporal + tf_rows + sym_rows + reg_rows + loo + min_sample
        + robustness_scores + overfit_rows + [champ_row] + alternatives + active + priority
    )

    return {
        "completed": completed,
        "temporal_split": temporal,
        "timeframe_robustness": tf_rows,
        "symbol_robustness": sym_rows,
        "regime_robustness": reg_rows,
        "leave_one_out": loo,
        "minimum_sample": min_sample,
        "robustness_scores": robustness_scores,
        "champion_verdict": champ_row,
        "alternatives": alternatives,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": build_export(all_rows),
    }
