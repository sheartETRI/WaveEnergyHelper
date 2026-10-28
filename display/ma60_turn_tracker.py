"""화면 렌더링과 이전 공개 API 호환. 공용 계산: tracking.ma60_turn."""
from tracking.ma60_turn import *  # noqa: F401,F403 - 이전 공개 API 유지
from tracking.ma60_turn import _ma_dir, _fmt_ts, _fmt_px
from display.analysis_cache import upward_candidates


def tracker_reference_lines(frame: pd.DataFrame) -> List[dict]:
    """대기 중 후보의 저점·기준선 — LW 가격 pane 가격선 사전(구조 기준선과 같은 형식). 없으면 빈 목록."""
    from charts.lw_builder import LW_LINE_STYLE_DASHED, LW_LINE_STYLE_DOTTED

    if frame is None or frame.empty:
        return []
    lines: List[dict] = []
    for d in waiting_rows(frame).to_dict("records"):        # 이미 상방(해당 없음)은 대기 중이 아니므로 선을 긋지 않는다
        lines.append({"price": float(d["패턴 저점"]), "color": TRACKER_LOW_COLOR, "style": LW_LINE_STYLE_DOTTED,
                      "title": "", "label": TRACKER_LOW_LABEL})
        lines.append({"price": float(d["기준선(×0.995)"]), "color": TRACKER_LINE_COLOR, "style": LW_LINE_STYLE_DASHED,
                      "title": "", "label": TRACKER_LINE_LABEL})
    return lines


def render_tracker_section(df: pd.DataFrame, symbol: str, interval: str,
                           recent_bars: int = RECENT_BARS) -> Tuple[pd.DataFrame, list]:
    """알람 탭 별도 섹션. 반환값은 (후보 표, 기울기 (tf, snapshot) 목록) — 후보 표는 차트 연동에, 둘 다 전체 복사용
    텍스트(display.alarm_copy_text)에 재사용(재계산 없음)."""
    import streamlit as st

    from display.ma60_slope import render_slope_block   # 기울기 실측(표시 전용, 판정 없음) — 섹션 상단 블록

    frame = upward_candidates(df, recent_bars=recent_bars)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        slope_rows = render_slope_block(df, symbol, interval)
        items = metric_items(summarize(frame))
        for col, (label, value, help_) in zip(st.columns(len(items)), items):
            col.metric(label, value, help=help_)
        if frame.empty:
            st.caption(EMPTY_CAPTION)
        else:
            st.caption(bar_unit_caption(interval))
            st.dataframe(
                display_frame(frame, symbol, interval), hide_index=True, width="stretch",
                column_config={c: st.column_config.TextColumn(DISPLAY_HEADERS.get(c, c), width=TABLE_COLUMN_WIDTHS.get(c))
                               for c in COLUMNS},
            )
        st.caption(summary_line(frame, recent_bars))
        st.caption(divergence_summary_line(frame))
        st.caption(f"대기 중 = 대파동(20,10,10) 쌍바닥 확정 후 {OBS_BARS}봉 창이 살아 있는 후보 · "
                   f"경과/소요 = 확정봉 기준 봉 수(대기: 현재까지 경과, 전환 발생: 전환까지 소요, 소멸: 창 종료까지) · "
                   f"창은 후보 가용 시점(피봇 확정 지연 1~2봉 가능) 기준 {OBS_BARS}봉이라 지연 후보는 분모에 '+N봉' 표기 · "
                   f"시각은 {KST_LABEL} 표시 · 마지막 봉은 진행 중일 수 있음 · "
                   f"확정 시 60MA '이미 상방' 은 상태 '{STATUS_ALREADY_UP}'(창 진행 중이든 끝났든 같음) — 대기·소멸·전환율에 들지 않고 건수만 별도 · "
                   f"{DIVERGENCE_COL} = 스토캐(20,10,10) 둘째 저점 > 첫째 저점(HL) 이면서 두 피봇 봉의 저가는 둘째 < 첫째 "
                   "(단일 정의, docs/CANDIDATES_POST_2027_03).")
    return frame, slope_rows
