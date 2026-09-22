"""발송 이력 (sent.json) — 중복 차단 · 30일 회전 · 최초 실행 폭탄 방지.

파일 형식: {"version": 1, "sent": {key: {"event_ts": ISO-UTC, "sent_at": ISO-UTC|null, "delivered": bool}},
             "kinds": {kind: 첫 스캔 ISO-UTC},
             "ledger": {"since": ISO-UTC, "rows": [행…]}}   ← 전방 ledger(notify.ledger). 회전 대상 아님.
key = "SYMBOL|tf|kind|YYYY-MM-DDTHH:MM:SSZ" (notify.events.event_key). "kinds" 는 알림 종류별 첫 배포 실행 기록
(없는 파일 = {} 로 읽음, 회전 대상 아님).

규칙
- 발송 성공 → 기록(delivered=true). 발송 실패 → 기록하지 않음(다음 실행 재시도).
- 최초 실행(이력에 발송 성공 기록이 하나도 없음) → 최근 INITIAL_RECENT_BARS 봉 이내에 확정된 이벤트만 발송 대상,
  나머지는 delivered=false 로 기록만 한다(폭탄 방지). '비어 있음' 을 '발송 성공 0건' 으로 읽는 이유: Secrets 미설정
  상태로 며칠 돌다가 Secrets 를 넣는 순간, 그동안 미발송·미기록으로 남은 이벤트가 한꺼번에 나가는 것을 막기 위해.
- **신규 알림 종류 도입 시 폭탄 방지(종류별, 위 전역 규칙과 별개)**: 그 종류를 처음 스캔하는 실행(``kinds`` 에 없고 sent 에도
  그 종류 키가 없음)에서는 그 종류의 이벤트를 **하나도 발송하지 않고** delivered=false 로 기록만 하며, 실행 끝에 ``kinds`` 에
  종류를 적는다. 다음 실행부터는 이력에 없는 새 이벤트만 발송한다. 종류에 이벤트가 없어도 ``kinds`` 는 적으므로 두 번째
  실행부터 정상 발송. 기존 종류(``kinds`` 필드 도입 전 이력)는 sent 키의 kind 조각으로 '이미 본 종류' 로 인정한다.
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
    return {"version": VERSION, "sent": {}, "kinds": {}, "ledger": {"since": None, "rows": []}}


def load(path: str) -> dict:
    if not os.path.isfile(path):
        return empty()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("sent"), dict):
        raise ValueError(f"malformed history: {path}")
    kinds = data.get("kinds", {})
    if not isinstance(kinds, dict):
        raise ValueError(f"malformed history (kinds): {path}")
    ledger = data.get("ledger") or {"since": None, "rows": []}
    if not isinstance(ledger, dict) or not isinstance(ledger.get("rows", []), list):
        raise ValueError(f"malformed history (ledger): {path}")
    return {"version": VERSION, "sent": dict(data["sent"]), "kinds": dict(kinds),
            "ledger": {"since": ledger.get("since"), "rows": list(ledger.get("rows", []))}}


def save(path: str, hist: dict) -> None:
    """원자적 저장(임시 파일 → 교체), 키 정렬 → git diff 가 안정적."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    ledger = hist.get("ledger") or {"since": None, "rows": []}
    payload = {"version": VERSION, "sent": dict(sorted(hist["sent"].items())),
               "kinds": dict(sorted(hist.get("kinds", {}).items())),
               "ledger": {"since": ledger.get("since"), "rows": list(ledger.get("rows", []))}}
    fd, tmp = tempfile.mkstemp(prefix=".sent-", suffix=".json", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def is_empty(hist: dict) -> bool:
    return not hist["sent"]


def key_kind(key: str) -> str:
    """키 "SYMBOL|tf|kind|ts" 의 kind 조각."""
    parts = key.split("|")
    return parts[2] if len(parts) >= 4 else ""


def nothing_delivered(hist: dict) -> bool:
    """발송 성공 기록이 하나도 없음 = 최초 실행 모드(최근 봉만 발송). 파일이 없거나 기록만 있는 경우 모두 해당."""
    return not any(v.get("delivered") for v in hist["sent"].values())


def kind_seen(hist: dict, kind: str) -> bool:
    """그 종류를 이미 스캔한 적이 있는가 — ``kinds`` 에 있거나(신규 형식) sent 에 그 종류 키가 하나라도 있으면(기존 이력) 참.
    거짓이면 이번이 그 종류의 첫 배포 실행 → 발송 없이 기록만."""
    return kind in hist.get("kinds", {}) or any(key_kind(k) == kind for k in hist["sent"])


def mark_kind(hist: dict, kind: str, now: Optional[pd.Timestamp] = None) -> bool:
    """종류를 '본 것' 으로 기록. 새로 적었으면 True."""
    if kind in hist.setdefault("kinds", {}):
        return False
    hist["kinds"][kind] = _iso(utcnow() if now is None else now)
    return True


def has(hist: dict, key: str) -> bool:
    return key in hist["sent"]


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(hist: dict, key: str, event_ts, *, delivered: bool, now: Optional[pd.Timestamp] = None) -> None:
    now = utcnow() if now is None else pd.Timestamp(now)
    hist["sent"][key] = {"event_ts": _iso(event_ts), "sent_at": _iso(now) if delivered else None,
                         "delivered": bool(delivered)}


def ledger_init(hist: dict, now: Optional[pd.Timestamp] = None) -> bool:
    """ledger 가 없으면 since = now 로 시작(그 이후 확정된 후보만 기록 — 과거 소급 금지). 새로 만들었으면 True."""
    led = hist.setdefault("ledger", {"since": None, "rows": []})
    if led.get("since"):
        return False
    led["since"] = _iso(utcnow() if now is None else now)
    led.setdefault("rows", [])
    return True


def _ledger_key(r: dict) -> str:
    """상승 행(기존) = symbol|tf|confirm_ts 그대로, 하방 행(direction == "down") = 뒤에 '|down'. notify.ledger.row_key 와 동일 규칙."""
    base = f"{r['symbol']}|{r['tf']}|{r['confirm_ts']}"
    return f"{base}|down" if r.get("direction") == "down" else base


def ledger_keys(hist: dict) -> set:
    return {_ledger_key(r) for r in hist.get("ledger", {}).get("rows", [])}


def ledger_append(hist: dict, rows, now: Optional[pd.Timestamp] = None) -> int:
    """확정봉 ≥ since 이고 아직 없는 행만 추가. 추가 건수 반환. since 없으면 아무것도 추가하지 않는다."""
    led = hist.get("ledger") or {}
    since = led.get("since")
    if not since:
        return 0
    since_ts = pd.Timestamp(since.rstrip("Z"))
    have = ledger_keys(hist)
    stamp = _iso(utcnow() if now is None else now)
    added = 0
    for r in sorted(rows, key=lambda r: (r["symbol"], r["tf"], r["confirm_ts"], r.get("direction") or "")):
        key = _ledger_key(r)
        if key in have or pd.Timestamp(r["confirm_ts"].rstrip("Z")) < since_ts:
            continue
        led["rows"].append({**r, "recorded_at": stamp})
        have.add(key)
        added += 1
    return added


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
    return {"total": len(hist["sent"]), "delivered": sum(1 for v in vals if v.get("delivered")),
            "kinds": len(hist.get("kinds", {})), "ledger": len(hist.get("ledger", {}).get("rows", []))}
