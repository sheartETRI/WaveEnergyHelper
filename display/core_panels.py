"""핵심 표시 패널 (11차 위임 B) — 파동에너지 요약·변곡 레이더·역학·해설·디버그.

main.py에 있던 v1 표시 헬퍼를 display 계층으로 이관한다(조립부에서 표시 로직 제거).
로직·판정은 analysis 모듈 소유 — 이 파일은 streamlit 렌더 래퍼만. 등급/추천 없음(관측 라벨).
"""
from __future__ import annotations

import streamlit as st

from analysis.dynamics_rules import structure_distribution, trace_transitions
from config.settings import NARRATION_CONFIG, NARRATION_DISCLAIMER
from narration.service import generate_narration


# ---------------------------------------------------------------- 해설 게이팅
def is_narration_ui_available(config=None) -> bool:
    """NARRATION_CONFIG.enabled — False면 사이드바 체크박스·해설 경로 전부 비활성."""
    cfg = config if config is not None else NARRATION_CONFIG
    return bool(cfg.get("enabled", True))


def should_show_narration(user_opt_in: bool, config=None) -> bool:
    """마스터 on + 사용자 옵트인."""
    return is_narration_ui_available(config) and user_opt_in


# ---------------------------------------------------------------- 파동에너지 요약
def _pattern_text(ws):
    """파동 패턴 요약 문자열. 쓰리 패턴은 확정 시에만 덧붙인다(미발생 시 변화 없음)."""
    text = f"DB:{ws.double_bottom}/DT:{ws.double_top}"
    if ws.triple_bottom == "확정":
        text += " · 쓰리바닥 확정"
    if ws.triple_top == "확정":
        text += " · 쓰리봉 확정"
    return text


def render_wave_summary(report, alignment):
    """파동에너지 분석 결과 요약 패널을 차트 위에 표시한다."""
    st.subheader("파동에너지 분석")
    c1, c2, c3, c4 = st.columns(4)

    trend = report.trend
    if trend.valid:
        c1.metric(
            "일봉 60MA 추세",
            trend.direction,
            f"{trend.slope_pct:+.2f}% · 가격 {'위' if trend.price_above_ma else '아래'}",
            delta_color="off",
        )
    else:
        c1.metric("일봉 60MA 추세", "검증불가", delta_color="off")

    bl = report.base_large
    if bl.valid:
        c2.metric(
            "대파동 (Top)",
            bl.direction,
            f"{bl.zone} · {_pattern_text(bl)}",
            delta_color="off",
        )
    else:
        c2.metric("대파동 (Top)", "검증불가", delta_color="off")

    us = report.upper_small
    upper_label = f"상위 {report.upper_interval} 소파동" if report.upper_interval else "상위 소파동"
    if us.valid:
        c3.metric(upper_label, us.direction, f"MTF {report.mtf_agreement}", delta_color="off")
    else:
        c3.metric(upper_label, "검증불가", f"MTF {report.mtf_agreement}", delta_color="off")

    bs = report.base_small
    if bs.valid:
        c4.metric(
            "소파동 타이밍 (Bot)",
            bs.direction,
            f"{bs.zone} · {_pattern_text(bs)}",
            delta_color="off",
        )
    else:
        c4.metric("소파동 타이밍 (Bot)", "검증불가", delta_color="off")

    st.markdown(f"### {report.verdict}")
    st.caption(f"MA 배열: {alignment}")
    if report.notes:
        st.caption(" / ".join(report.notes))

    _render_dynamics(report.dynamics)


# ---------------------------------------------------------------- 변곡 레이더
def render_transition_radar_content(content):
    """변곡 레이더 — 환경·형성 중·최근 이력 (표시 전용, 기본 표시)."""
    st.markdown("**변곡 레이더**")

    if content.environment_line:
        st.markdown(content.environment_line)

    if content.forming_items:
        for item in content.forming_items:
            st.markdown(item.headline_html, unsafe_allow_html=True)
            st.markdown(item.detail)
    else:
        st.markdown("변곡 형성 중인 패턴 없음")

    if content.recent_caption:
        st.caption(content.recent_caption)


# ---------------------------------------------------------------- AI 해설
def render_wave_narration(report, alignment, df, radar_content):
    """AI 해설 — Gemini OpenAI 호환 (표시 계층)."""
    st.markdown("**AI 해설**")
    last_ts = df.index[-1] if df is not None and not df.empty else None
    result = generate_narration(report, alignment, radar_content, last_ts)
    st.markdown(result.body)
    st.caption(NARRATION_DISCLAIMER)
    if result.extra_caption:
        st.caption(result.extra_caption)


def render_wave_narration_if_enabled(
    user_opt_in: bool,
    report,
    alignment,
    df,
    radar_content,
    *,
    config=None,
):
    """옵트인일 때만 해설 섹션·generate_narration 진입 (off 시 호출 0)."""
    if not should_show_narration(user_opt_in, config):
        return
    render_wave_narration(report, alignment, df, radar_content)


# ---------------------------------------------------------------- 역학관계
def _is_transition(hit):
    """TransitionHit 여부 (변곡점 전환은 bullish 속성을 가진다)."""
    return hit is not None and hasattr(hit, "bullish")


def _dispersion_headline_tag(hit):
    """이격도 유형 주석 괄호부. type None이면 생략."""
    if hit.dispersion_type is None:
        return ""
    pct = f"{hit.dispersion_pct:.1f}%" if hit.dispersion_pct is not None else ""
    return f" ({hit.dispersion_type} {pct})"


def _render_dynamics(dynamics):
    """역학관계(§6-①②④⑤) 판정을 verdict 아래에 표시한다."""
    transition_hits = getattr(dynamics, "transition_hits", []) if dynamics else []
    if dynamics is None or (not dynamics.hits and not transition_hits):
        st.caption("역학관계: 해당 패턴 없음")
        return

    head = dynamics.headline
    if head is not None:
        if _is_transition(head):
            tag = _dispersion_headline_tag(head)
            st.markdown(f"**⚡ 변곡점 [{head.rule_id}]{tag}: {head.description}**")
        else:
            st.markdown(f"**역학관계 [{head.rule_id}]: {head.description}**")

    for th in transition_hits:
        if th is head:
            continue
        st.caption(f"⚡ [{th.rule_id}] {th.description}")

    for hit in dynamics.hits:
        if hit is head:
            continue
        st.caption(f"[{hit.rule_id}] {hit.description}")

    if dynamics.notes:
        st.caption(" / ".join(dynamics.notes))


# ---------------------------------------------------------------- 디버그 트레이스
def _fmt_bar(ts):
    if ts is None:
        return "-"
    try:
        return ts.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        return str(ts)


def render_dynamics_trace(df):
    """[Debug] §6-④⑤ 변곡점 트레이스 + 구조 분포를 expander로 표시한다 (관측 전용)."""
    from indicators.ma_patterns import add_ma_patterns
    from indicators.stochastic import add_stochastic_slow_layers

    trace_df = df
    if "ma5_db" not in trace_df.columns:
        trace_df = add_ma_patterns(trace_df)
    sample_suffix = "(20,10,10)"
    if f"stoch_k_{sample_suffix}" not in trace_df.columns:
        trace_df = add_stochastic_slow_layers(trace_df)

    with st.expander("Debug: Dynamics Trace (§6-④⑤ 변곡점)", expanded=True):
        traces = trace_transitions(trace_df)
        rows = []
        for tr in traces:
            atom_status = " | ".join(
                f"{at.atom}: {'OK' if at.satisfied else (at.block_reason or 'BLOCK')}"
                for at in tr.atoms
            )
            pct_cell = (
                f"{tr.dispersion_pct:.1f}%"
                if tr.result == "HIT" and tr.dispersion_pct is not None
                else "-"
            )
            rows.append({
                "rule_id": tr.rule_id,
                "result": tr.result,
                "atoms": atom_status,
                "formation_bar": _fmt_bar(tr.formation_bar),
                "completion_bar": _fmt_bar(tr.completion_bar),
                "structure(req/actual)": f"{tr.structure_required}/{tr.structure_actual}",
                "dispersion_pct": pct_cell,
                "dispersion_type": tr.dispersion_type if tr.result == "HIT" else "-",
            })
        st.markdown("**Transition rule trace (8행)**")
        st.dataframe(rows, use_container_width=True, hide_index=True)

        dist = structure_distribution(trace_df)
        total = sum(dist.values()) or 1
        dist_rows = [
            {"structure": ("None" if k is None else k), "count": v, "ratio": f"{v / total * 100:.1f}%"}
            for k, v in dist.items()
        ]
        st.markdown(f"**Structure distribution (총 {total}봉)**")
        st.dataframe(dist_rows, use_container_width=True, hide_index=True)
