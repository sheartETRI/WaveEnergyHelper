"""Wave Path Analysis — DB 기준 상태 전이 경로 관측.

기존 Tracker/Lifecycle/Survival/Exit/Expectancy 산출물만 소비.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_exit import POLICY_A
from analysis.wave_segmentation import MIN_SAMPLE, SHORT_INITIAL

PATH_SEP = " → "

RESET_STATES = frozenset({"NONE", "INVALIDATED"})

WAVE_PATH_STATES = frozenset({
    "WAVE3_CANDIDATE",
    "WAVE3_ACTIVE",
    "DOUBLE_BOTTOM",
    "TRIPLE_BOTTOM_REQUIRED",
    "TRIPLE_BOTTOM_CONFIRMED",
    "WAVE3_COMPLETED",
})

STATE_SHORT = {
    "DOUBLE_BOTTOM_CANDIDATE": "DOUBLE_BOTTOM",
    "WAVE3_CANDIDATE": "WAVE3_CANDIDATE",
    "WAVE3_ACTIVE": "WAVE3_ACTIVE",
    "TRIPLE_BOTTOM_REQUIRED": "TRIPLE_BOTTOM_REQUIRED",
    "TRIPLE_BOTTOM_CONFIRMED": "TRIPLE_BOTTOM_CONFIRMED",
    "WAVE3_COMPLETED": "WAVE3_COMPLETED",
}


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _short_state(state: str) -> str:
    return STATE_SHORT.get(state, state)


def _episode_start_idx(tracker: pd.DataFrame, db_idx: int) -> int:
    for i in range(db_idx, -1, -1):
        if tracker.iloc[i]["state"] in RESET_STATES:
            return i + 1
    return 0


def extract_state_sequence(
    tracker: pd.DataFrame,
    db_ts: pd.Timestamp,
    bars_until_entry: int,
) -> List[str]:
    """DB~진입 구간(+에피소드 시작) 상태 전이 시퀀스 (압축)."""
    tr = tracker.sort_values("timestamp").reset_index(drop=True)
    hits = tr.index[tr["timestamp"] == db_ts]
    if len(hits) == 0:
        idx = tr["timestamp"].searchsorted(db_ts)
        if idx >= len(tr):
            return []
        db_idx = int(idx)
    else:
        db_idx = int(hits[0])

    entry_idx = min(db_idx + max(int(bars_until_entry), 0), len(tr) - 1)
    start_idx = _episode_start_idx(tr, db_idx)
    segment = tr.iloc[start_idx: entry_idx + 1]

    seq: List[str] = []
    prev: Optional[str] = None
    for _, row in segment.iterrows():
        raw = str(row["state"])
        if raw in RESET_STATES:
            continue
        short = _short_state(raw)
        if short not in WAVE_PATH_STATES:
            continue
        if short != prev:
            seq.append(short)
            prev = short
    return seq


def compress_path(states: List[str], initial: str, success: bool) -> str:
    """상태 시퀀스 + initial + TP3 결과를 Path 문자열로."""
    outcome = "TP3_WIN" if success else "TP3_LOSS"
    parts = list(states) + [initial, outcome]
    return PATH_SEP.join(parts)


def build_path_rows(symbol: str, interval: str) -> pd.DataFrame:
    exp_path = _path("wave_expectancy", symbol, interval)
    if not os.path.isfile(exp_path):
        return pd.DataFrame()

    exp = pd.read_csv(exp_path, parse_dates=["timestamp"])
    if exp.empty:
        return pd.DataFrame()

    lc = pd.read_csv(
        _path("wave_confirmation_lifecycle", symbol, interval),
        parse_dates=["timestamp"],
    )
    sv = pd.read_csv(
        _path("wave_survival", symbol, interval),
        parse_dates=["timestamp"],
    )
    tracker = pd.read_csv(
        _path("wave_tracker", symbol, interval),
        parse_dates=["timestamp"],
    )

    lc_keyed = lc.set_index("timestamp")
    sv_keyed = sv.set_index("timestamp") if not sv.empty else None

    rows: List[dict] = []
    for _, ep in exp.iterrows():
        db_ts = pd.Timestamp(ep["timestamp"])
        if db_ts not in lc_keyed.index:
            continue
        lc_row = lc_keyed.loc[db_ts]
        if isinstance(lc_row, pd.DataFrame):
            lc_row = lc_row.iloc[0]

        delay = lc_row.get("bars_until_initial")
        if pd.isna(delay):
            continue

        success = bool(ep["success"])
        if isinstance(ep["success"], str):
            success = ep["success"].lower() in ("true", "1", "yes")

        initial_raw = str(
            ep.get("initial_type")
            or lc_row.get("initial_outcome", "")
        )
        initial = SHORT_INITIAL.get(initial_raw, initial_raw)

        states = extract_state_sequence(tracker, db_ts, int(delay))
        if not states:
            entry_state = _short_state(str(ep.get("state", "OTHER")))
            if entry_state in WAVE_PATH_STATES:
                states = [entry_state]
            else:
                states = ["NONE"]

        path = compress_path(states, initial, success)

        surv = float(lc_row.get("bars_held_after_initial", 0))
        if sv_keyed is not None and db_ts in sv_keyed.index:
            sv_row = sv_keyed.loc[db_ts]
            if isinstance(sv_row, pd.DataFrame):
                sv_row = sv_row.iloc[0]
            surv = float(sv_row.get("survival_bars", surv))

        rows.append({
            "timestamp": db_ts,
            "path": path,
            "wave_states": PATH_SEP.join(states),
            "success": success,
            "return_pct": float(ep["return_pct"]),
            "expectancy_group": ep.get("expectancy_group", ""),
            "initial_type": initial,
            "survival_bars": surv,
        })

    return pd.DataFrame(rows)


def _path_metrics(group: pd.DataFrame) -> dict:
    m = compute_expectancy_metrics(group["return_pct"])
    m["path"] = group["path"].iloc[0]
    m["avg_survival"] = float(group["survival_bars"].mean())
    m["avg_return"] = float(group["return_pct"].mean())
    return m


def aggregate_paths(df: pd.DataFrame) -> List[dict]:
    """동일 Path 집계."""
    if df.empty:
        return []
    rows = []
    for path, grp in df.groupby("path"):
        rows.append(_path_metrics(grp))
    return rows


def compute_transitions(df: pd.DataFrame) -> Tuple[List[dict], Dict[str, float]]:
    """Markov 형태 전이 확률 (wave state only)."""
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        states = [
            s for s in str(row.get("wave_states", "")).split(PATH_SEP)
            if s in WAVE_PATH_STATES
        ]
        for i in range(len(states) - 1):
            counts[states[i]][states[i + 1]] += 1

    transitions: List[dict] = []
    probs: Dict[str, float] = {}
    for src, dsts in counts.items():
        total = sum(dsts.values())
        for dst, cnt in dsts.items():
            pct = cnt / total * 100.0 if total else 0.0
            key = f"{src} → {dst}"
            transitions.append({
                "from": src,
                "to": dst,
                "count": cnt,
                "pct": pct,
                "label": key,
            })
            probs[key] = pct

    transitions.sort(key=lambda x: x["count"], reverse=True)
    return transitions, probs


def transition_probability(transitions: List[dict], src: str, dst: str) -> Optional[float]:
    for t in transitions:
        if t["from"] == src and t["to"] == dst:
            return t["pct"]
    return None


def summarize_paths(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    aggregated = aggregate_paths(df)
    eligible = [p for p in aggregated if p.get("n", 0) >= MIN_SAMPLE]

    winning_pool = [p for p in eligible if p.get("expectancy", 0) > 0]
    losing_pool = [p for p in eligible if p.get("expectancy", 0) <= 0]
    top_winning = sorted(
        winning_pool, key=lambda x: x.get("expectancy", -999), reverse=True,
    )
    top_losing = sorted(
        losing_pool, key=lambda x: x.get("expectancy", 999),
    )

    transitions, _ = compute_transitions(df)

    path_counts = (
        df.groupby("path").size().sort_values(ascending=False).to_dict()
    )

    return {
        "count": len(df),
        "unique_paths": len(aggregated),
        "by_path": aggregated,
        "path_counts": path_counts,
        "top_winning_paths": top_winning,
        "top_losing_paths": top_losing,
        "top10_paths": sorted(
            aggregated, key=lambda x: x.get("n", 0), reverse=True,
        )[:10],
        "transitions": transitions,
        "tb_required_from_db": transition_probability(
            transitions, "DOUBLE_BOTTOM", "TRIPLE_BOTTOM_REQUIRED",
        ),
        "w3_completed_from_db": transition_probability(
            transitions, "DOUBLE_BOTTOM", "WAVE3_COMPLETED",
        ),
        "tb_required_from_active": transition_probability(
            transitions, "WAVE3_ACTIVE", "TRIPLE_BOTTOM_REQUIRED",
        ),
        "w3_completed_from_active": transition_probability(
            transitions, "WAVE3_ACTIVE", "WAVE3_COMPLETED",
        ),
    }
