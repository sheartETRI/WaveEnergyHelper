#!/usr/bin/env python
"""알림 푸시 폴러 (apolo systemd, Pushbullet) — notify 스캐너(Actions)의 검출·판정·이력·ledger 를 이 경로로 통합한 판.

목표: apolo systemd 하나로 알림을 돌린다. 검출은 signal-alarm 의 표시 모듈을 **직접 import** 한다(체리픽·재구현 없음):
  notify.events → display.ma60_turn_tracker · ma60_down_tracker · trend_structure · divergence_flag (→ validation.wave_ma60_turn_probe)
데이터는 data/binance.py 경로(api.binance.com → 451/403 시 data-api.binance.vision 자동 대체) 그대로.

    python scripts/push_alarms.py --test                 # 토큰 확인용 테스트 푸시 1건
    python scripts/push_alarms.py                        # 1회 순회(작업 스케줄러용) — 기본
    python scripts/push_alarms.py --loop 300 --offset 60 # 300초 격자(:01, :06, …)로 반복 — deploy/push_alarms.service
    python scripts/push_alarms.py --dry-run              # 보낼 내용·판정만 출력(전송·이력 기록 없음)
    python scripts/push_alarms.py --export-ledger ledger.csv
    python scripts/push_alarms.py --legacy-signals       # (옵션, 기본 꺼짐) 예전 3층 확정·RSI·MACD 경로

대상(사전 고정, config/settings.py 무접촉 — INTEGRITY_FILES): BTCUSDT × 1h·2h·4h·6h·12h·1d·2d (PUSH_TARGETS).
알림 종류 = notify.events.KINDS (대파동 쌍바닥 후보 · 60MA 상방/하방 전환 · 구조 훼손 LL) — LL 은 notify.plan.SEND_DISABLED_KINDS
로 발송만 꺼짐. 메시지 형식은 notify.events.format_message 그대로("(미검증)", 권고 어휘 없음).

규칙
  · 닫힌 봉만: 마지막 봉의 open_time + 간격 > 지금(UTC) 이면 진행 중이므로 뺀다. 2d 는 1d 닫힌 봉을 config 의 리샘플 규칙
    (data.processor.resample_timeframe: label/closed=right, origin=start)로 합성하되, 창이 하루씩 밀려도 짝이 바뀌지 않게
    첫 1d 봉을 epoch 일수 짝수에 맞추고(align_base_frame) 2봉이 안 찬 2d 봉은 뺀다(resample_closed).
  · 이력 = notify.history 형식(pushbullet_state.json): 키 심볼|TF|종류|봉 UTC(하방·상승은 종류가 다르다), 30일 회전, ledger 동거.
    예전 형식 파일(last_bar 필드)은 pushbullet_state.legacy.json 으로 옮기고 새로 시작한다(예전 경로가 계속 쓴다).
  · 폭탄 방지 2단(notify.plan): 전역(발송 성공 이력 없음 → 최근 2봉만) + 종류별(처음 스캔하는 종류는 0건 발송·전량 기록).
  · ledger(notify.ledger): 상승·하방 후보 생애주기(direction 필드)를 이력 파일 "ledger" 에 기록 — 서버 로컬, 브랜치 푸시 없음.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
import streamlit.logger  # noqa: E402

streamlit.logger.set_log_level("error")   # 런타임 없이 cache_data 를 쓰면 나오는 경고(ScriptRunContext·캐시) 억제

from analysis.alarm_signals import SEV_CONFIRMED, AlarmSignal, scan_alarm_signals  # noqa: E402
from config.settings import CUSTOM_INTERVALS, PUSH_PARAMS, PUSH_WATCHLIST  # noqa: E402
from data.binance import clear_klines_cache, fetch_klines, get_auto_limit  # noqa: E402
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe  # noqa: E402
from display.alarm_panel import format_signal_line  # noqa: E402
from display.tz_label import KST_LABEL, to_kst  # noqa: E402
from indicators.moving_averages import add_moving_averages  # noqa: E402
from indicators.stochastic import add_stochastic_slow_layers  # noqa: E402
from notify import events as EV  # noqa: E402
from notify import history as H  # noqa: E402
from notify import ledger as LG  # noqa: E402
from notify import plan as PL  # noqa: E402
from notify.pushbullet import DEFAULT_TOKEN_PATH, push_note, read_token  # noqa: E402

logger = logging.getLogger("push_alarms")

# ---------------------------------------------------------------- 대상 (사전 고정 — config/settings.py 는 INTEGRITY 대상이라 무접촉)
PUSH_TARGETS: Dict[str, Tuple[str, ...]] = {
    "symbols": ("BTCUSDT",),
    "intervals": ("1h", "2h", "4h", "6h", "12h", "1d", "2d"),
}
LEDGER_INTERVALS: Tuple[str, ...] = PUSH_TARGETS["intervals"]      # ledger 는 대상 7셀 전부
STATE_LEGACY_SUFFIX = ".legacy.json"
TITLE_PREFIX = "[WEH] "

STATE_VERSION = 1         # (예전 경로) 이력 파일 버전
SENT_KEEP = 5000          # (예전 경로) 이력 파일에 남기는 최근 키 수


# ---------------------------------------------------------------- 닫힌 봉
_UNIT_KW = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
_EPOCH = pd.Timestamp("1970-01-01")


def interval_delta(interval: str) -> pd.Timedelta:
    """Binance 네이티브 간격 문자열 → Timedelta ("1h","2h","4h","6h","12h","1d","1w" 등). 커스텀 TF(2d·4d·2w)는 미지원."""
    unit, n = interval[-1], int(interval[:-1])
    if interval in CUSTOM_INTERVALS or unit not in _UNIT_KW:
        # 커스텀 TF 는 리샘플 라벨(right/left)이 섞여 있어 open_time + 간격으로 닫힘을 판정할 수 없다 → 베이스 TF 에서 판정
        raise ValueError(f"지원하지 않는 간격: {interval}")
    return pd.Timedelta(**{_UNIT_KW[unit]: n})


def closed_frame(df: Optional[pd.DataFrame], interval: str, now: Optional[pd.Timestamp] = None) -> Optional[pd.DataFrame]:
    """마지막 봉이 아직 열려 있으면(open_time + 간격 > now) 그 봉을 뺀 프레임. now 는 naive UTC(df 인덱스와 같은 기준)."""
    if df is None or df.empty:
        return df
    if now is None:
        now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    last_open = pd.Timestamp(df.index[-1])
    if last_open + interval_delta(interval) > now:
        return df.iloc[:-1]
    return df


def resample_factor(interval: str) -> int:
    """'Nd' 커스텀 TF 의 베이스(1d) 봉 수. 그 외 커스텀(3h·2w)은 이 폴러의 대상이 아니다."""
    if interval in CUSTOM_INTERVALS and interval.endswith("d") and get_fetch_interval(interval) == "1d":
        return int(interval[:-1])
    raise ValueError(f"리샘플 대상이 아닌 간격: {interval}")


def align_base_frame(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """config 리샘플 규칙(origin=start)은 첫 봉을 기준으로 묶으므로 fetch 창이 하루씩 밀리면 2d 짝이 바뀐다.
    첫 1d 봉의 epoch 일수를 factor 의 배수에 맞춰(앞 봉 최대 factor−1 개 버림) 창과 무관하게 같은 짝을 만든다."""
    factor = resample_factor(interval)
    if df is None or df.empty:
        return df
    days = (pd.Timestamp(df.index[0]).normalize() - _EPOCH).days
    drop = (-days) % factor
    return df.iloc[drop:]


def resample_closed(df_base_closed: pd.DataFrame, interval: str) -> pd.DataFrame:
    """닫힌 1d 봉 → 커스텀 'Nd' 봉 (config 규칙 그대로) — 정렬 뒤, 베이스 봉이 factor 개 안 찬 봉(첫 홀·마지막 진행분)은 뺀다."""
    factor = resample_factor(interval)
    aligned = align_base_frame(df_base_closed, interval)
    if aligned is None or aligned.empty:
        return aligned
    out = resample_timeframe(aligned, interval)
    # 봉당 베이스 봉 수 — resample_timeframe 과 같은 파라미터(data.processor 의 2d/4d 규칙: right/right/origin=start)
    counts = aligned["close"].resample(f"{factor}D", label="right", closed="right", origin="start").size()
    full = counts[counts >= factor].index
    return out.loc[out.index.isin(full)]


def load_closed_frame(symbol: str, interval: str, now: Optional[pd.Timestamp] = None,
                      fetch: Callable = fetch_klines) -> Optional[pd.DataFrame]:
    """앱과 같은 데이터 경로(data/binance → build_dataframe → 리샘플)로 **닫힌 봉만** 담은 지표 프레임.

    지표는 추적 모듈이 필요로 하는 MA·스토캐 층만(앱 load_frame 에서 MACD·RSI 를 뺀 것 — 알림 종류가 쓰지 않음).
    """
    base = get_fetch_interval(interval)
    raw = fetch(symbol, base, get_auto_limit(interval))
    df = build_dataframe(raw)
    if df is None or df.empty:
        return None
    df = closed_frame(df, base, now)
    if interval != base:
        df = resample_closed(df, interval)
    if df is None or df.empty:
        return None
    df = add_moving_averages(df.copy())
    return add_stochastic_slow_layers(df)


def default_fetch_frame(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """순회마다 OHLCV 캐시를 비워 최신 봉까지 받는다(data.binance cache_data ttl=600 우회)."""
    clear_klines_cache()
    return load_closed_frame(symbol, interval)


# ---------------------------------------------------------------- 이력 (notify.history 형식) · 예전 형식 이관
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


# ---------------------------------------------------------------- 순회
def scan_cells(symbols: Sequence[str], intervals: Sequence[str], fetch_frame: Callable[[str, str], Optional[pd.DataFrame]],
               ledger_intervals: Sequence[str] = ()) -> Tuple[List[EV.Event], List[str], List[dict]]:
    """셀(심볼×TF) 순회. 실패 셀은 건너뛰고 사유를 모은다. 반환 (이벤트, 실패 사유, ledger 종료 행)."""
    evs: List[EV.Event] = []
    failures: List[str] = []
    ledger_rows: List[dict] = []
    for sym in symbols:
        for tf in intervals:
            try:
                pipe = fetch_frame(sym, tf)
                if pipe is None or pipe.empty:
                    raise RuntimeError("데이터 없음")
                cell = EV.scan_frame(pipe, sym, tf)
                fin = (LG.finished_rows(pipe, sym, tf) + LG.finished_rows_down(pipe, sym, tf)) if tf in ledger_intervals else []
            except Exception as exc:                  # 대상 하나가 실패해도 나머지는 계속
                logger.error("cell %s %s failed: %s", sym, tf, exc)
                failures.append(f"{sym} {tf}: {exc}")
                continue
            logger.info("cell %s %s: closed bars=%d last=%s UTC events=%d ledger_finished=%d",
                        sym, tf, len(pipe), pipe.index[-1], len(cell), len(fin))
            evs.extend(cell)
            ledger_rows.extend(fin)
    return evs, failures, ledger_rows


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
    evs, failures, ledger_rows = scan_cells(symbols, intervals, fetch_frame, ledger_intervals=ledger_intervals)
    decisions = PL.plan(evs, hist, now, disabled_kinds=disabled)
    summary: Dict[str, object] = {
        "events": len(evs), "sent": 0, "send_failed": 0, "record_only": 0, "new_kind_record_only": 0,
        "disabled_record_only": 0, "disabled_kinds": sorted(disabled), "dup": 0, "old": 0, "would_send": 0,
        "not_sent_no_token": 0, "new_kinds": list(new_kinds), "failures": failures,
        "ledger_added": 0, "ledger_since": hist["ledger"]["since"], "changed": rotated > 0 or ledger_new,
        "by_kind": {},
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
    if summary["changed"] and not dry_run:
        H.save(state_path, hist)
        logger.info("history saved: %s", H.counts(hist))
    logger.info("done %s", {k: v for k, v in summary.items() if k not in ("failures", "by_kind")})
    logger.info("by kind %s", by_kind)
    return summary


def export_ledger(state_path: str, out_path: str) -> int:
    hist = load_history(state_path)
    rows = hist.get("ledger", {}).get("rows", [])
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(LG.to_csv(rows))
    return len(rows)


# ================================================================ 예전 경로 (옵션 --legacy-signals, 기본 꺼짐)
# 3층 스토캐 확정·RSI·MACD 6종을 알람 탭 형식으로 보내던 경로. 발송 종류에서 제외됐지만 코드는 옵션으로 남긴다.
def signal_key(symbol: str, interval: str, s: AlarmSignal) -> str:
    return f"{symbol}|{interval}|{pd.Timestamp(s.timestamp).isoformat()}|{s.kind}|{s.layer or '-'}"


class PushState:
    """(예전 경로) 전송 이력(JSON): sent {키: 전송 시각}, last_bar {심볼|TF: 마지막 처리 봉 open_time}."""

    def __init__(self, path: str):
        self.path = path
        self.sent: dict = {}
        self.last_bar: dict = {}
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self.sent = dict(raw.get("sent", {}))
            self.last_bar = dict(raw.get("last_bar", {}))
        except (OSError, ValueError) as exc:
            logger.warning("이력 파일을 읽지 못해 빈 이력으로 시작: %s (%s)", self.path, exc)

    def save(self) -> None:
        if len(self.sent) > SENT_KEEP:                    # 오래된 키부터 버린다(값 = 전송 시각)
            keep = sorted(self.sent.items(), key=lambda kv: kv[1])[-SENT_KEEP:]
            self.sent = dict(keep)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": STATE_VERSION, "sent": self.sent, "last_bar": self.last_bar}, fh,
                      ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def was_sent(self, key: str) -> bool:
        return key in self.sent

    def mark_sent(self, keys: Iterable[str], when: Optional[str] = None) -> None:
        stamp = when or pd.Timestamp.now(tz="UTC").isoformat()
        for key in keys:
            self.sent[key] = stamp

    def get_last_bar(self, symbol: str, interval: str) -> Optional[pd.Timestamp]:
        raw = self.last_bar.get(f"{symbol}|{interval}")
        return pd.Timestamp(raw) if raw else None

    def set_last_bar(self, symbol: str, interval: str, ts) -> None:
        self.last_bar[f"{symbol}|{interval}"] = pd.Timestamp(ts).isoformat()


def select_signals(df: pd.DataFrame, signals: list, last_bar: Optional[pd.Timestamp], lookback_bars: int,
                   include_candidates: bool) -> list:
    """(예전 경로) 이번에 볼 신호: 마지막 처리 봉 이후(따라잡기), 이력이 없으면 최근 lookback_bars 봉. 후보는 옵션."""
    if df is None or df.empty or not signals:
        return []
    if last_bar is not None:
        cutoff = last_bar + pd.Timedelta(microseconds=1)
    else:
        cutoff = pd.Timestamp(df.index[max(0, len(df) - max(int(lookback_bars), 1))])
    out = [s for s in signals if pd.Timestamp(s.timestamp) >= cutoff]
    if not include_candidates:
        out = [s for s in out if s.severity == SEV_CONFIRMED]
    return out


def build_pushes(symbol: str, interval: str, df: pd.DataFrame, signals: list) -> list:
    """(예전 경로) 같은 봉의 신호를 푸시 1건으로. [{"title", "body", "keys", "bar"}] 봉 시각 오름차순."""
    by_bar: dict = {}
    for s in signals:
        by_bar.setdefault(pd.Timestamp(s.timestamp), []).append(s)
    pushes = []
    for bar in sorted(by_bar):
        group = by_bar[bar]
        lines = [format_signal_line(s) for s in group]
        close = df["close"].get(bar) if "close" in df.columns else None
        tail = f"종가 {float(close):,.8g}" if close is not None and not pd.isna(close) else ""
        body = "\n".join(lines + ([tail] if tail else []))
        title = f"{TITLE_PREFIX}{symbol} {interval} · {to_kst(bar):%m-%d %H:%M} {KST_LABEL}"
        pushes.append({"title": title, "body": body, "keys": [signal_key(symbol, interval, s) for s in group], "bar": bar})
    return pushes


def default_loader(symbol: str, interval: str):
    """(예전 경로) 앱과 같은 파이프라인(main.load_frame). 폴링마다 OHLCV 캐시를 비워 최신 봉까지 받는다."""
    import main as app
    clear_klines_cache()
    return app.load_frame(symbol, interval, with_macd=True)


def run_once(targets: Iterable[Tuple[str, str]], state: PushState, token: Optional[str], loader: Callable = default_loader,
             pusher: Callable = push_note, now: Optional[pd.Timestamp] = None, lookback_bars: int = 3,
             include_candidates: bool = False, dry_run: bool = False) -> dict:
    """(예전 경로) 감시 목록 1회 순회. 반환: {"pushed": n, "skipped": n, "failed": n, "errors": [...]}."""
    stats = {"pushed": 0, "skipped": 0, "failed": 0, "errors": []}
    for symbol, interval in targets:
        try:
            df = closed_frame(loader(symbol, interval), interval, now)
        except Exception as exc:                  # 대상 하나가 실패해도 나머지는 계속
            logger.error("%s %s 적재 실패: %s", symbol, interval, exc)
            stats["errors"].append(f"{symbol} {interval}: {exc}")
            continue
        if df is None or df.empty:
            logger.warning("%s %s 데이터 없음", symbol, interval)
            stats["errors"].append(f"{symbol} {interval}: 데이터 없음")
            continue
        signals = scan_alarm_signals(df, include_candidates=include_candidates)
        picked = select_signals(df, signals, state.get_last_bar(symbol, interval), lookback_bars, include_candidates)
        for push in build_pushes(symbol, interval, df, picked):
            fresh = [k for k in push["keys"] if not state.was_sent(k)]
            if not fresh:
                stats["skipped"] += 1
                continue
            logger.info("%s\n%s", push["title"], push["body"])
            if dry_run:
                stats["pushed"] += 1
                continue
            if pusher(token, push["title"], push["body"]):
                state.mark_sent(fresh)
                stats["pushed"] += 1
            else:
                stats["failed"] += 1
        if not dry_run:
            state.set_last_bar(symbol, interval, df.index[-1])
    if not dry_run:
        state.save()
    return stats


# ---------------------------------------------------------------- 반복 격자
def seconds_until_next_slot(now_epoch: float, period: int, offset: int) -> float:
    """다음 실행까지 초 — 실행 시각은 epoch 기준 period 격자 + offset (period 300·offset 60 → 매시 :01, :06, …).

    봉은 정각에 닫히므로 정각이 아니라 offset 초 뒤에 깨어나야 마감 직후 봉을 닫힌 봉으로 잡는다.
    """
    period = max(int(period), 5)
    base = now_epoch - offset
    next_slot = (base // period + 1) * period + offset
    return max(next_slot - now_epoch, 1.0)


# ---------------------------------------------------------------- CLI
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
