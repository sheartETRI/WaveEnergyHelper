"""Wave Failure Trigger Validation — 조기 무효화 trigger 검증.

wave_live_forward_journal.csv + OHLCV만 소비. 엔진·신호 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_exit import (
    RULE_K_CROSS,
    RULE_K_TURN,
    RULE_NEW_LL,
    RULE_RE_OS,
    RULE_SL3,
    RULE_TIMEOUT20,
    _build_bar_flags,
    _hits_at_bar,
)
from analysis.wave_live_forward_journal import _feature_at
from analysis.wave_money_flow import add_money_flow_features
from analysis.wave_outcome import _find_bar_index
from analysis.wave_regime_analysis import _load_pipeline
from analysis.wave_structure_confirmation import find_swing_highs, find_swing_lows
from analysis.wave_survival_segmentation import enrich_journal
from analysis.wave_symbol_segmentation import load_forward_journal
from analysis.wave_volume_energy import _load_ohlcv, add_volume_features

SCAN_HORIZON = 20
EARLY_TRIGGER_BARS = 5
SL_PCT = 3.0

TRIGGER_TYPES = (
    "STRUCTURE_FAIL",
    "MONEY_FLOW_DROP",
    "ENERGY_DROP",
    "STOP_LOSS_3",
    "NEW_LL",
    "K_TURN_DOWN",
    "K_CROSS_DOWN",
    "RE_OVERSOLD",
    "TIMEOUT",
)

EXIT_HIT_MAP = {
    RULE_SL3: "STOP_LOSS_3",
    RULE_NEW_LL: "NEW_LL",
    RULE_K_TURN: "K_TURN_DOWN",
    RULE_K_CROSS: "K_CROSS_DOWN",
    RULE_RE_OS: "RE_OVERSOLD",
    RULE_TIMEOUT20: "TIMEOUT",
}

TRIGGER_COMBOS = (
    ("STRUCTURE_FAIL OR MONEY_FLOW_DROP", ("STRUCTURE_FAIL", "MONEY_FLOW_DROP")),
    ("STRUCTURE_FAIL OR STOP_LOSS_3", ("STRUCTURE_FAIL", "STOP_LOSS_3")),
    ("MONEY_FLOW_DROP OR ENERGY_DROP", ("MONEY_FLOW_DROP", "ENERGY_DROP")),
    (
        "STRUCTURE_FAIL OR MONEY_FLOW_DROP OR STOP_LOSS_3",
        ("STRUCTURE_FAIL", "MONEY_FLOW_DROP", "STOP_LOSS_3"),
    ),
)

CSV_EXPORT_COLS = (
    "section", "event_id", "rule", "symbol", "timeframe", "regime", "survival_label",
    "trigger_type", "trigger_bar", "bars_to_trigger", "trigger_price", "return_at_trigger",
    "first_trigger", "first_trigger_bar", "first_trigger_return",
    "n", "failed_n", "survived_n", "neutral_n", "failure_rate", "survival_rate",
    "avg_return_20", "avg_return_40", "avg_bars_to_trigger", "median_bars_to_trigger",
    "early_trigger_ratio", "precision", "recall", "f1", "false_exit_rate",
    "survived_trigger_n", "combo", "rank", "score",
    "freshness", "current_trigger_status", "trigger_risk_score", "highest_risk_trigger",
    "value",
)


def _pct_ret(close: pd.Series, entry_idx: int, pos: int) -> float:
    entry = float(close.iloc[entry_idx])
    if entry <= 0:
        return 0.0
    return (float(close.iloc[pos]) / entry - 1.0) * 100.0


def _record_trigger(
    triggers: Dict[str, Tuple[int, float, float]],
    name: str,
    bar: int,
    entry_idx: int,
    close: pd.Series,
) -> None:
    if name in triggers:
        return
    bars = bar - entry_idx
    ret = _pct_ret(close, entry_idx, bar)
    price = float(close.iloc[bar])
    triggers[name] = (bars, ret, price)


def scan_event_triggers(
    ev: pd.Series,
    ohlcv: pd.DataFrame,
    combined: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    swing_lows,
    swing_highs,
) -> Tuple[Dict[str, Tuple[int, float, float]], Optional[str], Optional[int], Optional[float]]:
    """+1~+20봉 trigger 스캔 → (triggers, first_trigger, first_bar, first_return)."""
    ts = pd.Timestamp(ev["timestamp"])
    entry_idx = _find_bar_index(ohlcv, ts)
    if entry_idx is None or entry_idx >= len(ohlcv) - 1:
        return {}, None, None, None

    entry_price = float(ohlcv["close"].iloc[entry_idx])
    entry_struct = int(ev.get("structure_score", 0) or 0)
    entry_mf = int(ev.get("money_flow_score", 0) or 0)
    entry_energy = int(ev.get("energy_score", 0) or 0)

    end = min(entry_idx + SCAN_HORIZON, len(ohlcv) - 1)
    triggers: Dict[str, Tuple[int, float, float]] = {}
    close = ohlcv["close"]
    low = ohlcv["low"]

    for bar in range(entry_idx + 1, end + 1):
        if float(low.iloc[bar]) <= entry_price * (1.0 - SL_PCT / 100.0):
            _record_trigger(triggers, "STOP_LOSS_3", bar, entry_idx, close)

        hits = _hits_at_bar(bar, entry_idx, entry_price, ohlcv, k, d, oversold_entry, ll_new)
        for hit in hits:
            mapped = EXIT_HIT_MAP.get(hit)
            if mapped:
                _record_trigger(triggers, mapped, bar, entry_idx, close)

        feats = _feature_at(combined, swing_lows, swing_highs, bar)
        if entry_struct >= 3 and feats.get("structure_score", 0) < 3:
            _record_trigger(triggers, "STRUCTURE_FAIL", bar, entry_idx, close)
        elif feats.get("structure_score", 0) < 3:
            _record_trigger(triggers, "STRUCTURE_FAIL", bar, entry_idx, close)

        if entry_mf >= 4 and feats.get("money_flow_score", 0) < 4:
            _record_trigger(triggers, "MONEY_FLOW_DROP", bar, entry_idx, close)
        elif feats.get("money_flow_score", 0) < 4:
            _record_trigger(triggers, "MONEY_FLOW_DROP", bar, entry_idx, close)

        if entry_energy >= 3 and feats.get("energy_score", 0) < 3:
            _record_trigger(triggers, "ENERGY_DROP", bar, entry_idx, close)
        elif feats.get("energy_score", 0) < 3:
            _record_trigger(triggers, "ENERGY_DROP", bar, entry_idx, close)

    first_name: Optional[str] = None
    first_bar: Optional[int] = None
    first_ret: Optional[float] = None
    if triggers:
        first_name = min(triggers.keys(), key=lambda t: triggers[t][0])
        first_bar, first_ret, _ = triggers[first_name]

    return triggers, first_name, first_bar, first_ret


def _prf(y_true: pd.Series, y_pred: pd.Series) -> dict:
    tp = int(((y_true) & (y_pred)).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None
    return {
        "precision": round(precision * 100, 2) if precision is not None else None,
        "recall": round(recall * 100, 2) if recall is not None else None,
        "f1": round(f1 * 100, 2) if f1 is not None else None,
    }


def build_event_scans(enriched: pd.DataFrame) -> pd.DataFrame:
    """Completed 이벤트 trigger 스캔."""
    completed = enriched[enriched["status"] == "COMPLETED"].copy()
    if completed.empty:
        return pd.DataFrame()

    cache: Dict[Tuple[str, str], dict] = {}
    rows: List[dict] = []
    trigger_rows: List[dict] = []

    for _, ev in completed.iterrows():
        sym = str(ev["symbol"])
        tf = str(ev["timeframe"])
        key = (sym, tf)
        if key not in cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            combined = add_money_flow_features(add_volume_features(bare))
            pipe = _load_pipeline(sym, tf)
            if pipe.empty:
                k = d = oversold = ll = pd.Series(dtype=float)
            else:
                k, d, oversold, ll = _build_bar_flags(pipe)
            cache[key] = {
                "ohlcv": bare,
                "combined": combined,
                "k": k, "d": d, "oversold": oversold, "ll": ll,
                "sw_lows": find_swing_lows(combined["low"]),
                "sw_highs": find_swing_highs(combined["high"]),
            }

        c = cache.get(key)
        if not c:
            continue

        triggers, first_t, first_bar, first_ret = scan_event_triggers(
            ev, c["ohlcv"], c["combined"],
            c["k"], c["d"], c["oversold"], c["ll"],
            c["sw_lows"], c["sw_highs"],
        )

        base = {
            "event_id": ev["event_id"],
            "symbol": sym,
            "timeframe": tf,
            "rule": ev["rule"],
            "regime": ev.get("regime", ""),
            "survival_label": ev["survival_label"],
            "first_trigger": first_t,
            "first_trigger_bar": first_bar,
            "first_trigger_return": first_ret,
            "return_20": ev.get("return_20"),
            "return_40": ev.get("return_40"),
        }
        rows.append(base)

        for tname, (bars, ret, price) in triggers.items():
            trigger_rows.append({
                **base,
                "trigger_type": tname,
                "trigger_bar": bars,
                "bars_to_trigger": bars,
                "trigger_price": round(price, 4),
                "return_at_trigger": round(ret, 4),
            })

    if not rows:
        return pd.DataFrame()
    event_df = pd.DataFrame(rows)
    event_df.attrs["trigger_detail"] = pd.DataFrame(trigger_rows)
    return event_df


def trigger_performance(event_df: pd.DataFrame) -> List[dict]:
    detail = event_df.attrs.get("trigger_detail", pd.DataFrame())
    if detail.empty:
        return []
    rows = []
    for tname in TRIGGER_TYPES:
        sub = detail[detail["trigger_type"] == tname]
        if sub.empty:
            continue
        ev_ids = set(sub["event_id"])
        ev_sub = event_df[event_df["event_id"].isin(ev_ids)]
        failed = ev_sub[ev_sub["survival_label"] == "FAILED_20"]
        survived = ev_sub[ev_sub["survival_label"] == "SURVIVED_20"]
        neutral = ev_sub[ev_sub["survival_label"] == "NEUTRAL_20"]
        n = len(ev_sub)
        rows.append({
            "section": "trigger_performance",
            "trigger_type": tname,
            "n": n,
            "failed_n": len(failed),
            "survived_n": len(survived),
            "neutral_n": len(neutral),
            "failure_rate": round(len(failed) / n * 100, 2) if n else None,
            "survival_rate": round(len(survived) / n * 100, 2) if n else None,
            "avg_return_20": round(float(ev_sub["return_20"].mean()), 4) if n else None,
            "avg_return_40": round(float(ev_sub["return_40"].mean()), 4) if n else None,
        })
    return rows


def trigger_timing(detail: pd.DataFrame) -> List[dict]:
    if detail.empty:
        return []
    rows = []
    for tname in TRIGGER_TYPES:
        sub = detail[detail["trigger_type"] == tname]
        if sub.empty:
            continue
        bars = sub["bars_to_trigger"].astype(float)
        rows.append({
            "section": "trigger_timing",
            "trigger_type": tname,
            "n": len(sub),
            "avg_bars_to_trigger": round(float(bars.mean()), 2),
            "median_bars_to_trigger": round(float(bars.median()), 2),
            "early_trigger_ratio": round(float((bars <= EARLY_TRIGGER_BARS).sum() / len(bars) * 100), 2),
        })
    return rows


def trigger_precision_recall(event_df: pd.DataFrame, detail: pd.DataFrame) -> List[dict]:
    if event_df.empty:
        return []
    labeled = event_df[event_df["survival_label"].isin(["FAILED_20", "SURVIVED_20", "NEUTRAL_20"])]
    y_failed = labeled["survival_label"] == "FAILED_20"
    rows = []
    for tname in TRIGGER_TYPES:
        triggered_ids = set(detail[detail["trigger_type"] == tname]["event_id"]) if not detail.empty else set()
        y_pred = labeled["event_id"].isin(triggered_ids)
        pr = _prf(y_failed, y_pred)
        survived = labeled[labeled["survival_label"] == "SURVIVED_20"]
        surv_trig = survived["event_id"].isin(triggered_ids)
        false_exit = round(float(surv_trig.sum() / len(survived) * 100), 2) if len(survived) else None
        rows.append({
            "section": "precision_recall",
            "trigger_type": tname,
            "n": int(y_pred.sum()),
            "survived_trigger_n": int(surv_trig.sum()),
            "false_exit_rate": false_exit,
            **pr,
        })
    return rows


def _group_trigger_stats(event_df: pd.DataFrame, detail: pd.DataFrame, col: str) -> List[dict]:
    rows = []
    for val in sorted(event_df[col].dropna().unique()):
        ev_sub = event_df[event_df[col] == val]
        ids = set(ev_sub["event_id"])
        dsub = detail[detail["event_id"].isin(ids)] if not detail.empty else pd.DataFrame()
        dist = dsub["trigger_type"].value_counts().to_dict() if not dsub.empty else {}
        top_trigger = max(dist, key=dist.get) if dist else None
        failed = ev_sub[ev_sub["survival_label"] == "FAILED_20"]
        survived = ev_sub[ev_sub["survival_label"] == "SURVIVED_20"]
        first_failed = failed["first_trigger"].value_counts().to_dict() if not failed.empty else {}
        rows.append({
            "section": f"{col}_trigger",
            col: val,
            "n": len(ev_sub),
            "failure_rate": round(len(failed) / len(ev_sub) * 100, 2) if len(ev_sub) else None,
            "top_trigger": top_trigger,
            "failed_first_trigger": str(first_failed) if first_failed else "",
            "false_exit_rate": round(
                survived["first_trigger"].notna().sum() / len(survived) * 100, 2,
            ) if len(survived) else None,
        })
    return rows


def combo_analysis(event_df: pd.DataFrame, detail: pd.DataFrame) -> List[dict]:
    if event_df.empty or detail.empty:
        return []
    labeled = event_df[event_df["survival_label"].isin(["FAILED_20", "SURVIVED_20", "NEUTRAL_20"])]
    y_failed = labeled["survival_label"] == "FAILED_20"
    rows = []
    for combo_name, members in TRIGGER_COMBOS:
        triggered = set()
        for eid in labeled["event_id"]:
            types = set(detail[detail["event_id"] == eid]["trigger_type"])
            if types & set(members):
                triggered.add(eid)
        y_pred = labeled["event_id"].isin(triggered)
        pr = _prf(y_failed, y_pred)
        sub_detail = detail[(detail["event_id"].isin(triggered)) & (detail["trigger_type"].isin(members))]
        avg_bars = float(sub_detail["bars_to_trigger"].mean()) if not sub_detail.empty else None
        survived = labeled[labeled["survival_label"] == "SURVIVED_20"]
        false_exit = round(
            survived["event_id"].isin(triggered).sum() / len(survived) * 100, 2,
        ) if len(survived) else None
        rows.append({
            "section": "combo",
            "combo": combo_name,
            "n": int(y_pred.sum()),
            "avg_bars_to_trigger": round(avg_bars, 2) if avg_bars is not None else None,
            "false_exit_rate": false_exit,
            **pr,
        })
    return rows


def best_triggers(pr_rows: List[dict], timing_rows: List[dict], top_n: int = 10) -> List[dict]:
    timing_map = {t["trigger_type"]: t for t in timing_rows}
    scored = []
    for r in pr_rows:
        tname = r.get("trigger_type")
        if not tname or r.get("n", 0) == 0:
            continue
        f1 = r.get("f1") or 0
        prec = r.get("precision") or 0
        rec = r.get("recall") or 0
        fer = r.get("false_exit_rate") or 100
        early = timing_map.get(tname, {}).get("early_trigger_ratio") or 0
        score = f1 * 0.4 + prec * 0.2 + rec * 0.2 - fer * 0.15 + early * 0.05
        scored.append({
            "section": "best_trigger",
            "rank": 0,
            "trigger_type": tname,
            "score": round(score, 2),
            "precision": r.get("precision"),
            "recall": r.get("recall"),
            "f1": r.get("f1"),
            "false_exit_rate": r.get("false_exit_rate"),
            "early_trigger_ratio": early,
            "avg_bars_to_trigger": timing_map.get(tname, {}).get("avg_bars_to_trigger"),
        })
    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)[:top_n]
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def active_candidate_risk_overlay(enriched: pd.DataFrame, event_df: pd.DataFrame) -> List[dict]:
    from analysis.wave_live_forward_journal import active_candidate_tracking

    cands = active_candidate_tracking(enriched)
    if not cands:
        return []

    cache: Dict[Tuple[str, str], dict] = {}
    rows = []

    for c in cands:
        sym = c["symbol"]
        tf = c["timeframe"]
        rule = c["rule"]
        key = (sym, tf)
        if key not in cache:
            bare = _load_ohlcv(sym, tf)
            if bare.empty:
                continue
            combined = add_money_flow_features(add_volume_features(bare))
            pipe = _load_pipeline(sym, tf)
            if pipe.empty:
                k = d = oversold = ll = pd.Series(dtype=float)
            else:
                k, d, oversold, ll = _build_bar_flags(pipe)
            cache[key] = {
                "ohlcv": bare,
                "combined": combined,
                "k": k, "d": d, "oversold": oversold, "ll": ll,
                "sw_lows": find_swing_lows(combined["low"]),
                "sw_highs": find_swing_highs(combined["high"]),
            }

        cell = cache.get(key)
        if not cell:
            continue

        sub = enriched[
            (enriched["symbol"] == sym)
            & (enriched["timeframe"] == tf)
            & (enriched["rule"] == rule)
        ].sort_values("timestamp")
        if sub.empty:
            continue
        ev_row = sub.iloc[-1]

        triggers, first_t, _, _ = scan_event_triggers(
            ev_row, cell["ohlcv"], cell["combined"],
            cell["k"], cell["d"], cell["oversold"], cell["ll"],
            cell["sw_lows"], cell["sw_highs"],
        )

        risk_weights = {
            "STOP_LOSS_3": 100, "STRUCTURE_FAIL": 80, "MONEY_FLOW_DROP": 70,
            "ENERGY_DROP": 50, "NEW_LL": 60, "K_CROSS_DOWN": 40,
            "K_TURN_DOWN": 35, "RE_OVERSOLD": 30, "TIMEOUT": 20,
        }
        if triggers:
            highest = min(triggers.keys(), key=lambda t: triggers[t][0])
            risk = risk_weights.get(highest, 25)
            status = f"TRIGGERED:{highest}"
        else:
            highest = None
            risk = 0
            status = "CLEAR"

        rows.append({
            "section": "active_candidate",
            "symbol": sym,
            "timeframe": tf,
            "rule": c["rule"],
            "freshness": c.get("freshness"),
            "watchlist_score": c.get("watchlist_score"),
            "current_trigger_status": status,
            "highest_risk_trigger": highest,
            "trigger_risk_score": risk,
            "bars_since_signal": c.get("bars_since_signal", 0),
        })

    ranked = sorted(rows, key=lambda r: r["trigger_risk_score"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def observation_priority(active: List[dict]) -> List[dict]:
    return [
        {
            "section": "observation_priority",
            "rank": r.get("rank"),
            "symbol": r["symbol"],
            "timeframe": r["timeframe"],
            "rule": r["rule"],
            "trigger_risk_score": r.get("trigger_risk_score"),
            "highest_risk_trigger": r.get("highest_risk_trigger"),
            "current_trigger_status": r.get("current_trigger_status"),
        }
        for r in active[:12]
    ]


def build_export(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CSV_EXPORT_COLS))
    df = pd.DataFrame(rows)
    for col in CSV_EXPORT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[[c for c in CSV_EXPORT_COLS if c in df.columns]]


def full_failure_trigger_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)
    event_df = build_event_scans(enriched)
    detail = event_df.attrs.get("trigger_detail", pd.DataFrame()) if not event_df.empty else pd.DataFrame()

    perf = trigger_performance(event_df)
    timing = trigger_timing(detail)
    pr = trigger_precision_recall(event_df, detail)
    rule_grp = _group_trigger_stats(event_df, detail, "rule")
    sym_grp = _group_trigger_stats(event_df, detail, "symbol")
    reg_grp = _group_trigger_stats(event_df, detail, "regime")
    combos = combo_analysis(event_df, detail)
    best = best_triggers(pr, timing, 10)
    active = active_candidate_risk_overlay(enriched, event_df)
    priority = observation_priority(active)

    trigger_detail_rows = []
    if not detail.empty:
        for _, row in detail.iterrows():
            trigger_detail_rows.append({"section": "event_trigger", **row.to_dict()})

    first_trigger_rows = []
    if not event_df.empty:
        for _, row in event_df.iterrows():
            first_trigger_rows.append({"section": "event_first_trigger", **row.to_dict()})

    all_rows = (
        trigger_detail_rows + first_trigger_rows + perf + timing + pr
        + rule_grp + sym_grp + reg_grp + combos + best + active + priority
    )

    failed_first = event_df[event_df["survival_label"] == "FAILED_20"]["first_trigger"].value_counts() if not event_df.empty else pd.Series()

    return {
        "event_df": event_df,
        "detail": detail,
        "trigger_performance": perf,
        "trigger_timing": timing,
        "precision_recall": pr,
        "rule_trigger": rule_grp,
        "symbol_trigger": sym_grp,
        "regime_trigger": reg_grp,
        "combos": combos,
        "best_triggers": best,
        "active_candidates": active,
        "observation_priority": priority,
        "failed_first_trigger_dist": failed_first.to_dict() if not failed_first.empty else {},
        "export_df": build_export(all_rows),
    }
