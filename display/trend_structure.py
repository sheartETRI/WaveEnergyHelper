"""화면 렌더링과 이전 공개 API 호환. 공용 계산: tracking.structure."""
from tracking.structure import *  # noqa: F401,F403 - 이전 공개 API 유지
from display.analysis_cache import structure_analysis
from tracking.structure import _cls, _pct, _fmt_ts, _fmt_px
from charts.lw_builder import STRUCTURE_MARKER_SHAPE, TURN_MARKER_SHAPE


def structure_markers(result: Optional[dict]) -> List[dict]:
    """가격 pane 마커 — 고점은 봉 위, 저점은 봉 아래, 분류 텍스트. 밀집(MARKER_TEXT_MAX 초과)이면 텍스트 생략.

    shape 는 charts.lw_builder.STRUCTURE_MARKER_SHAPE(HH·HL arrowUp / LH·LL square / EQ circle), 60MA 전환은
    TURN_MARKER_SHAPE(circle) — 표시 스타일만, 판정 무접촉.
    """
    if not result or not result["chain"]:
        return []
    dense = len(result["chain"]) > MARKER_TEXT_MAX
    out = []
    for r in result["chain"]:
        is_high = r["kind"] == KIND_HIGH
        out.append({"ts": r["ts"], "position": "aboveBar" if is_high else "belowBar",
                    "color": MARKER_COLORS.get(r["cls"], MARKER_COLORS[CLS_EQ]),
                    "shape": STRUCTURE_MARKER_SHAPE.get(r["cls"], STRUCTURE_MARKER_SHAPE[CLS_EQ]),
                    "text": "" if dense else r["cls"]})
    t = result.get("turn") or {}
    if t.get("pos") is not None:
        out.append({"ts": t["ts"], "position": "belowBar", "color": MARKER_COLORS[KIND_TURN], "shape": TURN_MARKER_SHAPE,
                    "text": "" if dense else "60MA"})
    return out


def render_structure_section(df: pd.DataFrame, symbol: str, interval: str) -> Optional[dict]:
    """알람 탭 별도 섹션. 반환값은 분석 결과(차트 마커에 재사용)."""
    import streamlit as st

    result = structure_analysis(df)
    with st.container(border=True):
        st.markdown(f"**{SECTION_TITLE} · {symbol} {interval}**")
        st.caption(FIXED_CAPTION)
        if result is None:
            st.caption(NO_BASE_CAPTION)
            return None
        items = metric_items(result)
        for col, (label, value, help_) in zip(st.columns(len(items)), items):
            col.metric(label, value, help=help_)
        for line in detail_captions(result):
            st.caption(line)
        frame = chain_frame(result)
        if frame.empty:
            st.caption(NO_SWING_CAPTION)
        else:
            st.dataframe(frame, hide_index=True, width="stretch",
                         column_config={c: st.column_config.TextColumn(c) for c in COLUMNS})
        st.caption(f"스윙 = 좌우 {PIVOT}봉 대칭 극값(기존 swing 검출기, 확정에 {PIVOT}봉 후행) · 분류는 직전 동종 극점 대비 · "
                   f"시각은 {KST_LABEL} 표시 · 마지막 봉은 진행 중일 수 있음 · 파동 번호 없음 · 권고 없음")
    return result
