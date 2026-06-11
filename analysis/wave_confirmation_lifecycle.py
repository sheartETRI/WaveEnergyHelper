"""Wave Confirmation Lifecycle — INITIAL / POST 분리 생존 분석.

기존 wave_confirmation 모듈·CSV·REPORT 불변. 신규 레이어만 추가.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from analysis.wave_confirmation import (
    CONFIRM_WINDOWS,
    cross_confirm_at,
    extract_bar_flags,
    slope_confirm_at,
)
from config.settings import WAVE_LAYER_ROLES

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]

INITIAL_CROSS = "CROSS_CONFIRMED"
INITIAL_SLOPE = "SLOPE_CONFIRMED"
INITIAL_TB = "TB_CONFIRMED"
INITIAL_NO_CONFIRM = "NO_CONFIRM"

POST_HELD = "HELD"
POST_LATER_LL = "LATER_NEW_LL"
POST_LATER_OS = "LATER_RE_OVERSOLD"
POST_LATER_INV = "LATER_INVALIDATED"
POST_EXPIRED = "EXPIRED"

ALL_INITIAL = (INITIAL_CROSS, INITIAL_SLOPE, INITIAL_TB, INITIAL_NO_CONFIRM)
ALL_POST = (POST_HELD, POST_LATER_LL, POST_LATER_OS, POST_LATER_INV, POST_EXPIRED)

MAX_INITIAL_WINDOW = max(CONFIRM_WINDOWS)
_INITIAL_PRIORITY = {
    INITIAL_CROSS: 0,
    INITIAL_SLOPE: 1,
    INITIAL_TB: 2,
}


@dataclass
class LifecycleEpisode:
    timestamp: pd.Timestamp
    db_index: int
    initial_outcome: str = INITIAL_NO_CONFIRM
    post_outcome: str = POST_EXPIRED
    bars_until_initial: Optional[int] = None
    bars_until_post: Optional[int] = None
    bars_held_after_initial: Optional[int] = None


def _collect_bar_series(
    bare: pd.DataFrame,
    *,
    warmup: int = 240,
    pipeline_fn=None,
) -> Tuple[pd.DatetimeIndex, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    from display.asof import run_indicator_pipeline

    if pipeline_fn is None:
        pipeline_fn = run_indicator_pipeline
    if bare is None or bare.empty:
        return pd.DatetimeIndex([]), pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=bool), pd.Series(dtype=bool), pd.Series(dtype=bool), pd.Series(dtype=bool)

    full_df = pipeline_fn(bare)
    index_list: List[pd.Timestamp] = []
    rows_k, rows_d, rows_db, rows_tb, rows_ll, rows_os = [], [], [], [], [], []
    prev_oversold = False
    start = min(warmup, len(bare) - 1)

    for i in range(start, len(bare)):
        cut_df = full_df.iloc[: i + 1]
        flags = extract_bar_flags(cut_df, prev_oversold)
        prev_oversold = flags["major_oversold"]
        index_list.append(pd.Timestamp(bare.index[i]))
        rows_k.append(flags["major_k"])
        rows_d.append(flags["major_d"])
        rows_db.append(flags["db_edge"])
        rows_tb.append(flags["tb_edge"])
        rows_ll.append(flags["ll_new"])
        rows_os.append(flags["oversold_entry"])

    idx = pd.DatetimeIndex(index_list)
    return (
        idx,
        pd.Series(rows_k, index=idx),
        pd.Series(rows_d, index=idx),
        pd.Series(rows_db, index=idx),
        pd.Series(rows_tb, index=idx),
        pd.Series(rows_ll, index=idx),
        pd.Series(rows_os, index=idx),
    )


def _first_initial(
    db_index: int,
    k: pd.Series,
    d: pd.Series,
    tb_mask: pd.Series,
    series_end: int,
) -> Tuple[str, Optional[int], Optional[int]]:
    """INITIAL outcome — 윈도 내 최초 이벤트 (동시각 tie: CROSS > SLOPE > TB)."""
    candidates: List[Tuple[int, str, int]] = []
    for i in range(db_index, min(series_end, db_index + MAX_INITIAL_WINDOW) + 1):
        delay = i - db_index
        if cross_confirm_at(k, d, i):
            candidates.append((delay, INITIAL_CROSS, i))
        if slope_confirm_at(k, i):
            candidates.append((delay, INITIAL_SLOPE, i))
        if bool(tb_mask.iloc[i]):
            candidates.append((delay, INITIAL_TB, i))

    if not candidates:
        return INITIAL_NO_CONFIRM, None, None

    candidates.sort(key=lambda x: (x[0], _INITIAL_PRIORITY[x[1]]))
    delay, outcome, bar = candidates[0]
    return outcome, delay, bar


def analyze_lifecycle_episode(
    db_index: int,
    timestamp: pd.Timestamp,
    k: pd.Series,
    d: pd.Series,
    tb_mask: pd.Series,
    ll_mask: pd.Series,
    os_mask: pd.Series,
    series_end: int,
) -> LifecycleEpisode:
    """단일 DB 에피소드 lifecycle."""
    initial, bars_until_initial, initial_bar = _first_initial(
        db_index, k, d, tb_mask, series_end,
    )

    if initial == INITIAL_NO_CONFIRM:
        return LifecycleEpisode(
            timestamp=timestamp,
            db_index=db_index,
            initial_outcome=INITIAL_NO_CONFIRM,
            post_outcome=POST_EXPIRED,
            bars_until_initial=None,
            bars_until_post=MAX_INITIAL_WINDOW,
            bars_held_after_initial=0,
        )

    post_outcome = POST_HELD
    post_bar: Optional[int] = None

    for i in range(initial_bar + 1, series_end + 1):
        if bool(ll_mask.iloc[i]):
            post_outcome = POST_LATER_LL
            post_bar = i
            break
        if bool(os_mask.iloc[i]):
            post_outcome = POST_LATER_OS
            post_bar = i
            break

    if post_outcome == POST_HELD:
        bars_held = series_end - initial_bar
        bars_until_post = series_end - db_index
    else:
        bars_held = post_bar - initial_bar
        bars_until_post = post_bar - db_index

    return LifecycleEpisode(
        timestamp=timestamp,
        db_index=db_index,
        initial_outcome=initial,
        post_outcome=post_outcome,
        bars_until_initial=bars_until_initial,
        bars_until_post=bars_until_post,
        bars_held_after_initial=bars_held,
    )


def analyze_lifecycle_from_arrays(
    index: pd.DatetimeIndex,
    k: pd.Series,
    d: pd.Series,
    db_mask: pd.Series,
    tb_mask: pd.Series,
    ll_mask: pd.Series,
    os_mask: pd.Series,
) -> List[LifecycleEpisode]:
    series_end = len(index) - 1
    episodes: List[LifecycleEpisode] = []
    for i in range(len(index)):
        if not bool(db_mask.iloc[i]):
            continue
        episodes.append(
            analyze_lifecycle_episode(
                i, pd.Timestamp(index[i]), k, d, tb_mask, ll_mask, os_mask, series_end,
            )
        )
    return episodes


def run_lifecycle_timeline(
    symbol: str,
    interval: str,
    bare: pd.DataFrame,
    ohlcv_cache: dict,
    *,
    warmup: int = 240,
    pipeline_fn=None,
) -> pd.DataFrame:
    """DB 에피소드 lifecycle 타임라인."""
    idx, k, d, db, tb, ll, os = _collect_bar_series(
        bare, warmup=warmup, pipeline_fn=pipeline_fn,
    )
    if len(idx) == 0:
        return pd.DataFrame()
    episodes = analyze_lifecycle_from_arrays(idx, k, d, db, tb, ll, os)
    return lifecycle_to_dataframe(episodes)


def lifecycle_to_dataframe(episodes: List[LifecycleEpisode]) -> pd.DataFrame:
    rows = []
    for ep in episodes:
        rows.append({
            "timestamp": ep.timestamp,
            "initial_outcome": ep.initial_outcome,
            "post_outcome": ep.post_outcome,
            "bars_until_initial": ep.bars_until_initial,
            "bars_until_post": ep.bars_until_post,
            "bars_held_after_initial": ep.bars_held_after_initial,
        })
    return pd.DataFrame(rows)


def summarize_lifecycle(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return {"count": 0}

    def _dist(col: str) -> Dict[str, dict]:
        vc = df[col].value_counts()
        out = {}
        for k in vc.index:
            c = int(vc[k])
            out[str(k)] = {"count": c, "ratio": c / n * 100.0}
        return out

    transition: Dict[Tuple[str, str], int] = {}
    for _, row in df.iterrows():
        key = (str(row["initial_outcome"]), str(row["post_outcome"]))
        transition[key] = transition.get(key, 0) + 1

    held_by_initial: Dict[str, List[float]] = {}
    for init in (INITIAL_CROSS, INITIAL_SLOPE, INITIAL_TB):
        sub = df[df["initial_outcome"] == init]
        if len(sub):
            held_by_initial[init] = sub["bars_held_after_initial"].dropna().astype(float).tolist()

    def _held_ratio(initial: str) -> float:
        sub = df[df["initial_outcome"] == initial]
        if sub.empty:
            return 0.0
        return float((sub["post_outcome"] == POST_HELD).sum()) / len(sub) * 100.0

    def _ll_ratio(initial: str) -> float:
        sub = df[df["initial_outcome"] == initial]
        if sub.empty:
            return 0.0
        return float((sub["post_outcome"] == POST_LATER_LL).sum()) / len(sub) * 100.0

    until_init = df["bars_until_initial"].dropna()
    held_vals = df.loc[df["initial_outcome"] != INITIAL_NO_CONFIRM, "bars_held_after_initial"].dropna()

    return {
        "count": n,
        "initial_dist": _dist("initial_outcome"),
        "post_dist": _dist("post_outcome"),
        "transition": transition,
        "mean_bars_until_initial": float(until_init.mean()) if len(until_init) else None,
        "mean_bars_held_after_initial": float(held_vals.mean()) if len(held_vals) else None,
        "max_bars_held": float(held_vals.max()) if len(held_vals) else None,
        "cross_held_pct": _held_ratio(INITIAL_CROSS),
        "slope_held_pct": _held_ratio(INITIAL_SLOPE),
        "cross_ll_pct": _ll_ratio(INITIAL_CROSS),
        "slope_ll_pct": _ll_ratio(INITIAL_SLOPE),
        "held_by_initial_avg": {
            k: float(sum(v) / len(v)) if v else None for k, v in held_by_initial.items()
        },
    }
