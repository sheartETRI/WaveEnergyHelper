"""하위 TF 파동 카운팅 (v2, §4 L3) — 관측 전용.

기준 TF 쌍바닥 → 하위 1단계 TF 파동이 3파로 전개한다는 [F5-e] 가설의 관측 계측.
하위 TF 대파동 스토캐(20,10,10) 피봇 시퀀스로 1파/2파/3파를 라벨링한다.

★ 관측·저널 기록만 한다. 상태 기계 전이에는 절대 사용하지 않는다(전이는 §5 MACD·패턴만).
카운팅과 상태 기계의 일치율을 저널로 측정한 뒤에야 승격 여부를 판단한다.

보수적 규칙: 캠페인 시작 이후 첫 대파동 저점 피봇을 기점(origin)으로, 이후 확정 피봇
개수 + 1을 현재 진행 파동으로 본다 (origin→고점=1파, →저점=2파, →고점=3파).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

from config.settings import WAVE_LAYER_ROLES

_LARGE = WAVE_LAYER_ROLES["large"]
_LOW_COL = f"stoch_pivot_low_{_LARGE}"
_HIGH_COL = f"stoch_pivot_high_{_LARGE}"

# 라벨 매핑. 3파 이상은 연장으로 표기.
_WAVE_LABEL = {1: "1파", 2: "2파", 3: "3파"}


def _label(n: int) -> str:
    return _WAVE_LABEL.get(n, "3파 이상(연장)")


@dataclass
class WaveCounting:
    lower_tf: str
    origin_ts: Optional[pd.Timestamp] = None
    pivots: List[Tuple[pd.Timestamp, str, float]] = field(default_factory=list)  # (ts, 'H'/'L', val)
    forming_wave: Optional[int] = None
    forming_label: str = "불가"       # 데이터 없음/하위 없음 시 "불가"(대체 안 함, §1)
    note: str = ""


def collect_large_pivots(
    lower_full_df: pd.DataFrame,
    start_ts: pd.Timestamp,
) -> List[Tuple[pd.Timestamp, str, float]]:
    """start_ts 이후 대파동 스토캐 저·고점 피봇을 시간순으로 수집."""
    if lower_full_df is None or lower_full_df.empty:
        return []
    if _LOW_COL not in lower_full_df.columns or _HIGH_COL not in lower_full_df.columns:
        return []
    out: List[Tuple[pd.Timestamp, str, float]] = []
    sub = lower_full_df.loc[lower_full_df.index >= start_ts]
    for ts, row in sub.iterrows():
        lo, hi = row.get(_LOW_COL), row.get(_HIGH_COL)
        if lo is not None and not pd.isna(lo):
            out.append((pd.Timestamp(ts), "L", float(lo)))
        if hi is not None and not pd.isna(hi):
            out.append((pd.Timestamp(ts), "H", float(hi)))
    out.sort(key=lambda x: x[0])
    return out


def count_lower_waves(
    lower_full_df: Optional[pd.DataFrame],
    start_ts: pd.Timestamp,
    lower_tf: Optional[str],
    at_ts: Optional[pd.Timestamp] = None,
) -> WaveCounting:
    """캠페인 시작(start_ts)부터 하위 TF 파동 카운팅. at_ts 지정 시 그 시점까지만."""
    if lower_tf is None:
        return WaveCounting(lower_tf="", forming_label="불가", note="하위 TF 없음(사다리 최하단)")
    wc = WaveCounting(lower_tf=lower_tf)
    pivots = collect_large_pivots(lower_full_df, start_ts)
    if at_ts is not None:
        pivots = [p for p in pivots if p[0] <= at_ts]
    if not pivots:
        wc.forming_label = "불가"
        wc.note = "대파동 피봇 없음/데이터 부족"
        return wc

    # 기점 = 첫 저점 피봇.
    origin_idx = next((i for i, p in enumerate(pivots) if p[1] == "L"), None)
    if origin_idx is None:
        wc.forming_label = "미정"
        wc.note = "기점(저점) 미형성"
        wc.pivots = pivots
        return wc

    wc.origin_ts = pivots[origin_idx][0]
    after = pivots[origin_idx + 1:]        # 기점 이후 확정 피봇
    wc.pivots = pivots
    wc.forming_wave = len(after) + 1        # 진행 중 파동
    wc.forming_label = _label(wc.forming_wave)
    return wc


def lower_wave_label_at(
    lower_full_df: Optional[pd.DataFrame],
    start_ts: pd.Timestamp,
    at_ts: pd.Timestamp,
    lower_tf: Optional[str],
) -> str:
    """특정 시점(예: ENTRY-2)의 하위 파동 라벨 — 저널 lower_wave_count_at_entry2용."""
    return count_lower_waves(lower_full_df, start_ts, lower_tf, at_ts=at_ts).forming_label
