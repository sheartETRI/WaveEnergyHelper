"""슬림 앱(signal-alarm) 스모크 — 파이프라인→차트→알람 패널이 실제로 맞물리는지.

네트워크·streamlit 런타임 없이 돌아간다. 확인하는 계약:
  1. main.load_frame 이 쓰는 지표 조합으로 차트 figure가 컬럼 누락 없이 만들어진다.
  2. 같은 프레임에서 알람 패널의 순수 build_* 가 텍스트를 낸다.
  3. main.py가 import 가능하고 사이드바 레이어 선택 맵이 STOCH_LAYERS와 일치한다.

Plotly figure 를 만드는 테스트는 레거시 엔진(charts/plotly_builder) 검사다 — main 은 더 이상 plotly 를
import 하지 않으므로 plotly 미설치 환경에서는 skip 된다(requirements-legacy.txt).
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd
import pytest

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

# 레거시 Plotly 엔진 전용 테스트 — 데모 의존(requirements.txt)에 plotly 가 없으므로 미설치면 skip.
requires_plotly = pytest.mark.skipif(
    importlib.util.find_spec("plotly") is None, reason="plotly 미설치 — 레거시 엔진(plotly_builder) 테스트",
)


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


@requires_plotly
def test_chart_figure_builds_with_slim_flags():
    """main.py가 넘기는 플래그 조합으로 figure가 만들어진다(MACD 패널 켬/끔 모두)."""
    df = _pipeline_frame()
    for view_mode in ("Stacked", "Separated"):
        for show_macd in (True, False):
            fig = _figure(df, stochastic_view_mode=view_mode, show_macd=show_macd)
            assert fig is not None
            assert len(fig.data) > 0, f"{view_mode}: 트레이스가 비었다"


@requires_plotly
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


@requires_plotly
def test_stoch_view_mode_values_are_honored():
    """plotly_builder 의 스토캐 표시 분기값("Stacked"/"Separated")이 행 구성을 실제로 바꾼다.

    철자가 틀리면(예: "Separate") 조용히 Stacked로 떨어지므로, 행 구성이 달라지는지로 확인.
    (사이드바 '스토캐 표시' 라디오는 Plotly 전용이라 main 에서 제거됐다 — main 과의 결합 검사 없음.)
    """
    from charts.plotly_builder import _get_synced_chart_rows

    stacked = _get_synced_chart_rows(True, "Stacked", False, True)
    separated = _get_synced_chart_rows(True, "Separated", False, True)
    kinds_stacked = [r["kind"] for r in stacked]
    kinds_separated = [r["kind"] for r in separated]
    assert "stoch_stacked" in kinds_stacked
    assert "stoch_layer" in kinds_separated and "stoch_stacked" not in kinds_separated
    assert len(separated) > len(stacked)


@requires_plotly
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


@requires_plotly
def test_chart_vertical_controls_settings():
    """세로 조작성 설정 계층 — 모든 y축 fixedrange=False, rangeslider 꺼짐, dragmode pan,
    높이는 선택값 그대로(600/800/1000/1200, 기본 1000), 가격 행 도메인은 기본 모드 비중 이상,
    캡션·config 상수 존재."""
    from charts.plotly_builder import (
        CHART_CONTROLS_CAPTION, CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT, DEFAULT_LAYOUT_MODE,
        PLOTLY_CONFIG, _row_heights, _get_synced_chart_rows,
    )

    df = _pipeline_frame()
    five = _get_synced_chart_rows(True, "Stacked", True, True)
    price_share = _row_heights(five, DEFAULT_LAYOUT_MODE)[0]
    for height in CHART_HEIGHT_OPTIONS:
        fig = _figure(df, chart_height=height)
        layout = fig.layout
        assert layout.height >= height   # 최소 패널 높이 보장을 위해 올려 잡힐 수 있다
        assert layout.dragmode == "pan"
        yaxes = [v for k, v in layout.to_plotly_json().items() if k.startswith("yaxis")]
        assert yaxes and all(ax.get("fixedrange") is False for ax in yaxes), "모든 y축 fixedrange=False 명시"
        xaxes = [v for k, v in layout.to_plotly_json().items() if k.startswith("xaxis")]
        assert all(not ax.get("rangeslider", {}).get("visible", False) for ax in xaxes), "rangeslider 꺼짐"
        # 가격(첫 행) y축 도메인 폭이 5패널 기준 (기본 모드 가격 비중)×(1-간격) 이상.
        y0, y1 = layout.yaxis.domain
        assert (y1 - y0) >= price_share * (1 - 0.04 * 4) - 1e-9, f"가격 행 도메인 {y1 - y0:.2f}"

    assert CHART_HEIGHT_OPTIONS == (600, 800, 1000, 1200)
    assert DEFAULT_CHART_HEIGHT in CHART_HEIGHT_OPTIONS and DEFAULT_CHART_HEIGHT == 1000
    assert PLOTLY_CONFIG["scrollZoom"] is True and PLOTLY_CONFIG["doubleClick"] == "reset"
    assert all(word in CHART_CONTROLS_CAPTION for word in ("휠", "축", "더블클릭"))
    rows = _get_synced_chart_rows(True, "Separated", True, True)
    heights = _row_heights(rows)
    assert abs(sum(heights) - 1.0) < 1e-9
    assert _row_heights([{"kind": "price"}]) == [1.0]


@requires_plotly
def test_chart_panel_shares_and_min_height():
    """패널 비중(기본형): 5개 기준 0.50/0.06/0.18/0.14/0.12, 꺼진 패널은 가격 흡수, 간격 0.04,
    하위 패널(가격·거래량 제외) 실제 px ≥ 80 (미달이면 전체 높이 상향) — 두 모드 공통."""
    from charts.plotly_builder import (
        CHART_HEIGHT_OPTIONS, LAYOUT_MODE_BASIC, LAYOUT_MODES, MIN_SUBPANEL_PX, VERTICAL_SPACING,
        _effective_chart_height, _get_synced_chart_rows, _row_heights, _row_pixels,
    )

    five = _get_synced_chart_rows(True, "Stacked", True, True)
    assert [r["kind"] for r in five] == ["price", "volume", "stoch_stacked", "macd", "rsi"]
    assert [round(h, 4) for h in _row_heights(five, LAYOUT_MODE_BASIC)] == [0.5, 0.06, 0.18, 0.14, 0.12]
    three = _get_synced_chart_rows(True, "Stacked", False, False)   # MACD·RSI 꺼짐 → 가격 흡수
    assert [round(h, 4) for h in _row_heights(three, LAYOUT_MODE_BASIC)] == [0.76, 0.06, 0.18]
    assert VERTICAL_SPACING >= 0.04

    df = _pipeline_frame()
    for mode in LAYOUT_MODES:
        heights = _row_heights(five, mode)
        for height in CHART_HEIGHT_OPTIONS:
            fig = _figure(df, chart_height=height, layout_mode=mode)
            eff = _effective_chart_height(five, heights, height)
            assert fig.layout.height == eff >= height
            px = _row_pixels(heights, eff)
            for row, p in zip(five, px):
                if row["kind"] not in ("price", "volume"):
                    assert p >= MIN_SUBPANEL_PX - 1e-6, f"{mode} {row['kind']} {p:.1f}px @ {height}"
        # 이미 충분하면 올리지 않는다.
        assert _effective_chart_height(five, heights, 1000) == 1000


@requires_plotly
def test_chart_titles_removed_and_y_fitted():
    """서브플롯 제목 annotation 없음, 가격·거래량·MACD y 는 표시 창(최근 150봉) 데이터에 밀착,
    uirevision 은 심볼|TF, 거래량 눈금 3개 이하·SI 포맷·0 시작, 스토캐 참조선 20/80 만,
    하위 패널 마커는 텍스트 없이 마커만."""
    from charts.plotly_builder import (
        LAYOUT_MODE_BASIC, RECENT_WINDOW, STOCH_GUIDES, _create_synced_chart_figure,
    )

    df = _pipeline_frame()
    fig = _figure(df, layout_mode=LAYOUT_MODE_BASIC)
    layout = fig.layout
    assert not layout.annotations, "서브플롯 제목이 남아 있다"
    assert layout.uirevision == "BTCUSDT|1h"
    fig2 = _create_synced_chart_figure(df, "ETHUSDT", "4h", show_macd=True)
    assert fig2.layout.uirevision == "ETHUSDT|4h"

    win = df.iloc[-RECENT_WINDOW:]
    lo, hi = layout.yaxis.range
    ma_cols = [c for c in win.columns if c.startswith("MA") and c[2:].isdigit()]
    data_lo = min(win["low"].min(), win[ma_cols].min().min())
    data_hi = max(win["high"].max(), win[ma_cols].max().max())
    span = data_hi - data_lo
    assert data_lo - span * 0.05 <= lo <= data_lo and data_hi <= hi <= data_hi + span * 0.05, "가격 y 가 창에 밀착하지 않음"
    assert layout.yaxis.autorange is False
    # 전체 데이터 범위보다 좁아야 진짜 밀착이다(랜덤워크 700봉 전체 폭 > 최근 150봉 폭).
    assert (hi - lo) < (df["high"].max() - df["low"].min())

    vol = layout.yaxis2
    assert vol.nticks == 3 and vol.tickformat == "~s" and vol.rangemode == "tozero"
    assert vol.range[0] == 0 and vol.range[1] >= win["volume"].max()

    macd_ax = layout.yaxis4
    m_lo = win[["macd", "macd_signal", "macd_hist"]].min().min()
    m_hi = win[["macd", "macd_signal", "macd_hist"]].max().max()
    assert macd_ax.range[0] <= m_lo and macd_ax.range[1] >= m_hi

    assert STOCH_GUIDES == (20, 80)
    # 스토캐 stacked 패널(yaxis3)의 수평 참조선: 3층 × 2 + 층 구분선 2 = 8.
    # (hoverinfo skip + 선 폭 > 0. 채움 폴리곤은 hoverinfo skip 이지만 선 폭 0.)
    guides = [t for t in fig.data if t.yaxis == "y3" and t.mode == "lines" and t.hoverinfo == "skip"
              and (t.line.width or 0) > 0]
    assert len(guides) == 3 * len(STOCH_GUIDES) + 2
    assert layout.yaxis3.showgrid is False

    # 기본형: 하위 패널 마커(스토캐·RSI·MACD)는 mode "markers" (텍스트 없음), 호버 템플릿 있음.
    sub_markers = [t for t in fig.data
                   if getattr(t, "yaxis", "y") != "y" and "markers" in (getattr(t, "mode", None) or "")]
    assert sub_markers
    assert all(t.mode == "markers" and t.hovertemplate for t in sub_markers)


def test_main_wires_chart_height_and_controls():
    """main.py: wide 레이아웃, 차트 높이 셀렉트(charts.theme 의 CHART_HEIGHT_OPTIONS), render_lw_chart 에
    chart_height 전달. Plotly 전용 컨트롤(표시 모드·스토캐 표시·차트 엔진 라디오)은 없다."""
    source = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(source, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert 'layout="wide"' in body
    assert "from charts.theme import CHART_HEIGHT_OPTIONS, DEFAULT_CHART_HEIGHT" in body
    assert "CHART_HEIGHT_OPTIONS" in body and "chart_height=cfg[\"chart_height\"]" in body
    assert '"표시 모드"' not in body and "LAYOUT_MODE" not in body
    assert '"스토캐 표시"' not in body and '"Separated"' not in body
    assert '"차트 엔진"' not in body and "CHART_ENGINES" not in body
    # 플롯 전용 캡션·config 는 레거시 빌더 안에 그대로 남는다(파일 검사만 — plotly import 불필요).
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


# ------------------------------------------------------------ 표시 모드 2종 (비중 재배분 + 높이 옵션 확장)
@requires_plotly
def test_layout_modes_and_shares():
    """지표 중심(기본) 0.34/0.05/0.26/0.19/0.16 · 기본형 0.50/0.06/0.18/0.14/0.12,
    Separated 는 스토캐 비중을 3층이 나눔, 꺼진 패널은 두 모드 모두 가격이 흡수."""
    from charts.plotly_builder import (
        DEFAULT_LAYOUT_MODE, LAYOUT_MODE_BASIC, LAYOUT_MODE_INDICATOR, LAYOUT_MODE_LABELS, LAYOUT_MODES,
        PANEL_SHARES, PANEL_SHARES_BY_MODE, _get_synced_chart_rows, _row_heights,
    )

    assert LAYOUT_MODES == (LAYOUT_MODE_INDICATOR, LAYOUT_MODE_BASIC)
    assert DEFAULT_LAYOUT_MODE == LAYOUT_MODE_INDICATOR
    assert LAYOUT_MODE_LABELS == {LAYOUT_MODE_INDICATOR: "지표 중심", LAYOUT_MODE_BASIC: "기본형"}
    assert PANEL_SHARES is PANEL_SHARES_BY_MODE[LAYOUT_MODE_BASIC]

    five = _get_synced_chart_rows(True, "Stacked", True, True)
    assert [round(h, 4) for h in _row_heights(five, LAYOUT_MODE_INDICATOR)] == [0.34, 0.05, 0.26, 0.19, 0.16]
    assert [round(h, 4) for h in _row_heights(five)] == [0.34, 0.05, 0.26, 0.19, 0.16]   # 기본값 = 지표 중심
    # 하위 3패널 합계 0.44 → 0.61
    assert round(sum(_row_heights(five, LAYOUT_MODE_BASIC)[2:]), 4) == 0.44
    assert round(sum(_row_heights(five, LAYOUT_MODE_INDICATOR)[2:]), 4) == 0.61

    for mode in LAYOUT_MODES:
        table = PANEL_SHARES_BY_MODE[mode]
        assert abs(table["stoch_layer"] * 3 - table["stoch_stacked"]) < 1e-9
        sep = _get_synced_chart_rows(True, "Separated", True, True)
        assert abs(sum(_row_heights(sep, mode)) - 1.0) < 1e-9
        three = _get_synced_chart_rows(True, "Stacked", False, False)
        heights = _row_heights(three, mode)
        assert abs(heights[0] - (1.0 - table["volume"] - table["stoch_stacked"])) < 1e-9


@requires_plotly
def test_indicator_mode_subpanel_pixels():
    """지표 중심 + 1000: 하위 패널 실측 px — 스토캐 ≥ 200 · MACD ≥ 145 · RSI ≥ 120
    (공식: (전체−마진 60) × 비중 × (1 − 0.04×4) → 약 205 / 150 / 126). 모든 높이에서 지표 중심 > 기본형."""
    from charts.plotly_builder import (
        CHART_HEIGHT_OPTIONS, LAYOUT_MODE_BASIC, LAYOUT_MODE_INDICATOR, _effective_chart_height,
        _get_synced_chart_rows, _row_heights, _row_pixels,
    )

    five = _get_synced_chart_rows(True, "Stacked", True, True)
    kinds = [r["kind"] for r in five]

    def px(mode, height):
        h = _row_heights(five, mode)
        return dict(zip(kinds, _row_pixels(h, _effective_chart_height(five, h, height))))

    ind = px(LAYOUT_MODE_INDICATOR, 1000)
    assert ind["stoch_stacked"] >= 200 and ind["macd"] >= 145 and ind["rsi"] >= 120, ind
    assert _effective_chart_height(five, _row_heights(five, LAYOUT_MODE_INDICATOR), 1000) == 1000

    for height in CHART_HEIGHT_OPTIONS:
        a, b = px(LAYOUT_MODE_INDICATOR, height), px(LAYOUT_MODE_BASIC, height)
        for kind in ("stoch_stacked", "macd", "rsi"):
            assert a[kind] > b[kind] or height <= 800, f"{kind} @ {height}: {a[kind]:.1f} vs {b[kind]:.1f}"
    # 600 선택은 두 모드 모두 80px 규칙으로 올라간다(지표 중심 656, 기본형 854).
    assert _effective_chart_height(five, _row_heights(five, LAYOUT_MODE_INDICATOR), 600) < \
        _effective_chart_height(five, _row_heights(five, LAYOUT_MODE_BASIC), 600)


def _subpanel_marker_traces(fig):
    return [t for t in fig.data
            if getattr(t, "yaxis", "y") != "y" and "markers" in (getattr(t, "mode", None) or "")]


@requires_plotly
def test_subpanel_marker_text_follows_layout_mode():
    """하위 패널 마커 텍스트: 지표 중심 = markers+text (스토캐·RSI·MACD 모두), 기본형 = markers 만.
    가격 패널은 모드와 무관."""
    from charts.plotly_builder import LAYOUT_MODE_BASIC, LAYOUT_MODE_INDICATOR, SUBPANEL_MARKER_TEXT_BY_MODE

    assert SUBPANEL_MARKER_TEXT_BY_MODE == {LAYOUT_MODE_BASIC: False, LAYOUT_MODE_INDICATOR: True}
    df = _pipeline_frame()

    fig_i = _figure(df, layout_mode=LAYOUT_MODE_INDICATOR)
    mk_i = _subpanel_marker_traces(fig_i)
    assert mk_i and all(t.mode == "markers+text" and t.hovertemplate for t in mk_i)
    # MACD 이벤트 마커(GC/DC/0↑/0↓)도 텍스트 포함, y축은 MACD 행(y4).
    macd_i = [t for t in mk_i if t.name in ("GC", "DC", "0↑", "0↓")]
    assert macd_i and all(t.yaxis == "y4" and t.mode == "markers+text" for t in macd_i)
    # 스토캐 3층(y3)·RSI(y5) 마커도 텍스트.
    assert any(t.yaxis == "y3" for t in mk_i) and any(t.yaxis == "y5" for t in mk_i)

    fig_b = _figure(df, layout_mode=LAYOUT_MODE_BASIC)
    mk_b = _subpanel_marker_traces(fig_b)
    assert mk_b and all(t.mode == "markers" for t in mk_b)
    # 같은 데이터이므로 마커 트레이스 수는 모드와 무관(텍스트만 켜고 끔).
    assert len(mk_i) == len(mk_b)

    # Separated 도 동일 규칙.
    fig_s = _figure(df, layout_mode=LAYOUT_MODE_INDICATOR, stochastic_view_mode="Separated")
    assert all(t.mode == "markers+text" for t in _subpanel_marker_traces(fig_s))


@requires_plotly
def test_stoch_stack_guides_keep_clearance_in_indicator_mode():
    """스토캐 3층 스택(y 0~320): 층 분리선~참조선 25단위, 참조선 20~80 60단위, 층 간격 10단위.
    지표 중심 + 1000 에서 분리선~참조선 ≥ 12px 이므로 참조선끼리 겹치지 않는다(투명도 조정 불필요)."""
    from config.settings import STOCH_BAND, STOCH_GAP, STOCH_LAYERS, STOCH_MAX_Y
    from charts.plotly_builder import (
        LAYOUT_MODE_INDICATOR, STOCH_GUIDES, _get_synced_chart_rows, _row_heights, _row_pixels,
    )

    five = _get_synced_chart_rows(True, "Stacked", True, True)
    px = _row_pixels(_row_heights(five, LAYOUT_MODE_INDICATOR), 1000)[2]
    per_unit = px / STOCH_MAX_Y
    # 모든 수평선(참조선 6 + 분리선 2)의 y 값 — 인접 간격의 최소.
    ys = sorted([g + l["offset"] for l in STOCH_LAYERS for g in STOCH_GUIDES]
                + [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5])
    min_gap_units = min(b - a for a, b in zip(ys, ys[1:]))
    assert min_gap_units == 25
    assert min_gap_units * per_unit >= 12, f"최소 간격 {min_gap_units * per_unit:.1f}px"

    fig = _figure(_pipeline_frame(), layout_mode=LAYOUT_MODE_INDICATOR)
    guides = [t for t in fig.data if t.yaxis == "y3" and t.mode == "lines" and t.hoverinfo == "skip"
              and (t.line.width or 0) > 0]
    assert len(guides) == 3 * len(STOCH_GUIDES) + 2   # 구조 그대로(참조선 수·분리선 수 불변)
