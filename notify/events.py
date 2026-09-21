"""알림 이벤트 4종 — 검출 모듈 출력만 소비 (재구현 없음).

- ``ma60_turn``   : 대파동 쌍바닥 확정 후 20봉 창 안 60MA 하방→상방 전환. ``display.ma60_turn_tracker.track_candidates``
                    의 '전환 발생' 행 그대로(창·전환 규칙은 probe.simulate 와 동일, 그 모듈의 테스트가 단언).
- ``ma60_down``   : 대파동 쌍봉 확정 후 20봉 창 안 60MA 상방→하방 전환(상승 쪽의 거울상). ``display.ma60_down_tracker.track_candidates``
                    의 '전환 발생' 행 그대로. 현물 보유 시 참고용 관측 — 숏·매도 신호가 아니며 하방 전환율은 측정된 바 없음.
- ``stoch_db``    : 대파동(20,10,10) 쌍바닥 확정 후보(닫힌 봉 기준). ``track_candidates`` 의 후보 행 전부(상태 무관 — 발송 시점의
                    60MA 상태를 본문에 적음). 다이버전스는 ``display.divergence_flag`` 단일 정의(main 870f025).
- ``structure_ll``: 기준 저점 이후 추적 중인 고점·저점 연쇄에서 저점 LL. ``display.trend_structure.analyze`` 의
                    chain 행 중 cls == LL 그대로(기준점 = 최신 대파동 쌍바닥 후보, 스윙 = 기존 swing 검출기).

입력 프레임은 **닫힌 봉만** 담아야 한다(notify.fetch 가 보장). 두 모듈은 프레임의 마지막 봉을 현재로 보므로,
진행 중 봉을 넣지 않으면 진행 중 봉으로는 발화하지 않는다.

이벤트의 ``known_pos`` = 그 이벤트를 알 수 있게 된 확정봉 위치: 전환 = 전환봉, LL = 스윙봉 + PIVOT(스윙 확정 후행).
중복 키는 (symbol, tf, kind, 이벤트 봉 timestamp UTC).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from display import divergence_flag as DV
from display import ma60_down_tracker as MD
from display import ma60_turn_tracker as MT
from display import trend_structure as TS
from display.tz_label import to_kst

KIND_MA60_TURN = "ma60_turn"
KIND_MA60_DOWN = "ma60_down"
KIND_STRUCTURE_LL = "structure_ll"
KIND_STOCH_DB = "stoch_db"
KINDS = (KIND_MA60_TURN, KIND_MA60_DOWN, KIND_STRUCTURE_LL, KIND_STOCH_DB)

UNVERIFIED = MT.UNVERIFIED          # "(미검증)"
TITLE = {KIND_MA60_TURN: "60MA 전환 발생", KIND_MA60_DOWN: "60MA 하방 전환 발생",
         KIND_STRUCTURE_LL: "구조 훼손 — 저점 LL 발생", KIND_STOCH_DB: "대파동 쌍바닥 후보"}
DIVERGENCE_LINE = {True: "다이버전스 있음", False: "다이버전스 없음"}          # 60MA 전환 알림 끝 줄
STAR_DIVERGENCE = "★ 상승 다이버전스"                                          # 쌍바닥 후보 알림 2행(해당 시에만)
DB_FOOTNOTE = "참고: 과거 계측상 후보의 약 60%는 60MA 전환 없이 소멸"
FORBIDDEN_WORDS = ("매수", "진입", "매도", "숏", "청산")     # 권고 표현 금지 — 테스트가 메시지에서 부재를 단언
DOWN_NOTE = "현물 보유 시 참고용 관측 · 하방 전환율 미측정"


@dataclass(frozen=True)
class Event:
    symbol: str
    tf: str
    kind: str
    ts: pd.Timestamp        # 이벤트 봉 open_time (naive UTC) — 중복 키
    known_pos: int          # 확정봉 위치(프레임 내)
    last_pos: int           # 프레임 마지막(닫힌) 봉 위치
    fields: dict            # 메시지 본문용 값

    @property
    def key(self) -> str:
        return event_key(self.symbol, self.tf, self.kind, self.ts)

    @property
    def bars_since_known(self) -> int:
        return int(self.last_pos - self.known_pos)


def event_key(symbol: str, tf: str, kind: str, ts) -> str:
    return f"{symbol}|{tf}|{kind}|{pd.Timestamp(ts).strftime('%Y-%m-%dT%H:%M:%SZ')}"


def _kst(ts) -> str:
    return f"{to_kst(ts):%m-%d %H:%M}"


def _px(v) -> str:
    """위임 예시 표기: 1,000 이상은 정수, 그 미만은 소수 2자리."""
    v = float(v)
    return f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}"


def _pct(v: Optional[float]) -> str:
    return "" if v is None else f" ({v:+.2f}%)"


# ------------------------------------------------------------------ 60MA 전환
def ma60_turn_events(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Event]:
    """track_candidates 의 '전환 발생' 행 → 이벤트. 창 규칙·전환 정의는 그 모듈(→ probe) 소관."""
    n = len(pipe)
    frame = MT.track_candidates(pipe, recent_bars=n)
    out: List[Event] = []
    if frame.empty:
        return out
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))
    for d in frame[frame["상태"] == MT.STATUS_TURNED].to_dict("records"):
        t_pos = int(pipe.index.get_loc(d["전환 시각"]))
        out.append(Event(
            symbol=symbol, tf=tf, kind=KIND_MA60_TURN, ts=pd.Timestamp(d["전환 시각"]),
            known_pos=t_pos, last_pos=n - 1,
            fields={"confirm_ts": pd.Timestamp(d["확정 시각"]), "turn_ts": pd.Timestamp(d["전환 시각"]),
                    "bars": int(d["_bars"]), "price": float(d["전환 시 가격"]),
                    "pattern_low": float(d["패턴 저점"]), "baseline": float(d["기준선(×0.995)"]),
                    "divergence": bool(flags.get(int(d["_confirm_pos"]), False))},
        ))
    return out


# ------------------------------------------------------------------ 대파동 쌍바닥 후보
def stoch_db_events(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Event]:
    """track_candidates 의 후보 행 전부 → 이벤트(키 = 확정봉). 알 수 있게 된 봉은 가용 시점(known_pos, 피봇 확정 지연 반영)."""
    n = len(pipe)
    frame = MT.track_candidates(pipe, recent_bars=n)
    out: List[Event] = []
    if frame.empty:
        return out
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))
    for d in frame.to_dict("records"):
        turned = d["상태"] == MT.STATUS_TURNED
        out.append(Event(
            symbol=symbol, tf=tf, kind=KIND_STOCH_DB, ts=pd.Timestamp(d["확정 시각"]),
            known_pos=int(d["_known_pos"]), last_pos=n - 1,
            fields={"confirm_ts": pd.Timestamp(d["확정 시각"]), "status": d["상태"], "ma_now": d["60MA 현재"],
                    "already_up": d["확정 시 60MA"] == MT.ALREADY_UP_MARK,
                    "divergence": bool(flags.get(int(d["_confirm_pos"]), False)),
                    "pattern_low": float(d["패턴 저점"]), "baseline": float(d["기준선(×0.995)"]),
                    "turn_ts": pd.Timestamp(d["전환 시각"]) if turned else None,
                    "bars": int(d["_bars"]) if turned else None, "obs_bars": MT.OBS_BARS},
        ))
    return out


# ------------------------------------------------------------------ 60MA 하방 전환 (거울상)
def ma60_down_events(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Event]:
    """ma60_down_tracker.track_candidates 의 '전환 발생' 행 → 이벤트. 창·전환 정의는 그 모듈(→ 상승 쪽 + probe) 소관."""
    n = len(pipe)
    frame = MD.track_candidates(pipe, recent_bars=n)
    out: List[Event] = []
    if frame.empty:
        return out
    for d in frame[frame["상태"] == MD.STATUS_TURNED].to_dict("records"):
        t_pos = int(pipe.index.get_loc(d["전환 시각"]))
        out.append(Event(
            symbol=symbol, tf=tf, kind=KIND_MA60_DOWN, ts=pd.Timestamp(d["전환 시각"]),
            known_pos=t_pos, last_pos=n - 1,
            fields={"confirm_ts": pd.Timestamp(d["확정 시각"]), "turn_ts": pd.Timestamp(d["전환 시각"]),
                    "bars": int(d["_bars"]), "price": float(d["전환 시 가격"]),
                    "pattern_high": float(d[MD.HIGH_COL])},
        ))
    return out


# ------------------------------------------------------------------ 구조 훼손 (LL)
def structure_ll_events(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Event]:
    """trend_structure.analyze 의 연쇄에서 LL 저점 → 이벤트. 직전 저점은 연쇄 안의 앞 저점(없으면 기준 저점)."""
    n = len(pipe)
    result = TS.analyze(pipe)
    out: List[Event] = []
    if not result:
        return out
    base = result["base"]
    prev_low = float(base["low"])
    for r in result["chain"]:
        if r["kind"] != TS.KIND_LOW:
            continue
        if r["cls"] == TS.CLS_LL:
            out.append(Event(
                symbol=symbol, tf=tf, kind=KIND_STRUCTURE_LL, ts=pd.Timestamp(r["ts"]),
                known_pos=int(r["pos"]) + TS.PIVOT, last_pos=n - 1,
                fields={"low_ts": pd.Timestamp(r["ts"]), "low": float(r["price"]), "prev_low": prev_low,
                        "pct": r["pct"], "known_ts": pd.Timestamp(pipe.index[min(int(r["pos"]) + TS.PIVOT, n - 1)]),
                        "base_low": float(base["low"]), "base_confirm_ts": pd.Timestamp(base["confirm_ts"]),
                        "state": result["state"]["state"]},
            ))
        prev_low = float(r["price"])
    return out


def scan_frame(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Event]:
    return (ma60_turn_events(pipe, symbol, tf) + ma60_down_events(pipe, symbol, tf)
            + structure_ll_events(pipe, symbol, tf) + stoch_db_events(pipe, symbol, tf))


# ------------------------------------------------------------------ 메시지
def format_message(ev: Event) -> str:
    """종류별 고정 형식(전환 4줄·후보 4~5줄·그 외 3줄). 시각 KST. '(미검증)' 필수. 권고 어휘 없음."""
    f = ev.fields
    head = f"[{ev.symbol} {ev.tf}] {TITLE[ev.kind]} {UNVERIFIED}"
    if ev.kind == KIND_MA60_TURN:
        return "\n".join([
            head,
            f"쌍바닥 확정 {_kst(f['confirm_ts'])} → 전환 {_kst(f['turn_ts'])} (소요 {f['bars']}봉)",
            f"가격 {_px(f['price'])} · 패턴 저점 {_px(f['pattern_low'])} / 기준선 {_px(f['baseline'])}",
            DIVERGENCE_LINE[bool(f.get("divergence", False))],
        ])
    if ev.kind == KIND_STOCH_DB:
        if f["status"] == MT.STATUS_TURNED:
            ma_line = f"60MA 전환 발생 {_kst(f['turn_ts'])} (소요 {f['bars']}봉)"
        elif f["status"] == MT.STATUS_EXPIRED:
            ma_line = f"소멸 (창 {f['obs_bars']}봉 안 60MA 전환 없음)"
        elif f["status"] == MT.STATUS_NO_MA:
            ma_line = "60MA 미산출"
        elif f["already_up"]:
            ma_line = "60MA 이미 상방"
        else:
            ma_line = f"60MA 현재 {f['ma_now']} (전환 대기, 창 {f['obs_bars']}봉)"
        lines = [head]
        if f["divergence"]:
            lines.append(STAR_DIVERGENCE)
        lines += [f"확정 {_kst(f['confirm_ts'])} · {ma_line}",
                  f"패턴 저점 {_px(f['pattern_low'])} / 기준선 {_px(f['baseline'])}",
                  DB_FOOTNOTE]
        return "\n".join(lines)
    if ev.kind == KIND_MA60_DOWN:
        return "\n".join([
            head,
            f"쌍봉 확정 {_kst(f['confirm_ts'])} → 하방 전환 {_kst(f['turn_ts'])} (소요 {f['bars']}봉)",
            f"가격 {_px(f['price'])} · 패턴 고점 {_px(f['pattern_high'])} · {DOWN_NOTE}",
        ])
    if ev.kind == KIND_STRUCTURE_LL:
        return "\n".join([
            head,
            f"저점 {_kst(f['low_ts'])} {_px(f['low'])} < 직전 저점 {_px(f['prev_low'])}{_pct(f['pct'])} · 확정 {_kst(f['known_ts'])}",
            f"기준 저점 {_px(f['base_low'])} (쌍바닥 확정 {_kst(f['base_confirm_ts'])}) · 현재 구조: {f['state']}",
        ])
    raise ValueError(ev.kind)
