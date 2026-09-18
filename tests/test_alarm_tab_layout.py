"""알람 탭 정리(signal-alarm) — 이력 표 표시 필터·같은 시각 묶음 음영·컬럼 폭 + 본문 2탭 배선. 정의 무접촉."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import display.alarm_panel as AP
import main as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _frame():
    t = pd.Timestamp
    return pd.DataFrame([
        {"시각": t("2026-09-18 18:00"), "신호": "스토캐 쌍봉 후보", "레이어": "중(10,5,5)", "구분": "후보", "지표값": 91.9, "비고": "LH"},
        {"시각": t("2026-09-18 10:00"), "신호": "스토캐 쌍봉", "레이어": "소(5,3,3)", "구분": "확정", "지표값": 84.9, "비고": "HH"},
        {"시각": t("2026-09-18 10:00"), "신호": "스토캐 쌍바닥", "레이어": "대(20,10,10)", "구분": "확정", "지표값": 88.8, "비고": "LL"},
        {"시각": t("2026-09-18 04:00"), "신호": "RSI 과매수 진입", "레이어": "RSI", "구분": "확정", "지표값": 72.9, "비고": "기준 >70"},
        {"시각": t("2026-09-18 03:00"), "신호": "MACD 골든크로스", "레이어": "MACD", "구분": "확정", "지표값": 52.0, "비고": "교차 …"},
        {"시각": t("2026-09-18 03:00"), "신호": "스토캐 쌍바닥", "레이어": "소(5,3,3)", "구분": "확정", "지표값": 66.3, "비고": "LL"},
        {"시각": t("2026-09-18 02:00"), "신호": "스토캐 쌍봉 후보", "레이어": "대(20,10,10)", "구분": "후보", "지표값": 90.0, "비고": "HH"},
        {"시각": t("2026-09-18 02:00"), "신호": "스토캐 쌍바닥", "레이어": "중(10,5,5)", "구분": "확정", "지표값": 20.0, "비고": "LL"},
    ])


def test_layer_options_present_only_in_fixed_order():
    assert AP.history_layer_options(_frame()) == ["대(20,10,10)", "중(10,5,5)", "소(5,3,3)", "RSI", "MACD"]
    assert AP.history_layer_options(_frame().iloc[[3, 4]]) == ["RSI", "MACD"]
    assert AP.history_layer_options(pd.DataFrame(columns=["시각", "레이어"])) == []


def test_filter_defaults_to_all_and_keeps_order():
    f = _frame()
    assert AP.filter_history_frame(f).equals(f) and AP.filter_history_frame(f, [], []).equals(f)   # 빈 선택 = 전체
    sub = AP.filter_history_frame(f, layers=["RSI", "MACD"])
    assert sub["레이어"].tolist() == ["RSI", "MACD"]
    conf = AP.filter_history_frame(f, kinds=["확정"])
    assert (conf["구분"] == "확정").all() and len(conf) == 6
    both = AP.filter_history_frame(f, layers=["소(5,3,3)"], kinds=["확정"])
    assert both["신호"].tolist() == ["스토캐 쌍봉", "스토캐 쌍바닥"]       # 행 순서 유지(최신 위)


def test_same_time_groups_get_alternating_shading_only_when_two_or_more():
    colors = AP.history_group_colors(_frame())
    a, b = AP.HISTORY_GROUP_COLORS
    # 18:00 단독 / 10:00 묶음(a) / 04:00 단독 / 03:00 묶음(b) / 02:00 묶음(a)
    assert colors == ["", a, a, "", b, b, a, a]
    assert AP.history_group_colors(pd.DataFrame(columns=["시각"])) == []
    styler = AP.style_history_frame(_frame())
    assert hasattr(styler, "to_html")                                   # pandas Styler → st.dataframe 에 그대로


def test_column_widths_and_no_merge_logic():
    assert AP.HISTORY_COLUMN_WIDTHS["비고"] == "large"                     # 우측 잘림 방지
    assert set(AP.HISTORY_COLUMN_WIDTHS) == {"시각", "신호", "레이어", "구분", "지표값", "비고"}
    # 판정·병합 없음: 필터·음영 결과의 행 수는 입력 이하이고 내용은 그대로
    f = _frame()
    assert len(AP.filter_history_frame(f, kinds=["확정", "후보"])) == len(f)
    with open(os.path.join(ROOT, "display", "alarm_panel.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert "signals_to_frame(signals)" in body and "filter_history_frame(frame, layers=layer_pick, kinds=kind_pick)" in body
    assert 'width="stretch"' in body


def test_main_has_two_tabs_chart_first():
    assert M.MAIN_TABS == ("차트", "알람")
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert "tab_chart, tab_alarm = st.tabs(MAIN_TABS)" in body
    assert body.index("with tab_alarm:") < body.index("render_alarm_panel(") < body.index("with tab_chart:") < body.index("render_lw_chart(")
