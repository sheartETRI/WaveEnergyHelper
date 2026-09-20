"""알림 스캐너 실행 모듈 — GitHub Actions 15분 주기(.github/workflows/notify_scan.yml) 또는 수동.

    python -m notify.scanner --state notify/sent.json [--dry-run] [--symbols BTCUSDT ETHUSDT] [--tfs 1h 4h 1d]

흐름: 닫힌 봉 fetch(data-api.binance.vision) → 앱과 같은 지표 파이프라인(display.asof.run_indicator_pipeline)
→ 이벤트 2종(notify.events) → 이력 대조(notify.history) → 텔레그램(notify.telegram) → 이력 저장.
--dry-run: 발송·저장 없이 대상 목록만 로그. Secrets 부재: 발송 없이 로그만 남기고 정상 종료(rc 0).
종료 코드: 0 정상 / 1 셀 fetch·계산 실패 있음(다른 셀은 처리) / 2 이력 파일 손상.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:   # bare 모드(런타임 없음) 캐시 경고 억제 — 계산에 영향 없음. 실패해도 스캔은 진행.
    import streamlit.logger as _st_logger
    _st_logger.set_log_level("error")
except Exception:   # noqa: BLE001
    pass

from display.asof import run_indicator_pipeline  # noqa: E402
from notify import events as EV  # noqa: E402
from notify import history as H  # noqa: E402
from notify.history import utcnow  # noqa: E402
from notify import telegram as TG  # noqa: E402
from notify import fetch as F  # noqa: E402

log = logging.getLogger("notify")

SYMBOLS: Tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT")
TFS: Tuple[str, ...] = ("1h", "4h", "1d")
DEFAULT_STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent.json")

ACT_SEND, ACT_RECORD_ONLY, ACT_DUP, ACT_OLD = "send", "record_only", "skip_dup", "skip_old"


def build_pipe(bars: pd.DataFrame) -> pd.DataFrame:
    """앱·계측과 같은 파이프라인(MA → MA 패턴 → 스토캐 층). dispersion 은 불필요."""
    return run_indicator_pipeline(bars, include_dispersion=False)


def plan(evs: Sequence[EV.Event], hist: dict, now: pd.Timestamp) -> List[Tuple[EV.Event, str]]:
    """이벤트별 조치 결정 — 순수 함수.

    skip_old: 이벤트 봉이 SCAN_MAX_AGE_DAYS 보다 오래됨(회전 창 밖) · skip_dup: 이력에 있음 ·
    record_only: 최초 실행(이력 비어 있음)인데 최근 INITIAL_RECENT_BARS 봉 안에 확정되지 않음 · send: 발송 대상.
    """
    initial = H.is_empty(hist)
    cutoff = pd.Timestamp(now) - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)
    out: List[Tuple[EV.Event, str]] = []
    for ev in sorted(evs, key=lambda e: (e.symbol, e.tf, e.ts, e.kind)):
        if ev.ts < cutoff:
            out.append((ev, ACT_OLD))
        elif H.has(hist, ev.key):
            out.append((ev, ACT_DUP))
        elif initial and ev.bars_since_known >= H.INITIAL_RECENT_BARS:
            out.append((ev, ACT_RECORD_ONLY))
        else:
            out.append((ev, ACT_SEND))
    return out


def scan_cells(symbols: Sequence[str], tfs: Sequence[str],
               fetch: Callable[[str, str], pd.DataFrame]) -> Tuple[List[EV.Event], List[str]]:
    """셀(심볼×TF) 순회. 실패 셀은 건너뛰고 사유를 모은다."""
    evs: List[EV.Event] = []
    failures: List[str] = []
    for sym in symbols:
        for tf in tfs:
            try:
                bars = fetch(sym, tf)
                pipe = build_pipe(bars)
                cell = EV.scan_frame(pipe, sym, tf)
            except Exception as exc:   # noqa: BLE001 — 한 셀 실패가 다른 셀을 막지 않게
                failures.append(f"{sym} {tf}: {type(exc).__name__}: {str(exc)[:160]}")
                log.error("cell %s %s failed: %s: %s", sym, tf, type(exc).__name__, str(exc)[:160])
                continue
            log.info("cell %s %s: closed bars=%d last=%s UTC events=%d", sym, tf, len(bars),
                     bars.index[-1], len(cell))
            evs.extend(cell)
    return evs, failures


def run(*, state_path: str, dry_run: bool, symbols: Sequence[str] = SYMBOLS, tfs: Sequence[str] = TFS,
        fetch: Optional[Callable[[str, str], pd.DataFrame]] = None,
        send: Optional[Callable[[str, str, str], Tuple[bool, str]]] = None,
        env: Optional[dict] = None, now: Optional[pd.Timestamp] = None) -> Dict[str, object]:
    # 기본값은 호출 시점에 해석(모듈 속성) — 정의 시점 바인딩이면 테스트 대역이 실제 fetch/발송을 막지 못한다
    fetch = F.fetch_closed_bars if fetch is None else fetch
    send = TG.send_message if send is None else send
    now = utcnow() if now is None else pd.Timestamp(now)
    hist = H.load(state_path)
    rotated = H.rotate(hist, now)
    initial = H.is_empty(hist)          # 회전 후 기준 — plan() 과 같은 판정
    creds = TG.credentials(env)
    log.info("start now=%s UTC dry_run=%s state=%s history=%s rotated=%d secrets=%s",
             now.strftime("%Y-%m-%d %H:%M"), dry_run, state_path,
             "empty (initial run: recent %d bars only)" % H.INITIAL_RECENT_BARS if initial else H.counts(hist),
             rotated, "set" if creds else "absent (no send)")

    evs, failures = scan_cells(symbols, tfs, fetch)
    decisions = plan(evs, hist, now)
    summary = {"events": len(evs), "sent": 0, "send_failed": 0, "record_only": 0, "dup": 0, "old": 0,
               "would_send": 0, "not_sent_no_secrets": 0, "failures": failures, "changed": rotated > 0}

    for ev, act in decisions:
        if act == ACT_DUP:
            summary["dup"] += 1
            continue
        if act == ACT_OLD:
            summary["old"] += 1
            continue
        if act == ACT_RECORD_ONLY:
            summary["record_only"] += 1
            log.info("record-only (initial run, known %d bars ago): %s", ev.bars_since_known, ev.key)
            if not dry_run:
                H.record(hist, ev.key, ev.ts, delivered=False, now=now)
                summary["changed"] = True
            continue
        text = EV.format_message(ev)
        if dry_run:
            summary["would_send"] += 1
            log.info("[dry-run] would send %s\n%s", ev.key, text)
            continue
        if creds is None:
            summary["not_sent_no_secrets"] += 1
            log.info("secrets absent — not sent, not recorded: %s\n%s", ev.key, text)
            continue
        ok, reason = send(creds[0], creds[1], text)
        if ok:
            summary["sent"] += 1
            H.record(hist, ev.key, ev.ts, delivered=True, now=now)
            summary["changed"] = True
            log.info("sent %s", ev.key)
        else:
            summary["send_failed"] += 1
            log.warning("send failed (not recorded, retry next run) %s: %s", ev.key, reason)

    if summary["changed"] and not dry_run:
        H.save(state_path, hist)
        log.info("history saved: %s", H.counts(hist))
    log.info("done %s", {k: v for k, v in summary.items() if k != "failures"})
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="알림 스캐너 (미검증 관측 알림)")
    p.add_argument("--state", default=DEFAULT_STATE, help="발송 이력 JSON 경로")
    p.add_argument("--dry-run", action="store_true", help="발송·저장 없이 대상 목록만 로그")
    p.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    p.add_argument("--tfs", nargs="+", default=list(TFS))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    try:
        summary = run(state_path=a.state, dry_run=a.dry_run, symbols=a.symbols, tfs=a.tfs)
    except ValueError as exc:      # 이력 파일 손상
        log.error("%s", exc)
        return 2
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
