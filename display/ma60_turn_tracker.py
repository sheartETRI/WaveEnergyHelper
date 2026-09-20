"""60MA 전환 추적 — 후보 생애주기 표시 (미검증 · 관측 전용, signal-alarm 표시 계층).

이 표시는 **미검증**이다. 검정은 2027-03 이후 사전등록 스펙(docs/CANDIDATES_POST_2027_03 후보 1)으로
수행한다. 여기서는 "신호"가 아니라 후보의 **생애주기**(대기 중 → 전환 발생 / 소멸)를 보여 주고, 최근
구간의 실제 비율(전환 X건 / 소멸 Y건)을 사용자가 눈으로 누적 확인하게 하는 것이 목적이다.
"진입/매수" 권고 표현은 쓰지 않는다 — "진입" 대신 "전환 발생".

검출 로직은 **재구현하지 않는다** — 계측 스크립트(validation/wave_ma60_turn_probe, origin/main 26dfe9c 에서
체리픽·내용 무변경, CHERRYPICK_PROBE 로 sha256 고정)를 import 해 소비만 한다:
- 후보(대파동 쌍바닥 확정봉, as-of 가용 시점 known, 패턴 저점)·60MA 방향/전환 플래그: ``probe.extract_signals``
- 관찰 창 20봉: ``probe.OBS_BARS`` · 기준선 버퍼: ``probe.BUFFER`` (SS 승계)
이 모듈에 남는 것은 창 안 첫 전환 탐색과 경과 봉 수 계산(``probe.simulate`` 의 [k, k+OBS_BARS] 규칙을
그대로 따르되 1포지션·체결 없이 후보 전부를 분류)뿐이며, 테스트가 ``probe.simulate`` 와 상태 일치를 단언한다.

extract_signals 는 가격 10MA 쌍봉 컬럼(``ma10_dt``)도 요구하므로 앱 프레임에 ``indicators.ma_patterns``
(기존 검출기) 를 한 번 더 적용한다 — 정의 파일 무수정.
"""
from __future__ import annotations

import logging
import warnings
from typing import List, Optional

import numpy as np
import pandas as pd

# 계측 스크립트는 import 시 warnings/logging 을 전역으로 끈다(배치 실행용). 앱에서는 되돌린다.
_warn_filters = warnings.filters[:]
_log_disable = logging.root.manager.disable
import validation.wave_ma60_turn_probe as probe  # noqa: E402
warnings.filters[:] = _warn_filters
logging.disable(_log_disable)

from display.asof import _coerce_ma_numeric  # noqa: E402
from display.tz_label import KST_LABEL, to_kst  # noqa: E402
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
SECTION_TITLE = f"60MA 전환 추적 {UNVERIFIED}"
FIXED_CAPTION = ("탐색 계측 기준 후보의 약 60%는 60MA 전환 없이 소멸합니다 "
                 "(전환율 1h 40.7% / 4h 41.3%, 같은 표본 탐색 결과).")
PROBE_RATES = {"1h": 0.407, "4h": 0.413}   # REPORT_MA60_TURN_PROBE §3 '창 안 60MA 전환 발생' 비율 — 표기 대조용

STATUS_WAITING = "대기 중"
STATUS_TURNED = "전환 발생"
STATUS_EXPIRED = "소멸"
STATUS_NO_MA = "MA60 미산출"
STATUS_ORDER = (STATUS_WAITING, STATUS_TURNED, STATUS_EXPIRED, STATUS_NO_MA)

ALREADY_UP_MARK = "이미 상방"     # 확정(가용) 시점에 MA60 이 이미 상방이던 건 — 계측 37.6%

# 표는 현재 표시 중인 심볼·TF 한 셀만 담는다(적재 프레임 1개). 그래도 '경과 1/20' 이 몇 시간인지 표만 보고 알 수 있게
# 맨 앞에 심볼·TF 열을 두고(TF_COL), 캡션에 1봉 시간을 적는다.
TF_COL = "심볼·TF"
COLUMNS = (TF_COL, "상태", "확정 시각", "경과/소요", "60MA 현재", "확정 시 60MA", "전환 시각", "전환 시 가격",
           "패턴 저점", "기준선(×0.995)", "소멸 시각")
TIME_COLUMNS = ("확정 시각", "전환 시각", "소멸 시각")
DISPLAY_HEADERS = {c: f"{c} {KST_LABEL}" for c in TIME_COLUMNS}   # 표 헤더 라벨만 KST 표기(컬럼 키 불변)


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


def track_candidates(df: pd.DataFrame, recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """최근 recent_bars 안에 가용(known)된 후보의 생애주기 표.

    상태 규칙(probe.simulate 와 동일한 창 [k, k+OBS_BARS]):
      창 안 첫 60MA 전환 → 전환 발생 / 창이 모두 지났는데 전환 없음 → 소멸 / 아직 창 안 → 대기 중.
    마지막 봉은 진행 중일 수 있다(호출부 캡션).
    """
    pipe = tracker_pipe(df)
    if pipe is None:
        return pd.DataFrame(columns=list(COLUMNS))
    try:
        sig = probe.extract_signals(pipe)
    except (KeyError, ValueError):
        return pd.DataFrame(columns=list(COLUMNS))
    rows = lifecycle_rows(sig, pipe.index, pipe["close"].to_numpy(dtype=float), recent_bars)
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    out = pd.DataFrame(rows).sort_values("_known_pos", ascending=False, kind="mergesort")
    return out.reset_index(drop=True)


def summarize(frame: pd.DataFrame) -> dict:
    """구간 집계 — 전환 X / 소멸 Y / 대기 Z, 전환율 X/(X+Y) (종료된 건 기준), 이미 상방 W."""
    if frame is None or frame.empty:
        return {"turned": 0, "expired": 0, "waiting": 0, "no_ma": 0, "already_up": 0, "rate": None}
    st_ = frame["상태"]
    turned, expired = int((st_ == STATUS_TURNED).sum()), int((st_ == STATUS_EXPIRED).sum())
    done = turned + expired
    return {
        "turned": turned, "expired": expired,
        "waiting": int((st_ == STATUS_WAITING).sum()), "no_ma": int((st_ == STATUS_NO_MA).sum()),
        "already_up": int((frame["확정 시 60MA"] == ALREADY_UP_MARK).sum()),
        "rate": (turned / done) if done else None,
    }


def summary_line(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> str:
    s = summarize(frame)
    rate = "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%"
    extra = f" · MA60 미산출 {s['no_ma']}건" if s["no_ma"] else ""
    return (f"최근 {recent_bars}봉: 전환 {s['turned']}건 / 소멸 {s['expired']}건 / 대기 {s['waiting']}건{extra} — "
            f"전환율 {s['turned']}/{s['turned'] + s['expired']} = {rate} {UNVERIFIED} · "
            f"확정 시 이미 상방 {s['already_up']}건 별도")


def build_lines(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> List[str]:
    """텍스트 요약(테스트·검수용): 캡션, 상태별 한 줄, 집계."""
    lines = [SECTION_TITLE, FIXED_CAPTION]
    if frame is None or frame.empty:
        lines.append("해당 구간에 대파동 쌍바닥 후보 없음")
    for d in (frame if frame is not None else pd.DataFrame()).to_dict("records"):
        if d["상태"] == STATUS_TURNED:
            tail = f"전환 {to_kst(d['전환 시각']):%m-%d %H:%M} @ {d['전환 시 가격']:,.8g} · 소요 {d[ELAPSED_COL]}"
        elif d["상태"] == STATUS_EXPIRED:
            tail = f"소멸 {to_kst(d['소멸 시각']):%m-%d %H:%M} · 창 {d[ELAPSED_COL]}"
        else:
            tail = f"경과 {d[ELAPSED_COL]} · 60MA {d['60MA 현재']}"
        lines.append(f"[{d['상태']}] 확정 {to_kst(d['확정 시각']):%m-%d %H:%M} · {tail} · "
                     f"저점 {d['패턴 저점']:,.8g} · 기준선 {d['기준선(×0.995)']:,.8g}"
                     + (f" · {ALREADY_UP_MARK}" if d["확정 시 60MA"] == ALREADY_UP_MARK else ""))
    lines.append(summary_line(frame, recent_bars))
    return lines


# ------------------------------------------------------------------ 차트 연동 (대기 중 후보만)
TRACKER_LOW_COLOR = "#7E57C2"     # 구조 기준선(갈색·적색)과 구분되는 보라 계열
TRACKER_LINE_COLOR = "#26A69A"    # 청록
TRACKER_LOW_LABEL = f"추적 후보 패턴 저점 {UNVERIFIED}"
TRACKER_LINE_LABEL = f"추적 후보 기준선 ×0.995 {UNVERIFIED}"


def tracker_reference_lines(frame: pd.DataFrame) -> List[dict]:
    """대기 중 후보의 저점·기준선 — LW 가격 pane 가격선 사전(구조 기준선과 같은 형식). 없으면 빈 목록."""
    from charts.lw_builder import LW_LINE_STYLE_DASHED, LW_LINE_STYLE_DOTTED

    if frame is None or frame.empty:
        return []
    lines: List[dict] = []
    for d in frame[frame["상태"] == STATUS_WAITING].to_dict("records"):
        lines.append({"price": float(d["패턴 저점"]), "color": TRACKER_LOW_COLOR, "style": LW_LINE_STYLE_DOTTED,
                      "title": "", "label": TRACKER_LOW_LABEL})
        lines.append({"price": float(d["기준선(×0.995)"]), "color": TRACKER_LINE_COLOR, "style": LW_LINE_STYLE_DASHED,
                      "title": "", "label": TRACKER_LINE_LABEL})
    return lines


# 폭은 자동(None) — 문자열 표라 내용 폭에 맞춰지고, 빈 시각 열이 자리를 차지하지 않는다. 좁혀야 할 열만 지정.
TABLE_COLUMN_WIDTHS = {TF_COL: "small", "상태": "small", "경과/소요": "small", "60MA 현재": "small", "확정 시 60MA": "small"}


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
    out = frame[[c for c in COLUMNS if c != TF_COL]].copy()
    out.insert(0, TF_COL, f"{symbol} {interval}".strip())
    out = out[list(COLUMNS)]
    for c in ("확정 시각", "전환 시각", "소멸 시각"):
        out[c] = out[c].map(_fmt_ts)
    for c in ("전환 시 가격", "패턴 저점", "기준선(×0.995)"):
        out[c] = out[c].map(_fmt_px)
    return out


# ------------------------------------------------------------------ streamlit
def render_tracker_section(df: pd.DataFrame, symbol: str, interval: str,
                           recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """알람 탭 별도 섹션. 반환값은 후보 표(차트 연동에 재사용)."""
    import streamlit as st

    from display.ma60_slope import render_slope_block   # 기울기 실측(표시 전용, 판정 없음) — 섹션 상단 블록

    frame = track_candidates(df, recent_bars=recent_bars)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        render_slope_block(df, symbol, interval)
        s = summarize(frame)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"대기 중 {UNVERIFIED}", f"{s['waiting']}건")
        c2.metric(f"전환 발생 {UNVERIFIED}", f"{s['turned']}건")
        c3.metric(f"소멸 {UNVERIFIED}", f"{s['expired']}건")
        c4.metric("전환율(종료 건)", "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%",
                  help="전환 발생 ÷ (전환 발생 + 소멸). 대기 중은 제외. 미검증 표시.")
        if frame.empty:
            st.caption("해당 구간에 대파동 쌍바닥 후보 없음")
        else:
            st.caption(bar_unit_caption(interval))
            st.dataframe(
                display_frame(frame, symbol, interval), hide_index=True, width="stretch",
                column_config={c: st.column_config.TextColumn(DISPLAY_HEADERS.get(c, c), width=TABLE_COLUMN_WIDTHS.get(c))
                               for c in COLUMNS},
            )
        st.caption(summary_line(frame, recent_bars))
        st.caption(f"대기 중 = 대파동(20,10,10) 쌍바닥 확정 후 {OBS_BARS}봉 창이 살아 있는 후보 · "
                   f"경과/소요 = 확정봉 기준 봉 수(대기: 현재까지 경과, 전환 발생: 전환까지 소요, 소멸: 창 종료까지) · "
                   f"창은 후보 가용 시점(피봇 확정 지연 1~2봉 가능) 기준 {OBS_BARS}봉이라 지연 후보는 분모에 '+N봉' 표기 · "
                   f"시각은 {KST_LABEL} 표시 · 마지막 봉은 진행 중일 수 있음 · "
                   "확정 시 60MA '이미 상방' 은 전환이 아니므로 창 안의 새 전환만 셈.")
    return frame
