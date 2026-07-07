"""v2 캠페인 종합 뷰 — 선택 심볼을 TF 사다리로 스캔, 최근 캠페인 카드 렌더 (§3·§6).

메인 뷰. 각 TF에서 가장 최근 승격 캠페인 1건을 리플레이해 카드로 보여준다.
상위 1단계 TF는 참고 표시만(진입 판정 미사용, §4). 데이터 충분성 부족 TF는 명시.
전 구간 관측 등급.
"""
from __future__ import annotations

from typing import Optional

from analysis.campaign_backtest import run_symbol_tf
from analysis.candle_patterns import scan_candle_patterns
from analysis.campaign_score import CampaignScore
from analysis.campaign_state_machine import CampaignResult
from analysis.concordance import concordance_at
from analysis.pattern_scanner import scan_ma_candidates
from analysis.tf_ladder import TF_POOL, assess_tf_from_df, upper
from display.campaign_card import (
    render_campaign_card,
    render_candidate_notes,
    render_candle_notes,
)

_CONCORD_KO = {"confirmed": "확정 합치", "in_progress": "진행 중 합치", "none": "합치 없음", "n/a": "상응 없음"}


def _upper_regime_note(symbol: str, base_tf: str) -> str:
    """상위 1단계 TF 레짐(MA120 vs MA240) — 참고 표시만."""
    up = upper(base_tf)
    if up is None:
        return "상위 없음 (사다리 최상단)"
    try:
        from analysis.campaign_state_machine import prepare_base_frame
        from display.asof import fetch_ohlcv_bare

        bare = fetch_ohlcv_bare(symbol, up)
        if bare is None or bare.empty:
            return f"{up} 수집 중"
        full = prepare_base_frame(bare)
        last = full.iloc[-1]
        ma120, ma240 = last.get("MA120"), last.get("MA240")
        if ma120 is None or ma240 is None:
            return f"{up} 레짐 판정 데이터 부족"
        import pandas as pd
        if pd.isna(ma120) or pd.isna(ma240):
            return f"{up} 레짐 판정 데이터 부족"
        regime = "UP" if ma120 > ma240 else "DOWN"
        return f"{up} 레짐 {regime}"
    except Exception:
        return f"{up} 수집 중"


def _scan_tf(symbol: str, tf: str):
    """단일 fetch로 프레임 + 최근 캠페인 + 형성 중 candidate를 함께 산출.

    반환: (res, score, insuff, candidates). res None이면 확정 캠페인 없음.
    """
    from analysis.campaign_state_machine import prepare_base_frame
    from display.asof import fetch_ohlcv_bare

    bare = fetch_ohlcv_bare(symbol, tf)
    if bare is None or bare.empty:
        return None, None, assess_tf_from_df(None, tf), []
    full = prepare_base_frame(bare)
    r = run_symbol_tf(symbol, tf, full_df=full)
    candidates = scan_ma_candidates(full, symbol, tf, periods=[5, 10, 20])
    candles = scan_candle_patterns(full, symbol, tf)
    if not r.campaigns:
        return None, None, assess_tf_from_df(full, tf), candidates, candles, full
    res, score = r.campaigns[-1]
    return res, score, None, candidates, candles, full


def render_v2_campaign_view(symbol: str) -> None:
    import streamlit as st

    st.subheader(f"v2 캠페인 종합 · {symbol}")
    st.caption("패턴 주도 기준 TF 승격 · 전 구간 관측 등급 (게이트 승격 전 추천 아님)")

    any_card = False
    for tf in TF_POOL:
        try:
            res, score, insuff, candidates, candles, full = _scan_tf(symbol, tf)
        except Exception as exc:  # noqa: BLE001
            st.caption(f"{tf}: 스캔 실패 ({exc})")
            continue
        if res is None:
            st.caption(f"{tf}: 확정 캠페인 없음"
                       + (f" · {insuff.note}" if insuff and insuff.missing_ma_periods else ""))
        else:
            any_card = True
            concord = concordance_at(full, res.setup_layer, res.direction, res.setup_pos)
            from analysis.trend_layer import trend_state_at, trend_state_label
            t_state = trend_state_label(trend_state_at(full, res.setup_pos))
            render_campaign_card(
                res, score,
                upper_info=_upper_regime_note(symbol, tf),
                lower_info="수집 중 (하위 파동 카운팅 관측 전용)",
                concordance_info=_CONCORD_KO.get(concord, concord),
                history=f"추세상태(관측): {t_state} · 수집 중",
            )
        # candidate·캔들은 확정 유무와 무관하게 표시(관측 전용 — 승격/진입 아님, §B·§E).
        render_candidate_notes(candidates)
        render_candle_notes(candles)
    if not any_card:
        st.info("현재 확정된 캠페인이 없습니다 (전 TF 스캔 결과).")
