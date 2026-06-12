"""Wave Grade Failure — Early Warning 실패 원인 관측 분석.

Early Warning/Origin/Rule Grading 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import BRANCH_COMPLETED, BRANCH_REQUIRED, effect_size
from analysis.wave_generalization import (
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
)
from analysis.wave_grade_early_warning import (
    HORIZON,
    _grade_a_positions,
    _load_origin_events,
    _rule_fn,
    build_labeled_snapshots,
    generate_candidates,
)
from analysis.wave_grade_origin import (
    GRADE_A,
    extract_origin_features,
    features_at_offset,
    _load_branch_df,
    _lookup_branch,
)
from analysis.wave_outcome import _find_bar_index
from analysis.wave_path_analysis import STATE_SHORT, WAVE_PATH_STATES
from analysis.wave_regime_analysis import _load_pipeline

BEST_CANDIDATE = (
    ("major_k_slope_1", ">", 0),
    ("major_k_minus_d", ">", 0),
    ("macd", ">", 0),
)

FAILURE_CAUSES = (
    "RSI_DROP",
    "MAJOR_K_REVERSAL",
    "MACD_WEAKENING",
    "EMA_SLOPE_BAD",
    "MULTI_FAILURE",
)

CAUSE_CHECKS = (
    ("RSI_DROP", lambda cur, prev: (
        cur.get("rsi_slope_1") is not None and float(cur["rsi_slope_1"]) < 0
    )),
    ("MAJOR_K_REVERSAL", lambda cur, prev: (
        cur.get("major_k_slope_1") is not None and float(cur["major_k_slope_1"]) < 0
    )),
    ("MACD_WEAKENING", lambda cur, prev: (
        cur.get("macd_hist") is not None and prev.get("macd_hist") is not None
        and float(cur["macd_hist"]) < float(prev["macd_hist"])
    )),
    ("EMA_SLOPE_BAD", lambda cur, prev: (
        cur.get("ema20_slope_3") is not None and float(cur["ema20_slope_3"]) <= 0
    )),
)

COMPARE_FEATURES = (
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "rsi_slope_1",
    "macd", "macd_hist",
    "ema20_slope_3", "ema60_slope_3",
    "atr_pct", "volatility_20",
)

REGIME_FEATURES = ("atr_pct", "volatility_20", "rsi", "ema20_slope_3", "major_k")

ESCALATION_OFFSETS = (0, 1, 3, 5, 10)
TIMING_HORIZONS = (1, 3, 5, 10)

PATH_BUCKETS = ("WAVE3_COMPLETED", "TRIPLE_BOTTOM_REQUIRED", "INVALIDATED", "OTHER")

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "success",
    "failure_cause", "failure_horizon",
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "macd", "ema20_slope_3", "atr_pct", "volatility_20",
    "path", "branch",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _detect_causes_at(cur: dict, prev: dict) -> List[str]:
    active = []
    for name, fn in CAUSE_CHECKS:
        if fn(cur, prev):
            active.append(name)
    if len(active) >= 2:
        return active + ["MULTI_FAILURE"]
    return active


def _tracker_state_at(
    symbol: str, tf: str, ts: pd.Timestamp,
    tracker_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> str:
    key = (symbol, tf)
    tracker_cache = tracker_cache if tracker_cache is not None else {}
    if key not in tracker_cache:
        path = _csv_path("wave_tracker", symbol, tf)
        if os.path.isfile(path):
            tracker_cache[key] = pd.read_csv(path, parse_dates=["timestamp"])
        else:
            tracker_cache[key] = pd.DataFrame()
    tracker = tracker_cache[key]
    if tracker.empty:
        return "OTHER"
    keyed = tracker.set_index("timestamp")
    if ts in keyed.index:
        raw = str(keyed.loc[ts, "state"])
    else:
        idx = keyed.index.searchsorted(ts)
        if idx >= len(keyed):
            idx = len(keyed) - 1
        raw = str(keyed.iloc[idx]["state"])
    short = STATE_SHORT.get(raw, raw)
    if raw == "INVALIDATED" or short == "INVALIDATED":
        return "INVALIDATED"
    if short in WAVE_PATH_STATES:
        return short
    return "OTHER"


def _path_bucket(state: str) -> str:
    if state in PATH_BUCKETS:
        return state
    return "OTHER"


def build_failure_events(
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    tracker_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    candidate: Tuple[Tuple[str, str, float], ...] = BEST_CANDIDATE,
) -> pd.DataFrame:
    """Early Warning 발화 bar별 SUCCESS/FAILURE 이벤트."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    tcache = tracker_cache if tracker_cache is not None else {}
    origin = _load_origin_events()
    ga_map = _grade_a_positions(origin, cache)
    rule = _rule_fn(candidate)
    rows: List[dict] = []

    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            key = (sym, tf)
            if key not in cache:
                cache[key] = _load_pipeline(sym, tf)
            pipeline = cache[key]
            if pipeline.empty:
                continue
            ga_pos = ga_map.get(key, [])
            branch_df = _load_branch_df(sym, tf)

            for pos in range(20, len(pipeline) - HORIZON):
                feats = extract_origin_features(pipeline, pos)
                if not feats:
                    continue
                row_series = pd.Series(feats)
                if not rule(row_series):
                    continue

                success = any(pos < ga <= pos + HORIZON for ga in ga_pos)
                ts = pd.Timestamp(pipeline.index[pos])
                base_feats = feats

                failure_horizon = None
                failure_cause = None
                first_fail_rank = None
                cause_at_horizon: Dict[int, List[str]] = {}

                if not success:
                    prev_feats = base_feats
                    for h in range(1, HORIZON + 1):
                        if pos + h >= len(pipeline):
                            break
                        cur = extract_origin_features(pipeline, pos + h)
                        causes = _detect_causes_at(cur, prev_feats)
                        if causes:
                            cause_at_horizon[h] = causes
                            if failure_horizon is None:
                                failure_horizon = h
                                primary = [c for c in causes if c != "MULTI_FAILURE"]
                                failure_cause = primary[0] if primary else causes[0]
                        prev_feats = cur

                rows.append({
                    "timestamp": ts,
                    "symbol": sym,
                    "timeframe": tf,
                    "success": success,
                    "failure_cause": failure_cause or ("NONE" if success else "UNKNOWN"),
                    "failure_horizon": failure_horizon,
                    "path": _path_bucket(_tracker_state_at(sym, tf, ts, tcache)),
                    "branch": _lookup_branch(ts, branch_df),
                    **{f: base_feats.get(f) for f in COMPARE_FEATURES if f in base_feats},
                    "_pos": pos,
                    "_cause_at_horizon": cause_at_horizon,
                })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def failure_cause_distribution(events: pd.DataFrame) -> List[dict]:
    """실패 집단 원인 분포."""
    fail = events[~events["success"]]
    if fail.empty:
        return [{"cause": c, "count": 0, "pct": 0.0} for c in FAILURE_CAUSES]

    counts: Dict[str, int] = {c: 0 for c in FAILURE_CAUSES}
    for _, row in fail.iterrows():
        ch = row.get("_cause_at_horizon", {}) or {}
        seen = set()
        for h_causes in ch.values():
            for c in h_causes:
                if c in counts and c not in seen:
                    counts[c] += 1
                    seen.add(c)
        if not ch:
            fc = row.get("failure_cause", "UNKNOWN")
            if fc in counts:
                counts[fc] += 1

    total = len(fail)
    return [
        {"cause": c, "count": counts[c], "pct": counts[c] / total * 100.0}
        for c in FAILURE_CAUSES
    ]


def failure_timing(events: pd.DataFrame) -> List[dict]:
    """실패 발생 horizon 분포."""
    fail = events[~events["success"]]
    if fail.empty:
        return [{"horizon": h, "failure_pct": 0.0, "count": 0} for h in TIMING_HORIZONS]

    total = len(fail)
    rows = []
    for h in TIMING_HORIZONS:
        cnt = sum(
            1 for _, row in fail.iterrows()
            if row.get("failure_horizon") is not None and int(row["failure_horizon"]) <= h
        )
        rows.append({"horizon": h, "count": cnt, "failure_pct": cnt / total * 100.0})
    return rows


def first_failure_ranking(events: pd.DataFrame) -> List[dict]:
    """실패 집단에서 가장 먼저 발생한 원인."""
    fail = events[~events["success"]]
    if fail.empty:
        return []

    first_counts: Dict[str, int] = {}
    for _, row in fail.iterrows():
        ch = row.get("_cause_at_horizon", {}) or {}
        if not ch:
            fc = row.get("failure_cause", "UNKNOWN")
            first_counts[fc] = first_counts.get(fc, 0) + 1
            continue
        earliest = min(ch.keys())
        primary = [c for c in ch[earliest] if c != "MULTI_FAILURE"]
        first = primary[0] if primary else ch[earliest][0]
        first_counts[first] = first_counts.get(first, 0) + 1

    total = len(fail) or 1
    ranked = sorted(first_counts.items(), key=lambda x: x[1], reverse=True)
    return [
        {"rank": i + 1, "first_failure": name, "count": cnt, "pct": cnt / total * 100.0}
        for i, (name, cnt) in enumerate(ranked)
    ]


def success_vs_failure_separators(events: pd.DataFrame, top_n: int = 20) -> List[dict]:
    """SUCCESS vs FAILURE effect size."""
    succ = events[events["success"]]
    fail = events[~events["success"]]
    rows = []
    for feat in COMPARE_FEATURES:
        if feat not in events.columns:
            continue
        sv = succ[feat].dropna()
        fv = fail[feat].dropna()
        if len(sv) < 1 or len(fv) < 1:
            continue
        es = effect_size(sv, fv) if len(sv) >= 2 and len(fv) >= 2 else (
            abs(float(sv.mean()) - float(fv.mean())) if len(sv) and len(fv) else 0.0
        )
        rows.append({
            "feature": feat,
            "success_mean": float(sv.mean()),
            "failure_mean": float(fv.mean()),
            "delta": float(sv.mean()) - float(fv.mean()),
            "effect_size": es,
        })
    rows.sort(key=lambda x: x["effect_size"], reverse=True)
    return rows[:top_n]


def failure_path_distribution(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    tracker_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    lookahead: int = 10,
) -> List[dict]:
    """Early Warning 이후 tracker path bucket."""
    pcache = pipeline_cache if pipeline_cache is not None else {}
    tcache = tracker_cache if tracker_cache is not None else {}
    fail = events[~events["success"]]
    if fail.empty:
        return []

    counts: Dict[str, int] = {p: 0 for p in PATH_BUCKETS}
    for _, row in fail.iterrows():
        key = (row["symbol"], row["timeframe"])
        if key not in pcache:
            pcache[key] = _load_pipeline(key[0], key[1])
        pipeline = pcache[key]
        pos = row.get("_pos")
        if pos is None:
            pos = _find_bar_index(pipeline, pd.Timestamp(row["timestamp"]))
        if pos is None:
            continue
        obs = min(int(pos) + lookahead, len(pipeline) - 1)
        ts = pd.Timestamp(pipeline.index[obs])
        bucket = _path_bucket(_tracker_state_at(row["symbol"], row["timeframe"], ts, tcache))
        counts[bucket] = counts.get(bucket, 0) + 1

    total = len(fail) or 1
    return [
        {"path": p, "count": counts[p], "pct": counts[p] / total * 100.0}
        for p in PATH_BUCKETS if counts[p] > 0
    ] + [
        {"path": p, "count": counts[p], "pct": counts[p] / total * 100.0}
        for p in PATH_BUCKETS if counts[p] == 0
    ]


def failure_branch_comparison(events: pd.DataFrame) -> List[dict]:
    """SUCCESS vs FAILURE branch 비율."""
    rows = []
    branches = set()
    for _, row in events.iterrows():
        b = row.get("branch")
        if b and pd.notna(b):
            branches.add(str(b))
    for branch in sorted(branches):
        succ = len(events[(events["success"]) & (events["branch"] == branch)])
        fail = len(events[(~events["success"]) & (events["branch"] == branch)])
        rows.append({"branch": branch, "success": succ, "failure": fail})
    return sorted(rows, key=lambda x: x["success"] + x["failure"], reverse=True)


def failure_regime_comparison(events: pd.DataFrame) -> List[dict]:
    """성공 vs 실패 regime feature."""
    succ = events[events["success"]]
    fail = events[~events["success"]]
    rows = []
    for feat in REGIME_FEATURES:
        if feat not in events.columns:
            continue
        sv = succ[feat].dropna()
        fv = fail[feat].dropna()
        rows.append({
            "feature": feat,
            "success_mean": float(sv.mean()) if len(sv) else None,
            "failure_mean": float(fv.mean()) if len(fv) else None,
            "effect_size": effect_size(sv, fv) if len(sv) and len(fv) else 0.0,
        })
    rows.sort(key=lambda x: x["effect_size"], reverse=True)
    return rows


def escalation_timeline(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> List[dict]:
    """Early Warning 기준 offset별 success/failure 평균."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    metrics = ("major_k", "rsi", "macd", "ema20_slope_3")
    rows = []

    for offset in ESCALATION_OFFSETS:
        succ_vals: Dict[str, List[float]] = {m: [] for m in metrics}
        fail_vals: Dict[str, List[float]] = {m: [] for m in metrics}

        for _, ev in events.iterrows():
            key = (ev["symbol"], ev["timeframe"])
            if key not in cache:
                cache[key] = _load_pipeline(key[0], key[1])
            pipeline = cache[key]
            pos = ev.get("_pos")
            if pos is None:
                pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
            if pos is None or pos + offset >= len(pipeline):
                continue
            feats = features_at_offset(pipeline, int(pos), offset)
            bucket = succ_vals if ev["success"] else fail_vals
            for m in metrics:
                v = feats.get(m)
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    bucket[m].append(float(v))

        row = {"offset": offset}
        for m in metrics:
            sm = succ_vals[m]
            fm = fail_vals[m]
            row[f"success_{m}"] = float(np.mean(sm)) if sm else None
            row[f"failure_{m}"] = float(np.mean(fm)) if fm else None
        rows.append(row)
    return rows


def _conditions_hold(feats: dict, candidate: Tuple[Tuple[str, str, float], ...]) -> bool:
    row = pd.Series(feats)
    return _rule_fn(candidate)(row)


def false_positive_funnel(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    candidate: Tuple[Tuple[str, str, float], ...] = BEST_CANDIDATE,
) -> List[dict]:
    """단계별 생존 funnel."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    total = len(events)
    maintain_5 = 0
    maintain_10 = 0
    grade_a = int(events["success"].sum()) if not events.empty else 0

    for _, ev in events.iterrows():
        key = (ev["symbol"], ev["timeframe"])
        if key not in cache:
            cache[key] = _load_pipeline(key[0], key[1])
        pipeline = cache[key]
        pos = ev.get("_pos")
        if pos is None:
            pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
        if pos is None:
            continue
        if pos + 5 < len(pipeline):
            f5 = extract_origin_features(pipeline, pos + 5)
            if _conditions_hold(f5, candidate):
                maintain_5 += 1
        if pos + 10 < len(pipeline):
            f10 = extract_origin_features(pipeline, pos + 10)
            if _conditions_hold(f10, candidate):
                maintain_10 += 1

    return [
        {"stage": "Early Warning", "survivors": total},
        {"stage": "5-bar maintain", "survivors": maintain_5},
        {"stage": "10-bar maintain", "survivors": maintain_10},
        {"stage": "Grade A", "survivors": grade_a},
    ]


def symbol_failure_comparison(events: pd.DataFrame) -> Dict[str, dict]:
    out = {}
    for sym in GENERALIZATION_SYMBOLS:
        sub = events[events["symbol"] == sym]
        succ = sub[sub["success"]]
        fail = sub[~sub["success"]]
        top = failure_cause_distribution(sub)
        top_cause = top[0]["cause"] if top else None
        out[sym] = {
            "success": len(succ),
            "failure": len(fail),
            "top_cause": top_cause,
            "top_cause_pct": top[0]["pct"] if top else 0.0,
        }
    return out


def build_failure_csv(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    out = events.copy()
    out["macd"] = out.get("macd", out.get("macd_hist"))
    cols = [c for c in CSV_EXPORT_COLS if c in out.columns]
    return out[cols]


def full_grade_failure_summary() -> dict:
    """전체 failure 분석 payload."""
    cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    tcache: Dict[Tuple[str, str], pd.DataFrame] = {}
    events = build_failure_events(cache, tcache)

    causes = failure_cause_distribution(events)
    timing = failure_timing(events)
    first_fail = first_failure_ranking(events)
    separators = success_vs_failure_separators(events)
    paths = failure_path_distribution(events, cache, tcache)
    branches = failure_branch_comparison(events)
    regime = failure_regime_comparison(events)
    escalation = escalation_timeline(events, cache)
    funnel = false_positive_funnel(events, cache)
    sym_cmp = symbol_failure_comparison(events)

    n_succ = int(events["success"].sum()) if not events.empty else 0
    n_fail = len(events) - n_succ if not events.empty else 0

    return {
        "events": events,
        "success_count": n_succ,
        "failure_count": n_fail,
        "causes": causes,
        "timing": timing,
        "first_failure": first_fail,
        "separators": separators,
        "paths": paths,
        "branches": branches,
        "regime": regime,
        "escalation": escalation,
        "funnel": funnel,
        "symbol_comparison": sym_cmp,
        "dataframe": build_failure_csv(events),
    }
