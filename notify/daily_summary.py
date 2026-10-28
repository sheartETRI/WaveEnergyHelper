"""수집한 이벤트·스냅샷으로 만드는 일일 요약. 수신·발송·화면 렌더링 없음."""
from __future__ import annotations
from typing import Dict, Sequence, Tuple
import pandas as pd
from config.settings import CUSTOM_INTERVAL_BASE
import tracking.ma60_turn as MT
import tracking.ma60_down as MD
from utils.time_display import to_kst
from notify import events as EV, history as H
from notify.closed_bars import interval_delta
from notify.settings import TITLE_PREFIX
UNVERIFIED = EV.UNVERIFIED

__all__ = ['already_note', 'tf_seconds', 'daily_key', 'daily_summary_due', 'mark_daily_summary', 'sent_counts_last_24h', 'headline', 'build_daily_summary', 'daily_summary_title']

SUMMARY_TITLE = "일일 요약"

SUMMARY_NONE = "특이 사항 없음"

SUMMARY_LOOKBACK = pd.Timedelta(hours=24)

_TURN_LABEL = {EV.KIND_MA60_TURN: "60MA 상방 전환", EV.KIND_MA60_DOWN: "60MA 하방 전환"}

_DIV_LABEL = {EV.KIND_MA60_TURN: ("다이버전스 있음", "다이버전스 없음"),
              EV.KIND_MA60_DOWN: ("하락 다이버전스 있음", "하락 다이버전스 없음")}

_ALREADY_LABEL: Tuple[Tuple[str, str], ...] = (("already_up", MT.ALREADY_UP_MARK), ("already_down", MD.ALREADY_DOWN_MARK))


def already_note(snapshots: Sequence[dict]) -> str:
    """'이미 상방 1건 별도' / '이미 상방 1건 · 이미 하방 2건 별도' / '' (없음)."""
    parts = []
    for key, label in _ALREADY_LABEL:
        n = sum(int(s.get(key) or 0) for s in snapshots)
        if n:
            parts.append(f"{label} {n}건")
    return f"{' · '.join(parts)} 별도" if parts else ""


def tf_seconds(tf: str) -> float:
    """TF 길이(초) — '긴 TF부터' 정렬용. 커스텀(2d)은 베이스 × 배수."""
    base = CUSTOM_INTERVAL_BASE.get(tf)
    if base:
        return interval_delta(base).total_seconds() * int(tf[:-1])
    return interval_delta(tf).total_seconds()


def daily_key(now: pd.Timestamp) -> str:
    """요약 날짜 키 = UTC 날짜(00:00 UTC = 09:00 KST 경계)."""
    return pd.Timestamp(now).strftime("%Y-%m-%d")


def daily_summary_due(hist: dict, now: pd.Timestamp) -> bool:
    """그날(UTC) 아직 안 보냈으면 True — 00:00 UTC 이후 첫 순회에 1회, 늦게 켜져도 그날 첫 순회에 1회, 같은 날 두 번 없음."""
    return (hist.get("daily") or {}).get("last_date") != daily_key(now)


def mark_daily_summary(hist: dict, now: pd.Timestamp) -> None:
    hist["daily"] = {"last_date": daily_key(now), "sent_at": pd.Timestamp(now).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _when_label(ts: pd.Timestamp, now: pd.Timestamp) -> str:
    """이벤트 봉 시각(UTC) → '오늘 HH:MM' / '어제 HH:MM' / 'MM-DD HH:MM' (KST)."""
    k, n = to_kst(ts), to_kst(now)
    if k.date() == n.date():
        return f"오늘 {k:%H:%M}"
    if (n.normalize() - k.normalize()).days == 1:
        return f"어제 {k:%H:%M}"
    return f"{k:%m-%d %H:%M}"


def sent_counts_last_24h(hist: dict, now: pd.Timestamp) -> Dict[str, int]:
    """지난 24h 실제 발송(delivered=True) 건수 — 종류별. 이력 키의 kind 조각으로 센다."""
    out = {k: 0 for k in EV.KINDS}
    cutoff = pd.Timestamp(now) - SUMMARY_LOOKBACK
    for key, v in hist.get("sent", {}).items():
        if not v.get("delivered") or not v.get("sent_at"):
            continue
        if pd.Timestamp(v["sent_at"].rstrip("Z")) >= cutoff:
            kind = H.key_kind(key)
            if kind in out:
                out[kind] += 1
    return out


def headline(events: Sequence[EV.Event], snapshots: Sequence[dict], now: pd.Timestamp) -> str:
    """첫 줄 — 우선순위(기계적): ① 지난 24h 60MA 상방·하방 전환 → ② 대기 중 후보(★ 우선, 경과 짧은 순) → ③ 특이 사항 없음.
    여러 TF 면 긴 TF부터 나열하고 TF 마다 사건 종류를 병기한다. ② 의 대기 행은 표시 모듈의 '대기 중'(MT.waiting_rows) 그대로 —
    '이미 상방'(표 상태 해당 없음)은 거기서 이미 빠져 있다."""
    cutoff = pd.Timestamp(now) - SUMMARY_LOOKBACK
    turns = [e for e in events if e.kind in _TURN_LABEL and cutoff <= e.ts <= pd.Timestamp(now)]
    if turns:
        by_tf: Dict[str, EV.Event] = {}
        for e in turns:                                      # TF 당 최신 전환 1건
            if e.tf not in by_tf or e.ts > by_tf[e.tf].ts:
                by_tf[e.tf] = e
        tfs = sorted(by_tf, key=tf_seconds, reverse=True)
        parts = []
        for tf in tfs:
            e = by_tf[tf]
            div = _DIV_LABEL[e.kind][0 if e.fields.get("divergence") else 1]
            parts.append(f"{tf}: {_TURN_LABEL[e.kind]} ({_when_label(e.ts, now)}, {div})" if len(tfs) > 1
                         else f"{_TURN_LABEL[e.kind]} ({_when_label(e.ts, now)}, {div})")
        return f"볼 TF: {', '.join(tfs)} — {' · '.join(parts)}"
    waiting = [(s["tf"], w) for s in snapshots for w in s["waiting"]]
    if waiting:
        best: Dict[str, dict] = {}
        for tf, w in waiting:                                # TF 당 ★ 우선, 없으면 경과 짧은 것
            cur = best.get(tf)
            if cur is None or (w["divergence"], -w["bars"]) > (cur["divergence"], -cur["bars"]):
                best[tf] = w
        tfs = sorted(best, key=tf_seconds, reverse=True)
        parts = [f"{tf} {best[tf]['elapsed']}{' ★' if best[tf]['divergence'] else ''}" for tf in tfs] if len(tfs) > 1 else \
                [f"경과 {best[tfs[0]]['elapsed']}" + (", 다이버전스 있음" if best[tfs[0]]["divergence"] else "")]
        return f"볼 TF: {', '.join(tfs)} — 후보 대기 중 ({' · '.join(parts)})"
    return SUMMARY_NONE


def build_daily_summary(events: Sequence[EV.Event], snapshots: Sequence[dict], hist: dict, now: pd.Timestamp,
                        n_cells: int, failures: Sequence[str]) -> str:
    """요약 본문(줄바꿈 구분). 첫 줄 상태 문장 + 상세 4줄. 평가어 없음.
    "대기 중" 은 스냅샷의 대기 행(표시 모듈 기준, 이미 상방 제외됨)을 나열하고 '이미 상방/하방' 건수만 괄호로 별도 표기한다."""
    c = sent_counts_last_24h(hist, now)
    waiting_parts = []
    for s in sorted(snapshots, key=lambda x: tf_seconds(x["tf"])):
        for w in sorted(s["waiting"], key=lambda w: (not w["divergence"], w["bars"])):
            waiting_parts.append(f"{s['tf']}({w['elapsed']}{', ★' if w['divergence'] else ''})")
    note = already_note(snapshots)
    ma_parts = " ".join(f"{s['tf']}{s['ma60_dir']}" for s in sorted(snapshots, key=lambda x: tf_seconds(x["tf"])))
    ok = n_cells - len(failures)
    status = "스캐너 정상" if not failures else f"스캐너 오류 {len(failures)}셀"
    return "\n".join([
        headline(events, snapshots, now),
        f"지난 24h 발송: 후보 {c[EV.KIND_STOCH_DB]} · 상방 {c[EV.KIND_MA60_TURN]} · 하방 {c[EV.KIND_MA60_DOWN]}",
        f"대기 중: {' · '.join(waiting_parts) if waiting_parts else '없음'}" + (f" ({note})" if note else ""),
        f"60MA: {ma_parts or '—'}",
        f"{status} · 마지막 순회 {to_kst(now):%H:%M} · {ok}셀 OK",
    ])


def daily_summary_title(now: pd.Timestamp) -> str:
    return f"{TITLE_PREFIX}{SUMMARY_TITLE} {to_kst(now):%m-%d} {UNVERIFIED}"
