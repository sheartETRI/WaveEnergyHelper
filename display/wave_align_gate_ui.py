"""F2-b 배열 게이트 개방/폐쇄 상태 표시 (SPEC_WAVE_ALIGN_GATE §6).

**표시 전용이다.** 이 패널은 상태를 보여줄 뿐 어떤 이벤트도 걸러내거나 순서를 바꾸지 않는다.
gate_align 은 기록 전용 플래그이며 매매 신호가 아니다 (docs/SPEC_WAVE_ALIGN_GATE_FORWARD.md §3).
"""
from __future__ import annotations

import os

import streamlit as st

_VALIDATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "validation",
)

DISCLAIMER = (
    "기록 전용 · 매매 신호 아님 — 이 게이트는 6개월 전방 추적(§6) 중이며, "
    "이벤트 집합이나 순위에 어떤 영향도 주지 않는다."
)


@st.cache_data(show_spinner=False, ttl=900)
def _gate_status():
    from analysis.wave_align_gate_forward import current_gate_status

    return current_gate_status()


@st.cache_data(show_spinner=False, ttl=1800)
def _sidecar_summary():
    import pandas as pd

    from analysis.wave_align_gate_forward import forward_slice

    path = os.path.join(_VALIDATION_DIR, "wave_align_gate_forward.csv")
    if not os.path.isfile(path):
        return None
    sc = pd.read_csv(path, parse_dates=["timestamp"])
    fwd = forward_slice(sc)
    return {
        "total": len(sc),
        "scope": sc["gate_scope"].value_counts().to_dict(),
        "forward": len(fwd),
        "forward_open": int(fwd["gate_align"].fillna(False).astype(bool).sum()) if len(fwd) else 0,
    }


def render_wave_align_gate_panel(symbol: str, interval: str) -> None:
    from analysis.wave_align_gate_forward import (
        PROMOTED_LTF_TO_HTF,
        REVIEW_RULE,
        tracking_status,
    )

    st.subheader("F2-b 배열 게이트 상태")
    st.caption(DISCLAIMER)

    status = tracking_status()
    cols = st.columns(3)
    cols[0].metric("추적 시작", str(status["start"].date()))
    cols[1].metric("보고 예정", str(status["due"].date()))
    cols[2].metric("경과", f"{status['elapsed_days']}일")

    try:
        rows = _gate_status()
    except Exception as exc:  # noqa: BLE001 — 표시 전용이므로 실패해도 앱을 막지 않는다
        st.warning(f"게이트 상태를 불러오지 못했습니다: {exc}")
        return

    if not rows:
        st.info("게이트 상태 없음.")
        return

    st.markdown("**현재 개방 여부** (마지막 닫힌 HTF 봉 기준, F2-b = MA60·120·240 모두 상승)")
    for htf in sorted({r["htf"] for r in rows}):
        st.markdown(f"`HTF {htf}`")
        cols = st.columns(len([r for r in rows if r["htf"] == htf]))
        for col, r in zip(cols, [r for r in rows if r["htf"] == htf]):
            open_ = r.get("gate_align")
            label = "OPEN" if open_ else ("N/A" if open_ is None else "CLOSED")
            col.metric(
                r["symbol"].replace("USDT", ""),
                label,
                delta=(f"연속 {r.get('open_bars', 0)}봉" if open_ else None),
                delta_color="normal" if open_ else "off",
            )
            col.caption(f"최근 120봉 개방률 {r.get('open_rate_recent')}")

    ltf_map = ", ".join(f"{ltf}→{htf}" for ltf, htf in PROMOTED_LTF_TO_HTF.items())
    st.caption(f"승격 TF쌍 (LTF→HTF): {ltf_map}")

    summary = _sidecar_summary()
    if summary:
        st.markdown("**전방 추적 기록**")
        st.write(
            f"사이드카 이벤트 {summary['total']}건 · 승격 쌍 평가 "
            f"{summary['scope'].get('PROMOTED', 0)}건 · "
            f"추적 시작 이후 {summary['forward']}건 (게이트 개방 {summary['forward_open']}건)"
        )
    else:
        st.caption("사이드카 없음 — `python validation/wave_align_gate_forward_sweep.py --annotate`")

    with st.expander("재검토 트리거 (동결 규칙)"):
        st.write(REVIEW_RULE)
        st.caption("docs/SPEC_WAVE_ALIGN_GATE_FORWARD.md §2 — 전방 데이터를 보기 전에 확정됨.")
