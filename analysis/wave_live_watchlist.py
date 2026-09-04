"""Wave Live Watchlist — RULE_A/B/C 실시간 관측 레이어.

OHLCV + 기존 observation 함수만 사용. 엔진·신호·기존 CSV/REPORT 수정 없음.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from analysis.wave_cross_market_validation import rule_filters
from analysis.wave_money_flow import add_money_flow_features, extract_money_flow_at
from analysis.wave_outcome import _find_bar_index
from analysis.wave_regime_analysis import extract_regime_at
from analysis.wave_structure_confirmation import (
    PIVOT,
    _confirmed,
    extract_structure_at,
    find_swing_highs,
    find_swing_lows,
)
from analysis.wave_volume_energy import _load_ohlcv, add_volume_features, extract_volume_at

TARGET_SYMBOLS = ("ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT")
TIMEFRAMES = ("1h", "4h", "6h", "1d")
WATCH_RULES = ("RULE_A", "RULE_B", "RULE_C")
SCAN_BARS = 500
FRESHNESS_ACTIVE = 10
FRESHNESS_RECENT = 50
FREQ_WINDOWS_DAYS = (30, 90, 180)
FORWARD_HORIZONS = (5, 10, 20, 40)
RULE_WEIGHTS = {"RULE_B": 3.0, "RULE_A": 2.0, "RULE_C": 1.0}
HEATMAP_PRIORITY = ("RULE_B", "RULE_A", "RULE_C", "NONE")
TB_SPREAD_PCT = 4.0

CSV_EXPORT_COLS = (
    "timestamp", "symbol", "timeframe", "rule", "quality_score",
    "money_flow_score", "energy_score", "structure_score",
    "watchlist_score", "freshness", "bars_since_signal", "bar_index",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _confluence_path(symbol: str, tf: str) -> Optional[str]:
    for name in (
        f"wave_confluence_{symbol}_{tf}.csv",
        os.path.join("_generalization_cache", f"confluence_{symbol}_{tf}.csv"),
    ):
        path = os.path.join(_validation_dir(), name)
        if os.path.isfile(path):
            return path
    return None


def _load_pipeline(symbol: str, timeframe: str) -> pd.DataFrame:
    from data.binance import get_auto_limit
    from display.asof import fetch_ohlcv_bare, run_indicator_pipeline
    from analysis.wave_confluence import add_confluence_indicators

    lim = max(SCAN_BARS + 200, 1600 if timeframe == "4h" else get_auto_limit(timeframe))
    bare = fetch_ohlcv_bare(symbol, timeframe, lim, paginated=lim > 1000)
    if bare is None or bare.empty:
        return pd.DataFrame()
    return add_confluence_indicators(run_indicator_pipeline(bare))


def is_tb_proxy(
    swing_lows: List[Tuple[int, float]],
    pos: int,
    spread_pct: float = TB_SPREAD_PCT,
) -> bool:
    """관측용 Triple Bottom 구조 프록시."""
    conf_lows = _confirmed(swing_lows, pos)
    if len(conf_lows) < 3:
        return False
    lows_vals = [v for _, v in conf_lows[-3:]]
    mn = min(lows_vals)
    if mn <= 0:
        return False
    spread = (max(lows_vals) - mn) / mn * 100.0
    hl = conf_lows[-1][1] > conf_lows[-2][1]
    return spread <= spread_pct and hl


def load_tb_bar_indices(symbol: str, tf: str, ohlcv: pd.DataFrame) -> Set[int]:
    """Confluence cache의 TRIPLE_BOTTOM_REQUIRED 타임스탬프 → 봉 인덱스."""
    path = _confluence_path(symbol, tf)
    if not path or ohlcv.empty:
        return set()
    conf = pd.read_csv(path, parse_dates=["timestamp"])
    indices: Set[int] = set()
    for _, row in conf.iterrows():
        branch = str(row.get("branch", row.get("branch_label", "")))
        if branch != "TRIPLE_BOTTOM_REQUIRED" and "TRIPLE_BOTTOM" not in branch:
            continue
        idx = _find_bar_index(ohlcv, pd.Timestamp(row["timestamp"]))
        if idx is not None:
            indices.add(int(idx))
    return indices


def compute_regime_factor(pipeline: pd.DataFrame, pos: int) -> float:
    """0~1 regime 가중 (관측용)."""
    if pipeline.empty or pos < 0 or pos >= len(pipeline):
        return 0.5
    regime = extract_regime_at(pipeline, pos)
    score = 0.5
    e20 = regime.get("ema20_slope_3")
    e60 = regime.get("ema60_slope_3")
    if e20 is not None and e60 is not None:
        if e20 > 0 and e60 > 0:
            score = 1.0
        elif e20 < 0 and e60 < 0:
            score = 0.3
    rsi_slope = regime.get("rsi_slope_1")
    if rsi_slope is not None and rsi_slope > 0:
        score = min(1.0, score + 0.15)
    return max(0.1, min(1.0, score))


def compute_watchlist_score(
    rule: str,
    money_flow_score: int,
    structure_score: int,
    energy_score: int,
    regime_factor: float,
) -> float:
    """Rule × MF × Structure × Energy × Regime → 0~100."""
    rw = RULE_WEIGHTS.get(rule, 1.0) / max(RULE_WEIGHTS.values())
    mf_n = min(max(money_flow_score, 0), 5) / 5.0
    st_n = min(max(structure_score, 0), 6) / 6.0
    en_n = min(max(energy_score, 0), 5) / 5.0
    raw = rw * mf_n * st_n * en_n * regime_factor
    return round(float(raw * 100.0), 2)


def compute_live_rank_score(rule: str, watchlist_score: float, freshness: str) -> float:
    """Live Quality Ranking — RULE_B > RULE_A > RULE_C 기본 가중."""
    base = RULE_WEIGHTS.get(rule, 1.0) * 25.0
    fresh_bonus = {"ACTIVE": 15.0, "RECENT": 8.0, "OLD": 0.0}.get(freshness, 0.0)
    return round(base + watchlist_score * 0.5 + fresh_bonus, 2)


def classify_freshness(bars_since: int) -> str:
    if bars_since <= FRESHNESS_ACTIVE:
        return "ACTIVE"
    if bars_since <= FRESHNESS_RECENT:
        return "RECENT"
    return "OLD"


def scan_cell(
    symbol: str,
    tf: str,
    *,
    ohlcv: Optional[pd.DataFrame] = None,
    pipeline: Optional[pd.DataFrame] = None,
    scan_bars: int = SCAN_BARS,
) -> pd.DataFrame:
    """최근 scan_bars 봉 전체 스캔 → 봉별 feature + rule flag."""
    bare = ohlcv if ohlcv is not None else _load_ohlcv(symbol, tf)
    if bare is None or bare.empty:
        return pd.DataFrame()

    combined = add_money_flow_features(add_volume_features(bare))
    if combined.empty:
        return pd.DataFrame()

    pipe = pipeline if pipeline is not None else _load_pipeline(symbol, tf)
    swing_lows = find_swing_lows(combined["low"])
    swing_highs = find_swing_highs(combined["high"])
    tb_confirmed = load_tb_bar_indices(symbol, tf, combined)

    start = max(0, len(combined) - scan_bars)
    last_idx = len(combined) - 1
    rows: List[dict] = []

    for pos in range(start, len(combined)):
        vol_feats = extract_volume_at(combined, pos)
        mf_feats = extract_money_flow_at(combined, pos)
        struct_feats = extract_structure_at(combined, pos, swing_lows, swing_highs)

        mf_score = int(mf_feats.get("money_flow_score", 0) or 0)
        energy_score = int(vol_feats.get("energy_score", 0) or 0)
        struct_score = int(struct_feats.get("structure_score", 0) or 0)

        flag_tb = pos in tb_confirmed or is_tb_proxy(swing_lows, pos)
        flag_mf = mf_score >= 4
        flag_struct = struct_score >= 3
        flag_energy = energy_score >= 3

        quality_score = int(flag_tb) + int(flag_struct) + int(flag_energy) + int(flag_mf)
        regime_factor = compute_regime_factor(pipe, pos) if not pipe.empty else 0.5
        ts = pd.Timestamp(combined.index[pos])
        bars_since = last_idx - pos

        row = {
            "timestamp": ts,
            "symbol": symbol,
            "timeframe": tf,
            "bar_index": pos,
            "bars_since_signal": bars_since,
            "flag_tb": flag_tb,
            "flag_money_flow": flag_mf,
            "flag_structure": flag_struct,
            "flag_energy": flag_energy,
            "quality_score": quality_score,
            "money_flow_score": mf_score,
            "energy_score": energy_score,
            "structure_score": struct_score,
            "regime_factor": regime_factor,
            "close": float(combined["close"].iloc[pos]),
        }
        rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def extract_rule_events(scan_df: pd.DataFrame) -> pd.DataFrame:
    """스캔 프레임에서 RULE_A/B/C 발생 이벤트 추출."""
    if scan_df.empty:
        return pd.DataFrame()

    events: List[dict] = []
    filters = rule_filters()
    for rule in WATCH_RULES:
        mask = filters[rule](scan_df)
        sub = scan_df[mask]
        for _, row in sub.iterrows():
            freshness = classify_freshness(int(row["bars_since_signal"]))
            wl = compute_watchlist_score(
                rule,
                int(row["money_flow_score"]),
                int(row["structure_score"]),
                int(row["energy_score"]),
                float(row.get("regime_factor", 0.5)),
            )
            events.append({
                "timestamp": row["timestamp"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "rule": rule,
                "quality_score": int(row["quality_score"]),
                "money_flow_score": int(row["money_flow_score"]),
                "energy_score": int(row["energy_score"]),
                "structure_score": int(row["structure_score"]),
                "watchlist_score": wl,
                "freshness": freshness,
                "bars_since_signal": int(row["bars_since_signal"]),
                "bar_index": int(row["bar_index"]),
                "close": float(row["close"]),
            })
    if not events:
        return pd.DataFrame()
    return pd.DataFrame(events).sort_values("timestamp").reset_index(drop=True)


def frequency_table(events: pd.DataFrame, ref_ts: Optional[pd.Timestamp] = None) -> List[dict]:
    """rule × symbol × tf × 30/90/180일 count."""
    if events.empty:
        return []
    ref = ref_ts or pd.Timestamp(events["timestamp"].max())
    rows: List[dict] = []
    for rule in WATCH_RULES:
        for sym in TARGET_SYMBOLS:
            for tf in TIMEFRAMES:
                sub = events[
                    (events["rule"] == rule)
                    & (events["symbol"] == sym)
                    & (events["timeframe"] == tf)
                ]
                row = {"rule": rule, "symbol": sym, "timeframe": tf}
                for days in FREQ_WINDOWS_DAYS:
                    cutoff = ref - pd.Timedelta(days=days)
                    row[f"count_{days}d"] = int((sub["timestamp"] >= cutoff).sum())
                rows.append(row)
    return rows


def bars_between_events_avg(events: pd.DataFrame) -> List[dict]:
    """Rule 발생률 — bars_between_events 평균."""
    rows: List[dict] = []
    for rule in WATCH_RULES:
        for sym in TARGET_SYMBOLS:
            for tf in TIMEFRAMES:
                sub = events[
                    (events["rule"] == rule)
                    & (events["symbol"] == sym)
                    & (events["timeframe"] == tf)
                ].sort_values("bar_index")
                if len(sub) < 2:
                    rows.append({
                        "rule": rule, "symbol": sym, "timeframe": tf,
                        "event_count": len(sub),
                        "avg_bars_between": None,
                    })
                    continue
                gaps = sub["bar_index"].diff().dropna().astype(float)
                rows.append({
                    "rule": rule, "symbol": sym, "timeframe": tf,
                    "event_count": len(sub),
                    "avg_bars_between": round(float(gaps.mean()), 1),
                })
    return rows


def freshness_summary(events: pd.DataFrame) -> List[dict]:
    """심볼×TF×rule별 최근 이벤트 freshness."""
    rows: List[dict] = []
    if events.empty:
        return rows
    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            for rule in WATCH_RULES:
                sub = events[
                    (events["symbol"] == sym)
                    & (events["timeframe"] == tf)
                    & (events["rule"] == rule)
                ].sort_values("timestamp")
                if sub.empty:
                    rows.append({
                        "symbol": sym, "timeframe": tf, "rule": rule,
                        "freshness": "NONE", "bars_since_signal": None,
                    })
                    continue
                last = sub.iloc[-1]
                rows.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": rule,
                    "freshness": last["freshness"],
                    "bars_since_signal": int(last["bars_since_signal"]),
                })
    return rows


def forward_tracking(
    events: pd.DataFrame,
    ohlcv_by_cell: Dict[Tuple[str, str], pd.DataFrame],
) -> List[dict]:
    """발생 이후 +5/+10/+20/+40 성과."""
    if events.empty:
        return []

    by_horizon: Dict[int, List[float]] = {h: [] for h in FORWARD_HORIZONS}
    for _, ev in events.iterrows():
        key = (str(ev["symbol"]), str(ev["timeframe"]))
        ohlcv = ohlcv_by_cell.get(key)
        if ohlcv is None or ohlcv.empty:
            continue
        pos = _find_bar_index(ohlcv, pd.Timestamp(ev["timestamp"]))
        if pos is None:
            continue
        entry = float(ohlcv["close"].iloc[pos])
        if entry <= 0:
            continue
        for h in FORWARD_HORIZONS:
            if pos + h < len(ohlcv):
                ret = (float(ohlcv["close"].iloc[pos + h]) / entry - 1.0) * 100.0
                by_horizon[h].append(ret)

    rows: List[dict] = []
    for h in FORWARD_HORIZONS:
        vals = by_horizon[h]
        if not vals:
            rows.append({
                "horizon_bars": h,
                "n": 0,
                "avg_return": None,
                "max_return": None,
                "min_return": None,
            })
            continue
        arr = np.array(vals, dtype=float)
        rows.append({
            "horizon_bars": h,
            "n": len(vals),
            "avg_return": round(float(arr.mean()), 2),
            "max_return": round(float(arr.max()), 2),
            "min_return": round(float(arr.min()), 2),
        })

    for rule in WATCH_RULES:
        sub_ev = events[events["rule"] == rule]
        rule_horizons: Dict[int, List[float]] = {h: [] for h in FORWARD_HORIZONS}
        for _, ev in sub_ev.iterrows():
            key = (str(ev["symbol"]), str(ev["timeframe"]))
            ohlcv = ohlcv_by_cell.get(key)
            if ohlcv is None or ohlcv.empty:
                continue
            pos = _find_bar_index(ohlcv, pd.Timestamp(ev["timestamp"]))
            if pos is None:
                continue
            entry = float(ohlcv["close"].iloc[pos])
            if entry <= 0:
                continue
            for h in FORWARD_HORIZONS:
                if pos + h < len(ohlcv):
                    ret = (float(ohlcv["close"].iloc[pos + h]) / entry - 1.0) * 100.0
                    rule_horizons[h].append(ret)
        for h in FORWARD_HORIZONS:
            vals = rule_horizons[h]
            if not vals:
                continue
            arr = np.array(vals, dtype=float)
            rows.append({
                "rule": rule,
                "horizon_bars": h,
                "n": len(vals),
                "avg_return": round(float(arr.mean()), 2),
                "max_return": round(float(arr.max()), 2),
                "min_return": round(float(arr.min()), 2),
            })
    return rows


def live_quality_ranking(events: pd.DataFrame) -> List[dict]:
    """현재 셀별 최신 rule 상태 ranking."""
    rows: List[dict] = []
    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            sub = events[(events["symbol"] == sym) & (events["timeframe"] == tf)]
            if sub.empty:
                continue
            for rule in WATCH_RULES:
                rsub = sub[sub["rule"] == rule]
                if rsub.empty:
                    continue
                last = rsub.sort_values("timestamp").iloc[-1]
                score = compute_live_rank_score(
                    rule, float(last["watchlist_score"]), str(last["freshness"]),
                )
                rows.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": rule,
                    "score": score,
                    "watchlist_score": float(last["watchlist_score"]),
                    "freshness": last["freshness"],
                    "bars_since_signal": int(last["bars_since_signal"]),
                })
    ranked = sorted(rows, key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def symbol_tf_heatmap(scan_by_cell: Dict[Tuple[str, str], pd.DataFrame]) -> List[dict]:
    """심볼×TF 현재 상태 — RULE_B > RULE_A > RULE_C > NONE."""
    rows: List[dict] = []
    filters = rule_filters()
    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            scan = scan_by_cell.get((sym, tf))
            state = "NONE"
            if scan is not None and not scan.empty:
                last = scan.iloc[-1]
                for rule in ("RULE_B", "RULE_A", "RULE_C"):
                    if bool(filters[rule](pd.DataFrame([last])).iloc[0]):
                        state = rule
                        break
            rows.append({"symbol": sym, "timeframe": tf, "state": state})
    return rows


def current_candidates(events: pd.DataFrame) -> List[dict]:
    """ACTIVE/RECENT freshness 후보."""
    if events.empty:
        return []
    cands: List[dict] = []
    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            for rule in WATCH_RULES:
                sub = events[
                    (events["symbol"] == sym)
                    & (events["timeframe"] == tf)
                    & (events["rule"] == rule)
                    & (events["freshness"].isin(["ACTIVE", "RECENT"]))
                ].sort_values("timestamp")
                if sub.empty:
                    continue
                last = sub.iloc[-1]
                cands.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": rule,
                    "watchlist_score": float(last["watchlist_score"]),
                    "bars_since_signal": int(last["bars_since_signal"]),
                    "freshness": last["freshness"],
                })
    return sorted(cands, key=lambda x: x["watchlist_score"], reverse=True)


def observation_priority(ranking: List[dict], heatmap: List[dict]) -> List[dict]:
    """실시간 관측 우선순위."""
    priority: List[dict] = []
    active_cells = {f"{r['symbol']}_{r['timeframe']}" for r in ranking if r.get("freshness") == "ACTIVE"}
    for row in ranking[:12]:
        key = f"{row['symbol']}_{row['timeframe']}"
        hm = next(
            (h for h in heatmap if h["symbol"] == row["symbol"] and h["timeframe"] == row["timeframe"]),
            {},
        )
        priority.append({
            "rank": row.get("rank"),
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "rule": row["rule"],
            "score": row["score"],
            "heatmap_state": hm.get("state", "NONE"),
            "active_cell": key in active_cells,
        })
    return priority


def full_live_watchlist_summary(scan_bars: int = SCAN_BARS) -> dict:
    """전체 Live Watchlist 분석."""
    scan_by_cell: Dict[Tuple[str, str], pd.DataFrame] = {}
    ohlcv_by_cell: Dict[Tuple[str, str], pd.DataFrame] = {}
    pipeline_cache: Dict[Tuple[str, str], pd.DataFrame] = {}

    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            key = (sym, tf)
            bare = _load_ohlcv(sym, tf)
            ohlcv_by_cell[key] = bare
            pipeline_cache[key] = _load_pipeline(sym, tf)
            scan_by_cell[key] = scan_cell(
                sym, tf, ohlcv=bare, pipeline=pipeline_cache[key], scan_bars=scan_bars,
            )

    event_parts = [extract_rule_events(df) for df in scan_by_cell.values() if not df.empty]
    all_events = (
        pd.concat(event_parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
        if event_parts else pd.DataFrame()
    )

    ref_ts = None
    scan_parts = [df for df in scan_by_cell.values() if not df.empty]
    if scan_parts:
        ref_ts = pd.Timestamp(max(df["timestamp"].max() for df in scan_parts))

    freq = frequency_table(all_events, ref_ts)
    bars_between = bars_between_events_avg(all_events)
    fresh = freshness_summary(all_events)
    fwd = forward_tracking(all_events, ohlcv_by_cell)
    ranking = live_quality_ranking(all_events)
    heatmap = symbol_tf_heatmap(scan_by_cell)
    candidates = current_candidates(all_events)
    priority = observation_priority(ranking, heatmap)

    strongest = ranking[0] if ranking else None
    active_count = sum(1 for e in all_events.itertuples() if e.freshness == "ACTIVE")

    return {
        "scan_bars": scan_bars,
        "ref_timestamp": ref_ts,
        "events": all_events,
        "frequency": freq,
        "bars_between": bars_between,
        "freshness": fresh,
        "forward_tracking": fwd,
        "ranking": ranking,
        "heatmap": heatmap,
        "candidates": candidates,
        "observation_priority": priority,
        "strongest_candidate": strongest,
        "active_event_count": active_count,
        "total_events": len(all_events),
    }
