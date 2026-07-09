"""저널 탭 (11차 위임 A [탭3]) — forward 저널·관측 계기판 저널 최근 기록 표.

표시·관측 전용. 두 저널은 표시 시점에 누적되므로 부재(파일 없음/빈 표)를 정상 상태로 처리한다.
관측 계기판 저널은 앱을 한 번도 열지 않았으면 없을 수 있다(계기판 렌더 시 생성).
"""
from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd
import streamlit as st

from config.settings import OBSERVATORY_PARAMS

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VALIDATION_DIR = os.path.join(_ROOT, "validation")
_FORWARD_JOURNAL = os.path.join(_VALIDATION_DIR, "wave_live_forward_journal.csv")


def _observatory_journal_path() -> str:
    path = OBSERVATORY_PARAMS.get("journal_path", "validation/observatory_journal.csv")
    if not os.path.isabs(path):
        path = os.path.join(_ROOT, path)
    return path


@st.cache_data(show_spinner=False, ttl=300)
def _read_csv(path: str, parse_dates: Optional[List[str]] = None) -> pd.DataFrame:
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates or [])
    except Exception:  # noqa: BLE001 — 손상/빈 CSV는 빈 표로 처리
        return pd.DataFrame()


def _recent(df: pd.DataFrame, sort_col: str, n: int) -> pd.DataFrame:
    if df.empty or sort_col not in df.columns:
        return df.tail(n) if not df.empty else df
    return df.sort_values(sort_col).tail(n).iloc[::-1]


def render_observatory_journal_section(n: int = 30) -> None:
    """관측 계기판 저널(slope/월봉/전조 스냅샷) 최근 n행."""
    st.markdown("### 관측 계기판 저널")
    st.caption("표시 시점의 slope·월봉·전조 상태 스냅샷 (관측·저널 전용, 판정 아님)")
    path = _observatory_journal_path()
    df = _read_csv(path, parse_dates=["ts"])
    if df.empty:
        st.info("관측 저널 없음 — 계기판 탭을 한 번 열면 스냅샷이 누적됩니다.")
        return
    st.caption(f"총 {len(df)}행 · 최근 {min(n, len(df))}행")
    st.dataframe(_recent(df, "ts", n), use_container_width=True, hide_index=True)


def render_forward_journal_section(n: int = 30) -> None:
    """forward 저널(라이브 후보 추적) 최근 n행."""
    st.markdown("### Forward 저널")
    st.caption("라이브 후보 추적 누적 (관측 전용, wave_live_forward_journal_sweep.py 산출)")
    df = _read_csv(_FORWARD_JOURNAL, parse_dates=["timestamp"])
    if df.empty:
        st.info("Forward 저널 없음 — wave_live_forward_journal_sweep.py 실행 필요.")
        return

    if "status" in df.columns:
        completed = int((df["status"] == "COMPLETED").sum())
        pending = int((df["status"] != "COMPLETED").sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("총 이벤트", len(df))
        c2.metric("COMPLETED", completed)
        c3.metric("진행/대기", pending)

    st.caption(f"최근 {min(n, len(df))}행 (timestamp 내림차순)")
    st.dataframe(_recent(df, "timestamp", n), use_container_width=True, hide_index=True)


def render_journal_tab() -> None:
    """[탭3] 저널 — forward·관측 계기판 최근 기록."""
    st.subheader("저널")
    st.caption("표시 시점 누적 기록 (전 구간 관측 라벨 — 판정/추천 아님)")
    render_observatory_journal_section()
    st.divider()
    render_forward_journal_section()
