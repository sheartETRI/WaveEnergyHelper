"""Wave Regime Analysis — Rule이 동작하는 시장 구조 관측.

Generalization/Candidate/Confluence 산출물만 소비. ML·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_candidate_rules import rule_mask
from analysis.wave_confluence import add_confluence_indicators
from analysis.wave_generalization import (
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
    load_cell_confluence,
)
from analysis.wave_outcome import _find_bar_index
from config.settings import WAVE_LAYER_ROLES

REGIME_RULES = ("RULE_A", "RULE_B", "RULE_D")
_LAYER_LARGE = WAVE_LAYER_ROLES["large"]

REGIME_NUMERIC = (
    "ema20_slope_3",
    "ema60_slope_3",
    "ema120_slope_3",
    "atr_pct",
    "volatility_20",
    "macd_hist",
    "rsi",
    "rsi_slope_1",
    "dist_ema60_pct",
    "dist_ema120_pct",
    "major_k",
    "major_k_slope_1",
)

VOL_CLUSTERS = ("LOW_VOL", "MID_VOL", "HIGH_VOL")
TREND_CLUSTERS = ("TREND_UP", "TREND_FLAT", "TREND_DOWN")


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _generalization_path() -> str:
    return os.path.join(_validation_dir(), "wave_generalization.csv")


def _load_generalization() -> pd.DataFrame:
    path = _generalization_path()
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def _cell_expectancy(gen: pd.DataFrame, symbol: str, tf: str, rule: str) -> Optional[float]:
    row = gen[
        (gen["symbol"] == symbol)
        & (gen["timeframe"] == tf)
        & (gen["rule"] == rule)
    ]
    if row.empty:
        return None
    val = row.iloc[0].get("expectancy")
    if pd.isna(val):
        return None
    return float(val)


def _cell_has_data(gen: pd.DataFrame, symbol: str, tf: str, rule: str) -> bool:
    row = gen[
        (gen["symbol"] == symbol)
        & (gen["timeframe"] == tf)
        & (gen["rule"] == rule)
    ]
    if row.empty:
        return False
    n = row.iloc[0].get("n", row.iloc[0].get("count", 0))
    if pd.isna(n):
        return False
    return int(n) >= 1


def extract_regime_at(df: pd.DataFrame, pos: int) -> dict:
    """단일 봉 Regime feature."""
    row = df.iloc[pos]
    close = float(row["close"])
    out: dict = {}

    for span, col in ((20, "ema20"), (60, "ema60"), (120, "ema120")):
        ema_col = col
        if ema_col not in df.columns:
            continue
        ema = float(row[ema_col]) if pd.notna(row.get(ema_col)) else None
        if ema is not None and pos >= 3 and pd.notna(df[ema_col].iloc[pos - 3]) and ema != 0:
            prev = float(df[ema_col].iloc[pos - 3])
            out[f"{col}_slope_3"] = (ema - prev) / abs(prev) * 100.0 if prev else 0.0
        else:
            out[f"{col}_slope_3"] = None
        if ema is not None and ema != 0:
            out[f"dist_{col}_pct"] = (close - ema) / ema * 100.0
        else:
            out[f"dist_{col}_pct"] = None

    out["atr_pct"] = float(row["atr_pct"]) if pd.notna(row.get("atr_pct")) else None
    out["volatility_20"] = float(row["volatility_20"]) if pd.notna(row.get("volatility_20")) else None
    out["macd_hist"] = float(row["macd_hist"]) if pd.notna(row.get("macd_hist")) else None
    out["rsi"] = float(row["rsi"]) if pd.notna(row.get("rsi")) else None
    out["rsi_slope_1"] = float(row["rsi_slope_1"]) if pd.notna(row.get("rsi_slope_1")) else None

    k_col = f"stoch_k_{_LAYER_LARGE}"
    if k_col in df.columns and pd.notna(row.get(k_col)):
        out["major_k"] = float(row[k_col])
        if pos >= 1 and pd.notna(df[k_col].iloc[pos - 1]):
            out["major_k_slope_1"] = out["major_k"] - float(df[k_col].iloc[pos - 1])
        else:
            out["major_k_slope_1"] = None
    else:
        out["major_k"] = None
        out["major_k_slope_1"] = None

    # alias for report column names
    out["dist_ema60_pct"] = out.get("dist_ema60_pct")
    out["dist_ema120_pct"] = out.get("dist_ema120_pct")
    out["ema20_slope_3"] = out.get("ema20_slope_3")
    out["ema60_slope_3"] = out.get("ema60_slope_3")
    out["ema120_slope_3"] = out.get("ema120_slope_3")
    return out


def _vol_bucket(atr_pct: float, q33: float, q66: float) -> str:
    if atr_pct <= q33:
        return "LOW_VOL"
    if atr_pct <= q66:
        return "MID_VOL"
    return "HIGH_VOL"


def _trend_bucket(ema20_slope: Optional[float], ema60_slope: Optional[float]) -> str:
    if ema20_slope is None or ema60_slope is None:
        return "TREND_FLAT"
    if ema20_slope > 0 and ema60_slope > 0:
        return "TREND_UP"
    if ema20_slope < 0 and ema60_slope < 0:
        return "TREND_DOWN"
    return "TREND_FLAT"


def build_event_regimes(
    symbol: str,
    timeframe: str,
    rule: str,
    confluence: Optional[pd.DataFrame] = None,
    pipeline: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Rule 매칭 이벤트별 regime feature."""
    if confluence is None:
        confluence = load_cell_confluence(symbol, timeframe)
    if confluence.empty:
        return pd.DataFrame()

    if pipeline is None:
        from data.binance import get_auto_limit
        from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

        lim = 1600 if timeframe == "4h" else get_auto_limit(timeframe)
        bare = fetch_ohlcv_bare(symbol, timeframe, lim, paginated=lim > 1000)
        if bare is None or bare.empty:
            return pd.DataFrame()
        pipeline = add_confluence_indicators(run_indicator_pipeline(bare))

    mask = rule_mask(confluence, rule)
    events = confluence[mask].copy()
    if events.empty:
        return pd.DataFrame()

    rows: List[dict] = []
    for _, ev in events.iterrows():
        ts = pd.Timestamp(ev["timestamp"])
        pos = _find_bar_index(pipeline, ts)
        if pos is None or pos >= len(pipeline):
            continue
        regime = extract_regime_at(pipeline, pos)
        ret = ev.get("return_pct")
        success = ev.get("success")
        if isinstance(success, str):
            success = success.lower() in ("true", "1", "yes")
        rows.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "rule": rule,
            "timestamp": ts,
            "return_pct": float(ret) if pd.notna(ret) else None,
            "success": bool(success) if pd.notna(success) else None,
            **regime,
        })

    return pd.DataFrame(rows)


def _load_pipeline(symbol: str, timeframe: str) -> pd.DataFrame:
    from data.binance import get_auto_limit
    from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

    lim = 1600 if timeframe == "4h" else get_auto_limit(timeframe)
    bare = fetch_ohlcv_bare(symbol, timeframe, lim, paginated=lim > 1000)
    if bare is None or bare.empty:
        return pd.DataFrame()
    return add_confluence_indicators(run_indicator_pipeline(bare))


def build_cell_regimes(rule: str = "RULE_B") -> pd.DataFrame:
    """셀(symbol×tf) 단위 regime profile + generalization expectancy."""
    gen = _load_generalization()
    cell_rows: List[dict] = []
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}

    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            if not _cell_has_data(gen, sym, tf, rule):
                continue
            key = (sym, tf)
            if key not in pipeline_cache:
                pipeline_cache[key] = _load_pipeline(sym, tf)
            events = build_event_regimes(
                sym, tf, rule, pipeline=pipeline_cache[key],
            )
            if events.empty:
                continue
            exp = _cell_expectancy(gen, sym, tf, rule)
            cell_success = exp is not None and exp > 0
            row = {
                "symbol": sym,
                "timeframe": tf,
                "rule": rule,
                "expectancy": exp,
                "cell_success": cell_success,
                "event_count": len(events),
            }
            for feat in REGIME_NUMERIC:
                vals = events[feat].dropna() if feat in events.columns else pd.Series(dtype=float)
                row[feat] = float(vals.mean()) if len(vals) else None
            cell_rows.append(row)

    return pd.DataFrame(cell_rows)


def _collect_events(rule: str, pipeline_cache: Dict[Tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    parts = []
    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            key = (sym, tf)
            if key not in pipeline_cache:
                pipeline_cache[key] = _load_pipeline(sym, tf)
            ev = build_event_regimes(sym, tf, rule, pipeline=pipeline_cache[key])
            if not ev.empty:
                parts.append(ev)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def timeframe_regime_profile(cells: pd.DataFrame) -> pd.DataFrame:
    """TF별 평균 regime profile."""
    rows = []
    for tf in GENERALIZATION_TIMEFRAMES:
        grp = cells[cells["timeframe"] == tf]
        row = {"timeframe": tf}
        for feat in REGIME_NUMERIC:
            vals = grp[feat].dropna() if feat in grp.columns else pd.Series(dtype=float)
            row[feat] = float(vals.mean()) if len(vals) else None
        rows.append(row)
    return pd.DataFrame(rows)


def compare_success_failure(cells: pd.DataFrame) -> List[dict]:
    """성공 vs 실패 셀 regime separator."""
    success = cells[cells["cell_success"] == True]
    failure = cells[cells["cell_success"] == False]
    results = []
    for feat in REGIME_NUMERIC:
        if feat not in cells.columns:
            continue
        a = success[feat].dropna()
        b = failure[feat].dropna()
        if a.empty and b.empty:
            continue
        results.append({
            "feature": feat,
            "success_avg": float(a.mean()) if len(a) else None,
            "failure_avg": float(b.mean()) if len(b) else None,
            "effect_size": effect_size(a, b) if len(a) and len(b) else 0.0,
        })
    return sorted(results, key=lambda x: x["effect_size"], reverse=True)


def build_cluster_table(events: pd.DataFrame) -> List[dict]:
    """VOL × TREND bucket별 expectancy."""
    if events.empty:
        return []
    linked = events.dropna(subset=["return_pct", "atr_pct"])
    if linked.empty:
        return []

    q33 = float(linked["atr_pct"].quantile(0.33))
    q66 = float(linked["atr_pct"].quantile(0.66))

    rows: List[dict] = []
    for _, ev in linked.iterrows():
        vol = _vol_bucket(float(ev["atr_pct"]), q33, q66)
        trend = _trend_bucket(ev.get("ema20_slope_3"), ev.get("ema60_slope_3"))
        rows.append({
            "vol_cluster": vol,
            "trend_cluster": trend,
            "cluster": f"{vol}|{trend}",
            "return_pct": float(ev["return_pct"]),
        })

    cdf = pd.DataFrame(rows)
    out = []
    for cluster, grp in cdf.groupby("cluster"):
        rets = grp["return_pct"]
        n = len(rets)
        wins = (rets > 0).sum()
        out.append({
            "cluster": cluster,
            "n": n,
            "win_rate": wins / n * 100.0 if n else 0.0,
            "expectancy": float(rets.mean()) if n else None,
        })
    return sorted(out, key=lambda x: x.get("expectancy") or -999.0, reverse=True)


def symbol_regime_comparison(cells: pd.DataFrame) -> Dict[str, dict]:
    """심볼별 RULE_B 셀 regime 요약."""
    out = {}
    for sym in GENERALIZATION_SYMBOLS:
        grp = cells[cells["symbol"] == sym]
        if grp.empty:
            out[sym] = {"cells": 0, "success_cells": 0, "avg_expectancy": None}
            continue
        out[sym] = {
            "cells": len(grp),
            "success_cells": int((grp["cell_success"] == True).sum()),
            "avg_expectancy": float(grp["expectancy"].dropna().mean()) if grp["expectancy"].notna().any() else None,
            "avg_atr_pct": float(grp["atr_pct"].dropna().mean()) if grp["atr_pct"].notna().any() else None,
            "avg_major_k": float(grp["major_k"].dropna().mean()) if grp["major_k"].notna().any() else None,
        }
    return out


def summarize_regime_analysis(rule: str = "RULE_B") -> dict:
    """REPORT용 전체 요약."""
    cells = build_cell_regimes(rule)
    if cells.empty:
        return {"rule": rule, "count": 0}

    tf_profile = timeframe_regime_profile(cells)
    separators = compare_success_failure(cells)

    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    events = _collect_events(rule, pipeline_cache)
    clusters = build_cluster_table(events)

    tf_4h = cells[cells["timeframe"] == "4h"]
    tf_1d = cells[cells["timeframe"] == "1d"]
    sep_4h_1d = []
    for feat in REGIME_NUMERIC:
        if feat not in cells.columns:
            continue
        a = tf_4h[feat].dropna()
        b = tf_1d[feat].dropna()
        if a.empty and b.empty:
            continue
        sep_4h_1d.append({
            "feature": feat,
            "avg_4h": float(a.mean()) if len(a) else None,
            "avg_1d": float(b.mean()) if len(b) else None,
            "effect_size": effect_size(a, b) if len(a) and len(b) else 0.0,
        })
    sep_4h_1d = sorted(sep_4h_1d, key=lambda x: x["effect_size"], reverse=True)

    success_cells = cells[cells["cell_success"] == True]
    failure_cells = cells[cells["cell_success"] == False]

    return {
        "rule": rule,
        "count": len(cells),
        "success_cell_count": len(success_cells),
        "failure_cell_count": len(failure_cells),
        "cells": cells,
        "timeframe_profile": tf_profile,
        "separators": separators[:20],
        "separators_4h_vs_1d": sep_4h_1d[:20],
        "clusters": clusters,
        "best_cluster": clusters[0] if clusters else {},
        "worst_cluster": clusters[-1] if clusters else {},
        "symbol_comparison": symbol_regime_comparison(cells),
        "rule_b_alive": success_cells.to_dict("records"),
        "rule_b_dead": failure_cells.to_dict("records"),
    }


def build_full_regime_report() -> dict:
    """RULE_A/B/D 비교 포함 전체 report payload."""
    primary = summarize_regime_analysis("RULE_B")
    comparisons = {
        r: summarize_regime_analysis(r)
        for r in REGIME_RULES
    }
    return {
        "primary": primary,
        "by_rule": comparisons,
    }
