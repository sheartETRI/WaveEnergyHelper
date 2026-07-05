"""v2 캠페인 종합 뷰 — 선택 심볼을 TF 사다리로 스캔, 최근 캠페인 카드 렌더 (§3·§6).

메인 뷰. 각 TF에서 가장 최근 승격 캠페인 1건을 리플레이해 카드로 보여준다.
상위 1단계 TF는 참고 표시만(진입 판정 미사용, §4). 데이터 충분성 부족 TF는 명시.
전 구간 관측 등급.
"""
from __future__ import annotations

from typing import Optional

from analysis.campaign_backtest import run_symbol_tf
from analysis.campaign_score import CampaignScore
from analysis.campaign_state_machine import CampaignResult
from analysis.tf_ladder import TF_LADDER, assess_tf_from_df, upper
from display.campaign_card import render_campaign_card


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


def _latest_campaign(symbol: str, tf: str):
    """해당 TF의 가장 최근 캠페인 (없으면 None)."""
    r = run_symbol_tf(symbol, tf)
    if not r.campaigns:
        return None, None, assess_tf_from_df(None, tf)
    res, score = r.campaigns[-1]
    return res, score, None


def render_v2_campaign_view(symbol: str) -> None:
    import streamlit as st

    st.subheader(f"v2 캠페인 종합 · {symbol}")
    st.caption("패턴 주도 기준 TF 승격 · 전 구간 관측 등급 (게이트 승격 전 추천 아님)")

    any_card = False
    for tf in TF_LADDER:
        try:
            res, score, insuff = _latest_campaign(symbol, tf)
        except Exception as exc:  # noqa: BLE001
            st.caption(f"{tf}: 스캔 실패 ({exc})")
            continue
        if res is None:
            st.caption(f"{tf}: 확정 캠페인 없음"
                       + (f" · {insuff.note}" if insuff and insuff.missing_ma_periods else ""))
            continue
        any_card = True
        render_campaign_card(
            res, score,
            upper_info=_upper_regime_note(symbol, tf),
            lower_info="수집 중 (하위 파동 카운팅 관측 전용)",
            history="수집 중",
        )
    if not any_card:
        st.info("현재 확정된 캠페인이 없습니다 (전 TF 스캔 결과).")
