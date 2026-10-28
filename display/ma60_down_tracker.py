"""화면 렌더링과 이전 공개 API 호환. 공용 계산: tracking.ma60_down."""
from tracking.ma60_down import _DIR_MIRROR
from tracking.ma60_down import *  # noqa: F401,F403 - 이전 공개 API 유지
from display.analysis_cache import downward_candidates


def down_tracker_reference_lines(frame: pd.DataFrame) -> List[dict]:
    """대기 중 후보의 패턴 고점 — LW 가격 pane 가격선 사전(상승 쪽 ``tracker_reference_lines`` 와 같은 형식, 1선/후보).
    기준선(×1.005)은 두지 않으므로 고점선 하나뿐이다. 없으면 빈 목록."""
    from charts.lw_builder import LW_LINE_STYLE_DOTTED   # 지연 import — 차트 모듈이 없는 배포(main notify)에서도 이 모듈은 import 가능

    if frame is None or frame.empty:
        return []
    return [{"price": float(d[HIGH_COL]), "color": TRACKER_HIGH_COLOR, "style": LW_LINE_STYLE_DOTTED,
             "title": "", "label": TRACKER_HIGH_LABEL}
            for d in waiting_rows(frame).to_dict("records")]      # 이미 하방(해당 없음)은 대기 중이 아니므로 선 없음


def render_down_tracker_section(df: pd.DataFrame, symbol: str, interval: str,
                                recent_bars: int = RECENT_BARS) -> pd.DataFrame:
    """알람 탭 별도 섹션 — 상승 쪽 '60MA 전환 추적' 바로 옆(아래). 반환값은 후보 표(차트 고점선은 호출부가 ``down_tracker_reference_lines`` 로)."""
    import streamlit as st

    frame = downward_candidates(df, recent_bars=recent_bars)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        items = metric_items(summarize(frame))
        for col, (label, value, help_) in zip(st.columns(len(items)), items):
            col.metric(label, value, help=help_)
        if frame.empty:
            st.caption(EMPTY_CAPTION)
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
                   f"확정 시 60MA '이미 하방' 은 상태 '{STATUS_ALREADY_DOWN}'(창 진행 중이든 끝났든 같음) — 대기·소멸·실측에 들지 않고 건수만 별도 · "
                   f"{DOWN_DIVERGENCE_COL} = 스토캐(20,10,10) 둘째 봉우리 < 첫째 봉우리(LH) 이면서 두 피봇 봉의 고가는 둘째 > 첫째 "
                   "(상승 다이버전스 정의의 거울상, 판정 아님).")
    return frame
