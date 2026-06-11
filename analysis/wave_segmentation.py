"""Wave Segmentation — TP3 기준 성공/실패 요인 분석.

기존 분석 산출물만 소비. 신규 신호·ML 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import pandas as pd

from analysis.verdict_stability import NEUTRAL, enrich_timeline_stability, map_verdict_family
from analysis.wave_exit import POLICY_A
from analysis.wave_outcome import _find_bar_index
from analysis.wave_survival import (
    INITIAL_CROSS,
    INITIAL_SLOPE,
    INITIAL_TB,
)
from config.settings import WAVE_LAYER_ROLES

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]
STABLE_COL = "family_smoothed_3"
MIN_SAMPLE = 5

SHORT_INITIAL = {
    INITIAL_SLOPE: "SLOPE",
    INITIAL_CROSS: "CROSS",
    INITIAL_TB: "TB",
    "SLOPE_CONFIRMED": "SLOPE",
    "CROSS_CONFIRMED": "CROSS",
    "TB_CONFIRMED": "TB",
}

TRACKER_STATES = (
    "WAVE3_ACTIVE",
    "DOUBLE_BOTTOM_CANDIDATE",
    "TRIPLE_BOTTOM_REQUIRED",
    "TRIPLE_BOTTOM_CONFIRMED",
    "WAVE3_COMPLETED",
)

SURVIVAL_BUCKETS = ("<10", "10-19", "20-39", "40+")


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def survival_bucket(bars: float) -> str:
    if pd.isna(bars):
        return "<10"
    b = int(bars)
    if b < 10:
        return "<10"
    if b < 20:
        return "10-19"
    if b < 40:
        return "20-39"
    return "40+"


def classify_success(return_pct: float) -> Tuple[bool, bool, bool]:
    strong_success = return_pct >= 3.0
    strong_failure = return_pct <= -3.0
    success = return_pct > 0
    return success, strong_success, strong_failure


def _lookup_at(ts: pd.Timestamp, timeline: pd.DataFrame, col: str, default="") -> str:
    if timeline.empty or col not in timeline.columns:
        return default
    keyed = timeline.set_index("timestamp")
    if ts in keyed.index:
        v = keyed.loc[ts, col]
        if isinstance(v, pd.Series):
            v = v.iloc[-1]
        return str(v) if pd.notna(v) else default
    idx = keyed.index.searchsorted(ts)
    if idx < len(keyed):
        v = keyed.iloc[idx][col]
        return str(v) if pd.notna(v) else default
    if len(keyed):
        v = keyed.iloc[-1][col]
        return str(v) if pd.notna(v) else default
    return default


def _market_returns(ohlcv: pd.DataFrame, entry_idx: int) -> Tuple[Optional[float], Optional[float]]:
    if entry_idx < 0 or entry_idx >= len(ohlcv):
        return None, None
    close = ohlcv["close"]
    entry = float(close.iloc[entry_idx])
    if entry == 0:
        return None, None

    def _ret(n: int) -> Optional[float]:
        start = entry_idx - n
        if start < 0:
            return None
        return (entry - float(close.iloc[start])) / float(close.iloc[start]) * 100.0

    return _ret(20), _ret(40)


def build_segmentation(
    symbol: str,
    interval: str,
    ohlcv: pd.DataFrame,
    pipeline_df: pd.DataFrame,
) -> pd.DataFrame:
    exit_path = _path("wave_exit", symbol, interval)
    if not os.path.isfile(exit_path):
        return pd.DataFrame()

    exits = pd.read_csv(exit_path, parse_dates=["timestamp"])
    tp3 = exits[exits["policy"] == POLICY_A].copy()
    if tp3.empty:
        return pd.DataFrame()

    lifecycle = pd.read_csv(
        _path("wave_confirmation_lifecycle", symbol, interval),
        parse_dates=["timestamp"],
    )
    survival = pd.read_csv(
        _path("wave_survival", symbol, interval),
        parse_dates=["timestamp"],
    )
    tracker = pd.read_csv(
        _path("wave_tracker", symbol, interval),
        parse_dates=["timestamp"],
    )
    verdict = pd.read_csv(
        _path("verdict_timeline", symbol, interval),
        parse_dates=["timestamp"],
    )
    stab = enrich_timeline_stability(verdict)

    k_col = f"stoch_k_{_LAYER_LARGE}"
    d_col = f"stoch_d_{_LAYER_LARGE}"

    lc_keyed = lifecycle.set_index("timestamp")
    sv_keyed = survival.set_index("timestamp") if not survival.empty else None

    rows: List[dict] = []
    for _, ex in tp3.iterrows():
        db_ts = pd.Timestamp(ex["timestamp"])
        if db_ts not in lc_keyed.index:
            continue
        lc = lc_keyed.loc[db_ts]
        if isinstance(lc, pd.DataFrame):
            lc = lc.iloc[0]

        db_idx = _find_bar_index(ohlcv, db_ts)
        if db_idx is None:
            continue
        delay = lc.get("bars_until_initial")
        if pd.isna(delay):
            continue
        entry_idx = db_idx + int(delay)
        if entry_idx >= len(ohlcv):
            continue
        entry_ts = pd.Timestamp(ohlcv.index[entry_idx])

        ret = float(ex["return_pct"])
        success, strong_success, strong_failure = classify_success(ret)

        surv_bars = float(lc.get("bars_held_after_initial", 0))
        if sv_keyed is not None and db_ts in sv_keyed.index:
            sv = sv_keyed.loc[db_ts]
            if isinstance(sv, pd.DataFrame):
                sv = sv.iloc[0]
            surv_bars = float(sv.get("survival_bars", surv_bars))

        major_k = major_d = kd_gap = None
        if pipeline_df is not None and entry_idx < len(pipeline_df):
            if k_col in pipeline_df.columns:
                major_k = float(pipeline_df[k_col].iloc[entry_idx])
            if d_col in pipeline_df.columns:
                major_d = float(pipeline_df[d_col].iloc[entry_idx])
            if major_k is not None and major_d is not None and pd.notna(major_k) and pd.notna(major_d):
                kd_gap = major_k - major_d

        state = _lookup_at(entry_ts, tracker, "state", "NONE")
        if state not in TRACKER_STATES:
            state = state if state != "NONE" else "OTHER"

        category = _lookup_at(entry_ts, stab, "category", "판단불가")
        family = map_verdict_family(category)
        stable_family = _lookup_at(entry_ts, stab, STABLE_COL, NEUTRAL)

        initial = str(ex.get("initial_type", lc.get("initial_outcome", "")))
        ret20, ret40 = _market_returns(ohlcv, entry_idx)

        rows.append({
            "timestamp": db_ts,
            "entry_timestamp": entry_ts,
            "success": success,
            "strong_success": strong_success,
            "strong_failure": strong_failure,
            "state": state,
            "initial_type": SHORT_INITIAL.get(initial, initial),
            "survival_bars": surv_bars,
            "survival_bucket": survival_bucket(surv_bars),
            "verdict": _lookup_at(entry_ts, verdict, "verdict", ""),
            "category": category,
            "family": family,
            "stable_family": stable_family,
            "major_k": major_k,
            "major_d": major_d,
            "kd_gap": kd_gap,
            "return_pct": ret,
            "market_ret_20": ret20,
            "market_ret_40": ret40,
        })

    return pd.DataFrame(rows)


def _feature_rates(df: pd.DataFrame, col: str, success_col: str = "success") -> List[dict]:
    rows = []
    for val, grp in df.groupby(col, dropna=False):
        n = len(grp)
        if n == 0:
            continue
        succ = int(grp[success_col].sum())
        rows.append({
            "feature": col,
            "value": str(val),
            "n": n,
            "success": succ,
            "success_rate": succ / n * 100.0,
            "failure": n - succ,
            "failure_rate": (n - succ) / n * 100.0,
        })
    return rows


def _combo_conditions(df: pd.DataFrame) -> List[dict]:
    """2조건 조합 성공률 (n >= MIN_SAMPLE)."""
    dims = tuple(
        c for c in (
            "initial_type", "survival_bucket", "state", "family",
            "stable_family", "category", "verdict",
        )
        if c in df.columns
    )
    results: List[dict] = []

    def _add(mask: pd.Series, label: str) -> None:
        grp = df[mask]
        n = len(grp)
        if n < MIN_SAMPLE:
            return
        succ = int(grp["success"].sum())
        results.append({
            "condition": label,
            "n": n,
            "success": succ,
            "success_rate": succ / n * 100.0,
            "failure_rate": (n - succ) / n * 100.0,
        })

    for k1, k2 in combinations(dims, 2):
        for v1 in df[k1].dropna().unique():
            for v2 in df[df[k1] == v1][k2].dropna().unique():
                mask = (df[k1] == v1) & (df[k2] == v2)
                _add(mask, f"{k1}={v1} & {k2}={v2}")

    if "survival_bars" not in df.columns:
        return results

    for thr in (20, 40):
        base = df["survival_bars"] >= thr
        for k in dims:
            for v in df.loc[base, k].dropna().unique():
                mask = base & (df[k] == v)
                _add(mask, f"survival>={thr} & {k}={v}")

    return results


def summarize_segmentation(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    feature_cols = [
        c for c in (
            "initial_type", "state", "survival_bucket", "verdict",
            "category", "family", "stable_family",
        )
        if c in df.columns
    ]
    by_feature: Dict[str, List[dict]] = {}
    for col in feature_cols:
        by_feature[col] = _feature_rates(df, col)

    combos = _combo_conditions(df)
    combos_sorted = sorted(combos, key=lambda x: x["success_rate"], reverse=True)

    def _top_factors(rates: List[dict], rate_key: str, top_n: int = 20) -> List[dict]:
        eligible = [r for r in rates if r["n"] >= MIN_SAMPLE]
        return sorted(eligible, key=lambda x: x[rate_key], reverse=True)[:top_n]

    all_single = []
    for col, rates in by_feature.items():
        for r in rates:
            all_single.append({**r, "label": f"{col}={r['value']}"})

    top_success = _top_factors(all_single, "success_rate", 20)
    top_failure = _top_factors(all_single, "failure_rate", 20)

    top10_success = top_success[:10]
    top10_failure = top_failure[:10]

    strongest = combos_sorted[0] if combos_sorted else None
    weakest = combos_sorted[-1] if combos_sorted else None

    return {
        "count": len(df),
        "success_rate": float(df["success"].mean() * 100),
        "by_feature": by_feature,
        "combos": combos_sorted,
        "top_success": top_success,
        "top_failure": top_failure,
        "top10_success": top10_success,
        "top10_failure": top10_failure,
        "strongest_pair": strongest,
        "weakest_pair": weakest,
    }
