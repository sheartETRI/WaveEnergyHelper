"""Verdict stability 관측 레이어 — 엔진/UI/CSV 변경 없음.

confirm-bars 스무딩과 family grouping만 제공.
"""
from __future__ import annotations

from typing import Iterable, Sequence

BUY_FAMILY = "BUY_FAMILY"
SELL_FAMILY = "SELL_FAMILY"
NEUTRAL = "NEUTRAL"

FAMILY_ORDER = (BUY_FAMILY, SELL_FAMILY, NEUTRAL)

FAMILY_COLORS = {
    BUY_FAMILY: "#c8e6c9",
    SELL_FAMILY: "#ffcdd2",
    NEUTRAL: "#eeeeee",
}

_BUY_CATS = frozenset({"매수유효", "매수대기", "매수계열기타"})
_SELL_CATS = frozenset({"매도유효", "매도대기", "하락지속"})

CONFIRM_BAR_VARIANTS = (2, 3, 5)


def map_verdict_family(category: str) -> str:
    """카테고리 → BUY_FAMILY / SELL_FAMILY / NEUTRAL."""
    if category in _BUY_CATS:
        return BUY_FAMILY
    if category in _SELL_CATS:
        return SELL_FAMILY
    return NEUTRAL


def _runs(seq: Sequence) -> list[tuple[object, int]]:
    if not seq:
        return []
    out: list[tuple[object, int]] = []
    cur = seq[0]
    n = 1
    for v in seq[1:]:
        if v == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = v, 1
    out.append((cur, n))
    return out


def _expand_runs(runs: list[tuple[object, int]]) -> list:
    out: list = []
    for val, n in runs:
        out.extend([val] * n)
    return out


def smooth_verdict(seq: Sequence, confirm_bars: int) -> list:
    """짧은 run(< confirm_bars)을 양쪽 동일 이웃에 끼인 경우 제거.

    예: A A B A A, confirm=3 → A A A A A
        A A B B B A, confirm=3 → A A B B B A (B≥3, 끝 A는 edge 유지)
    """
    if confirm_bars <= 1 or len(seq) <= 1:
        return list(seq)

    result = list(seq)
    while True:
        runs = _runs(result)
        if len(runs) <= 1:
            break
        changed = False
        new_runs: list[tuple[object, int]] = []
        for i, (val, length) in enumerate(runs):
            if length >= confirm_bars:
                new_runs.append((val, length))
                continue
            left = runs[i - 1][0] if i > 0 else None
            right = runs[i + 1][0] if i + 1 < len(runs) else None
            if left is not None and right is not None and left == right and left != val:
                new_runs.append((left, length))
                changed = True
            else:
                new_runs.append((val, length))
        if not changed:
            break
        merged: list[tuple[object, int]] = []
        for val, length in new_runs:
            if merged and merged[-1][0] == val:
                merged[-1] = (val, merged[-1][1] + length)
            else:
                merged.append((val, length))
        result = _expand_runs(merged)
    return result


def enrich_timeline_stability(timeline) -> "pd.DataFrame":
    """타임라인 복사본에 smoothed / family 컬럼 추가 (원본 불변)."""
    import pandas as pd

    df = timeline.copy()
    cats = df["category"].tolist()

    df["family"] = [map_verdict_family(c) for c in cats]

    for n in CONFIRM_BAR_VARIANTS:
        df[f"verdict_smoothed_{n}"] = smooth_verdict(cats, n)
        fam = df["family"].tolist()
        df[f"family_smoothed_{n}"] = smooth_verdict(fam, n)

    return df
