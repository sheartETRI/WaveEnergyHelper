"""Wave Entry Filter Refinement — 진입 필터 정제 검증 (관측 전용).

wave_live_forward_journal.csv만 소비. 엔진·기존 산출물 변경 없음.
"""
from __future__ import annotations

import itertools
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_live_watchlist import WATCH_RULES
from analysis.wave_regime_segmentation import REGIMES
from analysis.wave_survival_segmentation import enrich_journal, survival_label
from analysis.wave_symbol_segmentation import load_forward_journal

FILTER_RULES = WATCH_RULES
FILTER_SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
FEATURE_THRESHOLDS: Dict[str, Tuple[int, ...]] = {
    "structure_score": (3, 4, 5),
    "money_flow_score": (4, 5),
    "energy_score": (3, 4),
    "quality_score": (3, 4),
    "watchlist_score": (20, 30),
}
MIN_CHAMPION_N = 15
BASELINE_LABEL = "BASELINE_ALL"

CSV_EXPORT_COLS = (
    "section", "filter_id", "rule", "symbol_filter", "regime_filter", "feature_filter",
    "event_id", "symbol", "timeframe", "regime", "survival_label",
    "n", "avg_return_20", "avg_return_40", "expectancy", "win_rate", "profit_factor",
    "survival_rate", "failure_rate", "expectancy_delta", "profit_factor_delta",
    "survival_delta", "rank", "score",
    "positive_cell_ratio", "positive_symbol_ratio", "positive_regime_ratio",
    "confidence_score", "stability_score",
    "champion_filter_match", "expected_expectancy", "expected_survival", "priority_rank",
    "freshness", "value",
)


def _rates(sub: pd.DataFrame) -> dict:
    labeled = sub[sub["survival_label"].isin(["SURVIVED_20", "FAILED_20", "NEUTRAL_20"])]
    n = len(labeled)
    if n == 0:
        return {"survival_rate": None, "failure_rate": None}
    return {
        "survival_rate": round((labeled["survival_label"] == "SURVIVED_20").sum() / n * 100, 2),
        "failure_rate": round((labeled["survival_label"] == "FAILED_20").sum() / n * 100, 2),
    }


def _perf(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0}
    rets20 = sub["return_20"].dropna().astype(float)
    rets40 = sub["return_40"].dropna().astype(float)
    m = compute_expectancy_metrics(rets20)
    r = _rates(sub)
    pf = m.get("profit_factor", 0)
    return {
        "n": len(sub),
        "avg_return_20": round(float(rets20.mean()), 4) if len(rets20) else None,
        "avg_return_40": round(float(rets40.mean()), 4) if len(rets40) else None,
        "expectancy": round(m.get("expectancy", 0), 4),
        "win_rate": round(m.get("win_rate", 0), 2),
        "profit_factor": round(pf, 4) if pf not in (float("inf"),) else 999.0,
        **r,
    }


def _feature_filter_str(feats: Dict[str, int]) -> str:
    if not feats:
        return "none"
    parts = []
    short = {
        "structure_score": "struct",
        "money_flow_score": "mf",
        "energy_score": "eng",
        "quality_score": "qual",
        "watchlist_score": "wl",
    }
    for k, v in sorted(feats.items()):
        parts.append(f"{short.get(k, k)}>={v}")
    return ",".join(parts)


def _filter_id(rule: str, symbol: str, regime: str, feats: Dict[str, int]) -> str:
    return f"R_{rule}|S_{symbol}|G_{regime}|F_{_feature_filter_str(feats)}"


def _apply_mask(df: pd.DataFrame, rule: str, symbol: str, regime: str, feats: Dict[str, int]) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if rule != "ALL":
        mask &= df["rule"] == rule
    if symbol != "ALL":
        mask &= df["symbol"] == symbol
    if regime != "ALL":
        mask &= df["regime"] == regime
    for col, thresh in feats.items():
        if col in df.columns:
            mask &= df[col].astype(float) >= thresh
    return df[mask]


def _feature_combos() -> List[Dict[str, int]]:
    keys = list(FEATURE_THRESHOLDS.keys())
    combos: List[Dict[str, int]] = [{}]
    for key in keys:
        new_combos = []
        for base in combos:
            new_combos.append(base)
            for thresh in FEATURE_THRESHOLDS[key]:
                new_combos.append({**base, key: thresh})
        combos = new_combos
    return combos


def generate_all_filters() -> List[dict]:
    """모든 필터 조합 정의."""
    filters: List[dict] = []
    feat_combos = _feature_combos()
    for rule in list(FILTER_RULES) + ["ALL"]:
        for symbol in list(FILTER_SYMBOLS) + ["ALL"]:
            for regime in list(REGIMES) + ["ALL"]:
                for feats in feat_combos:
                    if rule == "ALL" and symbol == "ALL" and regime == "ALL" and not feats:
                        fid = BASELINE_LABEL
                    elif rule == "ALL" and symbol == "ALL" and regime == "ALL":
                        continue
                    else:
                        fid = _filter_id(rule, symbol, regime, feats)
                    filters.append({
                        "filter_id": fid,
                        "rule": rule,
                        "symbol_filter": symbol,
                        "regime_filter": regime,
                        "feature_filter": _feature_filter_str(feats),
                        "feats": feats,
                    })
    return filters


def filter_performance(df: pd.DataFrame, filters: List[dict], baseline: dict) -> List[dict]:
    rows = []
    b_exp = baseline.get("expectancy") or 0
    b_pf = baseline.get("profit_factor") or 0
    b_surv = baseline.get("survival_rate") or 0

    for f in filters:
        sub = _apply_mask(df, f["rule"], f["symbol_filter"], f["regime_filter"], f["feats"])
        p = _perf(sub)
        if p.get("n", 0) == 0:
            continue
        rows.append({
            "section": "filter_performance",
            "filter_id": f["filter_id"],
            "rule": f["rule"],
            "symbol_filter": f["symbol_filter"],
            "regime_filter": f["regime_filter"],
            "feature_filter": f["feature_filter"],
            **p,
            "expectancy_delta": round((p.get("expectancy") or 0) - b_exp, 4),
            "profit_factor_delta": round((p.get("profit_factor") or 0) - b_pf, 4),
            "survival_delta": round((p.get("survival_rate") or 0) - b_surv, 4),
        })
    return rows


def rule_filter_analysis(df: pd.DataFrame, baseline: dict) -> List[dict]:
    rows = []
    b_exp = baseline.get("expectancy") or 0
    for rule in FILTER_RULES:
        sub = df[df["rule"] == rule]
        p = _perf(sub)
        rows.append({
            "section": "rule_filter",
            "filter_id": f"RULE_{rule}",
            "rule": rule,
            "symbol_filter": "ALL",
            "regime_filter": "ALL",
            "feature_filter": "none",
            **p,
            "expectancy_delta": round((p.get("expectancy") or 0) - b_exp, 4),
        })
    return rows


def symbol_filter_analysis(df: pd.DataFrame, baseline: dict) -> List[dict]:
    rows = []
    b_exp = baseline.get("expectancy") or 0
    for sym in FILTER_SYMBOLS:
        sub = df[df["symbol"] == sym]
        p = _perf(sub)
        rows.append({
            "section": "symbol_filter",
            "filter_id": f"SYMBOL_{sym}",
            "rule": "ALL",
            "symbol_filter": sym,
            "regime_filter": "ALL",
            "feature_filter": "none",
            **p,
            "expectancy_delta": round((p.get("expectancy") or 0) - b_exp, 4),
        })
    return rows


def regime_filter_analysis(df: pd.DataFrame, baseline: dict) -> List[dict]:
    rows = []
    b_exp = baseline.get("expectancy") or 0
    for regime in REGIMES:
        sub = df[df["regime"] == regime]
        p = _perf(sub)
        rows.append({
            "section": "regime_filter",
            "filter_id": f"REGIME_{regime}",
            "rule": "ALL",
            "symbol_filter": "ALL",
            "regime_filter": regime,
            "feature_filter": "none",
            **p,
            "expectancy_delta": round((p.get("expectancy") or 0) - b_exp, 4),
        })
    return rows


def feature_threshold_analysis(df: pd.DataFrame, baseline: dict) -> List[dict]:
    rows = []
    b_exp = baseline.get("expectancy") or 0
    for feat, thresholds in FEATURE_THRESHOLDS.items():
        for thresh in thresholds:
            sub = df[df[feat].astype(float) >= thresh]
            p = _perf(sub)
            rows.append({
                "section": "feature_threshold",
                "filter_id": f"{feat}>={thresh}",
                "rule": "ALL",
                "symbol_filter": "ALL",
                "regime_filter": "ALL",
                "feature_filter": f"{feat}>={thresh}",
                **p,
                "expectancy_delta": round((p.get("expectancy") or 0) - b_exp, 4),
            })
    return rows


def _filter_score(row: dict) -> float:
    exp = row.get("expectancy") or 0
    pf = row.get("profit_factor") or 0
    if pf == 999.0:
        pf = 5.0
    surv = row.get("survival_rate") or 0
    n = row.get("n") or 0
    n_bonus = min(n / 100, 1.0) * 0.5
    return exp * 0.35 + min(pf, 5) * 0.25 + surv * 0.02 + n_bonus


def champion_filters(perf_rows: List[dict], top_n: int = 20) -> Tuple[List[dict], List[dict]]:
    eligible = [
        r for r in perf_rows
        if r.get("n", 0) >= MIN_CHAMPION_N
        and r.get("filter_id") != BASELINE_LABEL
        and r.get("rule") != "ALL"
    ]
    for r in eligible:
        r["score"] = round(_filter_score(r), 2)

    ranked = sorted(eligible, key=lambda x: x["score"], reverse=True)
    champions = []
    for i, r in enumerate(ranked[:top_n], start=1):
        champions.append({"section": "champion_filter", "rank": i, **r})

    worst_src = [r for r in perf_rows if r.get("n", 0) >= MIN_CHAMPION_N and r.get("filter_id") != BASELINE_LABEL]
    for r in worst_src:
        if "score" not in r:
            r["score"] = round(_filter_score(r), 2)
    worst = []
    for i, r in enumerate(sorted(worst_src, key=lambda x: x.get("score", 0))[:top_n], start=1):
        worst.append({"section": "worst_filter", "rank": i, **r})

    return champions, worst


def robustness_analysis(df: pd.DataFrame, champions: List[dict]) -> List[dict]:
    rows = []
    for champ in champions:
        fid = champ["filter_id"]
        rule = champ.get("rule", "ALL")
        symbol = champ.get("symbol_filter", "ALL")
        regime = champ.get("regime_filter", "ALL")
        feat_str = champ.get("feature_filter", "none")
        feats = {}
        if feat_str and feat_str != "none":
            short_rev = {"struct": "structure_score", "mf": "money_flow_score", "eng": "energy_score",
                         "qual": "quality_score", "wl": "watchlist_score"}
            for part in feat_str.split(","):
                name, val = part.split(">=")
                feats[short_rev.get(name, name)] = int(val)

        sym_pos = reg_pos = cell_pos = cell_total = 0
        for sym in FILTER_SYMBOLS:
            for reg in REGIMES:
                sub = _apply_mask(df, rule, sym if symbol == "ALL" else symbol, reg if regime == "ALL" else regime, feats)
                if symbol != "ALL" and sym != symbol:
                    continue
                if regime != "ALL" and reg != regime:
                    continue
                if sub.empty:
                    continue
                cell_total += 1
                p = _perf(sub)
                if (p.get("expectancy") or 0) > 0:
                    cell_pos += 1

        sym_total = sym_pos_cnt = 0
        for sym in FILTER_SYMBOLS:
            if symbol != "ALL" and sym != symbol:
                continue
            sub = _apply_mask(df, rule, sym, regime if regime != "ALL" else "ALL", feats)
            if sub.empty:
                continue
            sym_total += 1
            if (_perf(sub).get("expectancy") or 0) > 0:
                sym_pos_cnt += 1

        reg_total = reg_pos_cnt = 0
        for reg in REGIMES:
            if regime != "ALL" and reg != regime:
                continue
            sub = _apply_mask(df, rule, symbol if symbol != "ALL" else "ALL", reg, feats)
            if sub.empty:
                continue
            reg_total += 1
            if (_perf(sub).get("expectancy") or 0) > 0:
                reg_pos_cnt += 1

        rows.append({
            "section": "robustness",
            "filter_id": fid,
            "rank": champ.get("rank"),
            "n": champ.get("n"),
            "positive_cell_ratio": round(cell_pos / cell_total * 100, 2) if cell_total else None,
            "positive_symbol_ratio": round(sym_pos_cnt / sym_total * 100, 2) if sym_total else None,
            "positive_regime_ratio": round(reg_pos_cnt / reg_total * 100, 2) if reg_total else None,
            "score": champ.get("score"),
        })
    return rows


def false_discovery_analysis(champions: List[dict], robustness: List[dict]) -> List[dict]:
    rob_map = {r["filter_id"]: r for r in robustness}
    rows = []
    for c in champions:
        fid = c["filter_id"]
        n = c.get("n", 0)
        rob = rob_map.get(fid, {})
        conf = round(min(1.0, n / 80) * 100, 2)
        stab_parts = [rob.get("positive_cell_ratio"), rob.get("positive_symbol_ratio"), rob.get("positive_regime_ratio")]
        stab_vals = [v for v in stab_parts if v is not None]
        stability = round(sum(stab_vals) / len(stab_vals), 2) if stab_vals else 0.0
        rows.append({
            "section": "false_discovery",
            "filter_id": fid,
            "rank": c.get("rank"),
            "n": n,
            "confidence_score": conf,
            "stability_score": stability,
            "expectancy": c.get("expectancy"),
            "score": c.get("score"),
        })
    return rows


def _parse_filter_def(champ: dict) -> Tuple[str, str, str, Dict[str, int]]:
    feat_str = champ.get("feature_filter", "none")
    feats: Dict[str, int] = {}
    if feat_str and feat_str != "none":
        short_rev = {"struct": "structure_score", "mf": "money_flow_score", "eng": "energy_score",
                     "qual": "quality_score", "wl": "watchlist_score"}
        for part in feat_str.split(","):
            name, val = part.split(">=")
            feats[short_rev.get(name, name)] = int(val)
    return (
        champ.get("rule", "ALL"),
        champ.get("symbol_filter", "ALL"),
        champ.get("regime_filter", "ALL"),
        feats,
    )


def _event_matches(row: pd.Series, rule: str, symbol: str, regime: str, feats: Dict[str, int]) -> bool:
    if rule != "ALL" and row.get("rule") != rule:
        return False
    if symbol != "ALL" and row.get("symbol") != symbol:
        return False
    if regime != "ALL" and row.get("regime") != regime:
        return False
    for col, thresh in feats.items():
        if float(row.get(col, 0) or 0) < thresh:
            return False
    return True


def active_candidate_overlay(enriched: pd.DataFrame, champions: List[dict]) -> List[dict]:
    if "freshness" not in enriched.columns:
        return []
    cands = active_candidate_tracking(enriched)
    if not cands:
        return []

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
        for champ in champions[:10]:
            r, s, g, feats = _parse_filter_def(champ)
            if ev is not None and _event_matches(ev, r, s, g, feats):
                matches.append(champ)

        best = matches[0] if matches else (champions[0] if champions else {})
        match_name = best.get("filter_id", "none") if matches else "none"

        rows.append({
            "section": "active_candidate",
            "event_id": f"{sym}_{tf}_{rule}",
            "symbol": sym,
            "timeframe": tf,
            "rule": rule,
            "freshness": c.get("freshness"),
            "champion_filter_match": match_name,
            "expected_expectancy": best.get("expectancy") if matches else None,
            "expected_survival": best.get("survival_rate") if matches else None,
            "score": best.get("score") if matches else None,
        })

    ranked = sorted(rows, key=lambda r: (r.get("expected_expectancy") or -999, r.get("score") or 0), reverse=True)
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
            "champion_filter_match": r.get("champion_filter_match"),
            "expected_expectancy": r.get("expected_expectancy"),
            "expected_survival": r.get("expected_survival"),
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


def full_entry_filter_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)
    completed = enriched[enriched["status"] == "COMPLETED"].copy()
    if completed.empty:
        return {"export_df": build_export([]), "baseline": {}}

    filters = generate_all_filters()
    baseline_row = next((f for f in filters if f["filter_id"] == BASELINE_LABEL), None)
    baseline_sub = completed if baseline_row is None else _apply_mask(
        completed, baseline_row["rule"], baseline_row["symbol_filter"],
        baseline_row["regime_filter"], baseline_row["feats"],
    )
    baseline = _perf(baseline_sub)
    baseline["filter_id"] = BASELINE_LABEL

    perf = filter_performance(completed, filters, baseline)
    rule_f = rule_filter_analysis(completed, baseline)
    sym_f = symbol_filter_analysis(completed, baseline)
    reg_f = regime_filter_analysis(completed, baseline)
    feat_f = feature_threshold_analysis(completed, baseline)
    champions, worst = champion_filters(perf, 20)
    robust = robustness_analysis(completed, champions)
    false_disc = false_discovery_analysis(champions, robust)
    active = active_candidate_overlay(completed, champions)
    priority = observation_priority(active)

    baseline_export = [{
        "section": "baseline",
        "filter_id": BASELINE_LABEL,
        "rule": "ALL",
        "symbol_filter": "ALL",
        "regime_filter": "ALL",
        "feature_filter": "none",
        **baseline,
        "expectancy_delta": 0.0,
        "profit_factor_delta": 0.0,
        "survival_delta": 0.0,
    }]

    all_rows = (
        baseline_export + perf + rule_f + sym_f + reg_f + feat_f
        + champions + worst + robust + false_disc + active + priority
    )

    return {
        "completed": completed,
        "baseline": baseline,
        "filter_performance": perf,
        "rule_filter": rule_f,
        "symbol_filter": sym_f,
        "regime_filter": reg_f,
        "feature_threshold": feat_f,
        "champion_filters": champions,
        "worst_filters": worst,
        "robustness": robust,
        "false_discovery": false_disc,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": build_export(all_rows),
    }
