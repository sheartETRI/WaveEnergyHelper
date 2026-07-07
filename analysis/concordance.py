"""상응 합치(concordance) 태그 (v2, 4차 위임 E-2) — 관측·저널 전용.

[F1] 상응 구조(김박사 확정): 가격계 신호 ↔ 오실레이터 신호의 급별 대응쌍.
  MA10 ↔ 스토캐 대파동(20,10,10)  ·  MA5 ↔ 중파동(10,5,5)  ·  캔들 ↔ 소파동(5,3,3).

각 S0/검출 이벤트에 대해 **상응 스토캐 층**에서 같은 방향 패턴 존재 여부를 판정한다.
합치 기준(김박사 확정): **방향만 같으면 진행 중(candidate/미확정) 패턴도 합치로 인정.**
저널에는 파트너 상태를 3분류로 기록: none | in_progress | confirmed.

★ 게이트·필터 사용 금지 — 저널 컬럼만. 스토캐 검출기가 이미 산출한 확정/후보 컬럼만 소비한다
  (stoch_{db,dt}_{suffix} = 확정, stoch_{db,dt}_candidate_{suffix} = 형성 중). 검출기 무수정.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import CONCORDANCE_PARAMS, WAVE_LAYER_ROLES

NONE = "none"
IN_PROGRESS = "in_progress"
CONFIRMED = "confirmed"
NA = "n/a"

_LARGE = WAVE_LAYER_ROLES["large"]   # (20,10,10)
_MID = WAVE_LAYER_ROLES["mid"]       # (10,5,5)
_SMALL = WAVE_LAYER_ROLES["small"]   # (5,3,3)

# 이벤트의 가격계 소스(ma_or_layer/캔들) → 상응 스토캐 층 suffix.
CORRESPONDENCE = {
    "MA10": _LARGE,
    "MA5": _MID,
    "candle": _SMALL,
}


def corresponding_suffix(ma_or_layer: str) -> Optional[str]:
    return CORRESPONDENCE.get(ma_or_layer)


def concordance_at(
    full_df: pd.DataFrame,
    ma_or_layer: str,
    direction: str,
    confirmed_pos: int,
    *,
    window: Optional[int] = None,
) -> str:
    """상응 층 합치 상태: confirmed > in_progress > none (창 [pos-W+1, pos]).

    상응 관계가 없는 급(MA20 등)은 'n/a'. 방향만 같으면 되며, 확정이 우선한다.
    """
    suffix = corresponding_suffix(ma_or_layer)
    if suffix is None or full_df is None or full_df.empty:
        return NA
    w = CONCORDANCE_PARAMS["window_bars"] if window is None else window
    pat = "db" if direction == "long" else "dt"
    conf_col = f"stoch_{pat}_{suffix}"
    cand_col = f"stoch_{pat}_candidate_{suffix}"
    pos = min(max(int(confirmed_pos), 0), len(full_df) - 1)
    lo = max(0, pos - w + 1)

    if conf_col in full_df.columns:
        seg = full_df[conf_col].iloc[lo:pos + 1]
        if seg.notna().any():
            return CONFIRMED
    if cand_col in full_df.columns:
        seg = full_df[cand_col].iloc[lo:pos + 1]
        if seg.notna().any():
            return IN_PROGRESS
    return NONE
