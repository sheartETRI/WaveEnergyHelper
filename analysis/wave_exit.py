"""Wave Exit — INITIAL 경로별 청산 규칙 사후 검증.

입력: lifecycle CSV + OHLCV + stoch K/D (기존 산출물 불변).
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

from analysis.wave_confirmation import extract_bar_flags
from analysis.wave_outcome import _find_bar_index, _mfe, _mae
from analysis.wave_survival import (
    INITIAL_CROSS,
    INITIAL_SLOPE,
    INITIAL_TB,
    SURVIVAL_INITIAL_TYPES,
    lifecycle_csv_path,
)
from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]

RULE_TP3 = "TAKE_PROFIT_3"
RULE_TP5 = "TAKE_PROFIT_5"
RULE_TP8 = "TAKE_PROFIT_8"
RULE_SL3 = "STOP_LOSS_3"
RULE_SL5 = "STOP_LOSS_5"
RULE_TIMEOUT20 = "TIMEOUT_20"
RULE_TIMEOUT40 = "TIMEOUT_40"
RULE_K_TURN = "MAJOR_K_TURN_DOWN"
RULE_K_CROSS = "MAJOR_K_CROSS_DOWN"
RULE_RE_OS = "RE_OVERSOLD_EXIT"
RULE_NEW_LL = "NEW_LL_EXIT"

ALL_RULES = (
    RULE_TP3, RULE_TP5, RULE_TP8,
    RULE_SL3, RULE_SL5,
    RULE_TIMEOUT20, RULE_TIMEOUT40,
    RULE_K_TURN, RULE_K_CROSS,
    RULE_RE_OS, RULE_NEW_LL,
)

POLICY_A = "TP3_SL3_TIMEOUT20"
POLICY_B = "TP5_SL3_TIMEOUT40"
POLICY_C = "TP5_KTURN_TIMEOUT40"
POLICY_D = "K_CROSS_DOWN_TIMEOUT40"
POLICY_E = "WAVE_INVALIDATION_EXIT"

ALL_POLICIES = (POLICY_A, POLICY_B, POLICY_C, POLICY_D, POLICY_E)

POLICY_RULES: Dict[str, Tuple[str, ...]] = {
    POLICY_A: (RULE_TP3, RULE_SL3, RULE_TIMEOUT20),
    POLICY_B: (RULE_TP5, RULE_SL3, RULE_TIMEOUT40),
    POLICY_C: (RULE_TP5, RULE_K_TURN, RULE_TIMEOUT40),
    POLICY_D: (RULE_K_CROSS, RULE_TIMEOUT40),
    POLICY_E: (RULE_NEW_LL, RULE_RE_OS, RULE_TIMEOUT40),
}

_TP_EXIT_PRICE = {
    RULE_TP3: 1.03,
    RULE_TP5: 1.05,
    RULE_TP8: 1.08,
}
_SL_EXIT_PRICE = {
    RULE_SL3: 0.97,
    RULE_SL5: 0.95,
}


def _k_d_cols() -> tuple[str, str]:
    return f"stoch_k_{_LAYER_LARGE}", f"stoch_d_{_LAYER_LARGE}"


def _cross_down_at(k: pd.Series, d: pd.Series, idx: int) -> bool:
    if idx < 1:
        return False
    kv_prev, dv_prev = k.iloc[idx - 1], d.iloc[idx - 1]
    kv, dv = k.iloc[idx], d.iloc[idx]
    if pd.isna(kv_prev) or pd.isna(dv_prev) or pd.isna(kv) or pd.isna(dv):
        return False
    return float(kv_prev) >= float(dv_prev) and float(kv) < float(dv)


def _k_turn_down_at(k: pd.Series, idx: int) -> bool:
    if idx < 2:
        return False
    k0, k1, k2 = k.iloc[idx - 2], k.iloc[idx - 1], k.iloc[idx]
    if pd.isna(k0) or pd.isna(k1) or pd.isna(k2):
        return False
    return float(k2) < float(k1) and float(k1) >= float(k0)


def _build_bar_flags(pipeline_df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """봉별 oversold_entry, ll_new, major_k, major_d 시계열."""
    n = len(pipeline_df)
    k_col, d_col = _k_d_cols()
    oversold_entries = []
    ll_news = []
    prev_os = False
    for i in range(n):
        flags = extract_bar_flags(pipeline_df.iloc[: i + 1], prev_os)
        prev_os = flags["major_oversold"]
        oversold_entries.append(flags["oversold_entry"])
        ll_news.append(flags["ll_new"])
    k_s = pipeline_df[k_col] if k_col in pipeline_df.columns else pd.Series([float("nan")] * n)
    d_s = pipeline_df[d_col] if d_col in pipeline_df.columns else pd.Series([float("nan")] * n)
    return k_s, d_s, pd.Series(oversold_entries), pd.Series(ll_news)


def _hits_at_bar(
    bar_idx: int,
    entry_idx: int,
    entry: float,
    ohlcv: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
) -> List[str]:
    hits: List[str] = []
    if bar_idx <= entry_idx:
        return hits

    high = float(ohlcv["high"].iloc[bar_idx])
    low = float(ohlcv["low"].iloc[bar_idx])

    if high >= entry * 1.03:
        hits.append(RULE_TP3)
    if high >= entry * 1.05:
        hits.append(RULE_TP5)
    if high >= entry * 1.08:
        hits.append(RULE_TP8)
    if low <= entry * 0.97:
        hits.append(RULE_SL3)
    if low <= entry * 0.95:
        hits.append(RULE_SL5)

    held = bar_idx - entry_idx
    if held == 20:
        hits.append(RULE_TIMEOUT20)
    if held == 40:
        hits.append(RULE_TIMEOUT40)

    if _k_turn_down_at(k, bar_idx):
        hits.append(RULE_K_TURN)
    if _cross_down_at(k, d, bar_idx):
        hits.append(RULE_K_CROSS)
    if bool(oversold_entry.iloc[bar_idx]):
        hits.append(RULE_RE_OS)
    if bool(ll_new.iloc[bar_idx]):
        hits.append(RULE_NEW_LL)

    return hits


def _exit_price_for_rule(rule: str, entry: float, ohlcv: pd.DataFrame, bar_idx: int) -> float:
    if rule in _TP_EXIT_PRICE:
        return entry * _TP_EXIT_PRICE[rule]
    if rule in _SL_EXIT_PRICE:
        return entry * _SL_EXIT_PRICE[rule]
    return float(ohlcv["close"].iloc[bar_idx])


def _resolve_policy_hit(hits: List[str], policy_rules: Tuple[str, ...]) -> Optional[str]:
    tp_hits = [r for r in hits if r.startswith("TAKE_PROFIT")]
    sl_hits = [r for r in hits if r.startswith("STOP_LOSS")]
    if tp_hits and sl_hits:
        for rule in policy_rules:
            if rule in sl_hits:
                return rule
    for rule in policy_rules:
        if rule in hits:
            return rule
    return None


def evaluate_policy(
    entry_idx: int,
    entry: float,
    ohlcv: pd.DataFrame,
    k: pd.Series,
    d: pd.Series,
    oversold_entry: pd.Series,
    ll_new: pd.Series,
    policy_rules: Tuple[str, ...],
    max_bar: Optional[int] = None,
) -> Optional[dict]:
    """정책별 청산 시뮬레이션."""
    end = len(ohlcv) - 1
    if max_bar is not None:
        end = min(end, entry_idx + max_bar)

    for bar_idx in range(entry_idx + 1, end + 1):
        hits = _hits_at_bar(
            bar_idx, entry_idx, entry, ohlcv, k, d, oversold_entry, ll_new,
        )
        chosen = _resolve_policy_hit(hits, policy_rules)
        if chosen:
            exit_px = _exit_price_for_rule(chosen, entry, ohlcv, bar_idx)
            held = bar_idx - entry_idx
            return {
                "exit_bar": bar_idx,
                "exit_reason": chosen,
                "exit_price": exit_px,
                "bars_held": held,
                "return_pct": (exit_px - entry) / entry * 100.0,
                "mfe_before_exit": _mfe(ohlcv["high"], entry_idx, held, entry),
                "mae_before_exit": _mae(ohlcv["low"], entry_idx, held, entry),
            }

    if policy_rules:
        timeout_rule = policy_rules[-1]
        if timeout_rule in (RULE_TIMEOUT20, RULE_TIMEOUT40):
            t = 20 if timeout_rule == RULE_TIMEOUT20 else 40
            tbar = entry_idx + t
            if tbar < len(ohlcv):
                exit_px = float(ohlcv["close"].iloc[tbar])
                return {
                    "exit_bar": tbar,
                    "exit_reason": timeout_rule,
                    "exit_price": exit_px,
                    "bars_held": t,
                    "return_pct": (exit_px - entry) / entry * 100.0,
                    "mfe_before_exit": _mfe(ohlcv["high"], entry_idx, t, entry),
                    "mae_before_exit": _mae(ohlcv["low"], entry_idx, t, entry),
                }
    return None


def build_exit_results(
    lifecycle: pd.DataFrame,
    ohlcv: pd.DataFrame,
    pipeline_df: pd.DataFrame,
) -> pd.DataFrame:
    k, d, os_entry, ll_new = _build_bar_flags(pipeline_df)
    rows: List[dict] = []

    for _, row in lifecycle.iterrows():
        initial = str(row["initial_outcome"])
        if initial not in SURVIVAL_INITIAL_TYPES:
            continue

        db_ts = pd.Timestamp(row["timestamp"])
        db_idx = _find_bar_index(ohlcv, db_ts)
        if db_idx is None:
            continue
        delay = row.get("bars_until_initial")
        if pd.isna(delay):
            continue
        entry_idx = db_idx + int(delay)
        if entry_idx >= len(ohlcv):
            continue
        entry = float(ohlcv["close"].iloc[entry_idx])
        if pd.isna(entry) or entry == 0:
            continue

        for policy in ALL_POLICIES:
            rules = POLICY_RULES[policy]
            max_bar = 40 if RULE_TIMEOUT40 in rules else 20
            result = evaluate_policy(
                entry_idx, entry, ohlcv, k, d, os_entry, ll_new, rules, max_bar=max_bar,
            )
            if result is None:
                continue
            rows.append({
                "timestamp": db_ts,
                "initial_type": initial,
                "policy": policy,
                "entry_price": entry,
                **result,
            })

    return pd.DataFrame(rows)


def load_exit_results(
    symbol: str,
    interval: str,
    ohlcv: pd.DataFrame,
    pipeline_df: pd.DataFrame,
) -> pd.DataFrame:
    path = lifecycle_csv_path(symbol, interval)
    if not os.path.isfile(path):
        return pd.DataFrame()
    lifecycle = pd.read_csv(path, parse_dates=["timestamp"])
    return build_exit_results(lifecycle, ohlcv, pipeline_df)


def summarize_exits(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    by_policy: Dict[str, dict] = {}
    for policy in ALL_POLICIES:
        sub = df[df["policy"] == policy]
        if sub.empty:
            by_policy[policy] = {"count": 0}
            continue
        rets = sub["return_pct"].astype(float)
        wins = sub["return_pct"] > 0
        avg_ret = float(rets.mean())
        win_rate = float(wins.sum()) / len(sub) * 100.0
        by_policy[policy] = {
            "count": len(sub),
            "avg_return": avg_ret,
            "median_return": float(rets.median()),
            "win_rate": win_rate,
            "avg_bars_held": float(sub["bars_held"].mean()),
            "avg_mfe": float(sub["mfe_before_exit"].dropna().mean() * 100)
            if sub["mfe_before_exit"].notna().any() else None,
            "avg_mae": float(sub["mae_before_exit"].dropna().mean() * 100)
            if sub["mae_before_exit"].notna().any() else None,
            "score": avg_ret * win_rate / 100.0,
        }

    by_initial_policy: List[dict] = []
    for itype in SURVIVAL_INITIAL_TYPES:
        for policy in ALL_POLICIES:
            sub = df[(df["initial_type"] == itype) & (df["policy"] == policy)]
            if sub.empty:
                continue
            rets = sub["return_pct"].astype(float)
            by_initial_policy.append({
                "initial_type": itype,
                "policy": policy,
                "avg_return": float(rets.mean()),
                "win_rate": float((rets > 0).sum()) / len(sub) * 100.0,
            })

    ranked = sorted(
        [(p, v) for p, v in by_policy.items() if v.get("count")],
        key=lambda x: x[1].get("score", -999),
        reverse=True,
    )

    return {
        "count": len(df),
        "by_policy": by_policy,
        "by_initial_policy": by_initial_policy,
        "ranked": ranked,
        "top3": ranked[:3],
        "worst": ranked[-1] if ranked else None,
    }
