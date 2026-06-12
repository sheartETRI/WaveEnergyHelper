"""Wave Symbol Segmentation — Rule vs Symbol 성과 분해 검증.

wave_live_forward_journal.csv + watchlist + observation CSV만 소비. 엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_live_forward_journal import active_candidate_tracking
from analysis.wave_live_watchlist import WATCH_RULES

PRIMARY_SYMBOLS = ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT")
EXTENDED_SYMBOLS = ("XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT")
ALL_SYMBOLS = PRIMARY_SYMBOLS + EXTENDED_SYMBOLS
TIMEFRAMES = ("1h", "4h", "1d")
FAILURE_FOCUS = ("STRUCTURE_FAIL", "MONEY_FLOW_DROP", "STOP_LOSS_3")
MIN_CELL_N = 1

CSV_EXPORT_COLS = (
    "section", "rule", "symbol", "timeframe", "rank",
    "n", "completed_n", "pending_n",
    "win_rate_5", "win_rate_10", "win_rate_20", "win_rate_40",
    "avg_return_20", "avg_return_40", "expectancy_20", "expectancy_40",
    "structure_fail_pct", "money_flow_drop_pct", "stop_loss_3_pct",
    "positive", "watchlist_score", "historical_avg20", "historical_expectancy20",
    "current_rank", "value",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def load_forward_journal() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_live_forward_journal.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def load_watchlist() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_live_watchlist.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def _win_rate(series: pd.Series) -> Optional[float]:
    labeled = series.dropna()
    if labeled.empty:
        return None
    wins = (labeled == "WIN").sum()
    return round(float(wins / len(labeled) * 100.0), 2)


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
        row[f"win_rate_{h}"] = _win_rate(sub[f"outcome_{h}"])
    row["avg_return_20"] = _avg(sub["return_20"])
    row["avg_return_40"] = _avg(sub["return_40"])
    row["expectancy_20"] = _expectancy(sub["return_20"])
    row["expectancy_40"] = _expectancy(sub["return_40"])
    return row


def rule_symbol_matrix(journal: pd.DataFrame) -> List[dict]:
    rows = []
    symbols = sorted(journal["symbol"].unique()) if not journal.empty else list(ALL_SYMBOLS)
    for rule in WATCH_RULES:
        for sym in symbols:
            sub = journal[(journal["rule"] == rule) & (journal["symbol"] == sym)]
            m = _cell_metrics(sub)
            rows.append({"section": "rule_symbol", "rule": rule, "symbol": sym, "timeframe": "", **m})
    return rows


def rule_symbol_tf_matrix(journal: pd.DataFrame) -> List[dict]:
    rows = []
    if journal.empty:
        return rows
    for rule in WATCH_RULES:
        for sym in sorted(journal["symbol"].unique()):
            for tf in TIMEFRAMES:
                sub = journal[
                    (journal["rule"] == rule)
                    & (journal["symbol"] == sym)
                    & (journal["timeframe"] == tf)
                ]
                if sub.empty:
                    continue
                m = _cell_metrics(sub)
                rows.append({
                    "section": "rule_symbol_tf",
                    "rule": rule,
                    "symbol": sym,
                    "timeframe": tf,
                    **m,
                })
    return rows


def failure_cause_by_rule_symbol(journal: pd.DataFrame) -> List[dict]:
    rows = []
    if journal.empty or "failure_cause" not in journal.columns:
        return rows
    fail = journal[journal["failure_cause"].notna()]
    for rule in WATCH_RULES:
        for sym in sorted(journal["symbol"].unique()):
            sub = fail[(fail["rule"] == rule) & (fail["symbol"] == sym)]
            if sub.empty:
                continue
            total = len(sub)
            row = {"section": "failure_cause", "rule": rule, "symbol": sym, "timeframe": "", "n": total}
            for cause in FAILURE_FOCUS:
                cnt = int((sub["failure_cause"] == cause).sum())
                row[f"{cause.lower()}_pct"] = round(cnt / total * 100.0, 1)
            rows.append(row)
    return rows


def champion_cells(cells: List[dict], key: str, top_n: int = 20) -> List[dict]:
    valid = [c for c in cells if c.get("n", 0) >= MIN_CELL_N and c.get(key) is not None]
    ranked = sorted(valid, key=lambda x: x[key], reverse=True)[:top_n]
    out = []
    for i, c in enumerate(ranked, start=1):
        out.append({
            "section": f"champion_{key}",
            "rank": i,
            "rule": c["rule"],
            "symbol": c["symbol"],
            "timeframe": c.get("timeframe", ""),
            "n": c.get("n", 0),
            "avg_return_20": c.get("avg_return_20"),
            "expectancy_20": c.get("expectancy_20"),
            "value": c.get(key),
        })
    return out


def worst_cells(cells: List[dict], key: str = "avg_return_20", top_n: int = 10) -> List[dict]:
    valid = [c for c in cells if c.get("n", 0) >= MIN_CELL_N and c.get(key) is not None]
    ranked = sorted(valid, key=lambda x: x[key])[:top_n]
    out = []
    for i, c in enumerate(ranked, start=1):
        out.append({
            "section": "worst_cell",
            "rank": i,
            "rule": c["rule"],
            "symbol": c["symbol"],
            "timeframe": c.get("timeframe", ""),
            "n": c.get("n", 0),
            "avg_return_20": c.get("avg_return_20"),
            "expectancy_20": c.get("expectancy_20"),
            "value": c.get(key),
        })
    return out


def within_rule_variance(rule_symbol: List[dict]) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        vals = [
            r["avg_return_20"] for r in rule_symbol
            if r.get("rule") == rule and r.get("avg_return_20") is not None and r.get("n", 0) > 0
        ]
        rows.append({
            "section": "within_rule_variance",
            "rule": rule,
            "value": round(float(np.var(vals)), 4) if len(vals) > 1 else 0.0,
            "n": len(vals),
        })
    return rows


def within_symbol_variance(rule_symbol: List[dict]) -> List[dict]:
    rows = []
    symbols = sorted({r["symbol"] for r in rule_symbol})
    for sym in symbols:
        vals = [
            r["avg_return_20"] for r in rule_symbol
            if r.get("symbol") == sym and r.get("avg_return_20") is not None and r.get("n", 0) > 0
        ]
        rows.append({
            "section": "within_symbol_variance",
            "symbol": sym,
            "value": round(float(np.var(vals)), 4) if len(vals) > 1 else 0.0,
            "n": len(vals),
        })
    return rows


def contribution_analysis(journal: pd.DataFrame) -> List[dict]:
    """Rule vs Symbol SS 분해 (event-level return_20)."""
    sub = journal[journal["return_20"].notna()].copy()
    if sub.empty:
        return []
    sub["return_20"] = sub["return_20"].astype(float)
    grand = float(sub["return_20"].mean())
    total_ss = float(((sub["return_20"] - grand) ** 2).sum())
    if total_ss == 0:
        return [
            {"section": "contribution", "rule": "RULE", "value": 0.0},
            {"section": "contribution", "rule": "SYMBOL", "value": 0.0},
        ]

    rule_ss = 0.0
    for rule, grp in sub.groupby("rule"):
        rule_ss += len(grp) * (float(grp["return_20"].mean()) - grand) ** 2

    sym_ss = 0.0
    for sym, grp in sub.groupby("symbol"):
        sym_ss += len(grp) * (float(grp["return_20"].mean()) - grand) ** 2

    residual = max(0.0, total_ss - rule_ss - sym_ss)
    return [
        {"section": "contribution", "rule": "RULE", "value": round(rule_ss / total_ss * 100.0, 2)},
        {"section": "contribution", "rule": "SYMBOL", "value": round(sym_ss / total_ss * 100.0, 2)},
        {"section": "contribution", "rule": "RESIDUAL", "value": round(residual / total_ss * 100.0, 2),
         "n": len(sub)},
    ]


def cross_symbol_robustness(
    rule_symbol: List[dict],
    rule_symbol_tf: List[dict],
) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        rs = [r for r in rule_symbol if r.get("rule") == rule and r.get("n", 0) > 0]
        positive_syms = sum(1 for r in rs if (r.get("avg_return_20") or 0) > 0)
        total_syms = len(rs)
        positive_symbol_ratio = positive_syms / total_syms if total_syms else 0.0

        rtf = [r for r in rule_symbol_tf if r.get("rule") == rule and r.get("n", 0) > 0]
        positive_cells = sum(1 for r in rtf if (r.get("avg_return_20") or 0) > 0)
        total_cells = len(rtf)
        positive_cell_ratio = positive_cells / total_cells if total_cells else 0.0

        sym_signs = []
        for r in rs:
            sign = "+" if (r.get("avg_return_20") or 0) > 0 else "-"
            sym_signs.append(f"{r['symbol'].replace('USDT', '')}: {sign}")

        rows.append({
            "section": "robustness",
            "rule": rule,
            "positive_cell_ratio": round(positive_cell_ratio * 100.0, 1),
            "positive_symbol_ratio": round(positive_symbol_ratio * 100.0, 1),
            "positive_cells": positive_cells,
            "total_cells": total_cells,
            "positive_symbols": positive_syms,
            "total_symbols": total_syms,
            "value": round(positive_symbol_ratio * 100.0, 1),
            "symbol_signs": ", ".join(sym_signs),
        })
    return rows


def _hist_lookup(rule_symbol: List[dict]) -> Dict[Tuple[str, str], dict]:
    return {(r["rule"], r["symbol"]): r for r in rule_symbol if r.get("section") == "rule_symbol"}


def active_candidate_segmentation(
    journal: pd.DataFrame,
    rule_symbol: List[dict],
) -> List[dict]:
    hist = _hist_lookup(rule_symbol)
    cands = active_candidate_tracking(journal)
    rows = []
    for i, c in enumerate(cands, start=1):
        key = (c["rule"], c["symbol"])
        h = hist.get(key, {})
        rows.append({
            "section": "active_candidate",
            "rank": i,
            "current_rank": i,
            "symbol": c["symbol"],
            "timeframe": c["timeframe"],
            "rule": c["rule"],
            "watchlist_score": c.get("watchlist_score"),
            "historical_avg20": h.get("avg_return_20"),
            "historical_expectancy20": h.get("expectancy_20"),
            "status": c.get("status"),
            "freshness": c.get("freshness"),
            "bars_since_signal": c.get("bars_since_signal"),
        })
    ranked = sorted(
        rows,
        key=lambda r: (
            r.get("historical_avg20") if r.get("historical_avg20") is not None else -999,
            r.get("watchlist_score") or 0,
        ),
        reverse=True,
    )
    for i, r in enumerate(ranked, start=1):
        r["current_rank"] = i
    return ranked


def observation_priority(active_rows: List[dict]) -> List[dict]:
    """Symbol-segmentation 기준 관측 우선순위."""
    ranked = sorted(
        active_rows,
        key=lambda r: (
            r.get("historical_avg20") if r.get("historical_avg20") is not None else -999,
            r.get("watchlist_score") or 0,
        ),
        reverse=True,
    )
    out = []
    for i, r in enumerate(ranked[:12], start=1):
        out.append({
            "section": "observation_priority",
            "rank": i,
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "rule": r["rule"],
            "historical_avg20": r.get("historical_avg20"),
            "watchlist_score": r.get("watchlist_score"),
            "freshness": r.get("freshness"),
        })
    return out


def build_segmentation_export(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CSV_EXPORT_COLS))
    df = pd.DataFrame(rows)
    for col in CSV_EXPORT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[[c for c in CSV_EXPORT_COLS if c in df.columns]]


def full_symbol_segmentation_summary() -> dict:
    journal = load_forward_journal()
    rule_sym = rule_symbol_matrix(journal)
    rule_sym_tf = rule_symbol_tf_matrix(journal)
    failures = failure_cause_by_rule_symbol(journal)
    champions_avg = champion_cells(rule_sym_tf, "avg_return_20", 20)
    champions_exp = champion_cells(rule_sym_tf, "expectancy_20", 20)
    worst = worst_cells(rule_sym_tf, "avg_return_20", 10)
    w_rule_var = within_rule_variance(rule_sym)
    w_sym_var = within_symbol_variance(rule_sym)
    contrib = contribution_analysis(journal)
    robust = cross_symbol_robustness(rule_sym, rule_sym_tf)
    active = active_candidate_segmentation(journal, rule_sym)
    priority = observation_priority(active)

    all_rows = (
        rule_sym + rule_sym_tf + failures + champions_avg + champions_exp
        + worst + w_rule_var + w_sym_var + contrib + robust + active + priority
    )
    export_df = build_segmentation_export(all_rows)

    return {
        "journal": journal,
        "rule_symbol": rule_sym,
        "rule_symbol_tf": rule_sym_tf,
        "failure_causes": failures,
        "champion_avg20": champions_avg,
        "champion_exp20": champions_exp,
        "worst_cells": worst,
        "within_rule_variance": w_rule_var,
        "within_symbol_variance": w_sym_var,
        "contribution": contrib,
        "robustness": robust,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": export_df,
        "available_symbols": sorted(journal["symbol"].unique().tolist()) if not journal.empty else [],
    }
