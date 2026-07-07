"""이평선 배열 맥락 분류기 (v2, 4차 위임 C) — 관측 태그 전용.

김박사 규칙("정배열이다가 모일 때 쌍봉, 역배열이다가 모일 때 쌍바닥")의 형식화.
원 발언대로 확정 규칙이 아니므로 **게이트로 사용 금지 — 저널 컬럼만**. 게이트 승격 가치는
저널 성적 분리(context_aligned군 vs 비정방향군) 후 김박사가 판단한다.

분류(각 TF·봉):
- bull_array(정배열): MA5>MA10>MA20>MA60  ·  bear_array(역배열): MA5<MA10<MA20<MA60  ·  그 외 mixed
- converging(모임): 정규화 스프레드(max−min)/close 가 상한 이하 AND window 전 대비 축소 추세

S0 정방향 정합(context_aligned):
- 쌍바닥(long): bear_array & converging → 정방향
- 쌍봉(short):  bull_array & converging → 정방향
- 그 외: 비정방향(False)

임계·창 크기는 config.ARRAY_CONTEXT_PARAMS 상수로 노출(김박사 조정 대상, 초기값 보수적).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from config.settings import ARRAY_CONTEXT_PARAMS

BULL_ARRAY = "bull_array"
BEAR_ARRAY = "bear_array"
MIXED = "mixed"


@dataclass
class ArrayContext:
    array: str                 # bull_array | bear_array | mixed
    converging: bool
    spread: Optional[float]    # (max−min)/close (정규화 이격)
    label: str                 # 예: "bear_array/converging"

    def as_tag(self) -> str:
        return self.label


def _ma_values(df: pd.DataFrame, pos: int, periods: List[int]) -> Optional[List[float]]:
    vals = []
    for p in periods:
        col = f"MA{p}"
        if col not in df.columns:
            return None
        v = df[col].iloc[pos]
        if v is None or pd.isna(v):
            return None
        vals.append(float(v))
    return vals


def classify_array(vals: List[float]) -> str:
    """CORE_MA 값 순서(5,10,20,60)로 정/역/혼합 배열 판정. 순서 목록은 짧은 MA→긴 MA."""
    if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
        return BULL_ARRAY   # 짧은 MA가 위 = 정배열
    if all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
        return BEAR_ARRAY   # 짧은 MA가 아래 = 역배열
    return MIXED


def _spread(df: pd.DataFrame, pos: int, periods: List[int]) -> Optional[float]:
    vals = _ma_values(df, pos, periods)
    if vals is None:
        return None
    close = df["close"].iloc[pos] if "close" in df.columns else None
    if close is None or pd.isna(close) or float(close) == 0.0:
        return None
    return (max(vals) - min(vals)) / abs(float(close))


def is_converging(df: pd.DataFrame, pos: int, params: dict = ARRAY_CONTEXT_PARAMS) -> bool:
    """모임(수렴): 현재 정규화 스프레드가 상한 이하이고 window 전보다 축소 추세."""
    periods = params["core_ma"]
    window = params["converge_window"]
    cur = _spread(df, pos, periods)
    if cur is None or cur > params["converge_spread_max"]:
        return False
    ref_pos = pos - window
    if ref_pos < 0:
        return False
    prev = _spread(df, ref_pos, periods)
    if prev is None:
        return False
    return cur <= prev * params["converge_shrink_ratio"]


def context_at(df: pd.DataFrame, pos: int, params: dict = ARRAY_CONTEXT_PARAMS) -> ArrayContext:
    """한 봉의 배열 맥락 태그 (관측 전용)."""
    periods = params["core_ma"]
    vals = _ma_values(df, pos, periods)
    if vals is None:
        return ArrayContext(array=MIXED, converging=False, spread=None, label="mixed/unknown")
    array = classify_array(vals)
    conv = is_converging(df, pos, params)
    spread = _spread(df, pos, periods)
    label = f"{array}/{'converging' if conv else 'stable'}"
    return ArrayContext(array=array, converging=conv, spread=spread, label=label)


def context_aligned(ctx: ArrayContext, direction: str) -> bool:
    """S0 정방향 정합: 역배열→모임+쌍바닥(long) 또는 정배열→모임+쌍봉(short)."""
    if not ctx.converging:
        return False
    if direction == "long":
        return ctx.array == BEAR_ARRAY
    if direction == "short":
        return ctx.array == BULL_ARRAY
    return False


def tag_s0(df: pd.DataFrame, pos: int, direction: str, params: dict = ARRAY_CONTEXT_PARAMS):
    """S0 봉의 (array_context 라벨, context_aligned bool) — 저널 기록용."""
    ctx = context_at(df, pos, params)
    return ctx.label, context_aligned(ctx, direction)
