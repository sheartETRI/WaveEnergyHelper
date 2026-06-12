"""Wave Quality Score — 관측 레이어 통합 품질 점수 검증.

기존 validation CSV만 소비. 엔진·신호·기존 CSV 수정 없음.
"""
from __future__ import annotations

import os
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES

STRUCTURE_MIN = 3
ENERGY_MIN = 3
MONEY_FLOW_MIN = 4
MAX_SCORE = 7
MIN_COMBO_N = 2

SYMBOL_TF_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("ETHUSDT", "4h"),
    ("BTCUSDT", "1d"),
)

FEATURE_DEFS: Tuple[Tuple[str, str], ...] = (
    ("flag_tb", "TRIPLE_BOTTOM_REQUIRED"),
    ("flag_structure", "Structure>=3"),
    ("flag_energy", "Energy>=3"),
    ("flag_money_flow", "MoneyFlow>=4"),
    ("flag_divergence", "Bullish_OBV_Div"),
    ("flag_price_ma480", "price<MA480"),
    ("flag_ma120_slope", "MA120_slope>0"),
)

FORWARD_HORIZONS = (20, 40, 80)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "success", "return_pct", "quality_score",
    "flag_tb", "flag_structure", "flag_energy", "flag_money_flow",
    "flag_divergence", "flag_price_ma480", "flag_ma120_slope",
    "structure_score", "energy_score", "money_flow_score",
    "wave_state", "branch", "path", "combo_label",
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
    """wave_*_{symbol}_{tf}.csv 쌍을 합친다."""
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
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _load_csv_source(canonical: str, fallbacks: Tuple[str, ...], paired_prefix: Optional[str] = None) -> pd.DataFrame:
    path = _resolve_csv(canonical, fallbacks)
    if path:
        return pd.read_csv(path, parse_dates=["timestamp"])
    if paired_prefix:
        return _load_paired_csv(paired_prefix)
    return pd.DataFrame()


def _wave_matches(row: pd.Series, wave: str) -> bool:
    ws = str(row.get("wave_state", ""))
    br = str(row.get("branch", ""))
    path = str(row.get("path", ""))
    return ws == wave or br == wave or wave in path


def _is_bullish_div(val) -> bool:
    if pd.isna(val):
        return False
    s = str(val).strip().upper()
    return s in ("BULLISH_OBV_DIV", "TRUE", "1", "YES")


def _price_below_ma480(row: pd.Series) -> bool:
    if "price_below_ma480" in row.index and pd.notna(row.get("price_below_ma480")):
        return bool(row["price_below_ma480"])
    pvm = row.get("price_vs_ma480")
    if pd.notna(pvm):
        return float(pvm) < 0
    return False


def compute_quality_flags(row: pd.Series) -> dict:
    """품질 점수 구성요소 (각 1점)."""
    structure = int(row.get("structure_score", 0) or 0)
    energy = int(row.get("energy_score", 0) or 0)
    money_flow = int(row.get("money_flow_score", 0) or 0)
    ma120 = row.get("ma120_slope")
    flags = {
        "flag_tb": _wave_matches(row, "TRIPLE_BOTTOM_REQUIRED"),
        "flag_structure": structure >= STRUCTURE_MIN,
        "flag_energy": energy >= ENERGY_MIN,
        "flag_money_flow": money_flow >= MONEY_FLOW_MIN,
        "flag_divergence": _is_bullish_div(row.get("bullish_div")),
        "flag_price_ma480": _price_below_ma480(row),
        "flag_ma120_slope": bool(pd.notna(ma120) and float(ma120) > 0),
    }
    flags["quality_score"] = int(sum(flags.values()))
    return flags


def combo_label_from_flags(flags: dict) -> str:
    parts = [label for key, label in FEATURE_DEFS if flags.get(key)]
    return " + ".join(parts) if parts else "(none)"


def _merge_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    return out


def build_quality_events() -> pd.DataFrame:
    """기존 CSV 병합 후 Quality Score 산출."""
    struct = _load_csv_source("wave_structure_confirmation.csv", ())
    if struct.empty:
        return pd.DataFrame()

    struct = _merge_key(struct)
    lte = _merge_key(_load_csv_source("wave_structure_lte.csv", ()))
    energy = _merge_key(_load_csv_source("wave_energy.csv", ("wave_volume_energy.csv",)))
    div = _merge_key(_load_csv_source("wave_divergence.csv", ("wave_energy_divergence.csv",)))
    mf = _merge_key(_load_csv_source("wave_money_flow.csv", ()))
    seg = _merge_key(_load_csv_source("wave_segmentation.csv", (), "wave_segmentation"))
    exp = _merge_key(_load_csv_source("wave_expectancy.csv", (), "wave_expectancy"))

    base = struct.copy()
    key = ["timestamp", "symbol"]

    if not lte.empty:
        lte_cols = [c for c in lte.columns if c not in base.columns or c in key]
        base = base.merge(lte[lte_cols], on=key, how="left", suffixes=("", "_lte"))

    if not energy.empty:
        ec = [c for c in ("timeframe", "energy_score", "vol_ratio_20", "obv_slope_5") if c in energy.columns]
        base = base.merge(energy[key + ec], on=key, how="left", suffixes=("", "_en"))

    if not div.empty:
        dc = [c for c in ("bullish_div", "bearish_div", "div_strength", "price_ll", "obv_hl") if c in div.columns]
        base = base.merge(div[key + dc], on=key, how="left", suffixes=("", "_div"))

    if not mf.empty:
        mc = [c for c in ("money_flow_score", "mfi", "cmf") if c in mf.columns]
        base = base.merge(mf[key + mc], on=key, how="left", suffixes=("", "_mf"))

    if not seg.empty:
        sc = [c for c in (
            "survival_bucket", "strong_failure", "strong_success", "verdict", "family",
        ) if c in seg.columns]
        base = base.merge(seg[key + sc], on=key, how="left", suffixes=("", "_seg"))

    if not exp.empty:
        ec = [c for c in ("expectancy_group", "survival_bucket") if c in exp.columns]
        base = base.merge(exp[key + ec], on=key, how="left", suffixes=("", "_exp"))

    # timeframe 보강
    if "timeframe" not in base.columns or base["timeframe"].isna().all():
        base["timeframe"] = base["symbol"].map(
            {"ETHUSDT": "4h", "BTCUSDT": "1d", "SOLUSDT": "1h", "BNBUSDT": "4h"},
        ).fillna("4h")

    # forward return (기존 outcome CSV — 재계산 없음)
    outcome_parts = []
    for sym, tf in SYMBOL_TF_PAIRS:
        op = os.path.join(_validation_dir(), f"wave_outcome_{sym}_{tf}.csv")
        if not os.path.isfile(op):
            continue
        odf = pd.read_csv(op, parse_dates=["timestamp"])
        odf["symbol"] = sym
        outcome_parts.append(odf)
    if outcome_parts:
        outcome = pd.concat(outcome_parts, ignore_index=True)
        oc = ["timestamp", "symbol"] + [f"return_{h}" for h in FORWARD_HORIZONS]
        oc += [c for c in ("survival_bars",) if c in outcome.columns]
        base = base.merge(outcome[[c for c in oc if c in outcome.columns]], on=key, how="left")

    rows: List[dict] = []
    for _, row in base.iterrows():
        flags = compute_quality_flags(row)
        rec = {
            "timestamp": row["timestamp"],
            "symbol": row["symbol"],
            "timeframe": str(row.get("timeframe", "4h")),
            "success": bool(row.get("success", False)),
            "return_pct": float(row.get("return_pct", 0)),
            "structure_score": int(row.get("structure_score", 0) or 0),
            "energy_score": int(row.get("energy_score", 0) or 0),
            "money_flow_score": int(row.get("money_flow_score", 0) or 0),
            "wave_state": str(row.get("wave_state", "")),
            "branch": str(row.get("branch", "")),
            "path": str(row.get("path", "")),
            "survival_bucket": row.get("survival_bucket"),
            "strong_failure": row.get("strong_failure"),
            **flags,
        }
        rec["combo_label"] = combo_label_from_flags(flags)
        for h in FORWARD_HORIZONS:
            col = f"return_{h}"
            if col in row.index:
                rec[col] = row[col]
        if "survival_bars" in row.index:
            rec["survival_bars"] = row["survival_bars"]
        rows.append(rec)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _metrics_row(label: str, sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"combo": label, "n": 0, "win_rate": None, "expectancy": None, "profit_factor": None}
    m = compute_expectancy_metrics(sub["return_pct"])
    return {
        "combo": label,
        "n": m.get("n", 0),
        "win_rate": m.get("win_rate"),
        "expectancy": m.get("expectancy"),
        "profit_factor": m.get("profit_factor"),
    }


def score_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(MAX_SCORE + 1):
        sub = df[df["quality_score"] == score]
        row = _metrics_row(f"score={score}", sub)
        row["score"] = score
        row["count"] = row["n"]
        rows.append(row)
    return rows


def cumulative_score_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for threshold in range(1, MAX_SCORE + 1):
        sub = df[df["quality_score"] >= threshold]
        row = _metrics_row(f"score>={threshold}", sub)
        row["threshold"] = threshold
        rows.append(row)
    return rows


def combination_performance(df: pd.DataFrame, min_n: int = MIN_COMBO_N) -> List[dict]:
    if df.empty:
        return []
    rows = []
    for label, sub in df.groupby("combo_label"):
        if label == "(none)":
            continue
        m = _metrics_row(str(label), sub)
        if m["n"] >= min_n:
            rows.append(m)
    return sorted(rows, key=lambda x: (x.get("expectancy") or -999), reverse=True)


def top_combinations(df: pd.DataFrame, n: int = 20) -> List[dict]:
    return combination_performance(df)[:n]


def worst_combinations(df: pd.DataFrame, n: int = 20) -> List[dict]:
    combos = combination_performance(df)
    return list(reversed(combos[-n:])) if combos else []


def failure_rate_by_score(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(MAX_SCORE + 1):
        sub = df[df["quality_score"] == score]
        if sub.empty:
            continue
        fail = (~sub["success"]).mean()
        strong = sub["strong_failure"].astype(bool).mean() if "strong_failure" in sub.columns else None
        rows.append({
            "quality_score": score,
            "n": len(sub),
            "failure_rate": float(fail) * 100.0,
            "strong_failure_rate": float(strong) * 100.0 if strong is not None and pd.notna(strong) else None,
        })
    return rows


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
    if s.endswith("+"):
        try:
            return float(s.rstrip("+")) + 5
        except ValueError:
            return None
    return None


def survival_by_score(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(MAX_SCORE + 1):
        sub = df[df["quality_score"] == score]
        if sub.empty:
            continue
        surv_bars = sub["survival_bars"].dropna().astype(float) if "survival_bars" in sub.columns else pd.Series(dtype=float)
        bucket_col = sub["survival_bucket"].dropna() if "survival_bucket" in sub.columns else pd.Series(dtype=object)
        mids = [_bucket_midpoint(b) for b in bucket_col]
        mids = [m for m in mids if m is not None]
        rows.append({
            "quality_score": score,
            "n": len(sub),
            "avg_survival_bars": float(surv_bars.mean()) if len(surv_bars) else None,
            "avg_survival_bucket_mid": float(np.mean(mids)) if mids else None,
        })
    return rows


def forward_return_by_score(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(MAX_SCORE + 1):
        sub = df[df["quality_score"] == score]
        if sub.empty:
            continue
        row: dict = {"quality_score": score, "n": len(sub)}
        for h in FORWARD_HORIZONS:
            col = f"return_{h}"
            if col not in sub.columns:
                row[f"avg_return_{h}"] = None
                continue
            vals = sub[col].dropna().astype(float)
            row[f"avg_return_{h}"] = float(vals.mean()) * 100.0 if len(vals) else None
            row[f"n_return_{h}"] = int(len(vals))
        rows.append(row)
    return rows


def check_score_monotonicity(score_perf: List[dict]) -> dict:
    """Score 0→7 win_rate / expectancy / PF 단조 증가 여부."""
    by_score = {r["score"]: r for r in score_perf if r.get("n", 0) > 0}
    scores = sorted(by_score.keys())
    metrics = ("win_rate", "expectancy", "profit_factor")
    details = {}
    all_pass = True
    for metric in metrics:
        vals = []
        for s in scores:
            v = by_score[s].get(metric)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                vals.append(None)
            else:
                vals.append(float(v))
        ok = all(
            vals[i] is not None and vals[i + 1] is not None and vals[i] <= vals[i + 1]
            for i in range(len(vals) - 1)
        )
        details[metric] = {"values": dict(zip(scores, vals)), "pass": ok}
        if not ok:
            all_pass = False
    return {"pass": all_pass, "result": "PASS" if all_pass else "FAIL", "details": details}


def feature_importance(df: pd.DataFrame) -> List[dict]:
    """각 플래그 ON/OFF expectancy 차이로 기여도 추정."""
    rows = []
    for key, label in FEATURE_DEFS:
        if key not in df.columns:
            continue
        on = df[df[key].astype(bool)]
        off = df[~df[key].astype(bool)]
        m_on = compute_expectancy_metrics(on["return_pct"]) if len(on) else {"expectancy": None, "n": 0}
        m_off = compute_expectancy_metrics(off["return_pct"]) if len(off) else {"expectancy": None, "n": 0}
        exp_on = m_on.get("expectancy")
        exp_off = m_off.get("expectancy")
        delta = None
        if exp_on is not None and exp_off is not None:
            delta = float(exp_on) - float(exp_off)
        rows.append({
            "feature": label,
            "n_on": m_on.get("n", 0),
            "n_off": m_off.get("n", 0),
            "expectancy_on": exp_on,
            "expectancy_off": exp_off,
            "delta_expectancy": delta,
            "importance": abs(delta) if delta is not None else 0.0,
        })
    return sorted(rows, key=lambda x: x.get("importance") or 0, reverse=True)


def symbol_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in ("ETHUSDT", "BTCUSDT"):
        sub = df[df["symbol"] == sym]
        if sub.empty:
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "symbol": sym,
            "n": m.get("n", 0),
            "avg_quality_score": float(sub["quality_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
        })
    return rows


def timeframe_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for tf in ("4h", "1d"):
        sub = df[df["timeframe"] == tf]
        if sub.empty:
            continue
        m = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "timeframe": tf,
            "n": m.get("n", 0),
            "avg_quality_score": float(sub["quality_score"].mean()),
            "win_rate": m.get("win_rate"),
            "expectancy": m.get("expectancy"),
        })
    return rows


def score_threshold_comparison(df: pd.DataFrame, threshold: int = 5) -> dict:
    high = df[df["quality_score"] >= threshold]
    low = df[df["quality_score"] < threshold]
    return {
        "threshold": threshold,
        "high": _metrics_row(f"score>={threshold}", high),
        "low": _metrics_row(f"score<{threshold}", low),
    }


def practical_minimum_combo(df: pd.DataFrame, min_n: int = 3) -> dict:
    """실전 최소 조건 — expectancy 최대·표본 충분 조합."""
    candidates = [
        c for c in combination_performance(df, min_n=min_n)
        if c.get("expectancy") is not None and c.get("n", 0) >= min_n
    ]
    if not candidates:
        # 고정 후보 탐색
        presets = [
            ("TB + Structure>=3 + MoneyFlow>=4",
             df["flag_tb"] & df["flag_structure"] & df["flag_money_flow"]),
            ("TB + Structure>=3",
             df["flag_tb"] & df["flag_structure"]),
            ("Structure>=3 + MoneyFlow>=4",
             df["flag_structure"] & df["flag_money_flow"]),
            ("TB + MoneyFlow>=4",
             df["flag_tb"] & df["flag_money_flow"]),
        ]
        best = None
        for label, mask in presets:
            m = _metrics_row(label, df[mask])
            if m["n"] >= min_n and (best is None or (m.get("expectancy") or -999) > (best.get("expectancy") or -999)):
                best = m
        return best or {}
    return candidates[0]


def theory_evaluation(
    score_perf: List[dict],
    importance: List[dict],
    mono: dict,
    score5: dict,
) -> dict:
    """레이어별 이론 지지 여부 요약."""
    layers = {
        "Wave (TB)": next((r for r in importance if r["feature"] == "TRIPLE_BOTTOM_REQUIRED"), {}),
        "Structure": next((r for r in importance if r["feature"] == "Structure>=3"), {}),
        "Energy": next((r for r in importance if r["feature"] == "Energy>=3"), {}),
        "Money Flow": next((r for r in importance if r["feature"] == "MoneyFlow>=4"), {}),
        "Divergence": next((r for r in importance if r["feature"] == "Bullish_OBV_Div"), {}),
        "LTE (MA480)": next((r for r in importance if r["feature"] == "price<MA480"), {}),
        "LTE (MA120 slope)": next((r for r in importance if r["feature"] == "MA120_slope>0"), {}),
    }
    supported = []
    weak = []
    for name, row in layers.items():
        d = row.get("delta_expectancy")
        if d is not None and d > 0:
            supported.append(name)
        elif d is not None and d <= 0:
            weak.append(name)
    high = score5.get("high", {})
    return {
        "monotonicity": mono.get("result", "FAIL"),
        "score5_significant": (
            high.get("n", 0) >= 3
            and high.get("expectancy") is not None
            and high.get("expectancy", 0) > 0
        ),
        "supported_layers": supported,
        "weak_layers": weak,
        "overall": (
            "PARTIAL"
            if mono.get("result") == "FAIL" and supported
            else ("SUPPORTED" if mono.get("result") == "PASS" else "WEAK")
        ),
    }


def build_quality_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    return df[cols].copy()


def full_quality_summary() -> dict:
    df = build_quality_events()
    sp = score_performance(df)
    return {
        "dataframe": build_quality_csv(df),
        "raw": df,
        "event_count": len(df),
        "score_performance": sp,
        "cumulative_performance": cumulative_score_performance(df),
        "top_combinations": top_combinations(df),
        "worst_combinations": worst_combinations(df),
        "failure_rate_by_score": failure_rate_by_score(df),
        "survival_by_score": survival_by_score(df),
        "forward_return_by_score": forward_return_by_score(df),
        "monotonicity": check_score_monotonicity(sp),
        "feature_importance": feature_importance(df),
        "symbol_comparison": symbol_comparison(df),
        "timeframe_comparison": timeframe_comparison(df),
        "score5_comparison": score_threshold_comparison(df, 5),
        "practical_minimum": practical_minimum_combo(df),
        "theory_evaluation": theory_evaluation(
            sp,
            feature_importance(df),
            check_score_monotonicity(sp),
            score_threshold_comparison(df, 5),
        ),
    }
