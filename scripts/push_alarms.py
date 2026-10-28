#!/usr/bin/env python
"""Pushbullet 폴러 CLI. 실행 옵션과 반복 주기만 조립한다.

기본 순회: notify.poller / 구형 알림: notify.legacy_signals
기존 공개 함수·상수는 명시적 import로 호환한다.
운영 안내: docs/운영_안내.md
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit.logger

# CLI로 직접 실행할 때만 로딩 중 캐시 안내 로그를 줄인다.
if __name__ == "__main__":
    streamlit.logger.set_log_level("error")

from config.settings import PUSH_PARAMS, PUSH_WATCHLIST
from notify.closed_bars import (
    align_base_frame, closed_frame, default_fetch_frame, interval_delta,
    load_closed_frame, resample_closed, resample_factor, served_from_stale_store,
)
from notify.daily_summary import (
    _when_label, already_note, build_daily_summary, daily_key, daily_summary_due,
    daily_summary_title, headline, mark_daily_summary, sent_counts_last_24h, tf_seconds,
)
from notify.legacy_signals import (
    PushState, build_pushes, default_loader, run_once, select_signals, signal_key,
)
from notify.poller import (
    cell_snapshot, export_ledger, is_legacy_state, legacy_state_path,
    load_history, run, scan_cells, split_title,
)
from notify.pushbullet import push_note, read_token
from notify.settings import (
    LEDGER_INTERVALS, PUSH_TARGETS, SENT_KEEP, STATE_LEGACY_SUFFIX, STATE_VERSION, TITLE_PREFIX,
)
from notify import events as EV, plan as PL

logger = logging.getLogger("push_alarms")


def seconds_until_next_slot(now_epoch: float, period: int, offset: int) -> float:
    """다음 실행까지 초 — 실행 시각은 epoch 기준 period 격자 + offset (period 300·offset 60 → 매시 :01, :06, …).

    봉은 정각에 닫히므로 정각이 아니라 offset 초 뒤에 깨어나야 마감 직후 봉을 닫힌 봉으로 잡는다.
    """
    period = max(int(period), 5)
    base = now_epoch - offset
    next_slot = (base // period + 1) * period + offset
    return max(next_slot - now_epoch, 1.0)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="알림 Pushbullet 푸시 폴러 (WaveEnergyHelper — notify 스캐너 통합판)")
    p.add_argument("--loop", type=int, metavar="SEC", help="이 초 격자로 반복(기본: 1회 순회 후 종료)")
    p.add_argument("--offset", type=int, default=60, metavar="SEC",
                   help="--loop 격자의 정각 대비 오프셋 초(기본 60 — 봉 마감 직후 :01 에 실행)")
    p.add_argument("--test", action="store_true", help="테스트 푸시 1건 보내고 종료")
    p.add_argument("--dry-run", action="store_true", help="전송·이력 기록 없이 판정과 보낼 내용만 출력")
    p.add_argument("--symbols", nargs="+", help=f"감시 심볼 (기본 {list(PUSH_TARGETS['symbols'])})")
    p.add_argument("--intervals", nargs="+", help=f"감시 TF (기본 {list(PUSH_TARGETS['intervals'])})")
    p.add_argument("--export-ledger", metavar="CSV", help="이력 파일의 ledger 를 CSV 로 내보내고 종료")
    p.add_argument("--legacy-signals", action="store_true",
                   help="(옵션, 기본 꺼짐) 예전 경로 — 3층 확정·RSI·MACD 를 알람 탭 형식으로. 이력은 <state>.legacy.json")
    p.add_argument("--include-candidates", action="store_true", help="(예전 경로) 후보(미확정) 신호도 보낸다")
    p.add_argument("--lookback", type=int, default=PUSH_PARAMS["lookback_bars"], help="(예전 경로) 이력 없는 첫 실행에 볼 최근 봉 수")
    p.add_argument("--token", default=os.path.join(ROOT, PUSH_PARAMS["token_file"]), help="토큰 파일 경로")
    p.add_argument("--state", default=os.path.join(ROOT, PUSH_PARAMS["state_file"]), help="전송 이력 파일 경로")
    p.add_argument("--log", help="로그 파일(지정 시 파일에도 기록)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    streamlit.logger.set_log_level("error")
    handlers = [logging.StreamHandler(sys.stdout)]
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)

    if args.export_ledger:
        n = export_ledger(args.state, args.export_ledger)
        logger.info("ledger %d rows → %s", n, args.export_ledger)
        return 0

    token = read_token(args.token)
    if token is None and not args.dry_run:
        logger.error("토큰 파일이 없거나 비어 있습니다: %s (Pushbullet Access Token 한 줄)", args.token)
        return 2
    if args.test:
        ok = push_note(token, "[WEH] 테스트 푸시", "WaveEnergyHelper 알림 푸시 연결 확인")
        logger.info("테스트 푸시 %s", "성공" if ok else "실패")
        return 0 if ok else 1

    if args.legacy_signals:
        symbols = args.symbols or PUSH_WATCHLIST["symbols"]
        intervals = args.intervals or PUSH_WATCHLIST["intervals"]
        targets = [(s, i) for s in symbols for i in intervals]
        include_candidates = args.include_candidates or PUSH_PARAMS["include_candidates"]
        state = PushState(legacy_state_path(args.state))
        logger.info("[legacy] 감시 %d건: %s | 후보 %s | 이력 %s", len(targets), ", ".join(f"{s} {i}" for s, i in targets),
                    "포함" if include_candidates else "제외", state.path)
        while True:
            stats = run_once(targets, state, token, lookback_bars=args.lookback,
                             include_candidates=include_candidates, dry_run=args.dry_run)
            logger.info("순회 완료 — 전송 %d · 중복 생략 %d · 실패 %d · 오류 %d",
                        stats["pushed"], stats["skipped"], stats["failed"], len(stats["errors"]))
            if not args.loop:
                return 0 if not stats["failed"] and not stats["errors"] else 1
            try:
                time.sleep(seconds_until_next_slot(time.time(), args.loop, args.offset))
            except KeyboardInterrupt:
                logger.info("중단")
                return 0

    symbols = tuple(args.symbols or PUSH_TARGETS["symbols"])
    intervals = tuple(args.intervals or PUSH_TARGETS["intervals"])
    logger.info("감시 %d셀: %s | 종류 %s (발송 제외 %s) | 이력 %s", len(symbols) * len(intervals),
                ", ".join(f"{s} {i}" for s in symbols for i in intervals), ",".join(EV.KINDS),
                ",".join(sorted(PL.SEND_DISABLED_KINDS)) or "-", args.state)
    while True:
        summary = run(state_path=args.state, dry_run=args.dry_run, token=token, symbols=symbols, intervals=intervals,
                      ledger_intervals=intervals)
        if not args.loop:
            return 0 if not summary["send_failed"] and not summary["failures"] else 1   # 스케줄러가 실패를 알 수 있게
        try:
            time.sleep(seconds_until_next_slot(time.time(), args.loop, args.offset))
        except KeyboardInterrupt:
            logger.info("중단")
            return 0


if __name__ == "__main__":
    sys.exit(main())
