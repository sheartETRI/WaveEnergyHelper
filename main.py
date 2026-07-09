# main.py — WaveEnergyHelper 진입점 (11차 위임: 표시 레이어 3탭 재구성).
#
# 열면 계기판이 먼저 보이고, 상세 분석은 필요할 때 들어가는 앱.
#   [탭1] 계기판   — 심볼 선택 → slope/월봉/전조 계기판 + 캠페인 카드 (display.v2_campaign_view)
#   [탭2] 상세 분석 — 45패널 카테고리 레지스트리 루프 (display.detail_tab)
#   [탭3] 저널     — forward·관측 계기판 최근 기록 (display.journal_tab)
#
# 조립부만 담당한다. 분석 로직·검출기·엔진 무수정. 45개 개별 import/호출은 레지스트리로 이관됨
# (구조 상세: docs/앱_사용법.md). 이전 v1 조립본은 legacy_main.py에 보존.
import streamlit as st

from config.settings import SUPPORTED_SYMBOLS
from display.detail_tab import render_detail_sidebar, render_detail_tab
from display.journal_tab import render_journal_tab
from display.v2_campaign_view import render_v2_campaign_view


def main():
    st.set_page_config(layout="wide", page_title="WaveEnergyHelper")

    # 공유 심볼(계기판·상세 분석 공통). TF·지표·패널 토글은 상세 분석 탭 전용 사이드바에서.
    st.sidebar.header("심볼")
    symbol = st.sidebar.selectbox("Symbol", options=SUPPORTED_SYMBOLS, index=0, key="global_symbol")
    st.sidebar.divider()
    detail_cfg = render_detail_sidebar()

    tab_dash, tab_detail, tab_journal = st.tabs(["계기판", "상세 분석", "저널"])

    with tab_dash:
        try:
            render_v2_campaign_view(symbol)
        except Exception as exc:  # noqa: BLE001 — 계기판 실패해도 앱은 계속
            st.warning(f"계기판 렌더 실패(앱 계속): {exc}")

    with tab_detail:
        render_detail_tab(symbol, detail_cfg)

    with tab_journal:
        try:
            render_journal_tab()
        except Exception as exc:  # noqa: BLE001
            st.warning(f"저널 탭 렌더 실패(앱 계속): {exc}")


if __name__ == "__main__":
    main()
