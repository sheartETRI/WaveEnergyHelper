"""Wave Money Flow — MFI/CMF/AD 기반 자금 유입 관측.

Volume Energy/Divergence/Expectancy 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_generalization import GENERALIZATION_SYMBOLS
from analysis.wave_outcome import _find_bar_index
from analysis.wave_volume_energy import _load_ohlcv

TIMING_OFFSETS = (-20, -10, -5, 0, 5, 10)

COMPARE_FEATURES = (
    "mfi", "cmf", "ad_slope_5", "ad_slope_10", "money_flow_score",
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "success", "return_pct",
    "mfi", "cmf", "ad_line", "ad_slope_5", "ad_slope_10",
    "money_flow_score", "energy_score", "bullish_div",
    "wave_state", "branch", "path",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def compute_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 14,
) -> pd.Series:
    tp = (high + low + close) / 3.0
    raw_mf = tp * volume
    diff = tp.diff()
    pos_mf = raw_mf.where(diff > 0, 0.0)
    neg_mf = raw_mf.where(diff < 0, 0.0)
    pos_sum = pos_mf.rolling(period, min_periods=period).sum()
    neg_sum = neg_mf.rolling(period, min_periods=period).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + mfr))


def compute_cmf(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    hl_range = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / hl_range
    mfv = mfm * volume
    vol_sum = volume.rolling(period, min_periods=1).sum()
    return mfv.rolling(period, min_periods=1).sum() / vol_sum.replace(0, np.nan)


def compute_ad_line(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    hl_range = (high - low).replace(0, np.nan)
    clv = ((close - low) - (high - close)) / hl_range
    return (clv * volume).fillna(0).cumsum()


def compute_ad_slope(ad: pd.Series, n: int) -> pd.Series:
    return ad - ad.shift(n)


def add_money_flow_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv is None or ohlcv.empty or "volume" not in ohlcv.columns:
        return pd.DataFrame()
    out = ohlcv.copy()
    h, l, c, v = out["high"], out["low"], out["close"], out["volume"]
    out["mfi"] = compute_mfi(h, l, c, v, 14)
    out["cmf"] = compute_cmf(h, l, c, v, 20)
    out["ad_line"] = compute_ad_line(h, l, c, v)
    out["ad_slope_5"] = compute_ad_slope(out["ad_line"], 5)
    out["ad_slope_10"] = compute_ad_slope(out["ad_line"], 10)
    out["mfi_slope_1"] = out["mfi"].diff(1)
    return out


def compute_money_flow_score(feats: dict) -> int:
    score = 0
    mfi = feats.get("mfi")
    if mfi is not None and mfi > 50:
        score += 1
    cmf = feats.get("cmf")
    if cmf is not None and cmf > 0:
        score += 1
    ad5 = feats.get("ad_slope_5")
    if ad5 is not None and ad5 > 0:
        score += 1
    ad10 = feats.get("ad_slope_10")
    if ad10 is not None and ad10 > 0:
        score += 1
    mfi_rise = feats.get("mfi_rising")
    if mfi_rise:
        score += 1
    return score


def extract_money_flow_at(df: pd.DataFrame, pos: int) -> dict:
    if pos < 0 or pos >= len(df):
        return {}
    row = df.iloc[pos]
    mfi = float(row["mfi"]) if pd.notna(row.get("mfi")) else None
    mfi_prev = float(df["mfi"].iloc[pos - 1]) if pos > 0 and pd.notna(df["mfi"].iloc[pos - 1]) else None
    feats = {
        "mfi": mfi,
        "cmf": float(row["cmf"]) if pd.notna(row.get("cmf")) else None,
        "ad_line": float(row["ad_line"]) if pd.notna(row.get("ad_line")) else None,
        "ad_slope_5": float(row["ad_slope_5"]) if pd.notna(row.get("ad_slope_5")) else None,
        "ad_slope_10": float(row["ad_slope_10"]) if pd.notna(row.get("ad_slope_10")) else None,
        "mfi_rising": mfi is not None and mfi_prev is not None and mfi > mfi_prev,
    }
    feats["money_flow_score"] = compute_money_flow_score(feats)
    return feats


def _load_base_events() -> pd.DataFrame:
    vol_path = os.path.join(_validation_dir(), "wave_volume_energy.csv")
    div_path = os.path.join(_validation_dir(), "wave_energy_divergence.csv")
    if not os.path.isfile(vol_path):
        return pd.DataFrame()
    vol = pd.read_csv(vol_path, parse_dates=["timestamp"])
    if os.path.isfile(div_path):
        div = pd.read_csv(div_path, parse_dates=["timestamp"])
        div_cols = ["timestamp", "symbol", "bullish_div", "div_strength"]
        div_cols = [c for c in div_cols if c in div.columns]
        vol = vol.merge(div[div_cols], on=["timestamp", "symbol"], how="left", suffixes=("", "_div"))
    if "bullish_div" in vol.columns:
        vol["bullish_div"] = vol["bullish_div"].apply(
            lambda x: str(x) == "BULLISH_OBV_DIV" or x is True or str(x).lower() == "true",
        )
    else:
        vol["bullish_div"] = False
    return vol


def _wave_matches(row: pd.Series, wave: str) -> bool:
    ws = str(row.get("wave_state", ""))
    br = str(row.get("branch", ""))
    path = str(row.get("path", ""))
    if wave == "TRIPLE_BOTTOM_REQUIRED":
        return ws == wave or br == wave or wave in path
    return ws == wave or br == wave or wave in path


def build_money_flow_events(cache: Optional[Dict] = None) -> pd.DataFrame:
    base = _load_base_events()
    if base.empty:
        return pd.DataFrame()

    mf_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    rows: List[dict] = []

    for _, ev in base.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in mf_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            mf_cache[key] = add_money_flow_features(bare)
        mf_df = mf_cache[key]
        bar_idx = _find_bar_index(mf_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        feats = extract_money_flow_at(mf_df, bar_idx)
        if not feats:
            continue
        rows.append({
            "timestamp": pd.Timestamp(ev["timestamp"]),
            "symbol": sym,
            "timeframe": tf,
            "success": bool(ev["success"]),
            "return_pct": float(ev["return_pct"]),
            "energy_score": int(ev["energy_score"]) if pd.notna(ev.get("energy_score")) else 0,
            "bullish_div": bool(ev.get("bullish_div", False)),
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
    return sorted(rows, key=lambda x: x.get("effect_size") or 0, reverse=True)


def money_flow_score_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(6):
        sub = df[df["money_flow_score"] == score]
        if sub.empty:
            rows.append({
                "score": score, "n": 0, "win_rate": None,
                "expectancy": None, "profit_factor": None,
            })
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "score": score,
            "n": metrics.get("n", 0),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "profit_factor": metrics.get("profit_factor"),
        })
    return rows


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


def energy_money_flow_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for mf_thr in (3, 4):
        mask = (df["energy_score"] >= 3) & (df["money_flow_score"] >= mf_thr)
        rows.append(_combo_metrics(df, mask, f"Energy>=3 + MoneyFlow>={mf_thr}"))
    return rows


def divergence_money_flow_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for mf_thr in (3, 4):
        mask = df["bullish_div"] & (df["money_flow_score"] >= mf_thr)
        rows.append(_combo_metrics(df, mask, f"BullishDiv + MoneyFlow>={mf_thr}"))
    return rows


def tb_money_flow_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    tb = df[df.apply(lambda r: _wave_matches(r, "TRIPLE_BOTTOM_REQUIRED"), axis=1)]
    rows.append(_combo_metrics(tb, pd.Series(True, index=tb.index), "TB + MoneyFlow (all)"))
    for mf_thr in (3, 4):
        mask = tb["money_flow_score"] >= mf_thr
        rows.append(_combo_metrics(tb, mask, f"TB + MoneyFlow>={mf_thr}"))
    return rows


def wave3_money_flow_combos(df: pd.DataFrame) -> List[dict]:
    w3 = df[df.apply(lambda r: _wave_matches(r, "WAVE3_COMPLETED"), axis=1)]
    rows = [_combo_metrics(w3, pd.Series(True, index=w3.index), "WAVE3_COMPLETED + MoneyFlow (all)")]
    for mf_thr in (3, 4):
        mask = w3["money_flow_score"] >= mf_thr
        rows.append(_combo_metrics(w3, mask, f"WAVE3_COMPLETED + MoneyFlow>={mf_thr}"))
    return rows


def triple_combo(df: pd.DataFrame) -> dict:
    mask = (
        (df["energy_score"] >= 3)
        & (df["money_flow_score"] >= 3)
        & df["bullish_div"]
    )
    return _combo_metrics(df, mask, "Energy>=3 + MoneyFlow>=3 + BullishDiv")


def money_flow_timing(df: pd.DataFrame, mf_cache: Optional[Dict] = None) -> List[dict]:
    mf_cache = mf_cache or {}
    scores: Dict[int, List[float]] = {o: [] for o in TIMING_OFFSETS}
    for _, ev in df.iterrows():
        sym, tf = str(ev["symbol"]), str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in mf_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            mf_cache[key] = add_money_flow_features(bare)
        mf_df = mf_cache[key]
        bar_idx = _find_bar_index(mf_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        for offset in TIMING_OFFSETS:
            pos = bar_idx + offset
            if pos < 0 or pos >= len(mf_df):
                continue
            feats = extract_money_flow_at(mf_df, pos)
            if feats.get("money_flow_score") is not None:
                scores[offset].append(float(feats["money_flow_score"]))
    rows = []
    for offset in TIMING_OFFSETS:
        vals = scores[offset]
        rows.append({
            "offset": offset,
            "score": float(np.mean(vals)) if vals else None,
            "n": len(vals),
        })
    return rows


def failure_reclassification(df: pd.DataFrame) -> List[dict]:
    fails = df[~df["success"]]
    if fails.empty:
        return []
    total = len(fails)
    low_mf = fails["money_flow_score"] <= 1
    return [
        {"cause": "MONEY_FLOW_SCORE<=1", "count": int(low_mf.sum()),
         "pct": float(low_mf.sum()) / total * 100.0},
        {"cause": "MONEY_FLOW_SCORE>1", "count": int((~low_mf).sum()),
         "pct": float((~low_mf).sum()) / total * 100.0},
    ]


def symbol_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in GENERALIZATION_SYMBOLS:
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "symbol": sym,
            "money_flow_score_avg": float(sub["money_flow_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
            "n": m.get("n", 0),
        })
    return rows


def build_money_flow_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    out = df[cols].copy()
    out["bullish_div"] = out["bullish_div"].map(
        lambda x: "BULLISH_OBV_DIV" if x else "",
    )
    return out


def full_money_flow_summary(cache: Optional[Dict] = None) -> dict:
    df = build_money_flow_events(cache)
    compare = success_failure_compare(df)
    return {
        "dataframe": build_money_flow_csv(df),
        "raw": df,
        "event_count": len(df),
        "feature_compare": compare,
        "top_separators": compare[:10],
        "score_performance": money_flow_score_performance(df),
        "energy_money_combos": energy_money_flow_combos(df),
        "divergence_money_combos": divergence_money_flow_combos(df),
        "tb_money_combos": tb_money_flow_combos(df),
        "wave3_money_combos": wave3_money_flow_combos(df),
        "triple_combo": triple_combo(df),
        "timing": money_flow_timing(df),
        "failure_reclass": failure_reclassification(df),
        "symbol_comparison": symbol_comparison(df),
    }
