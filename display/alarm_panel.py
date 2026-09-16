"""알람 패널 — 앱 화면 내 신호 표시(외부 전송 없음).

build_* 는 순수 텍스트/표(테스트 가능), render_* 는 streamlit 래퍼. 신호 추출은
analysis.alarm_signals 가 담당하고 여기서는 표시만 한다.

세 단: 현재 상태 배지 → 마지막 봉 알람 → 최근 N봉 신호 이력. 신호 종류(스토캐 쌍바닥·
쌍봉, RSI 과매도·과매수, MACD 크로스·0선)는 모두 같은 줄 형식·방향 색으로 섞여 나온다.
"마지막 봉"은 아직 닫히지 않은 진행 중 봉일 수 있다 — 확정 신호도 봉이 닫히기 전에는
되돌아갈 수 있으므로 그 사실을 캡션으로 같이 적는다(관측 라벨 유지, 매매 추천 아님).
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from analysis.alarm_signals import (
    DIR_BULL,
    SEV_CONFIRMED,
    AlarmSignal,
    recent_signals,
    rsi_zone,
    signals_to_frame,
)

# 기본 이력 창(봉). 사이드바에서 조절.
DEFAULT_HISTORY_BARS = 120

# MACD 4종의 발화 지연 안내 — 규칙은 analysis.alarm_signals(다음 봉 확정). 항상 정확히 1봉.
MACD_DELAY_NOTE = "MACD 크로스·0선 신호는 교차 다음 봉이 부호를 유지해야 표시됩니다(교차 봉 +1봉 지연, 시각은 확정 봉)."

_ZONE_ICON = {"과매도": "🔵", "과매수": "🔴", "중립": "⚪", "-": "⚪"}


def signal_icon(signal: AlarmSignal) -> str:
    """방향·확정 여부를 한 글자로. 확정은 채운 표식, 후보는 빈 표식."""
    if signal.severity == SEV_CONFIRMED:
        return "🔵" if signal.direction == DIR_BULL else "🔴"
    return "🔹" if signal.direction == DIR_BULL else "🔸"


def format_signal_line(signal: AlarmSignal) -> str:
    """신호 한 줄 — "🔵 스토캐 쌍바닥 · 대(20,10,10) · %K 18.4 · HL" 형태.

    MACD 는 가격 스케일이라 소수 한 자리로 뭉개지므로 유효숫자 4자리로 적는다
    ("🔵 MACD 골든크로스 · MACD · hist 12.34 · MACD -56.7").
    """
    parts = [f"{signal_icon(signal)} {signal.label}", signal.layer_name]
    if signal.value is not None:
        metric = signal.metric_name
        value = f"{signal.value:.4g}" if signal.layer_name == "MACD" else f"{signal.value:.1f}"
        parts.append(f"{metric} {value}")
    if signal.detail:
        parts.append(signal.detail)
    if signal.severity != SEV_CONFIRMED:
        parts.append("미확정(넥라인 돌파 전)")
    return " · ".join(parts)


def build_header(symbol: str, interval: str) -> str:
    """패널 제목. 관측 라벨을 유지한다(매매 추천 아님)."""
    return f"알람 · {symbol} {interval} — [관측]"


def build_bar_caption(df: pd.DataFrame) -> str:
    """마지막 봉 시각·종가 캡션. 마지막 봉은 아직 닫히지 않았을 수 있다."""
    if df is None or df.empty:
        return "데이터 없음"
    last_ts = df.index[-1]
    close = df["close"].iloc[-1] if "close" in df.columns else None
    price = "" if close is None or pd.isna(close) else f"  ·  종가 {float(close):,.8g}"
    return f"마지막 봉 {last_ts:%Y-%m-%d %H:%M} (미확정 가능){price}"


def has_macd(df: pd.DataFrame) -> bool:
    """MACD 알람이 가능한 프레임인지(add_macd 를 거쳤는지). 지연 안내 표시 여부 결정."""
    return df is not None and not df.empty and "macd" in df.columns


def build_status_lines(df: pd.DataFrame, symbol: str, interval: str) -> List[str]:
    """상태 요약 전체 — 제목, 마지막 봉, 현재 RSI 구역, (MACD 있으면) 지연 안내. 텍스트 요약/테스트용."""
    head = build_header(symbol, interval)
    if df is None or df.empty:
        return [head, "데이터 없음"]
    zone = rsi_zone(df)
    lines = [head, build_bar_caption(df), f"RSI 구역 {_ZONE_ICON.get(zone, '⚪')} {zone}"]
    if has_macd(df):
        lines.append(MACD_DELAY_NOTE)
    return lines


def build_current_bar_lines(signals: List[AlarmSignal], last_ts) -> List[str]:
    """마지막 봉에서 발생한 신호 줄 목록. 없으면 빈 목록."""
    if last_ts is None:
        return []
    return [format_signal_line(s) for s in signals if s.timestamp == last_ts]


def render_alarm_panel(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
    history_bars: int = DEFAULT_HISTORY_BARS,
    include_candidates: bool = True,
    layers: Optional[List[str]] = None,
) -> None:
    """알람 패널 렌더. df는 add_stochastic_slow_layers / add_rsi / add_macd 를 거친 프레임."""
    import streamlit as st

    with st.container(border=True):
        st.markdown(f"**{build_header(symbol, interval)}**")

        if df is None or df.empty:
            st.caption("데이터 없음")
            return

        signals = recent_signals(
            df, bars=history_bars, layers=layers, include_candidates=include_candidates
        )
        current = build_current_bar_lines(signals, df.index[-1])
        zone = rsi_zone(df)

        col_zone, col_bar, col_count = st.columns(3)
        col_zone.metric("RSI 구역", f"{_ZONE_ICON.get(zone, '⚪')} {zone}")
        col_bar.metric("마지막 봉", f"{df.index[-1]:%m-%d %H:%M}", help="미확정(진행 중) 봉일 수 있음")
        col_count.metric(f"최근 {history_bars}봉 신호", f"{len(signals)}건")
        st.caption(build_bar_caption(df))
        if has_macd(df):
            st.caption(MACD_DELAY_NOTE)

        st.markdown("**마지막 봉 알람**")
        if current:
            for line in current:
                st.warning(line)
        else:
            st.caption("마지막 봉에 새 신호 없음")

        st.markdown(f"**최근 {history_bars}봉 신호 이력**")
        frame = signals_to_frame(signals)
        if frame.empty:
            st.caption("해당 구간에 신호 없음")
        else:
            st.dataframe(
                frame,
                hide_index=True,
                column_config={
                    "시각": st.column_config.DatetimeColumn("시각", format="YYYY-MM-DD HH:mm"),
                    "지표값": st.column_config.NumberColumn("지표값", format="%.1f"),
                },
            )
            st.caption(
                f"확정 {int((frame['구분'] == '확정').sum())}건 · "
                f"후보 {int((frame['구분'] == '후보').sum())}건"
            )
