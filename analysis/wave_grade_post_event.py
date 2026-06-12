"""Wave Grade Post-Event — Grade A 발생 후 지연 진입 성과 관측.

Rule Grading/Candidate/Exit/Outcome 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_exit import (
    ALL_POLICIES,
    POLICY_RULES,
    RULE_K_CROSS,
    RULE_K_TURN,
    RULE_NEW_LL,
    RULE_RE_OS,
    RULE_SL3,
    RULE_SL5,
    RULE_TIMEOUT20,
    RULE_TIMEOUT40,
    _build_bar_flags,
    evaluate_policy,
)
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES
from analysis.wave_outcome import _find_bar_index, _forward_return, _mae, _mfe
from analysis.wave_regime_analysis import _load_pipeline
from analysis.wave_rule_grading import events_for_grade

ENTRY_DELAYS = (0, 1, 2, 3)
FORWARD_HORIZONS = (5, 10, 20, 40)
WIN_RATE_TOLERANCE = 0.8

FAILURE_CATEGORIES = (
    "STOP_LOSS",
    "TIMEOUT",
    "K_TURN_DOWN",
    "K_CROSS_DOWN",
    "NEW_LL",
    "RE_OVERSOLD",
)

EXIT_REASON_MAP = {
    RULE_SL3: "STOP_LOSS",
    RULE_SL5: "STOP_LOSS",
    RULE_TIMEOUT20: "TIMEOUT",
    RULE_TIMEOUT40: "TIMEOUT",
    RULE_K_TURN: "K_TURN_DOWN",
    RULE_K_CROSS: "K_CROSS_DOWN",
    RULE_NEW_LL: "NEW_LL",
    RULE_RE_OS: "RE_OVERSOLD",
}

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "delay", "entry_price",
    "return_5", "return_10", "return_20", "return_40",
    "mfe_20", "mae_20", "policy", "policy_return", "exit_reason",
)


def collect_grade_a_events() -> pd.DataFrame:
    """Grade A 이벤트 (BASE_RULE + major_k>=70)."""
    return events_for_grade("A")


def delayed_entry_index(grade_a_idx: int, delay: int, n_bars: int) -> Optional[int]:
    entry_idx = grade_a_idx + delay
    if entry_idx < 0 or entry_idx >= n_bars:
        return None
    return entry_idx


def compute_forward_outcomes(
    ohlcv: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
) -> dict:
    """delay 진입 후 forward return / MFE / MAE."""
    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]
    out: dict = {}
    for n in FORWARD_HORIZONS:
        out[f"return_{n}"] = _forward_return(close, entry_idx, n)
    out["mfe_20"] = _mfe(high, entry_idx, 20, entry_price)
    out["mae_20"] = _mae(low, entry_idx, 20, entry_price)
    return out


def apply_exit_policies(
    entry_idx: int,
    entry_price: float,
    ohlcv: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
) -> List[dict]:
    """각 exit policy 시뮬레이션."""
    results = []
    for policy in ALL_POLICIES:
        rules = POLICY_RULES[policy]
        max_bar = 40 if RULE_TIMEOUT40 in rules else 20
        result = evaluate_policy(
            entry_idx, entry_price, ohlcv, k, d, oversold_entry, ll_new,
            rules, max_bar=max_bar,
        )
        if result is None:
            continue
        results.append({
            "policy": policy,
            "policy_return": result["return_pct"],
            "exit_reason": result["exit_reason"],
            "bars_held": result["bars_held"],
            "win": result["return_pct"] > 0,
        })
    return results


def map_exit_reason(reason: str) -> Optional[str]:
    return EXIT_REASON_MAP.get(reason)


def decay_analysis(df: pd.DataFrame, reference_policy: Optional[str] = None) -> List[dict]:
    """delay별 expectancy / win_rate (참조 policy 또는 전 policy 평균)."""
    if df.empty:
        return []
    rows = []
    for delay in ENTRY_DELAYS:
        sub = df[df["delay"] == delay]
        if reference_policy:
            sub = sub[sub["policy"] == reference_policy]
        if sub.empty:
            rows.append({"delay": delay, "expectancy": None, "win_rate": None, "n": 0})
            continue
        metrics = compute_expectancy_metrics(sub["policy_return"])
        rows.append({
            "delay": delay,
            "expectancy": metrics.get("expectancy"),
            "win_rate": metrics.get("win_rate", 0),
            "n": metrics.get("n", 0),
        })
    return rows


def validity_window(decay_rows: List[dict]) -> int:
    """expectancy > 0 AND win_rate 유지( delay0 대비 80% )인 최대 delay."""
    if not decay_rows:
        return -1
    baseline = next((r for r in decay_rows if r["delay"] == 0), None)
    if baseline is None or baseline.get("win_rate") is None:
        return -1
    base_wr = baseline["win_rate"]
    valid_until = -1
    for row in sorted(decay_rows, key=lambda x: x["delay"]):
        exp = row.get("expectancy")
        wr = row.get("win_rate")
        if exp is not None and exp > 0 and wr is not None and wr >= base_wr * WIN_RATE_TOLERANCE:
            valid_until = row["delay"]
        else:
            break
    return valid_until


def failure_after_grade_a(df: pd.DataFrame, delay: int = 0) -> List[dict]:
    """Grade A 후 exit_reason 분포 (delay=0 기본)."""
    sub = df[df["delay"] == delay]
    if sub.empty:
        return []
    counts = Counter()
    for reason in sub["exit_reason"].dropna():
        cat = map_exit_reason(str(reason))
        if cat:
            counts[cat] += 1
    total = sum(counts.values())
    return [
        {"category": cat, "count": counts.get(cat, 0),
         "pct": counts.get(cat, 0) / total * 100.0 if total else 0.0}
        for cat in FAILURE_CATEGORIES
    ]


def delay_outcome_summary(df: pd.DataFrame) -> List[dict]:
    """delay별 win_rate / expectancy (전 policy)."""
    rows = []
    for delay in ENTRY_DELAYS:
        sub = df[df["delay"] == delay]
        if sub.empty:
            rows.append({"delay": delay, "win_rate": None, "expectancy": None, "n": 0})
            continue
        metrics = compute_expectancy_metrics(sub["policy_return"])
        rows.append({
            "delay": delay,
            "win_rate": metrics.get("win_rate", 0),
            "expectancy": metrics.get("expectancy"),
            "n": metrics.get("n", 0),
        })
    return rows


def forward_return_summary(df: pd.DataFrame) -> List[dict]:
    """delay별 평균 forward return."""
    rows = []
    for delay in ENTRY_DELAYS:
        sub = df[df["delay"] == delay].drop_duplicates(
            subset=["timestamp", "symbol", "timeframe", "delay"],
        )
        if sub.empty:
            rows.append({"delay": delay})
            continue
        row = {"delay": delay}
        for n in FORWARD_HORIZONS:
            col = f"return_{n}"
            vals = sub[col].dropna().astype(float)
            row[col] = float(vals.mean()) * 100.0 if len(vals) else None
        for col in ("mfe_20", "mae_20"):
            vals = sub[col].dropna().astype(float)
            row[col] = float(vals.mean()) * 100.0 if len(vals) else None
        rows.append(row)
    return rows


def exit_policy_by_delay(df: pd.DataFrame) -> List[dict]:
    """delay × policy expectancy."""
    rows = []
    for delay in ENTRY_DELAYS:
        for policy in ALL_POLICIES:
            sub = df[(df["delay"] == delay) & (df["policy"] == policy)]
            if sub.empty:
                continue
            metrics = compute_expectancy_metrics(sub["policy_return"])
            rows.append({
                "delay": delay,
                "policy": policy,
                "expectancy": metrics.get("expectancy"),
                "win_rate": metrics.get("win_rate", 0),
                "profit_factor": metrics.get("profit_factor"),
                "avg_bars_held": float(sub["bars_held"].mean()) if "bars_held" in sub else None,
                "n": metrics.get("n", 0),
            })
    return rows


def best_policy_by_delay(df: pd.DataFrame) -> List[dict]:
    rows = []
    policy_rows = exit_policy_by_delay(df)
    for delay in ENTRY_DELAYS:
        sub = [r for r in policy_rows if r["delay"] == delay and r.get("expectancy") is not None]
        if not sub:
            continue
        rows.append(max(sub, key=lambda x: x["expectancy"]))
    return rows


def symbol_tf_comparison(df: pd.DataFrame) -> List[dict]:
    """symbol × tf × delay expectancy."""
    rows = []
    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            for delay in ENTRY_DELAYS:
                sub = df[
                    (df["symbol"] == sym) & (df["timeframe"] == tf) & (df["delay"] == delay)
                ]
                if sub.empty:
                    continue
                metrics = compute_expectancy_metrics(sub["policy_return"])
                rows.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "delay": delay,
                    "expectancy": metrics.get("expectancy"),
                    "win_rate": metrics.get("win_rate", 0),
                    "n": metrics.get("n", 0),
                })
    return rows


def build_post_event_results(cache: Optional[Dict] = None) -> pd.DataFrame:
    """Grade A × delay × policy 전체 행 생성."""
    events = collect_grade_a_events()
    if events.empty:
        return pd.DataFrame()

    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    flags_cache: Dict[Tuple[str, str], Tuple] = {}
    rows: List[dict] = []

    for _, ev in events.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev["timeframe"])
        key = (sym, tf)
        if key not in pipeline_cache:
            pipeline = _load_pipeline(sym, tf)
            if pipeline.empty:
                continue
            pipeline_cache[key] = pipeline
            flags_cache[key] = _build_bar_flags(pipeline)
        pipeline = pipeline_cache[key]
        k, d, os_entry, ll_new = flags_cache[key]

        grade_idx = _find_bar_index(pipeline, pd.Timestamp(ev["timestamp"]))
        if grade_idx is None:
            continue

        for delay in ENTRY_DELAYS:
            entry_idx = delayed_entry_index(grade_idx, delay, len(pipeline))
            if entry_idx is None:
                continue
            entry_price = float(pipeline["close"].iloc[entry_idx])
            if pd.isna(entry_price) or entry_price == 0:
                continue

            fwd = compute_forward_outcomes(pipeline, entry_idx, entry_price)
            policies = apply_exit_policies(
                entry_idx, entry_price, pipeline, k, d, os_entry, ll_new,
            )
            if not policies:
                continue

            for pol in policies:
                rows.append({
                    "timestamp": pd.Timestamp(ev["timestamp"]),
                    "symbol": sym,
                    "timeframe": tf,
                    "delay": delay,
                    "entry_price": entry_price,
                    **fwd,
                    "policy": pol["policy"],
                    "policy_return": pol["policy_return"],
                    "exit_reason": pol["exit_reason"],
                    "bars_held": pol["bars_held"],
                })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def build_post_event_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    return df[cols].copy()


def full_post_event_summary(cache: Optional[Dict] = None) -> dict:
    df = build_post_event_results(cache)
    ref_policy = "TP5_SL3_TIMEOUT40"
    decay = decay_analysis(df, reference_policy=ref_policy)
    return {
        "dataframe": build_post_event_csv(df),
        "raw": df,
        "event_count": len(collect_grade_a_events()),
        "delay_outcomes": delay_outcome_summary(df),
        "forward_returns": forward_return_summary(df),
        "exit_policy_by_delay": exit_policy_by_delay(df),
        "best_policy_by_delay": best_policy_by_delay(df),
        "decay": decay,
        "valid_until_delay": validity_window(decay),
        "failure_distribution": failure_after_grade_a(df, delay=0),
        "symbol_tf_comparison": symbol_tf_comparison(df),
        "reference_policy": ref_policy,
    }
