"""Wave Volume Energy — 거래량 기반 에너지 레이어 관측.

Exit/Expectancy/Path/Branch/Confluence/Grading 산출물 + OHLCV만 소비. 신호·엔진 변경 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_branch_analysis import BRANCH_REQUIRED, effect_size
from analysis.wave_expectancy import build_expectancy, compute_expectancy_metrics
from analysis.wave_exit import POLICY_A
from analysis.wave_generalization import GENERALIZATION_SYMBOLS, GENERALIZATION_TIMEFRAMES
from analysis.wave_outcome import _find_bar_index
from analysis.wave_rule_grading import events_for_grade

TIMING_OFFSETS = (-10, -5, 0, 5, 10)

VOLUME_COMPARE_FEATURES = (
    "volume", "vol_ratio_20", "vol_ratio_60",
    "vol_slope_3", "vol_slope_5", "vol_slope_10",
    "vol_percentile_20", "vol_percentile_60",
    "obv", "obv_slope_3", "obv_slope_5", "obv_slope_10",
    "energy_score",
)

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "success", "return_pct",
    "volume", "vol_ratio_20", "vol_ratio_60", "vol_slope_5",
    "vol_percentile_60", "obv", "obv_slope_5", "obv_above_ma20",
    "energy_score", "wave_state", "branch", "path",
)

WAVE_ENERGY_COMBOS = (
    ("TRIPLE_BOTTOM_REQUIRED", "energy_score>=3"),
    ("TRIPLE_BOTTOM_REQUIRED", "vol_ratio_20>1.2"),
    ("TRIPLE_BOTTOM_REQUIRED", "obv_slope_5>0"),
    ("GRADE_A", "energy_score>=3"),
    ("GRADE_A", "obv_slope_5>0"),
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _csv_path(name: str, symbol: str, interval: str) -> str:
    return os.path.join(_validation_dir(), f"{name}_{symbol}_{interval}.csv")


def _load_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    from data.binance import get_auto_limit
    from display.asof import fetch_ohlcv_bare

    lim = 1600 if timeframe == "4h" else get_auto_limit(timeframe)
    bare = fetch_ohlcv_bare(symbol, timeframe, lim, paginated=lim > 1000)
    if bare is None or bare.empty or "volume" not in bare.columns:
        return pd.DataFrame()
    return bare


def compute_vol_ma(volume: pd.Series, window: int) -> pd.Series:
    return volume.rolling(window, min_periods=1).mean()


def compute_vol_ratio(volume: pd.Series, vol_ma: pd.Series) -> pd.Series:
    return volume / vol_ma.replace(0, np.nan)


def compute_vol_slope(volume: pd.Series, n: int) -> pd.Series:
    return volume - volume.shift(n)


def compute_vol_percentile(volume: pd.Series, window: int) -> pd.Series:
    def _pct(x):
        if len(x) < 2:
            return np.nan
        return float(pd.Series(x).rank(pct=True).iloc[-1] * 100.0)

    return volume.rolling(window, min_periods=2).apply(_pct, raw=False)


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def compute_obv_slope(obv: pd.Series, n: int) -> pd.Series:
    return obv - obv.shift(n)


def obv_divergence_candidate(close: pd.Series, obv: pd.Series, pos: int, lookback: int = 20) -> bool:
    """가격 신저점 + OBV 미신저점 (관측용)."""
    if pos < lookback or pos >= len(close):
        return False
    prev_price_low = float(close.iloc[pos - lookback:pos].min())
    prev_obv_low = float(obv.iloc[pos - lookback:pos].min())
    price_new_low = float(close.iloc[pos]) < prev_price_low
    obv_higher_low = float(obv.iloc[pos]) > prev_obv_low
    return price_new_low and obv_higher_low


def add_volume_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """OHLCV에 volume energy feature 컬럼 추가."""
    if ohlcv is None or ohlcv.empty or "volume" not in ohlcv.columns:
        return pd.DataFrame()
    out = ohlcv.copy()
    vol = out["volume"].astype(float)
    close = out["close"].astype(float)

    out["vol_ma_20"] = compute_vol_ma(vol, 20)
    out["vol_ma_60"] = compute_vol_ma(vol, 60)
    out["vol_ratio_20"] = compute_vol_ratio(vol, out["vol_ma_20"])
    out["vol_ratio_60"] = compute_vol_ratio(vol, out["vol_ma_60"])
    out["vol_slope_3"] = compute_vol_slope(vol, 3)
    out["vol_slope_5"] = compute_vol_slope(vol, 5)
    out["vol_slope_10"] = compute_vol_slope(vol, 10)
    out["vol_percentile_20"] = compute_vol_percentile(vol, 20)
    out["vol_percentile_60"] = compute_vol_percentile(vol, 60)

    out["obv"] = compute_obv(close, vol)
    out["obv_ma_20"] = compute_vol_ma(out["obv"], 20)
    out["obv_slope_3"] = compute_obv_slope(out["obv"], 3)
    out["obv_slope_5"] = compute_obv_slope(out["obv"], 5)
    out["obv_slope_10"] = compute_obv_slope(out["obv"], 10)
    out["obv_above_ma20"] = out["obv"] > out["obv_ma_20"]

    return out


def extract_volume_at(df: pd.DataFrame, pos: int) -> dict:
    """단일 봉 volume feature 추출."""
    if pos < 0 or pos >= len(df):
        return {}
    row = df.iloc[pos]
    feats = {
        "volume": float(row["volume"]) if pd.notna(row.get("volume")) else None,
        "vol_ma_20": float(row["vol_ma_20"]) if pd.notna(row.get("vol_ma_20")) else None,
        "vol_ma_60": float(row["vol_ma_60"]) if pd.notna(row.get("vol_ma_60")) else None,
        "vol_ratio_20": float(row["vol_ratio_20"]) if pd.notna(row.get("vol_ratio_20")) else None,
        "vol_ratio_60": float(row["vol_ratio_60"]) if pd.notna(row.get("vol_ratio_60")) else None,
        "vol_slope_3": float(row["vol_slope_3"]) if pd.notna(row.get("vol_slope_3")) else None,
        "vol_slope_5": float(row["vol_slope_5"]) if pd.notna(row.get("vol_slope_5")) else None,
        "vol_slope_10": float(row["vol_slope_10"]) if pd.notna(row.get("vol_slope_10")) else None,
        "vol_percentile_20": float(row["vol_percentile_20"]) if pd.notna(row.get("vol_percentile_20")) else None,
        "vol_percentile_60": float(row["vol_percentile_60"]) if pd.notna(row.get("vol_percentile_60")) else None,
        "obv": float(row["obv"]) if pd.notna(row.get("obv")) else None,
        "obv_slope_3": float(row["obv_slope_3"]) if pd.notna(row.get("obv_slope_3")) else None,
        "obv_slope_5": float(row["obv_slope_5"]) if pd.notna(row.get("obv_slope_5")) else None,
        "obv_slope_10": float(row["obv_slope_10"]) if pd.notna(row.get("obv_slope_10")) else None,
        "obv_above_ma20": bool(row["obv_above_ma20"]) if pd.notna(row.get("obv_above_ma20")) else False,
        "obv_divergence": obv_divergence_candidate(df["close"], df["obv"], pos),
    }
    feats["energy_score"] = compute_energy_score(feats)
    return feats


def compute_energy_score(feats: dict) -> int:
    """관측용 Energy Score 0~5 (실전 신호 금지)."""
    score = 0
    vr20 = feats.get("vol_ratio_20")
    if vr20 is not None and vr20 > 1.2:
        score += 1
    vs5 = feats.get("vol_slope_5")
    if vs5 is not None and vs5 > 0:
        score += 1
    os5 = feats.get("obv_slope_5")
    if os5 is not None and os5 > 0:
        score += 1
    if feats.get("obv_above_ma20"):
        score += 1
    vp60 = feats.get("vol_percentile_60")
    if vp60 is not None and vp60 >= 60:
        score += 1
    return score


def _load_optional_csv(name: str, symbol: str, interval: str) -> pd.DataFrame:
    path = _csv_path(name, symbol, interval)
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def _grade_a_keys() -> set:
    ev = events_for_grade("A")
    if ev.empty:
        return set()
    return {
        (str(r["symbol"]), str(r["timeframe"]), pd.Timestamp(r["timestamp"]))
        for _, r in ev.iterrows()
    }


def build_cell_volume_events(symbol: str, interval: str, grade_a_keys: set) -> pd.DataFrame:
    """단일 셀 TP3 기준 에피소드 + volume feature."""
    exp = build_expectancy(symbol, interval)
    if exp.empty:
        return pd.DataFrame()

    exit_df = _load_optional_csv("wave_exit", symbol, interval)
    if not exit_df.empty:
        tp3 = exit_df[exit_df["policy"] == POLICY_A].copy()
        if not tp3.empty:
            tp3 = tp3.rename(columns={"return_pct": "exit_return_pct"})
            exp = exp.merge(
                tp3[["timestamp", "exit_return_pct"]],
                on="timestamp", how="left",
            )
            if "exit_return_pct" in exp.columns:
                exp["return_pct"] = exp["exit_return_pct"].fillna(exp["return_pct"])

    exp["success"] = exp["return_pct"] > 0

    branch = _load_optional_csv("wave_branch", symbol, interval)
    paths = _load_optional_csv("wave_paths", symbol, interval)
    conf = _load_optional_csv("wave_confluence", symbol, interval)

    if not branch.empty:
        exp = exp.merge(
            branch[["timestamp", "branch"]],
            on="timestamp", how="left",
        )
    if not paths.empty:
        exp = exp.merge(
            paths[["timestamp", "path"]],
            on="timestamp", how="left",
        )
    if not conf.empty and "branch_label" in conf.columns:
        exp = exp.merge(
            conf[["timestamp", "branch_label"]],
            on="timestamp", how="left",
        )

    ohlcv = _load_ohlcv(symbol, interval)
    if ohlcv.empty:
        return pd.DataFrame()
    vol_df = add_volume_features(ohlcv)

    rows: List[dict] = []
    for _, ev in exp.iterrows():
        ts = pd.Timestamp(ev["timestamp"])
        bar_idx = _find_bar_index(vol_df, ts)
        if bar_idx is None:
            continue
        feats = extract_volume_at(vol_df, bar_idx)
        if not feats:
            continue

        wave_state = str(ev.get("state", ""))
        branch_val = str(ev.get("branch", ev.get("branch_label", "")))
        is_tb = (
            wave_state == BRANCH_REQUIRED
            or branch_val == BRANCH_REQUIRED
            or str(ev.get("branch_label", "")) == BRANCH_REQUIRED
        )
        is_grade_a = (symbol, interval, ts) in grade_a_keys

        rows.append({
            "timestamp": ts,
            "symbol": symbol,
            "timeframe": interval,
            "success": bool(ev["success"]),
            "return_pct": float(ev["return_pct"]),
            "wave_state": wave_state,
            "branch": branch_val,
            "path": str(ev.get("path", "")),
            "is_triple_bottom": is_tb,
            "is_grade_a": is_grade_a,
            **feats,
        })

    return pd.DataFrame(rows)


def build_volume_energy_events(cache: Optional[Dict] = None) -> pd.DataFrame:
    grade_a_keys = _grade_a_keys()
    parts: List[pd.DataFrame] = []
    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            cell = build_cell_volume_events(sym, tf, grade_a_keys)
            if not cell.empty:
                parts.append(cell)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def success_failure_compare(df: pd.DataFrame) -> List[dict]:
    """Feature별 성공/실패 평균 및 effect size."""
    if df.empty:
        return []
    succ = df[df["success"]]
    fail = df[~df["success"]]
    rows = []
    for feat in VOLUME_COMPARE_FEATURES:
        if feat not in df.columns:
            continue
        s_vals = succ[feat].dropna().astype(float)
        f_vals = fail[feat].dropna().astype(float)
        if s_vals.empty and f_vals.empty:
            continue
        rows.append({
            "feature": feat,
            "success_mean": float(s_vals.mean()) if len(s_vals) else None,
            "failure_mean": float(f_vals.mean()) if len(f_vals) else None,
            "effect_size": effect_size(s_vals, f_vals) if len(s_vals) >= 2 and len(f_vals) >= 2 else None,
        })
    return sorted(rows, key=lambda x: x.get("effect_size") or 0, reverse=True)


def top_volume_separators(compare_rows: List[dict], top_n: int = 10) -> List[dict]:
    return compare_rows[:top_n]


def energy_score_performance(df: pd.DataFrame) -> List[dict]:
    rows = []
    for score in range(6):
        sub = df[df["energy_score"] == score]
        if sub.empty:
            rows.append({
                "score": score, "n": 0, "win_rate": None,
                "expectancy": None, "profit_factor": None, "avg_return": None,
            })
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "score": score,
            "n": metrics.get("n", 0),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "profit_factor": metrics.get("profit_factor"),
            "avg_return": metrics.get("avg_return"),
        })
    return rows


def _combo_mask(df: pd.DataFrame, cohort: str, condition: str) -> pd.Series:
    if cohort == "TRIPLE_BOTTOM_REQUIRED":
        base = df["is_triple_bottom"] == True  # noqa: E712
    elif cohort == "GRADE_A":
        base = df["is_grade_a"] == True  # noqa: E712
    else:
        base = pd.Series(False, index=df.index)

    if condition == "energy_score>=3":
        cond = df["energy_score"] >= 3
    elif condition == "vol_ratio_20>1.2":
        cond = df["vol_ratio_20"] > 1.2
    elif condition == "obv_slope_5>0":
        cond = df["obv_slope_5"] > 0
    else:
        cond = pd.Series(False, index=df.index)

    return base & cond


def wave_energy_combos(df: pd.DataFrame) -> List[dict]:
    rows = []
    for cohort, condition in WAVE_ENERGY_COMBOS:
        mask = _combo_mask(df, cohort, condition)
        sub = df[mask]
        label = f"{cohort} + {condition}"
        if sub.empty:
            rows.append({
                "combo": label, "n": 0, "win_rate": None,
                "expectancy": None, "profit_factor": None,
            })
            continue
        metrics = compute_expectancy_metrics(sub["return_pct"])
        rows.append({
            "combo": label,
            "n": metrics.get("n", 0),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "profit_factor": metrics.get("profit_factor"),
        })
    return rows


def volume_event_timing(df: pd.DataFrame, ohlcv_cache: Dict) -> Tuple[List[dict], List[dict]]:
    """offset별 vol_ratio / obv_slope — 성공 vs 실패."""
    succ_offsets: Dict[int, List[dict]] = {o: [] for o in TIMING_OFFSETS}
    fail_offsets: Dict[int, List[dict]] = {o: [] for o in TIMING_OFFSETS}

    for _, ev in df.iterrows():
        sym, tf = str(ev["symbol"]), str(ev["timeframe"])
        key = (sym, tf)
        if key not in ohlcv_cache:
            bare = _load_ohlcv(sym, tf)
            ohlcv_cache[key] = add_volume_features(bare) if not bare.empty else pd.DataFrame()
        vol_df = ohlcv_cache[key]
        if vol_df.empty:
            continue
        bar_idx = _find_bar_index(vol_df, pd.Timestamp(ev["timestamp"]))
        if bar_idx is None:
            continue
        target = succ_offsets if ev["success"] else fail_offsets
        for offset in TIMING_OFFSETS:
            pos = bar_idx + offset
            if pos < 0 or pos >= len(vol_df):
                continue
            row = vol_df.iloc[pos]
            target[offset].append({
                "vol_ratio_20": float(row["vol_ratio_20"]) if pd.notna(row.get("vol_ratio_20")) else None,
                "obv_slope_5": float(row["obv_slope_5"]) if pd.notna(row.get("obv_slope_5")) else None,
            })

    def _summarize(offset_dict: Dict) -> List[dict]:
        rows = []
        for offset in TIMING_OFFSETS:
            pts = offset_dict[offset]
            if not pts:
                rows.append({"offset": offset, "vol_ratio_20": None, "obv_slope_5": None, "n": 0})
                continue
            vr = [p["vol_ratio_20"] for p in pts if p["vol_ratio_20"] is not None]
            os5 = [p["obv_slope_5"] for p in pts if p["obv_slope_5"] is not None]
            rows.append({
                "offset": offset,
                "vol_ratio_20": float(np.mean(vr)) if vr else None,
                "obv_slope_5": float(np.mean(os5)) if os5 else None,
                "n": len(pts),
            })
        return rows

    return _summarize(succ_offsets), _summarize(fail_offsets)


def failure_reclassification(df: pd.DataFrame) -> List[dict]:
    """실패 사례 중 거래량 에너지 부족 비율."""
    fails = df[~df["success"]]
    if fails.empty:
        return []
    total = len(fails)

    def _energy_deficient(row) -> bool:
        es = row.get("energy_score", 0)
        vr = row.get("vol_ratio_20")
        os5 = row.get("obv_slope_5")
        if es is not None and es <= 1:
            return True
        if vr is not None and vr < 1.0:
            return True
        if os5 is not None and os5 <= 0:
            return True
        return False

    energy_low = fails.apply(_energy_deficient, axis=1)
    low_score = fails["energy_score"] <= 1
    low_ratio = fails["vol_ratio_20"] < 1.0
    weak_obv = fails["obv_slope_5"] <= 0

    return [
        {"failure_cause": "ENERGY_DEFICIENT (any)", "count": int(energy_low.sum()),
         "pct": float(energy_low.sum()) / total * 100.0},
        {"failure_cause": "Energy Score <= 1", "count": int(low_score.sum()),
         "pct": float(low_score.sum()) / total * 100.0},
        {"failure_cause": "vol_ratio_20 < 1", "count": int(low_ratio.sum()),
         "pct": float(low_ratio.sum()) / total * 100.0},
        {"failure_cause": "OBV slope 5 <= 0", "count": int(weak_obv.sum()),
         "pct": float(weak_obv.sum()) / total * 100.0},
        {"failure_cause": "OTHER", "count": int((~energy_low).sum()),
         "pct": float((~energy_low).sum()) / total * 100.0},
    ]


def symbol_tf_comparison(df: pd.DataFrame) -> List[dict]:
    rows = []
    for sym in GENERALIZATION_SYMBOLS:
        for tf in GENERALIZATION_TIMEFRAMES:
            sub = df[(df["symbol"] == sym) & (df["timeframe"] == tf)]
            if sub.empty:
                continue
            metrics = compute_expectancy_metrics(sub["return_pct"])
            rows.append({
                "symbol": sym,
                "timeframe": tf,
                "energy_score_avg": float(sub["energy_score"].mean()),
                "expectancy": metrics.get("expectancy"),
                "win_rate": metrics.get("win_rate"),
                "n": metrics.get("n", 0),
            })
    return rows


def build_volume_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    return df[cols].copy()


def full_volume_energy_summary(cache: Optional[Dict] = None) -> dict:
    cache = cache or {}
    df = build_volume_energy_events(cache)
    compare = success_failure_compare(df)
    ohlcv_cache: Dict = {}
    timing_succ, timing_fail = volume_event_timing(df, ohlcv_cache)

    return {
        "dataframe": build_volume_csv(df),
        "raw": df,
        "event_count": len(df),
        "success_count": int(df["success"].sum()) if not df.empty else 0,
        "failure_count": int((~df["success"]).sum()) if not df.empty else 0,
        "feature_compare": compare,
        "top_separators": top_volume_separators(compare),
        "energy_score_perf": energy_score_performance(df),
        "wave_energy_combos": wave_energy_combos(df),
        "timing_success": timing_succ,
        "timing_failure": timing_fail,
        "failure_reclass": failure_reclassification(df),
        "symbol_tf_comparison": symbol_tf_comparison(df),
    }
