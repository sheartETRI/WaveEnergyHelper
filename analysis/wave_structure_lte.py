"""Wave Structure LTE — 장기 MA 구조 내 Structure Recovery 관측.

Structure Confirmation/Expectancy 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
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
from analysis.wave_volume_energy import _load_ohlcv

MA_PERIODS = (120, 240, 480, 960)
SLOPE_LOOKBACK = 5
STRUCTURE_MIN = 3

COMPARE_FEATURES = (
    "lte_position_score",
    "price_vs_ma120", "price_vs_ma240", "price_vs_ma480", "price_vs_ma960",
    "ma120_slope", "ma240_slope", "ma480_slope", "ma960_slope",
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "success", "return_pct",
    "ma120_slope", "ma240_slope", "ma480_slope", "ma960_slope",
    "price_vs_ma120", "price_vs_ma240", "price_vs_ma480", "price_vs_ma960",
    "lte_position_score", "structure_score", "hh",
    "energy_score", "money_flow_score", "wave_state", "branch", "path",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def compute_ma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=max(1, period // 2)).mean()


def compute_ma_slope(ma: pd.Series, lookback: int = SLOPE_LOOKBACK) -> pd.Series:
    return ma - ma.shift(lookback)


def compute_price_vs_ma(close: pd.Series, ma: pd.Series) -> pd.Series:
    return (close - ma) / ma.replace(0, np.nan) * 100.0


def compute_lte_position_score(hh: bool, price_below: dict) -> int:
    """HH 발생 * price < MA240/480/960 위치 점수 (0~4)."""
    score = 0
    if hh:
        score += 1
    for p in (240, 480, 960):
        if price_below.get(p):
            score += 1
    return score


def add_lte_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame()
    out = ohlcv.copy()
    close = out["close"]
    for p in MA_PERIODS:
        ma_col = f"ma{p}"
        out[ma_col] = compute_ma(close, p)
        out[f"ma{p}_slope"] = compute_ma_slope(out[ma_col])
        out[f"price_vs_ma{p}"] = compute_price_vs_ma(close, out[ma_col])
        out[f"price_below_ma{p}"] = close < out[ma_col]
    return out


def extract_lte_at(df: pd.DataFrame, pos: int, hh: bool) -> dict:
    if pos < 0 or pos >= len(df):
        return {}
    row = df.iloc[pos]
    price_below = {}
    feats: dict = {"hh": hh}
    for p in MA_PERIODS:
        slope = row.get(f"ma{p}_slope")
        pvm = row.get(f"price_vs_ma{p}")
        below = row.get(f"price_below_ma{p}")
        feats[f"ma{p}_slope"] = float(slope) if pd.notna(slope) else None
        feats[f"price_vs_ma{p}"] = float(pvm) if pd.notna(pvm) else None
        feats[f"price_below_ma{p}"] = bool(below) if pd.notna(below) else False
        price_below[p] = feats[f"price_below_ma{p}"]
    feats["lte_position_score"] = compute_lte_position_score(hh, price_below)
    return feats


def _load_base_events() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_structure_confirmation.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["timestamp"])
    vol_path = os.path.join(_validation_dir(), "wave_volume_energy.csv")
    if os.path.isfile(vol_path):
        vol = pd.read_csv(vol_path, parse_dates=["timestamp"])
        if "timeframe" in vol.columns:
            tf_map = vol.set_index(["timestamp", "symbol"])["timeframe"].to_dict()
            df["timeframe"] = df.apply(
                lambda r: tf_map.get((pd.Timestamp(r["timestamp"]), r["symbol"]), "4h"),
                axis=1,
            )
        else:
            df["timeframe"] = df["symbol"].map(
                {"ETHUSDT": "4h", "BTCUSDT": "1d", "SOLUSDT": "1h", "BNBUSDT": "4h"},
            ).fillna("4h")
    else:
        df["timeframe"] = "4h"
    for col in ("hh", "hl"):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].map(lambda x: str(x).lower() in ("true", "1", "yes"))
    return df


def _wave_matches(row: pd.Series, wave: str) -> bool:
    ws = str(row.get("wave_state", ""))
    br = str(row.get("branch", ""))
    path = str(row.get("path", ""))
    return ws == wave or br == wave or wave in path


def _is_tb_struct(row: pd.Series) -> bool:
    return _wave_matches(row, "TRIPLE_BOTTOM_REQUIRED") and int(row.get("structure_score", 0)) >= STRUCTURE_MIN


def build_lte_events(cache: Optional[Dict] = None) -> pd.DataFrame:
    base = _load_base_events()
    if base.empty:
        return pd.DataFrame()

    lte_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    rows: List[dict] = []

    for _, ev in base.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in lte_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            lte_cache[key] = add_lte_features(bare)
        lte_df = lte_cache[key]
        bar_idx = _find_bar_index(lte_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        hh = bool(ev.get("hh", False))
        feats = extract_lte_at(lte_df, bar_idx, hh)
        if not feats:
            continue
        rows.append({
            "timestamp": pd.Timestamp(ev["timestamp"]),
            "symbol": sym,
            "timeframe": tf,
            "success": bool(ev["success"]),
            "return_pct": float(ev["return_pct"]),
            "structure_score": int(ev["structure_score"]) if pd.notna(ev.get("structure_score")) else 0,
            "energy_score": int(ev.get("energy_score", 0)) if pd.notna(ev.get("energy_score")) else 0,
            "money_flow_score": int(ev.get("money_flow_score", 0)) if pd.notna(ev.get("money_flow_score")) else 0,
            "wave_state": str(ev.get("wave_state", "")),
            "branch": str(ev.get("branch", "")),
            "path": str(ev.get("path", "")),
            **feats,
        })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def success_failure_compare(df: pd.DataFrame) -> List[dict]:
    if df.empty:
        return []
    succ, fail = df[df["success"]], df[~df["success"]]
    rows = []
    for feat in COMPARE_FEATURES:
        if feat not in df.columns:
            continue
        s_vals = succ[feat].dropna().astype(float)
        f_vals = fail[feat].dropna().astype(float)
        if s_vals.empty and f_vals.empty:
            continue
        rows.append({
            "feature": feat,
            "success_mean": float(s_vals.mean()) if len(s_vals) else None,
            "failure_mean": float(f_vals.mean()) if len(f_vals) else None,
            "effect_size": effect_size(s_vals, f_vals) if len(s_vals) >= 2 and len(f_vals) >= 2 else None,
        })
    for p in MA_PERIODS:
        col = f"price_below_ma{p}"
        if col not in df.columns:
            continue
        s_rate = float(succ[col].mean()) * 100.0 if len(succ) else None
        f_rate = float(fail[col].mean()) * 100.0 if len(fail) else None
        rows.append({
            "feature": col,
            "success_mean": s_rate,
            "failure_mean": f_rate,
            "effect_size": abs((s_rate or 0) - (f_rate or 0)) / 100.0,
        })
    return sorted(rows, key=lambda x: x.get("effect_size") or 0, reverse=True)


def _combo_metrics(df: pd.DataFrame, mask: pd.Series, label: str) -> dict:
    sub = df[mask]
    if sub.empty:
        return {"combo": label, "n": 0, "win_rate": None, "expectancy": None, "profit_factor": None}
    m = compute_expectancy_metrics(sub["return_pct"])
    return {
        "combo": label,
        "n": m.get("n", 0),
        "win_rate": m.get("win_rate"),
        "expectancy": m.get("expectancy"),
        "profit_factor": m.get("profit_factor"),
    }


def tb_lte_combos(df: pd.DataFrame) -> List[dict]:
    tb = df[df.apply(_is_tb_struct, axis=1)]
    rows = [
        _combo_metrics(tb, tb["price_below_ma240"], "TB+Structure>=3 + price<MA240"),
        _combo_metrics(tb, tb["price_below_ma480"], "TB+Structure>=3 + price<MA480"),
        _combo_metrics(tb, tb["ma480_slope"] > 0, "TB+Structure>=3 + MA480_slope>0"),
        _combo_metrics(tb, tb["ma960_slope"] > 0, "TB+Structure>=3 + MA960_slope>0"),
        _combo_metrics(
            tb, (tb["ma480_slope"] > 0) & tb["price_below_ma480"],
            "TB+Structure>=3 + MA480_slope>0 + price<MA480",
        ),
        _combo_metrics(
            tb, tb["price_below_ma960"] if "price_below_ma960" in tb.columns else pd.Series(False, index=tb.index),
            "TB+Structure>=3 + price<MA960",
        ),
    ]
    return rows


def ma_position_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for p in MA_PERIODS:
        col = f"price_below_ma{p}"
        if col not in df.columns:
            continue
        for label, mask_val in [("below", True), ("above", False)]:
            mask = df[col] == mask_val
            m = _combo_metrics(df, mask, f"price_{label}_MA{p}")
            rows.append(m)
    return rows


def ma_slope_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for p in MA_PERIODS:
        col = f"ma{p}_slope"
        if col not in df.columns:
            continue
        for label, positive in [("up", True), ("down", False)]:
            mask = df[col] > 0 if positive else df[col] <= 0
            rows.append(_combo_metrics(df, mask, f"MA{p}_slope_{label}"))
    return rows


def wave3_lte_combos(df: pd.DataFrame) -> List[dict]:
    w3 = df[df.apply(lambda r: _wave_matches(r, "WAVE3_COMPLETED"), axis=1)]
    rows = [
        _combo_metrics(w3, pd.Series(True, index=w3.index), "WAVE3 + LTE (all)"),
        _combo_metrics(w3, w3["price_below_ma480"], "WAVE3 + price<MA480"),
        _combo_metrics(w3, w3["ma480_slope"] > 0, "WAVE3 + MA480_slope>0"),
        _combo_metrics(
            w3, (w3["ma480_slope"] > 0) & w3["price_below_ma480"],
            "WAVE3 + MA480_slope>0 + price<MA480",
        ),
    ]
    return rows


def final_tb_structure_lte(df: pd.DataFrame) -> dict:
    mask = df.apply(_is_tb_struct, axis=1) & (
        df["price_below_ma480"] & (df["ma480_slope"] > 0)
    )
    return _combo_metrics(df, mask, "TB + Structure>=3 + price<MA480 + MA480_slope>0")


def symbol_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in GENERALIZATION_SYMBOLS:
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "symbol": sym,
            "lte_position_score_avg": float(sub["lte_position_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
            "n": m.get("n", 0),
        })
    return rows


def timeframe_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for tf in GENERALIZATION_TIMEFRAMES:
        sub = df[df["timeframe"] == tf]
        if sub.empty:
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "timeframe": tf,
            "lte_position_score_avg": float(sub["lte_position_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
            "n": m.get("n", 0),
        })
    return rows


def build_lte_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    return df[cols].copy()


def full_lte_summary(cache: Optional[Dict] = None) -> dict:
    df = build_lte_events(cache)
    compare = success_failure_compare(df)
    return {
        "dataframe": build_lte_csv(df),
        "raw": df,
        "event_count": len(df),
        "feature_compare": compare,
        "top_separators": compare[:10],
        "ma_position_perf": ma_position_performance(df),
        "ma_slope_perf": ma_slope_performance(df),
        "tb_lte_combos": tb_lte_combos(df),
        "wave3_lte_combos": wave3_lte_combos(df),
        "final_combo": final_tb_structure_lte(df),
        "symbol_comparison": symbol_comparison(df),
        "timeframe_comparison": timeframe_comparison(df),
    }
