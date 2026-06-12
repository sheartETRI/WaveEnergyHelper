"""Wave Live Forward Journal — Live Watchlist 이벤트 forward 추적.

wave_live_watchlist.csv + observation CSV + OHLCV만 소비. 엔진·신호 변경 없음.
"""
from __future__ import annotations

import hashlib
import os
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_exit import (
    RULE_K_CROSS,
    RULE_K_TURN,
    RULE_NEW_LL,
    RULE_RE_OS,
    RULE_SL3,
    RULE_TIMEOUT20,
    RULE_TIMEOUT40,
    _build_bar_flags,
    _hits_at_bar,
)
from analysis.wave_live_watchlist import WATCH_RULES
from analysis.wave_money_flow import add_money_flow_features, extract_money_flow_at
from analysis.wave_outcome import _find_bar_index, _forward_return, _mae, _mfe
from analysis.wave_regime_analysis import _load_pipeline
from analysis.wave_structure_confirmation import (
    extract_structure_at,
    find_swing_highs,
    find_swing_lows,
)
from analysis.wave_volume_energy import _load_ohlcv, add_volume_features, extract_volume_at

FORWARD_HORIZONS = (5, 10, 20, 40)
FLAT_THRESHOLD_PCT = 0.1

FAILURE_CAUSES = (
    "STOP_LOSS_3",
    "TIMEOUT",
    "K_TURN_DOWN",
    "K_CROSS_DOWN",
    "RE_OVERSOLD",
    "NEW_LL",
    "STRUCTURE_FAIL",
    "MONEY_FLOW_DROP",
    "ENERGY_DROP",
)

EXIT_TO_CAUSE = {
    RULE_SL3: "STOP_LOSS_3",
    RULE_TIMEOUT20: "TIMEOUT",
    RULE_TIMEOUT40: "TIMEOUT",
    RULE_K_TURN: "K_TURN_DOWN",
    RULE_K_CROSS: "K_CROSS_DOWN",
    RULE_RE_OS: "RE_OVERSOLD",
    RULE_NEW_LL: "NEW_LL",
}

BACKTEST_EXPECT = {
    "RULE_A": 3.0,
    "RULE_B": 3.0,
    "RULE_C": 1.49,
}

CSV_EXPORT_COLS = (
    "event_id", "timestamp", "symbol", "timeframe", "rule",
    "freshness", "watchlist_score", "money_flow_score", "energy_score",
    "structure_score", "quality_score",
    "return_5", "return_10", "return_20", "return_40",
    "mfe_20", "mae_20", "mfe_40", "mae_40",
    "outcome_5", "outcome_10", "outcome_20", "outcome_40",
    "status", "pending_horizon", "failure_cause", "bars_elapsed",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def make_event_id(symbol: str, timeframe: str, rule: str, ts: pd.Timestamp) -> str:
    """고유 event_id 생성."""
    raw = f"{symbol}|{timeframe}|{rule}|{pd.Timestamp(ts).isoformat()}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:8]
    stamp = pd.Timestamp(ts).strftime("%Y%m%d%H%M")
    return f"E_{symbol}_{timeframe}_{rule}_{stamp}_{digest}"


def load_watchlist_events() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_live_watchlist.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


def outcome_label(return_pct: Optional[float]) -> Optional[str]:
    if return_pct is None or (isinstance(return_pct, float) and np.isnan(return_pct)):
        return None
    if abs(return_pct) < FLAT_THRESHOLD_PCT:
        return "FLAT"
    return "WIN" if return_pct > 0 else "LOSS"


def classify_status(bars_elapsed: int) -> Tuple[str, Optional[int]]:
    """Event status + 다음 pending horizon."""
    if bars_elapsed >= 40:
        return "COMPLETED", None
    if bars_elapsed >= 20:
        return "PENDING_40", 40
    if bars_elapsed >= 10:
        return "PENDING_20", 20
    if bars_elapsed >= 5:
        return "PENDING_10", 10
    return "PENDING_5", 5


def _pct(val: Optional[float]) -> Optional[float]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return round(float(val) * 100.0, 4)


def compute_forward_fields(
    ohlcv: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
) -> dict:
    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]
    out: dict = {}
    for h in FORWARD_HORIZONS:
        out[f"return_{h}"] = _pct(_forward_return(close, entry_idx, h))
    out["mfe_20"] = _pct(_mfe(high, entry_idx, 20, entry_price))
    out["mae_20"] = _pct(_mae(low, entry_idx, 20, entry_price))
    out["mfe_40"] = _pct(_mfe(high, entry_idx, 40, entry_price))
    out["mae_40"] = _pct(_mae(low, entry_idx, 40, entry_price))
    return out


def _feature_at(
    combined: pd.DataFrame,
    swing_lows,
    swing_highs,
    pos: int,
) -> dict:
    vol = extract_volume_at(combined, pos)
    mf = extract_money_flow_at(combined, pos)
    st = extract_structure_at(combined, pos, swing_lows, swing_highs)
    return {
        "money_flow_score": int(mf.get("money_flow_score", 0) or 0),
        "energy_score": int(vol.get("energy_score", 0) or 0),
        "structure_score": int(st.get("structure_score", 0) or 0),
    }


def detect_failure_cause(
    entry_idx: int,
    horizon: int,
    entry_price: float,
    ohlcv: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    entry_mf: int,
    entry_struct: int,
    entry_energy: int,
    feature_fn: Callable[[int], dict],
) -> Optional[str]:
    """실패 이벤트 원인 (가능한 경우)."""
    end = min(entry_idx + horizon, len(ohlcv) - 1)
    if end <= entry_idx:
        return None

    priority = (
        RULE_SL3, RULE_NEW_LL, RULE_K_CROSS, RULE_K_TURN,
        RULE_RE_OS, RULE_TIMEOUT20, RULE_TIMEOUT40,
    )
    first_hit: Optional[str] = None
    for t in range(entry_idx + 1, end + 1):
        hits = _hits_at_bar(t, entry_idx, entry_price, ohlcv, k, d, oversold_entry, ll_new)
        for rule in priority:
            if rule in hits:
                first_hit = EXIT_TO_CAUSE.get(rule, rule)
                break
        if first_hit:
            break

    struct_fail = False
    mf_drop = False
    en_drop = False
    for t in range(entry_idx + 1, end + 1):
        feats = feature_fn(t)
        if entry_struct >= 3 and feats["structure_score"] < 3:
            struct_fail = True
        if entry_mf >= 4 and feats["money_flow_score"] < 4:
            mf_drop = True
        if entry_energy >= 3 and feats["energy_score"] < 3:
            en_drop = True

    if first_hit == "STOP_LOSS_3":
        return "STOP_LOSS_3"
    if struct_fail:
        return "STRUCTURE_FAIL"
    if mf_drop:
        return "MONEY_FLOW_DROP"
    if en_drop:
        return "ENERGY_DROP"
    if first_hit:
        return first_hit
    return "TIMEOUT"


def build_journal_row(
    ev: pd.Series,
    ohlcv: pd.DataFrame,
    combined: pd.DataFrame,
    pipeline: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    swing_lows,
    swing_highs,
) -> Optional[dict]:
    ts = pd.Timestamp(ev["timestamp"])
    sym = str(ev["symbol"])
    tf = str(ev["timeframe"])
    rule = str(ev["rule"])

    entry_idx = _find_bar_index(ohlcv, ts)
    if entry_idx is None or entry_idx >= len(ohlcv):
        return None

    entry_price = float(ohlcv["close"].iloc[entry_idx])
    if entry_price <= 0:
        return None

    last_idx = len(ohlcv) - 1
    bars_elapsed = last_idx - entry_idx
    status, pending_horizon = classify_status(bars_elapsed)

    fwd = compute_forward_fields(ohlcv, entry_idx, entry_price)
    outcomes = {f"outcome_{h}": outcome_label(fwd.get(f"return_{h}")) for h in FORWARD_HORIZONS}

    entry_mf = int(ev.get("money_flow_score", 0) or 0)
    entry_struct = int(ev.get("structure_score", 0) or 0)
    entry_energy = int(ev.get("energy_score", 0) or 0)

    failure_cause = None
    ret20 = fwd.get("return_20")
    if ret20 is not None and ret20 < -FLAT_THRESHOLD_PCT and bars_elapsed >= 20:
        failure_cause = detect_failure_cause(
            entry_idx, 20, entry_price, ohlcv, k, d, oversold_entry, ll_new,
            entry_mf, entry_struct, entry_energy,
            lambda pos: _feature_at(combined, swing_lows, swing_highs, pos),
        )
    elif ret20 is not None and ret20 <= FLAT_THRESHOLD_PCT and bars_elapsed >= 20:
        failure_cause = detect_failure_cause(
            entry_idx, 20, entry_price, ohlcv, k, d, oversold_entry, ll_new,
            entry_mf, entry_struct, entry_energy,
            lambda pos: _feature_at(combined, swing_lows, swing_highs, pos),
        )

    return {
        "event_id": make_event_id(sym, tf, rule, ts),
        "timestamp": ts,
        "symbol": sym,
        "timeframe": tf,
        "rule": rule,
        "freshness": str(ev.get("freshness", "")),
        "watchlist_score": float(ev.get("watchlist_score", 0) or 0),
        "money_flow_score": entry_mf,
        "energy_score": entry_energy,
        "structure_score": entry_struct,
        "quality_score": int(ev.get("quality_score", 0) or 0),
        **fwd,
        **outcomes,
        "status": status,
        "pending_horizon": pending_horizon,
        "failure_cause": failure_cause,
        "bars_elapsed": bars_elapsed,
    }


def build_forward_journal(events: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Live Event Journal + Forward Tracking."""
    if events is None:
        events = load_watchlist_events()
    if events.empty:
        return pd.DataFrame()

    ohlcv_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    combined_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    flags_cache: Dict[Tuple[str, str], Tuple] = {}
    swing_cache: Dict[Tuple[str, str], Tuple] = {}

    rows: List[dict] = []
    for _, ev in events.iterrows():
        key = (str(ev["symbol"]), str(ev["timeframe"]))
        if key not in ohlcv_cache:
            bare = _load_ohlcv(key[0], key[1])
            ohlcv_cache[key] = bare
            if bare.empty:
                continue
            combined = add_money_flow_features(add_volume_features(bare))
            combined_cache[key] = combined
            pipeline_cache[key] = _load_pipeline(key[0], key[1])
            pipe = pipeline_cache[key]
            if not pipe.empty:
                k, d, os_e, ll = _build_bar_flags(pipe)
                flags_cache[key] = (k, d, os_e, ll)
            else:
                flags_cache[key] = (
                    pd.Series([np.nan] * len(bare)),
                    pd.Series([np.nan] * len(bare)),
                    pd.Series([False] * len(bare)),
                    pd.Series([False] * len(bare)),
                )
            swing_cache[key] = (
                find_swing_lows(combined["low"]),
                find_swing_highs(combined["high"]),
            )

        ohlcv = ohlcv_cache.get(key)
        if ohlcv is None or ohlcv.empty:
            continue
        k, d, os_e, ll = flags_cache[key]
        sw_lows, sw_highs = swing_cache[key]
        row = build_journal_row(
            ev, ohlcv, combined_cache[key], pipeline_cache[key],
            k, d, os_e, ll, sw_lows, sw_highs,
        )
        if row:
            rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _win_rate(series: pd.Series) -> Optional[float]:
    wins = series[series == "WIN"]
    labeled = series.dropna()
    if labeled.empty:
        return None
    return round(len(wins) / len(labeled) * 100.0, 2)


def rule_cohort_summary(journal: pd.DataFrame) -> List[dict]:
    rows = []
    for rule in WATCH_RULES:
        sub = journal[journal["rule"] == rule]
        if sub.empty:
            rows.append({"rule": rule, "n": 0})
            continue
        completed = sub[sub["status"] == "COMPLETED"]
        pending = sub[sub["status"] != "COMPLETED"]
        row = {
            "rule": rule,
            "n": len(sub),
            "completed_n": len(completed),
            "pending_n": len(pending),
        }
        for h in FORWARD_HORIZONS:
            col = f"outcome_{h}"
            row[f"win_rate_{h}"] = _win_rate(sub[col])
        for h in (20, 40):
            vals = sub[f"return_{h}"].dropna()
            row[f"avg_return_{h}"] = round(float(vals.mean()), 2) if len(vals) else None
        row["backtest_expect_20"] = BACKTEST_EXPECT.get(rule)
        row["delta_vs_backtest"] = (
            round(row["avg_return_20"] - row["backtest_expect_20"], 2)
            if row.get("avg_return_20") is not None else None
        )
        rows.append(row)
    return rows


def symbol_summary(journal: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in sorted(journal["symbol"].unique()):
        sub = journal[journal["symbol"] == sym]
        row = {"symbol": sym, "n": len(sub), "completed_n": int((sub["status"] == "COMPLETED").sum())}
        for h in FORWARD_HORIZONS:
            row[f"win_rate_{h}"] = _win_rate(sub[f"outcome_{h}"])
        for h in (20, 40):
            vals = sub[f"return_{h}"].dropna()
            row[f"avg_return_{h}"] = round(float(vals.mean()), 2) if len(vals) else None
        rows.append(row)
    return rows


def timeframe_summary(journal: pd.DataFrame) -> List[dict]:
    rows = []
    for tf in sorted(journal["timeframe"].unique(), key=lambda x: ("1h", "4h", "1d").index(x) if x in ("1h", "4h", "1d") else 99):
        sub = journal[journal["timeframe"] == tf]
        row = {"timeframe": tf, "n": len(sub), "completed_n": int((sub["status"] == "COMPLETED").sum())}
        for h in FORWARD_HORIZONS:
            row[f"win_rate_{h}"] = _win_rate(sub[f"outcome_{h}"])
        for h in (20, 40):
            vals = sub[f"return_{h}"].dropna()
            row[f"avg_return_{h}"] = round(float(vals.mean()), 2) if len(vals) else None
        rows.append(row)
    return rows


def compare_1h_vs_4h(journal: pd.DataFrame) -> List[dict]:
    rows = []
    for tf in ("1h", "4h"):
        sub = journal[journal["timeframe"] == tf]
        if sub.empty:
            continue
        row = {"timeframe": tf, "n": len(sub)}
        for h in FORWARD_HORIZONS:
            row[f"win_rate_{h}"] = _win_rate(sub[f"outcome_{h}"])
            vals = sub[f"return_{h}"].dropna()
            row[f"avg_return_{h}"] = round(float(vals.mean()), 2) if len(vals) else None
        rows.append(row)
    return rows


def failure_cause_distribution(journal: pd.DataFrame) -> List[dict]:
    sub = journal[journal["failure_cause"].notna()]
    if sub.empty:
        return []
    counts = sub["failure_cause"].value_counts()
    total = int(counts.sum())
    return [
        {"failure_cause": cause, "count": int(counts.get(cause, 0)),
         "pct": round(int(counts.get(cause, 0)) / total * 100.0, 1)}
        for cause in FAILURE_CAUSES if counts.get(cause, 0) > 0
    ]


def active_candidate_tracking(journal: pd.DataFrame) -> List[dict]:
    """ACTIVE/RECENT 후보만 추출."""
    sub = journal[journal["freshness"].isin(["ACTIVE", "RECENT"])].copy()
    if sub.empty:
        return []
    sub = sub.sort_values(["symbol", "timeframe", "rule", "timestamp"])
    latest = sub.groupby(["symbol", "timeframe", "rule"], as_index=False).tail(1)
    rows = []
    for _, row in latest.iterrows():
        rows.append({
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "rule": row["rule"],
            "bars_since_signal": int(row.get("bars_elapsed", 0)),
            "status": row["status"],
            "pending_horizon": row.get("pending_horizon"),
            "watchlist_score": float(row.get("watchlist_score", 0)),
            "freshness": row["freshness"],
        })
    return sorted(rows, key=lambda r: r["watchlist_score"], reverse=True)


def tracking_priority(journal: pd.DataFrame, candidates: List[dict]) -> List[dict]:
    """현재 추적 우선순위."""
    priority = []
    for i, c in enumerate(candidates[:15], start=1):
        sub = journal[
            (journal["symbol"] == c["symbol"])
            & (journal["timeframe"] == c["timeframe"])
            & (journal["rule"] == c["rule"])
        ].sort_values("timestamp")
        last = sub.iloc[-1] if not sub.empty else None
        priority.append({
            "rank": i,
            "symbol": c["symbol"],
            "timeframe": c["timeframe"],
            "rule": c["rule"],
            "freshness": c["freshness"],
            "status": c["status"],
            "watchlist_score": c["watchlist_score"],
            "return_20": float(last["return_20"]) if last is not None and pd.notna(last.get("return_20")) else None,
        })
    return priority


def full_forward_journal_summary() -> dict:
    journal = build_forward_journal()
    candidates = active_candidate_tracking(journal)
    rule_sum = rule_cohort_summary(journal)
    sym_sum = symbol_summary(journal)
    tf_sum = timeframe_summary(journal)
    h1h4 = compare_1h_vs_4h(journal)
    failures = failure_cause_distribution(journal)
    priority = tracking_priority(journal, candidates)

    pending = journal[journal["status"] != "COMPLETED"] if not journal.empty else pd.DataFrame()
    completed = journal[journal["status"] == "COMPLETED"] if not journal.empty else pd.DataFrame()

    return {
        "journal": journal,
        "active_candidates": candidates,
        "rule_summary": rule_sum,
        "symbol_summary": sym_sum,
        "timeframe_summary": tf_sum,
        "compare_1h_4h": h1h4,
        "failure_causes": failures,
        "tracking_priority": priority,
        "pending_count": len(pending),
        "completed_count": len(completed),
        "active_recent_count": len(candidates),
    }
