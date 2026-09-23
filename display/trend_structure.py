"""추세 구조 추적 — 고점·저점 연쇄 표시 (미검증 · 관측 전용, signal-alarm 표시 계층).

설계 원칙: **파동 번호(1파·2파·3파)를 붙이지 않는다.** 상승 추세는 고점 상승(HH)과 저점 상승(HL)의 연쇄이며
번호는 사후 해석이라 실시간 판정이 불가능하고 판정이 바뀐다. 이 도구는 **구조가 유지되는지 깨지는지만** 보여 준다.
권고·목표가 표현 없음. 되돌림 기준선(38.2%·50%·61.8%)은 참고 표시만 하고 판정에 쓰지 않는다.

검출 로직은 **재구현하지 않는다**:
- 기준점(스토캐 대파동 쌍바닥의 둘째 바닥 p2)·60MA 전환: ``validation.wave_ma60_turn_probe.extract_signals``
  (display.ma60_turn_tracker 가 import 한 ``probe`` 와 ``tracker_pipe``·``lifecycle_rows`` 를 그대로 소비)
- 스윙 고점·저점: ``analysis.wave_structure_confirmation.find_swing_highs / find_swing_lows / _confirmed / PIVOT``
  (SS 라운드·구조 기준선과 같은 검출 경로, 신규 검출기 없음)
이 모듈에 남는 것은 연쇄 정렬·HH/HL/LH/LL 분류·상태 판정·되돌림 산식뿐이다.

분류 규칙: 각 스윙은 **직전 동종 극점 대비** — 고점은 직전 고점(기준점 이전의 마지막 확정 고점 포함), 저점은 직전 저점
(첫 저점은 기준 저점 대비). 기준 저점 = 쌍바닥 구간(첫 바닥~둘째 바닥) 최저가 봉(probe 의 pattern_low, 60MA 추적의
'패턴 저점' 과 같은 값). 현재 구조 = **최근** 고점·저점의 분류: 유지 = 최근 고점 HH·최근 저점 HL / 경고 = 최근 고점 LH /
훼손 = 최근 저점 LL. LL 이 한 번이라도 있었으면 그 시각을 '마지막 훼손' 으로 따로 적는다(상태를 고정하지는 않는다 —
그 뒤 다시 HH·HL 이 이어지면 현재 구조는 유지로 읽힌다. 번호를 매기지 않으므로 '재개' 라 부르지도 않는다).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from analysis.wave_structure_confirmation import PIVOT, _confirmed, find_swing_highs, find_swing_lows
from charts.lw_builder import STRUCTURE_MARKER_SHAPE, TURN_MARKER_SHAPE
from display import ma60_turn_tracker as MT
from display.tz_label import KST_LABEL, to_kst

probe = MT.probe   # validation/wave_ma60_turn_probe (체리픽·sha256 고정) — 재수입 없이 같은 객체를 쓴다

UNVERIFIED = MT.UNVERIFIED
SECTION_TITLE = f"추세 구조 추적 {UNVERIFIED}"
FIXED_CAPTION = "고점·저점 연쇄를 그대로 표시합니다. 파동 번호는 사후 해석이므로 붙이지 않습니다."
RETRACE_REFS = (38.2, 50.0, 61.8)   # 참고 표시만 — 판정에 쓰지 않는다

KIND_HIGH = "고점"
KIND_LOW = "저점"
KIND_TURN = "60MA 상방 전환"        # 표 "종류" 라벨(마커 텍스트는 "60MA" 그대로) — 60MA 상방 전환 추적 섹션과 같은 표기
CLS_HH, CLS_HL, CLS_LH, CLS_LL, CLS_EQ = "HH", "HL", "LH", "LL", "EQ"

STATE_FORMING = "형성 중 (스윙 없음)"
STATE_PARTIAL = "형성 중 (고점·저점 한쪽 대기)"   # 최근 고점·저점 중 하나가 아직 없거나 EQ — 판정 유보
STATE_INTACT = "유지 (HH·HL)"
STATE_WARN = "경고 (LH 발생)"
STATE_BROKEN = "훼손 (LL 발생)"

TIME_COL = f"시각 {KST_LABEL}"
COLUMNS = (TIME_COL, "종류", "가격", "분류", "직전 동종 대비 %")

MARKER_COLORS = {CLS_HH: "#C62828", CLS_HL: "#0B8F45", CLS_LH: "#EF6C00", CLS_LL: "#1565C0", CLS_EQ: "#616161",
                 KIND_TURN: "#7E57C2"}
MARKER_TEXT_MAX = 40   # 이보다 많으면 텍스트 생략(점만) — 밀집 방지


# ------------------------------------------------------------------ 계산 (순수 함수)
def _cls(cur: float, prev: Optional[float], is_high: bool) -> str:
    if prev is None or not np.isfinite(prev):
        return "—"
    if cur == prev:
        return CLS_EQ
    if is_high:
        return CLS_HH if cur > prev else CLS_LH
    return CLS_HL if cur > prev else CLS_LL


def _pct(cur: float, prev: Optional[float]) -> Optional[float]:
    if prev is None or not np.isfinite(prev) or prev == 0:
        return None
    return (cur - prev) / prev * 100.0


def swing_chain(high: pd.Series, low: pd.Series, base_pos: int, base_low: float, last_pos: int) -> List[dict]:
    """기준점 이후의 확정 스윙(고·저) 연쇄 — 시간순. 분류는 직전 동종 극점 대비.

    high/low 는 프레임 전체 시리즈(naive UTC 인덱스). 스윙은 기존 검출기 그대로(PIVOT 좌우 대칭), 확정은 last_pos 기준.
    """
    highs = _confirmed(find_swing_highs(high), last_pos)
    lows = _confirmed(find_swing_lows(low), last_pos)
    prev_high: Optional[float] = None
    for i, v in highs:                      # 기준점 이전의 마지막 확정 고점 = 첫 고점의 비교 대상
        if i <= base_pos:
            prev_high = float(v)
    prev_low: Optional[float] = float(base_low)   # 첫 저점의 비교 대상 = 기준 저점
    events = [(i, float(v), KIND_HIGH) for i, v in highs if i > base_pos] + \
             [(i, float(v), KIND_LOW) for i, v in lows if i > base_pos]
    events.sort(key=lambda e: (e[0], 0 if e[2] == KIND_LOW else 1))
    rows: List[dict] = []
    for pos, val, kind in events:
        is_high = kind == KIND_HIGH
        prev = prev_high if is_high else prev_low
        rows.append({"pos": pos, "ts": high.index[pos], "kind": kind, "price": val,
                     "cls": _cls(val, prev, is_high), "pct": _pct(val, prev)})
        if is_high:
            prev_high = val
        else:
            prev_low = val
    return rows


def structure_state(chain: List[dict]) -> dict:
    """현재 구조 상태 = 최근 고점·저점 분류: 훼손(최근 저점 LL) > 경고(최근 고점 LH) > 유지(HH·HL) > 형성 중.

    last_ll_at = 연쇄 안에서 마지막으로 LL 이 나온 시각(없으면 None) — 훼손 이력 표기용, 상태 고정 아님.
    """
    highs = [r for r in chain if r["kind"] == KIND_HIGH]
    lows = [r for r in chain if r["kind"] == KIND_LOW]
    ll = [r for r in lows if r["cls"] == CLS_LL]
    last_ll_at = ll[-1]["ts"] if ll else None
    if not chain:
        return {"state": STATE_FORMING, "last_ll_at": None}
    if lows and lows[-1]["cls"] == CLS_LL:
        return {"state": STATE_BROKEN, "last_ll_at": last_ll_at}
    if highs and highs[-1]["cls"] == CLS_LH:
        return {"state": STATE_WARN, "last_ll_at": last_ll_at}
    if highs and lows and highs[-1]["cls"] == CLS_HH and lows[-1]["cls"] == CLS_HL:
        return {"state": STATE_INTACT, "last_ll_at": last_ll_at}
    return {"state": STATE_PARTIAL, "last_ll_at": last_ll_at}


def retracement(chain: List[dict], base_low: float) -> Optional[dict]:
    """되돌림 실측 — 최근 고점 H 에서 그 뒤 최근 저점 L 까지, 직전 상승폭(H − 직전 저점) 대비 %.

    최근 고점 뒤에 확정 저점이 없으면 None. 기준선 비교는 하지 않는다(표시는 호출부가 참고로만).
    """
    highs = [r for r in chain if r["kind"] == KIND_HIGH]
    if not highs:
        return None
    h = highs[-1]
    lows_after = [r for r in chain if r["kind"] == KIND_LOW and r["pos"] > h["pos"]]
    if not lows_after:
        return None
    lows_before = [r for r in chain if r["kind"] == KIND_LOW and r["pos"] < h["pos"]]
    prev_low = lows_before[-1]["price"] if lows_before else float(base_low)
    rise = h["price"] - prev_low
    if rise <= 0:
        return None
    lo = lows_after[-1]
    return {"high": h["price"], "high_ts": h["ts"], "low": lo["price"], "low_ts": lo["ts"],
            "prev_low": prev_low, "pct": (h["price"] - lo["price"]) / rise * 100.0}


def analyze(df: pd.DataFrame) -> Optional[dict]:
    """현재 프레임의 최신 대파동 쌍바닥 후보를 기준점으로 구조를 분석. 후보·컬럼이 없으면 None."""
    pipe = MT.tracker_pipe(df)
    if pipe is None:
        return None
    try:
        sig = probe.extract_signals(pipe)
    except (KeyError, ValueError):
        return None
    if not sig["cands"]:
        return None
    cand = max(sig["cands"], key=lambda c: c["known_pos"])
    n = len(pipe)
    last = n - 1
    p1, p2 = int(cand["p1"]), int(cand["p2"])
    lows_span = pipe["low"].to_numpy(dtype=float)[p1:p2 + 1]
    base_pos = p1 + int(np.nanargmin(lows_span))          # 쌍바닥 구간 최저가 봉 = probe.pattern_low 의 위치
    base_low = float(cand["pattern_low"])
    chain = swing_chain(pipe["high"], pipe["low"], base_pos, base_low, last)
    state = structure_state(chain)
    close_now = float(pipe["close"].iloc[last])
    # 60MA 전환 위치 — 60MA 추적과 같은 분류(lifecycle_rows)에서 이 후보의 행을 찾는다
    turn = None
    for r in MT.lifecycle_rows({**sig, "cands": [cand]}, pipe.index, pipe["close"].to_numpy(dtype=float), n):
        if r["상태"] == MT.STATUS_TURNED:
            t_pos = int(pipe.index.get_loc(r["전환 시각"]))
            before = sum(1 for s in chain if s["pos"] <= t_pos)
            turn = {"ts": r["전환 시각"], "price": float(r["전환 시 가격"]), "pos": t_pos, "swings_before": before,
                    "status": r["상태"]}
        else:
            turn = {"ts": None, "price": None, "pos": None, "swings_before": None, "status": r["상태"]}
    return {
        "base": {"ts": pipe.index[base_pos], "low": base_low, "p2_ts": pipe.index[p2],
                 "confirm_ts": pipe.index[int(cand["confirm_pos"])]},
        "chain": chain, "state": state, "close": close_now,
        "gain_pct": (close_now - base_low) / base_low * 100.0 if base_low else None,
        "retrace": retracement(chain, base_low), "turn": turn,
    }


# ------------------------------------------------------------------ 표시 변환
def _fmt_ts(v) -> str:
    return "" if v is None or pd.isna(v) else f"{to_kst(v):%Y-%m-%d %H:%M}"


def _fmt_px(v) -> str:
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{float(v):,.8g}"


def chain_frame(result: dict) -> pd.DataFrame:
    """스윙 연쇄 + 60MA 전환 행을 시간순 표로 (표시용 문자열)."""
    rows = []
    for r in result["chain"]:
        rows.append({"_pos": r["pos"], TIME_COL: _fmt_ts(r["ts"]), "종류": r["kind"], "가격": _fmt_px(r["price"]),
                     "분류": r["cls"], "직전 동종 대비 %": "" if r["pct"] is None else f"{r['pct']:+.2f}%"})
    t = result.get("turn") or {}
    if t.get("pos") is not None:
        rows.append({"_pos": t["pos"] + 0.5, TIME_COL: _fmt_ts(t["ts"]), "종류": KIND_TURN, "가격": _fmt_px(t["price"]),
                     "분류": "", "직전 동종 대비 %": ""})
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    out = pd.DataFrame(rows).sort_values("_pos", kind="mergesort").reset_index(drop=True)
    return out[list(COLUMNS)]


def build_lines(result: Optional[dict]) -> List[str]:
    """텍스트 요약(테스트·검수용)."""
    lines = [SECTION_TITLE, FIXED_CAPTION]
    if result is None:
        lines.append("대파동 쌍바닥 후보 없음 — 기준점 없음")
        return lines
    b = result["base"]
    lines.append(f"기준 저점 {_fmt_ts(b['ts'])} · {_fmt_px(b['low'])} (쌍바닥 둘째 바닥 {_fmt_ts(b['p2_ts'])} · "
                 f"확정 {_fmt_ts(b['confirm_ts'])})")
    lines.append(f"현재 구조: {result['state']['state']}"
                 + (f" · 마지막 훼손(LL) {_fmt_ts(result['state']['last_ll_at'])}" if result["state"]["last_ll_at"] is not None else ""))
    if result["gain_pct"] is not None:
        lines.append(f"누적: 기준 저점 대비 현재가 {result['gain_pct']:+.2f}% (현재가 {_fmt_px(result['close'])})")
    rt = result["retrace"]
    if rt:
        lines.append(f"되돌림 실측: 고점 {_fmt_px(rt['high'])}({_fmt_ts(rt['high_ts'])}) → 저점 {_fmt_px(rt['low'])}"
                     f"({_fmt_ts(rt['low_ts'])}) = 직전 상승폭 대비 {rt['pct']:.1f}% · 참고선 "
                     + " / ".join(f"{x:g}%" for x in RETRACE_REFS) + " (판정 아님)")
    else:
        lines.append("되돌림 실측: 최근 고점 뒤 확정 저점 없음")
    t = result.get("turn") or {}
    if t.get("pos") is not None:
        lines.append(f"60MA 상방 전환 {_fmt_ts(t['ts'])} @ {_fmt_px(t['price'])} — 연쇄 {t['swings_before']}번째 스윙 뒤")
    else:
        lines.append(f"60MA 상방 전환: 없음 (60MA 상방 전환 추적 상태 {t.get('status', '—')})")
    for r in result["chain"]:
        pct = "" if r["pct"] is None else f" {r['pct']:+.2f}%"
        lines.append(f"  {_fmt_ts(r['ts'])} {r['kind']} {_fmt_px(r['price'])} {r['cls']}{pct}")
    return lines


def structure_markers(result: Optional[dict]) -> List[dict]:
    """가격 pane 마커 — 고점은 봉 위, 저점은 봉 아래, 분류 텍스트. 밀집(MARKER_TEXT_MAX 초과)이면 텍스트 생략.

    shape 는 charts.lw_builder.STRUCTURE_MARKER_SHAPE(HH·HL arrowUp / LH·LL square / EQ circle), 60MA 전환은
    TURN_MARKER_SHAPE(circle) — 표시 스타일만, 판정 무접촉.
    """
    if not result or not result["chain"]:
        return []
    dense = len(result["chain"]) > MARKER_TEXT_MAX
    out = []
    for r in result["chain"]:
        is_high = r["kind"] == KIND_HIGH
        out.append({"ts": r["ts"], "position": "aboveBar" if is_high else "belowBar",
                    "color": MARKER_COLORS.get(r["cls"], MARKER_COLORS[CLS_EQ]),
                    "shape": STRUCTURE_MARKER_SHAPE.get(r["cls"], STRUCTURE_MARKER_SHAPE[CLS_EQ]),
                    "text": "" if dense else r["cls"]})
    t = result.get("turn") or {}
    if t.get("pos") is not None:
        out.append({"ts": t["ts"], "position": "belowBar", "color": MARKER_COLORS[KIND_TURN], "shape": TURN_MARKER_SHAPE,
                    "text": "" if dense else "60MA"})
    return out


# ------------------------------------------------------------------ streamlit
def render_structure_section(df: pd.DataFrame, symbol: str, interval: str) -> Optional[dict]:
    """알람 탭 별도 섹션. 반환값은 분석 결과(차트 마커에 재사용)."""
    import streamlit as st

    result = analyze(df)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        if result is None:
            st.caption("대파동 쌍바닥 후보 없음 — 기준점 없음")
            return None
        b, stt = result["base"], result["state"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"기준 저점 {UNVERIFIED}", _fmt_px(b["low"]),
                  help=f"쌍바닥 구간 최저가 봉 {_fmt_ts(b['ts'])} · 둘째 바닥 {_fmt_ts(b['p2_ts'])} · 확정 {_fmt_ts(b['confirm_ts'])}")
        c2.metric(f"현재 구조 {UNVERIFIED}", stt["state"],
                  help="유지 = 최근 고점 HH·최근 저점 HL / 경고 = 최근 고점 LH / 훼손 = 저점 LL 발생")
        c3.metric("기준 저점 대비 현재가", "—" if result["gain_pct"] is None else f"{result['gain_pct']:+.2f}%")
        rt = result["retrace"]
        c4.metric("되돌림 실측(직전 상승폭 대비)", "—" if rt is None else f"{rt['pct']:.1f}%",
                  help="최근 고점→그 뒤 최근 저점. 참고선 38.2 / 50 / 61.8% 는 표시만, 판정에 쓰지 않음.")
        st.caption(f"기준 저점 봉 {_fmt_ts(b['ts'])} (쌍바닥 구간 최저가) · 둘째 바닥 {_fmt_ts(b['p2_ts'])} · 쌍바닥 확정 {_fmt_ts(b['confirm_ts'])}")
        if stt["last_ll_at"] is not None:
            st.caption(f"마지막 훼손(저점 LL): {_fmt_ts(stt['last_ll_at'])}")
        t = result.get("turn") or {}
        if t.get("pos") is not None:
            st.caption(f"60MA 상방 전환 {_fmt_ts(t['ts'])} @ {_fmt_px(t['price'])} — 연쇄의 {t['swings_before']}번째 스윙 뒤 "
                       f"(60MA 상방 전환 추적 섹션과 같은 후보)")
        else:
            st.caption(f"60MA 상방 전환 없음 — 60MA 상방 전환 추적 상태: {t.get('status', '—')}")
        frame = chain_frame(result)
        if frame.empty:
            st.caption("기준점 이후 확정된 스윙 없음")
        else:
            st.dataframe(frame, hide_index=True, width="stretch",
                         column_config={c: st.column_config.TextColumn(c) for c in COLUMNS})
        st.caption(f"스윙 = 좌우 {PIVOT}봉 대칭 극값(기존 swing 검출기, 확정에 {PIVOT}봉 후행) · 분류는 직전 동종 극점 대비 · "
                   f"시각은 {KST_LABEL} 표시 · 마지막 봉은 진행 중일 수 있음 · 파동 번호 없음 · 권고 없음")
    return result
