"""발송 판정 — 순수 함수 (main notify/scanner.py 의 plan() 을 그대로 이식, 전송 수단과 무관).

조치(우선순위 순): skip_old → skip_dup → record_only_disabled_kind → record_only_new_kind → record_only(전역 최초 실행) → send.
- skip_old: 이벤트 봉이 history.SCAN_MAX_AGE_DAYS 보다 오래됨(회전 창 밖 — 회전으로 지운 키가 재발송되지 않게).
- skip_dup: 이력에 있음 또는 같은 실행 안에 같은 키가 이미 있음(두 후보가 같은 봉에서 전환하면 키가 같다 — 한 키에 알림 1건).
- record_only_disabled_kind: 발송이 꺼진 종류(SEND_DISABLED_KINDS 설정) — 검출·이력 기록은 그대로, 발송만 하지 않는다.
  되살리려면 집합에서 빼면 되고, 이미 기록된 과거 건은 dup 으로 걸러져 그 뒤 새 이벤트만 나간다.
- record_only_new_kind: 그 종류를 처음 스캔하는 실행(신규 알림 종류 도입 폭탄 방지) — 그 종류는 이번 실행에서 발송 0건, 전량 기록.
- record_only: 전역 최초 실행 모드(이력에 발송 성공 기록이 없음)인데 최근 history.INITIAL_RECENT_BARS 봉 안에 알려지지 않은 이벤트.
종류별 규칙이 전역 규칙보다 먼저 적용된다(둘은 별개).
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from notify import events as EV
from notify import history as H

ACT_SEND, ACT_RECORD_ONLY, ACT_DUP, ACT_OLD = "send", "record_only", "skip_dup", "skip_old"
ACT_NEW_KIND = "record_only_new_kind"      # 그 종류의 첫 배포 실행 — 발송 없이 기록만
ACT_DISABLED = "record_only_disabled_kind" # 발송이 꺼진 종류 — 검출·이력 기록은 그대로, 발송만 하지 않음

# 발송 제외 종류(설정). "구조 훼손(LL)" 은 검출·화면·ledger 유지, 발송만 끔 (2026-09-23 김박사 지시, main 0fa2be6 승계).
SEND_DISABLED_KINDS: FrozenSet[str] = frozenset({EV.KIND_STRUCTURE_LL})


def plan(evs: Sequence[EV.Event], hist: dict, now: pd.Timestamp,
         disabled_kinds: Optional[Iterable[str]] = None) -> List[Tuple[EV.Event, str]]:
    """이벤트별 조치 결정 — 순수 함수. disabled_kinds 기본값은 호출 시점의 모듈 설정."""
    disabled = SEND_DISABLED_KINDS if disabled_kinds is None else frozenset(disabled_kinds)
    initial = H.nothing_delivered(hist)
    new_kinds = {k for k in EV.KINDS if not H.kind_seen(hist, k)}
    cutoff = pd.Timestamp(now) - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)
    out: List[Tuple[EV.Event, str]] = []
    seen: set = set()
    for ev in sorted(evs, key=lambda e: (e.symbol, e.tf, e.ts, e.kind)):
        if ev.ts < cutoff:
            out.append((ev, ACT_OLD))
        elif H.has(hist, ev.key) or ev.key in seen:
            out.append((ev, ACT_DUP))
        elif ev.kind in disabled:
            out.append((ev, ACT_DISABLED))
        elif ev.kind in new_kinds:
            out.append((ev, ACT_NEW_KIND))
        elif initial and ev.bars_since_known >= H.INITIAL_RECENT_BARS:
            out.append((ev, ACT_RECORD_ONLY))
        else:
            out.append((ev, ACT_SEND))
        seen.add(ev.key)
    return out
