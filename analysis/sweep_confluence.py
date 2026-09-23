"""스윕×쌍바닥 합류(confluence) 판정 — 트랩 완료 이벤트를 기록한다 (기록 전용).

같은 TF에서 스윕 재탈환(sweep_low_reclaim)과 스토캐 쌍바닥(stoch_db_{layer})이
가까운 봉에서 함께 확정되면 "뻔한 저점 사냥 후 바닥 구조 완성" — 급등 전 트랩의
원형(2026-09 BTCUSDT 6h, 저점 74,968)이다. 상단은 전부 미러(페이크 돌파 × 쌍봉).
docs/SPEC_SWEEP_RECLAIM.md §6 동결 스펙 상응.

검출 로직은 새로 만들지 않는다 — indicators.stochastic 이 기록한 확정 컬럼과
analysis.sweep_reclaim.scan_sweep_events 출력을 읽는 조인 레이어다(검출기 무수정,
alarm_signals 와 같은 태도). 게이팅·알람 발송·백테스트 판정은 하지 않는다.

판정 규칙:
  · gap = (쌍바닥/쌍봉 확정 봉) − (스윕 확정 봉), 봉 단위 부호 있음.
    |gap| ≤ max_gap_bars 이면 합류.
  · timestamp = 두 확정 봉 중 나중 봉 — 그 시점에 양쪽 모두 기지(lookahead 없음).
  · 스윕 이벤트 1건당 레이어별 최대 1건 — 창 내 확정이 여럿이면 |gap| 최소,
    동률이면 앞선 봉. 쌍바닥 확정 1건이 복수 스윕과 짝지어지는 것은 허용.
  · 붕괴/돌파 지속 이벤트는 참여하지 않는다.
  · 레이어 컬럼이 없으면 그 레이어만 조용히 건너뛴다.

순수 pandas, streamlit 무의존 — 테스트 가능.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Optional

import pandas as pd

from config.settings import SWEEP_CONFLUENCE_PARAMS, WAVE_LAYER_ROLES
from analysis.sweep_reclaim import (
    DIR_BEAR,
    DIR_BULL,
    KIND_SWEEP_HIGH_RECLAIM,
    KIND_SWEEP_LOW_RECLAIM,
    SweepEvent,
    scan_sweep_events,
)

KIND_CONFLUENCE_BULL = "sweep_db_confluence"
KIND_CONFLUENCE_BEAR = "sweep_dt_confluence"

_KIND_META = {
    KIND_CONFLUENCE_BULL: ("스윕·쌍바닥 합류", DIR_BULL),
    KIND_CONFLUENCE_BEAR: ("스윕·쌍봉 합류", DIR_BEAR),
}

# (참여 스윕 kind) -> (합류 kind, 스토캐 컬럼 접두사)
_JOIN_RULES = {
    KIND_SWEEP_LOW_RECLAIM: (KIND_CONFLUENCE_BULL, "stoch_db"),
    KIND_SWEEP_HIGH_RECLAIM: (KIND_CONFLUENCE_BEAR, "stoch_dt"),
}


@dataclass(frozen=True)
class ConfluenceEvent:
    """합류 한 건. timestamp 는 두 확정 봉 중 나중 봉의 open_time."""

    timestamp: pd.Timestamp
    kind: str
    label: str
    direction: str
    layer: str                     # 스토캐 레이어 label, 예: "(20,10,10)"
    gap_bars: int                  # (스토캐 확정 − 스윕 확정), 음수면 쌍바닥이 먼저
    sweep_ts: pd.Timestamp         # 스윕 재탈환 확정 봉
    stoch_ts: pd.Timestamp         # 쌍바닥/쌍봉 확정 봉
    db_kind: Optional[str]         # 검출기 kind 컬럼 값(HL/LL 등), 없으면 None
    level: float                   # 스윕 필드 승계
    depth_pct: float
    dwell_bars: int
    detail: str = ""


_FRAME_COLUMNS = [
    "timestamp", "kind", "label", "direction", "layer", "gap_bars",
    "sweep_ts", "stoch_ts", "db_kind", "level", "depth_pct", "dwell_bars", "detail",
]


def _merged_params(params: Optional[dict]) -> dict:
    merged = dict(SWEEP_CONFLUENCE_PARAMS)
    if params:
        merged.update(params)
    return merged


def _layer_suffixes(roles: Iterable[str]) -> list[str]:
    return [WAVE_LAYER_ROLES[r] for r in roles if r in WAVE_LAYER_ROLES]


def _confirmed_positions(df: pd.DataFrame, col: str) -> list[int]:
    """확정 컬럼(확정 봉에만 값)이 채워진 봉의 위치 목록."""
    if col not in df.columns:
        return []
    series = df[col]
    mask = series.notna().to_numpy()
    return [int(i) for i in mask.nonzero()[0]]


def scan_confluence_events(
    df: pd.DataFrame,
    params: Optional[dict] = None,
    sweep_events: Optional[list[SweepEvent]] = None,
    sweep_params: Optional[dict] = None,
) -> list[ConfluenceEvent]:
    """df 전 구간의 합류 이벤트를 시간순으로 반환.

    df 는 indicators.stochastic 검출 컬럼(stoch_db_{suffix} 등)을 이미 가진 것이어야
    하며, 없는 레이어는 조용히 건너뛴다. sweep_events 를 주면 그대로 쓰고(사전 계산
    재사용), 없으면 scan_sweep_events(df, sweep_params) 로 계산한다.
    """
    if df is None or df.empty:
        return []

    p = _merged_params(params)
    max_gap = int(p["max_gap_bars"])
    suffixes = _layer_suffixes(p.get("layer_roles", []))
    if not suffixes:
        return []

    if sweep_events is None:
        sweep_events = scan_sweep_events(df, sweep_params)
    if not sweep_events:
        return []

    pos_of_ts = {ts: i for i, ts in enumerate(df.index)}
    events: list[ConfluenceEvent] = []

    for sweep in sweep_events:
        rule = _JOIN_RULES.get(sweep.kind)
        if rule is None:
            continue  # 붕괴/돌파 지속은 합류에 참여하지 않는다.
        conf_kind, stoch_prefix = rule
        sweep_pos = pos_of_ts.get(sweep.timestamp)
        if sweep_pos is None:
            continue

        for suffix in suffixes:
            stoch_positions = _confirmed_positions(df, f"{stoch_prefix}_{suffix}")
            candidates = [q for q in stoch_positions if abs(q - sweep_pos) <= max_gap]
            if not candidates:
                continue
            # |gap| 최소, 동률이면 앞선 봉.
            best = min(candidates, key=lambda q: (abs(q - sweep_pos), q))

            kind_col = f"{stoch_prefix}_kind_{suffix}"
            db_kind = None
            if kind_col in df.columns:
                raw = df[kind_col].iloc[best]
                if raw is not None and not pd.isna(raw):
                    db_kind = str(raw)

            later = max(sweep_pos, best)
            label, direction = _KIND_META[conf_kind]
            events.append(ConfluenceEvent(
                timestamp=df.index[later],
                kind=conf_kind,
                label=label,
                direction=direction,
                layer=suffix,
                gap_bars=best - sweep_pos,
                sweep_ts=sweep.timestamp,
                stoch_ts=df.index[best],
                db_kind=db_kind,
                level=sweep.level,
                depth_pct=sweep.depth_pct,
                dwell_bars=sweep.dwell_bars,
                detail=sweep.detail,
            ))

    events.sort(key=lambda e: (e.timestamp, e.kind, e.layer))
    return events


def confluence_to_frame(events: list[ConfluenceEvent]) -> pd.DataFrame:
    """이벤트 목록 -> 기록용 DataFrame."""
    if not events:
        return pd.DataFrame(columns=_FRAME_COLUMNS)
    return pd.DataFrame([asdict(e) for e in events], columns=_FRAME_COLUMNS)
