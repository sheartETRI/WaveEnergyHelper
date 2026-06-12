"""Wave Energy Divergence — OBV 에너지 다이버전스 관측.

Volume Energy/Branch/Path/Expectancy 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES
from analysis.wave_outcome import _find_bar_index
from analysis.wave_volume_energy import (
    _load_ohlcv,
    add_volume_features,
    compute_obv,
)

PIVOT_LOOKBACK = 5
PIVOT_LOOKFORWARD = 5
TIMING_OFFSETS = (-20, -10, -5, 0, 5, 10)

WAVE_DIV_COMBOS = (
    "TRIPLE_BOTTOM_REQUIRED",
    "WAVE3_COMPLETED",
    "DOUBLE_BOTTOM",
)

ENERGY_DIV_COMBOS = (
    ("energy_score>=3", "BULLISH_OBV_DIV"),
    ("energy_score<=1", "NO_DIV"),
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "price_ll", "obv_hl", "bullish_div", "bearish_div",
    "div_strength", "energy_score", "wave_state", "branch", "path",
    "success", "return_pct",
)

COMPARE_FEATURES = ("bullish_div", "bearish_div", "div_strength", "price_ll_pct", "obv_hl_pct")


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def find_pivot_lows(
    series: pd.Series,
    lookback: int = PIVOT_LOOKBACK,
    lookforward: int = PIVOT_LOOKFORWARD,
) -> List[Tuple[int, float]]:
    """Pivot low (lookback/lookforward)."""
    pivots: List[Tuple[int, float]] = []
    n = len(series)
    for i in range(lookback, n - lookforward):
        val = float(series.iloc[i])
        if pd.isna(val):
            continue
        before = series.iloc[i - lookback:i]
        after = series.iloc[i + 1: i + lookforward + 1]
        if val <= before.min() and val <= after.min():
            pivots.append((i, val))
    return pivots


def find_pivot_highs(
    series: pd.Series,
    lookback: int = PIVOT_LOOKBACK,
    lookforward: int = PIVOT_LOOKFORWARD,
) -> List[Tuple[int, float]]:
    pivots: List[Tuple[int, float]] = []
    n = len(series)
    for i in range(lookback, n - lookforward):
        val = float(series.iloc[i])
        if pd.isna(val):
            continue
        before = series.iloc[i - lookback:i]
        after = series.iloc[i + 1: i + lookforward + 1]
        if val >= before.max() and val >= after.max():
            pivots.append((i, val))
    return pivots


def _confirmed_pivots(pivots: List[Tuple[int, float]], pos: int) -> List[Tuple[int, float]]:
    return [(i, v) for i, v in pivots if i + PIVOT_LOOKFORWARD <= pos]


def detect_bullish_obv_div(
    pos: int,
    low: pd.Series,
    obv: pd.Series,
    price_lows: Optional[List[Tuple[int, float]]] = None,
) -> dict:
    """가격 Lower Low + OBV Higher Low → BULLISH_OBV_DIV."""
    if price_lows is None:
        price_lows = find_pivot_lows(low)
    confirmed = _confirmed_pivots(price_lows, pos)
    if len(confirmed) < 2:
        return _empty_div()

    i1, p1 = confirmed[-2]
    i2, p2 = confirmed[-1]
    o1 = float(obv.iloc[i1])
    o2 = float(obv.iloc[i2])
    if pd.isna(o1) or pd.isna(o2) or p1 == 0:
        return _empty_div()

    price_ll = p2 < p1
    obv_hl = o2 > o1
    bullish = price_ll and obv_hl

    price_ll_pct = (p1 - p2) / p1 * 100.0 if price_ll else 0.0
    obv_hl_pct = (o2 - o1) / abs(o1) * 100.0 if obv_hl else 0.0
    raw_strength = abs(price_ll_pct) * abs(obv_hl_pct) if bullish else 0.0

    return {
        "price_ll": price_ll,
        "obv_hl": obv_hl,
        "bullish_div": bullish,
        "bearish_div": False,
        "price_ll_pct": price_ll_pct if bullish else None,
        "obv_hl_pct": obv_hl_pct if bullish else None,
        "raw_strength": raw_strength,
        "div_strength": None,
    }


def detect_bearish_obv_div(
    pos: int,
    high: pd.Series,
    obv: pd.Series,
    price_highs: Optional[List[Tuple[int, float]]] = None,
) -> dict:
    """가격 Higher High + OBV Lower High → BEARISH_OBV_DIV."""
    if price_highs is None:
        price_highs = find_pivot_highs(high)
    confirmed = _confirmed_pivots(price_highs, pos)
    if len(confirmed) < 2:
        return {"bearish_div": False, "raw_strength": 0.0}

    i1, h1 = confirmed[-2]
    i2, h2 = confirmed[-1]
    o1 = float(obv.iloc[i1])
    o2 = float(obv.iloc[i2])
    if pd.isna(o1) or pd.isna(o2) or h1 == 0:
        return {"bearish_div": False, "raw_strength": 0.0}

    price_hh = h2 > h1
    obv_lh = o2 < o1
    bearish = price_hh and obv_lh
    return {"bearish_div": bearish, "raw_strength": 0.0}


def _empty_div() -> dict:
    return {
        "price_ll": False,
        "obv_hl": False,
        "bullish_div": False,
        "bearish_div": False,
        "price_ll_pct": None,
        "obv_hl_pct": None,
        "raw_strength": 0.0,
        "div_strength": None,
    }


def detect_divergence_at(
    pos: int,
    ohlcv: pd.DataFrame,
    obv: pd.Series,
    price_lows: Optional[List[Tuple[int, float]]] = None,
    price_highs: Optional[List[Tuple[int, float]]] = None,
) -> dict:
    bull = detect_bullish_obv_div(pos, ohlcv["low"], obv, price_lows)
    bear = detect_bearish_obv_div(pos, ohlcv["high"], obv, price_highs)
    if bear.get("bearish_div"):
        bull["bearish_div"] = True
    return bull


def normalize_strength(raw: float, raw_max: float) -> float:
    if raw_max <= 0 or raw <= 0:
        return 0.0
    return min(100.0, raw / raw_max * 100.0)


def compute_div_strength(price_ll_pct: float, obv_hl_pct: float) -> float:
    return abs(price_ll_pct) * abs(obv_hl_pct)


def _load_volume_energy_csv() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_volume_energy.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def _wave_matches(row: pd.Series, wave: str) -> bool:
    ws = str(row.get("wave_state", ""))
    br = str(row.get("branch", ""))
    path = str(row.get("path", ""))
    if wave == "DOUBLE_BOTTOM":
        return "DOUBLE_BOTTOM" in ws or "DOUBLE_BOTTOM" in br or "DOUBLE_BOTTOM" in path
    return ws == wave or br == wave or wave in path


def build_divergence_events(cache: Optional[Dict] = None) -> pd.DataFrame:
    base = _load_volume_energy_csv()
    if base.empty:
        return pd.DataFrame()

    ohlcv_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    pivot_cache: Dict[Tuple[str, str], Tuple] = {}
    rows: List[dict] = []

    for _, ev in base.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in ohlcv_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            vol_df = add_volume_features(bare)
            ohlcv_cache[key] = vol_df
            pivot_cache[key] = (
                find_pivot_lows(vol_df["low"]),
                find_pivot_highs(vol_df["high"]),
            )
        vol_df = ohlcv_cache[key]
        price_lows, price_highs = pivot_cache[key]
        obv = vol_df["obv"]

        bar_idx = _find_bar_index(vol_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue

        div = detect_divergence_at(bar_idx, vol_df, obv, price_lows, price_highs)
        rows.append({
            "timestamp": pd.Timestamp(ev["timestamp"]),
            "symbol": sym,
            "timeframe": tf,
            "success": bool(ev["success"]),
            "return_pct": float(ev["return_pct"]),
            "energy_score": int(ev["energy_score"]) if pd.notna(ev.get("energy_score")) else 0,
            "wave_state": str(ev.get("wave_state", "")),
            "branch": str(ev.get("branch", "")),
            "path": str(ev.get("path", "")),
            **div,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    raw_max = float(df["raw_strength"].max()) if df["raw_strength"].max() > 0 else 1.0
    df["div_strength"] = df["raw_strength"].apply(lambda r: normalize_strength(r, raw_max))
    return df


def bullish_div_rate(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df["bullish_div"].sum()) / len(df) * 100.0


def success_failure_divergence_compare(df: pd.DataFrame) -> List[dict]:
    if df.empty:
        return []
    succ = df[df["success"]]
    fail = df[~df["success"]]
    rows = []

    s_rate = float(succ["bullish_div"].mean()) * 100.0 if len(succ) else 0.0
    f_rate = float(fail["bullish_div"].mean()) * 100.0 if len(fail) else 0.0
    rows.append({
        "metric": "bullish_div_rate",
        "success": s_rate,
        "failure": f_rate,
        "effect_size": abs(s_rate - f_rate) / 100.0,
    })

    for feat in ("div_strength", "price_ll_pct", "obv_hl_pct"):
        if feat not in df.columns:
            continue
        s_vals = succ[feat].dropna().astype(float)
        f_vals = fail[feat].dropna().astype(float)
        if s_vals.empty and f_vals.empty:
            continue
        rows.append({
            "metric": feat,
            "success": float(s_vals.mean()) if len(s_vals) else None,
            "failure": float(f_vals.mean()) if len(f_vals) else None,
            "effect_size": effect_size(s_vals, f_vals) if len(s_vals) >= 2 and len(f_vals) >= 2 else None,
        })
    return sorted(rows, key=lambda x: x.get("effect_size") or 0, reverse=True)


def top_divergence_separators(compare_rows: List[dict], top_n: int = 10) -> List[dict]:
    return compare_rows[:top_n]


def wave_divergence_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for wave in WAVE_DIV_COMBOS:
        mask = df.apply(lambda r: _wave_matches(r, wave) and r["bullish_div"], axis=1)
        sub = df[mask]
        label = f"{wave} + BULLISH_OBV_DIV"
        if sub.empty:
            rows.append({
                "combo": label, "n": 0, "win_rate": None,
                "expectancy": None, "profit_factor": None,
            })
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "combo": label,
            "n": metrics.get("n", 0),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "profit_factor": metrics.get("profit_factor"),
        })
    return rows


def energy_divergence_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for cond, div_label in ENERGY_DIV_COMBOS:
        if cond == "energy_score>=3":
            mask = (df["energy_score"] >= 3) & df["bullish_div"]
            label = f"Energy Score >= 3 + BULLISH_OBV_DIV"
        else:
            mask = (df["energy_score"] <= 1) & (~df["bullish_div"])
            label = "Energy Score <= 1 + NO_DIV"
        sub = df[mask]
        if sub.empty:
            rows.append({"combo": label, "n": 0, "win_rate": None, "expectancy": None})
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "combo": label,
            "n": metrics.get("n", 0),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "profit_factor": metrics.get("profit_factor"),
        })
    return rows


def divergence_timing(df: pd.DataFrame, ohlcv_cache: Optional[Dict] = None) -> List[dict]:
    """이벤트 offset별 bullish div 발생률."""
    ohlcv_cache = ohlcv_cache or {}
    pivot_cache: Dict = {}
    counts: Dict[int, List[bool]] = {o: [] for o in TIMING_OFFSETS}

    for _, ev in df.iterrows():
        sym, tf = str(ev["symbol"]), str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in ohlcv_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            vol_df = add_volume_features(bare)
            ohlcv_cache[key] = vol_df
            pivot_cache[key] = (
                find_pivot_lows(vol_df["low"]),
                find_pivot_highs(vol_df["high"]),
            )
        vol_df = ohlcv_cache[key]
        bar_idx = _find_bar_index(vol_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        pl, ph = pivot_cache[key]
        obv = vol_df["obv"]
        for offset in TIMING_OFFSETS:
            pos = bar_idx + offset
            if pos < 0 or pos >= len(vol_df):
                continue
            div = detect_divergence_at(pos, vol_df, obv, pl, ph)
            counts[offset].append(bool(div["bullish_div"]))

    rows = []
    for offset in TIMING_OFFSETS:
        vals = counts[offset]
        rows.append({
            "offset": offset,
            "div_rate": float(np.mean(vals)) * 100.0 if vals else None,
            "n": len(vals),
        })
    return rows


def failure_reclassification(df: pd.DataFrame) -> List[dict]:
    fails = df[~df["success"]]
    if fails.empty:
        return []
    total = len(fails)
    no_bull = ~fails["bullish_div"]
    return [
        {"cause": "NO_BULLISH_DIV", "count": int(no_bull.sum()),
         "pct": float(no_bull.sum()) / total * 100.0},
        {"cause": "HAS_BULLISH_DIV", "count": int((~no_bull).sum()),
         "pct": float((~no_bull).sum()) / total * 100.0},
    ]


def symbol_divergence_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in GENERALIZATION_SYMBOLS:
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "symbol": sym,
            "div_rate": bullish_div_rate(sub),
            "expectancy": metrics.get("expectancy"),
            "win_rate": metrics.get("win_rate"),
            "n": metrics.get("n", 0),
        })
    return rows


def build_divergence_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    out = df[cols].copy()
    out["bullish_div"] = out["bullish_div"].map(
        lambda x: "BULLISH_OBV_DIV" if x else "",
    )
    out["bearish_div"] = out["bearish_div"].map(
        lambda x: "BEARISH_OBV_DIV" if x else "",
    )
    return out


def full_divergence_summary(cache: Optional[Dict] = None) -> dict:
    df = build_divergence_events(cache)
    compare = success_failure_divergence_compare(df)
    return {
        "dataframe": build_divergence_csv(df),
        "raw": df,
        "event_count": len(df),
        "bullish_div_rate": bullish_div_rate(df),
        "success_div_rate": float(df[df["success"]]["bullish_div"].mean()) * 100.0 if not df.empty else 0.0,
        "failure_div_rate": float(df[~df["success"]]["bullish_div"].mean()) * 100.0 if not df.empty else 0.0,
        "feature_compare": compare,
        "top_separators": top_divergence_separators(compare),
        "wave_div_combos": wave_divergence_combos(df),
        "energy_div_combos": energy_divergence_combos(df),
        "timing": divergence_timing(df),
        "failure_reclass": failure_reclassification(df),
        "symbol_comparison": symbol_divergence_comparison(df),
    }
