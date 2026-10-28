"""--legacy-signals 전용 알림 구현. CLI에서 기존 공개 API도 재노출한다."""
from __future__ import annotations

import json
import logging
import os
from typing import Callable, Iterable, Optional

import pandas as pd

from analysis.alarm_signals import AlarmSignal, SEV_CONFIRMED, scan_alarm_signals
from data.binance import clear_klines_cache
from notify.closed_bars import closed_frame, served_from_stale_store
from notify.pushbullet import push_note
from notify.settings import SENT_KEEP, STATE_VERSION, TITLE_PREFIX
from utils.alarm_text import format_signal_line
from utils.time_display import KST_LABEL, to_kst

logger = logging.getLogger("push_alarms")


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
    """(예전 경로) 앱과 같은 공용 파이프라인(data.frames.load_frame). 폴링마다 OHLCV 캐시를 비워 최신 봉까지 받는다."""
    import data.frames as app
    clear_klines_cache()
    frame = app.load_frame(symbol, interval, with_macd=True)
    return None if served_from_stale_store(symbol, interval) else frame


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
