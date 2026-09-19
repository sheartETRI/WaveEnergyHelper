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
from display.tz_label import KST_LABEL, kst_text, to_kst

# 기본 이력 창(봉). 사이드바에서 조절.
DEFAULT_HISTORY_BARS = 120

# MACD 4종의 발화 지연 안내 — 규칙은 analysis.alarm_signals(다음 봉 확정). 항상 정확히 1봉.
MACD_DELAY_NOTE = "MACD 크로스·0선 신호는 교차 다음 봉이 부호를 유지해야 표시됩니다(교차 봉 +1봉 지연, 시각은 확정 봉)."

_ZONE_ICON = {"과매도": "🔵", "과매수": "🔴", "중립": "⚪", "-": "⚪"}

# --- 이력 표 표시 정리 (알람 탭) — 표시 계층 전용: 신호 정의·판정·병합 없음 ---
HISTORY_KINDS = ("확정", "후보")
# 레이어 필터 옵션 정렬: 스토캐 대/중/소 → RSI → MACD (이름 첫 글자 기준, 정의 파일의 비공개 맵을 쓰지 않는다)
_LAYER_ORDER = {"대": 0, "중": 1, "소": 2, "R": 3, "M": 4}
# 같은 시각 묶음 음영(2건 이상인 시각만). 인접 묶음이 붙어 보이지 않게 두 색을 번갈아 쓴다.
HISTORY_GROUP_COLORS = ("#FFF4E5", "#EAF2FF")
HISTORY_TIME_HEADER = f"시각 {KST_LABEL}"   # 표 헤더 라벨만 — 프레임 컬럼 키 "시각" 은 그대로(필터·묶음 로직 불변)
HISTORY_COLUMN_WIDTHS = {"시각": "medium", "신호": "medium", "레이어": "small", "구분": "small",
                         "지표값": "small", "비고": "large"}   # 비고가 우측에서 잘리지 않게


def history_frame_kst(frame: pd.DataFrame) -> pd.DataFrame:
    """이력 표 표시용 사본 — '시각' 을 KST 로, '비고' 안의 UTC 시각 문자열(예: MACD 교차 시각)도 KST 로.

    signals_to_frame(정의 계층)의 출력은 건드리지 않는다. 같은 시각 묶음·필터는 균일 시프트라 불변.
    """
    if frame is None or frame.empty:
        return frame
    out = frame.copy()
    if "시각" in out.columns:
        out["시각"] = out["시각"].map(to_kst)
    if "비고" in out.columns:
        out["비고"] = out["비고"].map(lambda v: kst_text(v) if isinstance(v, str) else v)
    return out


def history_layer_options(frame: pd.DataFrame) -> List[str]:
    """이력 표에 실제로 있는 레이어 이름만, 대/중/소/RSI/MACD 순."""
    if frame is None or frame.empty or "레이어" not in frame.columns:
        return []
    names = list(dict.fromkeys(str(v) for v in frame["레이어"].tolist()))
    return sorted(names, key=lambda n: (_LAYER_ORDER.get(n[:1], 9), n))


def filter_history_frame(frame: pd.DataFrame, layers: Optional[List[str]] = None,
                         kinds: Optional[List[str]] = None) -> pd.DataFrame:
    """표시 필터 — 빈 선택/None 은 '전체'(사이드바 스토캐 레이어 선택과 같은 관례). 행 순서는 유지."""
    if frame is None or frame.empty:
        return frame
    out = frame
    if layers:
        out = out[out["레이어"].isin(layers)]
    if kinds:
        out = out[out["구분"].isin(kinds)]
    return out


def history_group_colors(frame: pd.DataFrame) -> List[str]:
    """행별 배경색 — 같은 시각이 2건 이상이면(동시 신호, 상충 포함) 그 묶음을 음영, 단독 행은 빈 문자열.

    signals_to_frame 이 (시각, kind) 정렬을 역순으로 내므로 같은 시각은 이미 인접해 있다 — 여기서는 색만 붙인다.
    """
    if frame is None or frame.empty:
        return []
    ts = frame["시각"].tolist()
    colors, band, i = [], 0, 0
    while i < len(ts):
        j = i
        while j < len(ts) and ts[j] == ts[i]:
            j += 1
        if j - i >= 2:
            colors += [HISTORY_GROUP_COLORS[band % len(HISTORY_GROUP_COLORS)]] * (j - i)
            band += 1
        else:
            colors.append("")
        i = j
    return colors


def style_history_frame(frame: pd.DataFrame):
    """같은 시각 묶음에 배경색을 입힌 Styler (st.dataframe 에 그대로 넘긴다)."""
    colors = history_group_colors(frame)
    return frame.style.apply(
        lambda _col: [f"background-color: {c}" if c else "" for c in colors], axis=0,
    )


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
    return f"마지막 봉 {to_kst(last_ts):%Y-%m-%d %H:%M} {KST_LABEL} (미확정 가능){price}"


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
        col_bar.metric(f"마지막 봉 {KST_LABEL}", f"{to_kst(df.index[-1]):%m-%d %H:%M}",
                       help="미확정(진행 중) 봉일 수 있음 · 시각은 KST 표시(데이터는 UTC)")
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
        frame = history_frame_kst(signals_to_frame(signals))   # 표시 직전 1회 KST 변환(정의 계층 프레임은 UTC)
        if frame.empty:
            st.caption("해당 구간에 신호 없음")
        else:
            # 표시 필터(기본 전체) — 신호 산출은 위 recent_signals 그대로, 표에서만 거른다
            col_layer, col_kind = st.columns([3, 2])
            layer_pick = col_layer.multiselect(
                "레이어 필터", options=history_layer_options(frame), default=history_layer_options(frame),
                help="비우면 전체",
            )
            kind_pick = col_kind.multiselect("구분 필터", options=list(HISTORY_KINDS), default=list(HISTORY_KINDS),
                                             help="비우면 전체")
            shown = filter_history_frame(frame, layers=layer_pick, kinds=kind_pick)
            if shown.empty:
                st.caption("필터에 맞는 신호 없음")
            else:
                st.dataframe(
                    style_history_frame(shown),
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "시각": st.column_config.DatetimeColumn(HISTORY_TIME_HEADER, format="YYYY-MM-DD HH:mm",
                                                                  width=HISTORY_COLUMN_WIDTHS["시각"]),
                        "신호": st.column_config.TextColumn("신호", width=HISTORY_COLUMN_WIDTHS["신호"]),
                        "레이어": st.column_config.TextColumn("레이어", width=HISTORY_COLUMN_WIDTHS["레이어"]),
                        "구분": st.column_config.TextColumn("구분", width=HISTORY_COLUMN_WIDTHS["구분"]),
                        "지표값": st.column_config.NumberColumn("지표값", format="%.1f",
                                                                width=HISTORY_COLUMN_WIDTHS["지표값"]),
                        "비고": st.column_config.TextColumn("비고", width=HISTORY_COLUMN_WIDTHS["비고"]),
                    },
                )
                st.caption(
                    f"확정 {int((shown['구분'] == '확정').sum())}건 · "
                    f"후보 {int((shown['구분'] == '후보').sum())}건 · 같은 시각 묶음은 배경색으로 표시"
                )
