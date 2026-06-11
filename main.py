# main.py
import streamlit as st
from config.settings import SUPPORTED_SYMBOLS, TIMEFRAMES, CUSTOM_INTERVALS
from data.binance import fetch_klines, fetch_klines_paginated, get_auto_limit
from data.processor import build_dataframe, resample_timeframe, get_fetch_interval
from indicators.moving_averages import add_moving_averages
from indicators.ma_patterns import add_ma_patterns
from indicators.ma_dispersion import add_ma_dispersion
from indicators.stochastic import add_stochastic_slow_layers
from indicators.oscillators import add_macd, add_rsi
from analysis.engine import get_ma_alignment
from analysis.wave_energy import analyze_wave_energy
from analysis.dynamics_rules import trace_transitions, structure_distribution
from display.asof import (
    build_ohlcv_cache,
    format_as_of_banner,
    parse_as_of,
    patch_load_frame_for_asof,
    truncate_to_asof,
)
from display.transition_radar import (
    build_transition_radar,
    prepare_trace_dataframe,
)
from narration.service import generate_narration
from config.settings import NARRATION_CONFIG, NARRATION_DISCLAIMER
from display.stability_verdict import (
    align_enriched_to_index,
    get_stability_enriched,
    render_stability_verdict_panel,
)
from display.wave_tracker_ui import (
    align_timeline_to_index as align_wave_tracker,
    get_wave_tracker_timeline,
    render_wave_tracker_panel,
)
from display.wave_confirmation_ui import (
    get_confirmation_episodes,
    render_wave_confirmation_panel,
)
from display.wave_confirmation_lifecycle_ui import (
    get_lifecycle_episodes,
    render_wave_lifecycle_panel,
)
from display.wave_survival_ui import render_wave_survival_panel
from display.wave_outcome_ui import render_wave_outcome_panel
from display.wave_exit_ui import render_wave_exit_panel
from display.wave_segmentation_ui import render_wave_segmentation_panel
from display.wave_expectancy_ui import render_wave_expectancy_panel
from display.wave_paths_ui import render_wave_paths_panel
from display.wave_branch_ui import render_wave_branch_panel
from display.wave_confluence_ui import render_wave_confluence_panel
from display.wave_candidate_rules_ui import render_wave_candidate_rules_panel
from display.wave_generalization_ui import render_wave_generalization_panel
from display.wave_regime_gated_ui import render_wave_regime_gated_panel
from charts.plotly_builder import render_chart


def is_narration_ui_available(config=None) -> bool:
    """NARRATION_CONFIG.enabled — False면 사이드바 체크박스·해설 경로 전부 비활성."""
    cfg = config if config is not None else NARRATION_CONFIG
    return bool(cfg.get("enabled", True))


def should_show_narration(user_opt_in: bool, config=None) -> bool:
    """마스터 on + 사용자 옵트인."""
    return is_narration_ui_available(config) and user_opt_in

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


def render_transition_radar(df):
    """변곡 레이더 — df에서 trace 계산 후 표시."""
    trace_df = prepare_trace_dataframe(df)
    render_transition_radar_content(
        build_transition_radar(trace_df, trace_transitions(trace_df)),
    )


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


def _fmt_bar(ts):
    if ts is None:
        return "-"
    try:
        return ts.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        return str(ts)


def render_dynamics_trace(df):
    """[Debug] §6-④⑤ 변곡점 트레이스 + 구조 분포를 expander로 표시한다 (관측 전용)."""
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


def main():
    st.set_page_config(layout="wide", page_title=" ")

    # --- Sidebar ---
    st.sidebar.header("Chart Settings")
    symbol = st.sidebar.selectbox("Select Symbol", options=SUPPORTED_SYMBOLS, index=0)
    interval = st.sidebar.selectbox("Select Timeframe", options=TIMEFRAMES, index=TIMEFRAMES.index("1d"))
    
    st.sidebar.subheader("Indicators")
    show_stoch = st.sidebar.checkbox("Show Stochastic Slow", value=True)
    stochastic_view_mode = st.sidebar.radio(
        "Stochastic View Mode",
        options=["Stacked", "Separated"],
        index=0,
        disabled=not show_stoch,
    )
    show_macd = st.sidebar.checkbox("Show MACD", value=True)
    show_rsi = st.sidebar.checkbox("Show RSI", value=True)
    show_ma_patterns = st.sidebar.checkbox("Show MA Patterns", value=False)
    show_ma_dispersion = st.sidebar.checkbox("MA Dispersion", value=False)
    debug_dynamics_trace = st.sidebar.checkbox("Debug: Dynamics Trace", value=False)
    show_ai_narration = False
    if is_narration_ui_available():
        show_ai_narration = st.sidebar.checkbox("AI 해설", value=False)
    show_stability_verdict = st.sidebar.checkbox("Show Stability Verdict", value=False)
    show_wave_tracker = st.sidebar.checkbox("Show Wave Tracker", value=False)
    show_wave_confirmation = st.sidebar.checkbox("Show Wave Confirmation", value=False)
    show_wave_lifecycle = st.sidebar.checkbox("Show Wave Lifecycle", value=False)
    show_wave_survival = st.sidebar.checkbox("Show Wave Survival", value=False)
    show_wave_outcome = st.sidebar.checkbox("Show Wave Outcome", value=False)
    show_wave_exit = st.sidebar.checkbox("Show Wave Exit", value=False)
    show_wave_segmentation = st.sidebar.checkbox("Show Wave Segmentation", value=False)
    show_wave_expectancy = st.sidebar.checkbox("Show Wave Expectancy", value=False)
    show_wave_paths = st.sidebar.checkbox("Show Wave Paths", value=False)
    show_wave_branch = st.sidebar.checkbox("Show Wave Branch", value=False)
    show_wave_confluence = st.sidebar.checkbox("Show Wave Confluence", value=False)
    show_candidate_rules = st.sidebar.checkbox("Show Candidate Rules", value=False)
    show_generalization = st.sidebar.checkbox("Show Generalization", value=False)
    show_regime_gated = st.sidebar.checkbox("Show Regime Gated", value=False)
    as_of_text = st.sidebar.text_input(
        "기준 시점 (백트레이스)",
        value="",
        placeholder="YYYY-MM-DD HH:MM",
        help="비우면 실시간. 설정 시 해당 시각 이하 데이터만 사용.",
    )
    as_of = parse_as_of(as_of_text)
    show_stoch_fill = show_stoch
    show_rsi_fill = show_rsi

    # --- Data Fetching & Processing ---
    limit = get_auto_limit(interval)
    if as_of is not None and symbol == "ETHUSDT" and interval == "4h":
        limit = 1600
    fetch_interval = get_fetch_interval(interval)

    with st.spinner(f"Loading {symbol} {interval} data..."):
        try:
            if as_of is not None and limit > 1000:
                raw_data = fetch_klines_paginated(symbol, fetch_interval, limit)
            else:
                raw_data = fetch_klines(symbol, fetch_interval, limit)
            if not raw_data:
                st.error(f"Failed to fetch data for {symbol}.")
                return

            df = build_dataframe(raw_data)
            if df is None or df.empty:
                st.error("Failed to build DataFrame.")
                return

            if interval in CUSTOM_INTERVALS:
                df = resample_timeframe(df, interval)

            ohlcv_bare_full = df.copy()
            if as_of is not None:
                df = truncate_to_asof(df, as_of)
                if df is None or df.empty:
                    st.error("기준 시점 이전 데이터가 없습니다.")
                    return
                if len(df) < 240:
                    st.error("기준 시점 이전 봉이 240미만 — MA 워밍업 부족.")
                    return
                st.warning(format_as_of_banner(as_of))

            # --- Indicator Calculation ---
            df = add_moving_averages(df)
            if show_ma_patterns:
                df = add_ma_patterns(df)
            if show_stoch:
                df = add_stochastic_slow_layers(df)
            if show_macd:
                df = add_macd(df)
            if show_rsi:
                df = add_rsi(df)
            if show_ma_dispersion:
                df = add_ma_dispersion(df)

            # --- Analysis ---
            alignment = get_ma_alignment(df)
            if as_of is not None:
                extra = {"4h": limit} if interval == "4h" else {}
                ohlcv_cache = build_ohlcv_cache(
                    symbol, interval, ohlcv_bare_full, extra_limits=extra,
                )
                with patch_load_frame_for_asof(symbol, as_of, ohlcv_cache):
                    report = analyze_wave_energy(df, symbol, interval)
            else:
                report = analyze_wave_energy(df, symbol, interval)
            render_wave_summary(report, alignment)
            trace_df = prepare_trace_dataframe(df)
            radar_content = build_transition_radar(trace_df, trace_transitions(trace_df))
            render_transition_radar_content(radar_content)
            render_wave_narration_if_enabled(
                show_ai_narration, report, alignment, df, radar_content,
            )

            if debug_dynamics_trace:
                render_dynamics_trace(df)

            stability_aligned = None
            if show_stability_verdict:
                extra_limits = {"4h": limit} if interval == "4h" else {}
                stab_cache = build_ohlcv_cache(
                    symbol, interval, ohlcv_bare_full, extra_limits=extra_limits,
                )
                as_of_iso = as_of.isoformat() if as_of is not None else ""
                with st.spinner("Building stability timeline..."):
                    if as_of is not None:
                        with patch_load_frame_for_asof(symbol, as_of, stab_cache):
                            enriched = get_stability_enriched(
                                symbol, interval, df, stab_cache, as_of_iso,
                            )
                    else:
                        enriched = get_stability_enriched(
                            symbol, interval, df, stab_cache, as_of_iso,
                        )
                    stability_aligned = align_enriched_to_index(enriched, df.index)
                render_stability_verdict_panel(stability_aligned)

            wave_tracker_aligned = None
            if show_wave_tracker:
                wt_cache = build_ohlcv_cache(
                    symbol, interval, ohlcv_bare_full,
                    extra_limits={"4h": limit} if interval == "4h" else {},
                )
                as_of_iso = as_of.isoformat() if as_of is not None else ""
                with st.spinner("Building wave tracker timeline..."):
                    if as_of is not None:
                        with patch_load_frame_for_asof(symbol, as_of, wt_cache):
                            wt_tl = get_wave_tracker_timeline(
                                symbol, interval, df, wt_cache, as_of_iso,
                            )
                    else:
                        wt_tl = get_wave_tracker_timeline(
                            symbol, interval, df, wt_cache, as_of_iso,
                        )
                    wave_tracker_aligned = align_wave_tracker(wt_tl, df.index)
                render_wave_tracker_panel(wave_tracker_aligned)

            if show_wave_confirmation:
                wc_cache = build_ohlcv_cache(
                    symbol, interval, ohlcv_bare_full,
                    extra_limits={"4h": limit} if interval == "4h" else {},
                )
                as_of_iso = as_of.isoformat() if as_of is not None else ""
                with st.spinner("Loading wave confirmation episodes..."):
                    if as_of is not None:
                        with patch_load_frame_for_asof(symbol, as_of, wc_cache):
                            wc_ep = get_confirmation_episodes(
                                symbol, interval, df, wc_cache, as_of_iso,
                            )
                    else:
                        wc_ep = get_confirmation_episodes(
                            symbol, interval, df, wc_cache, as_of_iso,
                        )
                render_wave_confirmation_panel(wc_ep)

            if show_wave_lifecycle:
                wl_cache = build_ohlcv_cache(
                    symbol, interval, ohlcv_bare_full,
                    extra_limits={"4h": limit} if interval == "4h" else {},
                )
                as_of_iso = as_of.isoformat() if as_of is not None else ""
                with st.spinner("Loading wave lifecycle..."):
                    if as_of is not None:
                        with patch_load_frame_for_asof(symbol, as_of, wl_cache):
                            wl_ep = get_lifecycle_episodes(
                                symbol, interval, df, wl_cache, as_of_iso,
                            )
                    else:
                        wl_ep = get_lifecycle_episodes(
                            symbol, interval, df, wl_cache, as_of_iso,
                        )
                render_wave_lifecycle_panel(wl_ep)

            if show_wave_survival:
                render_wave_survival_panel(symbol, interval)

            if show_wave_outcome:
                render_wave_outcome_panel(symbol, interval)

            if show_wave_exit:
                render_wave_exit_panel(symbol, interval)

            if show_wave_segmentation:
                render_wave_segmentation_panel(symbol, interval)

            if show_wave_expectancy:
                render_wave_expectancy_panel(symbol, interval)

            if show_wave_paths:
                render_wave_paths_panel(symbol, interval)

            if show_wave_branch:
                render_wave_branch_panel(symbol, interval)

            if show_wave_confluence:
                render_wave_confluence_panel(symbol, interval)

            if show_candidate_rules:
                render_wave_candidate_rules_panel(symbol, interval)

            if show_generalization:
                render_wave_generalization_panel(symbol, interval)

            if show_regime_gated:
                render_wave_regime_gated_panel(symbol, interval)

            # --- Rendering ---
            render_chart(
                df, symbol, interval,
                show_stochastic=show_stoch,
                stochastic_view_mode=stochastic_view_mode,
                show_stoch_fill=show_stoch_fill,
                show_macd=show_macd,
                show_rsi=show_rsi,
                show_rsi_fill=show_rsi_fill,
                show_ma_patterns=show_ma_patterns,
                show_ma_dispersion=show_ma_dispersion,
                show_stability=show_stability_verdict,
                stability_aligned=stability_aligned,
                show_wave_tracker=show_wave_tracker,
                wave_tracker_aligned=wave_tracker_aligned,
            )

        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
