# analysis/structure.py
"""구간별 배열 판정기 — §6-④⑤(변곡점 추세전환) 선행 인프라.

`get_ma_alignment`(요약 표시용 일괄 판정)와 용도가 다르다. 여기서는 ④⑤의 전제인
'분할 배열'(예: 캔들-5-10-20-60 정배열 + 60-120-240 역배열)을 봉 단위로 식별한다.

구조 상태는 코드 분기가 아니라 데이터(STRUCTURE_STATES)로 선언한다. 코어 이평(5,10,20,
60,120,240)만 사용하며 40·80은 사용하지 않는다.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

ChainItem = Union[str, int]   # "close" 또는 코어 이평 기간(int)


def _value_at(row: pd.Series, item: ChainItem):
    if item == "close":
        return row.get("close")
    return row.get(f"MA{item}")


def is_chain_ordered(row: pd.Series, chain: List[ChainItem], descending: bool = True) -> Optional[bool]:
    """chain 원소들이 row에서 엄격한 내림차순(정배열)인지 판정.

    chain 원소: "close" 또는 코어 이평 기간(int).
      예) ["close", 5, 10, 20, 60] + descending=True
          → close > MA5 > MA10 > MA20 > MA60 인지
    descending=False 면 엄격한 오름차순(역배열 방향).
    어느 값이든 NaN이면 None(판단불가). 동치(=)는 정렬 불성립(False).
    원소가 0~1개면 비교 대상이 없으므로 True(공집합 체인은 항상 만족).
    """
    values = []
    for item in chain:
        value = _value_at(row, item)
        if value is None or pd.isna(value):
            return None
        values.append(float(value))

    for left, right in zip(values, values[1:]):
        if descending:
            if not (left > right):    # 엄격 부등호: 동치는 불성립
                return False
        else:
            if not (left < right):
                return False
    return True


# 구조 상태: (라벨, 정배열 체인, 역배열 체인)
#   정배열 체인 = is_chain_ordered(descending=True) 로 검사 (값이 위→아래로 감소)
#   역배열 체인 = is_chain_ordered(descending=False) 로 검사 (값이 위→아래로 증가)
# U(공매도 측, ④): 정배열이 위에서부터 무너지는 단계. D(공매수 측, ⑤): 완전 대칭.
STRUCTURE_STATES: List[Tuple[str, List[ChainItem], List[ChainItem]]] = [
    # U1~U3 — 캔들~단기는 정배열, 장기 꼬리는 역배열
    ("U1", ["close", 5, 10, 20, 60],           [60, 120, 240]),   # F6-4a 전제
    ("U2", ["close", 5, 10, 20, 60, 120],      [120, 240]),       # F6-4b 전제
    ("U3", ["close", 5, 10, 20, 60, 120, 240], []),               # F6-4c 전제 (완전 정배열)
    # D1~D3 — U의 완전 대칭: 캔들~단기는 역배열, 장기 꼬리는 정배열
    ("D1", [60, 120, 240],                     ["close", 5, 10, 20, 60]),        # F6-5a 전제
    ("D2", [120, 240],                         ["close", 5, 10, 20, 60, 120]),   # F6-5b 전제
    ("D3", [],                                 ["close", 5, 10, 20, 60, 120, 240]),  # F6-5c 전제 (완전 역배열)
]


def classify_structure_at(df: pd.DataFrame, pos: int) -> Optional[str]:
    """해당 봉(pos)에서 성립하는 구조 상태 라벨 반환. 없으면 None.

    상호 배타성은 구조상 보장된다(예: U1은 60<120, D1은 60>120을 요구). 방어적으로
    복수 매칭이 발생하면 예외 대신 None + 경고 로그를 남긴다.
    """
    if df is None or df.empty:
        return None
    try:
        row = df.iloc[pos]
    except (IndexError, KeyError):
        return None

    matches: List[str] = []
    for label, normal_chain, inverse_chain in STRUCTURE_STATES:
        normal_ok = is_chain_ordered(row, normal_chain, descending=True)
        inverse_ok = is_chain_ordered(row, inverse_chain, descending=False)
        if normal_ok is None or inverse_ok is None:
            continue  # NaN 포함 → 이 상태는 판단불가
        if normal_ok and inverse_ok:
            matches.append(label)

    if not matches:
        return None
    if len(matches) > 1:
        logger.warning("classify_structure_at: 복수 구조 상태 동시 매칭 %s @ pos=%s", matches, pos)
        return None
    return matches[0]
