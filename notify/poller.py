"""알림 순회·이력 이관·ledger 내보내기. CLI와 독립적인 호출 API."""
from __future__ import annotations
import json
import logging
import os
import shutil
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import pandas as pd
import tracking.ma60_turn as MT
from tracking.divergence import DIVERGENCE_COL, YES as DIV_YES
from notify import events as EV, history as H, ledger as LG, plan as PL
from notify.pushbullet import push_note
from notify.settings import PUSH_TARGETS, LEDGER_INTERVALS, STATE_LEGACY_SUFFIX, TITLE_PREFIX
from notify.closed_bars import default_fetch_frame
from notify.daily_summary import (daily_key, daily_summary_due, mark_daily_summary,
                                  build_daily_summary, daily_summary_title)
logger = logging.getLogger("push_alarms")

__all__ = ['is_legacy_state', 'legacy_state_path', 'load_history', 'cell_snapshot', 'scan_cells', 'split_title', 'run', 'export_ledger']

def is_legacy_state(data: dict) -> bool:
    """예전 push_alarms 형식: last_bar 필드가 있거나 sent 값이 문자열(전송 시각)."""
    if not isinstance(data, dict):
        return False
    if "last_bar" in data:
        return True
    sent = data.get("sent")
    return isinstance(sent, dict) and any(not isinstance(v, dict) for v in sent.values())


def legacy_state_path(state_path: str) -> str:
    root, ext = os.path.splitext(state_path)
    return root + STATE_LEGACY_SUFFIX if ext == ".json" else state_path + STATE_LEGACY_SUFFIX


def load_history(state_path: str) -> dict:
    """notify.history 형식으로 읽는다. 예전 형식이면 <state>.legacy.json 으로 옮기고(예전 경로가 계속 사용) 빈 이력으로 시작."""
    if os.path.isfile(state_path):
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if is_legacy_state(data):
            dest = legacy_state_path(state_path)
            if os.path.exists(dest):
                dest = f"{dest}.{int(time.time())}.bak"
            shutil.move(state_path, dest)
            logger.warning("예전 형식 이력 파일을 %s 로 옮기고 새 이력으로 시작합니다(첫 실행 폭탄 방지 규칙 적용)", dest)
            return H.empty()
    return H.load(state_path)


def cell_snapshot(pipe: pd.DataFrame, symbol: str, tf: str) -> dict:
    """일일 요약용 셀 상태 — 추적 표(상승 쪽 track_candidates, 최근 120봉)의 '대기 중' 행과 MA60 방향. 판정 없음.

    waiting: [{"elapsed": "7/20", "bars": 7, "divergence": bool}] — 표시 모듈의 MT.waiting_rows 그대로(앱 메트릭 '대기 중' 과 같은 함수).
    확정 시 '이미 상방' 후보는 표 상태가 '해당 없음 (이미 상방)' 이라 여기 들지 않고, 건수만 already_up(= MT.summarize 값)에 싣는다.
    ma60_dir: "↑"(MA60 상승) / "↓"(하락) / "→"(같음·미산출).
    """
    ma = pd.to_numeric(pipe["MA60"], errors="coerce") if "MA60" in pipe.columns else pd.Series(dtype=float)
    ma60_dir = "→"
    if len(ma) >= 2 and pd.notna(ma.iloc[-1]) and pd.notna(ma.iloc[-2]):
        ma60_dir = "↑" if ma.iloc[-1] > ma.iloc[-2] else "↓" if ma.iloc[-1] < ma.iloc[-2] else "→"
    frame = MT.track_candidates(pipe)
    waiting: List[dict] = []
    for d in MT.waiting_rows(frame).to_dict("records"):
        bars = d.get("_bars")
        waiting.append({"elapsed": str(d[MT.ELAPSED_COL]), "bars": int(bars) if bars is not None and not pd.isna(bars) else 0,
                        "divergence": d.get(DIVERGENCE_COL) == DIV_YES})
    return {"symbol": symbol, "tf": tf, "ma60_dir": ma60_dir, "waiting": waiting, "already_up": MT.summarize(frame)["already_up"]}


def scan_cells(symbols: Sequence[str], intervals: Sequence[str], fetch_frame: Callable[[str, str], Optional[pd.DataFrame]],
               ledger_intervals: Sequence[str] = ()) -> Tuple[List[EV.Event], List[str], List[dict], List[dict]]:
    """셀(심볼×TF) 순회. 실패 셀은 건너뛰고 사유를 모은다. 반환 (이벤트, 실패 사유, ledger 종료 행, 셀 스냅샷)."""
    evs: List[EV.Event] = []
    failures: List[str] = []
    ledger_rows: List[dict] = []
    snapshots: List[dict] = []
    for sym in symbols:
        for tf in intervals:
            try:
                pipe = fetch_frame(sym, tf)
                if pipe is None or pipe.empty:
                    raise RuntimeError("데이터 없음")
                cell = EV.scan_frame(pipe, sym, tf)
                fin = (LG.finished_rows(pipe, sym, tf) + LG.finished_rows_down(pipe, sym, tf)) if tf in ledger_intervals else []
                snap = cell_snapshot(pipe, sym, tf)
            except Exception as exc:                  # 대상 하나가 실패해도 나머지는 계속
                logger.error("cell %s %s failed: %s", sym, tf, exc)
                failures.append(f"{sym} {tf}: {exc}")
                continue
            logger.info("cell %s %s: closed bars=%d last=%s UTC events=%d ledger_finished=%d",
                        sym, tf, len(pipe), pipe.index[-1], len(cell), len(fin))
            evs.extend(cell)
            ledger_rows.extend(fin)
            snapshots.append(snap)
    return evs, failures, ledger_rows, snapshots


def split_title(text: str) -> Tuple[str, str]:
    """notify 메시지(여러 줄) → Pushbullet 제목·본문. 제목 = 첫 줄("[SYM TF] 종류 (미검증)") 에 [WEH] 접두."""
    head, _, body = text.partition("\n")
    return TITLE_PREFIX + head, body


def run(*, state_path: str, dry_run: bool, token: Optional[str],
        symbols: Sequence[str] = PUSH_TARGETS["symbols"], intervals: Sequence[str] = PUSH_TARGETS["intervals"],
        ledger_intervals: Sequence[str] = LEDGER_INTERVALS,
        fetch_frame: Optional[Callable[[str, str], Optional[pd.DataFrame]]] = None,
        pusher: Callable[[Optional[str], str, str], bool] = push_note,
        now: Optional[pd.Timestamp] = None,
        disabled_kinds: Optional[Iterable[str]] = None) -> Dict[str, object]:
    """1회 순회 — main notify/scanner.run 과 같은 흐름(전송 수단만 Pushbullet). 반환 요약 dict."""
    fetch_frame = default_fetch_frame if fetch_frame is None else fetch_frame
    now = H.utcnow() if now is None else pd.Timestamp(now)
    disabled = PL.SEND_DISABLED_KINDS if disabled_kinds is None else frozenset(disabled_kinds)
    hist = load_history(state_path)
    rotated = H.rotate(hist, now)
    initial = H.nothing_delivered(hist)
    new_kinds = [k for k in EV.KINDS if not H.kind_seen(hist, k)]
    logger.info("start now=%s UTC dry_run=%s state=%s history=%s rotated=%d token=%s",
                now.strftime("%Y-%m-%d %H:%M"), dry_run, state_path,
                ("%s — initial mode: recent %d bars only" % (H.counts(hist), H.INITIAL_RECENT_BARS)) if initial else H.counts(hist),
                rotated, "set" if token else "absent (no send)")
    if new_kinds:
        logger.info("first scan for kinds %s — record-only this run, sending from the next run", ",".join(new_kinds))
    if disabled:
        logger.info("sending disabled for kinds %s (SEND_DISABLED_KINDS) — detected and recorded, not sent", ",".join(sorted(disabled)))

    ledger_new = H.ledger_init(hist, now=now)            # 첫 실행: since = now (과거 소급 금지). dry-run 은 저장하지 않음.
    if ledger_new:
        logger.info("ledger started: since=%s — only candidates confirmed after this are recorded", hist["ledger"]["since"])
    evs, failures, ledger_rows, snapshots = scan_cells(symbols, intervals, fetch_frame, ledger_intervals=ledger_intervals)
    decisions = PL.plan(evs, hist, now, disabled_kinds=disabled)
    summary: Dict[str, object] = {
        "events": len(evs), "sent": 0, "send_failed": 0, "record_only": 0, "new_kind_record_only": 0,
        "disabled_record_only": 0, "disabled_kinds": sorted(disabled), "dup": 0, "old": 0, "would_send": 0,
        "not_sent_no_token": 0, "new_kinds": list(new_kinds), "failures": failures,
        "ledger_added": 0, "ledger_since": hist["ledger"]["since"], "changed": rotated > 0 or ledger_new,
        "by_kind": {}, "daily_summary": None, "daily_summary_sent": False,
    }
    by_kind: Dict[str, Dict[str, int]] = summary["by_kind"]  # type: ignore[assignment]

    for ev, act in decisions:
        by_kind.setdefault(ev.kind, {})
        by_kind[ev.kind][act] = by_kind[ev.kind].get(act, 0) + 1
        if act == PL.ACT_DUP:
            summary["dup"] += 1
            continue
        if act == PL.ACT_OLD:
            summary["old"] += 1
            continue
        if act in (PL.ACT_DISABLED, PL.ACT_NEW_KIND, PL.ACT_RECORD_ONLY):
            counter = {PL.ACT_DISABLED: "disabled_record_only", PL.ACT_NEW_KIND: "new_kind_record_only",
                       PL.ACT_RECORD_ONLY: "record_only"}[act]
            summary[counter] += 1
            logger.info("record-only (%s, known %d bars ago): %s", act, ev.bars_since_known, ev.key)
            if not dry_run:
                H.record(hist, ev.key, ev.ts, delivered=False, now=now)
                summary["changed"] = True
            continue
        text = EV.format_message(ev)
        title, body = split_title(text)
        if dry_run:
            summary["would_send"] += 1
            logger.info("[dry-run] would send %s\n%s", ev.key, text)
            continue
        if not token:
            summary["not_sent_no_token"] += 1
            logger.info("token absent — not sent, not recorded: %s\n%s", ev.key, text)
            continue
        if pusher(token, title, body):
            summary["sent"] += 1
            H.record(hist, ev.key, ev.ts, delivered=True, now=now)
            summary["changed"] = True
            logger.info("sent %s", ev.key)
        else:
            summary["send_failed"] += 1
            logger.warning("send failed (not recorded, retry next run) %s", ev.key)

    if not dry_run:
        for k in new_kinds:                  # 이벤트가 없던 종류도 '본 것' 으로 — 다음 실행부터 새 이벤트 발송
            summary["changed"] = H.mark_kind(hist, k, now=now) or summary["changed"]
    added = H.ledger_append(hist, ledger_rows, now=now) if not dry_run else 0
    summary["ledger_added"] = added
    if added:
        summary["changed"] = True
        logger.info("ledger: +%d rows (total %d) up=%s down=%s", added, len(hist["ledger"]["rows"]),
                    LG.summary(hist["ledger"]["rows"]), LG.summary(hist["ledger"]["rows"], direction=LG.DIRECTION_DOWN))
    elif dry_run:
        since = LG.since_of(hist)
        eligible = [r for r in ledger_rows if since is not None and pd.Timestamp(r["confirm_ts"].rstrip("Z")) >= since]
        logger.info("[dry-run] ledger: finished candidates=%d, eligible(after since)=%d — not recorded", len(ledger_rows), len(eligible))
    # 일일 요약 — 발송 뒤에 만들어 오늘 발송분까지 센다. dry-run 은 항상 샘플 1건을 출력(기록·전송 없음).
    n_cells = len(symbols) * len(intervals)
    if dry_run or daily_summary_due(hist, now):
        text = build_daily_summary(evs, snapshots, hist, now, n_cells, failures)
        summary["daily_summary"] = text
        title = daily_summary_title(now)
        if dry_run:
            logger.info("[dry-run] daily summary sample (%s)\n%s\n%s", "due" if daily_summary_due(hist, now) else "already sent today",
                        title, text)
        elif not token:
            logger.info("token absent — daily summary not sent: %s", title)
        elif pusher(token, title, text):
            mark_daily_summary(hist, now)
            summary["daily_summary_sent"] = True
            summary["changed"] = True
            logger.info("daily summary sent (%s)\n%s", daily_key(now), text)
        else:
            logger.warning("daily summary send failed — retry next cycle today")
    if summary["changed"] and not dry_run:
        H.save(state_path, hist)
        logger.info("history saved: %s", H.counts(hist))
    logger.info("done %s", {k: v for k, v in summary.items() if k not in ("failures", "by_kind", "daily_summary")})
    logger.info("by kind %s", by_kind)
    return summary


def export_ledger(state_path: str, out_path: str) -> int:
    hist = load_history(state_path)
    rows = hist.get("ledger", {}).get("rows", [])
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(LG.to_csv(rows))
    return len(rows)
