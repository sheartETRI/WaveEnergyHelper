"""Wave Branch Analysis — DOUBLE_BOTTOM 이후 분기 원인 관측.

기존 산출물만 소비. ML·신호 생성 없음.
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.dynamics_rules import _regime_at, _zone_at
from analysis.structure import classify_structure_at
from analysis.verdict_stability import NEUTRAL, enrich_timeline_stability, map_verdict_family
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_outcome import _find_bar_index
from analysis.wave_path_analysis import STATE_SHORT
from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]
_LAYER_SMALL = WAVE_LAYER_ROLES["small"]
STABLE_COL = "family_smoothed_3"

BRANCH_COMPLETED = "WAVE3_COMPLETED"
BRANCH_REQUIRED = "TRIPLE_BOTTOM_REQUIRED"
ANALYZED_BRANCHES = (BRANCH_COMPLETED, BRANCH_REQUIRED)

CSV_EXPORT_COLS = (
    "timestamp", "branch", "major_k", "major_d", "major_k_minus_d",
    "major_k_slope_1", "major_k_slope_3", "major_k_level_bucket",
    "major_was_oversold_recent", "major_ll_recent", "bars_since_major_ll",
    "small_k", "small_d", "small_k_minus_d", "small_db_kind",
    "family_at_db", "stable_family_at_db", "verdict_at_db",
    "structure_label_at_db", "return_pct", "success",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _k_level_bucket(k: float) -> str:
    if k is None or (isinstance(k, float) and (math.isnan(k) or math.isinf(k))):
        return "unknown"
    if k < 20:
        return "<20"
    if k < 40:
        return "20-40"
    if k < 60:
        return "40-60"
    if k < 80:
        return "60-80"
    return "80+"


def _lookup_at(ts: pd.Timestamp, timeline: pd.DataFrame, col: str, default="") -> str:
    if timeline.empty or col not in timeline.columns:
        return default
    keyed = timeline.set_index("timestamp")
    if ts in keyed.index:
        v = keyed.loc[ts, col]
        if isinstance(v, pd.Series):
            v = v.iloc[-1]
        return str(v) if pd.notna(v) else default
    loc = keyed.index.searchsorted(ts)
    if loc < len(keyed):
        v = keyed.iloc[loc][col]
        return str(v) if pd.notna(v) else default
    if len(keyed):
        v = keyed.iloc[-1][col]
        return str(v) if pd.notna(v) else default
    return default


def extract_double_bottom_events(tracker: pd.DataFrame) -> List[dict]:
    """Tracker에서 DOUBLE_BOTTOM 진입 이벤트 + 분기 라벨."""
    tr = tracker.sort_values("timestamp").reset_index(drop=True)
    events: List[dict] = []
    for i in range(1, len(tr)):
        cur = str(tr.iloc[i]["state"])
        prev = str(tr.iloc[i - 1]["state"])
        if cur != "DOUBLE_BOTTOM_CANDIDATE":
            continue
        if prev == "DOUBLE_BOTTOM_CANDIDATE":
            continue
        branch = resolve_branch(tr, i)
        events.append({
            "timestamp": pd.Timestamp(tr.iloc[i]["timestamp"]),
            "tracker_idx": i,
            "branch": branch,
        })
    return events


def resolve_branch(tracker: pd.DataFrame, db_idx: int) -> str:
    """DOUBLE_BOTTOM 이후 첫 wave 분기."""
    for j in range(db_idx + 1, len(tracker)):
        raw = str(tracker.iloc[j]["state"])
        short = STATE_SHORT.get(raw, raw)
        if raw == "DOUBLE_BOTTOM_CANDIDATE":
            continue
        if short == BRANCH_COMPLETED:
            return BRANCH_COMPLETED
        if short == BRANCH_REQUIRED:
            return BRANCH_REQUIRED
        return "OTHER"
    return "OTHER"


def _bars_since(mask: pd.Series) -> Optional[int]:
    arr = mask.to_numpy()
    for i in range(len(arr) - 1, -1, -1):
        if arr[i]:
            return len(arr) - 1 - i
    return None


def _extract_features(
    pipeline: pd.DataFrame,
    pos: int,
    verdict_tl: pd.DataFrame,
    stab_tl: pd.DataFrame,
) -> dict:
    row = pipeline.iloc[pos]
    ts = pd.Timestamp(pipeline.index[pos])
    k_col = f"stoch_k_{_LAYER_LARGE}"
    d_col = f"stoch_d_{_LAYER_LARGE}"
    sk_col = f"stoch_k_{_LAYER_SMALL}"
    sd_col = f"stoch_d_{_LAYER_SMALL}"
    db_kind_col = f"stoch_db_kind_{_LAYER_SMALL}"
    ll_kind_col = f"stoch_db_kind_{_LAYER_LARGE}"
    db_col = f"stoch_db_{_LAYER_LARGE}"
    sdb_col = f"stoch_db_{_LAYER_SMALL}"

    major_k = float(row[k_col]) if k_col in pipeline.columns and pd.notna(row[k_col]) else None
    major_d = float(row[d_col]) if d_col in pipeline.columns and pd.notna(row[d_col]) else None
    kd = (major_k - major_d) if major_k is not None and major_d is not None else None

    k_series = pipeline[k_col] if k_col in pipeline.columns else pd.Series(dtype=float)
    slope_1 = None
    slope_3 = None
    d_slope_3 = None
    if major_k is not None and pos >= 1 and pd.notna(k_series.iloc[pos - 1]):
        slope_1 = major_k - float(k_series.iloc[pos - 1])
    if major_k is not None and pos >= 3 and pd.notna(k_series.iloc[pos - 3]):
        slope_3 = major_k - float(k_series.iloc[pos - 3])
    if d_col in pipeline.columns and pos >= 3:
        d_series = pipeline[d_col]
        if pd.notna(row[d_col]) and pd.notna(d_series.iloc[pos - 3]):
            d_slope_3 = float(row[d_col]) - float(d_series.iloc[pos - 3])

    oversold_thr = WAVE_ENERGY_PARAMS["oversold"]
    win5 = pipeline.iloc[max(0, pos - 4): pos + 1]
    major_os_recent = False
    if k_col in win5.columns:
        major_os_recent = bool((win5[k_col] < oversold_thr).any())

    win10 = pipeline.iloc[max(0, pos - 9): pos + 1]
    major_ll_recent = False
    if ll_kind_col in win10.columns:
        major_ll_recent = bool((win10[ll_kind_col] == "LL").any())
    if db_col in win10.columns and ll_kind_col in win10.columns:
        major_ll_recent = major_ll_recent or bool(
            ((win10[db_col].notna()) & (win10[ll_kind_col] == "LL")).any()
        )

    bars_ll = None
    bars_os = None
    if ll_kind_col in pipeline.columns:
        bars_ll = _bars_since(pipeline.iloc[: pos + 1][ll_kind_col] == "LL")
    if k_col in pipeline.columns:
        bars_os = _bars_since(pipeline.iloc[: pos + 1][k_col] < oversold_thr)

    small_k = float(row[sk_col]) if sk_col in pipeline.columns and pd.notna(row[sk_col]) else None
    small_d = float(row[sd_col]) if sd_col in pipeline.columns and pd.notna(row[sd_col]) else None
    skd = (small_k - small_d) if small_k is not None and small_d is not None else None
    small_db_kind = ""
    if db_kind_col in pipeline.columns and pd.notna(row.get(db_kind_col)):
        small_db_kind = str(row[db_kind_col])

    win20 = pipeline.iloc[max(0, pos - 19): pos + 1]
    small_tb_recent = False
    tb_col = f"stoch_tb_{_LAYER_SMALL}"
    if tb_col in win20.columns:
        small_tb_recent = bool(win20[tb_col].notna().any())

    recent_db = 0
    if sdb_col in win20.columns:
        hits = win20[sdb_col].notna()
        prev = False
        for h in hits:
            if h and not prev:
                recent_db += 1
            prev = bool(h)

    close = pipeline["close"]
    ret_10 = ret_20 = ret_40 = None
    if pos >= 10:
        ret_10 = (float(close.iloc[pos]) - float(close.iloc[pos - 10])) / float(close.iloc[pos - 10]) * 100
    if pos >= 20:
        ret_20 = (float(close.iloc[pos]) - float(close.iloc[pos - 20])) / float(close.iloc[pos - 20]) * 100
        rets = close.iloc[pos - 19: pos + 1].pct_change().dropna()
        vol_20 = float(rets.std() * 100) if len(rets) else None
        roll_max = close.iloc[max(0, pos - 19): pos + 1].max()
        dd_20 = (float(close.iloc[pos]) - float(roll_max)) / float(roll_max) * 100
    else:
        vol_20 = dd_20 = None
    if pos >= 40:
        ret_40 = (float(close.iloc[pos]) - float(close.iloc[pos - 40])) / float(close.iloc[pos - 40]) * 100

    category = _lookup_at(ts, stab_tl, "category", "판단불가")
    regime = _regime_at(row)
    zone = _zone_at(regime, row.get("close"), row.get("MA20"), row.get("MA60"))
    structure = classify_structure_at(pipeline, pos)

    return {
        "major_k": major_k,
        "major_d": major_d,
        "major_k_minus_d": kd,
        "major_k_slope_1": slope_1,
        "major_k_slope_3": slope_3,
        "major_d_slope_3": d_slope_3,
        "major_k_level_bucket": _k_level_bucket(major_k) if major_k is not None else "unknown",
        "major_was_oversold_recent": major_os_recent,
        "major_ll_recent": major_ll_recent,
        "bars_since_major_ll": bars_ll,
        "bars_since_major_oversold": bars_os,
        "small_k": small_k,
        "small_d": small_d,
        "small_k_minus_d": skd,
        "small_db_kind": small_db_kind,
        "small_tb_recent": small_tb_recent,
        "recent_small_db_count_20": recent_db,
        "ret_10": ret_10,
        "ret_20": ret_20,
        "ret_40": ret_40,
        "volatility_20": vol_20 if pos >= 20 else None,
        "drawdown_20": dd_20 if pos >= 20 else None,
        "verdict_at_db": _lookup_at(ts, verdict_tl, "verdict", ""),
        "category_at_db": category,
        "family_at_db": map_verdict_family(category),
        "stable_family_at_db": _lookup_at(ts, stab_tl, STABLE_COL, NEUTRAL),
        "structure_label_at_db": structure or "",
        "regime_at_db": regime,
        "zone_at_db": zone,
    }


def _link_episode(
    db_ts: pd.Timestamp,
    lifecycle: pd.DataFrame,
    expectancy: pd.DataFrame,
) -> Optional[dict]:
    lc = lifecycle[lifecycle["timestamp"] <= db_ts]
    if lc.empty:
        return None
    ep_ts = pd.Timestamp(lc.iloc[-1]["timestamp"])
    exp = expectancy[expectancy["timestamp"] == ep_ts]
    if exp.empty:
        return None
    row = exp.iloc[0]
    success = row["success"]
    if isinstance(success, str):
        success = success.lower() in ("true", "1", "yes")
    return {
        "episode_ts": ep_ts,
        "return_pct": float(row["return_pct"]),
        "success": bool(success),
    }


def build_branch_analysis(
    symbol: str,
    interval: str,
    ohlcv: pd.DataFrame,
    pipeline_df: pd.DataFrame,
) -> pd.DataFrame:
    tracker_path = _csv_path("wave_tracker", symbol, interval)
    if not os.path.isfile(tracker_path):
        return pd.DataFrame()

    tracker = pd.read_csv(tracker_path, parse_dates=["timestamp"])
    lifecycle = pd.read_csv(
        _csv_path("wave_confirmation_lifecycle", symbol, interval),
        parse_dates=["timestamp"],
    )
    expectancy = pd.read_csv(
        _csv_path("wave_expectancy", symbol, interval),
        parse_dates=["timestamp"],
    )
    verdict = pd.read_csv(
        _csv_path("verdict_timeline", symbol, interval),
        parse_dates=["timestamp"],
    )
    stab = enrich_timeline_stability(verdict)

    events = extract_double_bottom_events(tracker)
    rows: List[dict] = []
    for ev in events:
        ts = ev["timestamp"]
        pos = _find_bar_index(ohlcv, ts)
        if pos is None or pipeline_df is None or pos >= len(pipeline_df):
            continue
        feats = _extract_features(pipeline_df, pos, verdict, stab)
        ep = _link_episode(ts, lifecycle, expectancy)
        row = {
            "timestamp": ts,
            "branch": ev["branch"],
            **feats,
            "return_pct": ep["return_pct"] if ep else None,
            "success": ep["success"] if ep else None,
            "episode_ts": ep["episode_ts"] if ep else None,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def export_branch_csv(df: pd.DataFrame, path: str) -> None:
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    df[cols].to_csv(path, index=False)


def _pooled_std(a: pd.Series, b: pd.Series) -> float:
    a = a.dropna()
    b = b.dropna()
    if len(a) < 2 and len(b) < 2:
        return 0.0
    if len(a) < 2:
        return float(b.std(ddof=1)) if len(b) > 1 else 0.0
    if len(b) < 2:
        return float(a.std(ddof=1)) if len(a) > 1 else 0.0
    na, nb = len(a), len(b)
    va, vb = float(a.var(ddof=1)), float(b.var(ddof=1))
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    return pooled if pooled > 1e-12 else 0.0


def effect_size(a: pd.Series, b: pd.Series) -> float:
    pooled = _pooled_std(a, b)
    if pooled == 0:
        return 0.0
    return abs(float(a.mean()) - float(b.mean())) / pooled


def categorical_lift(
    df: pd.DataFrame,
    col: str,
    branch_col: str = "branch",
    target: str = BRANCH_REQUIRED,
) -> List[dict]:
    base = df[df[branch_col].isin(ANALYZED_BRANCHES)]
    if base.empty:
        return []
    p_req = (base[branch_col] == target).mean()
    if p_req == 0:
        return []

    rows = []
    for val, grp in base.groupby(col, dropna=False):
        n = len(grp)
        if n == 0:
            continue
        rate = (grp[branch_col] == target).mean()
        lift = rate / p_req if p_req else 0.0
        rows.append({
            "feature": col,
            "value": str(val),
            "n": n,
            "required_rate": rate * 100.0,
            "lift": lift,
        })
    return rows


NUMERIC_FEATURES = (
    "major_k", "major_d", "major_k_minus_d", "major_k_slope_1", "major_k_slope_3",
    "major_d_slope_3", "bars_since_major_ll", "bars_since_major_oversold",
    "small_k", "small_d", "small_k_minus_d", "recent_small_db_count_20",
    "ret_10", "ret_20", "ret_40", "volatility_20", "drawdown_20",
)

CATEGORICAL_FEATURES = (
    "major_k_level_bucket", "major_was_oversold_recent", "major_ll_recent",
    "small_db_kind", "small_tb_recent", "family_at_db", "stable_family_at_db",
    "category_at_db", "structure_label_at_db", "regime_at_db", "zone_at_db",
)


def summarize_branch_analysis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    analyzed = df[df["branch"].isin(ANALYZED_BRANCHES)].copy()
    other_count = int((~df["branch"].isin(ANALYZED_BRANCHES)).sum())

    branch_counts = df["branch"].value_counts().to_dict()
    completed = analyzed[analyzed["branch"] == BRANCH_COMPLETED]
    required = analyzed[analyzed["branch"] == BRANCH_REQUIRED]

    perf = {}
    for name, grp in (
        (BRANCH_COMPLETED, completed),
        (BRANCH_REQUIRED, required),
    ):
        linked = grp.dropna(subset=["return_pct"])
        if linked.empty:
            perf[name] = {"count": len(grp), "n": 0}
            continue
        m = compute_expectancy_metrics(linked["return_pct"])
        perf[name] = {**m, "count": len(grp)}

    numeric_cmp: List[dict] = []
    for col in NUMERIC_FEATURES:
        if col not in analyzed.columns:
            continue
        a = completed[col]
        b = required[col]
        if a.dropna().empty and b.dropna().empty:
            continue
        numeric_cmp.append({
            "feature": col,
            "completed_avg": float(a.mean()) if a.notna().any() else None,
            "completed_median": float(a.median()) if a.notna().any() else None,
            "completed_std": float(a.std()) if a.notna().sum() > 1 else None,
            "required_avg": float(b.mean()) if b.notna().any() else None,
            "required_median": float(b.median()) if b.notna().any() else None,
            "required_std": float(b.std()) if b.notna().sum() > 1 else None,
            "effect_size": effect_size(a, b),
        })

    cat_lifts: List[dict] = []
    for col in CATEGORICAL_FEATURES:
        if col not in analyzed.columns:
            continue
        cat_lifts.extend(categorical_lift(analyzed, col))

    top_numeric = sorted(numeric_cmp, key=lambda x: x["effect_size"], reverse=True)
    top_categorical = sorted(cat_lifts, key=lambda x: x["lift"], reverse=True)

    return {
        "count": len(df),
        "analyzed_count": len(analyzed),
        "other_count": other_count,
        "branch_counts": branch_counts,
        "branch_performance": perf,
        "numeric_comparison": numeric_cmp,
        "categorical_lift": cat_lifts,
        "top_numeric_separators": top_numeric[:20],
        "top_categorical_separators": top_categorical[:20],
    }
