"""Wave Candidate Rules — Confluence 우수 조건 강건성·안정성 관측.

기존 Confluence/Expectancy/Exit 산출물만 소비. 실전 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional

import pandas as pd

from analysis.wave_branch_analysis import BRANCH_REQUIRED
from analysis.wave_exit import POLICY_A, RULE_NEW_LL, RULE_RE_OS
from analysis.wave_expectancy import compute_expectancy_metrics

ROBUSTNESS_SCALE = 6.0  # TP3+SL3 % 스케일 (관측용 정규화)

FAILURE_CATEGORIES = ("RE_OVERSOLD", "NEW_LL", "STOP_LOSS", "TIMEOUT", "기타")

RULE_IDS = (
    "RULE_A",
    "RULE_B",
    "RULE_C",
    "RULE_D",
    "RULE_E",
    "RULE_F",
    "RULE_G",
    "RULE_H",
    "RULE_SCORE_3",
    "RULE_SCORE_4",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _is_triple_bottom(row: pd.Series) -> bool:
    branch = str(row.get("branch", row.get("branch_label", "")))
    return branch == BRANCH_REQUIRED


def _rsi_bucket_50_70(row: pd.Series) -> bool:
    return str(row.get("rsi_bucket", "")) in ("50-60", "60-70")


def _macd_above_zero(row: pd.Series) -> bool:
    v = row.get("MACD_ABOVE_ZERO", row.get("macd_above_zero"))
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


def _price_above_60(row: pd.Series) -> bool:
    v = row.get("PRICE_ABOVE_60", row.get("price_above_60"))
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


def _confluence_score(row: pd.Series) -> int:
    try:
        return int(row.get("confluence_score", 0))
    except (TypeError, ValueError):
        return 0


def rule_mask(df: pd.DataFrame, rule_id: str) -> pd.Series:
    """Rule별 boolean mask."""
    if df.empty:
        return pd.Series(dtype=bool)

    if rule_id == "RULE_A":
        return df.apply(_is_triple_bottom, axis=1)
    if rule_id == "RULE_B":
        return df.apply(lambda r: _is_triple_bottom(r) and _macd_above_zero(r), axis=1)
    if rule_id == "RULE_C":
        return df.apply(lambda r: _is_triple_bottom(r) and _rsi_bucket_50_70(r), axis=1)
    if rule_id == "RULE_D":
        return df.apply(lambda r: _is_triple_bottom(r) and _price_above_60(r), axis=1)
    if rule_id == "RULE_E":
        return df.apply(
            lambda r: _is_triple_bottom(r) and _macd_above_zero(r) and _rsi_bucket_50_70(r),
            axis=1,
        )
    if rule_id == "RULE_F":
        return df.apply(
            lambda r: _is_triple_bottom(r) and _macd_above_zero(r) and _price_above_60(r),
            axis=1,
        )
    if rule_id == "RULE_G":
        return df.apply(
            lambda r: _is_triple_bottom(r) and _rsi_bucket_50_70(r) and _price_above_60(r),
            axis=1,
        )
    if rule_id == "RULE_H":
        return df.apply(
            lambda r: (
                _is_triple_bottom(r)
                and _macd_above_zero(r)
                and _rsi_bucket_50_70(r)
                and _price_above_60(r)
            ),
            axis=1,
        )
    if rule_id == "RULE_SCORE_3":
        return df["confluence_score"] >= 3 if "confluence_score" in df.columns else pd.Series(False, index=df.index)
    if rule_id == "RULE_SCORE_4":
        return df["confluence_score"] >= 4 if "confluence_score" in df.columns else pd.Series(False, index=df.index)
    return pd.Series(False, index=df.index)


def _link_episode(
    db_ts: pd.Timestamp,
    lifecycle: pd.DataFrame,
    expectancy: pd.DataFrame,
) -> Optional[dict]:
    if lifecycle.empty or expectancy.empty:
        return None
    lc = lifecycle[lifecycle["timestamp"] <= db_ts]
    if lc.empty:
        return None
    ep_ts = pd.Timestamp(lc.iloc[-1]["timestamp"])
    exp = expectancy[expectancy["timestamp"] == ep_ts]
    if exp.empty:
        return None
    row = exp.iloc[0]
    success = row.get("success")
    if isinstance(success, str):
        success = success.lower() in ("true", "1", "yes")
    return {
        "episode_ts": ep_ts,
        "return_pct": float(row["return_pct"]),
        "success": bool(success),
    }


def _classify_failure_reason(exit_reason) -> str:
    if exit_reason is None or (isinstance(exit_reason, float) and pd.isna(exit_reason)):
        return "기타"
    r = str(exit_reason).upper()
    if RULE_RE_OS in r or "RE_OVERSOLD" in r:
        return "RE_OVERSOLD"
    if RULE_NEW_LL in r or "NEW_LL" in r:
        return "NEW_LL"
    if "STOP_LOSS" in r or r.startswith("SL"):
        return "STOP_LOSS"
    if "TIMEOUT" in r:
        return "TIMEOUT"
    return "기타"


def enrich_confluence_events(
    confluence: pd.DataFrame,
    symbol: str,
    interval: str,
) -> pd.DataFrame:
    """Confluence 이벤트에 episode·exit·survival 메타 연결."""
    if confluence.empty:
        return confluence

    out = confluence.copy()
    lc_path = _csv_path("wave_confirmation_lifecycle", symbol, interval)
    exp_path = _csv_path("wave_expectancy", symbol, interval)
    exit_path = _csv_path("wave_exit", symbol, interval)
    surv_path = _csv_path("wave_survival", symbol, interval)

    lifecycle = (
        pd.read_csv(lc_path, parse_dates=["timestamp"])
        if os.path.isfile(lc_path) else pd.DataFrame()
    )
    expectancy = (
        pd.read_csv(exp_path, parse_dates=["timestamp"])
        if os.path.isfile(exp_path) else pd.DataFrame()
    )
    exits = (
        pd.read_csv(exit_path, parse_dates=["timestamp"])
        if os.path.isfile(exit_path) else pd.DataFrame()
    )
    survival = (
        pd.read_csv(surv_path, parse_dates=["timestamp"])
        if os.path.isfile(surv_path) else pd.DataFrame()
    )

    tp3 = exits[exits["policy"] == POLICY_A] if not exits.empty else pd.DataFrame()
    exit_keyed = tp3.set_index("timestamp") if not tp3.empty else None
    surv_keyed = survival.set_index("timestamp") if not survival.empty else None

    episode_ts_list = []
    exit_reason_list = []
    mfe_list = []
    mae_list = []
    survival_list = []

    for _, row in out.iterrows():
        ts = pd.Timestamp(row["timestamp"])
        ep = _link_episode(ts, lifecycle, expectancy)
        if ep is None:
            episode_ts_list.append(None)
            exit_reason_list.append(None)
            mfe_list.append(None)
            mae_list.append(None)
            survival_list.append(None)
            continue
        ep_ts = ep["episode_ts"]
        episode_ts_list.append(ep_ts)
        if exit_keyed is not None and ep_ts in exit_keyed.index:
            ex = exit_keyed.loc[ep_ts]
            if isinstance(ex, pd.DataFrame):
                ex = ex.iloc[0]
            exit_reason_list.append(ex.get("exit_reason"))
            mfe = ex.get("mfe_before_exit")
            mae = ex.get("mae_before_exit")
            mfe_list.append(float(mfe) * 100.0 if pd.notna(mfe) else None)
            mae_list.append(float(mae) * 100.0 if pd.notna(mae) else None)
        else:
            exit_reason_list.append(None)
            mfe_list.append(None)
            mae_list.append(None)
        if surv_keyed is not None and ep_ts in surv_keyed.index:
            sv = surv_keyed.loc[ep_ts]
            if isinstance(sv, pd.DataFrame):
                sv = sv.iloc[0]
            survival_list.append(float(sv.get("survival_bars")) if pd.notna(sv.get("survival_bars")) else None)
        else:
            survival_list.append(None)

    out["episode_ts"] = episode_ts_list
    out["exit_reason"] = exit_reason_list
    out["mfe_pct"] = mfe_list
    out["mae_pct"] = mae_list
    out["survival_bars"] = survival_list
    out["failure_category"] = out["exit_reason"].map(_classify_failure_reason)
    return out


def _rule_metrics(grp: pd.DataFrame) -> dict:
    linked = grp.dropna(subset=["return_pct"])
    if linked.empty:
        return {
            "count": len(grp),
            "n": 0,
            "win": 0,
            "win_rate": 0.0,
            "avg_return": None,
            "median_return": None,
            "expectancy": None,
            "profit_factor": None,
            "payoff_ratio": None,
            "avg_mfe": None,
            "avg_mae": None,
            "avg_survival": None,
        }

    rets = linked["return_pct"].astype(float)
    m = compute_expectancy_metrics(rets)
    mfe = linked["mfe_pct"].dropna() if "mfe_pct" in linked.columns else pd.Series(dtype=float)
    mae = linked["mae_pct"].dropna() if "mae_pct" in linked.columns else pd.Series(dtype=float)
    surv = linked["survival_bars"].dropna() if "survival_bars" in linked.columns else pd.Series(dtype=float)

    pf = m.get("profit_factor", 0.0)
    if pf == float("inf"):
        pf = 999.0

    pr = m.get("payoff_ratio", 0.0)
    if pr == float("inf"):
        pr = 999.0

    return {
        "count": len(grp),
        "n": m.get("n", 0),
        "win": m.get("win", 0),
        "win_rate": m.get("win_rate", 0.0),
        "avg_return": m.get("avg_return"),
        "median_return": float(rets.median()),
        "expectancy": m.get("expectancy"),
        "profit_factor": pf,
        "payoff_ratio": pr,
        "avg_mfe": float(mfe.mean()) if len(mfe) else None,
        "avg_mae": float(mae.mean()) if len(mae) else None,
        "avg_survival": float(surv.mean()) if len(surv) else None,
    }


def compute_robustness(
    linked: pd.DataFrame,
    symbol: str = "ETHUSDT",
) -> dict:
    """ETH 시간 50/50 분할 A/B expectancy 및 robustness_gap."""
    empty = {
        "window_a_n": 0,
        "window_b_n": 0,
        "window_a_expectancy": None,
        "window_b_expectancy": None,
        "robustness_gap": None,
        "robustness_gap_normalized": 1.0,
    }
    if linked.empty or "timestamp" not in linked.columns:
        return empty
    grp = linked.sort_values("timestamp")
    if len(grp) < 4:
        return empty

    mid = len(grp) // 2
    a = grp.iloc[:mid]
    b = grp.iloc[mid:]
    a_linked = a.dropna(subset=["return_pct"])
    b_linked = b.dropna(subset=["return_pct"])

    if a_linked.empty or b_linked.empty:
        return empty

    exp_a = compute_expectancy_metrics(a_linked["return_pct"])["expectancy"]
    exp_b = compute_expectancy_metrics(b_linked["return_pct"])["expectancy"]
    gap = abs(float(exp_a) - float(exp_b))

    if symbol == "ETHUSDT":
        gap_norm = min(1.0, gap / ROBUSTNESS_SCALE)
    else:
        gap_norm = min(1.0, gap / ROBUSTNESS_SCALE)

    return {
        "window_a_n": len(a_linked),
        "window_b_n": len(b_linked),
        "window_a_expectancy": float(exp_a),
        "window_b_expectancy": float(exp_b),
        "robustness_gap": gap,
        "robustness_gap_normalized": gap_norm,
    }


def stability_score(expectancy: Optional[float], gap_normalized: float) -> Optional[float]:
    """관측용 Rule Stability Score."""
    if expectancy is None:
        return None
    return float(expectancy) * (1.0 - min(1.0, gap_normalized))


def failure_distribution(rule_id: str, failures: pd.DataFrame) -> List[dict]:
    """Rule 실패 건 exit_reason 분포."""
    if failures.empty or "failure_category" not in failures.columns:
        return []
    total = len(failures)
    rows = []
    for cat in FAILURE_CATEGORIES:
        cnt = int((failures["failure_category"] == cat).sum())
        if cnt == 0:
            continue
        rows.append({
            "rule": rule_id,
            "failure_reason": cat,
            "count": cnt,
            "pct": cnt / total * 100.0,
        })
    return rows


def evaluate_rule(df: pd.DataFrame, rule_id: str, symbol: str) -> dict:
    """단일 Rule 성과·강건성·실패 분포."""
    mask = rule_mask(df, rule_id)
    grp = df[mask]
    linked = df[mask].dropna(subset=["return_pct"])
    metrics = _rule_metrics(grp)
    robust = compute_robustness(linked, symbol) if not linked.empty else compute_robustness(pd.DataFrame(), symbol)

    exp = metrics.get("expectancy")
    gap_norm = robust.get("robustness_gap_normalized", 1.0)
    stab = stability_score(exp, gap_norm if gap_norm is not None else 1.0)

    failures = linked[linked["success"] == False] if not linked.empty and "success" in linked.columns else pd.DataFrame()
    fail_dist = failure_distribution(rule_id, failures)

    return {
        "rule": rule_id,
        **metrics,
        **robust,
        "stability_score": stab,
        "failure_distribution": fail_dist,
    }


def rank_rules(rule_results: List[dict]) -> List[dict]:
    """Stability Score → Expectancy → Sample Count."""
    def _key(r: dict):
        exp = r.get("expectancy")
        exp_val = exp if exp is not None else -999.0
        stab = r.get("stability_score")
        stab_val = stab if stab is not None else -999.0
        return (stab_val, exp_val, r.get("n", 0))

    return sorted(rule_results, key=_key, reverse=True)


def build_candidate_rules(
    symbol: str,
    interval: str,
    confluence_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Rule별 성과 요약 DataFrame."""
    if confluence_df is None:
        path = _csv_path("wave_confluence", symbol, interval)
        if not os.path.isfile(path):
            return pd.DataFrame()
        confluence_df = pd.read_csv(path, parse_dates=["timestamp"])

    if confluence_df.empty:
        return pd.DataFrame()

    enriched = enrich_confluence_events(confluence_df, symbol, interval)
    results = [evaluate_rule(enriched, rid, symbol) for rid in RULE_IDS]

    rows = []
    for r in results:
        rows.append({
            "rule": r["rule"],
            "count": r["count"],
            "n": r["n"],
            "win": r["win"],
            "win_rate": r["win_rate"],
            "avg_return": r["avg_return"],
            "median_return": r["median_return"],
            "expectancy": r["expectancy"],
            "profit_factor": r["profit_factor"],
            "payoff_ratio": r["payoff_ratio"],
            "avg_mfe": r["avg_mfe"],
            "avg_mae": r["avg_mae"],
            "avg_survival": r["avg_survival"],
            "window_a_expectancy": r.get("window_a_expectancy"),
            "window_b_expectancy": r.get("window_b_expectancy"),
            "window_a_n": r.get("window_a_n", 0),
            "window_b_n": r.get("window_b_n", 0),
            "robustness_gap": r.get("robustness_gap"),
            "robustness_gap_normalized": r.get("robustness_gap_normalized"),
            "stability_score": r.get("stability_score"),
        })
    return pd.DataFrame(rows)


def summarize_candidate_rules(
    rules_df: pd.DataFrame,
    symbol: str,
    interval: str,
    enriched: Optional[pd.DataFrame] = None,
) -> dict:
    """REPORT/UI용 요약."""
    if enriched is None:
        path = _csv_path("wave_confluence", symbol, interval)
        if os.path.isfile(path):
            conf = pd.read_csv(path, parse_dates=["timestamp"])
            enriched = enrich_confluence_events(conf, symbol, interval)

    if rules_df.empty and enriched is not None:
        results = [evaluate_rule(enriched, rid, symbol) for rid in RULE_IDS]
    elif not rules_df.empty:
        results = rules_df.to_dict("records")
    else:
        return {"count": 0, "symbol": symbol, "interval": interval}

    fail_rows: List[dict] = []
    if enriched is not None:
        for rid in RULE_IDS:
            mask = rule_mask(enriched, rid)
            linked = enriched[mask].dropna(subset=["return_pct"])
            failures = linked[linked["success"] == False] if not linked.empty else pd.DataFrame()
            fail_rows.extend(failure_distribution(rid, failures))

    ranked = rank_rules(results) if results and "failure_distribution" in results[0] else sorted(
        results,
        key=lambda r: (
            r.get("stability_score") if r.get("stability_score") is not None else -999.0,
            r.get("expectancy") if r.get("expectancy") is not None else -999.0,
            r.get("n", 0),
        ),
        reverse=True,
    )
    def _stab_key(x: dict, default: float) -> float:
        v = x.get("stability_score")
        return float(v) if v is not None else default

    most_stable = max(ranked, key=lambda x: _stab_key(x, -999.0)) if ranked else {}
    least_stable = min(ranked, key=lambda x: _stab_key(x, 999.0)) if ranked else {}

    return {
        "symbol": symbol,
        "interval": interval,
        "count": len(enriched) if enriched is not None else 0,
        "rule_performance": ranked,
        "rule_robustness": [
            {
                "rule": r["rule"],
                "window_a": r.get("window_a_expectancy"),
                "window_b": r.get("window_b_expectancy"),
                "gap": r.get("robustness_gap"),
            }
            for r in ranked
        ],
        "stability_scores": [
            {
                "rule": r["rule"],
                "stability_score": r.get("stability_score"),
                "expectancy": r.get("expectancy"),
                "n": r.get("n", 0),
            }
            for r in ranked
        ],
        "top_rules": ranked[:10],
        "most_stable_rule": most_stable,
        "least_stable_rule": least_stable,
        "failure_analysis": fail_rows,
    }
