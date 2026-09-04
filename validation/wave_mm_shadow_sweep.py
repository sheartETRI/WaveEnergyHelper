"""자금 관리 섀도 추적 실행기 — 기록 전용.

    python validation/wave_mm_shadow_sweep.py --record   # 사이드카 append (무개입)
    python validation/wave_mm_shadow_sweep.py --peek     # 현재 요약 (참고 표기)

헌장은 analysis/mm_shadow.py 모듈 docstring 에 동결돼 있다. 이 스크립트는
판정 로직을 갖지 않으며 임계값도 없다.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.mm_shadow import (
    VARIANTS,
    append_shadow,
    load_shadow,
    load_shadow_bars,
    load_shadow_events,
    shadow_path,
    simulate_variants,
    variant_summary,
)
from analysis.wave_align_gate_forward import REVIEW_DUE, TRACKING_START


def _fmt(v, d=6):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    return f"{v:.{d}f}"


def cmd_record() -> None:
    events = load_shadow_events()
    print(f"[shadow] F2-b 게이트 통과 전방 이벤트 {len(events)}건 "
          f"(추적 시작 {TRACKING_START.date()} 이후)")
    if events.empty:
        res = append_shadow(pd.DataFrame())
        print(f"[shadow] 기록할 이벤트 없음 — 사이드카 {res['total']}행 유지")
        return

    bars = load_shadow_bars(events)
    missing = [k for k, v in bars.items() if v is None or v.empty]
    if missing:
        raise SystemExit(f"OHLCV 캐시 없음: {missing}")

    rows = simulate_variants(events, bars)
    res = append_shadow(rows)
    print(f"[shadow] 산출 {len(rows)}행 → 기존 {res['existing']} / 추가 {res['appended']} "
          f"/ 합계 {res['total']}  ({shadow_path()})")
    print("[shadow] 원본 저널·F2-b 사이드카는 읽기만 했다 (무변형).")
    for r in variant_summary(load_shadow()):
        print(f"    {r['variant']:7s} trades={r.get('trades', 0)}")


def cmd_peek() -> None:
    shadow = load_shadow()
    print("[shadow] 참고 자료 — 판정이 아니며 규칙 권고가 아니다 (헌장 §1·§2).")
    print(f"[shadow] 1차 열람 예정: {REVIEW_DUE.date()} (F2-b 6개월 보고와 동시)")
    if shadow.empty:
        print("[shadow] 기록 없음")
        return
    print(f"{'variant':8s} {'trades':>7s} {'stop_rate':>10s} {'G':>12s} {'net_mean%':>11s}")
    for r in variant_summary(shadow):
        if not r.get("trades"):
            print(f"{r['variant']:8s} {0:>7d}")
            continue
        print(f"{r['variant']:8s} {r['trades']:>7d} {_fmt(r['stop_rate'], 4):>10s} "
              f"{_fmt(r['growth']):>12s} {_fmt(r['net_mean_pct'], 4):>11s}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--record":
        cmd_record()
    elif args and args[0] == "--peek":
        cmd_peek()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
