"""Wave HTF Gate — 상위 TF 파동 상태 게이트 (SPEC_WAVE_HTF_GATE R1, 관측 전용).

기존 산출물만 소비한다:
- HTF 상태: engine.get_ma_alignment + wave_tracker.run_timeline (신규 검출기 없음)
- LTF 이벤트: wave_live_forward_journal.csv (신규 이벤트 검출 로직 없음)
- 지표: wave_expectancy.compute_expectancy_metrics / wave_entry_filter_refinement._perf

asof 규칙(§3.4): LTF 이벤트 시각 t 에 대해 close_time < t 인 HTF 봉까지만 사용한다.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.engine import get_ma_alignment
from analysis.wave_entry_filter_refinement import _perf
from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_survival_segmentation import survival_label
from analysis.wave_tracker import (
    DOUBLE_BOTTOM_CANDIDATE,
    TRIPLE_BOTTOM_CONFIRMED,
    WAVE3_COMPLETED,
    run_timeline,
)
from config.settings import WAVE_LAYER_ROLES

# --- 사전 고정 (§3.1) ---
PAIRS: Dict[str, Tuple[str, str]] = {
    "PAIR_A": ("1d", "4h"),
    "PAIR_B": ("4h", "1h"),
}
PAIR_X: Tuple[str, str] = ("1d", "6h")  # 참고 보고 전용, 판정 미사용
SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")

# --- 게이트 정의 (§3.2) ---
G_WAVE_STATES = (DOUBLE_BOTTOM_CANDIDATE, WAVE3_COMPLETED, TRIPLE_BOTTOM_CONFIRMED)
ALIGN_BULLISH_PREFIX = "Bullish Alignment"  # engine.get_ma_alignment 기존 분류 문자열

# --- 트리거 정의 (§3.3) — Filter_C 합집합 Filter_Q (사전 고정) ---
TRIGGER_RULE = "RULE_C"
TRIGGER_QUALITY = 4
TRIGGER_LABEL = "RULE_C OR quality>=4"

# --- 판정 파라미터 (§4.1) ---
MIN_CELL_N = 30
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260903
CI_ALPHA = 0.05
CALIB_THRESHOLD = 0.90

# --- HTF 타임라인 빌드 파라미터 (사전 고정) ---
HTF_FETCH_LIMIT = {"1d": 500, "4h": 1600, "6h": 1000, "1h": 5000}
MA_WARMUP = 240

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]
_LAYER_SMALL = WAVE_LAYER_ROLES["small"]

_INTERVAL_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "3h": 180, "4h": 240, "6h": 360,
    "8h": 480, "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080,
}

GATES = ("NO_GATE", "G_ALIGN", "G_WAVE", "G_BOTH")

CSV_EXPORT_COLS = (
    "pair", "htf", "ltf", "event_id", "timestamp", "symbol", "rule",
    "quality_score", "return_20", "return_40", "survival_label",
    "htf_open_time", "htf_close_time", "htf_state", "htf_alignment",
    "g_align", "g_wave", "g_both",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _cache_dir() -> str:
    path = os.path.join(_validation_dir(), "_htf_gate_cache")
    os.makedirs(path, exist_ok=True)
    return path


def htf_state_path(symbol: str, htf: str) -> str:
    return os.path.join(_cache_dir(), f"htf_state_{symbol}_{htf}.csv")


def interval_delta(interval: str) -> pd.Timedelta:
    """봉 길이. 미지원 interval 은 ValueError."""
    minutes = _INTERVAL_MINUTES.get(interval)
    if minutes is None:
        raise ValueError(f"unsupported interval: {interval}")
    return pd.Timedelta(minutes=minutes)


def close_time_of(open_times, interval: str) -> pd.Series:
    """Binance 규약의 봉 마감 시각 (open_time + 봉길이 - 1ms)."""
    idx = pd.to_datetime(pd.Series(list(open_times)))
    return idx + interval_delta(interval) - pd.Timedelta(milliseconds=1)


def is_bullish_alignment(label) -> bool:
    """G_ALIGN 판정 — 기존 분류 문자열만 사용 (새 분류 없음)."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return False
    return str(label).startswith(ALIGN_BULLISH_PREFIX)


def is_wave_bottom_state(state) -> bool:
    """G_WAVE 판정 — wave_tracker 상태 3종."""
    return str(state) in G_WAVE_STATES


# ---------------------------------------------------------------- HTF 상태
def alignment_timeline(pipe: pd.DataFrame) -> List[str]:
    """봉별 get_ma_alignment (각 봉까지 절단한 프레임의 마지막 봉 기준)."""
    return [get_ma_alignment(pipe.iloc[: i + 1]) for i in range(len(pipe))]


def build_htf_states(
    symbol: str,
    htf: str,
    *,
    warmup: int = MA_WARMUP,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """HTF 닫힌 봉 기준 상태 시계열 (state + alignment + gate 플래그)."""
    from display.asof import build_ohlcv_cache, fetch_ohlcv_bare, run_indicator_pipeline

    lim = limit if limit is not None else HTF_FETCH_LIMIT.get(htf, 500)
    bare = fetch_ohlcv_bare(symbol, htf, lim, paginated=lim > 1000)
    if bare is None or bare.empty:
        raise RuntimeError(f"fetch failed: {symbol} {htf}")
    cache = build_ohlcv_cache(symbol, htf, bare, extra_limits={htf: lim})

    timeline = run_timeline(symbol, htf, bare, cache, warmup=warmup)
    if timeline.empty:
        return pd.DataFrame()

    pipe = run_indicator_pipeline(bare)
    align = pd.Series(alignment_timeline(pipe), index=pipe.index)

    out = timeline.rename(columns={"timestamp": "htf_open_time", "state": "htf_state"})
    out["htf_open_time"] = pd.to_datetime(out["htf_open_time"])
    out["htf_alignment"] = out["htf_open_time"].map(align)
    out["htf_close_time"] = close_time_of(out["htf_open_time"], htf).to_numpy()
    out["symbol"] = symbol
    out["htf"] = htf
    out["g_align"] = out["htf_alignment"].map(is_bullish_alignment)
    out["g_wave"] = out["htf_state"].map(is_wave_bottom_state)
    out["g_both"] = out["g_align"] & out["g_wave"]
    cols = [
        "symbol", "htf", "htf_open_time", "htf_close_time",
        "htf_state", "htf_alignment", "g_align", "g_wave", "g_both",
    ]
    return out[cols].sort_values("htf_close_time").reset_index(drop=True)


def load_htf_states(symbol: str, htf: str, *, build: bool = False) -> pd.DataFrame:
    """캐시된 HTF 상태 시계열. build=True 면 없을 때 새로 만든다(네트워크)."""
    path = htf_state_path(symbol, htf)
    if os.path.isfile(path):
        df = pd.read_csv(path, parse_dates=["htf_open_time", "htf_close_time"])
        for col in ("g_align", "g_wave", "g_both"):
            if col in df.columns and df[col].dtype == object:
                df[col] = df[col].map(lambda x: str(x).lower() in ("true", "1", "yes"))
        return df
    if not build:
        return pd.DataFrame()
    df = build_htf_states(symbol, htf)
    df.to_csv(path, index=False)
    return df


# ------------------------------------------------------------- LTF 이벤트
def load_forward_journal() -> pd.DataFrame:
    path = os.path.join(_validation_dir(), "wave_live_forward_journal.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def trigger_events(
    journal: pd.DataFrame,
    ltf: str,
    symbols: Tuple[str, ...] = SYMBOLS,
) -> pd.DataFrame:
    """§3.3 트리거 — 기존 이벤트 중 RULE_C 또는 quality>=4."""
    if journal.empty:
        return pd.DataFrame()
    sub = journal[
        (journal["timeframe"] == ltf) & (journal["symbol"].isin(symbols))
    ].copy()
    if sub.empty:
        return sub
    mask = (sub["rule"] == TRIGGER_RULE) | (
        sub["quality_score"].astype(float) >= TRIGGER_QUALITY
    )
    out = sub[mask].copy()
    out["survival_label"] = out["return_20"].apply(survival_label)
    return out.sort_values("timestamp").reset_index(drop=True)


# ------------------------------------------------------------------ asof
def attach_htf_gates(events: pd.DataFrame, states: pd.DataFrame, htf: str) -> pd.DataFrame:
    """이벤트 t 에 마감된 HTF 봉 상태 부착 (merge_asof backward, close_time < t)."""
    if events.empty:
        return events
    left = events.sort_values("timestamp").reset_index(drop=True)
    gate_cols = ["htf_open_time", "htf_close_time", "htf_state", "htf_alignment",
                 "g_align", "g_wave", "g_both"]
    if states.empty:
        out = left.copy()
        for col in gate_cols:
            out[col] = pd.NaT if col.endswith("_time") else None
        for col in ("g_align", "g_wave", "g_both"):
            out[col] = False
        out["htf"] = htf
        return out

    right = states.sort_values("htf_close_time").reset_index(drop=True)
    right = right[gate_cols + ["symbol"]]
    parts = []
    for sym, grp in left.groupby("symbol", sort=False):
        rgrp = right[right["symbol"] == sym].drop(columns=["symbol"])
        if rgrp.empty:
            continue
        merged = pd.merge_asof(
            grp.sort_values("timestamp"),
            rgrp,
            left_on="timestamp",
            right_on="htf_close_time",
            direction="backward",
            allow_exact_matches=False,
        )
        parts.append(merged)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    for col in ("g_align", "g_wave", "g_both"):
        out[col] = out[col].map(lambda v: bool(v) if pd.notna(v) else False).astype(bool)
    out["htf"] = htf
    return out.sort_values("timestamp").reset_index(drop=True)


def build_pair_events(
    pair: str,
    journal: Optional[pd.DataFrame] = None,
    *,
    build: bool = False,
) -> pd.DataFrame:
    """TF쌍 하나의 gate 플래그 부착 이벤트."""
    htf, ltf = PAIRS.get(pair, PAIR_X)
    j = load_forward_journal() if journal is None else journal
    events = trigger_events(j, ltf)
    if events.empty:
        return pd.DataFrame()
    frames = [load_htf_states(s, htf, build=build) for s in SYMBOLS]
    frames = [f for f in frames if not f.empty]
    states = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out = attach_htf_gates(events, states, htf)
    if out.empty:
        return out
    out["pair"] = pair
    out["ltf"] = ltf
    return out


# ------------------------------------------------------------------ 지표
def gate_mask(df: pd.DataFrame, gate: str) -> pd.Series:
    if gate == "NO_GATE":
        return pd.Series(True, index=df.index)
    if gate == "G_ALIGN":
        return df["g_align"].astype(bool)
    if gate == "G_WAVE":
        return df["g_wave"].astype(bool)
    if gate == "G_BOTH":
        return df["g_both"].astype(bool)
    raise ValueError(f"unknown gate: {gate}")


def expectancy_20(df: pd.DataFrame) -> Optional[float]:
    """expectancy_20 — compute_expectancy_metrics(return_20) 그대로."""
    if df.empty or "return_20" not in df.columns:
        return None
    rets = df["return_20"].dropna().astype(float)
    if rets.empty:
        return None
    return round(float(compute_expectancy_metrics(rets).get("expectancy", 0.0)), 4)


def gate_table(df: pd.DataFrame, label: str = "") -> List[dict]:
    """무게이트 / G_ALIGN / G_WAVE / G_BOTH 4열 비교 (§4.2)."""
    rows = []
    for gate in GATES:
        sub = df[gate_mask(df, gate)] if not df.empty else df
        perf = _perf(sub) if not sub.empty else {"n": 0}
        rows.append({
            "label": label,
            "gate": gate,
            "n": int(perf.get("n", 0)),
            "n_labeled": int(sub["return_20"].notna().sum()) if not sub.empty else 0,
            "expectancy_20": expectancy_20(sub),
            "profit_factor": perf.get("profit_factor"),
            "survival_rate": perf.get("survival_rate"),
            "win_rate": perf.get("win_rate"),
            "avg_return_20": perf.get("avg_return_20"),
        })
    return rows


def delta_expectancy(df: pd.DataFrame) -> Optional[float]:
    """Δ = E[G_BOTH] − E[G_ALIGN]."""
    if df.empty:
        return None
    e_both = expectancy_20(df[gate_mask(df, "G_BOTH")])
    e_align = expectancy_20(df[gate_mask(df, "G_ALIGN")])
    if e_both is None or e_align is None:
        return None
    return round(e_both - e_align, 4)


def _expectancy_arr(rets: np.ndarray) -> Optional[float]:
    if rets.size == 0:
        return None
    return float(compute_expectancy_metrics(pd.Series(rets)).get("expectancy", 0.0))


def bootstrap_delta(
    df: pd.DataFrame,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """G_ALIGN 코호트를 재표집(G_BOTH 중첩 구조 보존)한 Δ 의 95% CI."""
    point = delta_expectancy(df)
    empty = {"delta": point, "ci_low": None, "ci_high": None, "n_boot": 0,
             "n_align": 0, "n_both": 0}
    if df.empty:
        return empty
    align = df[gate_mask(df, "G_ALIGN")]
    align = align[align["return_20"].notna()].reset_index(drop=True)
    n = len(align)
    if n == 0:
        return empty
    both_flag = align["g_both"].astype(bool).to_numpy()
    rets = align["return_20"].astype(float).to_numpy()
    empty.update({"n_align": n, "n_both": int(both_flag.sum())})
    if both_flag.sum() == 0:
        return empty

    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        r = rets[idx]
        b = both_flag[idx]
        if b.sum() == 0:
            continue
        e_all = _expectancy_arr(r)
        e_both = _expectancy_arr(r[b])
        if e_all is None or e_both is None:
            continue
        deltas.append(e_both - e_all)
    if not deltas:
        return empty
    arr = np.asarray(deltas, dtype=float)
    return {
        "delta": point,
        "ci_low": round(float(np.percentile(arr, CI_ALPHA / 2 * 100)), 4),
        "ci_high": round(float(np.percentile(arr, (1 - CI_ALPHA / 2) * 100)), 4),
        "n_boot": len(arr),
        "n_align": n,
        "n_both": int(both_flag.sum()),
    }


def half_split_deltas(df: pd.DataFrame) -> List[dict]:
    """시계열 전/후 반분 Δ (§4.1-3)."""
    if df.empty:
        return []
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    mid = len(ordered) // 2
    rows = []
    for name, sub in (("first_half", ordered.iloc[:mid]), ("second_half", ordered.iloc[mid:])):
        rows.append({
            "split": name,
            "n": len(sub),
            "ts_min": sub["timestamp"].min() if len(sub) else None,
            "ts_max": sub["timestamp"].max() if len(sub) else None,
            "n_align": int(gate_mask(sub, "G_ALIGN").sum()) if len(sub) else 0,
            "n_both": int(gate_mask(sub, "G_BOTH").sum()) if len(sub) else 0,
            "e_align": expectancy_20(sub[gate_mask(sub, "G_ALIGN")]) if len(sub) else None,
            "e_both": expectancy_20(sub[gate_mask(sub, "G_BOTH")]) if len(sub) else None,
            "delta": delta_expectancy(sub),
        })
    return rows


def symbol_deltas(df: pd.DataFrame) -> List[dict]:
    """심볼별 Δ (§4.1-4)."""
    rows = []
    for sym in SYMBOLS:
        sub = df[df["symbol"] == sym] if not df.empty else df
        rows.append({
            "symbol": sym,
            "n": len(sub),
            "n_align": int(gate_mask(sub, "G_ALIGN").sum()) if len(sub) else 0,
            "n_both": int(gate_mask(sub, "G_BOTH").sum()) if len(sub) else 0,
            "e_align": expectancy_20(sub[gate_mask(sub, "G_ALIGN")]) if len(sub) else None,
            "e_both": expectancy_20(sub[gate_mask(sub, "G_BOTH")]) if len(sub) else None,
            "delta": delta_expectancy(sub),
        })
    return rows


def cell_counts(df: pd.DataFrame) -> List[dict]:
    """셀별 G_BOTH n (§4.1-2). 셀 = TF쌍, 참고로 TF쌍×심볼도 함께 보고."""
    rows = []
    if df.empty or "pair" not in df.columns:
        return rows
    for pair in sorted(df["pair"].dropna().unique()):
        sub = df[df["pair"] == pair]
        rows.append({
            "cell": pair,
            "level": "pair",
            "n_both": int(gate_mask(sub, "G_BOTH").sum()),
            "n_align": int(gate_mask(sub, "G_ALIGN").sum()),
        })
        for sym in SYMBOLS:
            s2 = sub[sub["symbol"] == sym]
            rows.append({
                "cell": f"{pair}|{sym}",
                "level": "pair_symbol",
                "n_both": int(gate_mask(s2, "G_BOTH").sum()) if len(s2) else 0,
                "n_align": int(gate_mask(s2, "G_ALIGN").sum()) if len(s2) else 0,
            })
    return rows


def gate_availability(
    htf: str,
    events: Optional[pd.DataFrame] = None,
    symbols: Tuple[str, ...] = SYMBOLS,
) -> List[dict]:
    """HTF 봉 수준 게이트 가용성 — 게이트가 애초에 열리는지 진단 (판정 미사용).

    events 를 주면 해당 이벤트 관측 창으로 제한한 카운트도 함께 낸다.
    """
    rows: List[dict] = []
    lo = hi = None
    if events is not None and not events.empty:
        lo = pd.Timestamp(events["timestamp"].min()) - interval_delta(htf)
        hi = pd.Timestamp(events["timestamp"].max())
    for sym in symbols:
        st = load_htf_states(sym, htf)
        if st.empty:
            rows.append({"symbol": sym, "htf": htf, "bars": 0})
            continue
        row = {
            "symbol": sym,
            "htf": htf,
            "bars": len(st),
            "bars_align": int(st["g_align"].sum()),
            "bars_wave": int(st["g_wave"].sum()),
            "bars_both": int(st["g_both"].sum()),
            "first_bar": st["htf_open_time"].min(),
            "last_bar": st["htf_open_time"].max(),
        }
        if lo is not None:
            win = st[(st["htf_close_time"] >= lo) & (st["htf_close_time"] <= hi)]
            row.update({
                "win_bars": len(win),
                "win_align": int(win["g_align"].sum()) if len(win) else 0,
                "win_wave": int(win["g_wave"].sum()) if len(win) else 0,
                "win_both": int(win["g_both"].sum()) if len(win) else 0,
                "win_start": lo,
                "win_end": hi,
            })
        rows.append(row)
    return rows


def bnb_core_overlap(df: pd.DataFrame) -> dict:
    """§4.2 — G_BOTH 가 기존 Filter_BNB_CORE 의 대리변수인지 확인.

    Filter_BNB_CORE = BNBUSDT & money_flow_score>=5 & structure_score>=5
    (analysis.wave_robustness_validation.FILTER_DEFS 정의 그대로).
    """
    bnb = df[df["symbol"] == "BNBUSDT"] if not df.empty else df
    if bnb.empty:
        return {"n_bnb": 0}
    core = (
        (bnb["money_flow_score"].astype(float) >= 5)
        & (bnb["structure_score"].astype(float) >= 5)
    )
    both = gate_mask(bnb, "G_BOTH")
    inter = int((core & both).sum())
    union = int((core | both).sum())
    n_core = int(core.sum())
    n_both = int(both.sum())
    return {
        "n_bnb": len(bnb),
        "n_bnb_core": n_core,
        "n_g_both": n_both,
        "n_intersection": inter,
        "jaccard": round(inter / union, 4) if union else None,
        "p_core_given_both": round(inter / n_both, 4) if n_both else None,
        "p_both_given_core": round(inter / n_core, 4) if n_core else None,
        "e_bnb_core": expectancy_20(bnb[core]),
        "e_g_both": expectancy_20(bnb[both]),
    }


def judge(df: pd.DataFrame) -> dict:
    """§4.1 사전등록 판정 — 4항목 전부 충족 시에만 ACCEPT."""
    boot = bootstrap_delta(df)
    cells = cell_counts(df)
    pair_cells = [c for c in cells if c["level"] == "pair"]
    halves = half_split_deltas(df)
    syms = symbol_deltas(df)

    delta = boot.get("delta")
    c1 = bool(
        delta is not None and delta > 0
        and boot.get("ci_low") is not None and boot["ci_low"] > 0
    )
    c2 = bool(pair_cells) and all(c["n_both"] >= MIN_CELL_N for c in pair_cells)
    c3 = bool(halves) and all(h["delta"] is not None and h["delta"] > 0 for h in halves)
    positive = [s["symbol"] for s in syms if s["delta"] is not None and s["delta"] > 0]
    c4 = len(positive) >= 2

    criteria = [
        {"id": 1, "text": "Δ > 0 & bootstrap 95% CI가 0 배제", "passed": c1,
         "detail": f"Δ={delta} CI=[{boot.get('ci_low')}, {boot.get('ci_high')}]"},
        {"id": 2, "text": f"셀별 n >= {MIN_CELL_N} (G_BOTH 기준)", "passed": c2,
         "detail": ", ".join(f"{c['cell']}={c['n_both']}" for c in pair_cells)},
        {"id": 3, "text": "전/후 반분 양쪽에서 Δ > 0", "passed": c3,
         "detail": ", ".join(f"{h['split']}={h['delta']}" for h in halves)},
        {"id": 4, "text": "{BTC, ETH, BNB} 중 2개 이상에서 Δ > 0", "passed": c4,
         "detail": ", ".join(f"{s['symbol']}={s['delta']}" for s in syms)},
    ]
    verdict = "ACCEPT" if all(c["passed"] for c in criteria) else "REJECT"
    return {
        "verdict": verdict,
        "criteria": criteria,
        "bootstrap": boot,
        "cells": cells,
        "halves": halves,
        "symbols": syms,
    }


# ------------------------------------------------- §2 F5-c 캘리브레이션
def fractal_correlation(
    symbol: str,
    htf: str,
    ltf: str,
    *,
    htf_pipe: Optional[pd.DataFrame] = None,
    ltf_pipe: Optional[pd.DataFrame] = None,
) -> dict:
    """corr(HTF 소파동 %K, HTF 봉 마감 시점으로 asof-align 한 LTF 대파동 %K)."""
    from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

    if htf_pipe is None:
        lim = HTF_FETCH_LIMIT.get(htf, 500)
        htf_pipe = run_indicator_pipeline(
            fetch_ohlcv_bare(symbol, htf, lim, paginated=lim > 1000),
        )
    if ltf_pipe is None:
        lim = HTF_FETCH_LIMIT.get(ltf, 1600)
        ltf_pipe = run_indicator_pipeline(
            fetch_ohlcv_bare(symbol, ltf, lim, paginated=lim > 1000),
        )

    small_col = f"stoch_k_{_LAYER_SMALL}"
    large_col = f"stoch_k_{_LAYER_LARGE}"
    left = pd.DataFrame({
        "close_time": close_time_of(htf_pipe.index, htf).to_numpy(),
        "htf_small_k": pd.to_numeric(htf_pipe[small_col], errors="coerce").to_numpy(),
    }).dropna().sort_values("close_time")
    right = pd.DataFrame({
        "close_time": close_time_of(ltf_pipe.index, ltf).to_numpy(),
        "ltf_large_k": pd.to_numeric(ltf_pipe[large_col], errors="coerce").to_numpy(),
    }).dropna().sort_values("close_time")

    merged = pd.merge_asof(left, right, on="close_time", direction="backward").dropna()
    if len(merged) < 2:
        return {"symbol": symbol, "htf": htf, "ltf": ltf, "n": len(merged), "corr": None}
    return {
        "symbol": symbol,
        "htf": htf,
        "ltf": ltf,
        "n": len(merged),
        "corr": round(float(merged["htf_small_k"].corr(merged["ltf_large_k"])), 4),
        "overlap_start": merged["close_time"].min(),
        "overlap_end": merged["close_time"].max(),
    }


def calibration_verdict(rows: List[dict]) -> dict:
    """§2 판정 — 쌍 평균 corr >= 0.90 이면 유지."""
    vals = [r["corr"] for r in rows if r.get("corr") is not None]
    mean_corr = round(float(np.mean(vals)), 4) if vals else None
    return {
        "mean_corr": mean_corr,
        "min_corr": round(float(np.min(vals)), 4) if vals else None,
        "threshold": CALIB_THRESHOLD,
        "keep_pair": bool(vals) and mean_corr is not None and mean_corr >= CALIB_THRESHOLD,
    }


def export_events_csv(df: pd.DataFrame, path: str) -> None:
    cols = [c for c in CSV_EXPORT_COLS if c in df.columns]
    df[cols].to_csv(path, index=False)
