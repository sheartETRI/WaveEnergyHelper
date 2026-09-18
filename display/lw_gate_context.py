"""LW 차트의 게이트 문맥 라벨·구조 기준선 공급 (display 전용, 슬림 앱).

main 브랜치(8cdd4e5 계열)의 display/wave_gate_context 에 해당하는 얇은 글루다.
**정의 함수는 재구현하지 않는다** — main 에서 체리픽한 analysis 파일을 그대로 import 만 한다:

- F2-b 판정 + 마지막 닫힌 봉 asof: ``analysis.wave_align_gate_forward.current_gate_status``
  (내부에서 ``gate_states`` → ``analysis.wave_htf_gate_v2.f2b_rising_flags`` · ``close_time_of``;
  HTF 데이터는 ``load_htf_pipe`` 가 슬림 앱의 ``display.asof`` 로 라이브 취득 — 사이드카·연구 캐시 없음)
- swing 저점 검출 경로 + ×(1−BUFFER) 기준선: ``analysis.wave_mm_struct_stop.struct_stops``
  (``analysis.wave_structure_confirmation.find_swing_lows`` · ``_confirmed``). 입력 봉은 슬림 앱이 이미 적재한
  LTF 프레임을 그대로 쓴다.

체리픽 동일성은 CHERRYPICK_FILES(원본 커밋·sha256)로 고정하고 테스트가 diff 없음을 단언한다.

문구 규율(main 승계): 상태 기술형만. 성과 지표 노출 없음. "매수/매도 권고"류 표현 금지.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from analysis.wave_align_gate_forward import PROMOTED_LTF_TO_HTF, current_gate_status
from analysis.wave_mm_struct_stop import REASON_OK, struct_stops

# ------------------------------------------------------------------ 체리픽 매니페스트
# 원본: origin/main 74fa4ad (2026-09-04, 8cdd4e5 계열 — 이 파일들은 그 뒤 변경 없음). sha256 은 LF 정규화 본문.
CHERRYPICK_SOURCE_COMMIT = "74fa4ad"
CHERRYPICK_FILES = {
    "analysis/wave_htf_gate.py": "ecb3c703d5b4859fc5f5f9cdb16798e37355b1e515a78d1cca5a545dfb97f6b9",
    "analysis/wave_htf_gate_v2.py": "c1bfc943a19b8913c61f37dff303cc131758879b04d29df32485ee14c4a08264",
    "analysis/wave_align_gate_forward.py": "33cd487da062175ef0edf9e96dd48006a16fd2a775d72a85497b05e684be3bb0",
    "analysis/wave_mm_struct_stop.py": "2938831bc408024f4b4089b3d5d29084f3cfc3cb9dff9d11a704f98fee0f57e6",
    "analysis/wave_mm_simulator.py": "6bcc1a89b316d64dc59045062f672389c48dc21d309b69d500dc4e9152445313",
}

# 라벨 문구 — main display/wave_gate_context.gate_label 과 동일
GATE_NA_TF = "[게이트 미적용 TF]"


def promoted_htf(interval: str) -> Optional[str]:
    return PROMOTED_LTF_TO_HTF.get(str(interval))


# ------------------------------------------------------------------ 게이트 상태
def _fetch_gate_row(symbol: str, htf: str) -> dict:
    """심볼×HTF 한 셀 — current_gate_status 를 그 셀만 호출(네트워크 1회). 실패는 상태 불명."""
    try:
        rows = current_gate_status(symbols=(symbol,), htfs=(htf,))
    except Exception:  # noqa: BLE001 — 표시 전용이므로 실패해도 앱을 막지 않는다
        rows = []
    for r in rows:
        if r.get("symbol") == symbol and r.get("htf") == htf:
            return r
    return {"symbol": symbol, "htf": htf, "gate_align": None}


@st.cache_data(show_spinner=False, ttl=900)
def gate_row(symbol: str, htf: str) -> dict:
    return _fetch_gate_row(symbol, htf)


def gate_label(symbol: str, interval: str, row: Optional[dict] = None) -> str:
    """차트에 병기할 상위 게이트 라벨 (main gate_label 문구 그대로).

    예) "[4h 게이트 개방 12봉]" / "[4h 게이트 폐쇄 · 최근 120봉 개방률 35%]" / "[게이트 미적용 TF]"
    """
    htf = promoted_htf(interval)
    if htf is None:
        return GATE_NA_TF
    row = row if row is not None else gate_row(symbol, htf)
    if row.get("gate_align") is None:
        return f"[{htf} 게이트 상태 불명]"
    bars = int(row.get("open_bars") or 0)
    if row.get("gate_align"):
        return f"[{htf} 게이트 개방 {bars}봉]"
    rate = row.get("open_rate_recent")
    tail = f" · 최근 120봉 개방률 {rate * 100:.0f}%" if rate is not None else ""
    return f"[{htf} 게이트 폐쇄{tail}]"


# ------------------------------------------------------------------ 구조 기준선
def struct_reference(df: pd.DataFrame, symbol: str, interval: str) -> Optional[dict]:
    """직전 확정 swing 저점과 ×(1−BUFFER) 기준선 — struct_stops 를 그대로 호출한다.

    앵커 = 마지막 **닫힌** 봉(index[-2]). struct_stops 는 진입가를 신호봉 다음 봉 시가로 정의하므로
    진행 중인 마지막 봉이 그 '다음 봉'이 된다. 미검출(NO_REFERENCE_LOW)·퇴화(DEGENERATE)·예외는 None
    → 호출부가 "기준선 없음" 폴백.
    """
    if df is None or len(df) < 3 or not {"open", "high", "low", "close"}.issubset(df.columns):
        return None
    bars = df[["open", "high", "low", "close"]].copy()
    bars.index = pd.to_datetime(bars.index)
    bars = bars[~bars.index.duplicated(keep="last")].sort_index()
    if len(bars) < 3:
        return None
    ts = bars.index[-2]
    events = pd.DataFrame({
        "event_id": ["UI"], "timestamp": [ts], "symbol": [symbol], "ltf": [str(interval)],
    })
    try:
        out = struct_stops(events, {(symbol, str(interval)): bars})
    except Exception:  # noqa: BLE001
        return None
    if out is None or out.empty:
        return None
    row = out.iloc[0]
    if str(row.get("reason")) != REASON_OK:
        return None
    return {
        "reference_low": float(row["reference_low"]),
        "line_price": float(row["stop_price"]),
        "reference_ts": str(ts),
    }
