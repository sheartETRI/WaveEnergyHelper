"""Wave Structure Confirmation — HH/HL/Neckline 구조 복원 관측.

Money Flow/Volume Energy/Expectancy 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
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

PIVOT = 3
TIMING_OFFSETS = (-20, -10, -5, 0, 5, 10)
RESISTANCE_LOOKBACK = 20

COMPARE_FEATURES = (
    "structure_score", "hl", "hh", "hhhl",
    "neckline_recovery", "resistance_break", "support_hold",
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "success", "return_pct",
    "hl", "hh", "hhhl", "neckline_recovery", "resistance_break", "support_hold",
    "structure_score", "energy_score", "money_flow_score",
    "wave_state", "branch", "path",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def find_swing_lows(series: pd.Series, pivot: int = PIVOT) -> List[Tuple[int, float]]:
    pivots: List[Tuple[int, float]] = []
    n = len(series)
    for i in range(pivot, n - pivot):
        val = float(series.iloc[i])
        if pd.isna(val):
            continue
        before = series.iloc[i - pivot:i]
        after = series.iloc[i + 1: i + pivot + 1]
        if val <= before.min() and val <= after.min():
            pivots.append((i, val))
    return pivots


def find_swing_highs(series: pd.Series, pivot: int = PIVOT) -> List[Tuple[int, float]]:
    pivots: List[Tuple[int, float]] = []
    n = len(series)
    for i in range(pivot, n - pivot):
        val = float(series.iloc[i])
        if pd.isna(val):
            continue
        before = series.iloc[i - pivot:i]
        after = series.iloc[i + 1: i + pivot + 1]
        if val >= before.max() and val >= after.max():
            pivots.append((i, val))
    return pivots


def _confirmed(pivots: List[Tuple[int, float]], pos: int) -> List[Tuple[int, float]]:
    return [(i, v) for i, v in pivots if i + PIVOT <= pos]


def compute_structure_score(feats: dict) -> int:
    score = 0
    for key in ("hl", "hh", "hhhl", "neckline_recovery", "resistance_break", "support_hold"):
        if feats.get(key):
            score += 1
    return score


def extract_structure_at(
    ohlcv: pd.DataFrame,
    pos: int,
    swing_lows: Optional[List[Tuple[int, float]]] = None,
    swing_highs: Optional[List[Tuple[int, float]]] = None,
) -> dict:
    """단일 봉 구조 feature."""
    if pos < 0 or pos >= len(ohlcv):
        return {}

    low_s = ohlcv["low"]
    high_s = ohlcv["high"]
    close_s = ohlcv["close"]

    if swing_lows is None:
        swing_lows = find_swing_lows(low_s)
    if swing_highs is None:
        swing_highs = find_swing_highs(high_s)

    conf_lows = _confirmed(swing_lows, pos)
    conf_highs = _confirmed(swing_highs, pos)

    close = float(close_s.iloc[pos])
    low = float(low_s.iloc[pos])

    hl = False
    if len(conf_lows) >= 2:
        _, l1 = conf_lows[-2]
        _, l2 = conf_lows[-1]
        hl = l2 > l1

    hh = False
    if len(conf_highs) >= 1:
        _, h_last = conf_highs[-1]
        hh = close > h_last
    if len(conf_highs) >= 2:
        _, h1 = conf_highs[-2]
        _, h2 = conf_highs[-1]
        hh = hh or h2 > h1

    hhhl = hl and hh

    neckline_recovery = False
    if len(conf_highs) >= 2:
        _, neck = conf_highs[-2]
        neckline_recovery = close > neck

    resistance_break = False
    if pos >= RESISTANCE_LOOKBACK:
        resist = float(high_s.iloc[pos - RESISTANCE_LOOKBACK:pos].max())
        resistance_break = close > resist

    support_hold = False
    if conf_lows:
        _, last_ll = conf_lows[-1]
        support_hold = low >= last_ll

    feats = {
        "hl": hl,
        "hh": hh,
        "hhhl": hhhl,
        "neckline_recovery": neckline_recovery,
        "resistance_break": resistance_break,
        "support_hold": support_hold,
    }
    feats["structure_score"] = compute_structure_score(feats)
    return feats


def _load_base_events() -> pd.DataFrame:
    mf_path = os.path.join(_validation_dir(), "wave_money_flow.csv")
    vol_path = os.path.join(_validation_dir(), "wave_volume_energy.csv")
    if not os.path.isfile(mf_path):
        return pd.DataFrame()
    mf = pd.read_csv(mf_path, parse_dates=["timestamp"])
    if os.path.isfile(vol_path):
        vol = pd.read_csv(vol_path, parse_dates=["timestamp"])
        if "timeframe" in vol.columns:
            tf_map = vol.set_index(["timestamp", "symbol"])["timeframe"].to_dict()
            mf["timeframe"] = mf.apply(
                lambda r: tf_map.get((pd.Timestamp(r["timestamp"]), r["symbol"]), "4h"),
                axis=1,
            )
        else:
            mf["timeframe"] = mf["symbol"].map(
                {"ETHUSDT": "4h", "BTCUSDT": "1d", "SOLUSDT": "1h", "BNBUSDT": "4h"},
            ).fillna("4h")
    else:
        mf["timeframe"] = "4h"
    if "money_flow_score" not in mf.columns:
        mf["money_flow_score"] = 0
    if "energy_score" not in mf.columns:
        mf["energy_score"] = 0
    return mf


def _wave_matches(row: pd.Series, wave: str) -> bool:
    ws = str(row.get("wave_state", ""))
    br = str(row.get("branch", ""))
    path = str(row.get("path", ""))
    return ws == wave or br == wave or wave in path


def build_structure_events(cache: Optional[Dict] = None) -> pd.DataFrame:
    base = _load_base_events()
    if base.empty:
        return pd.DataFrame()

    struct_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    pivot_cache: Dict[Tuple[str, str], Tuple] = {}
    rows: List[dict] = []

    for _, ev in base.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in struct_cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            struct_cache[key] = bare
            pivot_cache[key] = (find_swing_lows(bare["low"]), find_swing_highs(bare["high"]))
        ohlcv = struct_cache[key]
        sw_lows, sw_highs = pivot_cache[key]
        bar_idx = _find_bar_index(ohlcv, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        feats = extract_structure_at(ohlcv, bar_idx, sw_lows, sw_highs)
        if not feats:
            continue
        rows.append({
            "timestamp": pd.Timestamp(ev["timestamp"]),
            "symbol": sym,
            "timeframe": tf,
            "success": bool(ev["success"]),
            "return_pct": float(ev["return_pct"]),
            "energy_score": int(ev["energy_score"]) if pd.notna(ev.get("energy_score")) else 0,
            "money_flow_score": int(ev["money_flow_score"]) if pd.notna(ev.get("money_flow_score")) else 0,
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
        if feat in ("hl", "hh", "hhhl", "neckline_recovery", "resistance_break", "support_hold"):
            s_rate = float(succ[feat].mean()) * 100.0 if len(succ) else None
            f_rate = float(fail[feat].mean()) * 100.0 if len(fail) else None
            rows.append({
                "feature": feat,
                "success_mean": s_rate,
                "failure_mean": f_rate,
                "effect_size": abs((s_rate or 0) - (f_rate or 0)) / 100.0,
            })
        else:
            s_vals = succ[feat].dropna().astype(float)
            f_vals = fail[feat].dropna().astype(float)
            rows.append({
                "feature": feat,
                "success_mean": float(s_vals.mean()) if len(s_vals) else None,
                "failure_mean": float(f_vals.mean()) if len(f_vals) else None,
                "effect_size": effect_size(s_vals, f_vals) if len(s_vals) >= 2 and len(f_vals) >= 2 else None,
            })
    return sorted(rows, key=lambda x: x.get("effect_size") or 0, reverse=True)


def structure_score_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(7):
        sub = df[df["structure_score"] == score]
        if sub.empty:
            rows.append({
                "score": score, "n": 0, "win_rate": None,
                "expectancy": None, "profit_factor": None,
            })
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "score": score,
            "n": m.get("n", 0),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
            "profit_factor": m.get("profit_factor"),
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


def energy_structure_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for thr in (3, 4):
        mask = (df["energy_score"] >= 3) & (df["structure_score"] >= thr)
        rows.append(_combo_metrics(df, mask, f"Energy>=3 + Structure>={thr}"))
    return rows


def mf_structure_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    rows.append(_combo_metrics(
        df, (df["money_flow_score"] >= 3) & (df["structure_score"] >= 3),
        "MF>=3 + Structure>=3",
    ))
    rows.append(_combo_metrics(
        df, (df["money_flow_score"] >= 4) & (df["structure_score"] >= 4),
        "MF>=4 + Structure>=4",
    ))
    return rows


def tb_structure_combos(df: pd.DataFrame) -> List[dict]:
    tb = df[df.apply(lambda r: _wave_matches(r, "TRIPLE_BOTTOM_REQUIRED"), axis=1)]
    rows = []
    for thr in (3, 4):
        mask = tb["structure_score"] >= thr
        rows.append(_combo_metrics(tb, mask, f"TB + Structure>={thr}"))
    return rows


def wave3_structure_combos(df: pd.DataFrame) -> List[dict]:
    w3 = df[df.apply(lambda r: _wave_matches(r, "WAVE3_COMPLETED"), axis=1)]
    rows = [_combo_metrics(w3, pd.Series(True, index=w3.index), "WAVE3 + Structure (all)")]
    for thr in (3, 4):
        rows.append(_combo_metrics(w3, w3["structure_score"] >= thr, f"WAVE3 + Structure>={thr}"))
    return rows


def energy_mf_structure_combo(df: pd.DataFrame) -> dict:
    mask = (
        (df["energy_score"] >= 3)
        & (df["money_flow_score"] >= 3)
        & (df["structure_score"] >= 3)
    )
    return _combo_metrics(df, mask, "Energy>=3 + MF>=3 + Structure>=3")


def structure_timing(df: pd.DataFrame, cache: Optional[Dict] = None) -> List[dict]:
    cache = cache or {}
    pivot_cache: Dict = {}
    scores: Dict[int, List[float]] = {o: [] for o in TIMING_OFFSETS}
    for _, ev in df.iterrows():
        sym, tf = str(ev["symbol"]), str(ev.get("timeframe", "4h"))
        key = (sym, tf)
        if key not in cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            cache[key] = bare
            pivot_cache[key] = (find_swing_lows(bare["low"]), find_swing_highs(bare["high"]))
        ohlcv = cache[key]
        sw_l, sw_h = pivot_cache[key]
        bar_idx = _find_bar_index(ohlcv, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        for offset in TIMING_OFFSETS:
            pos = bar_idx + offset
            if pos < 0 or pos >= len(ohlcv):
                continue
            feats = extract_structure_at(ohlcv, pos, sw_l, sw_h)
            if feats.get("structure_score") is not None:
                scores[offset].append(float(feats["structure_score"]))
    return [
        {"offset": o, "score": float(np.mean(scores[o])) if scores[o] else None, "n": len(scores[o])}
        for o in TIMING_OFFSETS
    ]


def failure_reclassification(df: pd.DataFrame) -> List[dict]:
    fails = df[~df["success"]]
    if fails.empty:
        return []
    total = len(fails)
    low_struct = fails["structure_score"] <= 2
    return [
        {"cause": "STRUCTURE_SCORE<=2", "count": int(low_struct.sum()),
         "pct": float(low_struct.sum()) / total * 100.0},
        {"cause": "STRUCTURE_SCORE>2", "count": int((~low_struct).sum()),
         "pct": float((~low_struct).sum()) / total * 100.0},
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
            "structure_score_avg": float(sub["structure_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
            "n": m.get("n", 0),
        })
    return rows


def build_structure_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    return df[cols].copy()


def full_structure_summary(cache: Optional[Dict] = None) -> dict:
    df = build_structure_events(cache)
    compare = success_failure_compare(df)
    return {
        "dataframe": build_structure_csv(df),
        "raw": df,
        "event_count": len(df),
        "feature_compare": compare,
        "top_separators": compare[:10],
        "score_performance": structure_score_performance(df),
        "energy_structure_combos": energy_structure_combos(df),
        "mf_structure_combos": mf_structure_combos(df),
        "tb_structure_combos": tb_structure_combos(df),
        "wave3_structure_combos": wave3_structure_combos(df),
        "ems_combo": energy_mf_structure_combo(df),
        "timing": structure_timing(df),
        "failure_reclass": failure_reclassification(df),
        "symbol_comparison": symbol_comparison(df),
    }
