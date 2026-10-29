"""종목별 마지막 조회의 큰 추세와 고정 관찰 설명을 전용 탭에 모은다."""
from typing import Callable, Optional

import streamlit as st

from data.binance import clear_klines_cache
from display.energy_observation import render_saved_energy_observation
from display.mtf_guidance import render_saved_observation
from display.trend_context import render_saved_trend_context
from display.wave_basis_radar import render_basis_radar_section


def render_observation_tab(symbol: str, *, on_open_chart: Optional[Callable[[str], None]] = None) -> None:
    """탭 이동은 저장 view 재생, 명시적 조회만 같은 종목의 선정 결과를 갱신한다."""
    st.subheader("큰 추세와 관찰 설명")
    st.caption("4일봉·일봉의 큰 추세를 먼저 보고 관찰할 TF와 다음 확인 조건을 읽습니다. 차트 시간봉을 바꿔도 이 관찰 대상은 유지됩니다.")
    scanned = f"mtf_radar_observation:{symbol}" in st.session_state
    notice_key = f"observation_scan_notice:{symbol}"
    if st.button("레이더 다시 조회" if scanned else "관찰 TF 찾기", key=f"observation_scan:{symbol}"):
        clear_klines_cache()
        scan_view = render_basis_radar_section(symbol, show_observation=False, show_radar=False)
        notices = []
        if scan_view.get("guidance", {}).get("changed"):
            notices.append(scan_view["guidance"]["change"])
        if scan_view.get("energy", {}).get("changed"):
            notices.append(f"파동 에너지 관찰: {scan_view['energy']['change']}")
        st.session_state[notice_key] = notices
        # 조회 완료 후 버튼을 재조회 상태로 바꾸고 저장 view를 한 번만 그린다.
        st.rerun()
    render_saved_trend_context(symbol)
    for notice in st.session_state.pop(notice_key, []):
        st.info(notice)
    render_saved_observation(symbol, on_open_chart=on_open_chart)
    render_saved_energy_observation(symbol, on_open_chart=on_open_chart)
