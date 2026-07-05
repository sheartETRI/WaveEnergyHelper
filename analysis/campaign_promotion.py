"""L2 기준 TF 승격 (v2) — PatternEvent → 기준 TF 승격 + 동시 확정 충돌 규칙.

확정 규칙(§3):
- 패턴 확정(clean 이평선 쌍바닥/쌍봉) → 해당 TF가 기준 TF, 패턴 방향이 캠페인 방향.
- 동시 확정 충돌: 복수 TF 동시 확정 시 상위 TF 우선([F1]). 하위 이벤트는 기각하지 않고
  "SUPPRESSED_BY_UPPER"로 저널 기록만 한다(사후 분석용).
- 반대 방향 충돌: 진행 중 캠페인과 반대 방향의 상위 TF 확정 → 기존 캠페인 CONFLICT 마킹
  (자동 청산 없음 — 현물, 판단은 사용자).

승격 게이트: S0(§5)은 "이평선 쌍바닥 확정(kind HL + 넥라인 돌파)"이므로 승격 구동자는
MA(이평선) 쌍바닥/쌍봉 중 clean="clean" 이벤트로 한정한다. 스토캐·삼중은 강화·조정판정용
(승격 구동자 아님). candidate(clean != clean)는 승격 불가.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from analysis.pattern_scanner import PatternEvent
from analysis.tf_ladder import ladder_index

# 승격 구동자 조건.
PROMOTER_SOURCE = "ma"
PROMOTER_PATTERNS = {"double_bottom", "double_top"}

# 동시 확정 판정 윈도(상위 TF 1봉 지속). 잠정 튜너블 — §10 인접, 김박사 조정 대상.
TF_DURATION = {
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
    "4d": pd.Timedelta(days=4),
    "2w": pd.Timedelta(days=14),
}

PROMOTED = "PROMOTED"
SUPPRESSED_BY_UPPER = "SUPPRESSED_BY_UPPER"


@dataclass
class PromotedSignal:
    symbol: str
    base_tf: str
    direction: str            # long | short
    status: str               # PROMOTED | SUPPRESSED_BY_UPPER
    promoted_bar: pd.Timestamp
    driver: PatternEvent      # 승격을 일으킨 확정 이벤트
    suppressed_by: Optional[str] = None   # 상위 TF (SUPPRESSED_BY_UPPER 시)
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "base_tf": self.base_tf,
            "direction": self.direction,
            "status": self.status,
            "promoted_bar": pd.Timestamp(self.promoted_bar),
            "driver_source": self.driver.source,
            "driver_layer": self.driver.ma_or_layer,
            "driver_kind": self.driver.kind,
            "suppressed_by": self.suppressed_by,
        }


def is_promotable(ev: PatternEvent) -> bool:
    """승격 구동자 자격: clean 이평선 쌍바닥/쌍봉만."""
    return (
        ev.source == PROMOTER_SOURCE
        and ev.kind_pattern in PROMOTER_PATTERNS
        and ev.clean == "clean"
    )


def _concurrency_window(tf: str) -> pd.Timedelta:
    return TF_DURATION.get(tf, pd.Timedelta(days=1))


def _find_upper_suppressor(
    ev: PatternEvent,
    promotable: List[PatternEvent],
) -> Optional[PatternEvent]:
    """ev를 억제하는 최상위 동시-확정 상위 TF 이벤트 (없으면 None).

    상위 = 사다리 인덱스가 엄격히 큰 TF. 동시 = |Δbar| ≤ 상위 TF 1봉.
    """
    li = ladder_index(ev.tf)
    if li is None:
        return None
    best: Optional[PatternEvent] = None
    best_idx = -1
    for f in promotable:
        if f is ev or f.symbol != ev.symbol:
            continue
        lf = ladder_index(f.tf)
        if lf is None or lf <= li:
            continue
        if abs(ev.confirmed_bar - f.confirmed_bar) <= _concurrency_window(f.tf):
            if lf > best_idx:
                best, best_idx = f, lf
    return best


def resolve_promotions(events: List[PatternEvent]) -> List[PromotedSignal]:
    """승격 가능 이벤트를 승격/억제로 판정. 상위 TF 동시 확정이 하위를 억제한다.

    억제된 이벤트도 기각하지 않고 SUPPRESSED_BY_UPPER로 반환(저널 기록용).
    """
    promotable = [e for e in events if is_promotable(e)]
    out: List[PromotedSignal] = []
    for ev in promotable:
        suppressor = _find_upper_suppressor(ev, promotable)
        if suppressor is None:
            out.append(
                PromotedSignal(
                    symbol=ev.symbol,
                    base_tf=ev.tf,
                    direction=ev.direction,
                    status=PROMOTED,
                    promoted_bar=ev.confirmed_bar,
                    driver=ev,
                )
            )
        else:
            out.append(
                PromotedSignal(
                    symbol=ev.symbol,
                    base_tf=ev.tf,
                    direction=ev.direction,
                    status=SUPPRESSED_BY_UPPER,
                    promoted_bar=ev.confirmed_bar,
                    driver=ev,
                    suppressed_by=suppressor.tf,
                    notes=[
                        f"상위 {suppressor.tf} {suppressor.direction} 동시 확정에 억제됨"
                    ],
                )
            )
    out.sort(key=lambda s: (s.promoted_bar, ladder_index(s.base_tf) or 0))
    return out


def is_opposing_upper_conflict(
    active_tf: str,
    active_direction: str,
    ev: PatternEvent,
) -> bool:
    """진행 중 캠페인(active_tf/direction)과 반대 방향의 상위 TF 확정인가.

    True면 기존 캠페인을 CONFLICT로 마킹(상태 기계). 자동 청산은 하지 않는다.
    상위 = 사다리 인덱스 엄격히 큰 TF. 동일 TF 반대 확정은 상태 기계 S7 소관.
    """
    if not is_promotable(ev) or ev.direction == active_direction:
        return False
    la = ladder_index(active_tf)
    le = ladder_index(ev.tf)
    return la is not None and le is not None and le > la


def promotions_to_dataframe(signals: List[PromotedSignal]) -> pd.DataFrame:
    cols = [
        "symbol", "base_tf", "direction", "status", "promoted_bar",
        "driver_source", "driver_layer", "driver_kind", "suppressed_by",
    ]
    if not signals:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([s.as_dict() for s in signals])[cols]
