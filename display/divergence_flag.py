"""상승 다이버전스 플래그 — 단일 정의(docs/CANDIDATES_POST_2027_03 "다이버전스 플래그의 단일 정의 › 정의 고정", main 870f025).

- 지표: 대파동 스토캐스틱 슬로우 (20,10,10).
- 대상: 기존 검출기가 확정한 대파동 쌍바닥 중
  (1) 스토캐 저점: 두 번째 저점 > 첫 번째 저점 — 기존 검출기의 ``stoch_db_kind_{LARGE}`` == "HL" (확정봉에 기록됨) 을 소비.
  (2) 가격 저점: 각 스토캐 저점 **피봇 봉의 저가** 비교, 두 번째 < 첫 번째 — 첫 피봇 = 검출기가 기록한
      ``stoch_db_first_pos``, 둘째 피봇 = 확정봉 이하 마지막 스토캐 피봇 저점(계측 스크립트 probe 의 후보 p1·p2 그대로).
  둘 다 만족하면 상승 다이버전스("있음"). 새 파라미터 없음. 재구현 없음 — 후보·피봇 위치는 ``probe.extract_signals`` 의
  cands(p1, p2, confirm_pos) 를, 스토캐 저점 비교는 검출기 kind 컬럼을 그대로 쓴다.

앱 표시(60MA 전환 추적 표 '다이버전스' 열)·알림 메시지·전방 ledger 가 모두 이 함수를 공유한다.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

import validation.wave_ma60_turn_probe as probe

DIVERGENCE_COL = "다이버전스"
YES, NO = "있음", "없음"
KIND_HL = "HL"
KIND_COL = f"stoch_db_kind_{probe.LARGE}"


def divergence_flags(pipe: pd.DataFrame, sig: Optional[dict] = None) -> Dict[int, bool]:
    """확정봉 위치(confirm_pos) → 상승 다이버전스 여부. sig 를 주면 probe.extract_signals 재호출 없음."""
    if sig is None:
        sig = probe.extract_signals(pipe)
    kind = pipe[KIND_COL].to_numpy(dtype=object) if KIND_COL in pipe.columns else None
    low = pd.to_numeric(pipe["low"], errors="coerce").to_numpy(dtype=float)
    out: Dict[int, bool] = {}
    for cd in sig["cands"]:
        c, p1, p2 = int(cd["confirm_pos"]), int(cd["p1"]), int(cd["p2"])
        stoch_hl = kind is not None and kind[c] == KIND_HL
        price_ll = bool(low[p2] < low[p1])
        out[c] = bool(stoch_hl and price_ll)
    return out


def label(flag: Optional[bool]) -> str:
    return "" if flag is None else (YES if flag else NO)
