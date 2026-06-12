"""Wave Rule Set Robustness — Rule Set 견고성 검증.

기존 validation CSV만 소비. 엔진·신호·기존 CSV/REPORT 수정 없음.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_regime_analysis import VOL_CLUSTERS, TREND_CLUSTERS, _trend_bucket, _vol_bucket

SYMBOL_TF_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
)

SYMBOLS = ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT")
TIMEFRAMES = ("1h", "4h", "1d")

EXIT_POLICIES = (
    "TP3_SL3_TIMEOUT20",
    "TP5_SL3_TIMEOUT40",
    "TP5_KTURN_TIMEOUT40",
    "K_CROSS_DOWN_TIMEOUT40",
    "WAVE_INVALIDATION_EXIT",
)

QUARTERS = ("Q1", "Q2", "Q3", "Q4")
WINDOW_FRAC = 0.20
STEP_FRAC = 0.10
MIN_SEGMENT_N = 1
MIN_ROLLING_N = 2

CSV_EXPORT_COLS = (
    "rule", "segment_type", "segment", "n", "win_rate", "expectancy",
    "profit_factor", "robustness_component", "robustness_score",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _resolve_csv(name: str) -> Optional[str]:
    path = os.path.join(_validation_dir(), name)
    return path if os.path.isfile(path) else None


def _load_paired(prefix: str) -> pd.DataFrame:
    parts: List[pd.DataFrame] = []
    for sym, tf in SYMBOL_TF_PAIRS:
        path = os.path.join(_validation_dir(), f"{prefix}_{sym}_{tf}.csv")
        if not os.path.isfile(path):
            alt = _resolve_csv(f"{prefix}.csv")
            if alt:
                path = alt
            else:
                continue
        df = pd.read_csv(path, parse_dates=["timestamp"])
        if "symbol" not in df.columns:
            df["symbol"] = sym
        if "timeframe" not in df.columns:
            df["timeframe"] = tf
        parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _bool_col(series: pd.Series) -> pd.Series:
    return series.map(
        lambda x: str(x).lower() in ("true", "1", "yes") if isinstance(x, str) else bool(x),
    )


def rule_filters() -> Dict[str, Callable[[pd.DataFrame], pd.Series]]:
    return {
        "RULE_A": lambda df: _bool_col(df["flag_tb"]) & _bool_col(df["flag_money_flow"]),
        "RULE_B": lambda df: (
            _bool_col(df["flag_tb"]) & _bool_col(df["flag_money_flow"]) & _bool_col(df["flag_structure"])
        ),
        "RULE_C": lambda df: _bool_col(df["flag_energy"]) & _bool_col(df["flag_money_flow"]),
        "RULE_D": lambda df: _bool_col(df["flag_tb"]) & _bool_col(df["flag_structure"]),
        "RULE_E": lambda df: df["quality_score"].astype(float) >= 4,
    }


def load_robustness_events() -> pd.DataFrame:
    path = _resolve_csv("wave_quality_score.csv")
    if not path:
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["timestamp"])
    key = ["timestamp", "symbol"]

    outcome = _load_paired("wave_outcome")
    if not outcome.empty:
        oc = [c for c in ("survival_bars",) if c in outcome.columns]
        if oc:
            df = df.merge(outcome[key + oc], on=key, how="left")

    seg = _load_paired("wave_segmentation")
    if not seg.empty and "survival_bucket" in seg.columns:
        df = df.merge(seg[key + ["survival_bucket"]], on=key, how="left")

    # regime: verdict timeline + confluence vol
    df["verdict_regime"] = pd.Series(dtype=object)
    for sym, tf in SYMBOL_TF_PAIRS:
        vt_path = os.path.join(_validation_dir(), f"verdict_timeline_{sym}_{tf}.csv")
        if os.path.isfile(vt_path):
            vt = pd.read_csv(vt_path, parse_dates=["timestamp"])
            if "regime" in vt.columns:
                vt = vt[["timestamp", "regime"]].rename(columns={"regime": "verdict_regime"})
                mask = df["symbol"] == sym
                merged = df.loc[mask, ["timestamp"]].merge(vt, on="timestamp", how="left")
                df.loc[mask, "verdict_regime"] = merged["verdict_regime"].values

        cf_path = os.path.join(_validation_dir(), f"wave_confluence_{sym}_{tf}.csv")
        if os.path.isfile(cf_path):
            cf = pd.read_csv(cf_path, parse_dates=["timestamp"])
            vol_cols = [c for c in ("atr_pct", "volatility_20", "ema20_slope_3", "ema60_slope_3") if c in cf.columns]
            if vol_cols:
                cf_sub = cf[["timestamp"] + vol_cols]
                mask = df["symbol"] == sym
                merged = df.loc[mask, ["timestamp"]].merge(cf_sub, on="timestamp", how="left")
                for c in vol_cols:
                    if c not in df.columns:
                        df[c] = np.nan
                    df.loc[mask, c] = merged[c].values

    df["trend_regime"] = df.get("verdict_regime", pd.Series(dtype=object)).map(
        lambda x: {"UP": "TREND_UP", "DOWN": "TREND_DOWN"}.get(str(x).upper(), "TREND_FLAT")
        if pd.notna(x) else "TREND_FLAT",
    )

    atr = df["atr_pct"].dropna().astype(float) if "atr_pct" in df.columns else pd.Series(dtype=float)
    if len(atr) >= 3:
        q33, q66 = float(atr.quantile(0.33)), float(atr.quantile(0.66))
        df["vol_regime"] = df["atr_pct"].apply(
            lambda v: _vol_bucket(float(v), q33, q66) if pd.notna(v) else "MID_VOL",
        )
    else:
        df["vol_regime"] = "MID_VOL"

    if "ema20_slope_3" in df.columns and "ema60_slope_3" in df.columns:
        df["trend_regime_alt"] = df.apply(
            lambda r: _trend_bucket(
                float(r["ema20_slope_3"]) if pd.notna(r.get("ema20_slope_3")) else None,
                float(r["ema60_slope_3"]) if pd.notna(r.get("ema60_slope_3")) else None,
            ),
            axis=1,
        )
    else:
        df["trend_regime_alt"] = df["trend_regime"]

    return df


def load_exit_returns() -> pd.DataFrame:
    parts = []
    for sym, tf in SYMBOL_TF_PAIRS:
        path = os.path.join(_validation_dir(), f"wave_exit_{sym}_{tf}.csv")
        if not os.path.isfile(path):
            continue
        ex = pd.read_csv(path, parse_dates=["timestamp"])
        ex["symbol"] = sym
        ex["timeframe"] = tf
        parts.append(ex)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _bucket_midpoint(bucket) -> Optional[float]:
    if pd.isna(bucket):
        return None
    s = str(bucket)
    if "-" in s:
        a, b = s.split("-", 1)
        try:
            return (float(a) + float(b)) / 2.0
        except ValueError:
            return None
    return None


def _avg_survival(sub: pd.DataFrame) -> Optional[float]:
    if "survival_bars" in sub.columns:
        v = sub["survival_bars"].dropna().astype(float)
        if len(v):
            return float(v.mean())
    if "survival_bucket" in sub.columns:
        mids = [_bucket_midpoint(b) for b in sub["survival_bucket"].dropna()]
        mids = [m for m in mids if m is not None]
        if mids:
            return float(np.mean(mids))
    return None


def evaluate_segment(sub: pd.DataFrame, return_col: str = "return_pct") -> dict:
    if sub.empty or return_col not in sub.columns:
        return {"n": 0}
    rets = sub[return_col].dropna().astype(float)
    if len(rets) == 0:
        return {"n": 0}
    m = compute_expectancy_metrics(rets)
    med = float(rets.median())
    return {
        "n": m.get("n", 0),
        "win_rate": m.get("win_rate"),
        "expectancy": m.get("expectancy"),
        "profit_factor": m.get("profit_factor"),
        "payoff_ratio": m.get("payoff_ratio"),
        "avg_return": m.get("avg_return"),
        "median_return": med,
        "avg_survival": _avg_survival(sub),
    }


def apply_rule(df: pd.DataFrame, rule_id: str) -> pd.DataFrame:
    flt = rule_filters()[rule_id]
    return df[flt(df)].copy()


def baseline_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for rule_id in rule_filters():
        sub = apply_rule(df, rule_id)
        m = evaluate_segment(sub)
        rows.append({"rule": rule_id, "segment_type": "baseline", "segment": "all", **m})
    return rows


def walk_forward_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for rule_id in rule_filters():
        sub = apply_rule(df, rule_id).sort_values("timestamp")
        if sub.empty:
            continue
        n = len(sub)
        splits = np.array_split(sub, 4)
        for qi, chunk in enumerate(splits):
            if chunk.empty:
                continue
            m = evaluate_segment(chunk)
            rows.append({
                "rule": rule_id,
                "segment_type": "walk_forward",
                "segment": QUARTERS[qi],
                **m,
            })
    return rows


def rolling_window_summary(df: pd.DataFrame) -> List[dict]:
    rows = []
    for rule_id in rule_filters():
        sub = apply_rule(df, rule_id).sort_values("timestamp").reset_index(drop=True)
        n = len(sub)
        if n < MIN_ROLLING_N:
            rows.append({
                "rule": rule_id,
                "segment_type": "rolling_summary",
                "segment": "all",
                "n": n,
                "avg_expectancy": None,
                "min_expectancy": None,
                "max_expectancy": None,
                "expectancy_variance": None,
                "negative_window_ratio": None,
            })
            continue

        win_size = max(MIN_ROLLING_N, int(round(n * WINDOW_FRAC)))
        step = max(1, int(round(n * STEP_FRAC)))
        exps: List[float] = []
        wins: List[float] = []
        for start in range(0, n - win_size + 1, step):
            chunk = sub.iloc[start: start + win_size]
            m = evaluate_segment(chunk)
            if m.get("expectancy") is not None:
                exps.append(float(m["expectancy"]))
            if m.get("win_rate") is not None:
                wins.append(float(m["win_rate"]))

        if not exps:
            neg_ratio = None
        else:
            neg_ratio = sum(1 for e in exps if e < 0) / len(exps)

        rows.append({
            "rule": rule_id,
            "segment_type": "rolling_summary",
            "segment": "all",
            "n": n,
            "window_count": len(exps),
            "avg_expectancy": float(np.mean(exps)) if exps else None,
            "min_expectancy": float(np.min(exps)) if exps else None,
            "max_expectancy": float(np.max(exps)) if exps else None,
            "expectancy_variance": float(np.var(exps)) if len(exps) > 1 else 0.0,
            "negative_window_ratio": neg_ratio,
            "avg_win_rate": float(np.mean(wins)) if wins else None,
        })
    return rows


def exit_policy_performance(df: pd.DataFrame, exit_df: pd.DataFrame) -> List[dict]:
    rows = []
    if exit_df.empty:
        return rows

    ex = exit_df[["timestamp", "symbol", "policy", "return_pct"]].rename(
        columns={"return_pct": "policy_return"},
    )

    for rule_id in rule_filters():
        sub = apply_rule(df, rule_id)
        if sub.empty:
            continue
        merged = sub.merge(ex, on=["timestamp", "symbol"], how="inner")
        policy_rows = []
        for pol in EXIT_POLICIES:
            psub = merged[merged["policy"] == pol]
            m = evaluate_segment(psub, return_col="policy_return")
            row = {
                "rule": rule_id,
                "segment_type": "exit_policy",
                "segment": pol,
                **m,
            }
            rows.append(row)
            if m.get("n", 0) > 0:
                policy_rows.append(row)

        if len(policy_rows) >= 2:
            exps = [r["expectancy"] for r in policy_rows if r.get("expectancy") is not None]
            sens = max(exps) - min(exps) if exps else None
            ranked = sorted(policy_rows, key=lambda x: x.get("expectancy") or -999, reverse=True)
            for rank, r in enumerate(ranked, 1):
                for row in rows:
                    if row["rule"] == rule_id and row["segment"] == r["segment"]:
                        row["policy_rank"] = rank
            rows.append({
                "rule": rule_id,
                "segment_type": "exit_sensitivity",
                "segment": "all",
                "n": sub.shape[0],
                "exit_policy_sensitivity": sens,
            })
    return rows


def _segment_type_name(col: str) -> str:
    if col == "symbol":
        return "symbol"
    if col == "timeframe":
        return "timeframe"
    if col.endswith("_regime"):
        return "regime"
    return col


def _segment_by_column(df: pd.DataFrame, col: str, values: Sequence[str]) -> List[dict]:
    rows = []
    seg_type = _segment_type_name(col)
    for rule_id in rule_filters():
        sub = apply_rule(df, rule_id)
        for val in values:
            chunk = sub[sub[col] == val] if col in sub.columns else pd.DataFrame()
            m = evaluate_segment(chunk)
            rows.append({
                "rule": rule_id,
                "segment_type": seg_type,
                "segment": val,
                **m,
            })
    return rows


def symbol_robustness(df: pd.DataFrame) -> Tuple[List[dict], Dict[str, float]]:
    rows = _segment_by_column(df, "symbol", SYMBOLS)
    ratios = {}
    for rule_id in rule_filters():
        pos = sum(
            1 for r in rows
            if r["rule"] == rule_id and r.get("n", 0) >= MIN_SEGMENT_N
            and r.get("expectancy") is not None and r["expectancy"] > 0
        )
        tested = sum(1 for r in rows if r["rule"] == rule_id and r.get("n", 0) >= MIN_SEGMENT_N)
        ratios[rule_id] = pos / tested if tested else 0.0
    return rows, ratios


def timeframe_robustness(df: pd.DataFrame) -> Tuple[List[dict], Dict[str, float]]:
    rows = _segment_by_column(df, "timeframe", TIMEFRAMES)
    ratios = {}
    for rule_id in rule_filters():
        pos = sum(
            1 for r in rows
            if r["rule"] == rule_id and r.get("n", 0) >= MIN_SEGMENT_N
            and r.get("expectancy") is not None and r["expectancy"] > 0
        )
        tested = sum(1 for r in rows if r["rule"] == rule_id and r.get("n", 0) >= MIN_SEGMENT_N)
        ratios[rule_id] = pos / tested if tested else 0.0
    return rows, ratios


def regime_robustness(df: pd.DataFrame) -> Tuple[List[dict], Dict[str, float]]:
    rows: List[dict] = []
    regimes = list(VOL_CLUSTERS) + list(TREND_CLUSTERS)
    for col in ("vol_regime", "trend_regime"):
        if col in df.columns:
            for val in (VOL_CLUSTERS if "vol" in col else TREND_CLUSTERS):
                rows.extend(_segment_by_column(df, col, [val]))
    ratios = {}
    for rule_id in rule_filters():
        rrows = [r for r in rows if r["rule"] == rule_id and r.get("n", 0) >= MIN_SEGMENT_N]
        pos = sum(1 for r in rrows if r.get("expectancy") is not None and r["expectancy"] > 0)
        ratios[rule_id] = pos / len(rrows) if rrows else 0.0
    return rows, ratios


def _clamp_score(v: float) -> float:
    return float(max(0.0, min(100.0, v)))


def compute_robustness_scores(
    walk_rows: List[dict],
    rolling_rows: List[dict],
    exit_rows: List[dict],
    symbol_ratios: Dict[str, float],
    tf_ratios: Dict[str, float],
    regime_ratios: Dict[str, float],
) -> List[dict]:
    scores = []
    max_sens = 6.0
    for rule_id in rule_filters():
        wf = [r for r in walk_rows if r["rule"] == rule_id and r.get("n", 0) > 0]
        pos_q = sum(1 for r in wf if r.get("expectancy") is not None and r["expectancy"] > 0)
        wf_score = _clamp_score((pos_q / len(wf) * 100) if wf else 0)

        roll = next((r for r in rolling_rows if r["rule"] == rule_id), {})
        neg = roll.get("negative_window_ratio")
        roll_score = _clamp_score((1.0 - neg) * 100 if neg is not None else 50.0)

        sens_row = next((r for r in exit_rows if r["rule"] == rule_id and r["segment_type"] == "exit_sensitivity"), {})
        sens = sens_row.get("exit_policy_sensitivity")
        exit_score = _clamp_score(100.0 * (1.0 - (sens / max_sens if sens is not None else 0.5)))

        sym_score = _clamp_score(symbol_ratios.get(rule_id, 0) * 100)
        tf_score = _clamp_score(tf_ratios.get(rule_id, 0) * 100)
        reg_score = _clamp_score(regime_ratios.get(rule_id, 0) * 100)

        components = {
            "walk_forward": wf_score,
            "rolling": roll_score,
            "exit_stability": exit_score,
            "symbol": sym_score,
            "timeframe": tf_score,
            "regime": reg_score,
        }
        overall = float(np.mean(list(components.values())))
        scores.append({
            "rule": rule_id,
            "segment_type": "robustness_score",
            "segment": "overall",
            "robustness_score": overall,
            **{f"score_{k}": v for k, v in components.items()},
        })
    return scores


def select_champion(
    baseline: List[dict],
    scores: List[dict],
) -> dict:
    base_map = {r["rule"]: r for r in baseline}
    ranked = sorted(
        scores,
        key=lambda s: (
            s.get("robustness_score") or 0,
            base_map.get(s["rule"], {}).get("expectancy") or -999,
            base_map.get(s["rule"], {}).get("n") or 0,
        ),
        reverse=True,
    )
    if not ranked:
        return {}
    champ = ranked[0]
    champ["baseline"] = base_map.get(champ["rule"], {})
    return champ


def practical_pass_fail(champion: dict, baseline: List[dict]) -> dict:
    rule = champion.get("rule")
    base = next((r for r in baseline if r["rule"] == rule), {})
    score = champion.get("robustness_score", 0)
    exp = base.get("expectancy")
    n = base.get("n", 0)
    passes = (
        score >= 50
        and exp is not None and exp > 0
        and n >= 3
        and champion.get("score_walk_forward", 0) >= 50
    )
    return {
        "result": "PASS" if passes else "FAIL",
        "pass": passes,
        "robustness_score": score,
        "expectancy": exp,
        "n": n,
    }


def build_robustness_csv(all_rows: List[dict], scores: List[dict]) -> pd.DataFrame:
    score_map = {s["rule"]: s.get("robustness_score") for s in scores}
    out = []
    for r in all_rows:
        row = {c: r.get(c) for c in CSV_EXPORT_COLS}
        if row.get("robustness_score") is None:
            row["robustness_score"] = score_map.get(r.get("rule"))
        out.append(row)
    for s in scores:
        out.append({
            "rule": s["rule"],
            "segment_type": "robustness_score",
            "segment": "overall",
            "n": None,
            "win_rate": None,
            "expectancy": None,
            "profit_factor": None,
            "robustness_component": "overall",
            "robustness_score": s.get("robustness_score"),
        })
    return pd.DataFrame(out)


def full_robustness_summary() -> dict:
    df = load_robustness_events()
    exit_df = load_exit_returns()

    baseline = baseline_performance(df)
    walk = walk_forward_performance(df)
    rolling = rolling_window_summary(df)
    exit_perf = exit_policy_performance(df, exit_df)
    sym_rows, sym_ratios = symbol_robustness(df)
    tf_rows, tf_ratios = timeframe_robustness(df)
    reg_rows, reg_ratios = regime_robustness(df)
    scores = compute_robustness_scores(walk, rolling, exit_perf, sym_ratios, tf_ratios, reg_ratios)
    champion = select_champion(baseline, scores)
    pf = practical_pass_fail(champion, baseline)

    all_rows = baseline + walk + rolling + exit_perf + sym_rows + tf_rows + reg_rows

    return {
        "dataframe": build_robustness_csv(all_rows, scores),
        "events": df,
        "event_count": len(df),
        "baseline": baseline,
        "walk_forward": walk,
        "rolling": rolling,
        "exit_policy": [r for r in exit_perf if r["segment_type"] == "exit_policy"],
        "exit_sensitivity": [r for r in exit_perf if r["segment_type"] == "exit_sensitivity"],
        "symbol_robustness": sym_rows,
        "symbol_positive_ratio": sym_ratios,
        "timeframe_robustness": tf_rows,
        "timeframe_positive_ratio": tf_ratios,
        "regime_robustness": reg_rows,
        "regime_positive_ratio": reg_ratios,
        "robustness_scores": scores,
        "champion": champion,
        "practical_pass_fail": pf,
    }
