"""슬림 앱(signal-alarm) 스모크 — 파이프라인→차트→알람 패널이 실제로 맞물리는지.

네트워크·streamlit 런타임 없이 돌아간다. 확인하는 계약:
  1. main.load_frame 이 쓰는 지표 조합으로 차트 figure가 컬럼 누락 없이 만들어진다.
  2. 같은 프레임에서 알람 패널의 순수 build_* 가 텍스트를 낸다.
  3. main.py가 import 가능하고 사이드바 레이어 선택 맵이 STOCH_LAYERS와 일치한다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.alarm_signals import recent_signals, scan_alarm_signals
from config.settings import STOCH_LAYERS
from display.alarm_panel import (
    MACD_DELAY_NOTE,
    build_bar_caption,
    build_current_bar_lines,
    build_header,
    build_status_lines,
    format_signal_line,
)
from indicators.moving_averages import add_moving_averages
from indicators.oscillators import add_macd, add_rsi
from indicators.stochastic import add_stochastic_slow_layers

# MA 240까지 쓰므로 워밍업을 넉넉히 둔다(차트 RECENT_WINDOW=150).
BARS = 700


def _pipeline_frame():
    """main.load_frame 과 동일한 지표 순서로 만든 합성 프레임."""
    rng = np.random.default_rng(20260911)
    idx = pd.date_range("2026-01-01", periods=BARS, freq="h")
    close = 100 + np.cumsum(rng.normal(0, 1.1, BARS))
    df = pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.2, BARS),
            "high": close + np.abs(rng.normal(0, 0.7, BARS)),
            "low": close - np.abs(rng.normal(0, 0.7, BARS)),
            "close": close,
            "volume": rng.uniform(1, 10, BARS),
        },
        index=idx,
    )
    df = add_moving_averages(df)
    df = add_stochastic_slow_layers(df)
    df = add_macd(df)
    df = add_rsi(df)
    return df


def _figure(df, **kwargs):
    from charts.plotly_builder import _create_synced_chart_figure

    base = dict(
        show_stochastic=True,
        stochastic_view_mode="Stacked",
        show_stoch_fill=True,
        show_macd=True,
        show_rsi=True,
        show_rsi_fill=True,
    )
    base.update(kwargs)
    return _create_synced_chart_figure(df, "BTCUSDT", "1h", **base)


def test_chart_figure_builds_with_slim_flags():
    """main.py가 넘기는 플래그 조합으로 figure가 만들어진다(MACD 패널 켬/끔 모두)."""
    df = _pipeline_frame()
    for view_mode in ("Stacked", "Separated"):
        for show_macd in (True, False):
            fig = _figure(df, stochastic_view_mode=view_mode, show_macd=show_macd)
            assert fig is not None
            assert len(fig.data) > 0, f"{view_mode}: 트레이스가 비었다"


def test_macd_panel_carries_alarm_event_markers():
    """MACD 패널에 알람 이벤트 마커(GC/DC/0↑/0↓)가 알람 목록과 같은 봉에 찍힌다."""
    from analysis.alarm_signals import MACD_KINDS, macd_event_positions

    df = _pipeline_frame()
    fig = _figure(df, show_macd=True)
    traces = {t.name: t for t in fig.data if t.name in ("GC", "DC", "0↑", "0↓")}
    assert set(traces) == {"GC", "DC", "0↑", "0↓"}, "랜덤워크 700봉이면 4종 모두 있어야 한다"

    positions = macd_event_positions(df)
    name_of = dict(zip(MACD_KINDS, ("GC", "DC", "0↑", "0↓")))
    for kind, name in name_of.items():
        assert list(pd.to_datetime(traces[name].x)) == list(positions[kind])
        # y 는 확정 봉의 macd 값 위에 찍힌다.
        assert np.allclose(np.asarray(traces[name].y, dtype=float), df.loc[positions[kind], "macd"].to_numpy())
    # 마커는 확정 봉(교차 봉 +1)에 찍힌다 — 교차 봉에 찍으면 사후 이동 표시가 된다.
    from analysis.alarm_signals import macd_events
    for kind, events in macd_events(df).items():
        for e in events:
            assert df.index.get_loc(e.timestamp) == df.index.get_loc(e.cross_ts) + 1

    # MACD 패널을 끄면 마커도 없다.
    fig_off = _figure(df, show_macd=False)
    assert not any(t.name in ("GC", "DC", "0↑", "0↓") for t in fig_off.data)


def test_stoch_view_mode_values_are_honored():
    """사이드바가 넘기는 문자열이 plotly_builder의 분기값과 실제로 일치한다.

    철자가 틀리면(예: "Separate") 조용히 Stacked로 떨어지므로, 행 구성이 달라지는지로 확인.
    """
    import main
    from charts.plotly_builder import _get_synced_chart_rows

    stacked = _get_synced_chart_rows(True, "Stacked", False, True)
    separated = _get_synced_chart_rows(True, "Separated", False, True)
    kinds_stacked = [r["kind"] for r in stacked]
    kinds_separated = [r["kind"] for r in separated]
    assert "stoch_stacked" in kinds_stacked
    assert "stoch_layer" in kinds_separated and "stoch_stacked" not in kinds_separated
    assert len(separated) > len(stacked)

    # main.py 사이드바의 선택지가 그 두 값과 정확히 같아야 한다.
    source = (os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(source, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert '"Stacked", "Separated"' in body, "사이드바 선택지가 분기값과 어긋났다"
    assert main is not None


def test_chart_figure_builds_with_panels_off():
    """스토캐·RSI 패널을 모두 끈 경우에도 캔들만으로 figure가 만들어진다."""
    df = _pipeline_frame()
    fig = _figure(
        df,
        show_stochastic=False, show_stoch_fill=False,
        show_rsi=False, show_rsi_fill=False,
    )
    assert fig is not None and len(fig.data) > 0


def test_alarm_panel_pure_builders():
    """패널의 순수 부분이 프레임에서 텍스트를 만든다(streamlit 호출 없음)."""
    df = _pipeline_frame()

    lines = build_status_lines(df, "BTCUSDT", "1h")
    assert lines[0] == build_header("BTCUSDT", "1h")
    assert "BTCUSDT 1h" in lines[0]
    assert "마지막 봉" in lines[1]
    assert "RSI 구역" in lines[2]
    # MACD 가 계산된 프레임이면 1봉 지연 안내가 붙고, 없으면 안 붙는다.
    assert lines[3] == MACD_DELAY_NOTE and "1봉" in MACD_DELAY_NOTE
    assert MACD_DELAY_NOTE not in build_status_lines(df.drop(columns=["macd"]), "BTCUSDT", "1h")

    signals = recent_signals(df, bars=200)
    assert signals, "200봉 창에서 신호가 전무하면 환산이 끊긴 것"
    for s in signals:
        line = format_signal_line(s)
        assert s.label in line and s.layer_name in line
        # 권고형 문구 금지 — 라벨 체계(상태 기술)까지만. ("과매수/과매도"는 구역 이름이라 허용)
        assert not any(bad in line for bad in ("매수 신호", "매도 신호", "추천", "진입하", "청산하"))
    macd_lines = [format_signal_line(s) for s in signals if s.layer_name == "MACD"]
    assert macd_lines, "MACD 신호가 이력 창에 하나도 없으면 연결이 끊긴 것"
    assert all(("hist " in line) or ("MACD " in line) for line in macd_lines)
    assert all("교차 " in line for line in macd_lines), "교차 봉 시각이 비고로 보여야 한다"

    # 마지막 봉 줄은 해당 봉 신호만 뽑는다.
    current = build_current_bar_lines(signals, df.index[-1])
    expected = sum(1 for s in signals if s.timestamp == df.index[-1])
    assert len(current) == expected


def test_empty_frame_is_handled():
    """데이터 없음 경로가 예외 없이 끝난다."""
    empty = pd.DataFrame()
    assert build_status_lines(empty, "BTCUSDT", "1h")[1] == "데이터 없음"
    assert build_bar_caption(empty) == "데이터 없음"
    assert build_bar_caption(None) == "데이터 없음"
    assert build_current_bar_lines([], None) == []
    assert scan_alarm_signals(empty) == []


def test_main_module_contract():
    """main.py import 가능 + 레이어 선택 맵이 STOCH_LAYERS와 일치."""
    import main

    assert callable(main.load_frame) and callable(main.render_sidebar) and callable(main.main)
    labels = [layer["label"] for layer in STOCH_LAYERS]
    assert sorted(main._LAYER_CHOICES.values()) == sorted(labels)
    # 표시명은 대/중/소 접두가 붙어야 한다(사이드바 가독성).
    assert all(name[0] in "대중소" for name in main._LAYER_CHOICES)
    assert main.DEFAULT_INTERVAL in __import__("config.settings", fromlist=["x"]).TIMEFRAMES


def test_macd_panel_default_off_only_for_15m():
    """'MACD 패널' 토글 기본값 — 15m 만 꺼짐, 그 외 TF 는 켬. 사이드바가 그 함수를 실제로 쓴다."""
    import main
    from config.settings import TIMEFRAMES

    assert main.macd_panel_default("15m") is False
    for tf in TIMEFRAMES:
        assert main.macd_panel_default(tf) is (tf != "15m")
    source = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(source, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert "value=macd_panel_default(interval)" in body


def test_chart_vertical_controls_settings():
    """세로 조작성 설정 계층 — 모든 y축 fixedrange=False, rangeslider 꺼짐, dragmode pan,
    높이는 선택값 그대로, 가격 행 비중 ≥ 0.75, 캡션·config 상수 존재."""
    from charts.plotly_builder import (
        CHART_CONTROLS_CAPTION, CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT, PLOTLY_CONFIG,
        PRICE_ROW_SHARE, _row_heights, _get_synced_chart_rows,
    )

    df = _pipeline_frame()
    for height in CHART_HEIGHT_OPTIONS:
        fig = _figure(df, chart_height=height)
        layout = fig.layout
        assert layout.height == height
        assert layout.dragmode == "pan"
        yaxes = [v for k, v in layout.to_plotly_json().items() if k.startswith("yaxis")]
        assert yaxes and all(ax.get("fixedrange") is False for ax in yaxes), "모든 y축 fixedrange=False 명시"
        xaxes = [v for k, v in layout.to_plotly_json().items() if k.startswith("xaxis")]
        assert all(not ax.get("rangeslider", {}).get("visible", False) for ax in xaxes), "rangeslider 꺼짐"
        # 가격(첫 행) y축 도메인 폭이 전체의 0.75×(1-간격) 이상 — 지표 패널이 가격을 누르지 않는다.
        y0, y1 = layout.yaxis.domain
        assert (y1 - y0) >= PRICE_ROW_SHARE * 0.9, f"가격 행 도메인 {y1 - y0:.2f}"

    assert DEFAULT_CHART_HEIGHT in CHART_HEIGHT_OPTIONS and DEFAULT_CHART_HEIGHT == 800
    assert PLOTLY_CONFIG["scrollZoom"] is True and PLOTLY_CONFIG["doubleClick"] == "reset"
    assert all(word in CHART_CONTROLS_CAPTION for word in ("휠", "축", "더블클릭"))
    # row_heights: 가격 = PRICE_ROW_SHARE, 나머지 합 = 1-share, 합계 1.
    rows = _get_synced_chart_rows(True, "Separated", True, True)
    heights = _row_heights(rows)
    assert abs(sum(heights) - 1.0) < 1e-9 and heights[0] == PRICE_ROW_SHARE and PRICE_ROW_SHARE >= 0.75
    assert _row_heights([{"kind": "price", "weight": 0}]) == [1.0]


def test_main_wires_chart_height_and_controls():
    """main.py: wide 레이아웃, 차트 높이 셀렉트(600/800/1000, 기본 800), render_chart 에 chart_height 전달,
    render_chart 는 캡션·config 를 붙인다."""
    source = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(source, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert 'layout="wide"' in body
    assert "CHART_HEIGHT_OPTIONS" in body and "chart_height=cfg[\"chart_height\"]" in body
    with open(os.path.join(source, "charts", "plotly_builder.py"), encoding="utf-8") as fh:
        chart_src = fh.read()
    assert 'st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)' in chart_src
    assert "st.caption(CHART_CONTROLS_CAPTION)" in chart_src


def test_load_frame_without_macd_skips_macd_alarms():
    """토글 꺼짐(with_macd=False) 경로: MACD 컬럼이 없어 알람 4종이 조용히 빠지고 스토캐·RSI 는 그대로."""
    from analysis.alarm_signals import MACD_KINDS

    df = _pipeline_frame()
    with_macd = scan_alarm_signals(df)
    without = scan_alarm_signals(df.drop(columns=[c for c in df.columns if c.startswith("macd")]))
    assert any(s.kind in MACD_KINDS for s in with_macd)
    assert not any(s.kind in MACD_KINDS for s in without)
    assert [s for s in with_macd if s.kind not in MACD_KINDS] == without


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("ALL SLIM APP SMOKE TESTS PASSED")
