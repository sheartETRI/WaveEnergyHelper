"""Wave Survival — INITIAL 경로별 생존 기간 분석.

입력: wave_confirmation_lifecycle_*.csv (기존 산출물 불변).
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

INITIAL_CROSS = "CROSS_CONFIRMED"
INITIAL_SLOPE = "SLOPE_CONFIRMED"
INITIAL_TB = "TB_CONFIRMED"

SURVIVAL_INITIAL_TYPES = (INITIAL_SLOPE, INITIAL_CROSS, INITIAL_TB)

POST_HELD = "HELD"
POST_LATER_LL = "LATER_NEW_LL"
POST_LATER_OS = "LATER_RE_OVERSOLD"
POST_LATER_INV = "LATER_INVALIDATED"
POST_EXPIRED = "EXPIRED"

TERM_NEW_LL = "NEW_LL"
TERM_RE_OVERSOLD = "RE_OVERSOLD"
TERM_OTHER = "OTHER"
TERM_CENSORED = "CENSORED"

SURVIVAL_THRESHOLDS = (5, 10, 20, 40, 80)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def lifecycle_csv_path(symbol: str, interval: str) -> str:
    return os.path.join(
        _validation_dir(),
        f"wave_confirmation_lifecycle_{symbol}_{interval}.csv",
    )


def _termination_reason(post_outcome: str, censored: bool) -> str:
    if censored:
        return TERM_CENSORED
    if post_outcome == POST_LATER_LL:
        return TERM_NEW_LL
    if post_outcome == POST_LATER_OS:
        return TERM_RE_OVERSOLD
    if post_outcome == POST_LATER_INV:
        return TERM_OTHER
    return TERM_OTHER


def _is_censored(post_outcome: str) -> bool:
    return post_outcome in (POST_HELD, POST_EXPIRED)


def build_survival_from_lifecycle(lifecycle: pd.DataFrame) -> pd.DataFrame:
    """Lifecycle CSV → 생존 에피소드 DataFrame."""
    if lifecycle.empty:
        return pd.DataFrame()

    df = lifecycle.copy()
    df = df[df["initial_outcome"].isin(SURVIVAL_INITIAL_TYPES)]
    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        post = str(row["post_outcome"])
        censored = _is_censored(post)
        held = row.get("bars_held_after_initial")
        survival = float(held) if pd.notna(held) else 0.0
        rows.append({
            "timestamp": row["timestamp"],
            "initial_type": row["initial_outcome"],
            "survival_bars": int(survival),
            "termination_reason": _termination_reason(post, censored),
            "censored": censored,
            "post_outcome": post,
        })
    return pd.DataFrame(rows)


def load_survival(symbol: str, interval: str) -> pd.DataFrame:
    path = lifecycle_csv_path(symbol, interval)
    if not os.path.isfile(path):
        return pd.DataFrame()
    lifecycle = pd.read_csv(path, parse_dates=["timestamp"])
    return build_survival_from_lifecycle(lifecycle)


def survival_rate_at(survival_df: pd.DataFrame, threshold: int, initial_type: Optional[str] = None) -> float:
    sub = survival_df
    if initial_type:
        sub = sub[sub["initial_type"] == initial_type]
    if sub.empty:
        return 0.0
    return float((sub["survival_bars"] >= threshold).sum()) / len(sub) * 100.0


def summarize_survival(survival_df: pd.DataFrame) -> dict:
    if survival_df.empty:
        return {"count": 0}

    by_type: Dict[str, dict] = {}
    for itype in SURVIVAL_INITIAL_TYPES:
        sub = survival_df[survival_df["initial_type"] == itype]
        if sub.empty:
            by_type[itype] = {"count": 0}
            continue

        vals = sub["survival_bars"].astype(float)
        terminated = sub[~sub["censored"]]
        term_counts = terminated["termination_reason"].value_counts()
        n_term = len(terminated) or 1

        rates = {t: survival_rate_at(survival_df, t, itype) for t in SURVIVAL_THRESHOLDS}

        by_type[itype] = {
            "count": len(sub),
            "avg": float(vals.mean()),
            "median": float(vals.median()),
            "max": float(vals.max()),
            "rates": rates,
            "hazard": {
                TERM_NEW_LL: float(term_counts.get(TERM_NEW_LL, 0)) / n_term * 100.0,
                TERM_RE_OVERSOLD: float(term_counts.get(TERM_RE_OVERSOLD, 0)) / n_term * 100.0,
                TERM_OTHER: float(term_counts.get(TERM_OTHER, 0)) / n_term * 100.0,
            },
        }

    longest = survival_df.loc[survival_df["survival_bars"].idxmax()]
    initial_dist = survival_df["initial_type"].value_counts().to_dict()

    return {
        "count": len(survival_df),
        "by_type": by_type,
        "initial_dist": {k: int(v) for k, v in initial_dist.items()},
        "longest": {
            "timestamp": str(longest["timestamp"]),
            "initial_type": str(longest["initial_type"]),
            "survival_bars": int(longest["survival_bars"]),
            "termination_reason": str(longest["termination_reason"]),
            "censored": bool(longest["censored"]),
        },
    }
