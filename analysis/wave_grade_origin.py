"""Wave Grade Origin — Grade A 생성 메커니즘 관측 분석.

Rule Grading/Regime/Branch/Path 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import effect_size
from analysis.wave_generalization import (
    GENERALIZATION_SYMBOLS,
    GENERALIZATION_TIMEFRAMES,
)
from analysis.wave_outcome import _find_bar_index
from analysis.wave_path_analysis import build_path_rows
from analysis.wave_regime_analysis import _load_pipeline, extract_regime_at
from analysis.wave_rule_grading import collect_base_events, collect_rule_events
from config.settings import WAVE_LAYER_ROLES

GRADE_A = "GRADE_A"
GRADE_BC = "GRADE_BC"
GRADE_D = "GRADE_D"

MAJOR_K_THRESHOLD = 70
TIMELINE_OFFSETS = (-20, -10, -5, -3, -1, 0)
LEAD_OFFSETS = (5, 10, 20)
TIMELINE_METRICS = ("major_k", "rsi", "macd", "ema20_slope_3", "atr_pct")

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]

ORIGIN_FEATURES = (
    "ema20_slope_3", "ema60_slope_3", "ema120_slope_3",
    "major_k", "major_d", "major_k_minus_d", "major_k_slope_1", "major_k_slope_3",
    "rsi", "rsi_slope_1", "rsi_slope_3",
    "macd", "macd_signal", "macd_hist", "macd_gap",
    "atr_pct", "volatility_20",
    "dist_ema20_pct", "dist_ema60_pct", "dist_ema120_pct",
)

CAUSALITY_FEATURES = (
    ("ema20_slope_3", "EMA slope"),
    ("rsi", "RSI"),
    ("macd_hist", "MACD"),
    ("major_k", "major_k"),
)

CSV_EXPORT_COLS = (
    "timestamp", "grade", "symbol", "timeframe",
    "major_k", "major_d", "major_k_slope_1",
    "rsi", "rsi_slope_1",
    "macd", "macd_hist",
    "atr_pct", "volatility_20",
    "dist_ema60_pct", "path", "branch",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def classify_grade(major_k: Optional[float]) -> Optional[str]:
    if major_k is None or (isinstance(major_k, float) and np.isnan(major_k)):
        return None
    return GRADE_A if float(major_k) >= MAJOR_K_THRESHOLD else GRADE_BC


def extract_origin_features(pipeline: pd.DataFrame, pos: int) -> dict:
    """이벤트 봉 origin feature 추출."""
    if pos < 0 or pos >= len(pipeline):
        return {}
    regime = extract_regime_at(pipeline, pos)
    row = pipeline.iloc[pos]

    k_col = f"stoch_k_{_LAYER_LARGE}"
    d_col = f"stoch_d_{_LAYER_LARGE}"
    major_k = regime.get("major_k")
    major_d = None
    if d_col in pipeline.columns and pd.notna(row.get(d_col)):
        major_d = float(row[d_col])

    major_k_slope_3 = None
    if major_k is not None and k_col in pipeline.columns and pos >= 3:
        prev = pipeline[k_col].iloc[pos - 3]
        if pd.notna(prev):
            major_k_slope_3 = float(major_k) - float(prev)

    rsi_slope_3 = None
    if "rsi" in pipeline.columns and pos >= 3:
        cur_rsi = row.get("rsi")
        prev_rsi = pipeline["rsi"].iloc[pos - 3]
        if pd.notna(cur_rsi) and pd.notna(prev_rsi):
            rsi_slope_3 = float(cur_rsi) - float(prev_rsi)

    macd = float(row["macd"]) if pd.notna(row.get("macd")) else None
    macd_signal = float(row["macd_signal"]) if pd.notna(row.get("macd_signal")) else None
    macd_hist = regime.get("macd_hist")
    macd_gap = (macd - macd_signal) if macd is not None and macd_signal is not None else None

    kd = (major_k - major_d) if major_k is not None and major_d is not None else None

    return {
        **regime,
        "major_d": major_d,
        "major_k_minus_d": kd,
        "major_k_slope_3": major_k_slope_3,
        "rsi_slope_3": rsi_slope_3,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "macd_gap": macd_gap,
    }


def features_at_offset(
    pipeline: pd.DataFrame,
    event_pos: int,
    offset: int,
) -> dict:
    return extract_origin_features(pipeline, event_pos + offset)


def _load_branch_df(symbol: str, tf: str) -> pd.DataFrame:
    path = _csv_path("wave_branch", symbol, tf)
    if os.path.isfile(path):
        return pd.read_csv(path, parse_dates=["timestamp"])
    return pd.DataFrame()


def _load_paths_df(symbol: str, tf: str) -> pd.DataFrame:
    path = _csv_path("wave_paths", symbol, tf)
    if os.path.isfile(path):
        return pd.read_csv(path, parse_dates=["timestamp"])
    built = build_path_rows(symbol, tf)
    return built if not built.empty else pd.DataFrame()


def _lookup_branch(ts: pd.Timestamp, branch_df: pd.DataFrame) -> Optional[str]:
    if branch_df.empty:
        return None
    keyed = branch_df.set_index("timestamp")
    if ts in keyed.index:
        return str(keyed.loc[ts, "branch"])
    idx = keyed.index.searchsorted(ts)
    if idx < len(keyed) and abs((keyed.index[idx] - ts).total_seconds()) < 3600:
        return str(keyed.iloc[idx]["branch"])
    if idx > 0 and abs((keyed.index[idx - 1] - ts).total_seconds()) < 3600:
        return str(keyed.iloc[idx - 1]["branch"])
    return None


def _lookup_path(ts: pd.Timestamp, paths_df: pd.DataFrame) -> Optional[str]:
    if paths_df.empty:
        return None
    keyed = paths_df.set_index("timestamp")
    if ts in keyed.index:
        v = keyed.loc[ts, "path"]
        return str(v.iloc[-1] if isinstance(v, pd.Series) else v)
    idx = keyed.index.searchsorted(ts)
    best = None
    best_delta = None
    for i in (idx - 1, idx):
        if 0 <= i < len(keyed):
            delta = abs((keyed.index[i] - ts).total_seconds())
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best = str(keyed.iloc[i]["path"])
    if best_delta is not None and best_delta <= 86400 * 2:
        return best
    return None


def collect_origin_events(
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> pd.DataFrame:
    """BASE_RULE 이벤트 + GRADE_A / GRADE_BC 분류 + origin feature."""
    base = collect_base_events()
    if base.empty:
        return pd.DataFrame()

    cache = pipeline_cache if pipeline_cache is not None else {}
    rows: List[dict] = []

    for _, ev in base.iterrows():
        sym = ev["symbol"]
        tf = ev["timeframe"]
        ts = pd.Timestamp(ev["timestamp"])
        key = (sym, tf)
        if key not in cache:
            cache[key] = _load_pipeline(sym, tf)
        pipeline = cache[key]
        if pipeline.empty:
            continue

        pos = _find_bar_index(pipeline, ts)
        if pos is None:
            continue

        feats = extract_origin_features(pipeline, pos)
        grade = classify_grade(feats.get("major_k"))
        if grade is None:
            continue

        branch_df = _load_branch_df(sym, tf)
        paths_df = _load_paths_df(sym, tf)

        rows.append({
            "timestamp": ts,
            "symbol": sym,
            "timeframe": tf,
            "grade": grade,
            "return_pct": ev.get("return_pct"),
            "success": ev.get("success"),
            "path": _lookup_path(ts, paths_df),
            "branch": _lookup_branch(ts, branch_df),
            **feats,
        })

    return pd.DataFrame(rows)


def collect_grade_d_events(
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> pd.DataFrame:
    """RULE_A (GRADE_D) 참조 이벤트."""
    raw = collect_rule_events("RULE_A")
    if raw.empty:
        return pd.DataFrame()
    cache = pipeline_cache if pipeline_cache is not None else {}
    rows: List[dict] = []
    for _, ev in raw.iterrows():
        sym, tf = ev["symbol"], ev["timeframe"]
        ts = pd.Timestamp(ev["timestamp"])
        key = (sym, tf)
        if key not in cache:
            cache[key] = _load_pipeline(sym, tf)
        pipeline = cache[key]
        pos = _find_bar_index(pipeline, ts) if not pipeline.empty else None
        feats = extract_origin_features(pipeline, pos) if pos is not None else {}
        rows.append({
            "timestamp": ts, "symbol": sym, "timeframe": tf,
            "grade": GRADE_D, **feats,
        })
    return pd.DataFrame(rows)


def compare_a_vs_bc(events: pd.DataFrame) -> List[dict]:
    """A vs BC feature 평균 비교."""
    a = events[events["grade"] == GRADE_A]
    bc = events[events["grade"] == GRADE_BC]
    rows = []
    for feat in ORIGIN_FEATURES:
        if feat not in events.columns:
            continue
        av = a[feat].dropna()
        bv = bc[feat].dropna()
        rows.append({
            "feature": feat,
            "a_mean": float(av.mean()) if len(av) else None,
            "bc_mean": float(bv.mean()) if len(bv) else None,
            "delta": (
                float(av.mean()) - float(bv.mean())
                if len(av) and len(bv) else None
            ),
            "effect_size": effect_size(av, bv) if len(av) and len(bv) else 0.0,
        })
    return sorted(rows, key=lambda x: x["effect_size"], reverse=True)


def build_origin_timeline(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
) -> List[dict]:
    """Grade A 이벤트 전 timeline offset별 평균."""
    a_events = events[events["grade"] == GRADE_A]
    if a_events.empty:
        return []

    cache = pipeline_cache if pipeline_cache is not None else {}
    buckets: Dict[int, List[dict]] = {o: [] for o in TIMELINE_OFFSETS}

    for _, ev in a_events.iterrows():
        key = (ev["symbol"], ev["timeframe"])
        if key not in cache:
            cache[key] = _load_pipeline(key[0], key[1])
        pipeline = cache[key]
        pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
        if pos is None:
            continue
        for offset in TIMELINE_OFFSETS:
            if pos + offset < 0:
                continue
            buckets[offset].append(features_at_offset(pipeline, pos, offset))

    rows = []
    for offset in TIMELINE_OFFSETS:
        parts = buckets[offset]
        if not parts:
            rows.append({"offset": offset})
            continue
        pdf = pd.DataFrame(parts)
        row = {"offset": offset}
        for m in TIMELINE_METRICS:
            if m in pdf.columns:
                row[m] = float(pdf[m].dropna().mean()) if pdf[m].notna().any() else None
        rows.append(row)
    return rows


def path_distribution(events: pd.DataFrame) -> List[dict]:
    """GRADE_A path 비율."""
    a = events[events["grade"] == GRADE_A].dropna(subset=["path"])
    if a.empty:
        return []
    total = len(a)
    counts = a["path"].value_counts()
    return [
        {"path": path, "count": int(cnt), "pct": cnt / total * 100.0}
        for path, cnt in counts.items()
    ]


def branch_distribution(events: pd.DataFrame) -> List[dict]:
    """GRADE_A vs GRADE_BC branch 비율."""
    rows = []
    for branch in sorted(events["branch"].dropna().unique()):
        a_cnt = len(events[(events["grade"] == GRADE_A) & (events["branch"] == branch)])
        bc_cnt = len(events[(events["grade"] == GRADE_BC) & (events["branch"] == branch)])
        rows.append({"branch": branch, "a": a_cnt, "bc": bc_cnt})
    return sorted(rows, key=lambda x: x["a"] + x["bc"], reverse=True)


def compute_separators(events: pd.DataFrame, top_n: int = 20) -> List[dict]:
    """A vs BC effect size Top N."""
    return compare_a_vs_bc(events)[:top_n]


def compute_lead_indicators(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    top_n: int = 20,
) -> List[dict]:
    """Grade A 발생 N봉 전 lead indicator 탐색."""
    a = events[events["grade"] == GRADE_A]
    bc = events[events["grade"] == GRADE_BC]
    if a.empty or bc.empty:
        return []

    cache = pipeline_cache if pipeline_cache is not None else {}
    results: List[dict] = []

    for lead in LEAD_OFFSETS:
        a_feats: List[dict] = []
        bc_feats: List[dict] = []
        for subset, bucket in ((a, a_feats), (bc, bc_feats)):
            for _, ev in subset.iterrows():
                key = (ev["symbol"], ev["timeframe"])
                if key not in cache:
                    cache[key] = _load_pipeline(key[0], key[1])
                pipeline = cache[key]
                pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
                if pos is None or pos - lead < 0:
                    continue
                bucket.append(features_at_offset(pipeline, pos, -lead))

        if not a_feats or not bc_feats:
            continue
        adf = pd.DataFrame(a_feats)
        bdf = pd.DataFrame(bc_feats)
        for feat in ORIGIN_FEATURES:
            if feat not in adf.columns:
                continue
            av = adf[feat].dropna()
            bv = bdf[feat].dropna()
            if len(av) < 2 or len(bv) < 2:
                continue
            es = effect_size(av, bv)
            if es > 0:
                results.append({
                    "feature": feat,
                    "effect_size": es,
                    "lead_bars": lead,
                    "a_mean": float(av.mean()),
                    "bc_mean": float(bv.mean()),
                })

    results.sort(key=lambda x: x["effect_size"], reverse=True)
    return results[:top_n]


def pseudo_causality_order(
    events: pd.DataFrame,
    pipeline_cache: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None,
    threshold: float = 0.3,
) -> List[dict]:
    """관측용 pseudo-causality — 직전 무엇이 먼저 좋아지는가."""
    a = events[events["grade"] == GRADE_A]
    bc = events[events["grade"] == GRADE_BC]
    if a.empty or bc.empty:
        return []

    cache = pipeline_cache if pipeline_cache is not None else {}
    offsets = list(range(-20, 1))
    first_seen: Dict[str, int] = {}

    for feat, _label in CAUSALITY_FEATURES:
        for offset in offsets:
            a_vals, bc_vals = [], []
            for subset, bucket in ((a, a_vals), (bc, bc_vals)):
                for _, ev in subset.iterrows():
                    key = (ev["symbol"], ev["timeframe"])
                    if key not in cache:
                        cache[key] = _load_pipeline(key[0], key[1])
                    pipeline = cache[key]
                    pos = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
                    if pos is None or pos + offset < 0:
                        continue
                    f = features_at_offset(pipeline, pos, offset)
                    if feat in f and f[feat] is not None:
                        bucket.append(float(f[feat]))
            if len(a_vals) < 2 or len(bc_vals) < 2:
                continue
            es = effect_size(pd.Series(a_vals), pd.Series(bc_vals))
            if es >= threshold and feat not in first_seen:
                first_seen[feat] = abs(offset)

    ordered = sorted(first_seen.items(), key=lambda x: x[1], reverse=True)
    label_map = {f: lbl for f, lbl in CAUSALITY_FEATURES}
    return [
        {"feature": label_map.get(f, f), "first_offset": off, "bars_before": off}
        for f, off in ordered
    ]


def symbol_comparison(events: pd.DataFrame) -> Dict[str, dict]:
    """심볼별 A vs BC separator 요약."""
    out = {}
    for sym in GENERALIZATION_SYMBOLS:
        sub = events[events["symbol"] == sym]
        a = sub[sub["grade"] == GRADE_A]
        bc = sub[sub["grade"] == GRADE_BC]
        if a.empty and bc.empty:
            out[sym] = {"a_n": 0, "bc_n": 0, "top_separator": None, "top_effect": None}
            continue
        seps = compare_a_vs_bc(sub)
        top = seps[0] if seps else {}
        out[sym] = {
            "a_n": len(a),
            "bc_n": len(bc),
            "top_separator": top.get("feature"),
            "top_effect": top.get("effect_size"),
            "a_avg_major_k": float(a["major_k"].dropna().mean()) if "major_k" in a.columns and a["major_k"].notna().any() else None,
            "bc_avg_major_k": float(bc["major_k"].dropna().mean()) if "major_k" in bc.columns and bc["major_k"].notna().any() else None,
        }
    return out


def build_origin_csv(events: pd.DataFrame) -> pd.DataFrame:
    """Per-event origin CSV."""
    if events.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in events.columns]
    return events[cols].copy()


def full_grade_origin_summary() -> dict:
    """전체 origin 분석 payload."""
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    events = collect_origin_events(pipeline_cache)
    grade_d = collect_grade_d_events(pipeline_cache)

    comparison = compare_a_vs_bc(events) if not events.empty else []
    timeline = build_origin_timeline(events, pipeline_cache) if not events.empty else []
    paths = path_distribution(events) if not events.empty else []
    branches = branch_distribution(events) if not events.empty else []
    separators = compute_separators(events) if not events.empty else []
    leads = compute_lead_indicators(events, pipeline_cache) if not events.empty else []
    causality = pseudo_causality_order(events, pipeline_cache) if not events.empty else []
    sym_cmp = symbol_comparison(events) if not events.empty else {}

    a_n = len(events[events["grade"] == GRADE_A]) if not events.empty else 0
    bc_n = len(events[events["grade"] == GRADE_BC]) if not events.empty else 0

    return {
        "events": events,
        "grade_d_count": len(grade_d),
        "a_count": a_n,
        "bc_count": bc_n,
        "comparison": comparison,
        "timeline": timeline,
        "paths": paths,
        "branches": branches,
        "separators": separators,
        "lead_indicators": leads,
        "causality_order": causality,
        "symbol_comparison": sym_cmp,
        "dataframe": build_origin_csv(events),
    }
