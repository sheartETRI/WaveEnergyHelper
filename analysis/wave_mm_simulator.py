"""SPEC_WAVE_MM_STOP_AUDIT §2 — 트레이드 시뮬레이터 (MM-R0).

기존 이벤트·게이트 산출물만 소비한다. 진입 이벤트 정의를 바꾸지 않는다.

체결 모형 (스펙 §2 고정):
- 진입: 이벤트 봉 **다음 봉 시가**
- 손절: 봉 내 low <= 기준가×(1-STOP_PCT) → 그 가격에 체결, 슬리피지 STOP_SLIPPAGE_PCT 가산
- 시간 청산: 진입 후 TIME_EXIT_BARS 봉의 종가 (expectancy_20 지평과 정합 — 신호봉 i 기준 i+20 종가)
- 동시 충족 봉은 손절 우선 (보수적)
- 비용: 왕복 COST_ROUNDTRIP_PCT
- 포트폴리오: 동시 1포지션, 보유 중 이벤트는 건너뜀

검증 모드(entry_mode="event_close")는 저널 return_20 규약(신호봉 종가 진입)을 재현한다.
프로덕션 판정에는 스펙대로 "next_open" 만 쓴다.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_htf_gate_v2 import (
    GATE_VERSION_V2,
    PAIRS_V2,
    SYMBOLS_V2,
    WINDOW_MAIN,
    build_pair_events_v2,
)

# --- §0 BASE 규칙 (사용자 현행, §8 확인 완료) ---
CAPITAL_KRW = 70_000_000
TRANCHE_PCT = 5.0          # 트랜치당 자본 비중
STOP_PCT = 3.0             # 평균 매수단가 대비 손절 폭
# --- §2 체결 가정 (고정) ---
STOP_SLIPPAGE_PCT = 0.05
COST_ROUNDTRIP_PCT = 0.2
TIME_EXIT_BARS = 20

STREAMS: Dict[str, str] = {pair: ltf for pair, (_htf, ltf) in PAIRS_V2.items()}

EXIT_STOP = "STOP"
EXIT_TIME = "TIME"

TRADE_COLS = (
    "event_id", "pair", "ltf", "symbol", "signal_ts", "entry_ts", "entry_price",
    "exit_ts", "exit_price", "exit_reason", "bars_held",
    "gross_ret", "net_ret", "log_growth", "stop_pct_used", "size_pct",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation",
    )


def _cache_dir() -> str:
    path = os.path.join(_validation_dir(), "_mm_cache")
    os.makedirs(path, exist_ok=True)
    return path


def bars_path(symbol: str, ltf: str) -> str:
    return os.path.join(_cache_dir(), f"ohlcv_{symbol}_{ltf}.csv")


# ------------------------------------------------------------------ 모집단
def load_gate_events(
    window: Tuple[str, str] = WINDOW_MAIN,
    symbols=SYMBOLS_V2,
) -> pd.DataFrame:
    """§2 모집단 — F2-b 게이트를 통과한 트리거 이벤트 (승격 워치리스트 필터와 동일)."""
    frames = [build_pair_events_v2(p, GATE_VERSION_V2) for p in PAIRS_V2]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    ev = pd.concat(frames, ignore_index=True)
    ev["timestamp"] = pd.to_datetime(ev["timestamp"])
    mask = (
        ev["g_align"].astype(bool)
        & ev["symbol"].isin(symbols)
        & (ev["timestamp"] >= pd.Timestamp(window[0]))
        & (ev["timestamp"] <= pd.Timestamp(window[1]))
    )
    ev = ev[mask].copy()
    # 자의성 고정: 이벤트 시각 순, 동시각이면 심볼 사전순
    return ev.sort_values(["timestamp", "symbol"], kind="mergesort").reset_index(drop=True)


def load_bars(symbol: str, ltf: str, *, build: bool = False) -> pd.DataFrame:
    """LTF OHLCV (캐시). build=True 면 없을 때 새로 받는다(네트워크)."""
    path = bars_path(symbol, ltf)
    if os.path.isfile(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index.name = "open_time"
        return df
    if not build:
        return pd.DataFrame()
    from analysis.wave_htf_gate_v2 import fetch_window_bare

    bare = fetch_window_bare(symbol, ltf, WINDOW_MAIN[0], WINDOW_MAIN[1], pad_bars=60)
    bare.to_csv(path)
    return bare


# ------------------------------------------------------------------ 시뮬레이션
def _bar_pos(bars: pd.DataFrame, ts: pd.Timestamp) -> Optional[int]:
    idx = bars.index.searchsorted(ts)
    if idx >= len(bars) or bars.index[idx] != ts:
        return None
    return int(idx)


def simulate(
    events: pd.DataFrame,
    bars_by_key: Dict[Tuple[str, str], pd.DataFrame],
    *,
    use_stop: bool = True,
    stop_pct=STOP_PCT,
    entry_mode: str = "next_open",
    apply_cost: bool = True,
    one_position: bool = True,
    time_exit_bars: int = TIME_EXIT_BARS,
    tranche_pct=TRANCHE_PCT,
) -> pd.DataFrame:
    """이벤트 계열 → 트레이드 계열.

    entry_mode:
      "next_open"   — 스펙 §2 체결 모형 (이벤트 봉 다음 봉 시가)
      "event_close" — 검증용. 저널 return_20 규약(신호봉 종가) 재현.
    """
    if events.empty:
        return pd.DataFrame(columns=list(TRADE_COLS))

    # stop_pct 는 고정 퍼센트이거나 {event_id: 퍼센트} 매핑 (§5 ATR 손절 보조 보고용)
    stop_map = stop_pct if isinstance(stop_pct, dict) else None
    stop_frac_default = (stop_pct / 100.0) if stop_map is None else None
    slip = STOP_SLIPPAGE_PCT / 100.0
    cost = (COST_ROUNDTRIP_PCT / 100.0) if apply_cost else 0.0
    # tranche_pct 는 고정 퍼센트이거나 {event_id: 퍼센트} 매핑 (SIZING 라운드용).
    # 매핑에 없는 이벤트는 기본 트랜치로 떨어진다.
    size_map = tranche_pct if isinstance(tranche_pct, dict) else None
    weight_default = (tranche_pct / 100.0) if size_map is None else (TRANCHE_PCT / 100.0)

    rows = []
    busy_until: Optional[pd.Timestamp] = None

    for ev in events.itertuples():
        ts = pd.Timestamp(ev.timestamp)
        if one_position and busy_until is not None and ts < busy_until:
            continue
        bars = bars_by_key.get((ev.symbol, ev.ltf))
        if bars is None or bars.empty:
            continue
        pos = _bar_pos(bars, ts)
        if pos is None:
            continue

        if entry_mode == "next_open":
            entry_idx = pos + 1
            if entry_idx >= len(bars):
                continue
            entry_price = float(bars["open"].iloc[entry_idx])
        elif entry_mode == "event_close":
            entry_idx = pos
            entry_price = float(bars["close"].iloc[entry_idx])
        else:
            raise ValueError(f"unknown entry_mode: {entry_mode}")
        if not np.isfinite(entry_price) or entry_price <= 0:
            continue

        # 시간 청산 봉 — 신호봉 기준 i+time_exit_bars 종가 (expectancy_20 지평)
        exit_idx = pos + time_exit_bars
        if exit_idx >= len(bars):
            continue

        exit_price = float(bars["close"].iloc[exit_idx])
        exit_reason = EXIT_TIME
        exit_at = exit_idx

        stop_frac = (stop_frac_default if stop_map is None
                     else (stop_map.get(ev.event_id, np.nan) or np.nan) / 100.0)
        if use_stop and stop_frac is not None and np.isfinite(stop_frac) and stop_frac > 0:
            stop_price = entry_price * (1.0 - stop_frac)
            lows = bars["low"].iloc[entry_idx:exit_idx + 1]
            hit = lows[lows <= stop_price]
            if len(hit):
                exit_at = int(bars.index.get_loc(hit.index[0]))
                exit_price = stop_price * (1.0 - slip)   # 손절 체결 슬리피지
                exit_reason = EXIT_STOP

        weight = (weight_default if size_map is None
                  else float(size_map.get(ev.event_id, TRANCHE_PCT)) / 100.0)
        gross = (exit_price - entry_price) / entry_price
        net = gross - cost
        rows.append({
            "event_id": ev.event_id,
            "pair": ev.pair,
            "ltf": ev.ltf,
            "symbol": ev.symbol,
            "signal_ts": ts,
            "entry_ts": bars.index[entry_idx],
            "entry_price": entry_price,
            "exit_ts": bars.index[exit_at],
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "bars_held": exit_at - entry_idx,
            "stop_pct_used": (round(stop_frac * 100, 4)
                              if (use_stop and stop_frac is not None
                                  and np.isfinite(stop_frac)) else None),
            "size_pct": round(weight * 100, 6),
            "gross_ret": gross,
            "net_ret": net,
            "log_growth": float(np.log1p(weight * net)),
        })
        busy_until = bars.index[exit_at]

    return pd.DataFrame(rows, columns=list(TRADE_COLS))


# ------------------------------------------------------------------ 지표
def growth(trades: pd.DataFrame) -> Optional[float]:
    """G — 트레이드 계열 로그 성장률 합 (기하 성과, 비용 차감 후)."""
    if trades.empty:
        return None
    return round(float(trades["log_growth"].sum()), 6)


def equity_curve(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    t = trades.sort_values("exit_ts")
    return pd.Series(t["log_growth"].cumsum().to_numpy(), index=t["exit_ts"])


def max_drawdown(trades: pd.DataFrame) -> Optional[float]:
    """로그 자산곡선 최대 낙폭 (비율)."""
    eq = equity_curve(trades)
    if eq.empty:
        return None
    wealth = np.exp(eq.to_numpy())
    peak = np.maximum.accumulate(wealth)
    return round(float((1.0 - wealth / peak).max()), 6)


def exposure_rate(trades: pd.DataFrame, window=WINDOW_MAIN) -> Optional[float]:
    """노출률 — 포지션 보유 시간 / 전체 구간."""
    if trades.empty:
        return None
    held = (pd.to_datetime(trades["exit_ts"]) - pd.to_datetime(trades["entry_ts"])).sum()
    span = pd.Timestamp(window[1]) - pd.Timestamp(window[0])
    return round(float(held / span), 6)


def monthly_returns(trades: pd.DataFrame) -> pd.DataFrame:
    """월별 로그 성장률 계열 (청산 시각 기준)."""
    if trades.empty:
        return pd.DataFrame(columns=["month", "log_growth", "trades"])
    t = trades.copy()
    t["month"] = pd.to_datetime(t["exit_ts"]).dt.to_period("M").astype(str)
    g = t.groupby("month").agg(log_growth=("log_growth", "sum"),
                               trades=("log_growth", "size")).reset_index()
    return g


def trade_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    net = trades["net_ret"].astype(float)
    stops = trades["exit_reason"].eq(EXIT_STOP)
    return {
        "trades": len(trades),
        "stop_rate": round(float(stops.mean()), 6),
        "win_rate": round(float((net > 0).mean()), 6),
        "net_mean_pct": round(float(net.mean() * 100), 6),
        "net_median_pct": round(float(net.median() * 100), 6),
        "growth": growth(trades),
        "max_drawdown": max_drawdown(trades),
        "exposure": exposure_rate(trades),
        "bars_held_mean": round(float(trades["bars_held"].mean()), 3),
    }


def counterfactual_stopped(
    base: pd.DataFrame, nostop: pd.DataFrame,
) -> dict:
    """§3 — 손절된 트레이드가 손절 없었다면 20봉 시점에 양수였을 비율.

    같은 event_id 로 짝지어야 의미가 있다. 1포지션 제약 때문에 두 시나리오의
    트레이드 집합이 다르므로, 양쪽에 모두 체결된 이벤트만 대상으로 한다.
    """
    if base.empty or nostop.empty:
        return {"paired": 0}
    b = base.set_index("event_id")
    n = nostop.set_index("event_id")
    common = b.index.intersection(n.index)
    if len(common) == 0:
        return {"paired": 0}
    bs = b.loc[common]
    ns = n.loc[common]
    stopped = bs["exit_reason"].eq(EXIT_STOP)
    if int(stopped.sum()) == 0:
        return {"paired": int(len(common)), "stopped": 0}
    would_win = ns.loc[stopped.index[stopped], "net_ret"] > 0
    return {
        "paired": int(len(common)),
        "stopped": int(stopped.sum()),
        "would_be_positive": int(would_win.sum()),
        "would_be_positive_rate": round(float(would_win.mean()), 6),
        "stopped_net_mean_pct": round(float(bs.loc[stopped, "net_ret"].mean() * 100), 6),
        "counterfactual_net_mean_pct": round(
            float(ns.loc[stopped.index[stopped], "net_ret"].mean() * 100), 6),
    }
