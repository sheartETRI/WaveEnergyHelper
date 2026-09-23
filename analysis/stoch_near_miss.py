"""대파동 구역 니어미스 기록 — 침체/과매수 문턱에 못 미친 바닥/봉우리를 기록한다.

2026-09 BTCUSDT 6h 사례(1차 바닥 K 20.49, 침체선 20.0에 0.49 미달 → 쌍바닥 후보
미성립, 이후 K 89 직행)에서 드러난 FN 클래스의 빈도를 세기 위한 진단 레이어다.
기록 전용 — 검출기(indicators/stochastic)와 그 판정은 건드리지 않고, 이미 계산된
stoch_k_{suffix} 컬럼만 읽는다. docs/SPEC_SWEEP_RECLAIM.md §7 동결 스펙 상응.
니어미스는 신호가 아니다 — 침체선 완화 여부는 이 표본이 쌓인 뒤 판단한다.

판정(하단 기준, 상단은 미러):
  · 국소 극소: K[i-1] > K[i] < K[i+1] (엄격 부등호 — 동값 플래토는 판정하지 않음),
    확정 봉 = i+1 (t+1, lookahead 없음). 마지막 봉이 극소 후보면 보류.
  · db 니어미스: oversold < K[i] ≤ oversold + near_band — 구역 진입 실패 바닥.
    K[i] ≤ oversold 는 본 검출기 영역이므로 여기서 기록하지 않는다.
  · margin: 경계까지 거리 (db: K − oversold, dt: overbought − K).
  · 구역 값은 STOCH_DOUBLE_PARAMS 재사용 — 중복 정의 금지.

순수 pandas/numpy, streamlit 무의존 — 테스트 가능.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import STOCH_DOUBLE_PARAMS, STOCH_NEAR_MISS_PARAMS, WAVE_LAYER_ROLES

KIND_DB_NEAR = "stoch_db_near"
KIND_DT_NEAR = "stoch_dt_near"

_KIND_META = {
    KIND_DB_NEAR: "쌍바닥 구역 니어미스",
    KIND_DT_NEAR: "쌍봉 구역 니어미스",
}


@dataclass(frozen=True)
class NearMissEvent:
    """니어미스 한 건. timestamp 는 확정 봉(극값 다음 봉)의 open_time."""

    timestamp: pd.Timestamp
    kind: str
    label: str
    layer: str          # 스토캐 레이어 label, 예: "(20,10,10)"
    extreme_ts: pd.Timestamp  # 극값 봉
    k_extreme: float    # 극값 봉의 %K
    zone: float         # 미달한 경계값 (oversold 또는 overbought)
    margin: float       # 경계까지 거리 (양수)


_FRAME_COLUMNS = [
    "timestamp", "kind", "label", "layer", "extreme_ts", "k_extreme", "zone", "margin",
]


def _merged_params(params: Optional[dict]) -> dict:
    merged = dict(STOCH_NEAR_MISS_PARAMS)
    if params:
        merged.update(params)
    return merged


def scan_near_miss_events(
    df: pd.DataFrame, params: Optional[dict] = None
) -> list[NearMissEvent]:
    """df 전 구간의 구역 니어미스를 시간순으로 반환.

    df 는 indicators.stochastic 이 계산한 stoch_k_{suffix} 컬럼을 가진 것이어야
    하며, 없는 레이어는 조용히 건너뛴다.
    """
    if df is None or df.empty:
        return []

    p = _merged_params(params)
    band = float(p["near_band"])
    oversold = float(STOCH_DOUBLE_PARAMS["oversold"])
    overbought = float(STOCH_DOUBLE_PARAMS["overbought"])

    events: list[NearMissEvent] = []
    for role in p.get("layer_roles", []):
        suffix = WAVE_LAYER_ROLES.get(role)
        if suffix is None:
            continue
        col = f"stoch_k_{suffix}"
        if col not in df.columns:
            continue
        k = df[col].astype(float).to_numpy()

        for i in range(1, len(k) - 1):
            prev, cur, nxt = k[i - 1], k[i], k[i + 1]
            if np.isnan(prev) or np.isnan(cur) or np.isnan(nxt):
                continue
            if prev > cur < nxt and oversold < cur <= oversold + band:
                kind, zone, margin = KIND_DB_NEAR, oversold, cur - oversold
            elif prev < cur > nxt and overbought - band <= cur < overbought:
                kind, zone, margin = KIND_DT_NEAR, overbought, overbought - cur
            else:
                continue
            events.append(NearMissEvent(
                timestamp=df.index[i + 1],
                kind=kind,
                label=_KIND_META[kind],
                layer=suffix,
                extreme_ts=df.index[i],
                k_extreme=float(cur),
                zone=zone,
                margin=float(margin),
            ))

    events.sort(key=lambda e: (e.timestamp, e.kind, e.layer))
    return events


def near_miss_to_frame(events: list[NearMissEvent]) -> pd.DataFrame:
    """이벤트 목록 -> 기록용 DataFrame."""
    if not events:
        return pd.DataFrame(columns=_FRAME_COLUMNS)
    return pd.DataFrame([asdict(e) for e in events], columns=_FRAME_COLUMNS)
