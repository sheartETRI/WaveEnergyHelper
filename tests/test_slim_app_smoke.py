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
    build_bar_caption,
    build_current_bar_lines,
    build_header,
    build_status_lines,
    format_signal_line,
)
from indicators.moving_averages import add_moving_averages
from indicators.oscillators import add_rsi
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
    df = add_rsi(df)
    return df


def _figure(df, **kwargs):
    from charts.plotly_builder import _create_synced_chart_figure

    base = dict(
        show_stochastic=True,
        stochastic_view_mode="Stacked",
        show_stoch_fill=True,
        show_macd=False,  # 슬림 구성은 MACD를 계산하지 않는다
        show_rsi=True,
        show_rsi_fill=True,
    )
    base.update(kwargs)
    return _create_synced_chart_figure(df, "BTCUSDT", "1h", **base)


def test_chart_figure_builds_with_slim_flags():
    """main.py가 넘기는 플래그 조합으로 figure가 만들어진다(MACD 없이도)."""
    df = _pipeline_frame()
    for view_mode in ("Stacked", "Separated"):
        fig = _figure(df, stochastic_view_mode=view_mode)
        assert fig is not None
        assert len(fig.data) > 0, f"{view_mode}: 트레이스가 비었다"


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

    signals = recent_signals(df, bars=200)
    assert signals, "200봉 창에서 신호가 전무하면 환산이 끊긴 것"
    for s in signals:
        line = format_signal_line(s)
        assert s.label in line and s.layer_name in line

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


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("ALL SLIM APP SMOKE TESTS PASSED")
