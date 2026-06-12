"""Wave Watchlist Tracker — Grade A 형성 상태 전이 관측.

Confirmation Gate/Early Warning 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES
from analysis.wave_grade_early_warning import HORIZON, _grade_a_positions, _load_origin_events, _rule_fn
from analysis.wave_grade_failure import BEST_CANDIDATE, _detect_causes_at
from analysis.wave_grade_origin import extract_origin_features
from analysis.wave_confirmation_gate import (
    _ema20_pos,
    _eval_gate,
    _kd_pos,
    _rsi_hold,
    _window_feats,
)

STATE_NONE = "STATE_NONE"
STATE_EARLY_WARNING = "STATE_EARLY_WARNING"
STATE_CONFIRMING = "STATE_CONFIRMING"
STATE_STRONG_CONFIRMING = "STATE_STRONG_CONFIRMING"
STATE_GRADE_A_READY = "STATE_GRADE_A_READY"
STATE_FAILED = "STATE_FAILED"

ORDERED_STATES = (
    STATE_NONE,
    STATE_EARLY_WARNING,
    STATE_CONFIRMING,
    STATE_STRONG_CONFIRMING,
    STATE_GRADE_A_READY,
    STATE_FAILED,
)

FUNNEL_STATES = (
    STATE_EARLY_WARNING,
    STATE_CONFIRMING,
    STATE_STRONG_CONFIRMING,
    STATE_GRADE_A_READY,
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "state", "duration", "next_state", "success",
)

def _is_confirming(base: dict, future: List[dict], h: int) -> bool:
    return (
        _eval_gate(base, future, _rsi_hold, h)
        and _eval_gate(base, future, _kd_pos, h)
    )


def _is_strong_confirming(base: dict, future: List[dict], h: int) -> bool:
    return (
        _is_confirming(base, future, h)
        and _eval_gate(base, future, _ema20_pos, h)
    )


def _is_grade_a_at(pos: int, ga_positions: List[int]) -> bool:
    return pos in ga_positions


def _has_failure(cur: dict, prev: dict) -> bool:
    causes = _detect_causes_at(cur, prev)
    primary = [c for c in causes if c != "MULTI_FAILURE"]
    return len(primary) > 0


def trace_event(
    pos: int,
    pipeline: pd.DataFrame,
    ga_positions: List[int],
    sym: str,
    tf: str,
) -> Tuple[List[str], List[dict], bool]:
    """단일 Early Warning 이벤트 상태 전이 추적."""
    ts = pd.Timestamp(pipeline.index[pos])
    base, future = _window_feats(pipeline, pos, max_h=HORIZON)
    path = [STATE_EARLY_WARNING]
    transitions: List[dict] = []
    current = STATE_EARLY_WARNING
    entry_h = 0

    transitions.append({
        "timestamp": ts,
        "symbol": sym,
        "timeframe": tf,
        "state": STATE_NONE,
        "duration": 0,
        "next_state": STATE_EARLY_WARNING,
        "success": False,
    })

    reached_confirming = False
    reached_strong = False
    prev_feats = base

    for h in range(1, HORIZON + 1):
        if pos + h >= len(pipeline):
            break
        obs_pos = pos + h
        cur = extract_origin_features(pipeline, obs_pos)

        if _is_grade_a_at(obs_pos, ga_positions):
            duration = h - entry_h
            transitions.append({
                "timestamp": ts,
                "symbol": sym,
                "timeframe": tf,
                "state": current,
                "duration": duration,
                "next_state": STATE_GRADE_A_READY,
                "success": True,
            })
            path.append(STATE_GRADE_A_READY)
            return path, transitions, True

        if current in (STATE_CONFIRMING, STATE_STRONG_CONFIRMING) and _has_failure(cur, prev_feats):
            duration = h - entry_h
            transitions.append({
                "timestamp": ts,
                "symbol": sym,
                "timeframe": tf,
                "state": current,
                "duration": duration,
                "next_state": STATE_FAILED,
                "success": False,
            })
            path.append(STATE_FAILED)
            return path, transitions, False

        if current == STATE_EARLY_WARNING and _is_confirming(base, future, h):
            duration = h - entry_h
            transitions.append({
                "timestamp": ts,
                "symbol": sym,
                "timeframe": tf,
                "state": STATE_EARLY_WARNING,
                "duration": duration,
                "next_state": STATE_CONFIRMING,
                "success": False,
            })
            current = STATE_CONFIRMING
            entry_h = h
            path.append(STATE_CONFIRMING)
            reached_confirming = True

        elif current == STATE_CONFIRMING and _is_strong_confirming(base, future, h):
            duration = h - entry_h
            transitions.append({
                "timestamp": ts,
                "symbol": sym,
                "timeframe": tf,
                "state": STATE_CONFIRMING,
                "duration": duration,
                "next_state": STATE_STRONG_CONFIRMING,
                "success": False,
            })
            current = STATE_STRONG_CONFIRMING
            entry_h = h
            path.append(STATE_STRONG_CONFIRMING)
            reached_strong = True

        elif current == STATE_EARLY_WARNING and h >= 3 and not reached_confirming and _has_failure(cur, prev_feats):
            duration = h - entry_h
            transitions.append({
                "timestamp": ts,
                "symbol": sym,
                "timeframe": tf,
                "state": STATE_EARLY_WARNING,
                "duration": duration,
                "next_state": STATE_FAILED,
                "success": False,
            })
            path.append(STATE_FAILED)
            return path, transitions, False

        prev_feats = cur

    duration = HORIZON - entry_h
    transitions.append({
        "timestamp": ts,
        "symbol": sym,
        "timeframe": tf,
        "state": current,
        "duration": max(duration, 1),
        "next_state": STATE_FAILED,
        "success": False,
    })
    path.append(STATE_FAILED)
    return path, transitions, False


def build_watchlist_traces(
    pipeline_cache: Optional[Dict] = None,
) -> Tuple[pd.DataFrame, List[dict]]:
    """전체 Early Warning 이벤트 상태 추적."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    origin = _load_origin_events()
    ga_map = _grade_a_positions(origin, cache)
    rule = _rule_fn(BEST_CANDIDATE)

    all_transitions: List[dict] = []
    event_paths: List[dict] = []

    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            key = (sym, tf)
            if key not in cache:
                from analysis.wave_regime_analysis import _load_pipeline
                cache[key] = _load_pipeline(sym, tf)
            pipeline = cache[key]
            if pipeline.empty:
                continue
            ga_pos = ga_map.get(key, [])

            for pos in range(20, len(pipeline) - HORIZON):
                feats = extract_origin_features(pipeline, pos)
                if not feats or not rule(pd.Series(feats)):
                    continue
                path, transitions, success = trace_event(pos, pipeline, ga_pos, sym, tf)
                all_transitions.extend(transitions)
                event_paths.append({
                    "timestamp": pd.Timestamp(pipeline.index[pos]),
                    "symbol": sym,
                    "timeframe": tf,
                    "path": " → ".join(path),
                    "success": success,
                    "terminal": path[-1],
                    "max_state": _max_funnel_state(path),
                })

    df = pd.DataFrame(all_transitions) if all_transitions else pd.DataFrame()
    return df, event_paths


def _max_funnel_state(path: List[str]) -> str:
    order = {s: i for i, s in enumerate(FUNNEL_STATES)}
    best = STATE_EARLY_WARNING
    for s in path:
        if s in order and order[s] > order.get(best, -1):
            best = s
    return best


def transition_matrix(transitions: pd.DataFrame) -> List[dict]:
    if transitions.empty:
        return []
    pairs = transitions[["state", "next_state"]].value_counts()
    total = len(transitions)
    rows = []
    for (frm, to), cnt in pairs.items():
        rows.append({
            "from": frm,
            "to": to,
            "count": int(cnt),
            "pct": int(cnt) / total * 100.0,
        })
    return sorted(rows, key=lambda x: x["count"], reverse=True)


def state_duration(transitions: pd.DataFrame) -> List[dict]:
    if transitions.empty:
        return []
    rows = []
    for state in ORDERED_STATES:
        sub = transitions[transitions["state"] == state]["duration"].dropna()
        if sub.empty:
            rows.append({"state": state, "avg": None, "median": None, "max": None})
        else:
            rows.append({
                "state": state,
                "avg": float(sub.mean()),
                "median": float(sub.median()),
                "max": int(sub.max()),
            })
    return rows


def conversion_rates(event_paths: List[dict]) -> List[dict]:
    if not event_paths:
        return []
    total = len(event_paths)
    successes = [e for e in event_paths if e["terminal"] == STATE_GRADE_A_READY]

    def _rate(state: str) -> Optional[float]:
        entered = [e for e in event_paths if _state_in_path(e["path"], state)]
        if not entered:
            return None
        converted = [e for e in entered if e["terminal"] == STATE_GRADE_A_READY]
        return len(converted) / len(entered) * 100.0

    return [
        {"state": STATE_EARLY_WARNING, "conversion": _rate(STATE_EARLY_WARNING), "entered": total},
        {"state": STATE_CONFIRMING, "conversion": _rate(STATE_CONFIRMING),
         "entered": sum(1 for e in event_paths if _state_in_path(e["path"], STATE_CONFIRMING))},
        {"state": STATE_STRONG_CONFIRMING, "conversion": _rate(STATE_STRONG_CONFIRMING),
         "entered": sum(1 for e in event_paths if _state_in_path(e["path"], STATE_STRONG_CONFIRMING))},
    ]


def _state_in_path(path_str: str, state: str) -> bool:
    return state in path_str.split(" → ")


def failure_leakage(transitions: pd.DataFrame) -> List[dict]:
    """상태별 FAILED 전이 비율."""
    if transitions.empty:
        return []
    rows = []
    for state in (STATE_EARLY_WARNING, STATE_CONFIRMING, STATE_STRONG_CONFIRMING):
        from_state = transitions[transitions["state"] == state]
        if from_state.empty:
            rows.append({"state": state, "fail_rate": None, "fail_count": 0, "total_exits": 0})
            continue
        fails = from_state[from_state["next_state"] == STATE_FAILED]
        rows.append({
            "state": state,
            "fail_rate": len(fails) / len(from_state) * 100.0,
            "fail_count": len(fails),
            "total_exits": len(from_state),
        })
    return sorted(rows, key=lambda x: x.get("fail_rate") or 0, reverse=True)


def watchlist_funnel(event_paths: List[dict]) -> List[dict]:
    if not event_paths:
        return []
    total = len(event_paths)
    rows = []
    for state in FUNNEL_STATES:
        cnt = sum(1 for e in event_paths if _state_in_path(e["path"], state))
        rows.append({
            "state": state,
            "count": cnt,
            "pct": cnt / total * 100.0 if total else 0.0,
        })
    return rows


def path_distribution(event_paths: List[dict], terminal: str, top_n: int = 10) -> List[dict]:
    subset = [e for e in event_paths if e["terminal"] == terminal]
    if not subset:
        return []
    counts = Counter(e["path"] for e in subset)
    total = len(subset)
    return [
        {"path": path, "count": cnt, "pct": cnt / total * 100.0}
        for path, cnt in counts.most_common(top_n)
    ]


def symbol_watchlist_comparison(event_paths: List[dict]) -> Dict[str, dict]:
    out = {}
    for sym in GENERALIZATION_SYMBOLS:
        sub = [e for e in event_paths if e["symbol"] == sym]
        if not sub:
            out[sym] = {"conversion": None, "fail_rate": None, "avg_duration": None, "n": 0}
            continue
        conv = sum(1 for e in sub if e["terminal"] == STATE_GRADE_A_READY) / len(sub) * 100.0
        fail = sum(1 for e in sub if e["terminal"] == STATE_FAILED) / len(sub) * 100.0
        out[sym] = {
            "conversion": conv,
            "fail_rate": fail,
            "avg_duration": None,
            "n": len(sub),
        }
    return out


def build_watchlist_csv(transitions: pd.DataFrame) -> pd.DataFrame:
    if transitions.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in transitions.columns]
    return transitions[cols].copy()


def full_watchlist_summary() -> dict:
    cache: Dict = {}
    transitions, event_paths = build_watchlist_traces(cache)

    matrix = transition_matrix(transitions)
    durations = state_duration(transitions)
    conversions = conversion_rates(event_paths)
    leakage = failure_leakage(transitions)
    funnel = watchlist_funnel(event_paths)
    success_paths = path_distribution(event_paths, STATE_GRADE_A_READY)
    failure_paths = path_distribution(event_paths, STATE_FAILED)
    sym_cmp = symbol_watchlist_comparison(event_paths)

    riskiest = leakage[0] if leakage else {}

    return {
        "transitions": transitions,
        "event_paths": event_paths,
        "matrix": matrix,
        "durations": durations,
        "conversions": conversions,
        "leakage": leakage,
        "funnel": funnel,
        "success_paths": success_paths,
        "failure_paths": failure_paths,
        "symbol_comparison": sym_cmp,
        "riskiest_state": riskiest.get("state"),
        "dataframe": build_watchlist_csv(transitions),
        "event_count": len(event_paths),
        "success_count": sum(1 for e in event_paths if e["terminal"] == STATE_GRADE_A_READY),
    }
