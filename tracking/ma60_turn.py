"""60MA 상방 후보 생애주기·표시용 값의 공용 계산 (미검증).

고정 계측 원본에서 추출한 tracking.signals를 사용한다. 관찰 창은 가용 시점부터 20봉,
경과는 확정봉 기준이다. 이미 상방인 후보의 표 상태와 원 생애주기(_lifecycle)를 구분한다.
UI와 notify가 같은 함수를 사용하고 렌더링은 display.ma60_turn_tracker가 담당한다.
출처와 이동 계약: docs/정의_출처.md, config/refactor_provenance.json.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from tracking import signals as probe

from data.numeric import _coerce_ma_numeric  # noqa: E402
from tracking.divergence import DIVERGENCE_COL, NO as DIV_NO, YES as DIV_YES, divergence_flags, label as div_label  # noqa: E402
from utils.time_display import KST_LABEL, to_kst  # noqa: E402
from indicators.ma_patterns import add_ma_patterns  # noqa: E402

# ------------------------------------------------------------------ 체리픽 매니페스트
CHERRYPICK_PROBE_SOURCE_COMMIT = "26dfe9c"
CHERRYPICK_PROBE = {
    "validation/wave_ma60_turn_probe.py": "95cc6bef99c280870b198ac87003ac7efcaa0cb2183fc606af2ea73560a8bc3d",
}

# ------------------------------------------------------------------ 고정 표기 (변경 금지)
OBS_BARS = probe.OBS_BARS            # 20 — 사전등록 고정값
BUFFER = probe.BUFFER                # 0.005 — SS 승계
RECENT_BARS = 120
UNVERIFIED = "(미검증)"
SECTION_TITLE = f"60MA 상방 전환 추적 {UNVERIFIED}"   # 하방 섹션과 대칭 표기(2026-09-23) — 식별자·이력 키·ledger 필드 불변
FIXED_CAPTION = ("탐색 계측 기준 후보의 약 60%는 60MA 전환 없이 소멸합니다 "
                 "(전환율 1h 40.7% / 4h 41.3%, 같은 표본 탐색 결과).")
PROBE_RATES = {"1h": 0.407, "4h": 0.413}   # REPORT_MA60_TURN_PROBE §3 '창 안 60MA 전환 발생' 비율 — 표기 대조용

STATUS_WAITING = "대기 중"
STATUS_TURNED = "전환 발생"
STATUS_EXPIRED = "소멸"
STATUS_NO_MA = "MA60 미산출"

ALREADY_UP_MARK = "이미 상방"     # 확정(가용) 시점에 MA60 이 이미 상방이던 건 — 계측 37.6%
STATUS_ALREADY_UP = f"해당 없음 ({ALREADY_UP_MARK})"   # 그 후보의 표 상태 — 창 진행 중이든 끝났든 같다(대기·소멸·전환율에서 제외, 건수만)
STATUS_ORDER = (STATUS_WAITING, STATUS_TURNED, STATUS_EXPIRED, STATUS_ALREADY_UP, STATUS_NO_MA)
LIFECYCLE_COL = "_lifecycle"     # 내부 열: 창 규칙으로 계산한 원 생애주기(대기/전환/소멸/미산출). '이미 상방' 행도 그대로 남겨
                                 # ledger 기록·60MA 전환 알림(notify)은 이 열을 본다 — 검출·기록 불변, 상태 표기만 분리.

# 표는 현재 표시 중인 심볼·TF 한 셀만 담는다(적재 프레임 1개). 그래도 '경과 1/20' 이 몇 시간인지 표만 보고 알 수 있게
# 맨 앞에 심볼·TF 열을 두고(TF_COL), 캡션에 1봉 시간을 적는다.
TF_COL = "심볼·TF"
COLUMNS = (TF_COL, "상태", "확정 시각", "경과/소요", "60MA 현재", "확정 시 60MA", DIVERGENCE_COL, "전환 시각", "전환 시 가격",
           "패턴 저점", "기준선(×0.995)", "소멸 시각")
TIME_COLUMNS = ("확정 시각", "전환 시각", "소멸 시각")
DISPLAY_HEADERS = {c: f"{c} {KST_LABEL}" for c in TIME_COLUMNS}   # 표 헤더 라벨만 KST 표기(컬럼 키 불변)
EMPTY_CAPTION = "해당 구간에 대파동 쌍바닥 후보 없음"   # 후보 없음 — 화면·build_lines·전체 복사용 텍스트 공통


# ------------------------------------------------------------------ 계산
def tracker_pipe(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """앱 프레임(MA·스토캐 계산 완료) 에 가격 MA 패턴 컬럼을 더한다 — extract_signals 입력."""
    if df is None or df.empty or not {"open", "high", "low", "close", "MA10", "MA60"}.issubset(df.columns):
        return None
    if f"stoch_db_{probe.LARGE}" not in df.columns:
        return None
    pipe = _coerce_ma_numeric(df)
    return add_ma_patterns(pipe)


def _ma_dir(up: np.ndarray, valid: np.ndarray, pos: int) -> str:
    if pos < 0 or pos >= len(up) or not valid[pos]:
        return "—"
    return "상방" if up[pos] else "하방"


ELAPSED_COL = "경과/소요"   # 대기 중: 확정봉→현재 경과 봉 수 · 전환 발생: 확정봉→전환봉 소요 봉 수 · 소멸: 창 종료까지(=20+가용 지연)


def elapsed_label(bars: int, lag: int) -> str:
    """'n/20'. 피봇 확정 지연(lag)으로 가용이 확정봉보다 늦은 후보는 창이 그만큼 늦게 닫히므로 분모에 지연을 더해 표기."""
    denom = OBS_BARS + int(lag)
    return f"{bars}/{denom}" + (f" (가용 +{int(lag)}봉)" if lag else "")


def lifecycle_rows(sig: dict, idx, close: np.ndarray, recent_bars: int) -> List[dict]:
    """후보 생애주기 분류 — probe.extract_signals 출력만 소비하는 순수 함수(테스트 대상).

    창은 probe.simulate 와 동일하게 가용 시점 k 기준 [k, k+OBS_BARS]. 경과/소요 봉 수는 **표에 보이는 확정봉(c)** 기준:
      대기 중 = 현재봉 − c · 전환 발생 = 전환봉 − c · 소멸 = (k+OBS_BARS) − c = 20 + 지연.
    출력의 '상태' 는 창 규칙 그대로다('이미 상방' 행도 대기/전환/소멸). 표 상태 '해당 없음 (이미 상방)' 은 track_candidates 가
    ``apply_already_status`` 로 덧씌운다(원 값은 LIFECYCLE_COL).
    """
    n = len(idx)
    up, turn, valid = sig["ma60_up"], sig["ma60_turn"], sig["ma60_valid"]
    last = n - 1
    rows: List[dict] = []
    for cd in sig["cands"]:
        k, c = int(cd["known_pos"]), int(cd["confirm_pos"])
        lag = k - c
        if k < n - int(recent_bars):
            continue
        w_hi = k + OBS_BARS
        hi = min(w_hi, last)
        rec = {
            "상태": STATUS_WAITING, "확정 시각": idx[c],
            ELAPSED_COL: elapsed_label(last - c, lag), "60MA 현재": _ma_dir(up, valid, last),
            "확정 시 60MA": (ALREADY_UP_MARK if (valid[k] and up[k]) else _ma_dir(up, valid, k)),
            "전환 시각": pd.NaT, "전환 시 가격": np.nan,
            "패턴 저점": float(cd["pattern_low"]), "기준선(×0.995)": float(cd["pattern_low"]) * (1.0 - BUFFER),
            "소멸 시각": pd.NaT,
            "_known_pos": k, "_confirm_pos": c, "_lag": lag, "_bars": last - c,
        }
        if not valid[k:hi + 1].all():
            rec.update({"상태": STATUS_NO_MA, ELAPSED_COL: "—", "_bars": None})
        else:
            hits = np.flatnonzero(turn[k:hi + 1])
            if len(hits):
                t = k + int(hits[0])
                rec.update({"상태": STATUS_TURNED, "전환 시각": idx[t], "전환 시 가격": float(close[t]),
                            ELAPSED_COL: elapsed_label(t - c, lag), "_bars": t - c})
            elif w_hi <= last:
                rec.update({"상태": STATUS_EXPIRED, "소멸 시각": idx[w_hi],
                            ELAPSED_COL: elapsed_label(w_hi - c, lag), "_bars": w_hi - c})
        rows.append(rec)
    return rows


def apply_already_status(rows: List[dict], mark: str = ALREADY_UP_MARK, status: str = STATUS_ALREADY_UP) -> List[dict]:
    """'확정 시 60MA' 가 mark('이미 상방')인 행의 표 상태를 status('해당 없음 (이미 상방)')로 — 창 진행 중이든 끝났든 같다.

    창 규칙으로 계산한 원 생애주기는 LIFECYCLE_COL 에 남긴다(ledger 기록·60MA 전환 알림이 보는 값 — 기록·검출 불변).
    하방 추적은 거울 라벨(이미 하방)로 같은 함수를 호출한다. 표·메트릭·차트선·일일 요약(scripts/push_alarms)은 모두 이 결과의
    '상태' 만 보므로 제외 규칙은 여기 한 곳이다.
    """
    for r in rows:
        r[LIFECYCLE_COL] = r["상태"]
        if r["확정 시 60MA"] == mark:
            r["상태"] = status
    return rows


def waiting_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """'대기 중' 행 — 메트릭·차트 기준선·일일 요약이 같은 함수를 쓴다. '이미 상방' 은 상태가 다르므로(해당 없음) 들지 않는다."""
    if frame is None or frame.empty or "상태" not in frame.columns:
        return pd.DataFrame(columns=list(COLUMNS))
    return frame[frame["상태"] == STATUS_WAITING]


def track_candidates(df: pd.DataFrame, recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """최근 recent_bars 안에 가용(known)된 후보의 생애주기 표.

    상태 규칙(probe.simulate 와 동일한 창 [k, k+OBS_BARS]):
      창 안 첫 60MA 전환 → 전환 발생 / 창이 모두 지났는데 전환 없음 → 소멸 / 아직 창 안 → 대기 중.
      확정 시 60MA 가 이미 상방 → 해당 없음 (이미 상방) — 창과 무관하게 같은 상태(원 생애주기는 LIFECYCLE_COL, apply_already_status).
    마지막 봉은 진행 중일 수 있다(호출부 캡션).
    """
    pipe = tracker_pipe(df)
    if pipe is None:
        return pd.DataFrame(columns=list(COLUMNS))
    try:
        sig = probe.extract_signals(pipe)
    except (KeyError, ValueError):
        return pd.DataFrame(columns=list(COLUMNS))
    rows = apply_already_status(lifecycle_rows(sig, pipe.index, pipe["close"].to_numpy(dtype=float), recent_bars))
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    flags = divergence_flags(pipe, sig)                      # 단일 정의 — 확정봉 → 있음/없음
    for r in rows:
        r[DIVERGENCE_COL] = div_label(flags.get(int(r["_confirm_pos"])))
    out = pd.DataFrame(rows).sort_values("_known_pos", ascending=False, kind="mergesort")
    return out.reset_index(drop=True)


def summarize(frame: pd.DataFrame) -> dict:
    """구간 집계 — 전환 X / 소멸 Y / 대기 Z, 전환율 X/(X+Y) (종료된 건 기준), 이미 상방 W(해당 없음 — 앞 셋·전환율에 들지 않음).
    상태 열만 본다(이미 상방은 apply_already_status 가 상태로 분리해 두었다). 일일 요약(scripts/push_alarms)도 이 함수·waiting_rows 를 쓴다."""
    if frame is None or frame.empty:
        return {"turned": 0, "expired": 0, "waiting": 0, "no_ma": 0, "already_up": 0, "rate": None}
    st_ = frame["상태"]
    turned, expired = int((st_ == STATUS_TURNED).sum()), int((st_ == STATUS_EXPIRED).sum())
    done = turned + expired
    return {
        "turned": turned, "expired": expired,
        "waiting": int(len(waiting_rows(frame))), "no_ma": int((st_ == STATUS_NO_MA).sum()),
        "already_up": int((st_ == STATUS_ALREADY_UP).sum()),
        "rate": (turned / done) if done else None,
    }


def summary_line(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> str:
    s = summarize(frame)
    rate = "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%"
    extra = f" · MA60 미산출 {s['no_ma']}건" if s["no_ma"] else ""
    return (f"최근 {recent_bars}봉: 전환 {s['turned']}건 / 소멸 {s['expired']}건 / 대기 {s['waiting']}건{extra} — "
            f"전환율 {s['turned']}/{s['turned'] + s['expired']} = {rate} {UNVERIFIED} · "
            f"확정 시 이미 상방 {s['already_up']}건 별도")


def divergence_summary(frame: pd.DataFrame) -> dict:
    """있음/없음 코호트별 전환·소멸 건수 — 전방 비교(후보 2·5)의 표본 크기 확인용. 판정 아님."""
    out = {DIV_YES: {"turned": 0, "expired": 0}, DIV_NO: {"turned": 0, "expired": 0}}
    if frame is None or frame.empty or DIVERGENCE_COL not in frame.columns:
        return out
    for d in frame.to_dict("records"):
        key = "turned" if d["상태"] == STATUS_TURNED else "expired" if d["상태"] == STATUS_EXPIRED else None
        if key is not None and d[DIVERGENCE_COL] in out:
            out[d[DIVERGENCE_COL]][key] += 1
    return out


def divergence_summary_line(frame: pd.DataFrame) -> str:
    s = divergence_summary(frame)
    y, n = s[DIV_YES], s[DIV_NO]
    return (f"{DIVERGENCE_COL} 있음: 전환 {y['turned']} / 소멸 {y['expired']} · 없음: 전환 {n['turned']} / 소멸 {n['expired']} "
            f"{UNVERIFIED[:-1]}, 표본 적음)")


def metric_items(s: dict) -> List[tuple]:
    """메트릭 5칸 (라벨, 값, 도움말) — summarize 결과로. 화면 메트릭과 전체 복사용 텍스트(display.alarm_copy_text)가 같은 목록."""
    return [
        (f"대기 중 {UNVERIFIED}", f"{s['waiting']}건", None),
        (f"전환 발생 {UNVERIFIED}", f"{s['turned']}건", None),
        (f"소멸 {UNVERIFIED}", f"{s['expired']}건", None),
        ("전환율(종료 건)", "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%",
         "전환 발생 ÷ (전환 발생 + 소멸). 대기 중·이미 상방(해당 없음)은 제외. 미검증 표시."),
        (f"{ALREADY_UP_MARK} {UNVERIFIED}", f"{s['already_up']}건",
         f"확정 시 60MA 가 이미 상방이던 후보 — 상태 '{STATUS_ALREADY_UP}'. 대기·소멸·전환율에 들지 않음(건수만)."),
    ]


def build_lines(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> List[str]:
    """텍스트 요약(테스트·검수용): 캡션, 상태별 한 줄, 집계."""
    lines = [SECTION_TITLE, FIXED_CAPTION]
    if frame is None or frame.empty:
        lines.append(EMPTY_CAPTION)
    for d in (frame if frame is not None else pd.DataFrame()).to_dict("records"):
        if d["상태"] == STATUS_TURNED:
            tail = f"전환 {to_kst(d['전환 시각']):%m-%d %H:%M} @ {d['전환 시 가격']:,.8g} · 소요 {d[ELAPSED_COL]}"
        elif d["상태"] == STATUS_EXPIRED:
            tail = f"소멸 {to_kst(d['소멸 시각']):%m-%d %H:%M} · 창 {d[ELAPSED_COL]}"
        else:
            tail = f"경과 {d[ELAPSED_COL]} · 60MA {d['60MA 현재']}"
        lines.append(f"[{d['상태']}] 확정 {to_kst(d['확정 시각']):%m-%d %H:%M} · {tail} · "
                     f"저점 {d['패턴 저점']:,.8g} · 기준선 {d['기준선(×0.995)']:,.8g}"
                     + (f" · {DIVERGENCE_COL} {d[DIVERGENCE_COL]}" if d.get(DIVERGENCE_COL) else ""))
    lines.append(summary_line(frame, recent_bars))
    lines.append(divergence_summary_line(frame))
    return lines


# ------------------------------------------------------------------ 차트 연동 (대기 중 후보만)
TRACKER_LOW_COLOR = "#7E57C2"     # 구조 기준선(갈색·적색)과 구분되는 보라 계열
TRACKER_LINE_COLOR = "#26A69A"    # 청록
TRACKER_LOW_LABEL = f"상방 추적 후보 패턴 저점 {UNVERIFIED}"
TRACKER_LINE_LABEL = f"상방 추적 후보 기준선 ×0.995 {UNVERIFIED}"




# 폭은 자동(None) — 문자열 표라 내용 폭에 맞춰지고, 빈 시각 열이 자리를 차지하지 않는다. 좁혀야 할 열만 지정.
TABLE_COLUMN_WIDTHS = {TF_COL: "small", "상태": "small", "경과/소요": "small", "60MA 현재": "small", "확정 시 60MA": "small",
                       DIVERGENCE_COL: "small"}


def _fmt_ts(v) -> str:
    """표시 직전 KST 변환 — track_candidates 의 시각(UTC, 계측·테스트 대조용)은 그대로 둔다."""
    return "" if v is None or pd.isna(v) else f"{to_kst(v):%Y-%m-%d %H:%M}"


def _fmt_px(v) -> str:
    return "" if v is None or pd.isna(v) else f"{float(v):,.8g}"


def bar_hours(interval: str) -> Optional[float]:
    """TF 문자열 → 1봉 시간(시). 1M(월)은 달 길이가 달라 None."""
    iv = str(interval)
    unit, num = iv[-1], iv[:-1]
    try:
        n = float(num)
    except ValueError:
        return None
    return {"m": n / 60.0, "h": n, "d": n * 24.0, "w": n * 24.0 * 7}.get(unit)


def bar_unit_caption(interval: str) -> str:
    h = bar_hours(interval)
    if h is None:
        return f"경과/소요 단위 = {interval} 봉"
    unit = f"{h:g}시간" if h < 24 else f"{h / 24:g}일"
    return f"경과/소요 단위 = {interval} 봉 (1봉 = {unit})"


def display_frame(frame: pd.DataFrame, symbol: str = "", interval: str = "") -> pd.DataFrame:
    """표시용 문자열 표 — 시각은 'YYYY-MM-DD HH:mm', 빈 값은 공백(None 노출·폭 잘림 방지). 값 계산 없음.

    심볼·TF 열은 여기서 채운다(생애주기 계산은 TF 를 모른다 — 표시 전용 정보).
    """
    out = frame.copy()
    if DIVERGENCE_COL not in out.columns:
        out[DIVERGENCE_COL] = ""
    out = out[[c for c in COLUMNS if c != TF_COL]]
    out.insert(0, TF_COL, f"{symbol} {interval}".strip())
    out = out[list(COLUMNS)]
    for c in ("확정 시각", "전환 시각", "소멸 시각"):
        out[c] = out[c].map(_fmt_ts)
    for c in ("전환 시 가격", "패턴 저점", "기준선(×0.995)"):
        out[c] = out[c].map(_fmt_px)
    return out


# ------------------------------------------------------------------ streamlit
