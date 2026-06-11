"""Wave Confluence — MACD/RSI/EMA/변동성 다중지표 Confluence 관측.

기존 Branch/Expectancy/Exit 산출물만 소비. ML·신호 생성 없음.
"""
from __future__ import annotations

import math
import os
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import BRANCH_COMPLETED, BRANCH_REQUIRED, effect_size
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_exit import POLICY_A
from analysis.wave_outcome import _find_bar_index
from analysis.wave_segmentation import MIN_SAMPLE

SUCCESS_COHORT = "SUCCESS"
FAILURE_COHORT = "FAILURE"

SCORE_FLAGS = (
    "MACD_GC_RECENT",
    "RSI_RECOVERING",
    "EMA20_GT_60",
    "PRICE_ABOVE_60",
    "TRIPLE_BOTTOM_REQUIRED",
)

BUNDLE_DIMS = (
    "branch_label",
    "MACD_GC_RECENT",
    "MACD_DC_RECENT",
    "MACD_ABOVE_ZERO",
    "HIST_RISING",
    "RSI_RECOVERING",
    "RSI_OVERSOLD",
    "RSI_CROSS_50_RECENT",
    "rsi_bucket",
    "PRICE_ABOVE_20",
    "PRICE_ABOVE_60",
    "EMA20_GT_60",
    "EMA60_GT_120",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _rsi_bucket(rsi: float) -> str:
    if rsi is None or (isinstance(rsi, float) and math.isnan(rsi)):
        return "unknown"
    if rsi < 30:
        return "<30"
    if rsi < 40:
        return "30-40"
    if rsi < 50:
        return "40-50"
    if rsi < 60:
        return "50-60"
    if rsi < 70:
        return "60-70"
    return "70+"


def _cross_recent(series: pd.Series, other: pd.Series, pos: int, window: int = 5) -> bool:
    start = max(1, pos - window + 1)
    for i in range(start, pos + 1):
        if pd.isna(series.iloc[i]) or pd.isna(other.iloc[i]):
            continue
        if pd.isna(series.iloc[i - 1]) or pd.isna(other.iloc[i - 1]):
            continue
        if series.iloc[i - 1] <= other.iloc[i - 1] and series.iloc[i] > other.iloc[i]:
            return True
    return False


def _cross_below_recent(series: pd.Series, other: pd.Series, pos: int, window: int = 5) -> bool:
    start = max(1, pos - window + 1)
    for i in range(start, pos + 1):
        if pd.isna(series.iloc[i]) or pd.isna(other.iloc[i]):
            continue
        if pd.isna(series.iloc[i - 1]) or pd.isna(other.iloc[i - 1]):
            continue
        if series.iloc[i - 1] >= other.iloc[i - 1] and series.iloc[i] < other.iloc[i]:
            return True
    return False


def _level_cross_recent(series: pd.Series, level: float, pos: int, window: int = 5) -> bool:
    start = max(1, pos - window + 1)
    for i in range(start, pos + 1):
        if pd.isna(series.iloc[i]) or pd.isna(series.iloc[i - 1]):
            continue
        if series.iloc[i - 1] < level <= series.iloc[i]:
            return True
        if series.iloc[i - 1] > level >= series.iloc[i]:
            return True
    return False


def add_confluence_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """MACD/RSI/EMA/ATR/변동성 컬럼 추가 (12,26,9 MACD / RSI14)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    close = out["close"]

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["macd_gap"] = out["macd"] - out["macd_signal"]
    out["macd_hist_prev"] = out["macd_hist"].shift(1)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    out["rsi"] = (100 - (100 / (1 + rs))).fillna(100)
    out["rsi_slope_1"] = out["rsi"].diff(1)
    out["rsi_slope_3"] = out["rsi"] - out["rsi"].shift(3)

    for span, col in ((20, "ema20"), (60, "ema60"), (120, "ema120")):
        out[col] = close.ewm(span=span, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat([
        (out["high"] - out["low"]).abs(),
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr14"] = tr.ewm(span=14, adjust=False).mean()
    out["atr_pct"] = out["atr14"] / close * 100.0
    out["volatility_20"] = close.pct_change().rolling(20).std() * 100.0

    return out


def extract_confluence_at(df: pd.DataFrame, pos: int) -> dict:
    """단일 봉 Confluence feature."""
    row = df.iloc[pos]
    close = float(row["close"])
    macd = float(row["macd"]) if pd.notna(row.get("macd")) else None
    sig = float(row["macd_signal"]) if pd.notna(row.get("macd_signal")) else None
    hist = float(row["macd_hist"]) if pd.notna(row.get("macd_hist")) else None
    hist_prev = float(row["macd_hist_prev"]) if pd.notna(row.get("macd_hist_prev")) else None
    rsi = float(row["rsi"]) if pd.notna(row.get("rsi")) else None

    ema20 = float(row["ema20"]) if pd.notna(row.get("ema20")) else None
    ema60 = float(row["ema60"]) if pd.notna(row.get("ema60")) else None
    ema120 = float(row["ema120"]) if pd.notna(row.get("ema120")) else None

    feats = {
        "macd": macd,
        "macd_signal": sig,
        "macd_hist": hist,
        "macd_gap": (macd - sig) if macd is not None and sig is not None else None,
        "macd_gc_recent": _cross_recent(df["macd"], df["macd_signal"], pos),
        "macd_dc_recent": _cross_below_recent(df["macd"], df["macd_signal"], pos),
        "macd_above_zero": macd is not None and macd > 0,
        "macd_below_zero": macd is not None and macd < 0,
        "hist_rising": hist is not None and hist_prev is not None and hist > hist_prev,
        "hist_falling": hist is not None and hist_prev is not None and hist < hist_prev,
        "rsi": rsi,
        "rsi_slope_1": float(row["rsi_slope_1"]) if pd.notna(row.get("rsi_slope_1")) else None,
        "rsi_slope_3": float(row["rsi_slope_3"]) if pd.notna(row.get("rsi_slope_3")) else None,
        "rsi_bucket": _rsi_bucket(rsi),
        "rsi_recovering": (
            rsi is not None
            and pd.notna(row.get("rsi_slope_1"))
            and float(row["rsi_slope_1"]) > 0
            and rsi < 60
        ),
        "rsi_overbought": rsi is not None and rsi >= 70,
        "rsi_oversold": rsi is not None and rsi <= 30,
        "rsi_cross_50_recent": _level_cross_recent(df["rsi"], 50.0, pos),
        "ema20": ema20,
        "ema60": ema60,
        "ema120": ema120,
        "price_above_20": ema20 is not None and close > ema20,
        "price_above_60": ema60 is not None and close > ema60,
        "ema20_gt_60": ema20 is not None and ema60 is not None and ema20 > ema60,
        "ema60_gt_120": ema60 is not None and ema120 is not None and ema60 > ema120,
        "atr14": float(row["atr14"]) if pd.notna(row.get("atr14")) else None,
        "atr_pct": float(row["atr_pct"]) if pd.notna(row.get("atr_pct")) else None,
        "volatility_20": float(row["volatility_20"]) if pd.notna(row.get("volatility_20")) else None,
    }

    feats["MACD_GC_RECENT"] = feats["macd_gc_recent"]
    feats["MACD_DC_RECENT"] = feats["macd_dc_recent"]
    feats["MACD_ABOVE_ZERO"] = feats["macd_above_zero"]
    feats["MACD_BELOW_ZERO"] = feats["macd_below_zero"]
    feats["HIST_RISING"] = feats["hist_rising"]
    feats["HIST_FALLING"] = feats["hist_falling"]
    feats["RSI_RECOVERING"] = feats["rsi_recovering"]
    feats["RSI_OVERBOUGHT"] = feats["rsi_overbought"]
    feats["RSI_OVERSOLD"] = feats["rsi_oversold"]
    feats["RSI_CROSS_50_RECENT"] = feats["rsi_cross_50_recent"]
    feats["PRICE_ABOVE_20"] = feats["price_above_20"]
    feats["PRICE_ABOVE_60"] = feats["price_above_60"]
    feats["EMA20_GT_60"] = feats["ema20_gt_60"]
    feats["EMA60_GT_120"] = feats["ema60_gt_120"]

    return feats


def confluence_score(row: pd.Series) -> int:
    score = 0
    if bool(row.get("MACD_GC_RECENT")):
        score += 1
    if bool(row.get("RSI_RECOVERING")):
        score += 1
    if bool(row.get("EMA20_GT_60")):
        score += 1
    if bool(row.get("PRICE_ABOVE_60")):
        score += 1
    if str(row.get("branch")) == BRANCH_REQUIRED:
        score += 1
    return score


def _assign_cohort(row: pd.Series, symbol: str) -> str:
    branch = str(row.get("branch", ""))
    success = row.get("success")
    if isinstance(success, str):
        success = success.lower() in ("true", "1", "yes")
    if symbol == "ETHUSDT":
        if branch == BRANCH_REQUIRED and success:
            return SUCCESS_COHORT
        if branch == BRANCH_COMPLETED and not success:
            return FAILURE_COHORT
        return "OTHER"
    if pd.notna(row.get("return_pct")):
        return SUCCESS_COHORT if success else FAILURE_COHORT
    return "OTHER"


def build_confluence(
    symbol: str,
    interval: str,
    ohlcv: pd.DataFrame,
    pipeline_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    branch_path = _csv_path("wave_branch", symbol, interval)
    if not os.path.isfile(branch_path):
        return pd.DataFrame()

    branch = pd.read_csv(branch_path, parse_dates=["timestamp"])
    base = pipeline_df if pipeline_df is not None else ohlcv
    enriched = add_confluence_indicators(base.copy())

    rows: List[dict] = []
    for _, br in branch.iterrows():
        ts = pd.Timestamp(br["timestamp"])
        pos = _find_bar_index(ohlcv, ts)
        if pos is None or pos >= len(enriched):
            continue
        cf = extract_confluence_at(enriched, pos)
        success = br.get("success")
        if isinstance(success, str):
            success = success.lower() in ("true", "1", "yes")
        row = {
            "timestamp": ts,
            "branch": br.get("branch"),
            "branch_label": str(br.get("branch")),
            "return_pct": br.get("return_pct"),
            "success": success,
            "cohort": "",
            **cf,
        }
        row["cohort"] = _assign_cohort(pd.Series(row), symbol)
        row["confluence_score"] = confluence_score(pd.Series(row))
        rows.append(row)

    return pd.DataFrame(rows)


def _success_lift(df: pd.DataFrame, col: str, val) -> dict:
    linked = df.dropna(subset=["return_pct"])
    if linked.empty:
        return {}
    base = linked["success"].mean()
    if base == 0:
        return {}
    mask = linked[col] == val if not isinstance(val, bool) else linked[col] == val
    grp = linked[mask]
    if grp.empty:
        return {}
    rate = grp["success"].mean()
    return {
        "feature": col,
        "value": str(val),
        "n": len(grp),
        "success_rate": rate * 100.0,
        "lift": rate / base if base else 0.0,
    }


def _bool_lift(df: pd.DataFrame, col: str) -> Optional[dict]:
    if col not in df.columns:
        return None
    for val in (True, False):
        r = _success_lift(df, col, val)
        if r and r["n"] >= 1:
            return {**r, "label": f"{col}={val}"}
    return None


def _compare_numeric(success: pd.DataFrame, failure: pd.DataFrame, col: str) -> dict:
    a = success[col].dropna()
    b = failure[col].dropna()
    return {
        "feature": col,
        "success_avg": float(a.mean()) if len(a) else None,
        "success_median": float(a.median()) if len(a) else None,
        "failure_avg": float(b.mean()) if len(b) else None,
        "failure_median": float(b.median()) if len(b) else None,
        "effect_size": effect_size(a, b) if len(a) and len(b) else 0.0,
    }


NUMERIC_CONFLUENCE = (
    "macd", "macd_signal", "macd_hist", "macd_gap",
    "rsi", "rsi_slope_1", "rsi_slope_3",
    "ema20", "ema60", "ema120",
    "atr14", "atr_pct", "volatility_20",
)

BOOL_CONFLUENCE = (
    "MACD_GC_RECENT", "MACD_DC_RECENT", "MACD_ABOVE_ZERO", "MACD_BELOW_ZERO",
    "HIST_RISING", "HIST_FALLING",
    "RSI_RECOVERING", "RSI_OVERBOUGHT", "RSI_OVERSOLD", "RSI_CROSS_50_RECENT",
    "PRICE_ABOVE_20", "PRICE_ABOVE_60", "EMA20_GT_60", "EMA60_GT_120",
)

CAT_CONFLUENCE = ("rsi_bucket",)


def _bundle_combos(df: pd.DataFrame) -> List[dict]:
    linked = df.dropna(subset=["return_pct"])
    if linked.empty:
        return []
    dims = {k: linked[k] for k in BUNDLE_DIMS if k in linked.columns}
    results: List[dict] = []

    def _add(mask: pd.Series, label: str) -> None:
        grp = linked[mask]
        n = len(grp)
        if n < MIN_SAMPLE:
            return
        m = compute_expectancy_metrics(grp["return_pct"])
        results.append({
            "bundle": label,
            "n": n,
            "win": m.get("win", 0),
            "win_rate": m.get("win_rate", 0),
            "expectancy": m.get("expectancy", 0),
        })

    cols = list(dims.keys())
    for k1, k2 in combinations(cols, 2):
        for v1 in linked[k1].dropna().unique():
            for v2 in linked[linked[k1] == v1][k2].dropna().unique():
                mask = (linked[k1] == v1) & (linked[k2] == v2)
                _add(mask, f"{k1}={v1} & {k2}={v2}")

    return sorted(results, key=lambda x: x["expectancy"], reverse=True)


def summarize_confluence(df: pd.DataFrame, symbol: str = "ETHUSDT") -> dict:
    if df.empty:
        return {"count": 0}

    success = df[df["cohort"] == SUCCESS_COHORT]
    failure = df[df["cohort"] == FAILURE_COHORT]
    linked = df.dropna(subset=["return_pct"])

    numeric_cmp = [
        _compare_numeric(success, failure, c)
        for c in NUMERIC_CONFLUENCE if c in df.columns
    ]
    numeric_cmp = [x for x in numeric_cmp if x["success_avg"] is not None or x["failure_avg"] is not None]

    cat_lifts: List[dict] = []
    for col in BOOL_CONFLUENCE + CAT_CONFLUENCE:
        if col not in df.columns:
            continue
        if col in CAT_CONFLUENCE:
            base = linked["success"].mean() if not linked.empty else 0
            for val, grp in linked.groupby(col):
                if len(grp) < 1 or base == 0:
                    continue
                rate = grp["success"].mean()
                cat_lifts.append({
                    "feature": col,
                    "value": str(val),
                    "label": f"{col}={val}",
                    "n": len(grp),
                    "success_rate": rate * 100.0,
                    "lift": rate / base,
                })
        else:
            for val in (True, False):
                r = _success_lift(linked, col, val)
                if r:
                    r["label"] = f"{col}={val}"
                    cat_lifts.append(r)

    factors: List[dict] = []
    for n in numeric_cmp:
        factors.append({**n, "label": n["feature"], "kind": "numeric", "score": n["effect_size"]})
    for c in cat_lifts:
        factors.append({**c, "kind": "categorical", "score": c["lift"]})

    top_factors = sorted(factors, key=lambda x: x["score"], reverse=True)[:20]
    bundles = _bundle_combos(df)

    score_rows = []
    for sc, grp in linked.groupby("confluence_score"):
        m = compute_expectancy_metrics(grp["return_pct"])
        score_rows.append({
            "score": int(sc),
            "count": len(grp),
            "win_rate": m.get("win_rate", 0),
            "expectancy": m.get("expectancy", 0),
        })
    score_rows.sort(key=lambda x: x["score"])

    macd_cmp = [x for x in numeric_cmp if x["feature"].startswith("macd")]
    rsi_cmp = [x for x in numeric_cmp if x["feature"].startswith("rsi")]
    ema_cmp = [x for x in numeric_cmp if x["feature"].startswith("ema")]

    return {
        "count": len(df),
        "success_count": len(success),
        "failure_count": len(failure),
        "numeric_comparison": numeric_cmp,
        "categorical_lift": cat_lifts,
        "top_confluence_factors": top_factors,
        "top_confluence_bundles": bundles[:20],
        "score_summary": score_rows,
        "macd_comparison": macd_cmp,
        "rsi_comparison": rsi_cmp,
        "ema_comparison": ema_cmp,
    }
