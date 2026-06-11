"""Wave Outcome — INITIAL 경로별 가격 성과(Forward Return / MFE / MAE) 분석.

입력: wave_confirmation_lifecycle_*.csv + OHLCV (기존 산출물 불변).
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from analysis.wave_survival import (
    INITIAL_CROSS,
    INITIAL_SLOPE,
    INITIAL_TB,
    SURVIVAL_INITIAL_TYPES,
    lifecycle_csv_path,
)

OUTCOME_HORIZONS = (5, 10, 20, 40, 80)
SURVIVAL_FILTER_THRESHOLDS = (20, 40, 80)


def _find_bar_index(ohlcv: pd.DataFrame, ts: pd.Timestamp) -> Optional[int]:
    idx = pd.DatetimeIndex(ohlcv.index)
    ts = pd.Timestamp(ts)
    if ts in idx:
        return int(idx.get_loc(ts))
    loc = idx.searchsorted(ts)
    if loc < len(idx) and idx[loc] == ts:
        return int(loc)
    if loc > 0 and abs((idx[loc - 1] - ts).total_seconds()) < abs((idx[min(loc, len(idx)-1)] - ts).total_seconds()):
        return int(loc - 1)
    if loc < len(idx):
        return int(loc)
    return None


def _forward_return(close: pd.Series, entry_idx: int, n: int) -> Optional[float]:
    target = entry_idx + n
    if target >= len(close) or entry_idx < 0:
        return None
    entry = float(close.iloc[entry_idx])
    if entry == 0 or pd.isna(entry):
        return None
    exit_p = float(close.iloc[target])
    if pd.isna(exit_p):
        return None
    return (exit_p - entry) / entry


def _mfe(high: pd.Series, entry_idx: int, n: int, entry: float) -> Optional[float]:
    end = entry_idx + n + 1
    if end > len(high) or entry_idx < 0 or entry == 0:
        return None
    window = high.iloc[entry_idx + 1 : end]
    if window.empty or window.isna().all():
        return None
    return (float(window.max()) - entry) / entry


def _mae(low: pd.Series, entry_idx: int, n: int, entry: float) -> Optional[float]:
    end = entry_idx + n + 1
    if end > len(low) or entry_idx < 0 or entry == 0:
        return None
    window = low.iloc[entry_idx + 1 : end]
    if window.empty or window.isna().all():
        return None
    return (float(window.min()) - entry) / entry


def compute_episode_outcome(
    row: pd.Series,
    ohlcv: pd.DataFrame,
) -> Optional[dict]:
    """단일 lifecycle 에피소드 성과."""
    initial = str(row["initial_outcome"])
    if initial not in SURVIVAL_INITIAL_TYPES:
        return None

    db_ts = pd.Timestamp(row["timestamp"])
    db_idx = _find_bar_index(ohlcv, db_ts)
    if db_idx is None:
        return None

    delay = row.get("bars_until_initial")
    if pd.isna(delay):
        return None
    initial_idx = db_idx + int(delay)
    if initial_idx >= len(ohlcv):
        return None

    entry = float(ohlcv["close"].iloc[initial_idx])
    if pd.isna(entry) or entry == 0:
        return None

    survival = row.get("bars_held_after_initial")
    survival_bars = int(survival) if pd.notna(survival) else 0

    out = {
        "timestamp": db_ts,
        "initial_type": initial,
        "entry_price": entry,
        "initial_bar_index": initial_idx,
        "survival_bars": survival_bars,
    }

    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]

    for n in OUTCOME_HORIZONS:
        out[f"return_{n}"] = _forward_return(close, initial_idx, n)
        out[f"mfe_{n}"] = _mfe(high, initial_idx, n, entry)
        out[f"mae_{n}"] = _mae(low, initial_idx, n, entry)

    return out


def build_outcomes_from_lifecycle(
    lifecycle: pd.DataFrame,
    ohlcv: pd.DataFrame,
) -> pd.DataFrame:
    rows: List[dict] = []
    for _, row in lifecycle.iterrows():
        ep = compute_episode_outcome(row, ohlcv)
        if ep:
            rows.append(ep)
    return pd.DataFrame(rows)


def load_outcomes(symbol: str, interval: str, ohlcv: pd.DataFrame) -> pd.DataFrame:
    path = lifecycle_csv_path(symbol, interval)
    if not os.path.isfile(path):
        return pd.DataFrame()
    lifecycle = pd.read_csv(path, parse_dates=["timestamp"])
    return build_outcomes_from_lifecycle(lifecycle, ohlcv)


def _pct_mean(series: pd.Series) -> Optional[float]:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.mean()) * 100.0


def _pct_median(series: pd.Series) -> Optional[float]:
    s = series.dropna()
    if s.empty:
        return None
    return float(s.median()) * 100.0


def _win_rate(series: pd.Series) -> Optional[float]:
    s = series.dropna()
    if s.empty:
        return None
    return float((s > 0).sum()) / len(s) * 100.0


def summarize_outcomes(outcomes: pd.DataFrame) -> dict:
    if outcomes.empty:
        return {"count": 0}

    by_type: Dict[str, dict] = {}
    for itype in SURVIVAL_INITIAL_TYPES:
        sub = outcomes[outcomes["initial_type"] == itype]
        if sub.empty:
            by_type[itype] = {"count": 0}
            continue

        stats = {"count": len(sub)}
        for n in OUTCOME_HORIZONS:
            rcol = f"return_{n}"
            mcol = f"mfe_{n}"
            acol = f"mae_{n}"
            stats[f"mean_return_{n}"] = _pct_mean(sub[rcol])
            stats[f"median_return_{n}"] = _pct_median(sub[rcol])
            stats[f"win_{n}"] = _win_rate(sub[rcol])
            stats[f"mean_mfe_{n}"] = _pct_mean(sub[mcol])
            stats[f"mean_mae_{n}"] = _pct_mean(sub[acol])

        survival_cond: Dict[int, dict] = {}
        for thr in SURVIVAL_FILTER_THRESHOLDS:
            filt = sub[sub["survival_bars"] >= thr]
            survival_cond[thr] = {
                "count": len(filt),
                "mean_return_20": _pct_mean(filt["return_20"]) if len(filt) else None,
                "mean_return_40": _pct_mean(filt["return_40"]) if len(filt) else None,
                "mean_return_80": _pct_mean(filt["return_80"]) if len(filt) else None,
            }
        stats["survival_cond"] = survival_cond
        by_type[itype] = stats

    return {
        "count": len(outcomes),
        "by_type": by_type,
        "initial_dist": outcomes["initial_type"].value_counts().to_dict(),
    }
