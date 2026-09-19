"""LW 가격 pane 구조 마커 훅(structure_markers) — 없으면 출력 불변, 있으면 표시 시프트·정렬·캔들 시리즈 배선."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import charts.lw_builder as LW  # noqa: E402


def _ohlc(n=30):
    idx = pd.date_range("2026-09-01", periods=n, freq="h")
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx)


def test_structure_markers_absent_keeps_html_identical_and_present_wires_to_candles():
    df = _ohlc()
    base = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    same = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="", structure_markers=[])
    assert base == same and "var STRUCTURE_MARKERS = [];" in base
    marks = [{"ts": pd.Timestamp("2026-09-01 05:00"), "position": "belowBar", "color": "#0B8F45", "shape": "circle", "text": "HL"},
             {"ts": pd.Timestamp("2026-09-01 02:00"), "position": "aboveBar", "color": "#C62828", "shape": "circle", "text": "HH"}]
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="", structure_markers=marks)
    payload = LW.structure_markers_payload(marks)
    assert [m["text"] for m in payload] == ["HH", "HL"]                                   # 시간순 정렬
    assert payload[0]["time"] == LW._display_seconds(pd.Timestamp("2026-09-01 02:00"))    # 표시 시프트 동일
    assert "LWC.createSeriesMarkers(candles, STRUCTURE_MARKERS)" in html and '"text": "HH"' in html
