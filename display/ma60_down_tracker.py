"""60MA 하방 전환 추적 — 현물 보유 경고용 관측 (미검증 · 상승 쪽의 거울상, signal-alarm 표시 계층).

현물 보유 중 청산 판단 **참고용 관측**이다. 숏·선물 진입 신호가 아니며, "매도/청산하라" 같은 권고 표현을 쓰지 않고
상태만 기술한다("60MA 하방 전환 발생"). 모든 표기에 "(미검증)". 하방 전환의 전환율은 계측된 바 없다 —
상승 쪽 계측 수치(1h 40.7% / 4h 41.3%)를 이쪽에 쓰지 않는다.

정의는 상승 쪽(display/ma60_turn_tracker)의 **정확한 거울상**이며 파라미터를 신설하지 않는다:
- 후보: 스토캐 대파동(20,10,10) **쌍봉 확정**. 계측 스크립트 ``probe.extract_signals`` 에 쌍봉 경로가 있으므로
  (``stoch_tops`` — 확정봉·as-of 가용 시점 known·지연) 그것을 그대로 쓴다(알람 계층 DT 검출은 쓰지 않음).
  패턴 고점은 쌍바닥의 ``pattern_low`` 산식(첫 바닥 ~ 둘째 바닥 구간 low 최소)의 거울상 — 앱 검출기가 기록한
  첫 봉우리(``stoch_dt_first_pos``) ~ 둘째 봉우리(확정봉 이하 마지막 피봇 고점, probe 의 ``_last_pos_leq`` 와 같은
  규칙) 구간 high 최대. 첫 봉우리 미기록·순서 역전 건은 쌍바닥과 같은 규칙으로 제외.
- 전환: 확정 후 **20봉 창(probe.OBS_BARS)** 안에 MA60(t) < MA60(t−1) 이고 직전 봉은 그렇지 않은 봉. 60MA 방향·전환
  플래그는 ``probe.extract_signals`` 를 **MA60 부호를 반전한 프레임**에 적용해 얻는다(−MA60 의 '상방' = MA60 의
  '하방', 전환 정의·유효 구간 규칙이 그대로 승계됨 — 표시 계층에 기울기 계산 없음).
- 창 길이·경과/소요·as-of 규칙: 상승 쪽 ``lifecycle_rows`` 를 거울상 sig 로 **그대로 호출**한다(창 [k, k+20], 경과는
  표에 보이는 확정봉 기준). 결과 행의 방향 라벨만 되돌린다(거울 공간 '상방' → 실제 '하방').
- 하락 다이버전스 열: 상승 다이버전스 단일 정의(``display.divergence_flag``, main 870f025)의 **거울상** — (1) 스토캐 고점:
  두 번째 봉우리 < 첫 번째 = 기존 검출기의 ``stoch_dt_kind_{LARGE}`` == "LH"(확정봉에 기록, 쌍바닥 "HL" 의 반전 라벨) 소비,
  (2) 가격 고점: 두 피봇 봉의 **고가** 비교, 두 번째 > 첫 번째(p1·p2 는 위 cands 그대로). 둘 다 만족하면 "있음".
  새 파라미터 없음. 정의 파일·상승 쪽 함수 무접촉.
- 차트: 대기 중 후보의 패턴 고점을 상승 쪽 기준선 방식(가격선 사전, ``down_tracker_reference_lines``)으로 구분 색 1선만 그린다.
상승 쪽 로직·정의는 일절 건드리지 않는다(import 만). 기준선(×0.995)은 롱 손절 참조값이라 거울상(×1.005)을 두지 않는다
— 현물 보유 관측에는 해당 없음(위임 §2 열 목록에도 없음).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

import display.ma60_turn_tracker as up   # 상승 쪽 표시 모듈 — probe·창·경과 규칙의 단일 출처(무수정)
from display.divergence_flag import NO as DIV_NO, YES as DIV_YES, label as div_label   # 라벨만 승계(정의 함수는 거울상)
from display.tz_label import KST_LABEL, to_kst

probe = up.probe                          # validation.wave_ma60_turn_probe (체리픽 매니페스트는 up.CHERRYPICK_PROBE)

# ------------------------------------------------------------------ 고정 표기 (변경 금지)
OBS_BARS = up.OBS_BARS                    # 20 — 승계
RECENT_BARS = up.RECENT_BARS              # 120 — 승계
UNVERIFIED = up.UNVERIFIED
SECTION_TITLE = f"60MA 하방 전환 추적 {UNVERIFIED}"
FIXED_CAPTION = "현물 보유 시 참고용 관측입니다. 하방 전환의 전환율은 측정된 바 없습니다."

STATUS_WAITING = up.STATUS_WAITING
STATUS_TURNED = up.STATUS_TURNED          # "전환 발생" — 하방 전환 발생
STATUS_EXPIRED = up.STATUS_EXPIRED
STATUS_NO_MA = up.STATUS_NO_MA
STATUS_ORDER = up.STATUS_ORDER

ALREADY_DOWN_MARK = "이미 하방"           # 확정(가용) 시점에 MA60 이 이미 하방이던 건 — 상승 쪽 '이미 상방' 의 거울상
_DIR_MIRROR = {"상방": "하방", "하방": "상방", "—": "—", up.ALREADY_UP_MARK: ALREADY_DOWN_MARK}

TF_COL = up.TF_COL
ELAPSED_COL = up.ELAPSED_COL
HIGH_COL = "패턴 고점"
DOWN_DIVERGENCE_COL = "하락 다이버전스"      # 상승 쪽 '다이버전스' 열의 거울상 — 값은 같은 라벨(있음/없음)
COLUMNS = (TF_COL, "상태", "확정 시각", ELAPSED_COL, "60MA 현재", "확정 시 60MA", DOWN_DIVERGENCE_COL, "전환 시각",
           "전환 시 가격", HIGH_COL, "소멸 시각")
TIME_COLUMNS = up.TIME_COLUMNS
DISPLAY_HEADERS = up.DISPLAY_HEADERS
TABLE_COLUMN_WIDTHS = {**{k: v for k, v in up.TABLE_COLUMN_WIDTHS.items() if k in COLUMNS}, DOWN_DIVERGENCE_COL: "small"}

KIND_LH = "LH"                                    # 쌍봉 검출기 kind: 두 번째 봉우리 < 첫 번째 (쌍바닥 "HL" 의 반전 라벨)
KIND_COL = f"stoch_dt_kind_{probe.LARGE}"


# ------------------------------------------------------------------ 계산
def tracker_pipe(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """상승 쪽과 같은 입력 준비(가격 MA 패턴 컬럼 추가). 쌍봉 첫 봉우리 컬럼이 없으면 None."""
    pipe = up.tracker_pipe(df)
    if pipe is None or f"stoch_dt_first_pos_{probe.LARGE}" not in pipe.columns:
        return None
    return pipe


def mirror_pipe(pipe: pd.DataFrame) -> pd.DataFrame:
    """MA60 부호 반전 사본 — probe.extract_signals 의 '상방/전환' 이 실제 '하방/하방 전환' 이 된다. 다른 컬럼 불변."""
    out = pipe.copy()
    out["MA60"] = -pd.to_numeric(out["MA60"], errors="coerce")
    return out


def extract_mirror_signals(pipe: pd.DataFrame) -> dict:
    """거울상 sig — ``up.lifecycle_rows`` 입력 형식 그대로.

    cands = probe 의 ``stoch_tops``(대파동 쌍봉 확정·known·lag) 에 패턴 고점을 붙인 것. lifecycle_rows 가 읽는 키 이름이
    ``pattern_low`` 이므로 **거울 공간 값(패턴 고점)을 그 키에 담는다** — 표에 옮길 때 ``패턴 고점`` 열로 이름을 되돌린다.
    ma60_up/ma60_turn/ma60_valid 는 MA60 부호 반전 프레임의 probe 출력(= 실제 하방/하방 전환/유효).
    """
    sig = probe.extract_signals(mirror_pipe(pipe))
    high = pipe["high"].to_numpy(dtype=float)
    first = pipe[f"stoch_dt_first_pos_{probe.LARGE}"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    piv_high = pipe[f"stoch_pivot_high_{probe.LARGE}"].notna().to_numpy()
    cands: List[dict] = []
    for top in sig["stoch_tops"]:
        c = int(top["confirm_pos"])
        p2 = probe._last_pos_leq(piv_high, c)          # 둘째 봉우리 — probe 의 _tops 와 같은 규칙
        p1 = int(first[c]) if np.isfinite(first[c]) else None
        if p2 is None or p1 is None or p1 >= p2:       # 쌍바닥 cands 와 같은 제외 규칙
            continue
        cands.append({**top, "p1": p1, "p2": p2, "pattern_low": float(np.nanmax(high[p1:p2 + 1]))})
    return {"cands": cands, "ma60_up": sig["ma60_up"], "ma60_turn": sig["ma60_turn"], "ma60_valid": sig["ma60_valid"]}


def bearish_divergence_flags(pipe: pd.DataFrame, sig: dict) -> dict:
    """확정봉 위치 → 하락 다이버전스 여부 — ``divergence_flag.divergence_flags`` 의 거울상(저가→고가, HL→LH, < → >).

    sig 는 ``extract_mirror_signals`` 출력(cands 의 p1·p2·confirm_pos 그대로). 재구현 없음: 스토캐 고점 비교는 검출기 kind
    컬럼, 피봇 위치는 cands.
    """
    kind = pipe[KIND_COL].to_numpy(dtype=object) if KIND_COL in pipe.columns else None
    high = pd.to_numeric(pipe["high"], errors="coerce").to_numpy(dtype=float)
    out = {}
    for cd in sig["cands"]:
        c, p1, p2 = int(cd["confirm_pos"]), int(cd["p1"]), int(cd["p2"])
        stoch_lh = kind is not None and kind[c] == KIND_LH
        price_hh = bool(high[p2] > high[p1])
        out[c] = bool(stoch_lh and price_hh)
    return out


def unmirror_row(rec: dict) -> dict:
    """거울 공간 행 → 실제 방향 라벨. 값(시각·가격·경과)은 그대로."""
    out = dict(rec)
    out[HIGH_COL] = out.pop("패턴 저점")
    out.pop("기준선(×0.995)", None)
    out["60MA 현재"] = _DIR_MIRROR.get(out["60MA 현재"], out["60MA 현재"])
    out["확정 시 60MA"] = _DIR_MIRROR.get(out["확정 시 60MA"], out["확정 시 60MA"])
    return out


def lifecycle_rows(sig: dict, idx, close: np.ndarray, recent_bars: int) -> List[dict]:
    """상승 쪽 lifecycle_rows 를 거울상 sig 로 호출하고 라벨만 되돌린다 — 창·경과·as-of 규칙 동일 승계."""
    return [unmirror_row(r) for r in up.lifecycle_rows(sig, idx, close, recent_bars)]


def track_candidates(df: pd.DataFrame, recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """최근 recent_bars 안에 가용(known)된 쌍봉 후보의 생애주기 표(상승 쪽과 같은 형식, 열만 거울상)."""
    pipe = tracker_pipe(df)
    if pipe is None:
        return pd.DataFrame(columns=list(COLUMNS))
    try:
        sig = extract_mirror_signals(pipe)
    except (KeyError, ValueError):
        return pd.DataFrame(columns=list(COLUMNS))
    rows = lifecycle_rows(sig, pipe.index, pipe["close"].to_numpy(dtype=float), recent_bars)
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    flags = bearish_divergence_flags(pipe, sig)               # 거울상 정의 — 확정봉 → 있음/없음
    for r in rows:
        r[DOWN_DIVERGENCE_COL] = div_label(flags.get(int(r["_confirm_pos"])))
    out = pd.DataFrame(rows).sort_values("_known_pos", ascending=False, kind="mergesort")
    return out.reset_index(drop=True)


def summarize(frame: pd.DataFrame) -> dict:
    """구간 집계 — 전환 X / 소멸 Y / 대기 Z, 전환율 X/(X+Y) (종료 건 기준, 이 창의 실측), 이미 하방 W."""
    if frame is None or frame.empty:
        return {"turned": 0, "expired": 0, "waiting": 0, "no_ma": 0, "already_down": 0, "rate": None}
    st_ = frame["상태"]
    turned, expired = int((st_ == STATUS_TURNED).sum()), int((st_ == STATUS_EXPIRED).sum())
    done = turned + expired
    return {
        "turned": turned, "expired": expired,
        "waiting": int((st_ == STATUS_WAITING).sum()), "no_ma": int((st_ == STATUS_NO_MA).sum()),
        "already_down": int((frame["확정 시 60MA"] == ALREADY_DOWN_MARK).sum()),
        "rate": (turned / done) if done else None,
    }


def summary_line(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> str:
    s = summarize(frame)
    rate = "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%"
    extra = f" · MA60 미산출 {s['no_ma']}건" if s["no_ma"] else ""
    return (f"최근 {recent_bars}봉: 하방 전환 {s['turned']}건 / 소멸 {s['expired']}건 / 대기 {s['waiting']}건{extra} — "
            f"이 창 실측 {s['turned']}/{s['turned'] + s['expired']} = {rate} {UNVERIFIED} · "
            f"확정 시 이미 하방 {s['already_down']}건 별도")


def divergence_summary(frame: pd.DataFrame) -> dict:
    """있음/없음 코호트별 하방 전환·소멸 건수 — 상승 쪽 ``divergence_summary`` 와 같은 형식. 판정 아님."""
    out = {DIV_YES: {"turned": 0, "expired": 0}, DIV_NO: {"turned": 0, "expired": 0}}
    if frame is None or frame.empty or DOWN_DIVERGENCE_COL not in frame.columns:
        return out
    for d in frame.to_dict("records"):
        key = "turned" if d["상태"] == STATUS_TURNED else "expired" if d["상태"] == STATUS_EXPIRED else None
        if key is not None and d[DOWN_DIVERGENCE_COL] in out:
            out[d[DOWN_DIVERGENCE_COL]][key] += 1
    return out


def divergence_summary_line(frame: pd.DataFrame) -> str:
    s = divergence_summary(frame)
    y, n = s[DIV_YES], s[DIV_NO]
    return (f"{DOWN_DIVERGENCE_COL} 있음: 하방 전환 {y['turned']} / 소멸 {y['expired']} · "
            f"없음: 하방 전환 {n['turned']} / 소멸 {n['expired']} {UNVERIFIED[:-1]}, 표본 적음)")


def build_lines(frame: pd.DataFrame, recent_bars: int = RECENT_BARS) -> List[str]:
    """텍스트 요약(테스트·검수용): 캡션, 상태별 한 줄, 집계."""
    lines = [SECTION_TITLE, FIXED_CAPTION]
    if frame is None or frame.empty:
        lines.append("해당 구간에 대파동 쌍봉 후보 없음")
    for d in (frame if frame is not None else pd.DataFrame()).to_dict("records"):
        if d["상태"] == STATUS_TURNED:
            tail = f"하방 전환 {to_kst(d['전환 시각']):%m-%d %H:%M} @ {d['전환 시 가격']:,.8g} · 소요 {d[ELAPSED_COL]}"
        elif d["상태"] == STATUS_EXPIRED:
            tail = f"소멸 {to_kst(d['소멸 시각']):%m-%d %H:%M} · 창 {d[ELAPSED_COL]}"
        else:
            tail = f"경과 {d[ELAPSED_COL]} · 60MA {d['60MA 현재']}"
        lines.append(f"[{d['상태']}] 확정 {to_kst(d['확정 시각']):%m-%d %H:%M} · {tail} · 고점 {d[HIGH_COL]:,.8g}"
                     + (f" · {ALREADY_DOWN_MARK}" if d["확정 시 60MA"] == ALREADY_DOWN_MARK else "")
                     + (f" · {DOWN_DIVERGENCE_COL} {d[DOWN_DIVERGENCE_COL]}" if d.get(DOWN_DIVERGENCE_COL) else ""))
    lines.append(summary_line(frame, recent_bars))
    lines.append(divergence_summary_line(frame))
    return lines


# ------------------------------------------------------------------ 차트 연동 (대기 중 후보의 패턴 고점만)
TRACKER_HIGH_COLOR = "#E64A19"    # 상승 쪽 추적선(보라 #7E57C2 · 청록 #26A69A)·구조 기준선(갈색·적색)과 구분되는 주황 계열
TRACKER_HIGH_LABEL = f"하방 추적 후보 패턴 고점 {UNVERIFIED}"


def down_tracker_reference_lines(frame: pd.DataFrame) -> List[dict]:
    """대기 중 후보의 패턴 고점 — LW 가격 pane 가격선 사전(상승 쪽 ``tracker_reference_lines`` 와 같은 형식, 1선/후보).
    기준선(×1.005)은 두지 않으므로 고점선 하나뿐이다. 없으면 빈 목록."""
    from charts.lw_builder import LW_LINE_STYLE_DOTTED   # 지연 import — 차트 모듈이 없는 배포(main notify)에서도 이 모듈은 import 가능

    if frame is None or frame.empty:
        return []
    return [{"price": float(d[HIGH_COL]), "color": TRACKER_HIGH_COLOR, "style": LW_LINE_STYLE_DOTTED,
             "title": "", "label": TRACKER_HIGH_LABEL}
            for d in frame[frame["상태"] == STATUS_WAITING].to_dict("records")]


def display_frame(frame: pd.DataFrame, symbol: str = "", interval: str = "") -> pd.DataFrame:
    """표시용 문자열 표 — 상승 쪽과 같은 포맷 규칙(시각 KST, 빈 값 공백). 값 계산 없음."""
    out = frame[[c for c in COLUMNS if c != TF_COL and c in frame.columns]].copy()
    if DOWN_DIVERGENCE_COL not in out.columns:
        out[DOWN_DIVERGENCE_COL] = ""
    out.insert(0, TF_COL, f"{symbol} {interval}".strip())
    out = out[list(COLUMNS)]
    for c in TIME_COLUMNS:
        out[c] = out[c].map(up._fmt_ts)
    for c in ("전환 시 가격", HIGH_COL):
        out[c] = out[c].map(up._fmt_px)
    return out


# ------------------------------------------------------------------ streamlit
def render_down_tracker_section(df: pd.DataFrame, symbol: str, interval: str,
                                recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """알람 탭 별도 섹션 — 상승 쪽 '60MA 전환 추적' 바로 옆(아래). 반환값은 후보 표(차트 고점선은 호출부가 ``down_tracker_reference_lines`` 로)."""
    import streamlit as st

    frame = track_candidates(df, recent_bars=recent_bars)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        s = summarize(frame)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"대기 중 {UNVERIFIED}", f"{s['waiting']}건")
        c2.metric(f"하방 전환 발생 {UNVERIFIED}", f"{s['turned']}건")
        c3.metric(f"소멸 {UNVERIFIED}", f"{s['expired']}건")
        c4.metric("이 창 실측(종료 건)", "—" if s["rate"] is None else f"{s['rate'] * 100:.0f}%",
                  help="하방 전환 발생 ÷ (하방 전환 발생 + 소멸). 대기 중은 제외. 이 표시 구간의 실측일 뿐 "
                       "하방 전환율은 별도로 측정된 바 없음. 미검증 표시.")
        if frame.empty:
            st.caption("해당 구간에 대파동 쌍봉 후보 없음")
        else:
            st.caption(up.bar_unit_caption(interval))
            st.dataframe(
                display_frame(frame, symbol, interval), hide_index=True, width="stretch",
                column_config={c: st.column_config.TextColumn(DISPLAY_HEADERS.get(c, c), width=TABLE_COLUMN_WIDTHS.get(c))
                               for c in COLUMNS},
            )
        st.caption(summary_line(frame, recent_bars))
        st.caption(divergence_summary_line(frame))
        st.caption(f"대기 중 = 대파동(20,10,10) 쌍봉 확정 후 {OBS_BARS}봉 창이 살아 있는 후보 · "
                   f"하방 전환 = 창 안에 MA60(t) < MA60(t−1) 이고 직전 봉은 아닌 봉(상승 쪽 정의의 거울상) · "
                   f"경과/소요 = 확정봉 기준 봉 수(대기: 현재까지 경과, 전환 발생: 전환까지 소요, 소멸: 창 종료까지) · "
                   f"창은 후보 가용 시점(피봇 확정 지연 1~2봉 가능) 기준 {OBS_BARS}봉이라 지연 후보는 분모에 '+N봉' 표기 · "
                   f"시각은 {KST_LABEL} 표시 · 마지막 봉은 진행 중일 수 있음 · "
                   "확정 시 60MA '이미 하방' 은 전환이 아니므로 창 안의 새 전환만 셈 · "
                   f"{DOWN_DIVERGENCE_COL} = 스토캐(20,10,10) 둘째 봉우리 < 첫째 봉우리(LH) 이면서 두 피봇 봉의 고가는 둘째 > 첫째 "
                   "(상승 다이버전스 정의의 거울상, 판정 아님).")
    return frame
