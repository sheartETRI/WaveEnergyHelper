"""Wave Grade Early Warning — Grade A 조기 경고 관측 분석.

Grade Origin/Rule Grading 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_generalization import (
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
)
from analysis.wave_grade_origin import (
    GRADE_A,
    extract_origin_features,
    features_at_offset,
)
from analysis.wave_outcome import _find_bar_index
from analysis.wave_regime_analysis import _load_pipeline

HORIZON = 10
EARLY_OFFSETS = (-20, -15, -10, -5)

EARLY_FEATURES = (
    "major_k", "major_d", "major_k_minus_d", "major_k_slope_1", "major_k_slope_3",
    "rsi", "rsi_slope_1", "rsi_slope_3",
    "macd", "macd_signal", "macd_hist",
    "ema20_slope_3", "ema60_slope_3",
    "atr_pct", "volatility_20",
)

CANDIDATE_ATOMS: List[Tuple[str, str, float]] = [
    ("major_k_slope_1", ">", 0),
    ("major_k_slope_3", ">", 0),
    ("major_k_minus_d", ">", 0),
    ("rsi", ">", 50),
    ("ema20_slope_3", ">", 0),
    ("macd", ">", 0),
]

FP_FAILURE_CHECKS = (
    ("major_k_reversal", "major_k_slope_1", lambda v: v is not None and v < 0),
    ("rsi_drop", "rsi_slope_1", lambda v: v is not None and v < 0),
    ("ema_slope_bad", "ema20_slope_3", lambda v: v is not None and v < 0),
    ("macd_weak", "macd_hist", lambda v: v is not None and v < 0),
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "offset", "positive",
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "rsi_slope_1", "macd", "ema20_slope_3", "atr_pct", "volatility_20",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _load_origin_events() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_grade_origin.csv")
    if os.path.isfile(path):
        df = pd.read_csv(path, parse_dates=["timestamp"])
        if not df.empty:
            return df
    from analysis.wave_grade_origin import collect_origin_events
    return collect_origin_events()


def _grade_a_positions(
    origin: pd.DataFrame,
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame],
) -> Dict[Tuple[str, str], List[int]]:
    """셀별 Grade A bar index 목록."""
    out: Dict[Tuple[str, str], List[int]] = {}
    a = origin[origin["grade"] == GRADE_A] if not origin.empty else pd.DataFrame()
    for _, row in a.iterrows():
        key = (row["symbol"], row["timeframe"])
        if key not in pipeline_cache:
            pipeline_cache[key] = _load_pipeline(key[0], key[1])
        pipeline = pipeline_cache[key]
        pos = _find_bar_index(pipeline, pd.Timestamp(row["timestamp"]))
        if pos is None:
            continue
        out.setdefault(key, []).append(pos)
    return out


def is_positive_bar(pos: int, grade_a_positions: List[int], horizon: int = HORIZON) -> bool:
    """향후 horizon 봉 내 Grade A 발생 여부."""
    for ga in grade_a_positions:
        if pos < ga <= pos + horizon:
            return True
    return False


def build_labeled_snapshots(
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> pd.DataFrame:
    """전 셀 bar-level + Grade A offset snapshot."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    origin = _load_origin_events()
    ga_map = _grade_a_positions(origin, cache)
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

            for ga in ga_pos:
                ts = pd.Timestamp(pipeline.index[ga])
                for offset in EARLY_OFFSETS:
                    obs = ga + offset
                    if obs < 0:
                        continue
                    feats = extract_origin_features(pipeline, obs)
                    if not feats:
                        continue
                    rows.append({
                        "timestamp": pd.Timestamp(pipeline.index[obs]),
                        "symbol": sym,
                        "timeframe": tf,
                        "offset": offset,
                        "positive": is_positive_bar(obs, ga_pos),
                        "source": "grade_a_lead",
                        **{f: feats.get(f) for f in EARLY_FEATURES if f in feats},
                    })

            for pos in range(20, len(pipeline) - HORIZON):
                positive = is_positive_bar(pos, ga_pos)
                feats = extract_origin_features(pipeline, pos)
                if not feats:
                    continue
                rows.append({
                    "timestamp": pd.Timestamp(pipeline.index[pos]),
                    "symbol": sym,
                    "timeframe": tf,
                    "offset": 0,
                    "positive": positive,
                    "source": "bar_scan",
                    **{f: feats.get(f) for f in EARLY_FEATURES if f in feats},
                })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def compute_early_separators(snapshots: pd.DataFrame) -> List[dict]:
    """offset별 positive vs negative effect size."""
    if snapshots.empty:
        return []

    lead = snapshots[snapshots["source"] == "grade_a_lead"]
    bar_neg = snapshots[(snapshots["source"] == "bar_scan") & (~snapshots["positive"])]

    results: List[dict] = []
    for offset in EARLY_OFFSETS:
        pos_df = lead[(lead["offset"] == offset) & (lead["positive"])]
        neg_df = bar_neg
        if pos_df.empty or neg_df.empty:
            continue
        for feat in EARLY_FEATURES:
            if feat not in pos_df.columns:
                continue
            pv = pos_df[feat].dropna()
            nv = neg_df[feat].dropna()
            if len(pv) < 2 or len(nv) < 2:
                continue
            es = effect_size(pv, nv)
            if es > 0:
                results.append({
                    "feature": feat,
                    "effect_size": es,
                    "offset": offset,
                    "pos_mean": float(pv.mean()),
                    "neg_mean": float(nv.mean()),
                })

    results.sort(key=lambda x: x["effect_size"], reverse=True)
    return results


def _eval_condition(row: pd.Series, cond: Tuple[str, str, float]) -> bool:
    feat, op, thr = cond
    v = row.get(feat)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    if op == ">":
        return float(v) > thr
    if op == "<":
        return float(v) < thr
    return False


def _rule_label(conds: Tuple[Tuple[str, str, float], ...]) -> str:
    parts = []
    for feat, op, thr in conds:
        parts.append(f"{feat}{op}{thr:g}")
    return " AND ".join(parts)


def _rule_fn(conds: Tuple[Tuple[str, str, float], ...]) -> Callable[[pd.Series], bool]:
    def _fn(row: pd.Series) -> bool:
        return all(_eval_condition(row, c) for c in conds)
    return _fn


def generate_candidates(max_combo: int = 3) -> List[Tuple[str, Tuple[Tuple[str, str, float], ...]]]:
    """단일~3조건 후보."""
    out: List[Tuple[str, Tuple[Tuple[str, str, float], ...]]] = []
    for n in range(1, max_combo + 1):
        for combo in combinations(CANDIDATE_ATOMS, n):
            out.append((_rule_label(combo), combo))
    return out


def evaluate_candidate(
    snapshots: pd.DataFrame,
    conds: Tuple[Tuple[str, str, float], ...],
    offset: Optional[int] = None,
) -> dict:
    """precision / recall / coverage / future GradeA rate."""
    if snapshots.empty:
        return {"precision": None, "recall": None, "coverage": None, "positive_rate": None}

    rule = _rule_fn(conds)

    if offset is not None:
        pos_df = snapshots[(snapshots["source"] == "grade_a_lead") & (snapshots["offset"] == offset)]
        neg_df = snapshots[(snapshots["source"] == "bar_scan") & (~snapshots["positive"])]
        df = pd.concat([pos_df, neg_df], ignore_index=True)
    else:
        df = snapshots[snapshots["source"] == "bar_scan"].copy()

    if df.empty:
        return {"precision": None, "recall": None, "coverage": None, "positive_rate": None}

    df = df.copy()
    df["_fire"] = df.apply(rule, axis=1)

    fired = df[df["_fire"]]
    positives = df[df["positive"]]
    tp = len(fired[fired["positive"]])
    fp = len(fired[~fired["positive"]])
    fn = len(positives[~positives.apply(rule, axis=1)])

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    coverage = len(fired) / len(df) if len(df) else None
    positive_rate = tp / len(fired) if len(fired) > 0 else None

    return {
        "precision": precision,
        "recall": recall,
        "coverage": coverage,
        "positive_rate": positive_rate,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "fired": len(fired),
        "total": len(df),
    }


def evaluate_all_candidates(
    snapshots: pd.DataFrame,
    offset: Optional[int] = None,
) -> List[dict]:
    rows = []
    for label, conds in generate_candidates(max_combo=3):
        m = evaluate_candidate(snapshots, conds, offset=offset)
        rows.append({"candidate": label, **m})
    rows.sort(
        key=lambda x: (
            x.get("precision") or 0,
            x.get("recall") or 0,
        ),
        reverse=True,
    )
    return rows


def best_horizon(separators: List[dict]) -> dict:
    """offset별 평균 effect size → best horizon."""
    if not separators:
        return {"offset": None, "avg_effect": None}

    by_off: Dict[int, List[float]] = {}
    for r in separators:
        off = r["offset"]
        by_off.setdefault(off, []).append(r["effect_size"])

    best_off = max(by_off.keys(), key=lambda o: float(np.mean(by_off[o])))
    return {
        "offset": best_off,
        "avg_effect": float(np.mean(by_off[best_off])),
        "by_offset": {
            o: float(np.mean(v)) for o, v in sorted(by_off.items())
        },
    }


def false_positive_analysis(
    snapshots: pd.DataFrame,
    candidate: Tuple[Tuple[str, str, float], ...],
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> List[dict]:
    """FP 발생 시 실패 원인 분포."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    bar_df = snapshots[(snapshots["source"] == "bar_scan")].copy()
    if bar_df.empty:
        return []

    rule = _rule_fn(candidate)
    bar_df["_fire"] = bar_df.apply(rule, axis=1)
    fps = bar_df[bar_df["_fire"] & ~bar_df["positive"]]
    if fps.empty:
        return [{"cause": c[0], "count": 0, "pct": 0.0} for c in FP_FAILURE_CHECKS]

    cause_counts: Dict[str, int] = {c[0]: 0 for c in FP_FAILURE_CHECKS}
    checked = 0

    for _, row in fps.iterrows():
        key = (row["symbol"], row["timeframe"])
        if key not in cache:
            cache[key] = _load_pipeline(key[0], key[1])
        pipeline = cache[key]
        pos = _find_bar_index(pipeline, pd.Timestamp(row["timestamp"]))
        if pos is None or pos + 3 >= len(pipeline):
            continue
        future = extract_origin_features(pipeline, pos + 3)
        checked += 1
        for cause, feat, fn in FP_FAILURE_CHECKS:
            if fn(future.get(feat)):
                cause_counts[cause] += 1

    total = checked or 1
    return [
        {"cause": cause, "count": cause_counts[cause], "pct": cause_counts[cause] / total * 100.0}
        for cause, _, _ in FP_FAILURE_CHECKS
    ]


def formation_order(separators: List[dict]) -> List[dict]:
    """Grade A 발생 전 변화 순서 (effect size × offset)."""
    if not separators:
        return []
    seen = set()
    ordered = []
    for r in sorted(separators, key=lambda x: (-x["offset"], -x["effect_size"])):
        feat = r["feature"]
        if feat in seen:
            continue
        seen.add(feat)
        ordered.append({
            "feature": feat,
            "offset": r["offset"],
            "effect_size": r["effect_size"],
        })
    return ordered[:10]


def symbol_early_comparison(
    snapshots: pd.DataFrame,
    separators: List[dict],
) -> Dict[str, dict]:
    out = {}
    top_feat = separators[0]["feature"] if separators else "major_k_slope_3"
    for sym in GENERALIZATION_SYMBOLS:
        sub = snapshots[(snapshots["symbol"] == sym) & (snapshots["source"] == "grade_a_lead")]
        pos = sub[sub["positive"]]
        neg = snapshots[(snapshots["symbol"] == sym) & (snapshots["source"] == "bar_scan") & (~snapshots["positive"])]
        if top_feat in pos.columns and top_feat in neg.columns:
            pv = pos[top_feat].dropna()
            nv = neg[top_feat].dropna()
            es = effect_size(pv, nv) if len(pv) and len(nv) else 0.0
        else:
            es = 0.0
        out[sym] = {
            "positive_snapshots": len(pos),
            "top_feature": top_feat,
            "top_effect": es,
        }
    return out


def build_early_warning_csv(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty:
        return pd.DataFrame()
    lead = snapshots[snapshots["source"] == "grade_a_lead"].copy()
    cols = [c for c in CSV_EXPORT_COLS if c in lead.columns]
    return lead[cols]


def full_early_warning_summary() -> dict:
    """전체 early warning payload."""
    cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    snapshots = build_labeled_snapshots(cache)
    separators = compute_early_separators(snapshots)
    horizon = best_horizon(separators)
    best_off = horizon.get("offset")

    candidates = evaluate_all_candidates(snapshots, offset=best_off)
    top_candidates = candidates[:15]

    best_cand = candidates[0] if candidates else {}
    best_conds = None
    for label, conds in generate_candidates(max_combo=3):
        if label == best_cand.get("candidate"):
            best_conds = conds
            break

    fp_analysis = (
        false_positive_analysis(snapshots, best_conds, cache)
        if best_conds else []
    )

    order = formation_order(separators)
    sym_cmp = symbol_early_comparison(snapshots, separators)

    origin = _load_origin_events()
    a_count = len(origin[origin["grade"] == GRADE_A]) if not origin.empty else 0

    return {
        "snapshots": snapshots,
        "separators": separators,
        "horizon": horizon,
        "candidates": top_candidates,
        "best_candidate": best_cand,
        "fp_analysis": fp_analysis,
        "formation_order": order,
        "symbol_comparison": sym_cmp,
        "dataframe": build_early_warning_csv(snapshots),
        "a_count": a_count,
    }
