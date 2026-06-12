"""Wave Exit Policy Simulation — Exit 정책별 성과 시뮬레이션 (관측 전용).

wave_live_forward_journal.csv + OHLCV만 소비. 엔진·기존 산출물 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from analysis.wave_exit import (
    RULE_K_CROSS,
    RULE_K_TURN,
    RULE_RE_OS,
    RULE_SL3,
    RULE_TIMEOUT20,
    _build_bar_flags,
    _hits_at_bar,
)
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_live_forward_journal import _feature_at, active_candidate_tracking
from analysis.wave_money_flow import add_money_flow_features
from analysis.wave_outcome import _find_bar_index, _mfe, _mae
from analysis.wave_regime_analysis import _load_pipeline
from analysis.wave_structure_confirmation import find_swing_highs, find_swing_lows
from analysis.wave_survival_segmentation import enrich_journal, survival_label
from analysis.wave_symbol_segmentation import load_forward_journal
from analysis.wave_volume_energy import _load_ohlcv, add_volume_features

HORIZON = 20
EARLY_EXIT_BARS = 5
SL_PCT = 3.0

EXIT_POLICIES = (
    "POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E",
    "POLICY_F", "POLICY_G", "POLICY_H", "POLICY_I", "NO_EXIT",
)

EXIT_HIT_MAP = {
    RULE_SL3: "STOP_LOSS_3",
    RULE_K_TURN: "K_TURN_DOWN",
    RULE_K_CROSS: "K_CROSS_DOWN",
    RULE_RE_OS: "RE_OVERSOLD",
    RULE_TIMEOUT20: "TIMEOUT",
}

CSV_EXPORT_COLS = (
    "section", "event_id", "policy", "rule", "symbol", "timeframe", "regime",
    "survival_label", "exit_bar", "exit_reason", "exit_return", "baseline_return",
    "mfe", "mae", "max_mfe", "max_mae", "avg_mfe", "avg_mae",
    "n", "avg_return", "median_return", "win_rate", "loss_rate",
    "profit_factor", "expectancy", "false_exit_rate", "false_exit_n",
    "saved_failure_rate", "saved_failure_n", "avg_exit_bar", "median_exit_bar",
    "early_exit_ratio", "rank", "score", "freshness",
    "risk_score", "recommended_policy", "expected_protection",
    "baseline_expectancy", "policy_expectancy", "expectancy_delta",
    "drawdown_delta", "survival_delta", "value",
)


def _pct(close: pd.Series, entry_idx: int, pos: int, entry: float) -> float:
    if entry <= 0:
        return 0.0
    return (float(close.iloc[pos]) / entry - 1.0) * 100.0


def _exit_price(trigger: str, entry: float, ohlcv: pd.DataFrame, bar: int) -> float:
    if trigger == "STOP_LOSS_3":
        return entry * (1.0 - SL_PCT / 100.0)
    return float(ohlcv["close"].iloc[bar])


def _triggers_at_bar(
    bar: int,
    entry_idx: int,
    entry: float,
    entry_struct: int,
    entry_mf: int,
    entry_energy: int,
    ohlcv: pd.DataFrame,
    combined: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    swing_lows,
    swing_highs,
) -> Set[str]:
    triggers: Set[str] = set()
    low = ohlcv["low"]
    if float(low.iloc[bar]) <= entry * (1.0 - SL_PCT / 100.0):
        triggers.add("STOP_LOSS_3")

    hits = _hits_at_bar(bar, entry_idx, entry, ohlcv, k, d, oversold_entry, ll_new)
    for hit in hits:
        mapped = EXIT_HIT_MAP.get(hit)
        if mapped:
            triggers.add(mapped)

    feats = _feature_at(combined, swing_lows, swing_highs, bar)
    if feats.get("structure_score", 0) < 3 or (entry_struct >= 3 and feats.get("structure_score", 0) < 3):
        triggers.add("STRUCTURE_FAIL")
    if feats.get("money_flow_score", 0) < 4 or (entry_mf >= 4 and feats.get("money_flow_score", 0) < 4):
        triggers.add("MONEY_FLOW_DROP")
    if feats.get("energy_score", 0) < 3 or (entry_energy >= 3 and feats.get("energy_score", 0) < 3):
        triggers.add("ENERGY_DROP")

    held = bar - entry_idx
    if held == HORIZON:
        triggers.add("TIMEOUT")

    return triggers


def _policy_exit(
    policy: str,
    triggers: Set[str],
    struct_streak: int,
) -> Tuple[Optional[str], int]:
    """(exit_reason, new_struct_streak)."""
    if policy == "NO_EXIT":
        return None, struct_streak

    if policy == "POLICY_A":
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        return None, 0

    if policy == "POLICY_B":
        if "STRUCTURE_FAIL" in triggers:
            return "STRUCTURE_FAIL", 0
        return None, 0

    if policy == "POLICY_C":
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        if "STRUCTURE_FAIL" in triggers:
            return "STRUCTURE_FAIL", 0
        return None, 0

    if policy == "POLICY_D":
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        if "MONEY_FLOW_DROP" in triggers:
            return "MONEY_FLOW_DROP", 0
        return None, 0

    if policy == "POLICY_E":
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        if "STRUCTURE_FAIL" in triggers:
            return "STRUCTURE_FAIL", 0
        if "MONEY_FLOW_DROP" in triggers:
            return "MONEY_FLOW_DROP", 0
        return None, 0

    if policy == "POLICY_F":
        streak = struct_streak + 1 if "STRUCTURE_FAIL" in triggers else 0
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        if streak >= 2:
            return "STRUCTURE_FAIL_x2", streak
        return None, streak

    if policy == "POLICY_G":
        if "STOP_LOSS_3" in triggers:
            return "STOP_LOSS_3", 0
        if "STRUCTURE_FAIL" in triggers and "MONEY_FLOW_DROP" in triggers:
            return "STRUCTURE_FAIL+MF_DROP", 0
        return None, 0

    if policy == "POLICY_H":
        if "RE_OVERSOLD" in triggers:
            return "RE_OVERSOLD", 0
        return None, 0

    if policy == "POLICY_I":
        if "TIMEOUT" in triggers:
            return "TIMEOUT", 0
        return None, 0

    return None, struct_streak


def simulate_event_policy(
    ev: pd.Series,
    policy: str,
    ohlcv: pd.DataFrame,
    combined: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    swing_lows,
    swing_highs,
) -> Optional[dict]:
    ts = pd.Timestamp(ev["timestamp"])
    entry_idx = _find_bar_index(ohlcv, ts)
    if entry_idx is None:
        return None

    entry = float(ohlcv["close"].iloc[entry_idx])
    end = min(entry_idx + HORIZON, len(ohlcv) - 1)
    if end <= entry_idx:
        return None

    entry_struct = int(ev.get("structure_score", 0) or 0)
    entry_mf = int(ev.get("money_flow_score", 0) or 0)
    entry_energy = int(ev.get("energy_score", 0) or 0)
    close = ohlcv["close"]

    struct_streak = 0
    exit_bar = end
    exit_reason = "HOLD_20" if policy == "NO_EXIT" else "TIMEOUT_HOLD"

    for bar in range(entry_idx + 1, end + 1):
        triggers = _triggers_at_bar(
            bar, entry_idx, entry, entry_struct, entry_mf, entry_energy,
            ohlcv, combined, k, d, oversold_entry, ll_new, swing_lows, swing_highs,
        )
        reason, struct_streak = _policy_exit(policy, triggers, struct_streak)
        if reason and policy != "NO_EXIT":
            exit_bar = bar
            exit_reason = reason
            break

    held = exit_bar - entry_idx
    exit_px = _exit_price(
        exit_reason if exit_reason.startswith("STOP_LOSS") else "CLOSE",
        entry, ohlcv, exit_bar,
    )
    if not exit_reason.startswith("STOP_LOSS"):
        exit_px = float(ohlcv["close"].iloc[exit_bar])

    exit_return = (exit_px / entry - 1.0) * 100.0
    baseline_return = float(ev.get("return_20")) if pd.notna(ev.get("return_20")) else _pct(close, entry_idx, end, entry)

    return {
        "event_id": ev["event_id"],
        "policy": policy,
        "rule": ev["rule"],
        "symbol": ev["symbol"],
        "timeframe": ev["timeframe"],
        "regime": ev.get("regime", ""),
        "survival_label": ev.get("survival_label", ""),
        "exit_bar": held,
        "exit_reason": exit_reason,
        "exit_return": round(exit_return, 4),
        "baseline_return": round(baseline_return, 4),
        "mfe": round(_mfe(ohlcv["high"], entry_idx, held, entry) * 100.0, 4),
        "mae": round(_mae(ohlcv["low"], entry_idx, held, entry) * 100.0, 4),
    }


def build_event_simulations(enriched: pd.DataFrame) -> pd.DataFrame:
    completed = enriched[enriched["status"] == "COMPLETED"].copy()
    if completed.empty:
        return pd.DataFrame()

    cache: Dict[Tuple[str, str], dict] = {}
    rows: List[dict] = []

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
                "ohlcv": bare, "combined": combined,
                "k": k, "d": d, "oversold": oversold, "ll": ll,
                "sw_lows": find_swing_lows(combined["low"]),
                "sw_highs": find_swing_highs(combined["high"]),
            }

        cell = cache.get(key)
        if not cell:
            continue

        for policy in EXIT_POLICIES:
            sim = simulate_event_policy(
                ev, policy, cell["ohlcv"], cell["combined"],
                cell["k"], cell["d"], cell["oversold"], cell["ll"],
                cell["sw_lows"], cell["sw_highs"],
            )
            if sim:
                rows.append(sim)

    return pd.DataFrame(rows)


def _summary_metrics(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0}
    rets = sub["exit_return"].astype(float)
    m = compute_expectancy_metrics(rets)
    med = float(rets.median())
    return {
        "n": len(sub),
        "avg_return": round(float(rets.mean()), 4),
        "median_return": round(med, 4),
        "win_rate": round(m.get("win_rate", 0), 2),
        "loss_rate": round(100.0 - m.get("win_rate", 0), 2),
        "profit_factor": round(m["profit_factor"], 4) if m.get("profit_factor") not in (float("inf"),) else 999.0,
        "expectancy": round(m.get("expectancy", 0), 4),
    }


def policy_summary(sim_df: pd.DataFrame) -> List[dict]:
    rows = []
    for policy in EXIT_POLICIES:
        sub = sim_df[sim_df["policy"] == policy]
        if sub.empty:
            continue
        m = _summary_metrics(sub)
        rows.append({"section": "policy_summary", "policy": policy, **m})
    return rows


def drawdown_analysis(sim_df: pd.DataFrame) -> List[dict]:
    rows = []
    for policy in EXIT_POLICIES:
        sub = sim_df[sim_df["policy"] == policy]
        if sub.empty:
            continue
        mae = sub["mae"].astype(float)
        mfe = sub["mfe"].astype(float)
        rows.append({
            "section": "drawdown",
            "policy": policy,
            "n": len(sub),
            "avg_mae": round(float(mae.mean()), 4),
            "max_mae": round(float(mae.max()), 4),
            "avg_mfe": round(float(mfe.mean()), 4),
            "max_mfe": round(float(mfe.max()), 4),
        })
    return rows


def false_exit_analysis(sim_df: pd.DataFrame) -> List[dict]:
    rows = []
    for policy in EXIT_POLICIES:
        sub = sim_df[sim_df["policy"] == policy]
        survived = sub[sub["survival_label"] == "SURVIVED_20"]
        if survived.empty:
            continue
        early = survived[survived["exit_bar"] < HORIZON]
        n = len(survived)
        rows.append({
            "section": "false_exit",
            "policy": policy,
            "n": n,
            "false_exit_n": len(early),
            "false_exit_rate": round(len(early) / n * 100, 2),
        })
    return rows


def saved_failure_analysis(sim_df: pd.DataFrame) -> List[dict]:
    rows = []
    for policy in EXIT_POLICIES:
        sub = sim_df[sim_df["policy"] == policy]
        failed = sub[sub["survival_label"] == "FAILED_20"]
        if failed.empty:
            continue
        saved = failed[failed["exit_return"] > failed["baseline_return"]]
        n = len(failed)
        rows.append({
            "section": "saved_failure",
            "policy": policy,
            "n": n,
            "saved_failure_n": len(saved),
            "saved_failure_rate": round(len(saved) / n * 100, 2),
        })
    return rows


def exit_timing(sim_df: pd.DataFrame) -> List[dict]:
    rows = []
    for policy in EXIT_POLICIES:
        sub = sim_df[sim_df["policy"] == policy]
        if sub.empty:
            continue
        bars = sub["exit_bar"].astype(float)
        rows.append({
            "section": "exit_timing",
            "policy": policy,
            "n": len(sub),
            "avg_exit_bar": round(float(bars.mean()), 2),
            "median_exit_bar": round(float(bars.median()), 2),
            "early_exit_ratio": round(float((bars <= EARLY_EXIT_BARS).sum() / len(bars) * 100), 2),
        })
    return rows


def _group_exit_effect(sim_df: pd.DataFrame, col: str) -> List[dict]:
    rows = []
    for val in sorted(sim_df[col].dropna().unique()):
        for policy in EXIT_POLICIES:
            sub = sim_df[(sim_df[col] == val) & (sim_df["policy"] == policy)]
            if sub.empty:
                continue
            m = _summary_metrics(sub)
            survived = sub[sub["survival_label"] == "SURVIVED_20"]
            failed = sub[sub["survival_label"] == "FAILED_20"]
            fe = survived[survived["exit_bar"] < HORIZON] if not survived.empty else pd.DataFrame()
            sf = failed[failed["exit_return"] > failed["baseline_return"]] if not failed.empty else pd.DataFrame()
            rows.append({
                "section": f"{col}_exit",
                col: val,
                "policy": policy,
                **m,
                "false_exit_rate": round(len(fe) / len(survived) * 100, 2) if len(survived) else None,
                "saved_failure_rate": round(len(sf) / len(failed) * 100, 2) if len(failed) else None,
            })
    return rows


def _policy_score(row: dict, baseline_exp: float) -> float:
    exp = row.get("expectancy") or 0
    pf = row.get("profit_factor") or 0
    if pf == 999.0:
        pf = 5.0
    sf = row.get("saved_failure_rate") or 0
    fe = row.get("false_exit_rate") or 100
    delta = exp - baseline_exp
    return exp * 0.3 + min(pf, 5) * 0.2 + sf * 0.25 - fe * 0.15 + delta * 0.1


def champion_policies(
    summary: List[dict],
    false_exits: List[dict],
    saved: List[dict],
    top_n: int = 10,
) -> Tuple[List[dict], List[dict]]:
    fe_map = {r["policy"]: r for r in false_exits}
    sf_map = {r["policy"]: r for r in saved}
    baseline_exp = next((s.get("expectancy", 0) for s in summary if s.get("policy") == "NO_EXIT"), 0)

    scored = []
    for s in summary:
        pol = s["policy"]
        if pol == "NO_EXIT":
            continue
        row = {
            **s,
            "false_exit_rate": fe_map.get(pol, {}).get("false_exit_rate"),
            "saved_failure_rate": sf_map.get(pol, {}).get("saved_failure_rate"),
        }
        row["score"] = round(_policy_score(row, baseline_exp), 2)
        scored.append(row)

    ranked = sorted(scored, key=lambda x: x["score"], reverse=True)
    champions = []
    for i, r in enumerate(ranked[:top_n], start=1):
        champions.append({"section": "champion_policy", "rank": i, **r})

    worst = []
    for i, r in enumerate(sorted(scored, key=lambda x: x["score"])[:top_n], start=1):
        worst.append({"section": "worst_policy", "rank": i, **r})

    return champions, worst


def policy_contribution(summary: List[dict], drawdown: List[dict], false_exits: List[dict]) -> List[dict]:
    baseline = next((s for s in summary if s.get("policy") == "NO_EXIT"), None)
    dd_base = next((d for d in drawdown if d.get("policy") == "NO_EXIT"), None)
    fe_base = next((f for f in false_exits if f.get("policy") == "NO_EXIT"), None)
    if not baseline:
        return []

    b_exp = baseline.get("expectancy", 0)
    b_mae = dd_base.get("avg_mae", 0) if dd_base else 0
    b_surv = 100.0 - (fe_base.get("false_exit_rate", 0) if fe_base else 0)

    rows = []
    for s in summary:
        pol = s["policy"]
        dd = next((d for d in drawdown if d.get("policy") == pol), {})
        fe = next((f for f in false_exits if f.get("policy") == pol), {})
        p_exp = s.get("expectancy", 0)
        p_mae = dd.get("avg_mae", 0)
        p_surv = 100.0 - (fe.get("false_exit_rate", 0) or 0)
        rows.append({
            "section": "contribution",
            "policy": pol,
            "baseline_expectancy": round(b_exp, 4),
            "policy_expectancy": round(p_exp, 4),
            "expectancy_delta": round(p_exp - b_exp, 4),
            "drawdown_delta": round(p_mae - b_mae, 4),
            "survival_delta": round(p_surv - b_surv, 4),
        })
    return rows


def active_candidate_overlay(
    enriched: pd.DataFrame,
    sim_df: pd.DataFrame,
    champions: List[dict],
) -> List[dict]:
    cands = active_candidate_tracking(enriched)
    if not cands or sim_df.empty:
        return []

    rule_best: Dict[str, str] = {}
    for rule in ("RULE_A", "RULE_B", "RULE_C"):
        sub = sim_df[sim_df["rule"] == rule]
        if sub.empty:
            continue
        grp = sub.groupby("policy")["exit_return"].mean()
        if not grp.empty:
            rule_best[rule] = str(grp.idxmax())

    global_best = champions[0]["policy"] if champions else "POLICY_C"

    rows = []
    for c in cands:
        rule = c["rule"]
        rec = rule_best.get(rule, global_best)
        sub = sim_df[(sim_df["rule"] == rule) & (sim_df["policy"] == rec)]
        sf_sub = sub[sub["survival_label"] == "FAILED_20"]
        saved_rate = 0.0
        if not sf_sub.empty:
            saved = sf_sub[sf_sub["exit_return"] > sf_sub["baseline_return"]]
            saved_rate = len(saved) / len(sf_sub) * 100

        champ = next((x for x in champions if x.get("policy") == rec), {})
        rows.append({
            "section": "active_candidate",
            "event_id": f"{c['symbol']}_{c['timeframe']}_{rule}",
            "symbol": c["symbol"],
            "timeframe": c["timeframe"],
            "rule": rule,
            "freshness": c.get("freshness"),
            "risk_score": c.get("watchlist_score"),
            "recommended_policy": rec,
            "expected_protection": round(saved_rate, 2),
            "score": champ.get("score"),
        })

    ranked = sorted(rows, key=lambda r: (r.get("risk_score") or 0), reverse=True)
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
            "recommended_policy": r.get("recommended_policy"),
            "expected_protection": r.get("expected_protection"),
            "risk_score": r.get("risk_score"),
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


def full_exit_policy_summary() -> dict:
    journal = load_forward_journal()
    enriched = enrich_journal(journal)
    sim_df = build_event_simulations(enriched)

    event_rows = [{"section": "event_simulation", **r} for r in sim_df.to_dict("records")] if not sim_df.empty else []

    summary = policy_summary(sim_df)
    drawdown = drawdown_analysis(sim_df)
    false_ex = false_exit_analysis(sim_df)
    saved = saved_failure_analysis(sim_df)
    timing = exit_timing(sim_df)
    rule_eff = _group_exit_effect(sim_df, "rule")
    sym_eff = _group_exit_effect(sim_df, "symbol")
    reg_eff = _group_exit_effect(sim_df, "regime")
    champions, worst = champion_policies(summary, false_ex, saved, 10)
    contrib = policy_contribution(summary, drawdown, false_ex)
    active = active_candidate_overlay(enriched, sim_df, champions)
    priority = observation_priority(active)

    all_rows = (
        event_rows + summary + drawdown + false_ex + saved + timing
        + rule_eff + sym_eff + reg_eff + champions + worst + contrib + active + priority
    )

    return {
        "sim_df": sim_df,
        "policy_summary": summary,
        "drawdown": drawdown,
        "false_exit": false_ex,
        "saved_failure": saved,
        "exit_timing": timing,
        "rule_exit": rule_eff,
        "symbol_exit": sym_eff,
        "regime_exit": reg_eff,
        "champion_policies": champions,
        "worst_policies": worst,
        "contribution": contrib,
        "active_candidates": active,
        "observation_priority": priority,
        "export_df": build_export(all_rows),
    }
