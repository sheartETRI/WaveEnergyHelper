"""Wave Confirmation Gate — Early Warning 이후 1~3봉 생존 관측.

Failure/Early Warning/Origin 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_generalization import GENERALIZATION_SYMBOLS
from analysis.wave_grade_failure import BEST_CANDIDATE, build_failure_events
from analysis.wave_grade_origin import extract_origin_features, features_at_offset
from analysis.wave_outcome import _find_bar_index

CONFIRMATION_HORIZONS = (1, 2, 3)

COMPARE_FEATURES = (
    "major_k", "major_k_slope_1", "major_k_slope_3", "major_k_minus_d",
    "rsi", "macd_hist", "ema20_slope_3", "ema60_slope_3",
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "success", "gate_name", "gate_pass",
    "horizon", "major_k", "major_k_slope_1", "major_k_minus_d",
    "rsi", "macd_hist", "ema20_slope_3",
)

GateFn = Callable[[dict, dict, int], bool]


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _nan(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v))


def _fev(v) -> Optional[float]:
    if _nan(v):
        return None
    return float(v)


def _window_feats(pipeline, pos: int, max_h: int = 3) -> Tuple[dict, List[dict]]:
    """t=0 및 t+1..t+max_h feature."""
    base = extract_origin_features(pipeline, pos)
    future = []
    for h in range(1, max_h + 1):
        if pos + h < len(pipeline):
            future.append(extract_origin_features(pipeline, pos + h))
        else:
            future.append({})
    return base, future


# --- atomic gate evaluators (pass at horizon h) ---

def _k_slope1_pos(base: dict, future: List[dict], h: int) -> bool:
    v = _fev(future[h - 1].get("major_k_slope_1"))
    return v is not None and v > 0


def _k_slope3_pos(base: dict, future: List[dict], h: int) -> bool:
    v = _fev(future[h - 1].get("major_k_slope_3"))
    return v is not None and v > 0


def _kd_pos(base: dict, future: List[dict], h: int) -> bool:
    v = _fev(future[h - 1].get("major_k_minus_d"))
    return v is not None and v > 0


def _rsi_hold(base: dict, future: List[dict], h: int) -> bool:
    b = _fev(base.get("rsi"))
    v = _fev(future[h - 1].get("rsi"))
    return b is not None and v is not None and v >= b


def _macd_hold(base: dict, future: List[dict], h: int) -> bool:
    b = _fev(base.get("macd_hist"))
    v = _fev(future[h - 1].get("macd_hist"))
    return b is not None and v is not None and v >= b


def _ema20_pos(base: dict, future: List[dict], h: int) -> bool:
    v = _fev(future[h - 1].get("ema20_slope_3"))
    return v is not None and v > 0


def _ema20_rise(base: dict, future: List[dict], h: int) -> bool:
    b = _fev(base.get("ema20_slope_3"))
    v = _fev(future[h - 1].get("ema20_slope_3"))
    return b is not None and v is not None and v >= b


def _ema60_pos(base: dict, future: List[dict], h: int) -> bool:
    v = _fev(future[h - 1].get("ema60_slope_3"))
    return v is not None and v > 0


ATOMIC_GATES: List[Tuple[str, GateFn]] = [
    ("K_SLOPE1_POS", _k_slope1_pos),
    ("K_SLOPE3_POS", _k_slope3_pos),
    ("KD_POS", _kd_pos),
    ("RSI_HOLD", _rsi_hold),
    ("MACD_HOLD", _macd_hold),
    ("EMA20_POS", _ema20_pos),
    ("EMA20_RISE", _ema20_rise),
    ("EMA60_POS", _ema60_pos),
]


def _cumulative_gate(fn: GateFn, h: int) -> GateFn:
    """+1..h 모든 봉에서 gate 통과."""
    def _fn(base: dict, future: List[dict], _h: int) -> bool:
        for i in range(1, h + 1):
            if not fn(base, future, i):
                return False
        return True
    return _fn


def build_gate_catalog() -> List[Tuple[str, GateFn, int]]:
    """단일 gate × horizon (+ cumulative RSI/MACD hold variants)."""
    catalog: List[Tuple[str, GateFn, int]] = []
    for h in CONFIRMATION_HORIZONS:
        for name, fn in ATOMIC_GATES:
            catalog.append((f"{name}_+{h}", fn, h))
        catalog.append((f"RSI_HOLD_CUM_+{h}", _cumulative_gate(_rsi_hold, h), h))
        catalog.append((f"MACD_HOLD_CUM_+{h}", _cumulative_gate(_macd_hold, h), h))
    return catalog


def build_composite_catalog(max_combo: int = 3) -> List[Tuple[str, List[Tuple[str, GateFn, int]]]]:
    """최대 3개 조합 (동일 horizon)."""
    composites: List[Tuple[str, List[Tuple[str, GateFn, int]]]] = []
    base_atoms = [
        ("RSI_HOLD", _rsi_hold),
        ("MACD_HOLD", _macd_hold),
        ("K_SLOPE1_POS", _k_slope1_pos),
        ("K_SLOPE3_POS", _k_slope3_pos),
        ("KD_POS", _kd_pos),
        ("EMA20_POS", _ema20_pos),
    ]
    for h in CONFIRMATION_HORIZONS:
        for n in range(2, min(max_combo, len(base_atoms)) + 1):
            for combo in combinations(base_atoms, n):
                label = " AND ".join(a[0] for a in combo) + f"_+{h}"
                parts = [(a[0], a[1], h) for a in combo]
                composites.append((label, parts))
    return composites


def _eval_gate(base: dict, future: List[dict], fn: GateFn, h: int) -> bool:
    if h > len(future) or not future[h - 1]:
        return False
    return fn(base, future, h)


def _eval_composite(base: dict, future: List[dict], parts: List[Tuple[str, GateFn, int]]) -> bool:
    return all(_eval_gate(base, future, fn, h) for _, fn, h in parts)


def enrich_events_with_windows(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict] = None,
) -> pd.DataFrame:
    """이벤트에 confirmation window feature 부착."""
    cache = pipeline_cache if pipeline_cache is not None else {}
    rows = []
    for _, ev in events.iterrows():
        key = (ev["symbol"], ev["timeframe"])
        if key not in cache:
            from analysis.wave_regime_analysis import _load_pipeline
            cache[key] = _load_pipeline(key[0], key[1])
        pipeline = cache[key]
        pos = ev.get("_pos")
        if pos is None:
            pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
        if pos is None:
            continue
        base, future = _window_feats(pipeline, int(pos))
        rows.append({**ev.to_dict(), "_base": base, "_future": future})
    return pd.DataFrame(rows)


def evaluate_gate_metrics(
    enriched: pd.DataFrame,
    gate_name: str,
    gate_fn: Callable[[dict, List[dict]], bool],
) -> dict:
    """precision / recall / coverage / future GradeA rate."""
    if enriched.empty:
        return {
            "gate": gate_name, "precision": None, "recall": None,
            "coverage": None, "positive_rate": None,
            "tp": 0, "fp": 0, "fn": 0, "fired": 0, "total": 0,
        }

    passes = []
    for _, row in enriched.iterrows():
        base = row.get("_base", {})
        future = row.get("_future", [])
        passes.append(gate_fn(base, future))

    enriched = enriched.copy()
    enriched["_pass"] = passes
    fired = enriched[enriched["_pass"]]
    positives = enriched[enriched["success"]]
    tp = len(fired[fired["success"]])
    fp = len(fired[~fired["success"]])
    fn = len(positives[~positives["_pass"]])
    total = len(enriched)

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    coverage = len(fired) / total if total else None
    positive_rate = tp / len(fired) if len(fired) > 0 else None

    return {
        "gate": gate_name,
        "precision": precision,
        "recall": recall,
        "coverage": coverage,
        "positive_rate": positive_rate,
        "tp": tp, "fp": fp, "fn": fn,
        "fired": len(fired), "total": total,
    }


def evaluate_all_gates(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for name, fn, h in build_gate_catalog():
        rows.append(evaluate_gate_metrics(
            enriched, name,
            lambda b, f, _fn=fn, _h=h: _eval_gate(b, f, _fn, _h),
        ))
    rows.sort(key=lambda x: (
        x.get("precision") or 0,
        x.get("recall") or 0,
        x.get("coverage") or 0,
    ), reverse=True)
    return rows


def evaluate_composite_gates(enriched: pd.DataFrame) -> List[dict]:
    rows = []
    for label, parts in build_composite_catalog(max_combo=3):
        rows.append(evaluate_gate_metrics(
            enriched, label,
            lambda b, f, _p=parts: _eval_composite(b, f, _p),
        ))
    rows.sort(key=lambda x: (
        x.get("precision") or 0,
        x.get("recall") or 0,
        x.get("coverage") or 0,
    ), reverse=True)
    return rows


def _funnel_rsi_macd_cumulative(enriched: pd.DataFrame) -> List[dict]:
    """RSI_HOLD + MACD_HOLD cumulative funnel."""
    total = len(enriched)
    s1 = sum(
        1 for _, r in enriched.iterrows()
        if _eval_gate(r["_base"], r["_future"], _rsi_hold, 1)
        and _eval_gate(r["_base"], r["_future"], _macd_hold, 1)
    )
    s2 = sum(
        1 for _, r in enriched.iterrows()
        if all(
            _eval_gate(r["_base"], r["_future"], _rsi_hold, i)
            and _eval_gate(r["_base"], r["_future"], _macd_hold, i)
            for i in range(1, 3)
        )
    )
    s3 = sum(
        1 for _, r in enriched.iterrows()
        if all(
            _eval_gate(r["_base"], r["_future"], _rsi_hold, i)
            and _eval_gate(r["_base"], r["_future"], _macd_hold, i)
            for i in range(1, 4)
        )
    )
    ga = int(enriched["success"].sum())
    return [
        {"stage": "Early Warning", "survivors": total},
        {"stage": "Gate +1", "survivors": s1},
        {"stage": "Gate +2", "survivors": s2},
        {"stage": "Gate +3", "survivors": s3},
        {"stage": "Grade A", "survivors": ga},
    ]


def confirmation_separators(
    enriched: pd.DataFrame,
    horizon: int = 1,
    top_n: int = 20,
) -> List[dict]:
    """Confirmation window 내 SUCCESS vs FAILURE."""
    succ = enriched[enriched["success"]]
    fail = enriched[~enriched["success"]]
    rows = []
    for feat in COMPARE_FEATURES:
        sv, fv = [], []
        for _, row in succ.iterrows():
            f = row["_future"][horizon - 1] if horizon <= len(row["_future"]) else {}
            v = f.get(feat)
            if not _nan(v):
                sv.append(float(v))
        for _, row in fail.iterrows():
            f = row["_future"][horizon - 1] if horizon <= len(row["_future"]) else {}
            v = f.get(feat)
            if not _nan(v):
                fv.append(float(v))
        if not sv or not fv:
            continue
        rows.append({
            "feature": feat,
            "horizon": horizon,
            "success_mean": float(np.mean(sv)),
            "failure_mean": float(np.mean(fv)),
            "effect_size": effect_size(pd.Series(sv), pd.Series(fv)) if len(sv) >= 2 and len(fv) >= 2 else abs(np.mean(sv) - np.mean(fv)),
        })
    rows.sort(key=lambda x: x["effect_size"], reverse=True)
    return rows[:top_n]


def best_confirmation_horizon(enriched: pd.DataFrame) -> dict:
    """+1/+2/+3 중 최고 precision gate horizon."""
    best = {"horizon": None, "gate": None, "precision": None, "recall": None}
    for h in CONFIRMATION_HORIZONS:
        h_gates = []
        for name, fn, gh in build_gate_catalog():
            if gh != h:
                continue
            h_gates.append(evaluate_gate_metrics(
                enriched, name,
                lambda b, f, _fn=fn, _h=h: _eval_gate(b, f, _fn, _h),
            ))
        if not h_gates:
            continue
        h_gates.sort(key=lambda x: (
            x.get("precision") or 0,
            x.get("recall") or 0,
        ), reverse=True)
        top = h_gates[0]
        prec = top.get("precision") or 0
        if best["precision"] is None or prec > best["precision"]:
            best = {
                "horizon": h,
                "gate": top["gate"],
                "precision": top.get("precision"),
                "recall": top.get("recall"),
            }
    return best


def symbol_gate_comparison(
    enriched: pd.DataFrame,
    gate_name: str,
    gate_fn: Callable[[dict, List[dict]], bool],
) -> Dict[str, dict]:
    out = {}
    for sym in GENERALIZATION_SYMBOLS:
        sub = enriched[enriched["symbol"] == sym]
        if sub.empty:
            out[sym] = {"precision": None, "recall": None, "positive_rate": None, "n": 0}
            continue
        m = evaluate_gate_metrics(sub, gate_name, gate_fn)
        out[sym] = {
            "precision": m.get("precision"),
            "recall": m.get("recall"),
            "positive_rate": m.get("positive_rate"),
            "n": m.get("total", 0),
        }
    return out


def build_confirmation_csv(
    enriched: pd.DataFrame,
    top_gates: List[dict],
) -> pd.DataFrame:
    """이벤트 × top gate 평가 CSV."""
    if enriched.empty or not top_gates:
        return pd.DataFrame()

    catalog = {name: (fn, h) for name, fn, h in build_gate_catalog()}
    rows = []
    for gate_info in top_gates[:5]:
        gname = gate_info["gate"]
        if gname not in catalog:
            continue
        fn, h = catalog[gname]
        for _, row in enriched.iterrows():
            base = row["_base"]
            future = row["_future"]
            passed = _eval_gate(base, future, fn, h)
            f = future[h - 1] if h <= len(future) else {}
            rows.append({
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "success": row["success"],
                "gate_name": gname,
                "gate_pass": passed,
                "horizon": h,
                "major_k": f.get("major_k"),
                "major_k_slope_1": f.get("major_k_slope_1"),
                "major_k_minus_d": f.get("major_k_minus_d"),
                "rsi": f.get("rsi"),
                "macd_hist": f.get("macd_hist"),
                "ema20_slope_3": f.get("ema20_slope_3"),
            })
    if not rows:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in rows[0]]
    return pd.DataFrame(rows)[cols]


def full_confirmation_gate_summary() -> dict:
    cache: Dict = {}
    events = build_failure_events(cache)
    enriched = enrich_events_with_windows(events, cache)

    gates = evaluate_all_gates(enriched)
    composites = evaluate_composite_gates(enriched)
    funnel = _funnel_rsi_macd_cumulative(enriched)
    best_h = best_confirmation_horizon(enriched)

    best_gate = gates[0] if gates else {}
    best_composite = composites[0] if composites else {}

    separators = []
    for h in CONFIRMATION_HORIZONS:
        separators.extend(confirmation_separators(enriched, horizon=h))

    separators.sort(key=lambda x: x["effect_size"], reverse=True)
    separators = separators[:20]

    sym_cmp = {}
    if gates:
        gname = gates[0]["gate"]
        cat = {n: (fn, h) for n, fn, h in build_gate_catalog()}
        if gname in cat:
            fn, h = cat[gname]
            sym_cmp = symbol_gate_comparison(
                enriched, gname,
                lambda b, f, _fn=fn, _hh=h: _eval_gate(b, f, _fn, _hh),
            )

    return {
        "events": enriched,
        "gates": gates[:20],
        "composites": composites[:20],
        "funnel": funnel,
        "best_horizon": best_h,
        "separators": separators,
        "symbol_comparison": sym_cmp,
        "best_gate": best_gate,
        "best_composite": best_composite,
        "success_count": int(events["success"].sum()) if not events.empty else 0,
        "failure_count": int((~events["success"]).sum()) if not events.empty else 0,
        "dataframe": build_confirmation_csv(enriched, gates),
    }
