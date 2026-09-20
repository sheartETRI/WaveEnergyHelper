"""발송 이력 (sent.json) — 중복 차단 · 30일 회전 · 최초 실행 폭탄 방지.

파일 형식: {"version": 1, "sent": {key: {"event_ts": ISO-UTC, "sent_at": ISO-UTC|null, "delivered": bool}}}
key = "SYMBOL|tf|kind|YYYY-MM-DDTHH:MM:SSZ" (notify.events.event_key).

규칙
- 발송 성공 → 기록(delivered=true). 발송 실패 → 기록하지 않음(다음 실행 재시도).
- 최초 실행(이력에 발송 성공 기록이 하나도 없음) → 최근 INITIAL_RECENT_BARS 봉 이내에 확정된 이벤트만 발송 대상,
  나머지는 delivered=false 로 기록만 한다(폭탄 방지). '비어 있음' 을 '발송 성공 0건' 으로 읽는 이유: Secrets 미설정
  상태로 며칠 돌다가 Secrets 를 넣는 순간, 그동안 미발송·미기록으로 남은 이벤트가 한꺼번에 나가는 것을 막기 위해.
- 이벤트 봉이 RETENTION_DAYS 보다 오래되면 회전(삭제). 스캔은 SCAN_MAX_AGE_DAYS(< RETENTION_DAYS) 안의 이벤트만
  보므로 회전으로 지운 키가 다시 발송되는 일은 없다.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Optional

import pandas as pd

VERSION = 1
RETENTION_DAYS = 30
SCAN_MAX_AGE_DAYS = 20          # RETENTION_DAYS 보다 짧아야 한다(회전 후 재발송 방지)
INITIAL_RECENT_BARS = 2         # 이력이 비어 있으면 최근 2봉 이내 확정분만 발송

assert SCAN_MAX_AGE_DAYS < RETENTION_DAYS


def utcnow() -> pd.Timestamp:
    """naive UTC 현재 시각 (프레임 인덱스와 같은 규약)."""
    return pd.Timestamp.now("UTC").tz_localize(None)


def empty() -> dict:
    return {"version": VERSION, "sent": {}}


def load(path: str) -> dict:
    if not os.path.isfile(path):
        return empty()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("sent"), dict):
        raise ValueError(f"malformed history: {path}")
    return {"version": VERSION, "sent": dict(data["sent"])}


def save(path: str, hist: dict) -> None:
    """원자적 저장(임시 파일 → 교체), 키 정렬 → git diff 가 안정적."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    payload = {"version": VERSION, "sent": dict(sorted(hist["sent"].items()))}
    fd, tmp = tempfile.mkstemp(prefix=".sent-", suffix=".json", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def is_empty(hist: dict) -> bool:
    return not hist["sent"]


def nothing_delivered(hist: dict) -> bool:
    """발송 성공 기록이 하나도 없음 = 최초 실행 모드(최근 봉만 발송). 파일이 없거나 기록만 있는 경우 모두 해당."""
    return not any(v.get("delivered") for v in hist["sent"].values())


def has(hist: dict, key: str) -> bool:
    return key in hist["sent"]


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(hist: dict, key: str, event_ts, *, delivered: bool, now: Optional[pd.Timestamp] = None) -> None:
    now = utcnow() if now is None else pd.Timestamp(now)
    hist["sent"][key] = {"event_ts": _iso(event_ts), "sent_at": _iso(now) if delivered else None,
                         "delivered": bool(delivered)}


def rotate(hist: dict, now: Optional[pd.Timestamp] = None, days: int = RETENTION_DAYS) -> int:
    """이벤트 봉이 now − days 보다 오래된 키 삭제. 삭제 건수 반환."""
    now = utcnow() if now is None else pd.Timestamp(now)
    cutoff = now - pd.Timedelta(days=days)
    stale = [k for k, v in hist["sent"].items() if pd.Timestamp(v["event_ts"].rstrip("Z")) < cutoff]
    for k in stale:
        del hist["sent"][k]
    return len(stale)


def counts(hist: dict) -> Dict[str, int]:
    vals = hist["sent"].values()
    return {"total": len(hist["sent"]), "delivered": sum(1 for v in vals if v.get("delivered"))}
