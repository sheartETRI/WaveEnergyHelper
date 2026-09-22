"""전방 ledger — 대파동 쌍바닥 후보의 생애주기가 끝날 때(60MA 전환 발생 / 소멸) 한 줄씩 기록 (알림과 별개, 미검증 관측).
하방(거울상) 후보도 같은 ledger 에 ``direction: "down"`` 행으로 기록한다 — 상승 쪽 기존 행 형식(키 집합)은 불변이며
direction 키가 없는 행은 상승 쪽이다(CSV 내보내기에서만 "up" 으로 채움).

목적: 사람이 고르지 않고 모든 후보를 결과까지 기록해, 몇 달 뒤 "다이버전스 있음 vs 없음" 의 전환율을 편향 없이 비교한다.
- 대상 셀: notify.scanner.SYMBOLS × LEDGER_TFS(1h·4h·6h·1d). 6h 는 기록 전용(알림 대상 아님).
- 후보·상태·소요 봉 수·전환 가격은 ``display.ma60_turn_tracker.track_candidates`` 의 행 그대로(창 20봉·as-of 규칙 그 모듈 소관),
  다이버전스는 ``display.divergence_flag`` (단일 정의, main 870f025) 그대로. 재구현 없음.
- **과거 소급 기록 금지**: ledger 가 처음 만들어진 실행 시각(``since``) 이후에 확정된 후보(확정봉 open_time ≥ since)만 기록.
- 저장 위치: 워크플로가 커밋하는 유일한 파일인 notify/sent.json(notify-state 브랜치) 안의 ``"ledger"`` 필드
  (.github/workflows/notify_scan.yml 무수정 제약). CSV 는 ``to_csv`` 로 내보낸다(python -m notify.scanner --export-ledger 경로).
"""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional

import pandas as pd

from display import divergence_flag as DV
from display import ma60_down_tracker as MD
from display import ma60_turn_tracker as MT

LEDGER_TFS = ("1h", "4h", "6h", "1d")
RESULT_TURNED, RESULT_EXPIRED = "turned", "expired"
DIRECTION_UP, DIRECTION_DOWN = "up", "down"
# 상승 행 필드(기존, 순서 불변) + 하방 행 전용 필드(direction · pattern_high · already_down). 상승 행에는 뒤 세 키가 없다.
FIELDS = ("symbol", "tf", "confirm_ts", "divergence", "result", "bars_to_turn", "turn_ts", "turn_price",
          "pattern_low", "already_up", "recorded_at", "direction", "pattern_high", "already_down")


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def direction_of(row: Dict) -> str:
    """행의 방향 — direction 키 없음 = 상승(기존 행)."""
    return DIRECTION_DOWN if row.get("direction") == DIRECTION_DOWN else DIRECTION_UP


def row_key(symbol: str, tf: str, confirm_ts, direction: str = DIRECTION_UP) -> str:
    """중복 키 — 상승 행은 종전 그대로(symbol|tf|confirm_ts), 하방 행은 '|down' 을 붙여 같은 확정봉의 상승 행과 구분."""
    base = f"{symbol}|{tf}|{_iso(confirm_ts)}"
    return f"{base}|{DIRECTION_DOWN}" if direction == DIRECTION_DOWN else base


def key_of(row: Dict) -> str:
    return row_key(row["symbol"], row["tf"], row["confirm_ts"], direction_of(row))


def finished_rows(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Dict]:
    """프레임(닫힌 봉만)에서 생애주기가 끝난 후보 → ledger 행 후보 목록(since 필터·중복 제거는 history 쪽)."""
    n = len(pipe)
    frame = MT.track_candidates(pipe, recent_bars=n)
    if frame.empty:
        return []
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))      # 단일 정의 — 확정봉 위치 → 있음/없음
    out: List[Dict] = []
    for d in frame.to_dict("records"):
        if d["상태"] == MT.STATUS_TURNED:
            result, bars, turn_ts, price = RESULT_TURNED, int(d["_bars"]), _iso(d["전환 시각"]), float(d["전환 시 가격"])
        elif d["상태"] == MT.STATUS_EXPIRED:
            result, bars, turn_ts, price = RESULT_EXPIRED, None, None, None
        else:
            continue
        out.append({
            "symbol": symbol, "tf": tf, "confirm_ts": _iso(d["확정 시각"]),
            "divergence": bool(flags.get(int(d["_confirm_pos"]), False)),
            "result": result, "bars_to_turn": bars, "turn_ts": turn_ts, "turn_price": price,
            "pattern_low": float(d["패턴 저점"]), "already_up": d["확정 시 60MA"] == MT.ALREADY_UP_MARK,
        })
    return out


def finished_rows_down(pipe: pd.DataFrame, symbol: str, tf: str) -> List[Dict]:
    """하방(거울상) 후보의 종료 행 — ``display.ma60_down_tracker.track_candidates`` 행 그대로. 다이버전스는 그 모듈의
    거울상 정의 라벨(하락 다이버전스 열). 상승 쪽 ``finished_rows`` 와 같은 결과·소요·가격 규칙, 극점은 패턴 고점."""
    n = len(pipe)
    frame = MD.track_candidates(pipe, recent_bars=n)
    if frame.empty:
        return []
    out: List[Dict] = []
    for d in frame.to_dict("records"):
        if d["상태"] == MD.STATUS_TURNED:
            result, bars, turn_ts, price = RESULT_TURNED, int(d["_bars"]), _iso(d["전환 시각"]), float(d["전환 시 가격"])
        elif d["상태"] == MD.STATUS_EXPIRED:
            result, bars, turn_ts, price = RESULT_EXPIRED, None, None, None
        else:
            continue
        out.append({
            "symbol": symbol, "tf": tf, "confirm_ts": _iso(d["확정 시각"]),
            "divergence": d.get(MD.DOWN_DIVERGENCE_COL) == DV.YES,
            "result": result, "bars_to_turn": bars, "turn_ts": turn_ts, "turn_price": price,
            "direction": DIRECTION_DOWN, "pattern_high": float(d[MD.HIGH_COL]),
            "already_down": d["확정 시 60MA"] == MD.ALREADY_DOWN_MARK,
        })
    return out


def to_csv(rows: List[Dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in FIELDS} | {"direction": direction_of(r)})
    return buf.getvalue()


def summary(rows: List[Dict], direction: str = DIRECTION_UP) -> Dict[str, Dict[str, int]]:
    """방향별 있음/없음 × 전환/소멸 건수 (보고·로그용). 기본은 상승 행(기존 호출 불변)."""
    out = {"divergence": {"turned": 0, "expired": 0}, "no_divergence": {"turned": 0, "expired": 0}}
    for r in rows:
        if direction_of(r) != direction:
            continue
        out["divergence" if r.get("divergence") else "no_divergence"][r["result"]] += 1
    return out


def since_of(hist: dict) -> Optional[pd.Timestamp]:
    s = (hist.get("ledger") or {}).get("since")
    return None if not s else pd.Timestamp(s.rstrip("Z"))
