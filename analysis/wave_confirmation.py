"""소파동 DB 이후 대파동 K 전환 지연시간 — 관측용 Confirmation Window 분석.

기존 verdict / stability / dynamics / Wave Tracker 상태 머신과 독립.
신규 검출기 없음 — 기존 stoch 컬럼만 사용.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from analysis.wave_tracker import _pattern_edge
from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]
_LAYER_SMALL = WAVE_LAYER_ROLES["small"]

CONFIRM_WINDOWS = (3, 5, 8, 13)

OUTCOME_INVALIDATED = "INVALIDATED"
OUTCOME_CROSS = "CROSS_CONFIRMED"
OUTCOME_SLOPE = "SLOPE_CONFIRMED"
OUTCOME_TB_CONFIRMED = "TB_CONFIRMED"
OUTCOME_TB_REQUIRED = "TB_REQUIRED"
OUTCOME_NO_CONFIRM = "NO_CONFIRM_WITHIN_WINDOW"

ALL_OUTCOMES = (
    OUTCOME_INVALIDATED,
    OUTCOME_CROSS,
    OUTCOME_SLOPE,
    OUTCOME_TB_CONFIRMED,
    OUTCOME_TB_REQUIRED,
    OUTCOME_NO_CONFIRM,
)


@dataclass
class DBEpisode:
    timestamp: pd.Timestamp
    db_index: int
    major_k_at_db: float
    major_d_at_db: float
    confirm_cross_delay: Optional[int] = None
    confirm_slope_delay: Optional[int] = None
    confirmed_by_cross: bool = False
    confirmed_by_slope: bool = False
    tb_index: Optional[int] = None
    invalidated_before_confirm: bool = False
    invalidation_index: Optional[int] = None
    k_fell_after_db: bool = False
    required_tb_before_confirm: bool = False
    final_outcome: str = OUTCOME_NO_CONFIRM
    within: Dict[int, Dict[str, bool]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.within:
            self.within = {w: {"cross": False, "slope": False} for w in CONFIRM_WINDOWS}


def _k_d_cols() -> tuple[str, str]:
    return f"stoch_k_{_LAYER_LARGE}", f"stoch_d_{_LAYER_LARGE}"


def cross_confirm_at(k: pd.Series, d: pd.Series, idx: int) -> bool:
    """K가 D를 상향 돌파 (확정형)."""
    if idx < 0 or idx >= len(k):
        return False
    if idx == 0:
        return False
    kv_prev, dv_prev = k.iloc[idx - 1], d.iloc[idx - 1]
    kv, dv = k.iloc[idx], d.iloc[idx]
    if pd.isna(kv_prev) or pd.isna(dv_prev) or pd.isna(kv) or pd.isna(dv):
        return False
    return float(kv_prev) <= float(dv_prev) and float(kv) > float(dv)


def slope_confirm_at(k: pd.Series, idx: int) -> bool:
    """K 기울기 상승 전환 (근사형)."""
    if idx < 2 or idx >= len(k):
        return False
    k0, k1, k2 = k.iloc[idx - 2], k.iloc[idx - 1], k.iloc[idx]
    if pd.isna(k0) or pd.isna(k1) or pd.isna(k2):
        return False
    return float(k2) > float(k1) and float(k1) <= float(k0)


def _finalize_episode(ep: DBEpisode) -> None:
    """에피소드 종료 시 final_outcome 및 within_* 확정."""
    for w in CONFIRM_WINDOWS:
        ep.within[w]["cross"] = (
            ep.confirm_cross_delay is not None and ep.confirm_cross_delay <= w
        )
        ep.within[w]["slope"] = (
            ep.confirm_slope_delay is not None and ep.confirm_slope_delay <= w
        )

    if ep.invalidation_index is not None:
        ep.final_outcome = OUTCOME_INVALIDATED
    elif ep.confirmed_by_cross:
        ep.final_outcome = OUTCOME_CROSS
    elif ep.confirmed_by_slope:
        ep.final_outcome = OUTCOME_SLOPE
    elif ep.tb_index is not None:
        ep.final_outcome = OUTCOME_TB_CONFIRMED
    elif ep.k_fell_after_db:
        ep.final_outcome = OUTCOME_TB_REQUIRED
    else:
        ep.final_outcome = OUTCOME_NO_CONFIRM

    cross_bar = (
        ep.db_index + ep.confirm_cross_delay
        if ep.confirm_cross_delay is not None
        else None
    )
    slope_bar = (
        ep.db_index + ep.confirm_slope_delay
        if ep.confirm_slope_delay is not None
        else None
    )
    if ep.tb_index is not None:
        tb_before_cross = cross_bar is None or ep.tb_index < cross_bar
        tb_before_slope = slope_bar is None or ep.tb_index < slope_bar
        ep.required_tb_before_confirm = bool(tb_before_cross and tb_before_slope)


def analyze_episodes_from_arrays(
    index: pd.Index,
    k: pd.Series,
    d: pd.Series,
    db_edge_mask: pd.Series,
    tb_edge_mask: pd.Series,
    ll_new_mask: pd.Series,
    oversold_entry_mask: pd.Series,
) -> List[DBEpisode]:
    """봉별 시계열 배열에서 DB 에피소드 분석 (테스트·사후 분석용)."""
    episodes: List[DBEpisode] = []
    active: List[DBEpisode] = []

    for i in range(len(index)):
        ts = pd.Timestamp(index[i])

        if bool(db_edge_mask.iloc[i]):
            kv = float(k.iloc[i]) if pd.notna(k.iloc[i]) else float("nan")
            dv = float(d.iloc[i]) if pd.notna(d.iloc[i]) else float("nan")
            ep = DBEpisode(
                timestamp=ts,
                db_index=i,
                major_k_at_db=kv,
                major_d_at_db=dv,
            )
            if cross_confirm_at(k, d, i):
                ep.confirm_cross_delay = 0
                ep.confirmed_by_cross = True
            if slope_confirm_at(k, i):
                ep.confirm_slope_delay = 0
                ep.confirmed_by_slope = True
            episodes.append(ep)
            active.append(ep)

        for ep in active:
            delay = i - ep.db_index
            if delay <= 0:
                continue

            if ep.invalidation_index is None:
                if bool(ll_new_mask.iloc[i]) or bool(oversold_entry_mask.iloc[i]):
                    ep.invalidation_index = i
                    if not ep.confirmed_by_cross and not ep.confirmed_by_slope:
                        ep.invalidated_before_confirm = True

            if not ep.confirmed_by_cross and cross_confirm_at(k, d, i):
                ep.confirm_cross_delay = delay
                ep.confirmed_by_cross = True

            if not ep.confirmed_by_slope and slope_confirm_at(k, i):
                ep.confirm_slope_delay = delay
                ep.confirmed_by_slope = True

            if ep.tb_index is None and bool(tb_edge_mask.iloc[i]):
                ep.tb_index = i

            if not ep.k_fell_after_db and i >= 1 and pd.notna(k.iloc[i]) and pd.notna(k.iloc[i - 1]):
                if float(k.iloc[i]) < float(k.iloc[i - 1]):
                    ep.k_fell_after_db = True

    for ep in active:
        _finalize_episode(ep)
    return episodes


def extract_bar_flags(
    base_df: pd.DataFrame,
    prev_major_oversold: bool,
) -> dict:
    """절단 df 마지막 봉 기준 기존 신호 플래그."""
    k_col, d_col = _k_d_cols()
    oversold_thr = WAVE_ENERGY_PARAMS["oversold"]

    major_k = float("nan")
    major_d = float("nan")
    if base_df is not None and not base_df.empty:
        if k_col in base_df.columns and base_df[k_col].notna().any():
            major_k = float(base_df[k_col].dropna().iloc[-1])
        if d_col in base_df.columns and base_df[d_col].notna().any():
            major_d = float(base_df[d_col].dropna().iloc[-1])

    major_oversold = pd.notna(major_k) and major_k < oversold_thr
    oversold_entry = major_oversold and not prev_major_oversold

    db_new, _ = _pattern_edge(base_df, _LAYER_SMALL, "db")
    tb_new, _ = _pattern_edge(base_df, _LAYER_SMALL, "tb")
    ll_new, ll_kind = _pattern_edge(base_df, _LAYER_LARGE, "db")
    ll_new = ll_new and ll_kind == "LL"

    return {
        "major_k": major_k,
        "major_d": major_d,
        "major_oversold": major_oversold,
        "oversold_entry": oversold_entry,
        "db_edge": db_new,
        "tb_edge": tb_new,
        "ll_new": ll_new,
    }


def run_episodes_timeline(
    symbol: str,
    interval: str,
    bare: pd.DataFrame,
    ohlcv_cache: dict,
    *,
    warmup: int = 240,
    pipeline_fn=None,
) -> pd.DataFrame:
    """봉별 룩어헤드 없이 DB 에피소드 타임라인 생성.

    전체 bare에 파이프라인 1회 적용 후 iloc[:i+1] 절단 — truncate 재계산과 동치.
    """
    from display.asof import run_indicator_pipeline

    if pipeline_fn is None:
        pipeline_fn = run_indicator_pipeline

    if bare is None or bare.empty:
        return pd.DataFrame()

    full_df = pipeline_fn(bare)

    rows_k: List[float] = []
    rows_d: List[float] = []
    rows_db: List[bool] = []
    rows_tb: List[bool] = []
    rows_ll: List[bool] = []
    rows_os: List[bool] = []
    index_list: List[pd.Timestamp] = []

    prev_oversold = False
    start = min(warmup, len(bare) - 1)

    for i in range(start, len(bare)):
        as_of = bare.index[i]
        cut_df = full_df.iloc[: i + 1]
        flags = extract_bar_flags(cut_df, prev_oversold)
        prev_oversold = flags["major_oversold"]

        index_list.append(pd.Timestamp(as_of))
        rows_k.append(flags["major_k"])
        rows_d.append(flags["major_d"])
        rows_db.append(flags["db_edge"])
        rows_tb.append(flags["tb_edge"])
        rows_ll.append(flags["ll_new"])
        rows_os.append(flags["oversold_entry"])

    if not index_list:
        return pd.DataFrame()

    idx = pd.DatetimeIndex(index_list)
    k_s = pd.Series(rows_k, index=idx)
    d_s = pd.Series(rows_d, index=idx)
    episodes = analyze_episodes_from_arrays(
        idx,
        k_s,
        d_s,
        pd.Series(rows_db, index=idx),
        pd.Series(rows_tb, index=idx),
        pd.Series(rows_ll, index=idx),
        pd.Series(rows_os, index=idx),
    )
    return episodes_to_dataframe(episodes)


def episodes_to_dataframe(episodes: List[DBEpisode]) -> pd.DataFrame:
    rows = []
    for ep in episodes:
        row = {
            "timestamp": ep.timestamp,
            "db_index": ep.db_index,
            "major_k_at_db": ep.major_k_at_db,
            "major_d_at_db": ep.major_d_at_db,
            "confirm_cross_delay": ep.confirm_cross_delay,
            "confirm_slope_delay": ep.confirm_slope_delay,
            "confirmed_by_cross": ep.confirmed_by_cross,
            "confirmed_by_slope": ep.confirmed_by_slope,
            "required_tb_before_confirm": ep.required_tb_before_confirm,
            "tb_index": ep.tb_index,
            "invalidated_before_confirm": ep.invalidated_before_confirm,
            "final_outcome": ep.final_outcome,
        }
        for w in CONFIRM_WINDOWS:
            row[f"within_{w}_cross"] = ep.within[w]["cross"]
            row[f"within_{w}_slope"] = ep.within[w]["slope"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_episodes(df: pd.DataFrame) -> dict:
    """리포트용 집계."""
    n = len(df)
    if n == 0:
        return {"count": 0}

    outcomes = df["final_outcome"].value_counts()
    pct = lambda k: float(outcomes.get(k, 0)) / n * 100.0

    cross_delays = df.loc[df["confirm_cross_delay"].notna(), "confirm_cross_delay"]
    slope_delays = df.loc[df["confirm_slope_delay"].notna(), "confirm_slope_delay"]

    delay_dist: Dict[int, Dict[str, int]] = {}
    for d in range(int(max(
        cross_delays.max() if len(cross_delays) else 0,
        slope_delays.max() if len(slope_delays) else 0,
        13,
    )) + 1):
        delay_dist[d] = {
            "cross": int((cross_delays == d).sum()) if len(cross_delays) else 0,
            "slope": int((slope_delays == d).sum()) if len(slope_delays) else 0,
        }

    window_stats = {}
    for w in CONFIRM_WINDOWS:
        window_stats[w] = {
            "cross": float(df[f"within_{w}_cross"].sum()) / n * 100.0 if n else 0.0,
            "slope": float(df[f"within_{w}_slope"].sum()) / n * 100.0 if n else 0.0,
        }

    return {
        "count": n,
        "cross_pct": pct(OUTCOME_CROSS),
        "slope_pct": pct(OUTCOME_SLOPE),
        "tb_required_pct": pct(OUTCOME_TB_REQUIRED),
        "tb_confirmed_pct": pct(OUTCOME_TB_CONFIRMED),
        "invalidated_pct": pct(OUTCOME_INVALIDATED),
        "no_confirm_pct": pct(OUTCOME_NO_CONFIRM),
        "mean_cross_delay": float(cross_delays.mean()) if len(cross_delays) else None,
        "mean_slope_delay": float(slope_delays.mean()) if len(slope_delays) else None,
        "delay_dist": delay_dist,
        "window_stats": window_stats,
        "outcomes": outcomes.to_dict(),
    }
