"""LW 엔진 1단계 — charts/lw_builder 단위·스모크.

- JSON 직렬화: 시간 정렬·중복 제거·NaN 처리·거래량 색
- gate_context 필수 인자, 기준선 없음 폴백, 기준선 2개 라벨
- 벤더 파일 존재·버전 헤더, 동작 요건 옵션(autoScale·휠·팬·autoSize), 색 토큰 승계
- 렌더 스모크: components.html 문자열 생성·높이 전달, 2단계 캡션
- main 배선: 차트 엔진 라디오(기본 LW, Plotly 회귀 경로), plotly_builder 는 lw_builder 를 모른다
"""
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from charts import lw_builder as LW  # noqa: E402
from charts.plotly_builder import COLOR_BEAR, COLOR_BULL, RECENT_WINDOW  # noqa: E402
from config.settings import MA_COLORS, MA_LINE_WIDTHS  # noqa: E402


def _frame(n=40):
    rng = np.random.default_rng(7)
    idx = pd.date_range("2026-01-01", periods=n, freq="h")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({
        "open": close - 0.3, "high": close + 0.8, "low": close - 0.8, "close": close,
        "volume": rng.uniform(1, 5, n),
    }, index=idx)
    df["MA5"] = df["close"].rolling(5).mean()
    df["MA20"] = df["close"].rolling(20).mean()
    return df


# ------------------------------------------------------------ 직렬화
def test_payload_sorted_unique_and_nan_free():
    df = _frame(30)
    shuffled = df.sample(frac=1.0, random_state=1)                 # 순서 뒤섞기
    dup = pd.concat([shuffled, df.iloc[[10]]])                     # 중복 시각 1개
    dup.loc[dup.index[3], "close"] = np.nan                        # OHLC NaN 1개 → 캔들 제외
    payload = LW.frame_to_lw_payload(dup)

    times = [c["time"] for c in payload["candles"]]
    assert times == sorted(times) and len(times) == len(set(times))
    assert len(payload["candles"]) == 29                            # 30 - NaN 1 (중복은 1건으로)
    assert all(isinstance(c["time"], int) for c in payload["candles"])
    assert set(payload["candles"][0]) == {"time", "open", "high", "low", "close"}
    # MA 는 워밍업 NaN 을 뺀다: MA5 → 26점 이하, MA20 → 11점 이하 (NaN 종가 행 영향 포함)
    assert set(payload["mas"]) == {"5", "20"}
    assert 0 < len(payload["mas"]["20"]) < len(payload["mas"]["5"]) <= 26
    assert all(np.isfinite(p["value"]) for p in payload["mas"]["5"])
    json.dumps(payload)                                             # 직렬화 가능


def test_payload_time_is_utc_seconds_of_naive_index():
    df = _frame(3)
    payload = LW.frame_to_lw_payload(df)
    assert payload["candles"][0]["time"] == int(pd.Timestamp("2026-01-01").timestamp())
    assert payload["candles"][1]["time"] - payload["candles"][0]["time"] == 3600


def test_volume_colors_follow_bull_bear_tokens():
    df = _frame(6)
    df.loc[df.index[0], ["open", "close"]] = [10.0, 11.0]   # 상승
    df.loc[df.index[1], ["open", "close"]] = [11.0, 10.0]   # 하락
    df.loc[df.index[2], ["open", "close"]] = [10.0, 10.0]   # 보합 → 상승 색 (>=)
    vol = LW.frame_to_lw_payload(df)["volume"]
    assert [v["color"] for v in vol[:3]] == [COLOR_BULL, COLOR_BEAR, COLOR_BULL]
    assert COLOR_BULL == "#ff0000" and COLOR_BEAR == "#0000ff"


def test_payload_without_ohlc_or_empty_is_empty():
    empty = {"candles": [], "volume": [], "mas": {}, "stoch": None, "macd": None, "rsi": None,
             "markers": {"stoch": {}, "rsi": [], "macd": []}}
    assert LW.frame_to_lw_payload(pd.DataFrame()) == empty
    assert LW.frame_to_lw_payload(pd.DataFrame({"close": [1.0]})) == empty


# ------------------------------------------------------------ 계약: gate_context · 기준선
def test_gate_context_is_required():
    df = _frame()
    with pytest.raises(TypeError):
        LW.build_lw_html(df, "BTCUSDT", "1h", chart_height=600, vendor_js="")   # 위치 인자 누락
    with pytest.raises(ValueError):
        LW.build_lw_html(df, "BTCUSDT", "1h", "", chart_height=600, vendor_js="")
    with pytest.raises(ValueError):
        LW.build_lw_html(df, "BTCUSDT", "1h", "   ", chart_height=600, vendor_js="")


def test_struct_reference_fallback_and_lines():
    assert LW.struct_reference_lines(None) == []
    assert LW.struct_reference_lines({}) == []
    assert LW.struct_reference_lines({"reference_low": 1.0}) == []
    assert LW.struct_reference_lines({"reference_low": float("nan"), "line_price": 1.0}) == []
    lines = LW.struct_reference_lines({"reference_low": 100.0, "line_price": 99.5})
    assert [l["price"] for l in lines] == [100.0, 99.5]
    assert [l["title"] for l in lines] == ["", ""]                              # 차트 내 title 제거
    assert [l["label"] for l in lines] == [LW.STRUCT_LOW_LABEL, LW.STRUCT_LINE_LABEL]
    assert lines[0]["color"] != lines[1]["color"]                                # 축 뱃지는 색으로 구분
    assert LW.STRUCT_LINE_LABEL == "패턴 저점 기준선 (검증 중)"   # main 8cdd4e5 문구
    for l in lines:
        assert "손절" not in l["label"] and "권고" not in l["label"]

    df = _frame()
    html_none = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 X]", chart_height=600, vendor_js="")
    assert LW.STRUCT_LINE_MISSING in html_none and "var STRUCT_LINES = [];" in html_none
    html_ref = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 X]", chart_height=600, vendor_js="",
                                struct_reference={"reference_low": 100.0, "line_price": 99.5})
    assert LW.STRUCT_LINE_MISSING not in html_ref
    assert "createPriceLine" in html_ref and "axisLabelVisible: true" in html_ref  # 축 가격 뱃지 유지
    assert '"title": ""' in html_ref and LW.STRUCT_LINE_LABEL not in html_ref      # 차트 내 라벨 없음


def test_struct_caption_line_format_with_swatches():
    """캡션 줄: ' · ─ 저점 76,046 · ┄ 기준선 75,666 (검증 중)' — 색 견본은 각 선 색, '(검증 중)' 유지."""
    lines = LW.struct_reference_lines({"reference_low": 76046.0, "line_price": 75665.77})
    cap = LW.struct_caption_html(lines)
    assert cap == (' · <span style="color:#8D6E63">─</span> 저점 76,046'
                   ' · <span style="color:#EF5350">┄</span> 기준선 75,666 (검증 중)')
    assert LW.struct_caption_html([]) == " · 기준선 없음"
    assert LW.format_price(76046.0) == "76,046" and LW.format_price(612.3456) == "612.35"
    html = LW.build_lw_html(_frame(), "BTCUSDT", "1h", "[4h 게이트 폐쇄]", chart_height=600, vendor_js="",
                            struct_reference={"reference_low": 76046.0, "line_price": 75665.77})
    cap_div = html.split('id="lw-caption"', 1)[1].split("</div>", 1)[0]
    assert "BTCUSDT 1h · [4h 게이트 폐쇄] · " in cap_div and "저점 76,046" in cap_div
    assert "기준선 75,666 (검증 중)" in cap_div and 'color:#8D6E63' in cap_div and 'color:#EF5350' in cap_div
    # 알람 마커 텍스트는 이번 범위 아님 — 그대로 markers+text 경로 (createSeriesMarkers 유지)
    assert "createSeriesMarkers" in html


def test_caption_carries_gate_context_and_escapes_html():
    df = _frame()
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[1d 게이트 폐쇄 <120봉>]", chart_height=600, vendor_js="")
    assert 'id="lw-caption"' in html
    assert "BTCUSDT 1h · [1d 게이트 폐쇄 &lt;120봉&gt;]" in html


# ------------------------------------------------------------ 벤더 · 동작 요건 · 토큰
def test_vendor_file_is_present_with_version_header():
    assert os.path.isfile(LW.VENDOR_PATH)
    src = LW.load_vendor_js()
    head = src[:1200]
    assert f"lightweight-charts {LW.VENDOR_VERSION}" in head        # 벤더링 헤더(우리)
    assert LW.VENDOR_HEADER_MARK in head                            # 원본 라이선스 헤더(TradingView)
    assert "Apache License 2.0" in head
    assert LW.VENDOR_VERSION == "5.2.1"
    assert len(src) > 150_000
    # 헤더에 적힌 upstream sha256 과 실제 본문(원본 라이선스 주석부터)의 해시가 일치한다.
    m = re.search(r"sha256\(upstream file\) = ([0-9a-f]{64})", head)
    body = src[src.index("/*!\n * @license"):]
    assert m and hashlib.sha256(body.encode("utf-8")).hexdigest() == m.group(1)


def test_chart_options_meet_behaviour_requirements():
    opts = LW.chart_options()
    assert opts["rightPriceScale"]["autoScale"] is True             # x 줌·팬 시 y 자동 밀착
    assert opts["handleScale"]["mouseWheel"] is True                 # 휠 줌
    assert opts["handleScroll"]["pressedMouseMove"] is True          # 드래그 팬
    assert opts["crosshair"]["mode"] == 0                            # 크로스헤어 Normal
    assert opts["autoSize"] is True                                  # 컨테이너 폭 추종
    assert opts["timeScale"]["timeVisible"] is True
    cand = LW.candle_options()
    assert cand["upColor"] == COLOR_BULL and cand["downColor"] == COLOR_BEAR
    assert cand["wickUpColor"] == COLOR_BULL and cand["wickDownColor"] == COLOR_BEAR


def test_ma_tokens_are_inherited():
    styles = LW.ma_styles()
    assert set(styles) == {str(p) for p in MA_COLORS}
    for period, color in MA_COLORS.items():
        st = styles[str(period)]
        assert st["color"] == color
        assert st["width"] == LW.lw_line_width(MA_LINE_WIDTHS.get(period, 1.0))
        assert st["style"] == (LW.LW_LINE_STYLE_DASHED if period in (40, 80) else LW.LW_LINE_STYLE_SOLID)
    assert [LW.lw_line_width(w) for w in (1.0, 1.2, 1.4, 1.6, 1.8, 9.0)] == [1, 1, 1, 2, 2, 4]


def test_html_embeds_vendor_payload_and_window():
    df = _frame(200)
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=777, vendor_js="/*VENDOR*/")
    assert "<script>/*VENDOR*/</script>" in html
    assert f"var WINDOW = {RECENT_WINDOW};" in html
    assert "height:777px" in html
    assert '"autoScale": true' in html and '"autoSize": true' in html
    assert "var LWC = LightweightCharts;" in html
    assert "LWC.CandlestickSeries" in html and "LWC.HistogramSeries" in html and "LWC.LineSeries" in html
    assert "window.__lw" in html
    # 벤더 JS 를 기본 경로에서 실제로 인라인한다.
    full = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=600)
    assert LW.VENDOR_HEADER_MARK in full


# ------------------------------------------------------------ 렌더 스모크
def test_render_smoke_calls_components_html_with_height(monkeypatch):
    calls, captions = [], []
    monkeypatch.setattr(LW.components, "html", lambda html, **kw: calls.append((html, kw)))
    monkeypatch.setattr(LW.st, "caption", lambda text: captions.append(text))
    LW.render_lw_chart(_frame(), "BTCUSDT", "1h", "[g]", chart_height=1000)
    assert len(calls) == 1
    html, kw = calls[0]
    assert kw["height"] == 1000 and kw.get("scrolling") is False
    assert html.startswith("<!-- lw_builder stage2 -->") and LW.VENDOR_HEADER_MARK in html
    assert captions == [LW.LW_CONTROLS_CAPTION]
    assert all(w in LW.LW_CONTROLS_CAPTION for w in ("휠", "가격축", "더블클릭", "패널 경계"))


def test_render_skips_empty_frame(monkeypatch):
    calls = []
    monkeypatch.setattr(LW.components, "html", lambda html, **kw: calls.append(html))
    LW.render_lw_chart(pd.DataFrame(), "BTCUSDT", "1h", "[g]", chart_height=600)
    LW.render_lw_chart(None, "BTCUSDT", "1h", "[g]", chart_height=600)
    assert calls == []


# ------------------------------------------------------------ 배선 · Plotly 무영향
def test_main_wires_engine_radio_default_lw():
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert 'CHART_ENGINES = ("LW", "Plotly")' in body            # Plotly 는 회귀 경로로 유지
    assert 'DEFAULT_CHART_ENGINE = "LW"' in body                     # 2단계 완료 시점 전환
    assert '"차트 엔진", options=list(CHART_ENGINES)' in body
    assert "render_lw_chart(" in body and "gate_context=" in body or "gate_context_for(" in body
    import main as M
    assert M.DEFAULT_CHART_ENGINE == "LW" and set(M.CHART_ENGINES) == {"LW", "Plotly"}
    # gate_context_for 는 display.lw_gate_context.gate_label 에 위임한다 (네트워크 없이 확인)
    M.gate_label = lambda symbol, interval: f"[{symbol}/{interval}]"
    assert M.gate_context_for("BTCUSDT", "1h") == "[BTCUSDT/1h]"
    assert "struct_reference=struct_reference(df, symbol, interval)" in body


def test_plotly_builder_is_untouched_by_lw_layer():
    with open(os.path.join(ROOT, "charts", "plotly_builder.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "lw_builder" not in src and "lightweight-charts.standalone" not in src
    assert "streamlit_lightweight_charts" not in open(LW.__file__, encoding="utf-8").read()


# ============================================================ 2단계: pane 구성 직렬화
def _pipeline_frame(n=700):
    """main.load_frame 과 같은 지표 순서 — 스토캐 3층·MACD·RSI 컬럼 포함."""
    from indicators.moving_averages import add_moving_averages
    from indicators.oscillators import add_macd, add_rsi
    from indicators.stochastic import add_stochastic_slow_layers

    rng = np.random.default_rng(20260918)
    idx = pd.date_range("2026-01-01", periods=n, freq="h")
    close = 100 + np.cumsum(rng.normal(0, 1.1, n))
    df = pd.DataFrame({
        "open": close + rng.normal(0, 0.2, n), "high": close + np.abs(rng.normal(0, 0.7, n)),
        "low": close - np.abs(rng.normal(0, 0.7, n)), "close": close, "volume": rng.uniform(1, 10, n),
    }, index=idx)
    return add_rsi(add_macd(add_stochastic_slow_layers(add_moving_averages(df))))


def test_stoch_pane_payload_keeps_three_offset_layers_and_guides():
    from config.settings import STOCH_BAND, STOCH_GAP, STOCH_LAYERS, STOCH_MAX_Y

    payload = LW.frame_to_lw_payload(_pipeline_frame())
    st_ = payload["stoch"]
    assert st_ and [L["label"] for L in st_["layers"]] == [l["label"] for l in STOCH_LAYERS]
    for L, cfg in zip(st_["layers"], STOCH_LAYERS):
        assert L["offset"] == cfg["offset"] and L["k_color"] == cfg["k_color"] and L["d_color"] == cfg["d_color"]
        assert L["guides"] == [20 + cfg["offset"], 80 + cfg["offset"]]          # 층당 20/80
        vals = [p["value"] for p in L["k"]]
        assert min(vals) >= cfg["offset"] - 1e-9 and max(vals) <= cfg["offset"] + 100 + 1e-9   # 오프셋 배치
        assert all(np.isfinite(p["value"]) for p in L["k"] + L["d"])
    assert st_["separators"] == [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5]
    assert st_["max_y"] == STOCH_MAX_Y == 320
    json.dumps(payload)


def test_macd_and_rsi_pane_payloads_follow_plotly_tokens():
    from config.settings import RSI_PARAMS

    payload = LW.frame_to_lw_payload(_pipeline_frame())
    macd = payload["macd"]
    assert macd and len(macd["hist"]) == len(macd["macd"]) == len(macd["signal"]) > 0
    colors = {h["color"] for h in macd["hist"]}
    assert colors <= set(LW.MACD_HIST_COLORS.values()) and len(colors) >= 2
    # plotly add_macd_panel 규칙 그대로: 직전 대비 증가=진한 적(부호 무관), 감소&0 이상=연한 적, 감소&0 미만=진한 청
    assert LW.macd_hist_color(2.0, 1.0) == "#FF4D4D" and LW.macd_hist_color(1.0, 2.0) == "#F7B6B6"
    assert LW.macd_hist_color(-2.0, -1.0) == "#2F6BFF" and LW.macd_hist_color(-1.0, -2.0) == "#FF4D4D"
    assert LW.macd_hist_color(1.0, float("nan")) == "#FF4D4D"

    rsi = payload["rsi"]
    assert rsi and all(0 <= p["value"] <= 100 for p in rsi["line"])
    assert [g["value"] for g in rsi["guides"]] == [RSI_PARAMS["overbought"], RSI_PARAMS["oversold"], RSI_PARAMS["midline"]]
    assert [g["value"] for g in rsi["guides"]] == [70, 30, 50]


def test_pane_layout_respects_toggles_and_missing_columns():
    payload = LW.frame_to_lw_payload(_pipeline_frame())
    full = LW.pane_layout(payload)
    assert [p["kind"] for p in full] == ["price", "stoch", "macd", "rsi"]
    assert [p["stretch"] for p in full] == [39, 26, 19, 16]           # 지표 중심 0.39/0.26/0.19/0.16 근사
    assert LW.PANE_STRETCH["stoch"] + LW.PANE_STRETCH["macd"] + LW.PANE_STRETCH["rsi"] == 61
    off = LW.pane_layout(payload, show_stochastic=False, show_rsi=False)
    assert [p["kind"] for p in off] == ["price", "macd"]
    # 컬럼 없음(축소 폴백): MACD 컬럼이 없는 프레임 → macd pane 없음, 토글이 켜져 있어도
    df = _pipeline_frame().drop(columns=[c for c in _pipeline_frame().columns if c.startswith("macd")])
    p2 = LW.frame_to_lw_payload(df)
    assert p2["macd"] is None
    assert [p["kind"] for p in LW.pane_layout(p2)] == ["price", "stoch", "rsi"]
    # OHLC 만 있는 프레임 → 가격 pane 하나
    assert [p["kind"] for p in LW.pane_layout(LW.frame_to_lw_payload(_frame()))] == ["price"]


def test_html_declares_panes_and_resize_option():
    df = _pipeline_frame()
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=1000, vendor_js="")
    assert '"enableResize": true' in html                              # pane 경계 드래그
    assert 'var PANES = [{"kind": "price", "stretch": 39}, {"kind": "stoch", "stretch": 26}' in html
    assert "setStretchFactor" in html and "chart.panes()" in html
    assert '"axisDoubleClickReset": {"time": true, "price": true}' in html
    assert '"axisPressedMouseMove": true' in html
    html2 = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=1000, vendor_js="",
                             show_stochastic=False, show_macd=False, show_rsi=False)
    assert 'var PANES = [{"kind": "price", "stretch": 39}];' in html2


# ============================================================ 2단계: 알람 마커
def test_markers_follow_indicator_columns_and_macd_events():
    from analysis.alarm_signals import macd_event_positions
    from config.settings import STOCH_LAYERS

    df = _pipeline_frame()
    payload = LW.frame_to_lw_payload(df)
    mk = payload["markers"]
    # 스토캐: 층별 DB/DT/TB/TT non-null 봉 수와 일치, 시간 오름차순
    for layer in STOCH_LAYERS:
        label = layer["label"]
        expected = sum(int(df[f"stoch_{k}_{label}"].notna().sum()) for k in ("db", "dt", "tb", "tt")
                       if f"stoch_{k}_{label}" in df.columns)
        got = mk["stoch"].get(label, [])
        assert len(got) == expected
        times = [m["time"] for m in got]
        assert times == sorted(times)
    assert sum(len(v) for v in mk["stoch"].values()) > 0
    # RSI
    assert len(mk["rsi"]) == int(df["rsi_db"].notna().sum()) + int(df["rsi_dt"].notna().sum()) > 0
    # MACD: 확정 봉 = macd_event_positions (알람과 동일)
    pos = macd_event_positions(df)
    assert len(mk["macd"]) == sum(len(v) for v in pos.values()) > 0
    macd_times = {m["time"] for m in mk["macd"]}
    expected_times = {int(pd.Timestamp(ts).timestamp()) for v in pos.values() for ts in v}
    assert macd_times == expected_times
    # 스타일: 텍스트 라벨 유지, 방향 색·shape·position 매핑
    styles = {(m["text"], m["shape"], m["color"], m["position"]) for v in mk["stoch"].values() for m in v}
    assert styles <= set(LW.STOCH_MARKER_STYLE.values())
    macd_styles = {(m["text"], m["shape"], m["color"], m["position"]) for m in mk["macd"]}
    assert macd_styles <= {("GC", "circle", "#0B8F45", "aboveBar"), ("DC", "circle", "#C62828", "belowBar"),
                           ("0↑", "square", "#1565C0", "aboveBar"), ("0↓", "square", "#AD1457", "belowBar")}
    for m in mk["macd"] + mk["rsi"]:
        assert set(m) == {"time", "position", "shape", "color", "text"}
    json.dumps(payload)


def test_markers_are_wired_to_pane_series_in_html():
    df = _pipeline_frame()
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=1000, vendor_js="")
    assert "LWC.createSeriesMarkers(stochK[label], M.stoch[label])" in html
    assert "LWC.createSeriesMarkers(rsiLine, M.rsi)" in html and "LWC.createSeriesMarkers(macdLine, M.macd)" in html
    assert '"text": "DB"' in html and '"text": "GC"' in html or '"text": "DC"' in html
    # 마커는 억제 없이 전량 — 별도 억제 상수·함수가 없다
    src = open(LW.__file__, encoding="utf-8").read()
    assert "suppress" not in src.lower() and "억제 로직 없음" in src


def test_markers_empty_without_indicator_columns():
    mk = LW.frame_to_lw_payload(_frame())["markers"]
    assert mk == {"stoch": {}, "rsi": [], "macd": []}


# ============================================================ 2단계: 세로 줌
def test_vertical_zoom_is_scoped_to_price_axis_and_resettable():
    df = _pipeline_frame()
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[g]", chart_height=1000, vendor_js="")
    # 기본 제공: 가격축 누른-드래그 스케일 · 축 더블클릭 원복
    assert '"axisPressedMouseMove": true' in html
    assert '"axisDoubleClickReset": {"time": true, "price": true}' in html
    # 커스텀: 가격축 영역 위 휠 → autoscaleInfoProvider 오버라이드, 본체 휠은 통과, 더블클릭으로 복귀
    assert "if (!overPriceAxis(e)) return;" in html
    assert "autoscaleInfoProvider: provider" in html and "autoscaleInfoProvider: undefined" in html
    assert "wrap.addEventListener('wheel'" in html and "{ capture: true, passive: false }" in html
    assert "if (overPriceAxis(e)) resetVertical();" in html
    assert f"var VZOOM_IN = {LW.VZOOM_IN_FACTOR}; var VZOOM_OUT = {LW.VZOOM_OUT_FACTOR};" in html
    assert 0 < LW.VZOOM_IN_FACTOR < 1 < LW.VZOOM_OUT_FACTOR
    # 조작법 캡션에 세로 줌 안내
    assert "가격축 위 휠" in LW.LW_CONTROLS_CAPTION and "더블클릭" in LW.LW_CONTROLS_CAPTION
