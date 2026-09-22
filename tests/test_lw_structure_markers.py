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


# ------------------------------------------------------------ shape 배정(표시 스타일만, 판정 무접촉)
def test_structure_marker_shape_assignment_and_legend():
    """HH·HL=arrowUp / LH·LL=square / EQ=circle, 60MA 전환=circle(LL 파랑 사각과 구분). 범례 문구 고정."""
    assert LW.STRUCTURE_MARKER_SHAPE == {"HH": "arrowUp", "HL": "arrowUp", "LH": "square", "LL": "square", "EQ": "circle"}
    assert LW.TURN_MARKER_SHAPE == "circle"
    assert LW.STRUCTURE_LEGEND_CAPTION == "▲ HH·HL 유지 ■ LH 경고 ■ LL 훼손"
    assert set(LW.STRUCTURE_MARKER_SHAPE.values()) | {LW.TURN_MARKER_SHAPE} <= {"circle", "square", "arrowUp", "arrowDown"}


def test_trend_structure_markers_take_shape_from_lw_builder_and_keep_position_color_text():
    import display.trend_structure as TS

    ts = pd.Timestamp("2026-09-01 00:00")
    chain = [{"ts": ts + pd.Timedelta(hours=i), "kind": k, "price": p, "cls": c, "pct": None}
             for i, (k, p, c) in enumerate([("고점", 110, "HH"), ("저점", 104, "HL"), ("고점", 108, "LH"), ("저점", 100, "LL"), ("고점", 108, "EQ")])]
    result = {"chain": chain, "turn": {"ts": ts + pd.Timedelta(hours=9), "price": 105.0, "pos": 9, "swings_before": 5, "status": "x"}}
    marks = TS.structure_markers(result)
    assert [(m["text"], m["shape"], m["position"]) for m in marks] == [
        ("HH", "arrowUp", "aboveBar"), ("HL", "arrowUp", "belowBar"),
        ("LH", "square", "aboveBar"), ("LL", "square", "belowBar"),
        ("EQ", "circle", "aboveBar"), ("60MA", "circle", "belowBar"),
    ]
    assert [m["color"] for m in marks] == ["#C62828", "#0B8F45", "#EF6C00", "#1565C0", "#616161", "#7E57C2"]
    # LL(파랑 사각)과 60MA 전환(보라)은 shape 이 다르다
    assert marks[3]["shape"] != marks[5]["shape"]
    # 텍스트 임계 40 유지 — 초과 시 텍스트만 생략, shape 는 그대로
    assert TS.MARKER_TEXT_MAX == 40
    dense = TS.structure_markers(dict(result, chain=chain * 9))
    assert all(m["text"] == "" for m in dense) and dense[0]["shape"] == "arrowUp" and dense[-1]["shape"] == "circle"
    # 직렬화도 shape 를 그대로 싣는다
    payload = LW.structure_markers_payload(marks)
    assert [m["shape"] for m in payload] == ["arrowUp", "arrowUp", "square", "square", "circle", "circle"]


def test_render_adds_legend_caption_only_when_structure_markers_present(monkeypatch):
    captions = []
    monkeypatch.setattr(LW.components, "html", lambda html, **kw: None)
    monkeypatch.setattr(LW.st, "caption", lambda text: captions.append(text))
    df = _ohlc()
    LW.render_lw_chart(df, "BTCUSDT", "1h", "[g]", chart_height=600)
    assert captions == [LW.LW_CONTROLS_CAPTION]
    captions.clear()
    marks = [{"ts": pd.Timestamp("2026-09-01 02:00"), "position": "aboveBar", "color": "#C62828", "shape": "arrowUp", "text": "HH"}]
    LW.render_lw_chart(df, "BTCUSDT", "1h", "[g]", chart_height=600, structure_markers=marks)
    assert captions == [LW.LW_CONTROLS_CAPTION, LW.STRUCTURE_LEGEND_CAPTION]
