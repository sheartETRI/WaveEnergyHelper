"""Wave Quality Rule Set — 기대값을 만드는 최소 Rule Set 발견.

기존 validation CSV만 소비. 엔진·신호·기존 CSV 수정 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_regime_gated import compute_robustness_gap

MIN_RULE_N = 3
MAX_RULE_SIZE = 5
TOP_K = 30

SYMBOL_TF_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
)

RULE_CONDITIONS: Tuple[Tuple[str, str], ...] = (
    ("flag_tb", "TB"),
    ("flag_structure", "Structure>=3"),
    ("flag_energy", "Energy>=3"),
    ("flag_money_flow", "MoneyFlow>=4"),
    ("flag_ma120_slope", "MA120_slope>0"),
    ("flag_divergence", "Bullish_Div"),
    ("flag_price_ma480", "price<MA480"),
)

INTERACTION_CHAIN: Tuple[str, ...] = (
    "flag_money_flow",
    "flag_structure",
    "flag_tb",
    "flag_energy",
)

CSV_EXPORT_COLS = (
    "rule_id", "rule_size", "rule_label", "n", "win_rate", "expectancy",
    "profit_factor", "payoff_ratio", "avg_return", "median_return",
    "avg_survival", "robustness_gap",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _resolve_csv(canonical: str, fallbacks: Tuple[str, ...]) -> Optional[str]:
    base = _validation_dir()
    for name in (canonical, *fallbacks):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def _load_paired_csv(prefix: str) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for sym, tf in SYMBOL_TF_PAIRS:
        path = os.path.join(_validation_dir(), f"{prefix}_{sym}_{tf}.csv")
        if not os.path.isfile(path):
            continue
        df = pd.read_csv(path, parse_dates=["timestamp"])
        if "symbol" not in df.columns:
            df["symbol"] = sym
        if "timeframe" not in df.columns:
            df["timeframe"] = tf
        parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _label_for_keys(keys: Sequence[str]) -> str:
    key_to_label = {k: lbl for k, lbl in RULE_CONDITIONS}
    return " + ".join(key_to_label[k] for k in keys)


def load_ruleset_events() -> pd.DataFrame:
    """wave_quality_score.csv + survival 보강."""
    path = os.path.join(_validation_dir(), "wave_quality_score.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["timestamp"])
    key = ["timestamp", "symbol"]

    outcome_parts = []
    for sym, tf in SYMBOL_TF_PAIRS:
        op = _resolve_csv(f"wave_outcome_{sym}_{tf}.csv", ("wave_outcome.csv",))
        if op:
            odf = pd.read_csv(op, parse_dates=["timestamp"])
            odf["symbol"] = sym
            outcome_parts.append(odf)
    if outcome_parts:
        outcome = pd.concat(outcome_parts, ignore_index=True)
        oc = [c for c in ("survival_bars",) if c in outcome.columns]
        if oc:
            df = df.merge(outcome[key + oc], on=key, how="left")

    seg = _load_paired_csv("wave_segmentation")
    if not seg.empty and "survival_bucket" in seg.columns:
        sc = [c for c in ("survival_bucket",) if c in seg.columns]
        df = df.merge(seg[key + sc], on=key, how="left", suffixes=("", "_seg"))

    for col, _ in RULE_CONDITIONS:
        if col in df.columns:
            df[col] = df[col].map(lambda x: str(x).lower() in ("true", "1", "yes") if isinstance(x, str) else bool(x))
    return df


def _bucket_midpoint(bucket) -> Optional[float]:
    if pd.isna(bucket):
        return None
    s = str(bucket)
    if "-" in s:
        parts = s.split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2.0
        except ValueError:
            return None
    return None


def _avg_survival(sub: pd.DataFrame) -> Optional[float]:
    if "survival_bars" in sub.columns:
        vals = sub["survival_bars"].dropna().astype(float)
        if len(vals):
            return float(vals.mean())
    if "survival_bucket" in sub.columns:
        mids = [_bucket_midpoint(b) for b in sub["survival_bucket"].dropna()]
        mids = [m for m in mids if m is not None]
        if mids:
            return float(np.mean(mids))
    return None


def evaluate_rule_set(df: pd.DataFrame, keys: Sequence[str]) -> dict:
    """단일 rule set 성과."""
    mask = pd.Series(True, index=df.index)
    for k in keys:
        if k not in df.columns:
            return {"rule_label": _label_for_keys(keys), "rule_size": len(keys), "n": 0}
        mask &= df[k].astype(bool)

    sub = df[mask]
    label = _label_for_keys(keys)
    if len(sub) < MIN_RULE_N:
        return {
            "rule_keys": list(keys),
            "rule_label": label,
            "rule_size": len(keys),
            "n": len(sub),
        }

    rets = sub["return_pct"].dropna().astype(float)
    m = compute_expectancy_metrics(rets)
    gap = compute_robustness_gap(sub)
    med = float(rets.median()) if len(rets) else None

    return {
        "rule_keys": list(keys),
        "rule_label": label,
        "rule_size": len(keys),
        "n": m.get("n", 0),
        "win_rate": m.get("win_rate"),
        "expectancy": m.get("expectancy"),
        "profit_factor": m.get("profit_factor"),
        "payoff_ratio": m.get("payoff_ratio"),
        "avg_return": m.get("avg_return"),
        "median_return": med,
        "avg_survival": _avg_survival(sub),
        "robustness_gap": gap,
    }


def generate_all_rule_sets(df: pd.DataFrame) -> List[dict]:
    """1~5개 조건 전수 조합 (n>=MIN_RULE_N)."""
    keys = [k for k, _ in RULE_CONDITIONS]
    results: List[dict] = []
    rid = 0
    for size in range(1, MAX_RULE_SIZE + 1):
        for combo in combinations(keys, size):
            row = evaluate_rule_set(df, combo)
            if row.get("n", 0) >= MIN_RULE_N:
                rid += 1
                row["rule_id"] = rid
                results.append(row)
    return results


def _sort_top(rules: List[dict], key: str, reverse: bool = True, n: int = TOP_K) -> List[dict]:
    valid = [r for r in rules if r.get(key) is not None and r.get("n", 0) >= MIN_RULE_N]
    return sorted(valid, key=lambda x: x.get(key) or (-999 if reverse else 999), reverse=reverse)[:n]


def top_by_expectancy(rules: List[dict]) -> List[dict]:
    return _sort_top(rules, "expectancy")


def top_by_win_rate(rules: List[dict]) -> List[dict]:
    return _sort_top(rules, "win_rate")


def top_by_profit_factor(rules: List[dict]) -> List[dict]:
    return _sort_top(rules, "profit_factor")


def top_by_robust(rules: List[dict]) -> List[dict]:
    """robustness_gap 낮을수록 robust."""
    valid = [r for r in rules if r.get("robustness_gap") is not None and r.get("n", 0) >= MIN_RULE_N]
    return sorted(valid, key=lambda x: x.get("robustness_gap", 999))[:TOP_K]


def _dominates(a: dict, b: dict) -> bool:
    """a가 b를 3축 모두에서 지배 (expectancy, win_rate, n)."""
    ae, aw, an = a.get("expectancy"), a.get("win_rate"), a.get("n", 0)
    be, bw, bn = b.get("expectancy"), b.get("win_rate"), b.get("n", 0)
    if None in (ae, aw, be, bw):
        return False
    return ae >= be and aw >= bw and an >= bn and (ae > be or aw > bw or an > bn)


def pareto_frontier(rules: List[dict]) -> List[dict]:
    valid = [r for r in rules if r.get("n", 0) >= MIN_RULE_N and r.get("expectancy") is not None]
    frontier: List[dict] = []
    for r in valid:
        dominated = any(_dominates(other, r) for other in valid if other is not r)
        if not dominated:
            frontier.append(r)
    return sorted(frontier, key=lambda x: (x.get("expectancy") or 0), reverse=True)


def rule_size_effect(rules: List[dict]) -> List[dict]:
    """조건 개수별 평균 성과."""
    rows = []
    for size in range(1, MAX_RULE_SIZE + 1):
        subset = [r for r in rules if r.get("rule_size") == size and r.get("n", 0) >= MIN_RULE_N]
        if not subset:
            continue
        rows.append({
            "rule_size": size,
            "rule_count": len(subset),
            "avg_n": float(np.mean([r["n"] for r in subset])),
            "avg_win_rate": float(np.mean([r["win_rate"] for r in subset if r.get("win_rate") is not None])),
            "avg_expectancy": float(np.mean([r["expectancy"] for r in subset if r.get("expectancy") is not None])),
            "avg_profit_factor": float(np.mean([
                r["profit_factor"] for r in subset
                if r.get("profit_factor") is not None and r["profit_factor"] != float("inf")
            ])),
            "max_expectancy": max((r.get("expectancy") or -999) for r in subset),
        })
    return rows


def feature_interaction_map(df: pd.DataFrame) -> List[dict]:
    """조건 순차 추가 시 ΔExpectancy / ΔWinRate."""
    rows = []
    chains = [
        INTERACTION_CHAIN,
        ("flag_tb", "flag_structure", "flag_money_flow", "flag_energy"),
        ("flag_structure", "flag_money_flow", "flag_energy"),
    ]
    seen = set()
    for chain in chains:
        if tuple(chain) in seen:
            continue
        seen.add(tuple(chain))
        prev: Optional[dict] = None
        for i, key in enumerate(chain):
            keys = chain[: i + 1]
            cur = evaluate_rule_set(df, keys)
            if cur.get("n", 0) < MIN_RULE_N and i > 0:
                break
            row = {
                "chain": " → ".join(_label_for_keys([k]) for k in keys),
                "step": i + 1,
                "rule_label": cur.get("rule_label"),
                "n": cur.get("n", 0),
                "expectancy": cur.get("expectancy"),
                "win_rate": cur.get("win_rate"),
                "delta_expectancy": None,
                "delta_win_rate": None,
            }
            if prev and cur.get("expectancy") is not None and prev.get("expectancy") is not None:
                row["delta_expectancy"] = float(cur["expectancy"]) - float(prev["expectancy"])
            if prev and cur.get("win_rate") is not None and prev.get("win_rate") is not None:
                row["delta_win_rate"] = float(cur["win_rate"]) - float(prev["win_rate"])
            rows.append(row)
            prev = cur if cur.get("n", 0) >= MIN_RULE_N else prev
    return rows


def _balanced_score(rule: dict) -> Optional[float]:
    exp = rule.get("expectancy")
    n = rule.get("n", 0)
    gap = rule.get("robustness_gap")
    if exp is None or n < MIN_RULE_N:
        return None
    robust = 1.0 / (1.0 + (gap if gap is not None else 5.0))
    sample = min(n / 20.0, 1.0)
    return float(exp) * robust * (0.5 + 0.5 * sample)


def best_practical_rules(rules: List[dict]) -> dict:
    valid = [r for r in rules if r.get("n", 0) >= MIN_RULE_N and r.get("expectancy") is not None]
    if not valid:
        return {}
    best_exp = max(valid, key=lambda x: x.get("expectancy") or -999)
    robust_valid = [r for r in valid if r.get("robustness_gap") is not None]
    best_robust = min(robust_valid, key=lambda x: x.get("robustness_gap", 999)) if robust_valid else {}
    best_sample = max(valid, key=lambda x: x.get("n", 0))
    for r in valid:
        r["_balanced"] = _balanced_score(r)
    balanced_valid = [r for r in valid if r.get("_balanced") is not None]
    best_balanced = max(balanced_valid, key=lambda x: x["_balanced"]) if balanced_valid else {}
    return {
        "best_expectancy": best_exp,
        "best_robust": best_robust,
        "best_sample": best_sample,
        "best_balanced": best_balanced,
    }


def symbol_rule_comparison(df: pd.DataFrame, rule_keys: Sequence[str]) -> List[dict]:
    rows = []
    for sym in ("ETHUSDT", "BTCUSDT"):
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        ev = evaluate_rule_set(sub, rule_keys)
        rows.append({"symbol": sym, **{k: ev.get(k) for k in (
            "n", "win_rate", "expectancy", "profit_factor", "rule_label",
        )}})
    return rows


def timeframe_rule_comparison(df: pd.DataFrame, rule_keys: Sequence[str]) -> List[dict]:
    rows = []
    for tf in ("4h", "1d"):
        sub = df[df["timeframe"] == tf]
        if sub.empty:
            continue
        ev = evaluate_rule_set(sub, rule_keys)
        rows.append({"timeframe": tf, **{k: ev.get(k) for k in (
            "n", "win_rate", "expectancy", "profit_factor", "rule_label",
        )}})
    return rows


def _quality_score_benchmark(df: pd.DataFrame) -> dict:
    """Quality Score 방식 벤치마크."""
    rows = []
    for score in range(8):
        sub = df[df["quality_score"] == score]
        if len(sub) >= MIN_RULE_N:
            m = compute_expectancy_metrics(sub["return_pct"])
            rows.append({"method": f"score={score}", "n": m["n"], **m})
    for thr in range(1, 8):
        sub = df[df["quality_score"] >= thr]
        if len(sub) >= MIN_RULE_N:
            m = compute_expectancy_metrics(sub["return_pct"])
            rows.append({"method": f"score>={thr}", "n": m["n"], **m})
    best = max(rows, key=lambda x: x.get("expectancy") or -999) if rows else {}
    return {"benchmarks": rows, "best": best}


def compare_vs_quality_score(rules: List[dict], df: pd.DataFrame) -> dict:
    """Rule Set vs Quality Score 설명력 비교."""
    bench = _quality_score_benchmark(df)
    best_q = bench.get("best", {})
    valid = [r for r in rules if r.get("n", 0) >= MIN_RULE_N]
    best_rule = max(valid, key=lambda x: x.get("expectancy") or -999) if valid else {}

    q_exp = best_q.get("expectancy")
    r_exp = best_rule.get("expectancy")
    q_n = best_q.get("n", 0)
    r_n = best_rule.get("n", 0)

    exp_improvement = None
    if q_exp is not None and r_exp is not None:
        exp_improvement = float(r_exp) - float(q_exp)

    # PASS: rule set best expectancy >= quality best AND (higher n or >= expectancy with gap)
    passes = False
    if r_exp is not None and q_exp is not None:
        passes = float(r_exp) >= float(q_exp) and (
            float(r_exp) > float(q_exp) or int(r_n) >= int(q_n)
        )

    return {
        "quality_best": best_q,
        "rule_best": best_rule,
        "expectancy_improvement": exp_improvement,
        "result": "PASS" if passes else "FAIL",
        "pass": passes,
    }


def element_necessity(rules: List[dict]) -> List[dict]:
    """Top rule 출현 빈도 + 단독 성과로 필요/불필요 구분."""
    top = top_by_expectancy(rules)[:15]
    freq: Dict[str, int] = {lbl: 0 for _, lbl in RULE_CONDITIONS}
    for r in top:
        label = r.get("rule_label", "")
        for key, lbl in RULE_CONDITIONS:
            if lbl in label:
                freq[lbl] += 1

    singles = {r["rule_label"]: r for r in rules if r.get("rule_size") == 1 and r.get("n", 0) >= MIN_RULE_N}
    rows = []
    for key, lbl in RULE_CONDITIONS:
        s = singles.get(lbl, {})
        exp = s.get("expectancy")
        classification = "unnecessary"
        if freq.get(lbl, 0) >= 3 and exp is not None and exp > 0:
            classification = "essential"
        elif freq.get(lbl, 0) >= 2 or (exp is not None and exp > 0):
            classification = "useful"
        elif exp is not None and exp < 0:
            classification = "weak"
        rows.append({
            "element": lbl,
            "top15_frequency": freq.get(lbl, 0),
            "solo_n": s.get("n", 0),
            "solo_expectancy": exp,
            "classification": classification,
        })
    return sorted(rows, key=lambda x: x["top15_frequency"], reverse=True)


def build_ruleset_csv(rules: List[dict]) -> pd.DataFrame:
    if not rules:
        return pd.DataFrame()
    rows = [{c: r.get(c) for c in CSV_EXPORT_COLS} for r in rules]
    return pd.DataFrame(rows)


def full_ruleset_summary() -> dict:
    df = load_ruleset_events()
    rules = generate_all_rule_sets(df)
    practical = best_practical_rules(rules)
    best_bal = practical.get("best_balanced", {})
    best_keys = best_bal.get("rule_keys", practical.get("best_expectancy", {}).get("rule_keys", []))

    return {
        "dataframe": build_ruleset_csv(rules),
        "raw_events": df,
        "rule_count": len(rules),
        "event_count": len(df),
        "all_rules": rules,
        "top_expectancy": top_by_expectancy(rules),
        "top_win_rate": top_by_win_rate(rules),
        "top_profit_factor": top_by_profit_factor(rules),
        "top_robust": top_by_robust(rules),
        "pareto_frontier": pareto_frontier(rules),
        "rule_size_effect": rule_size_effect(rules),
        "feature_interaction": feature_interaction_map(df),
        "practical_rules": practical,
        "symbol_comparison": symbol_rule_comparison(df, best_keys) if best_keys else [],
        "timeframe_comparison": timeframe_rule_comparison(df, best_keys) if best_keys else [],
        "vs_quality_score": compare_vs_quality_score(rules, df),
        "element_necessity": element_necessity(rules),
    }
