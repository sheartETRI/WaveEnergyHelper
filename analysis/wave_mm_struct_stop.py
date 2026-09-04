"""SPEC_WAVE_MM_STRUCT_STOP §1 — 구조 손절 (패턴 저점 이탈) vs 고정 −3%.

폭 조정이 아니라 계열 교체다. 책의 원칙 "진입 근거가 소멸하면 청산" —
쌍바닥 진입의 근거 소멸은 패턴 저점 이탈이므로, 가격 거리가 아니라 구조에 손절을 붙인다.

reference_low = 진입 봉 직전에 **확정된** 마지막 swing low
  (is_tb_proxy 가 소비하는 것과 동일한 산출 경로: find_swing_lows + _confirmed.
   신규 검출기·파라미터 없음. asof: 신호봉 기준으로 확정된 저점만 — idx+PIVOT <= pos)
손절선 = reference_low × (1 − BUFFER)

미검출·퇴화(손절선이 진입가 이상) 이벤트는 BASE(−3% 평단)로 떨어지며 건수를 보고한다.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_mm_simulator import STOP_PCT
from analysis.wave_structure_confirmation import PIVOT, _confirmed, find_swing_lows

# --- §1 고정 (대안 탐색 금지) ---
BUFFER = 0.005          # 0.5% — SZ-R0 실측 atrp 중앙값 0.998% 의 절반
FALLBACK_PCT = STOP_PCT  # 미검출·퇴화 시 BASE

# --- §2 SS-R0 관문 ---
DETECT_MIN = 0.80
DIVERGE_MIN = 0.30
DIVERGE_PP = 1.0        # −3% 와 1%p 초과로 다른지

REASON_OK = "STRUCT"
REASON_NO_LOW = "NO_REFERENCE_LOW"
REASON_DEGENERATE = "DEGENERATE_ABOVE_ENTRY"


def struct_stops(
    events: pd.DataFrame,
    bars_by_key: Dict[Tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    """이벤트별 구조 손절선과 진입가 대비 거리(%).

    진입가는 시뮬레이터와 동일하게 신호봉 다음 봉 시가다.
    """
    rows = []
    for (sym, ltf), grp in events.groupby(["symbol", "ltf"]):
        bars = bars_by_key.get((sym, ltf))
        if bars is None or bars.empty:
            continue
        lows = find_swing_lows(bars["low"])
        for ev in grp.itertuples():
            ts = pd.Timestamp(ev.timestamp)
            if ts not in bars.index:
                continue
            pos = int(bars.index.get_loc(ts))
            if pos + 1 >= len(bars):
                continue
            entry_price = float(bars["open"].iloc[pos + 1])
            if not np.isfinite(entry_price) or entry_price <= 0:
                continue

            confirmed = _confirmed(lows, pos)
            rec = {
                "event_id": ev.event_id, "symbol": sym, "ltf": ltf, "timestamp": ts,
                "entry_price": entry_price, "n_confirmed_lows": len(confirmed),
            }
            if not confirmed:
                rec.update({"reference_low": None, "stop_price": None,
                            "stop_pct": FALLBACK_PCT, "reason": REASON_NO_LOW,
                            "detected": False, "applied_struct": False})
                rows.append(rec)
                continue

            ref_idx, ref_low = confirmed[-1]
            stop_price = float(ref_low) * (1.0 - BUFFER)
            rec.update({"reference_low": float(ref_low),
                        "reference_idx": int(ref_idx),
                        "bars_since_low": pos - int(ref_idx),
                        "stop_price": stop_price, "detected": True})
            if stop_price >= entry_price:
                rec.update({"stop_pct": FALLBACK_PCT, "reason": REASON_DEGENERATE,
                            "applied_struct": False,
                            "struct_pct": (entry_price - stop_price) / entry_price * 100.0})
            else:
                pct = (entry_price - stop_price) / entry_price * 100.0
                rec.update({"stop_pct": pct, "reason": REASON_OK,
                            "applied_struct": True, "struct_pct": pct})
            rows.append(rec)
    return pd.DataFrame(rows)


def struct_stop_map(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {}
    return dict(zip(df["event_id"], df["stop_pct"]))


# ------------------------------------------------------------ §2 관문
def detection_gate(df: pd.DataFrame, trades: Optional[pd.DataFrame] = None) -> dict:
    """SS-R0 — 검출률과 −3% 대비 이격 비율. 체결 트레이드 기준."""
    sub = df
    if trades is not None and not trades.empty:
        sub = df[df["event_id"].isin(set(trades["event_id"]))]
    if sub.empty:
        return {"n": 0, "go": False}

    detected = sub["detected"].fillna(False).astype(bool)
    applied = sub["applied_struct"].fillna(False).astype(bool)
    detect_rate = float(detected.mean())

    # 이격 비율 — 구조 손절이 실제 적용된 트레이드가 −3% 와 1%p 초과로 다른 비율.
    # 분모는 체결 트레이드 전체다 (미검출·퇴화는 BASE 와 같으므로 '다르지 않음'으로 센다).
    dist = sub.loc[applied, "struct_pct"].astype(float)
    n_diverge = int(((dist - FALLBACK_PCT).abs() > DIVERGE_PP).sum()) if len(dist) else 0
    diverge = n_diverge / max(len(sub), 1)

    q = dist.quantile([0.25, 0.5, 0.75]) if len(dist) else pd.Series(dtype=float)
    return {
        "n": len(sub),
        "detected": int(detected.sum()),
        "detect_rate": round(detect_rate, 4),
        "applied_struct": int(applied.sum()),
        "no_reference_low": int((sub["reason"] == REASON_NO_LOW).sum()),
        "degenerate": int((sub["reason"] == REASON_DEGENERATE).sum()),
        "diverge_share": round(float(diverge), 4),
        "dist_p25": round(float(q.get(0.25, np.nan)), 4) if len(dist) else None,
        "dist_p50": round(float(q.get(0.5, np.nan)), 4) if len(dist) else None,
        "dist_p75": round(float(q.get(0.75, np.nan)), 4) if len(dist) else None,
        "dist_mean": round(float(dist.mean()), 4) if len(dist) else None,
        "dist_min": round(float(dist.min()), 4) if len(dist) else None,
        "dist_max": round(float(dist.max()), 4) if len(dist) else None,
        "cond_detect": bool(detect_rate >= DETECT_MIN),
        "cond_diverge": bool(diverge >= DIVERGE_MIN),
        "go": bool(detect_rate >= DETECT_MIN and diverge >= DIVERGE_MIN),
    }


# ------------------------------------------------- §4-1 메커니즘 재계측
def mechanism(struct: pd.DataFrame, nostop: pd.DataFrame) -> dict:
    """구조 손절 트레이드의 실현가 vs 20봉 반사실.

    MM-R1 의 '되돌림 직전 매도' 격차(−3.2485% vs −2.7808% = −0.4677%p)가 줄었는가.
    """
    from analysis.wave_mm_simulator import EXIT_STOP

    if struct.empty or nostop.empty:
        return {"paired": 0}
    s = struct.set_index("event_id")
    n = nostop.set_index("event_id")
    common = s.index.intersection(n.index)
    if len(common) == 0:
        return {"paired": 0}
    ss, nn = s.loc[common], n.loc[common]
    stopped = ss["exit_reason"].eq(EXIT_STOP)
    if int(stopped.sum()) == 0:
        return {"paired": int(len(common)), "stopped": 0}
    ids = stopped.index[stopped]
    realized = float(ss.loc[ids, "net_ret"].mean() * 100)
    counter = float(nn.loc[ids, "net_ret"].mean() * 100)
    would_win = nn.loc[ids, "net_ret"] > 0
    return {
        "paired": int(len(common)),
        "stopped": int(stopped.sum()),
        "realized_mean_pct": round(realized, 4),
        "counterfactual_mean_pct": round(counter, 4),
        "gap_pp": round(realized - counter, 4),
        "would_be_positive": int(would_win.sum()),
        "would_be_positive_rate": round(float(would_win.mean()), 4),
    }
