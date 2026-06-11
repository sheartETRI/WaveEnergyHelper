"""Wave Generalization — Candidate Rule 종목·타임프레임 반복성 관측.

기존 파이프라인·Candidate Rules만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import (
    BRANCH_COMPLETED,
    BRANCH_REQUIRED,
    extract_double_bottom_events,
)
from config.settings import WAVE_LAYER_ROLES
from analysis.wave_candidate_rules import (
    _rule_metrics,
    enrich_confluence_events,
    rule_mask,
)
from analysis.wave_confirmation_lifecycle import run_lifecycle_timeline
from analysis.wave_confluence import (
    add_confluence_indicators,
    confluence_score,
    extract_confluence_at,
)
from analysis.wave_exit import POLICY_A, build_exit_results
from analysis.wave_outcome import _find_bar_index
from analysis.wave_survival import build_survival_from_lifecycle
_LAYER_LARGE = WAVE_LAYER_ROLES["large"]

GENERALIZATION_SYMBOLS = ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT")
GENERALIZATION_TIMEFRAMES = ("1h", "4h", "1d")
GENERALIZATION_RULES = (
    "RULE_A",
    "RULE_B",
    "RULE_C",
    "RULE_D",
    "RULE_SCORE_3",
)

MA_WARMUP = 240


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _confluence_csv_path(symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"wave_confluence_{symbol}_{interval}.csv")


def _cache_dir() -> str:
    path = os.path.join(_validation_dir(), "_generalization_cache")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_confluence_path(symbol: str, interval: str) -> str:
    return os.path.join(_cache_dir(), f"confluence_{symbol}_{interval}.csv")


def _tracker_csv_path(symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"wave_tracker_{symbol}_{interval}.csv")


def _cell_limit(interval: str) -> Optional[int]:
    if interval == "4h":
        return 1600
    return None


def load_cell_confluence(symbol: str, interval: str) -> pd.DataFrame:
    """기존 Confluence CSV → 캐시 → 라이브 빌드."""
    for path in (_confluence_csv_path(symbol, interval), _cache_confluence_path(symbol, interval)):
        if os.path.isfile(path):
            return pd.read_csv(path, parse_dates=["timestamp"])
    df = build_cell_confluence_live(symbol, interval)
    if not df.empty:
        df.to_csv(_cache_confluence_path(symbol, interval), index=False)
    return df


def _infer_branch_from_pipeline(pipeline: pd.DataFrame, pos: int) -> str:
    """Tracker 미존재 셀용 관측 proxy (Branch 분석 major_k_slope_1 방향성)."""
    k_col = f"stoch_k_{_LAYER_LARGE}"
    if k_col not in pipeline.columns or pos < 1:
        return BRANCH_COMPLETED
    k_series = pipeline[k_col]
    if pd.isna(k_series.iloc[pos]) or pd.isna(k_series.iloc[pos - 1]):
        return BRANCH_COMPLETED
    slope_1 = float(k_series.iloc[pos]) - float(k_series.iloc[pos - 1])
    return BRANCH_REQUIRED if slope_1 < 0 else BRANCH_COMPLETED


def _events_from_lifecycle(
    lifecycle: pd.DataFrame,
    bare: pd.DataFrame,
    pipeline: pd.DataFrame,
    tracker: Optional[pd.DataFrame],
) -> List[dict]:
    """DB 에피소드 → branch 라벨 (tracker 우선, 없으면 proxy)."""
    if tracker is not None and not tracker.empty:
        return extract_double_bottom_events(tracker)

    events = []
    for _, row in lifecycle.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        pos = _find_bar_index(bare, ts)
        if pos is None:
            continue
        events.append({
            "timestamp": ts,
            "branch": _infer_branch_from_pipeline(pipeline, pos),
        })
    return events


def build_cell_confluence_live(symbol: str, interval: str) -> pd.DataFrame:
    """메모리 파이프라인으로 Confluence 이벤트 구성 (기존 CSV 불변)."""
    from data.binance import get_auto_limit
    from display.asof import build_ohlcv_cache, fetch_ohlcv_bare, run_indicator_pipeline

    lim = _cell_limit(interval)
    if lim is None:
        lim = get_auto_limit(interval)
    bare = fetch_ohlcv_bare(symbol, interval, lim, paginated=lim > 1000)
    if bare is None or bare.empty or len(bare) < MA_WARMUP + 1:
        return pd.DataFrame()

    pipeline = run_indicator_pipeline(bare)
    extra = {"4h": lim} if interval == "4h" else {}
    cache = build_ohlcv_cache(symbol, interval, bare, extra_limits=extra)

    lifecycle = run_lifecycle_timeline(symbol, interval, bare, cache, warmup=MA_WARMUP)
    if lifecycle.empty:
        return pd.DataFrame()

    exits = build_exit_results(lifecycle, bare, pipeline)
    tp3 = exits[exits["policy"] == POLICY_A] if not exits.empty else pd.DataFrame()
    exit_keyed = tp3.set_index("timestamp") if not tp3.empty else None

    survival = build_survival_from_lifecycle(lifecycle)
    surv_keyed = survival.set_index("timestamp") if not survival.empty else None

    tracker_path = _tracker_csv_path(symbol, interval)
    tracker = (
        pd.read_csv(tracker_path, parse_dates=["timestamp"])
        if os.path.isfile(tracker_path) else None
    )
    events = _events_from_lifecycle(lifecycle, bare, pipeline, tracker)
    if not events:
        return pd.DataFrame()

    enriched = add_confluence_indicators(pipeline.copy())
    rows: List[dict] = []
    for ev in events:
        ts = ev["timestamp"]
        pos = _find_bar_index(bare, ts)
        if pos is None or pos >= len(enriched):
            continue
        cf = extract_confluence_at(enriched, pos)
        ret = succ = None
        if exit_keyed is not None and ts in exit_keyed.index:
            ex = exit_keyed.loc[ts]
            if isinstance(ex, pd.DataFrame):
                ex = ex.iloc[0]
            ret = ex.get("return_pct")
            if pd.notna(ret):
                ret = float(ret)
                succ = ret > 0
        surv_bars = None
        if surv_keyed is not None and ts in surv_keyed.index:
            sv = surv_keyed.loc[ts]
            if isinstance(sv, pd.DataFrame):
                sv = sv.iloc[0]
            if pd.notna(sv.get("survival_bars")):
                surv_bars = float(sv["survival_bars"])
        row = {
            "timestamp": ts,
            "branch": ev["branch"],
            "branch_label": str(ev["branch"]),
            "return_pct": ret,
            "success": succ,
            **cf,
            "survival_bars": surv_bars,
        }
        row["confluence_score"] = confluence_score(pd.Series(row))
        rows.append(row)

    return pd.DataFrame(rows)


def evaluate_cell_rules(
    confluence: pd.DataFrame,
    symbol: str,
    interval: str,
) -> List[dict]:
    """단일 symbol×timeframe 셀의 Rule별 지표."""
    if confluence.empty:
        return [
            _empty_cell(symbol, interval, rule)
            for rule in GENERALIZATION_RULES
        ]

    enriched = enrich_confluence_events(confluence, symbol, interval)
    if "survival_bars" in confluence.columns and "survival_bars" not in enriched.columns:
        enriched["survival_bars"] = confluence["survival_bars"].values

    results = []
    for rule in GENERALIZATION_RULES:
        mask = rule_mask(enriched, rule)
        grp = enriched[mask]
        m = _rule_metrics(grp)
        results.append({
            "symbol": symbol,
            "timeframe": interval,
            "rule": rule,
            "count": m["count"],
            "n": m["n"],
            "win_rate": m["win_rate"],
            "expectancy": m["expectancy"],
            "profit_factor": m["profit_factor"],
            "payoff_ratio": m["payoff_ratio"],
            "avg_return": m["avg_return"],
            "avg_survival": m["avg_survival"],
        })
    return results


def _empty_cell(symbol: str, interval: str, rule: str) -> dict:
    return {
        "symbol": symbol,
        "timeframe": interval,
        "rule": rule,
        "count": 0,
        "n": 0,
        "win_rate": 0.0,
        "expectancy": None,
        "profit_factor": None,
        "payoff_ratio": None,
        "avg_return": None,
        "avg_survival": None,
    }


def aggregate_cells(cell_rows: List[dict]) -> pd.DataFrame:
    """12셀 결과 DataFrame."""
    return pd.DataFrame(cell_rows)


def expectancy_positive_rate(rows: List[dict], rule: str, total_cells: int = 12) -> float:
    """양수 expectancy 셀 비율 (전체 셀 대비)."""
    rule_rows = [r for r in rows if r["rule"] == rule]
    positive = sum(
        1 for r in rule_rows
        if r.get("expectancy") is not None and r["expectancy"] > 0
    )
    return positive / total_cells if total_cells else 0.0


def _cell_n(row: dict) -> int:
    n = row.get("n")
    if n is not None and not (isinstance(n, float) and np.isnan(n)):
        return int(n)
    c = row.get("count")
    return int(c) if c is not None and not (isinstance(c, float) and np.isnan(c)) else 0


def median_expectancy(rows: List[dict], rule: str) -> Optional[float]:
    exps = [
        r["expectancy"] for r in rows
        if r["rule"] == rule and r.get("expectancy") is not None and _cell_n(r) >= 1
    ]
    if not exps:
        return None
    return float(np.median(exps))


def generalization_score(rows: List[dict], rule: str, total_cells: int = 12) -> Optional[float]:
    """관측용: positive_rate × median_expectancy."""
    med = median_expectancy(rows, rule)
    if med is None:
        return None
    return expectancy_positive_rate(rows, rule, total_cells) * med


def _variance(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return 0.0 if len(values) == 1 else None
    return float(np.var(values, ddof=0))


def rule_symbol_variance(rows: List[dict], rule: str) -> Optional[float]:
    """심볼별 TF expectancy 분산의 평균."""
    vars_: List[float] = []
    for sym in GENERALIZATION_SYMBOLS:
        exps = [
            r["expectancy"] for r in rows
            if r["rule"] == rule and r["symbol"] == sym
            and r.get("expectancy") is not None and _cell_n(r) >= 1
        ]
        v = _variance(exps)
        if v is not None:
            vars_.append(v)
    return float(np.mean(vars_)) if vars_ else None


def rule_timeframe_variance(rows: List[dict], rule: str) -> Optional[float]:
    """TF별 심볼 expectancy 분산의 평균."""
    vars_: List[float] = []
    for tf in GENERALIZATION_TIMEFRAMES:
        exps = [
            r["expectancy"] for r in rows
            if r["rule"] == rule and r["timeframe"] == tf
            and r.get("expectancy") is not None and _cell_n(r) >= 1
        ]
        v = _variance(exps)
        if v is not None:
            vars_.append(v)
    return float(np.mean(vars_)) if vars_ else None


def rule_overall_variance(rows: List[dict], rule: str) -> Optional[float]:
    exps = [
        r["expectancy"] for r in rows
        if r["rule"] == rule and r.get("expectancy") is not None and _cell_n(r) >= 1
    ]
    return _variance(exps)


def find_outlier_cells(
    rows: List[dict],
    rule: Optional[str] = None,
    best: bool = True,
) -> Optional[dict]:
    """최고/최악 성과 셀."""
    pool = rows
    if rule:
        pool = [r for r in rows if r["rule"] == rule]
    valid = [r for r in pool if r.get("expectancy") is not None and _cell_n(r) >= 1]
    if not valid:
        return None
    key_fn = lambda r: r["expectancy"]
    return max(valid, key=key_fn) if best else min(valid, key=key_fn)


def heatmap_matrix(rows: List[dict], rule: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Rule별 symbol×timeframe expectancy 매트릭스."""
    matrix: Dict[str, Dict[str, Optional[float]]] = {}
    for sym in GENERALIZATION_SYMBOLS:
        matrix[sym] = {}
        for tf in GENERALIZATION_TIMEFRAMES:
            match = next(
                (r for r in rows if r["rule"] == rule and r["symbol"] == sym and r["timeframe"] == tf),
                None,
            )
            matrix[sym][tf] = match.get("expectancy") if match else None
    return matrix


def build_generalization(
    symbols: Tuple[str, ...] = GENERALIZATION_SYMBOLS,
    timeframes: Tuple[str, ...] = GENERALIZATION_TIMEFRAMES,
    live_build: bool = True,
) -> Tuple[pd.DataFrame, List[dict]]:
    """전체 Generalization 매트릭스."""
    all_rows: List[dict] = []
    for sym in symbols:
        for tf in timeframes:
            if live_build:
                conf = load_cell_confluence(sym, tf)
            else:
                path = _confluence_csv_path(sym, tf)
                conf = (
                    pd.read_csv(path, parse_dates=["timestamp"])
                    if os.path.isfile(path) else pd.DataFrame()
                )
            all_rows.extend(evaluate_cell_rules(conf, sym, tf))
    return aggregate_cells(all_rows), all_rows


def summarize_generalization(rows: List[dict]) -> dict:
    """REPORT/UI용 요약."""
    total_cells = len(GENERALIZATION_SYMBOLS) * len(GENERALIZATION_TIMEFRAMES)
    rule_summaries = []
    variance_rows = []

    for rule in GENERALIZATION_RULES:
        pos_rate = expectancy_positive_rate(rows, rule, total_cells)
        med = median_expectancy(rows, rule)
        gen_score = generalization_score(rows, rule, total_cells)
        sym_var = rule_symbol_variance(rows, rule)
        tf_var = rule_timeframe_variance(rows, rule)
        ovr_var = rule_overall_variance(rows, rule)
        positive_cells = sum(
            1 for r in rows
            if r["rule"] == rule and r.get("expectancy") is not None and r["expectancy"] > 0
        )
        rule_summaries.append({
            "rule": rule,
            "positive_cells": positive_cells,
            "positive_rate": pos_rate * 100.0,
            "median_expectancy": med,
            "generalization_score": gen_score,
        })
        variance_rows.append({
            "rule": rule,
            "symbol_variance": sym_var,
            "timeframe_variance": tf_var,
            "overall_variance": ovr_var,
            "variance": ovr_var,
        })

    ranked = sorted(
        rule_summaries,
        key=lambda x: (
            x.get("generalization_score") if x.get("generalization_score") is not None else -999.0,
            x.get("median_expectancy") if x.get("median_expectancy") is not None else -999.0,
            x.get("positive_cells", 0),
        ),
        reverse=True,
    )

    best_overall = find_outlier_cells(rows, best=True)
    worst_overall = find_outlier_cells(rows, best=False)
    best_per_rule = {rule: find_outlier_cells(rows, rule, best=True) for rule in GENERALIZATION_RULES}
    worst_per_rule = {rule: find_outlier_cells(rows, rule, best=False) for rule in GENERALIZATION_RULES}

    symbol_cmp: Dict[str, dict] = {}
    for sym in GENERALIZATION_SYMBOLS:
        sym_rows = [r for r in rows if r["symbol"] == sym and r["rule"] == "RULE_B"]
        valid = [r for r in sym_rows if r.get("expectancy") is not None and _cell_n(r) >= 1]
        symbol_cmp[sym] = {
            "cells_with_data": len(valid),
            "median_expectancy": float(np.median([r["expectancy"] for r in valid])) if valid else None,
            "positive_cells": sum(1 for r in valid if r["expectancy"] > 0),
        }

    tf_cmp: Dict[str, dict] = {}
    for tf in GENERALIZATION_TIMEFRAMES:
        tf_rows = [r for r in rows if r["timeframe"] == tf and r["rule"] == "RULE_B"]
        valid = [r for r in tf_rows if r.get("expectancy") is not None and _cell_n(r) >= 1]
        tf_cmp[tf] = {
            "cells_with_data": len(valid),
            "median_expectancy": float(np.median([r["expectancy"] for r in valid])) if valid else None,
            "positive_cells": sum(1 for r in valid if r["expectancy"] > 0),
        }

    rule_b_rows = [r for r in rows if r["rule"] == "RULE_B"]
    rule_b_valid = [r for r in rule_b_rows if _cell_n(r) >= 1]

    return {
        "total_cells": total_cells,
        "rule_summary": ranked,
        "rule_variance": sorted(
            variance_rows,
            key=lambda x: x.get("overall_variance") if x.get("overall_variance") is not None else 999.0,
        ),
        "top_rules": ranked,
        "most_general_rule": ranked[0] if ranked else {},
        "least_general_rule": ranked[-1] if ranked else {},
        "best_cell": best_overall,
        "worst_cell": worst_overall,
        "best_cells_per_rule": best_per_rule,
        "worst_cells_per_rule": worst_per_rule,
        "symbol_comparison": symbol_cmp,
        "timeframe_comparison": tf_cmp,
        "rule_b_summary": {
            "positive_cells": sum(1 for r in rule_b_valid if r.get("expectancy", 0) > 0),
            "total_with_data": len(rule_b_valid),
            "cells": rule_b_valid,
        },
        "heatmap_rules": {rule: heatmap_matrix(rows, rule) for rule in GENERALIZATION_RULES},
    }
