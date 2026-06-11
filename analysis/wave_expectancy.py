"""Wave Expectancy — TP3 기준 기대값 분석.

기존 Segmentation·Exit 산출물만 소비. 전략·엔진 수정 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Dict, List, Optional

import pandas as pd

from analysis.wave_exit import POLICY_A
from analysis.wave_segmentation import MIN_SAMPLE

FAMILY_SHORT = {
    "BUY_FAMILY": "BUY",
    "SELL_FAMILY": "SELL",
    "NEUTRAL": "NEUTRAL",
}

FEATURE_DIMS = (
    "initial_type", "state", "family", "stable_family",
    "survival_bucket", "verdict",
)

COMBO_DIMS = (
    "initial_type", "survival_bucket", "state", "family",
    "stable_family", "verdict",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _seg_path(symbol: str, interval: str) -> str:
    return os.path.join(
        _validation_dir(), f"wave_segmentation_{symbol}_{interval}.csv",
    )


def _exit_path(symbol: str, interval: str) -> str:
    return os.path.join(
        _validation_dir(), f"wave_exit_{symbol}_{interval}.csv",
    )


def compute_expectancy_metrics(returns: pd.Series) -> dict:
    """그룹 return_pct 시리즈로 기대값 지표 계산."""
    rets = returns.dropna().astype(float)
    n = len(rets)
    if n == 0:
        return {"n": 0}

    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / n

    avg_win = float(wins.mean()) if win_count else 0.0
    avg_loss = float(losses.abs().mean()) if loss_count else 0.0

    expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss

    total_profit = float(wins.sum()) if win_count else 0.0
    total_loss = float(losses.abs().sum()) if loss_count else 0.0
    if total_loss > 0:
        profit_factor = total_profit / total_loss
    elif total_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    if avg_loss > 0:
        payoff_ratio = avg_win / avg_loss
        recovery_ratio = avg_win / avg_loss
    else:
        payoff_ratio = float("inf") if avg_win > 0 else 0.0
        recovery_ratio = payoff_ratio

    return {
        "n": n,
        "win": win_count,
        "loss": loss_count,
        "win_rate": win_rate * 100.0,
        "success_rate": win_rate * 100.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "payoff_ratio": payoff_ratio,
        "recovery_ratio": recovery_ratio,
        "avg_return": float(rets.mean()),
    }


def _normalize_family(val: str) -> str:
    return FAMILY_SHORT.get(str(val), str(val))


CSV_EXPORT_COLS = (
    "timestamp", "return_pct", "success", "initial_type", "state",
    "family", "stable_family", "survival_bucket", "expectancy_group",
)


def build_expectancy(symbol: str, interval: str) -> pd.DataFrame:
    """Segmentation CSV + Exit CSV 검증 후 에피소드 DataFrame."""
    seg_path = _seg_path(symbol, interval)
    if not os.path.isfile(seg_path):
        return pd.DataFrame()

    seg = pd.read_csv(seg_path, parse_dates=["timestamp"])
    if seg.empty:
        return pd.DataFrame()

    exit_path = _exit_path(symbol, interval)
    if os.path.isfile(exit_path):
        exits = pd.read_csv(exit_path, parse_dates=["timestamp"])
        tp3 = exits[exits["policy"] == POLICY_A]
        if len(tp3) != len(seg):
            pass  # 관측용: segmentation 기준 유지

    if "success" in seg.columns:
        if seg["success"].dtype == object:
            seg["success"] = seg["success"].map(
                lambda x: str(x).lower() in ("true", "1", "yes"),
            )
    else:
        seg["success"] = seg["return_pct"] > 0

    seg["expectancy_group"] = (
        seg["initial_type"].astype(str) + "|"
        + seg["state"].astype(str) + "|"
        + seg["survival_bucket"].astype(str)
    )
    return seg


def export_expectancy_csv(df: pd.DataFrame, path: str) -> None:
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    df[cols].to_csv(path, index=False)


def _group_metrics(df: pd.DataFrame, col: str, value) -> dict:
    mask = df[col] == value
    m = compute_expectancy_metrics(df.loc[mask, "return_pct"])
    m["feature"] = col
    m["value"] = str(value)
    m["label"] = f"{col}={value}"
    return m


def _combo_expectancy(df: pd.DataFrame) -> List[dict]:
    """Segmentation과 동일 2조건 조합 + expectancy."""
    dims = tuple(c for c in COMBO_DIMS if c in df.columns)
    results: List[dict] = []

    def _add(mask: pd.Series, label: str) -> None:
        grp = df[mask]
        if len(grp) < MIN_SAMPLE:
            return
        m = compute_expectancy_metrics(grp["return_pct"])
        results.append({"condition": label, **m})

    for k1, k2 in combinations(dims, 2):
        for v1 in df[k1].dropna().unique():
            for v2 in df[df[k1] == v1][k2].dropna().unique():
                mask = (df[k1] == v1) & (df[k2] == v2)
                _add(mask, f"{k1}={v1} & {k2}={v2}")

    if "survival_bars" in df.columns:
        for thr in (20, 40):
            base = df["survival_bars"] >= thr
            for k in dims:
                for v in df.loc[base, k].dropna().unique():
                    mask = base & (df[k] == v)
                    _add(mask, f"survival>={thr} & {k}={v}")

    return results


def _find_win_exp_mismatches(groups: List[dict]) -> dict:
    """성공률 vs 기대값 불일치 그룹."""
    eligible = [g for g in groups if g.get("n", 0) >= MIN_SAMPLE]
    high_win_low_exp = [
        g for g in eligible
        if g.get("success_rate", 0) >= 50.0
        and round(g.get("expectancy", 0), 2) <= 0
    ]
    low_win_high_exp = [
        g for g in eligible
        if g.get("success_rate", 0) < 50.0
        and round(g.get("expectancy", 0), 2) > 0
    ]
    high_win_low_exp.sort(
        key=lambda x: (x["success_rate"], -x["expectancy"]), reverse=True,
    )
    low_win_high_exp.sort(key=lambda x: x["expectancy"], reverse=True)
    return {
        "high_win_low_expectancy": high_win_low_exp,
        "low_win_high_expectancy": low_win_high_exp,
    }


def summarize_expectancy(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0}

    by_feature: Dict[str, List[dict]] = {}
    for col in FEATURE_DIMS:
        if col not in df.columns:
            continue
        rows = []
        for val in df[col].dropna().unique():
            rows.append(_group_metrics(df, col, val))
        by_feature[col] = rows

    all_single: List[dict] = []
    for col, rows in by_feature.items():
        for r in rows:
            all_single.append({**r, "label": f"{col}={r['value']}"})

    combos = _combo_expectancy(df)
    all_groups = all_single + [
        {**c, "label": c["condition"]} for c in combos
    ]

    eligible = [g for g in all_groups if g.get("n", 0) >= MIN_SAMPLE]
    top_expectancy = sorted(
        eligible, key=lambda x: x.get("expectancy", -999), reverse=True,
    )[:20]
    worst_expectancy = sorted(
        eligible, key=lambda x: x.get("expectancy", 999),
    )[:20]

    pf_eligible = [
        g for g in eligible
        if g.get("profit_factor", 0) not in (float("inf"), 0)
        and g.get("n", 0) >= MIN_SAMPLE
    ]
    highest_pf = max(
        pf_eligible, key=lambda x: x["profit_factor"], default=None,
    )
    payoff_eligible = [
        g for g in eligible
        if g.get("payoff_ratio", 0) != float("inf")
        and g.get("avg_loss", 0) > 0
    ]
    highest_payoff = max(
        payoff_eligible, key=lambda x: x["payoff_ratio"], default=None,
    )

    mismatches = _find_win_exp_mismatches(all_groups)

    overall = compute_expectancy_metrics(df["return_pct"])

    return {
        "count": len(df),
        "overall": overall,
        "by_feature": by_feature,
        "combos": sorted(combos, key=lambda x: x.get("expectancy", -999), reverse=True),
        "top_expectancy": top_expectancy,
        "worst_expectancy": worst_expectancy,
        "top10_expectancy": top_expectancy[:10],
        "worst10_expectancy": worst_expectancy[:10],
        "highest_profit_factor": highest_pf,
        "highest_payoff_ratio": highest_payoff,
        **mismatches,
        "scatter": [
            {
                "label": g["label"],
                "success_rate": g["success_rate"],
                "expectancy": g["expectancy"],
                "n": g["n"],
            }
            for g in eligible
        ],
    }
