"""v2 시그널 카드 — 캠페인당 카드 1장 (§6). v2의 최종 소비 인터페이스.

45패널 나열이 아니라 이 카드가 메인 뷰다. build_campaign_card는 순수 함수(테스트 가능),
render_campaign_card는 streamlit 래퍼.

정직성 규율(§6): "과거 성적"은 저널 누적 전까지 "수집 중". 근거 없는 자신감 표시 금지.
전 구간 "관측 등급" 라벨(게이트 승격 전).
"""
from __future__ import annotations

from typing import List, Optional

from analysis.campaign_score import CampaignScore
from analysis.campaign_state_machine import (
    DONE,
    S5_WAVE2,
    S6_ENTRY2,
    S7_WAVE3,
    CampaignResult,
)

_STATE_KO = {
    "S0_SETUP": "S0 발단", "S1_CONFIRM": "S1 확인대기", "S2_ENTRY1": "S2 진입1",
    "S3_WAVE1": "S3 1파보유", "S4_EXIT1": "S4 청산1", S5_WAVE2: "S5 2파조정",
    S6_ENTRY2: "S6 재진입", S7_WAVE3: "S7 3파보유", DONE: "종료",
}
_DIR_KO = {"long": "매수 캠페인", "short": "매도 캠페인"}


def build_campaign_card(
    res: CampaignResult,
    score: CampaignScore,
    *,
    upper_info: Optional[str] = None,
    lower_info: Optional[str] = None,
    history: Optional[str] = None,
    region_price_label: Optional[str] = None,
    concordance_info: Optional[str] = None,
) -> List[str]:
    """§6 시그널 카드 라인들. 없는 정보는 정직하게 '수집 중'/'—'로 표시."""
    lines: List[str] = []
    lines.append(
        f"{res.symbol} · 기준 {res.base_tf} · {_DIR_KO.get(res.direction, res.direction)} "
        f"· 상태 {_STATE_KO.get(res.state, res.state)} · [관측 등급]"
    )

    # 발단
    kind = "HL" if res.direction == "long" else "LH"
    pat = "쌍바닥" if res.direction == "long" else "쌍봉"
    onset = f"발단: {res.setup_layer} {pat}({kind})"
    if res.strength_flag:
        onset += f" + 스토캐 삼중({res.strength_layer}) [강화]"
    lines.append(onset)

    # 진행: ENTRY-1 → EXIT-1
    if res.entry1 is not None:
        prog = f"진행: ENTRY-1 {res.entry1.price:.6g}"
        if res.exit1 is not None:
            t1 = f" ({score.t1_return:+.1%})" if score.t1_return is not None else ""
            label = "EXIT-1" if res.direction == "long" else "재매수전"
            prog += f" → {label} {res.exit1.price:.6g}{t1}"
        lines.append(prog)
    else:
        lines.append("진행: 진입 전 (MACD 크로스 대기)")

    # 2파 예측
    region = res.predicted_region_label
    if region_price_label:
        region = f"{region} = {region_price_label}"
    grade_ko = {"small": "소파동", "mid": "중파동", "large": "대파동"}.get(res.predicted_grade, "미정")
    lines.append(f"2파 예측: {grade_ko} → {region}")

    # 재진입 조건/결과
    if res.entry2 is not None:
        t2 = f" ({score.t2_return:+.1%})" if score.t2_return is not None else " (보유중)"
        lines.append(f"재진입: ENTRY-2 {res.entry2.price:.6g}{t2}")
    else:
        lines.append("재진입 조건: 구간 도달 AND MACD 재GC (대기중, 무효화 없음)")

    lines.append(f"하위 파동: {lower_info or '수집 중'}")
    lines.append(f"상위 참고: {upper_info or '수집 중'}")
    if concordance_info:
        lines.append(f"상응 합치: {concordance_info}")   # 관측 태그(게이트 아님)
    lines.append(f"과거 성적: {history or '수집 중'}")

    # 합산(종료 시)
    if score.combined_net is not None and res.state == DONE:
        lines.append(f"합산(net): {score.combined_net:+.2%} · MAE(T2) "
                     f"{'' if score.mae_t2 is None else format(score.mae_t2, '+.1%')}")
    return lines


def render_campaign_card(res: CampaignResult, score: CampaignScore, **kwargs) -> None:
    """streamlit 카드 렌더 (컨테이너 1개)."""
    import streamlit as st

    lines = build_campaign_card(res, score, **kwargs)
    with st.container(border=True):
        st.markdown(f"**{lines[0]}**")
        for ln in lines[1:]:
            st.caption(ln)


def build_candidate_note(ev) -> str:
    """candidate(넥라인 미돌파) 1건을 확정과 명확히 구분되는 표기로 (§B).

    예: '후보 — MA10 쌍바닥(HL) · 넥라인 612.4 상향 돌파 대기 [미확정·승격 불가]'.
    """
    pat = "쌍바닥" if ev.direction == "long" else "쌍봉"
    kdir = "상향" if ev.direction == "long" else "하향"
    nl = "—" if ev.neckline_price is None else f"{ev.neckline_price:.6g}"
    kind = f"({ev.kind})" if ev.kind else ""
    return (
        f"후보 — {ev.ma_or_layer} {pat}{kind} · 넥라인 {nl} {kdir} 돌파 대기 "
        f"[미확정 · 승격 불가]"
    )


def render_candidate_notes(events) -> None:
    """형성 중 candidate들을 확정 카드와 시각적으로 구분해 렌더 (streamlit).

    승격·진입 대상이 아님을 명시(표시·저널 전용, §B 금지사항).
    """
    import streamlit as st

    if not events:
        return
    with st.container(border=True):
        st.markdown("**형성 중 후보 (candidate) — 표시·관측 전용, 승격/진입 아님**")
        for ev in events:
            st.caption(build_candidate_note(ev))


def build_candle_note(ev) -> str:
    """캔들 쌍바닥/쌍봉 1건 표기 (§E, 관측·표시 전용, 승격 소스 아님)."""
    pat = "쌍바닥" if ev.direction == "long" else "쌍봉"
    kind = f"({ev.kind})" if ev.kind else ""
    nl = "—" if ev.neckline_price is None else f"{ev.neckline_price:.6g}"
    return (
        f"캔들 {pat}{kind} · 4봉 확정 {ev.confirmed_bar:%Y-%m-%d %H:%M} · 넥라인 {nl} "
        f"[하급 타이밍 · 승격 소스 아님]"
    )


def render_candle_notes(events, *, limit: int = 5) -> None:
    """최근 캔들 패턴들을 관측 전용으로 렌더 (streamlit). 승격 소스 아님 명시."""
    import streamlit as st

    if not events:
        return
    recent = sorted(events, key=lambda e: e.confirmed_pos, reverse=True)[:limit]
    with st.container(border=True):
        st.markdown("**캔들 패턴 (소파동급) — 검출·표시·저널 전용, 캠페인 승격 아님**")
        for ev in recent:
            st.caption(build_candle_note(ev))
