"""검증 위계를 화면에 복원하기 위한 표시 계층 헬퍼 (display 전용).

**표시 전용이다.** 게이트·트리거·손절·asof 정의를 재구현하지 않는다 —
전부 기존 모듈에서 import 해 읽기만 한다. 어떤 기록도 쓰지 않는다.

문구 규율:
- 상태 기술형만 쓴다. "매수/매도 권고", "진입 시점", "목표가" 류 단정 표현 금지.
- 성과 지표(G·Δ·수익률·승률·기대값)는 어떤 형태로도 노출하지 않는다 —
  섀도·전방 추적의 열람 동결(2027-03)을 UI 가 우회하지 못하게 한다.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from analysis.wave_align_gate_forward import (
    PROMOTED_LTF_TO_HTF,
    REVIEW_DUE,
    TRACKING_START,
    current_gate_status,
    sidecar_path,
)
from analysis.wave_htf_gate import interval_delta
from analysis.wave_htf_gate_v2 import SYMBOLS_V2
from analysis.mm_shadow import VARIANTS, shadow_path

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation",
)

# 항목 3 고정 주석 — 문구 변경 금지 (in-sample 프로파일의 정직한 요약)
GATE_PROFILE_NOTE = (
    "이 필터는 에피소드 과반에서 무게이트 대비 열세였고 "
    "소수 국면이 우위를 견인한 유형 (in-sample 결과)"
)

STRUCT_LINE_LABEL = "패턴 저점 기준선 (검증 중)"
STRUCT_LINE_MISSING = "기준선 없음"

GATE_OPEN = "개방"
GATE_CLOSED = "폐쇄"
GATE_NA = "미적용"

FRESHNESS_WARN_BARS = 2


# ------------------------------------------------------------------ 게이트 상태
@st.cache_data(show_spinner=False, ttl=900)
def gate_rows() -> list[dict]:
    """심볼×HTF 의 현재 게이트 상태.

    analysis.wave_align_gate_forward.current_gate_status() 를 그대로 쓴다.
    그 함수가 F2-b 판정(analysis.wave_htf_gate_v2.f2b_rising_flags)과
    '마지막 닫힌 봉' asof 규칙을 이미 담고 있으므로 여기서 재구현하지 않는다.
    """
    try:
        return current_gate_status()
    except Exception:  # noqa: BLE001 — 표시 전용이므로 실패해도 앱을 막지 않는다
        return []


def gate_state_for(symbol: str, htf: str, rows: Optional[list[dict]] = None) -> dict:
    """심볼·HTF 한 셀의 상태. 없으면 미적용."""
    for r in (rows if rows is not None else gate_rows()):
        if r.get("symbol") == symbol and r.get("htf") == htf:
            return r
    return {"symbol": symbol, "htf": htf, "gate_align": None}


def state_text(row: dict) -> str:
    v = row.get("gate_align")
    if v is None:
        return GATE_NA
    return GATE_OPEN if v else GATE_CLOSED


def gate_label(symbol: str, interval: str, rows: Optional[list[dict]] = None) -> str:
    """파동 문구에 병기할 상위 게이트 라벨.

    승격 TF쌍의 LTF 가 아니면 게이트가 정의되지 않았음을 그대로 표기한다.
    예) "[1d 게이트 폐쇄 120봉]" / "[게이트 미적용 TF]"
    """
    htf = PROMOTED_LTF_TO_HTF.get(str(interval))
    if htf is None:
        return "[게이트 미적용 TF]"
    row = gate_state_for(symbol, htf, rows)
    if row.get("gate_align") is None:
        return f"[{htf} 게이트 상태 불명]"
    bars = int(row.get("open_bars") or 0)
    if row.get("gate_align"):
        return f"[{htf} 게이트 개방 {bars}봉]"
    rate = row.get("open_rate_recent")
    tail = f" · 최근 120봉 개방률 {rate * 100:.0f}%" if rate is not None else ""
    return f"[{htf} 게이트 폐쇄{tail}]"


def promoted_htf(interval: str) -> Optional[str]:
    return PROMOTED_LTF_TO_HTF.get(str(interval))


def promoted_htf_available(interval: str) -> bool:
    """승격 TF쌍의 LTF 인가 — 구조 기준선을 그릴 자격이 있는 TF인지."""
    return promoted_htf(interval) is not None


# ------------------------------------------------------------ 구조 기준선 (항목 4)
@st.cache_data(show_spinner=False, ttl=900)
def struct_reference(symbol: str, interval: str, signal_ts_iso: str) -> Optional[dict]:
    """직전 확정 swing 저점과 ×0.995 기준선.

    analysis.wave_mm_struct_stop.struct_stops() 를 그대로 호출한다 —
    reference_low 산출 경로를 재계산하지 않는다. 미검출·퇴화는 None 을 돌려
    호출부가 라인을 그리지 않게 한다.
    """
    from analysis.mm_shadow import load_shadow_bars
    from analysis.wave_mm_struct_stop import REASON_OK, struct_stops

    ts = pd.Timestamp(signal_ts_iso)
    events = pd.DataFrame({
        "event_id": ["UI"], "timestamp": [ts],
        "symbol": [symbol], "ltf": [str(interval)],
    })
    try:
        bars = load_shadow_bars(events, start=ts - interval_delta(interval) * 300)
        out = struct_stops(events, bars)
    except Exception:  # noqa: BLE001
        return None
    if out.empty:
        return None
    row = out.iloc[0]
    if str(row.get("reason")) != REASON_OK:
        return None
    return {
        "reference_low": float(row["reference_low"]),
        "line_price": float(row["stop_price"]),
        "reference_ts": str(ts),
    }


# ------------------------------------------------ 추적 현황 (항목 5 — 성과 금지)
@st.cache_data(show_spinner=False, ttl=900)
def tracking_counts() -> dict:
    """기록 행 수와 커버리지 기간만. **성과 지표는 계산하지도 반환하지도 않는다.**"""
    out: dict = {
        "review_due": REVIEW_DUE, "tracking_start": TRACKING_START,
        "gate_rows": 0, "gate_first": None, "gate_last": None,
        "shadow_by_variant": {v: 0 for v in VARIANTS},
        "shadow_first": None, "shadow_last": None, "shadow_mtime": None,
    }
    gate = sidecar_path()
    if os.path.isfile(gate):
        try:
            g = pd.read_csv(gate, parse_dates=["timestamp"])
            fwd = g[(g["timestamp"] >= TRACKING_START) & (g["gate_scope"] == "PROMOTED")]
            out["gate_rows"] = int(len(fwd))
            if len(fwd):
                out["gate_first"] = fwd["timestamp"].min()
                out["gate_last"] = fwd["timestamp"].max()
            out["gate_mtime"] = pd.Timestamp(os.path.getmtime(gate), unit="s")
        except Exception:  # noqa: BLE001
            pass
    shadow = shadow_path()
    if os.path.isfile(shadow):
        try:
            s = pd.read_csv(shadow, parse_dates=["signal_ts", "exit_ts"])
            out["shadow_by_variant"] = {
                v: int((s["variant"] == v).sum()) for v in VARIANTS
            }
            if len(s):
                out["shadow_first"] = s["signal_ts"].min()
                out["shadow_last"] = s["exit_ts"].max()
            out["shadow_mtime"] = pd.Timestamp(os.path.getmtime(shadow), unit="s")
        except Exception:  # noqa: BLE001
            pass
    return out


# ------------------------------------------------------------ 신선도 (항목 6)
def freshness(interval: str, last_bar_ts, now: Optional[pd.Timestamp] = None) -> dict:
    """마지막 수신 봉 대비 지연. 경고는 색상 판단 재료만 돌려준다 (알림 없음)."""
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow().tz_localize(None)
    if last_bar_ts is None or pd.isna(last_bar_ts):
        return {"last_bar": None, "lag": None, "lag_bars": None, "warn": True}
    last = pd.Timestamp(last_bar_ts)
    lag = now - last
    try:
        bars = lag / interval_delta(interval)
    except ValueError:
        bars = None
    return {
        "last_bar": last, "lag": lag,
        "lag_bars": None if bars is None else float(bars),
        "warn": bool(bars is not None and bars > FRESHNESS_WARN_BARS),
    }


def format_lag(lag) -> str:
    if lag is None or pd.isna(lag):
        return "—"
    total = int(pd.Timedelta(lag).total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    h, m = divmod(total // 60, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{sign}{d}일 {h}시간"
    if h:
        return f"{sign}{h}시간 {m}분"
    return f"{sign}{m}분"
