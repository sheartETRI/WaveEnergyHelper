#!/usr/bin/env python
"""알람 Pushbullet 푸시 폴러 — 감시 목록(config.PUSH_WATCHLIST)을 주기적으로 받아 닫힌 봉의 새 확정 신호를 보낸다.

앱(main.py)은 자동 주기 갱신을 하지 않으므로 무인 알림은 이 스크립트가 맡는다. 검출·표시 코드는 import 만 한다
(main.load_frame · analysis.alarm_signals · display.alarm_panel.format_signal_line) — 제3의 구현 없음.

    python scripts/push_alarms.py --test            # 토큰 확인용 테스트 푸시 1건
    python scripts/push_alarms.py                   # 1회 순회(작업 스케줄러용) — 기본
    python scripts/push_alarms.py --loop 300        # 300초 격자로 반복(:01, :06, … — 봉 마감 직후, deploy/push_alarms.service)
    python scripts/push_alarms.py --dry-run         # 보낼 내용만 출력(전송·이력 기록 없음)

규칙
  · 닫힌 봉만 본다: 마지막 봉의 open_time + 간격 > 지금(UTC) 이면 진행 중 봉이므로 뺀다(신호가 뒤집힐 수 있음).
  · 신호 종류·형식은 알람 탭과 같다(scan_alarm_signals + format_signal_line). 기본은 확정 신호만(후보 제외).
  · 전송 이력 파일(config.PUSH_PARAMS["state_file"], 기본 pushbullet_state.json — .gitignore)에 보낸 신호 키를 적어
    같은 신호를 두 번 보내지 않는다. 대상별 마지막 처리 봉도 적어 두어, 폴러가 쉬었다 돌아오면 그 뒤 봉을 따라잡는다.
    이력이 없는 첫 실행은 최근 lookback_bars 봉만 본다(과거 알람 폭주 방지).
  · 같은 (심볼·TF·봉)의 신호는 푸시 1건으로 묶는다.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Callable, Iterable, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
import streamlit.logger  # noqa: E402

streamlit.logger.set_log_level("error")   # 런타임 없이 cache_data 를 쓰면 나오는 경고(ScriptRunContext·캐시) 억제

from analysis.alarm_signals import SEV_CONFIRMED, AlarmSignal, scan_alarm_signals  # noqa: E402
from config.settings import CUSTOM_INTERVALS, PUSH_PARAMS, PUSH_WATCHLIST  # noqa: E402
from display.alarm_panel import format_signal_line  # noqa: E402
from display.tz_label import KST_LABEL, to_kst  # noqa: E402
from notify.pushbullet import DEFAULT_TOKEN_PATH, push_note, read_token  # noqa: E402

logger = logging.getLogger("push_alarms")

STATE_VERSION = 1
SENT_KEEP = 5000          # 이력 파일에 남기는 최근 키 수


# ---------------------------------------------------------------- 닫힌 봉
_UNIT_KW = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def interval_delta(interval: str) -> pd.Timedelta:
    """Binance 네이티브 간격 문자열 → Timedelta ("1h","2h","4h","6h","1d","1w" 등). 커스텀 TF(2d·4d·2w)는 미지원."""
    unit, n = interval[-1], int(interval[:-1])
    if interval in CUSTOM_INTERVALS or unit not in _UNIT_KW:
        # 커스텀 TF 는 리샘플 라벨(right/left)이 섞여 있어 open_time + 간격으로 닫힘을 판정할 수 없다
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


# ---------------------------------------------------------------- 전송 이력
def signal_key(symbol: str, interval: str, s: AlarmSignal) -> str:
    return f"{symbol}|{interval}|{pd.Timestamp(s.timestamp).isoformat()}|{s.kind}|{s.layer or '-'}"


class PushState:
    """전송 이력(JSON): sent {키: 전송 시각}, last_bar {심볼|TF: 마지막 처리 봉 open_time}."""

    def __init__(self, path: str):
        self.path = path
        self.sent: dict = {}
        self.last_bar: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(raw, dict):
            self.sent = dict(raw.get("sent", {}))
            self.last_bar = dict(raw.get("last_bar", {}))

    def save(self) -> None:
        if len(self.sent) > SENT_KEEP:                    # 오래된 키부터 버린다(값 = 전송 시각)
            keep = sorted(self.sent.items(), key=lambda kv: kv[1])[-SENT_KEEP:]
            self.sent = dict(keep)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": STATE_VERSION, "sent": self.sent, "last_bar": self.last_bar}, fh,
                      ensure_ascii=False, indent=0)
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


# ---------------------------------------------------------------- 신호 선별 · 메시지
def select_signals(
    df: pd.DataFrame,
    signals: list[AlarmSignal],
    last_bar: Optional[pd.Timestamp],
    lookback_bars: int,
    include_candidates: bool,
) -> list[AlarmSignal]:
    """이번에 볼 신호: 마지막 처리 봉 이후(따라잡기), 이력이 없으면 최근 lookback_bars 봉. 후보는 옵션."""
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


def build_pushes(symbol: str, interval: str, df: pd.DataFrame, signals: list[AlarmSignal]) -> list[dict]:
    """같은 봉의 신호를 푸시 1건으로. [{"title", "body", "keys", "bar"}] 봉 시각 오름차순."""
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
        title = f"[WEH] {symbol} {interval} · {to_kst(bar):%m-%d %H:%M} {KST_LABEL}"
        pushes.append({"title": title, "body": body, "keys": [signal_key(symbol, interval, s) for s in group], "bar": bar})
    return pushes


# ---------------------------------------------------------------- 1회 순회
def default_loader(symbol: str, interval: str):
    """앱과 같은 파이프라인(main.load_frame). 폴링마다 OHLCV 캐시를 비워 최신 봉까지 받는다."""
    from data.binance import clear_klines_cache
    import main as app
    clear_klines_cache()
    return app.load_frame(symbol, interval, with_macd=True)


def run_once(
    targets: Iterable[tuple[str, str]],
    state: PushState,
    token: Optional[str],
    loader: Callable = default_loader,
    pusher: Callable = push_note,
    now: Optional[pd.Timestamp] = None,
    lookback_bars: int = 3,
    include_candidates: bool = False,
    dry_run: bool = False,
) -> dict:
    """감시 목록 1회 순회. 반환: {"pushed": n, "skipped": n, "failed": n, "errors": [...]}."""
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
    p = argparse.ArgumentParser(description="알람 Pushbullet 푸시 폴러 (WaveEnergyHelper)")
    p.add_argument("--loop", type=int, metavar="SEC", help="이 초 격자로 반복(기본: 1회 순회 후 종료)")
    p.add_argument("--offset", type=int, default=60, metavar="SEC",
                   help="--loop 격자의 정각 대비 오프셋 초(기본 60 — 봉 마감 직후 :01 에 실행)")
    p.add_argument("--test", action="store_true", help="테스트 푸시 1건 보내고 종료")
    p.add_argument("--dry-run", action="store_true", help="전송·이력 기록 없이 보낼 내용만 출력")
    p.add_argument("--symbols", nargs="+", help=f"감시 심볼 (기본 {PUSH_WATCHLIST['symbols']})")
    p.add_argument("--intervals", nargs="+", help=f"감시 TF (기본 {PUSH_WATCHLIST['intervals']})")
    p.add_argument("--include-candidates", action="store_true", help="후보(미확정) 신호도 보낸다")
    p.add_argument("--lookback", type=int, default=PUSH_PARAMS["lookback_bars"], help="이력 없는 첫 실행에 볼 최근 봉 수")
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

    token = read_token(args.token)
    if token is None and not args.dry_run:
        logger.error("토큰 파일이 없거나 비어 있습니다: %s (Pushbullet Access Token 한 줄)", args.token)
        return 2
    if args.test:
        ok = push_note(token, "[WEH] 테스트 푸시", "WaveEnergyHelper 알람 푸시 연결 확인")
        logger.info("테스트 푸시 %s", "성공" if ok else "실패")
        return 0 if ok else 1

    symbols = args.symbols or PUSH_WATCHLIST["symbols"]
    intervals = args.intervals or PUSH_WATCHLIST["intervals"]
    targets = [(s, i) for s in symbols for i in intervals]
    include_candidates = args.include_candidates or PUSH_PARAMS["include_candidates"]
    state = PushState(args.state)
    logger.info("감시 %d건: %s | 후보 %s | 이력 %s", len(targets), ", ".join(f"{s} {i}" for s, i in targets),
                "포함" if include_candidates else "제외", args.state)

    while True:
        stats = run_once(targets, state, token, lookback_bars=args.lookback,
                         include_candidates=include_candidates, dry_run=args.dry_run)
        logger.info("순회 완료 — 전송 %d · 중복 생략 %d · 실패 %d · 오류 %d",
                    stats["pushed"], stats["skipped"], stats["failed"], len(stats["errors"]))
        if not args.loop:
            return 0 if not stats["failed"] and not stats["errors"] else 1   # 스케줄러가 실패를 알 수 있게
        try:
            time.sleep(seconds_until_next_slot(time.time(), args.loop, args.offset))
        except KeyboardInterrupt:
            logger.info("중단")
            return 0


if __name__ == "__main__":
    sys.exit(main())
