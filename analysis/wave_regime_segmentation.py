"""Wave Regime Segmentation — Rule / Symbol / Regime 성과 분해.

wave_live_forward_journal.csv + OHLCV pipeline만 소비. 엔진 변경 없음.

Regime 정의 (객관적, 기존 extract_regime_at 기반):
- BULL: ema20_slope_3 > 0 AND ema60_slope_3 > 0
- BEAR: ema20_slope_3 < 0 AND ema60_slope_3 < 0
- SIDEWAYS: 그 외 (혼합 또는 slope 결측)
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_symbol_segmentation import load_forward_journal
from analysis.wave_live_watchlist import WATCH_RULES
from analysis.wave_outcome import _find_bar_index
from analysis.wave_regime_analysis import _load_pipeline, extract_regime_at

REGIMES = ("BULL", "BEAR", "SIDEWAYS")
FAILURE_FOCUS = ("STRUCTURE_FAIL", "MONEY_FLOW_DROP", "STOP_LOSS_3")
MIN_CELL_N = 1

REGIME_DEFINITION = (
    "BULL: ema20_slope_3 > 0 AND ema60_slope_3 > 0; "
    "BEAR: ema20_slope_3 < 0 AND ema60_slope_3 < 0; "
    "SIDEWAYS: mixed slopes or missing"
)

CSV_EXPORT_COLS = (
    "section", "event_id", "rule", "symbol", "timeframe", "regime", "rank",
    "n", "completed_n", "pending_n",
    "win_rate_5", "win_rate_10", "win_rate_20", "win_rate_40",
    "avg_return_20", "avg_return_40", "expectancy_20", "expectancy_40",
    "structure_fail_pct", "money_flow_drop_pct", "stop_loss_3_pct",
    "positive_regime_ratio", "positive_cell_ratio", "positive_symbol_ratio",
    "rule_contribution", "symbol_contribution", "regime_contribution", "residual",
    "watchlist_score", "historical_avg20_in_regime", "historical_expectancy20_in_regime",
    "regime_rank", "value", "regime_signs",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def classify_regime(feats: dict) -> str:
    """EMA slope 기반 BULL/BEAR/SIDEWAYS."""
    e20 = feats.get("ema20_slope_3")
    e60 = feats.get("ema60_slope_3")
    if e20 is None or e60 is None:
        return "SIDEWAYS"
    if e20 > 0 and e60 > 0:
        return "BULL"
    if e20 < 0 and e60 < 0:
        return "BEAR"
    return "SIDEWAYS"


def _win_rate(series: pd.Series) -> Optional[float]:
    labeled = series.dropna()
    if labeled.empty:
        return None
    return round(float((labeled == "WIN").sum() / len(labeled) * 100.0), 2)


def _expectancy(returns: pd.Series) -> Optional[float]:
    rets = returns.dropna().astype(float)
    if rets.empty:
        return None
    m = compute_expectancy_metrics(rets)
    return round(float(m.get("expectancy", 0) or 0), 4)


def _avg(returns: pd.Series) -> Optional[float]:
    rets = returns.dropna().astype(float)
    if rets.empty:
        return None
    return round(float(rets.mean()), 4)


def _cell_metrics(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0}
    completed = sub[sub["status"] == "COMPLETED"]
    pending = sub[sub["status"] != "COMPLETED"]
    row = {
        "n": len(sub),
        "completed_n": len(completed),
        "pending_n": len(pending),
    }
    for h in (5, 10, 20, 40):
        col = f"outcome_{h}"
        if col in sub.columns:
            row[f"win_rate_{h}"] = _win_rate(sub[col])
    row["avg_return_20"] = _avg(sub["return_20"])
    row["avg_return_40"] = _avg(sub["return_40"])
    row["expectancy_20"] = _expectancy(sub["return_20"])
    row["expectancy_40"] = _expectancy(sub["return_40"])
    return row


def assign_event_regimes(journal: pd.DataFrame) -> pd.DataFrame:
    """Event별 regime 부여."""
    if journal.empty:
        return pd.DataFrame()
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    regimes: List[str] = []

    for _, ev in journal.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev["timeframe"])
        key = (sym, tf)
        if key not in pipeline_cache:
            pipeline_cache[key] = _load_pipeline(sym, tf)
        pipe = pipeline_cache[key]
        if pipe.empty:
            regimes.append("SIDEWAYS")
            continue
        pos = _find_bar_index(pipe, pd.Timestamp(ev["timestamp"]))
        if pos is None:
            regimes.append("SIDEWAYS")
            continue
        feats = extract_regime_at(pipe, pos)
        regimes.append(classify_regime(feats))

    out = journal.copy()
    out["regime"] = regimes
    return out


def rule_regime_matrix(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        for regime in REGIMES:
            sub = enriched[(enriched["rule"] == rule) & (enriched["regime"] == regime)]
            m = _cell_metrics(sub)
            rows.append({"section": "rule_regime", "rule": rule, "regime": regime, **m})
    return rows


def symbol_regime_matrix(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in sorted(enriched["symbol"].unique()):
        for regime in REGIMES:
            sub = enriched[(enriched["symbol"] == sym) & (enriched["regime"] == regime)]
            if sub.empty:
                continue
            m = _cell_metrics(sub)
            rows.append({"section": "symbol_regime", "symbol": sym, "regime": regime, **m})
    return rows


def rule_symbol_regime_matrix(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        for sym in sorted(enriched["symbol"].unique()):
            for regime in REGIMES:
                sub = enriched[
                    (enriched["rule"] == rule)
                    & (enriched["symbol"] == sym)
                    & (enriched["regime"] == regime)
                ]
                if sub.empty:
                    continue
                m = _cell_metrics(sub)
                rows.append({
                    "section": "rule_symbol_regime",
                    "rule": rule,
                    "symbol": sym,
                    "regime": regime,
                    **m,
                })
    return rows


def champion_cells(cells: List[dict], key: str, top_n: int = 20) -> List[dict]:
    valid = [
        c for c in cells
        if c.get("n", 0) >= MIN_CELL_N and c.get(key) is not None
    ]
    ranked = sorted(valid, key=lambda x: x[key], reverse=True)[:top_n]
    return [
        {
            "section": f"champion_{key}",
            "rank": i,
            "rule": c.get("rule"),
            "symbol": c.get("symbol"),
            "regime": c.get("regime"),
            "n": c.get("n", 0),
            "avg_return_20": c.get("avg_return_20"),
            "expectancy_20": c.get("expectancy_20"),
            "value": c.get(key),
        }
        for i, c in enumerate(ranked, start=1)
    ]


def worst_cells(cells: List[dict], key: str = "avg_return_20", top_n: int = 20) -> List[dict]:
    valid = [
        c for c in cells
        if c.get("n", 0) >= MIN_CELL_N and c.get(key) is not None
    ]
    ranked = sorted(valid, key=lambda x: x[key])[:top_n]
    return [
        {
            "section": "worst_cell",
            "rank": i,
            "rule": c.get("rule"),
            "symbol": c.get("symbol"),
            "regime": c.get("regime"),
            "n": c.get("n", 0),
            "avg_return_20": c.get("avg_return_20"),
            "value": c.get(key),
        }
        for i, c in enumerate(ranked, start=1)
    ]


def three_way_contribution(enriched: pd.DataFrame) -> List[dict]:
    """Rule / Symbol / Regime SS 분해."""
    sub = enriched[enriched["return_20"].notna()].copy()
    if sub.empty:
        return []
    sub["return_20"] = sub["return_20"].astype(float)
    grand = float(sub["return_20"].mean())
    total_ss = float(((sub["return_20"] - grand) ** 2).sum())
    if total_ss == 0:
        return [
            {"section": "contribution", "rule": "RULE", "rule_contribution": 0.0},
            {"section": "contribution", "rule": "SYMBOL", "symbol_contribution": 0.0},
            {"section": "contribution", "rule": "REGIME", "regime_contribution": 0.0},
        ]

    def _group_ss(col: str) -> float:
        ss = 0.0
        for _, grp in sub.groupby(col):
            ss += len(grp) * (float(grp["return_20"].mean()) - grand) ** 2
        return ss

    rule_ss = _group_ss("rule")
    sym_ss = _group_ss("symbol")
    reg_ss = _group_ss("regime")
    residual = max(0.0, total_ss - rule_ss - sym_ss - reg_ss)

    return [
        {
            "section": "contribution",
            "rule": "RULE",
            "rule_contribution": round(rule_ss / total_ss * 100.0, 2),
            "n": len(sub),
        },
        {
            "section": "contribution",
            "rule": "SYMBOL",
            "symbol_contribution": round(sym_ss / total_ss * 100.0, 2),
        },
        {
            "section": "contribution",
            "rule": "REGIME",
            "regime_contribution": round(reg_ss / total_ss * 100.0, 2),
        },
        {
            "section": "contribution",
            "rule": "RESIDUAL",
            "residual": round(residual / total_ss * 100.0, 2),
        },
    ]


def positive_ratio_analysis(
    rule_regime: List[dict],
    rule_symbol_regime: List[dict],
    enriched: pd.DataFrame,
) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        rr = [r for r in rule_regime if r.get("rule") == rule and r.get("n", 0) > 0]
        pos_reg = sum(1 for r in rr if (r.get("avg_return_20") or 0) > 0)
        total_reg = len(rr)
        regime_signs = ", ".join(
            f"{r['regime'][:4]}: {'+' if (r.get('avg_return_20') or 0) > 0 else '-'}"
            for r in rr
        )

        rsr = [r for r in rule_symbol_regime if r.get("rule") == rule and r.get("n", 0) > 0]
        pos_cell = sum(1 for r in rsr if (r.get("avg_return_20") or 0) > 0)
        total_cell = len(rsr)

        rs = enriched[enriched["rule"] == rule]
        sym_means = rs.groupby("symbol")["return_20"].mean()
        pos_sym = int((sym_means > 0).sum())
        total_sym = len(sym_means)

        rows.append({
            "section": "positive_ratio",
            "rule": rule,
            "positive_regime_ratio": round(pos_reg / total_reg * 100.0, 1) if total_reg else 0.0,
            "positive_cell_ratio": round(pos_cell / total_cell * 100.0, 1) if total_cell else 0.0,
            "positive_symbol_ratio": round(pos_sym / total_sym * 100.0, 1) if total_sym else 0.0,
            "regime_signs": regime_signs,
        })
    return rows


def failure_cause_by_regime(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    fail = enriched[enriched["failure_cause"].notna()]
    if fail.empty:
        return rows
    for regime in REGIMES:
        sub = fail[fail["regime"] == regime]
        if sub.empty:
            continue
        total = len(sub)
        row = {"section": "failure_regime", "regime": regime, "n": total}
        for cause in FAILURE_FOCUS:
            cnt = int((sub["failure_cause"] == cause).sum())
            row[f"{cause.lower()}_pct"] = round(cnt / total * 100.0, 1)
        rows.append(row)
    return rows


def _hist_in_regime(
    enriched: pd.DataFrame,
    rule: str,
    symbol: str,
    regime: str,
) -> Tuple[Optional[float], Optional[float]]:
    sub = enriched[
        (enriched["rule"] == rule)
        & (enriched["symbol"] == symbol)
        & (enriched["regime"] == regime)
    ]
    if sub.empty:
        return None, None
    return _avg(sub["return_20"]), _expectancy(sub["return_20"])


def active_candidate_regime_overlay(enriched: pd.DataFrame) -> List[dict]:
    cands = active_candidate_tracking(enriched)
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    rows = []

    for c in cands:
        sym = c["symbol"]
        tf = c["timeframe"]
        rule = c["rule"]
        key = (sym, tf)
        if key not in pipeline_cache:
            pipeline_cache[key] = _load_pipeline(sym, tf)
        pipe = pipeline_cache[key]
        regime = "SIDEWAYS"
        if not pipe.empty:
            pos = len(pipe) - 1 - int(c.get("bars_since_signal", 0))
            pos = max(0, min(pos, len(pipe) - 1))
            regime = classify_regime(extract_regime_at(pipe, pos))
        hist_avg, hist_exp = _hist_in_regime(enriched, rule, sym, regime)
        rows.append({
            "section": "active_candidate",
            "symbol": sym,
            "timeframe": tf,
            "rule": rule,
            "regime": regime,
            "watchlist_score": c.get("watchlist_score"),
            "historical_avg20_in_regime": hist_avg,
            "historical_expectancy20_in_regime": hist_exp,
            "freshness": c.get("freshness"),
            "status": c.get("status"),
        })

    ranked = sorted(
        rows,
        key=lambda r: (
            r.get("historical_avg20_in_regime") if r.get("historical_avg20_in_regime") is not None else -999,
            r.get("watchlist_score") or 0,
        ),
        reverse=True,
    )
    for i, r in enumerate(ranked, start=1):
        r["regime_rank"] = i
    return ranked


def observation_priority(active: List[dict]) -> List[dict]:
    return [
        {
            "section": "observation_priority",
            "rank": r.get("regime_rank"),
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "rule": r["rule"],
            "regime": r["regime"],
            "historical_avg20_in_regime": r.get("historical_avg20_in_regime"),
            "watchlist_score": r.get("watchlist_score"),
        }
        for r in active[:12]
    ]


def event_regime_rows(enriched: pd.DataFrame) -> List[dict]:
    return [
        {
            "section": "event_regime",
            "event_id": row["event_id"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "rule": row["rule"],
            "regime": row["regime"],
        }
        for _, row in enriched.iterrows()
    ]


def build_export(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CSV_EXPORT_COLS))
    df = pd.DataFrame(rows)
    for col in CSV_EXPORT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[[c for c in CSV_EXPORT_COLS if c in df.columns]]


def full_regime_segmentation_summary() -> dict:
    journal = load_forward_journal()
    enriched = assign_event_regimes(journal)

    rr = rule_regime_matrix(enriched)
    sr = symbol_regime_matrix(enriched)
    rsr = rule_symbol_regime_matrix(enriched)
    champ_avg = champion_cells(rsr, "avg_return_20", 20)
    champ_exp = champion_cells(rsr, "expectancy_20", 20)
    worst = worst_cells(rsr, "avg_return_20", 20)
    contrib = three_way_contribution(enriched)
    pos_ratio = positive_ratio_analysis(rr, rsr, enriched)
    failures = failure_cause_by_regime(enriched)
    active = active_candidate_regime_overlay(enriched)
    priority = observation_priority(active)
    events = event_regime_rows(enriched)

    all_rows = (
        events + rr + sr + rsr + champ_avg + champ_exp + worst
        + contrib + pos_ratio + failures + active + priority
    )
    return {
        "enriched": enriched,
        "rule_regime": rr,
        "symbol_regime": sr,
        "rule_symbol_regime": rsr,
        "champion_avg20": champ_avg,
        "champion_exp20": champ_exp,
        "worst_cells": worst,
        "contribution": contrib,
        "positive_ratio": pos_ratio,
        "failure_regime": failures,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": build_export(all_rows),
        "regime_definition": REGIME_DEFINITION,
    }
