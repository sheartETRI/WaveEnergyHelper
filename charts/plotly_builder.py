# charts/plotly_builder.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

from analysis.alarm_signals import (
    KIND_MACD_DEAD,
    KIND_MACD_GOLDEN,
    KIND_MACD_ZERO_DOWN,
    KIND_MACD_ZERO_UP,
    macd_event_positions,
)
from config.settings import (
    MA_COLORS,
    MA_LINE_WIDTHS,
    RSI_PARAMS,
    STOCH_BAND,
    STOCH_GAP,
    STOCH_LAYERS,
    STOCH_MAX_Y,
)


COLOR_BULL = "#ff0000"
COLOR_BEAR = "#0000ff"
TV_BACKGROUND = "#ffffff"
TV_TEXT = "#191c24"
TV_GRID = "rgba(42, 46, 57, 0.12)"
RECENT_WINDOW = 150

# --- 세로 조작성 설정 (설정 계층만, 데이터·지표 무관) ---
# 차트 전체 높이(px): Streamlit 은 뷰포트 높이를 읽지 못하므로 사이드바 선택식.
CHART_HEIGHT_OPTIONS = (600, 800, 1000, 1200)
DEFAULT_CHART_HEIGHT = 1000
# 표시 모드 2종 — 패널 비중 세트만 다르다. 꺼진 패널 흡수·최소 px·간격 규칙은 두 모드 공통.
#   기본형   : 가격 0.50 / 거래량 0.06 / 스토캐 0.18 / MACD 0.14 / RSI 0.12  (하위 3패널 합 0.44)
#   지표 중심: 가격 0.34 / 거래량 0.05 / 스토캐 0.26 / MACD 0.19 / RSI 0.16  (하위 3패널 합 0.61)
# 꺼진 패널의 비중은 가격이 흡수한다. Separated 스토캐는 스토캐 비중을 3층이 나눈다.
LAYOUT_MODE_BASIC = "basic"
LAYOUT_MODE_INDICATOR = "indicator"
LAYOUT_MODES = (LAYOUT_MODE_INDICATOR, LAYOUT_MODE_BASIC)          # 사이드바 순서 (기본 = 지표 중심)
LAYOUT_MODE_LABELS = {LAYOUT_MODE_INDICATOR: "지표 중심", LAYOUT_MODE_BASIC: "기본형"}
DEFAULT_LAYOUT_MODE = LAYOUT_MODE_INDICATOR
PANEL_SHARES_BY_MODE = {
    LAYOUT_MODE_BASIC: {"volume": 0.06, "stoch_stacked": 0.18, "stoch_layer": 0.18 / 3, "macd": 0.14,
                        "rsi": 0.12, "ma_dispersion": 0.10},
    LAYOUT_MODE_INDICATOR: {"volume": 0.05, "stoch_stacked": 0.26, "stoch_layer": 0.26 / 3, "macd": 0.19,
                            "rsi": 0.16, "ma_dispersion": 0.10},
}
PANEL_SHARES = PANEL_SHARES_BY_MODE[LAYOUT_MODE_BASIC]   # 하위 호환 별칭(기본형 세트)
# 하위 패널 마커 텍스트 라벨(스토캐 DB/DT/TB/TT · RSI DB/DT · MACD GC/DC/0↑/0↓):
# 기본형은 판독 불가로 숨김 유지, 지표 중심은 패널이 커져 다시 표시한다.
SUBPANEL_MARKER_TEXT_BY_MODE = {LAYOUT_MODE_BASIC: False, LAYOUT_MODE_INDICATOR: True}
VERTICAL_SPACING = 0.04
# 하위 패널(가격·거래량 제외) 최소 픽셀 높이. 미달이면 차트 전체 높이를 올려 잡는다.
# 거래량은 0.06 비중의 얇은 막대 스트립이라 예외 — 포함하면 어떤 선택값이든 1333px 이상이 된다.
MIN_SUBPANEL_PX = 80
CHART_MARGIN = dict(l=50, r=20, t=30, b=30)
# 화면 캡션용 조작법 요약(휠 / 축 위 휠 / 더블클릭). config 의 scrollZoom·doubleClick 과 짝.
CHART_CONTROLS_CAPTION = (
    "조작: 휠 = 커서 기준 확대·축소  ·  축(눈금) 위에서 휠 = 그 축만 확대·축소  ·  "
    "더블클릭 = 초기 범위로  ·  드래그 = 이동"
)
PLOTLY_CONFIG = {"scrollZoom": True, "doubleClick": "reset", "displaylogo": False}
# 스토캐 참조선: 레이어당 20/80 두 줄만.
STOCH_GUIDES = (20, 80)
STOCH_DISPLAY_LAYERS = [
    {"panel_title": "Large wave", "suffix": "(20,10,10)"},
    {"panel_title": "Mid wave", "suffix": "(10,5,5)"},
    {"panel_title": "Small wave", "suffix": "(5,3,3)"},
]


def add_horizontal_line_trace(fig, x_index, y_value, row_index, color="rgba(120,120,120,0.9)", dash="dash", width=1.2):
    """Adds a horizontal line as a Scatter trace."""
    fig.add_trace(
        go.Scatter(
            x=x_index,
            y=[y_value] * len(x_index),
            mode="lines",
            line=dict(color=color, dash=dash, width=width),
            hoverinfo="skip",
            showlegend=False,
        ),
        row=row_index,
        col=1,
    )


def _interpolate_crossing_x(x0, y0, x1, y1, baseline):
    """Returns the interpolated x-position where the line crosses the baseline."""
    if pd.isna(y0) or pd.isna(y1) or y0 == y1:
        return None

    ratio = (baseline - y0) / (y1 - y0)
    if ratio < 0 or ratio > 1:
        return None

    if isinstance(x0, pd.Timestamp) and isinstance(x1, pd.Timestamp):
        delta = x1 - x0
        return x0 + (delta * ratio)

    try:
        return x0 + ((x1 - x0) * ratio)
    except TypeError:
        return None


def add_masked_fill_segments(fig, x_index, series, mask, baseline, row_index, fillcolor):
    """Adds independent fill polygons for each contiguous True mask segment."""
    x_series = pd.Series(x_index, index=series.index)
    active_mask = (mask.fillna(False) & series.notna()).tolist()
    if not any(active_mask):
        return

    segment_ranges = []
    segment_start = None
    for pos, is_active in enumerate(active_mask):
        if is_active and segment_start is None:
            segment_start = pos
        elif not is_active and segment_start is not None:
            segment_ranges.append((segment_start, pos - 1))
            segment_start = None
    if segment_start is not None:
        segment_ranges.append((segment_start, len(active_mask) - 1))

    for start_pos, end_pos in segment_ranges:
        segment_x = x_series.iloc[start_pos : end_pos + 1].tolist()
        segment_y = series.iloc[start_pos : end_pos + 1].tolist()
        if not segment_y:
            continue

        if start_pos > 0:
            entry_x = _interpolate_crossing_x(
                x_series.iloc[start_pos - 1],
                series.iloc[start_pos - 1],
                x_series.iloc[start_pos],
                series.iloc[start_pos],
                baseline,
            )
            if entry_x is not None:
                segment_x.insert(0, entry_x)
                segment_y.insert(0, baseline)

        if end_pos < len(series) - 1:
            exit_x = _interpolate_crossing_x(
                x_series.iloc[end_pos],
                series.iloc[end_pos],
                x_series.iloc[end_pos + 1],
                series.iloc[end_pos + 1],
                baseline,
            )
            if exit_x is not None:
                segment_x.append(exit_x)
                segment_y.append(baseline)

        fig.add_trace(
            go.Scatter(
                x=segment_x,
                y=[baseline] * len(segment_x),
                mode="lines",
                line=dict(width=0),
                connectgaps=False,
                hoverinfo="skip",
                showlegend=False,
            ),
            row=row_index,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=segment_x,
                y=segment_y,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor=fillcolor,
                connectgaps=False,
                hoverinfo="skip",
                showlegend=False,
            ),
            row=row_index,
            col=1,
        )


def add_stochastic_db_markers(fig, df, row_index, db_col, y_offset=0.0, show_text=True):
    """Adds stochastic DB pattern labels using a precomputed column."""
    if db_col not in df.columns:
        return

    points = df[df[db_col].notna()]
    if points.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=points.index,
            y=points[db_col] + y_offset,
            mode="markers+text" if show_text else "markers",
            name="DB",
            text=["DB"] * len(points),
            textposition="top center",
            hovertemplate="DB %{x}<br>%{y:.1f}<extra></extra>",
            textfont=dict(color="#0B8F45", size=11),
            marker=dict(symbol="circle", size=8, color="#0B8F45", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_dt_markers(fig, df, row_index, dt_col, y_offset=0.0, show_text=True):
    """Adds stochastic DT pattern labels using a precomputed column."""
    if dt_col not in df.columns:
        return

    points = df[df[dt_col].notna()]
    if points.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=points.index,
            y=points[dt_col] + y_offset,
            mode="markers+text" if show_text else "markers",
            name="DT",
            text=["DT"] * len(points),
            textposition="bottom center",
            hovertemplate="DT %{x}<br>%{y:.1f}<extra></extra>",
            textfont=dict(color="#C62828", size=11),
            marker=dict(symbol="circle", size=8, color="#C62828", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_tb_markers(fig, df, row_index, tb_col, y_offset=0.0, show_text=True):
    """Adds stochastic triple-bottom (TB) labels. DB와 구분되는 색(teal)."""
    if tb_col not in df.columns:
        return

    points = df[df[tb_col].notna()]
    if points.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=points.index,
            y=points[tb_col] + y_offset,
            mode="markers+text" if show_text else "markers",
            name="TB",
            text=["TB"] * len(points),
            textposition="top center",
            hovertemplate="TB %{x}<br>%{y:.1f}<extra></extra>",
            textfont=dict(color="#1565C0", size=11),
            marker=dict(symbol="diamond", size=9, color="#1565C0", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_tt_markers(fig, df, row_index, tt_col, y_offset=0.0, show_text=True):
    """Adds stochastic triple-top (TT) labels. DT와 구분되는 색(magenta)."""
    if tt_col not in df.columns:
        return

    points = df[df[tt_col].notna()]
    if points.empty:
        return

    fig.add_trace(
        go.Scatter(
            x=points.index,
            y=points[tt_col] + y_offset,
            mode="markers+text" if show_text else "markers",
            name="TT",
            text=["TT"] * len(points),
            textposition="bottom center",
            hovertemplate="TT %{x}<br>%{y:.1f}<extra></extra>",
            textfont=dict(color="#AD1457", size=11),
            marker=dict(symbol="diamond", size=9, color="#AD1457", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stacked_stochastic_panel(fig, df, row_index, show_fill=True, show_marker_text=False):
    """Adds the existing stacked 3-layer stochastic slow traces. show_marker_text 는 표시 모드가 정한다."""
    for layer in STOCH_LAYERS:
        label = layer["label"]
        offset = layer["offset"]
        k_col = f"stoch_k_shifted_{label}"
        d_col = f"stoch_d_shifted_{label}"
        raw_k_col = f"stoch_k_{label}"
        if k_col not in df.columns or d_col not in df.columns:
            continue

        if show_fill:
            below_mask = df[raw_k_col] < 20
            above_mask = df[raw_k_col] > 80

            add_masked_fill_segments(fig, df.index, df[k_col], below_mask, 20 + offset, row_index, "rgba(0, 0, 255, 0.22)")
            add_masked_fill_segments(fig, df.index, df[k_col], above_mask, 80 + offset, row_index, "rgba(255, 0, 0, 0.22)")

        fig.add_trace(
            go.Scatter(x=df.index, y=df[k_col], mode="lines", name=f"K {label}", line=dict(color=layer["k_color"], width=1)),
            row=row_index,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df[d_col], mode="lines", name=f"D {label}", line=dict(color=layer["d_color"], width=1)),
            row=row_index,
            col=1,
        )

        # 레이어당 참조선은 20/80 두 줄만(50 선·y 그리드는 층마다 겹쳐 줄무늬가 되므로 제거).
        for guide_value in STOCH_GUIDES:
            add_horizontal_line_trace(fig, df.index, guide_value + offset, row_index)

        # 하위 패널 마커 텍스트는 표시 모드가 정한다(기본형 숨김 · 지표 중심 표시).
        add_stochastic_db_markers(fig, df, row_index, f"stoch_db_{label}", y_offset=offset, show_text=show_marker_text)
        add_stochastic_dt_markers(fig, df, row_index, f"stoch_dt_{label}", y_offset=offset, show_text=show_marker_text)
        add_stochastic_tb_markers(fig, df, row_index, f"stoch_tb_{label}", y_offset=offset, show_text=show_marker_text)
        add_stochastic_tt_markers(fig, df, row_index, f"stoch_tt_{label}", y_offset=offset, show_text=show_marker_text)

    for separator in [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5]:
        add_horizontal_line_trace(fig, df.index, separator, row_index, color="rgba(80,80,80,0.7)", dash="solid", width=1.0)


def add_single_stochastic_layer_panel(fig, df, row_index, layer_suffix, panel_title, show_fill=True,
                                      show_marker_text=False):
    """Adds one stochastic layer panel using the original 0-100 scale."""
    k_col = f"stoch_k_{layer_suffix}"
    d_col = f"stoch_d_{layer_suffix}"
    db_col = f"stoch_db_{layer_suffix}"
    dt_col = f"stoch_dt_{layer_suffix}"

    layer = next((candidate for candidate in STOCH_LAYERS if candidate["label"] == layer_suffix), None)
    if layer is None or k_col not in df.columns or d_col not in df.columns:
        return

    if show_fill:
        below_mask = df[k_col] < 20
        above_mask = df[k_col] > 80

        add_masked_fill_segments(fig, df.index, df[k_col], below_mask, 20, row_index, "rgba(0, 0, 255, 0.22)")
        add_masked_fill_segments(fig, df.index, df[k_col], above_mask, 80, row_index, "rgba(255, 0, 0, 0.22)")

    for guide_value in STOCH_GUIDES:
        add_horizontal_line_trace(fig, df.index, guide_value, row_index)

    fig.add_trace(
        go.Scatter(x=df.index, y=df[k_col], mode="lines", name=f"%K {panel_title}", line=dict(color=layer["k_color"], width=1)),
        row=row_index,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df[d_col], mode="lines", name=f"%D {panel_title}", line=dict(color=layer["d_color"], width=1)),
        row=row_index,
        col=1,
    )

    add_stochastic_db_markers(fig, df, row_index, db_col, show_text=show_marker_text)
    add_stochastic_dt_markers(fig, df, row_index, dt_col, show_text=show_marker_text)
    add_stochastic_tb_markers(fig, df, row_index, f"stoch_tb_{layer_suffix}", show_text=show_marker_text)
    add_stochastic_tt_markers(fig, df, row_index, f"stoch_tt_{layer_suffix}", show_text=show_marker_text)


def add_macd_panel(fig, df, row_index, show_marker_text=False):
    """Adds traditional MACD panel."""
    if "macd" not in df.columns:
        return

    hist = df["macd_hist"]
    hist_prev = df["macd_hist_prev"]
    colors = [
        "#FF4D4D" if c >= (0 if pd.isna(p) else p) else "#F7B6B6" if c >= 0 else "#2F6BFF" if c <= (0 if pd.isna(p) else p) else "#AFC6FF"
        for c, p in zip(hist, hist_prev)
    ]

    fig.add_trace(go.Bar(x=df.index, y=hist, marker_color=colors, name="MACD Hist", showlegend=False), row=row_index, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], mode="lines", name="MACD", line=dict(color="#FF3344", width=1)), row=row_index, col=1)
    fig.add_trace(
        go.Scatter(x=df.index, y=df["macd_signal"], mode="lines", name="Signal", line=dict(color="#2F6BFF", width=1)),
        row=row_index,
        col=1,
    )
    add_horizontal_line_trace(fig, df.index, 0.0, row_index)
    add_macd_event_markers(fig, df, row_index, show_text=show_marker_text)


# MACD 알람 이벤트 마커 — 스토캐 DB/DT(원, 초록/빨강)·TB/TT(마름모) 관례를 그대로 잇는다.
# (라벨, 마커 모양, 색, 텍스트 위치). x 는 확정 봉(교차 봉 +1, 알람 발화 시점) — 교차 봉에
# 찍으면 사후에 마커가 생기는 표시가 된다. y 는 확정 봉의 macd 값.
_MACD_EVENT_STYLE = {
    KIND_MACD_GOLDEN: ("GC", "circle", "#0B8F45", "top center"),
    KIND_MACD_DEAD: ("DC", "circle", "#C62828", "bottom center"),
    KIND_MACD_ZERO_UP: ("0↑", "diamond", "#1565C0", "top center"),
    KIND_MACD_ZERO_DOWN: ("0↓", "diamond", "#AD1457", "bottom center"),
}


def add_macd_event_markers(fig, df, row_index, show_text=False):
    """Adds MACD cross / zero-line event labels on the MACD panel.

    이벤트 위치는 analysis.alarm_signals.macd_event_positions 가 정한다(알람 목록과 동일한
    확정 봉 — 다음 봉 확정 규칙 포함).
    """
    if "macd" not in df.columns:
        return

    for kind, positions in macd_event_positions(df).items():
        if len(positions) == 0:
            continue
        text, symbol, color, text_position = _MACD_EVENT_STYLE[kind]
        fig.add_trace(
            go.Scatter(
                x=positions,
                y=df.loc[positions, "macd"],
                mode="markers+text" if show_text else "markers",   # 텍스트는 지표 중심 모드에서만
                name=text,
                text=[text] * len(positions),
                textposition=text_position,
                textfont=dict(color=color, size=11),
                hovertemplate=text + " %{x}<br>MACD %{y:.4g}<extra></extra>",
                marker=dict(symbol=symbol, size=8, color=color, line=dict(color="#FFFFFF", width=1)),
            ),
            row=row_index,
            col=1,
        )


def add_rsi_panel(fig, df, row_index, show_fill=True, show_marker_text=False):
    """Adds RSI panel."""
    if "rsi" not in df.columns:
        return

    ob, os_, mid = RSI_PARAMS["overbought"], RSI_PARAMS["oversold"], RSI_PARAMS["midline"]

    if show_fill:
        add_masked_fill_segments(fig, df.index, df["rsi"], df["rsi"] > ob, ob, row_index, "rgba(255, 0, 0, 0.35)")
        add_masked_fill_segments(fig, df.index, df["rsi"], df["rsi"] < os_, os_, row_index, "rgba(0, 0, 255, 0.35)")

    add_horizontal_line_trace(fig, df.index, ob, row_index, color="rgba(255,165,0,0.5)")
    add_horizontal_line_trace(fig, df.index, os_, row_index, color="rgba(0,255,255,0.5)")
    add_horizontal_line_trace(fig, df.index, mid, row_index, color="rgba(0,128,0,0.8)", dash="dot")
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], mode="lines", name="RSI", line=dict(color="#000000", width=1.4)), row=row_index, col=1)
    add_stochastic_db_markers(fig, df, row_index, "rsi_db", show_text=show_marker_text)
    add_stochastic_dt_markers(fig, df, row_index, "rsi_dt", show_text=show_marker_text)


def _prepare_chart_df(df: pd.DataFrame) -> pd.DataFrame:
    chart_df = df.sort_index().copy()
    chart_df.index = pd.to_datetime(chart_df.index)
    chart_df["time"] = chart_df.index.map(lambda ts: int(ts.timestamp()))
    return chart_df


def _to_record_list(df: pd.DataFrame, columns: list[str], rename_map: dict[str, str] | None = None) -> list[dict]:
    export_df = df.loc[:, columns].copy()
    if rename_map:
        export_df = export_df.rename(columns=rename_map)
    export_df = export_df.dropna()
    return export_df.to_dict(orient="records")


def _get_ma_series_options(period: int) -> dict:
    options = {
        "color": MA_COLORS[period],
        "lineWidth": MA_LINE_WIDTHS.get(period, 1.0),
        "priceLineVisible": False,
        "lastValueVisible": False,
    }

    if period in {40, 80}:
        options["lineType"] = 1

    return options


def _build_lightweight_price_charts(df: pd.DataFrame, symbol: str, display_interval: str) -> list[dict]:
    chart_df = _prepare_chart_df(df)
    candle_data = _to_record_list(chart_df, ["time", "open", "high", "low", "close"])

    price_series = [
        {
            "type": "Candlestick",
            "data": candle_data,
            "options": {
                "upColor": COLOR_BULL,
                "downColor": COLOR_BEAR,
                "borderUpColor": COLOR_BULL,
                "borderDownColor": COLOR_BEAR,
                "wickUpColor": COLOR_BULL,
                "wickDownColor": COLOR_BEAR,
            },
        }
    ]

    for period in MA_COLORS:
        ma_col = f"MA{period}"
        if ma_col not in chart_df.columns:
            continue

        ma_data = _to_record_list(chart_df, ["time", ma_col], {ma_col: "value"})
        if not ma_data:
            continue

        price_series.append(
            {
                "type": "Line",
                "data": ma_data,
                "options": _get_ma_series_options(period),
            }
        )

    chart_options = {
        "height": 520,
        "layout": {
            "background": {"type": "solid", "color": TV_BACKGROUND},
            "textColor": TV_TEXT,
        },
        "grid": {
            "vertLines": {"color": TV_GRID},
            "horzLines": {"color": TV_GRID},
        },
        "crosshair": {"mode": 0},
        "rightPriceScale": {
            "borderVisible": False,
            "scaleMargins": {"top": 0.1, "bottom": 0.2},
        },
        "timeScale": {
            "borderVisible": False,
            "timeVisible": display_interval not in {"1d", "2d", "3d", "4d", "1w", "2w", "1M"},
            "secondsVisible": False,
        },
        "watermark": {
            "visible": True,
            "fontSize": 28,
            "horzAlign": "left",
            "vertAlign": "top",
            "color": "rgba(25, 28, 36, 0.10)",
            "text": f"{symbol} {display_interval}",
        },
    }

    volume_df = chart_df.loc[:, ["time", "volume"]].copy()
    volume_df["value"] = volume_df["volume"]
    volume_df["color"] = chart_df.apply(lambda row: COLOR_BULL if row["close"] >= row["open"] else COLOR_BEAR, axis=1)
    volume_data = _to_record_list(volume_df, ["time", "value", "color"])
    volume_options = {
        "height": 140,
        "layout": {
            "background": {"type": "solid", "color": TV_BACKGROUND},
            "textColor": TV_TEXT,
        },
        "grid": {
            "vertLines": {"color": TV_GRID},
            "horzLines": {"color": TV_GRID},
        },
        "rightPriceScale": {
            "borderVisible": False,
            "scaleMargins": {"top": 0.15, "bottom": 0},
        },
        "timeScale": {
            "borderVisible": False,
            "visible": True,
            "timeVisible": display_interval not in {"1d", "2d", "3d", "4d", "1w", "2w", "1M"},
            "secondsVisible": False,
        },
    }
    volume_series = [
        {
            "type": "Histogram",
            "data": volume_data,
            "options": {
                "priceFormat": {"type": "volume"},
                "priceLineVisible": False,
                "lastValueVisible": False,
            },
        }
    ]

    return [
        {"chart": chart_options, "series": price_series},
        {"chart": volume_options, "series": volume_series},
    ]


def add_ma_pattern_markers(fig, df, row_index, periods=(5, 10, 20)):
    """가격 패널 위에 이평선 쌍바닥(DB)/쌍봉(DT) 지점을 표시한다.

    잡음 방지를 위해 MA5/MA10/MA20만 표시한다 (MA60 이상 제외).
    """
    for period in periods:
        db_col = f"ma{period}_db"
        dt_col = f"ma{period}_dt"

        if db_col in df.columns:
            pts = df[df[db_col].notna()]
            if not pts.empty:
                fig.add_trace(
                    go.Scatter(
                        x=pts.index,
                        y=pts[db_col],
                        mode="markers+text",
                        name=f"MA{period} DB",
                        text=[f"MA{period} DB"] * len(pts),
                        textposition="top center",
                        textfont=dict(color="#0B8F45", size=10),
                        marker=dict(symbol="triangle-up", size=9, color="#0B8F45", line=dict(color="#FFFFFF", width=1)),
                    ),
                    row=row_index,
                    col=1,
                )

        if dt_col in df.columns:
            pts = df[df[dt_col].notna()]
            if not pts.empty:
                fig.add_trace(
                    go.Scatter(
                        x=pts.index,
                        y=pts[dt_col],
                        mode="markers+text",
                        name=f"MA{period} DT",
                        text=[f"MA{period} DT"] * len(pts),
                        textposition="bottom center",
                        textfont=dict(color="#C62828", size=10),
                        marker=dict(symbol="triangle-down", size=9, color="#C62828", line=dict(color="#FFFFFF", width=1)),
                    ),
                    row=row_index,
                    col=1,
                )


def add_price_panel(fig, df, row_index, symbol: str):
    """Adds the main candlestick and moving-average panel."""
    required_cols = {"open", "high", "low", "close"}
    if not required_cols.issubset(df.columns):
        return

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol,
            increasing=dict(line=dict(color=COLOR_BULL), fillcolor=COLOR_BULL),
            decreasing=dict(line=dict(color=COLOR_BEAR), fillcolor=COLOR_BEAR),
        ),
        row=row_index,
        col=1,
    )

    for period, color in MA_COLORS.items():
        ma_col = f"MA{period}"
        if ma_col not in df.columns:
            continue

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[ma_col],
                mode="lines",
                name=ma_col,
                line=dict(
                    color=color,
                    width=MA_LINE_WIDTHS.get(period, 1.0),
                    dash="dash" if period in {40, 80} else "solid",
                ),
            ),
            row=row_index,
            col=1,
        )


def add_volume_panel(fig, df, row_index):
    """Adds a volume histogram panel."""
    required_cols = {"open", "close", "volume"}
    if not required_cols.issubset(df.columns):
        return

    colors = [COLOR_BULL if close >= open_ else COLOR_BEAR for open_, close in zip(df["open"], df["close"])]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["volume"],
            marker_color=colors,
            name="Volume",
            showlegend=False,
        ),
        row=row_index,
        col=1,
    )


def add_ma_dispersion_panel(fig, df, row_index):
    """MA dispersion 라인 + 수렴 극점(pivot_low) 마커."""
    if "ma_dispersion" not in df.columns:
        return
    disp = df["ma_dispersion"]
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=disp,
            mode="lines",
            name="MA Dispersion",
            line=dict(color="#7B1FA2", width=1.4),
            connectgaps=False,
        ),
        row=row_index,
        col=1,
    )
    if "ma_dispersion_pivot_low" in df.columns:
        piv = df["ma_dispersion_pivot_low"]
        mask = piv.notna()
        if mask.any():
            fig.add_trace(
                go.Scatter(
                    x=df.index[mask],
                    y=piv[mask],
                    mode="markers",
                    name="Convergence",
                    marker=dict(symbol="triangle-down", size=9, color="#4CAF50"),
                    hovertemplate="convergence %{x}<br>%{y:.4f}<extra></extra>",
                ),
                row=row_index,
                col=1,
            )


def _get_synced_chart_rows(
    show_stochastic: bool,
    stochastic_view_mode: str,
    show_macd: bool,
    show_rsi: bool,
    show_ma_dispersion: bool = False,
) -> list[dict]:
    # weight 는 가격 이외 패널들 사이의 상대 비중(가격 행은 PRICE_ROW_SHARE 로 고정, _row_heights 참조).
    rows = [
        {"kind": "price", "title": "Price", "weight": 0},
        {"kind": "volume", "title": "Volume", "weight": 130},
    ]

    if show_stochastic:
        if stochastic_view_mode == "Separated":
            for layer in STOCH_DISPLAY_LAYERS:
                rows.append(
                    {
                        "kind": "stoch_layer",
                        "title": layer["panel_title"],
                        "weight": 240,
                        "suffix": layer["suffix"],
                    }
                )
        else:
            rows.append({"kind": "stoch_stacked", "title": "Stochastic Slow", "weight": 270})

    if show_macd:
        rows.append({"kind": "macd", "title": "MACD", "weight": 240})

    if show_rsi:
        rows.append({"kind": "rsi", "title": "RSI", "weight": 240})

    if show_ma_dispersion:
        rows.append({"kind": "ma_dispersion", "title": "MA Dispersion", "weight": 200})

    return rows


def _row_heights(rows: list[dict], layout_mode: str = DEFAULT_LAYOUT_MODE) -> list[float]:
    """make_subplots row_heights — 표시 중인 패널 집합 기준 절대 비중. 꺼진 패널 비중은 가격이 흡수.

    layout_mode 는 비중 세트(PANEL_SHARES_BY_MODE)만 고른다.
    """
    table = PANEL_SHARES_BY_MODE[layout_mode]
    shares = [table.get(row["kind"], 0.0) for row in rows]
    price_share = 1.0 - sum(s for row, s in zip(rows, shares) if row["kind"] != "price")
    return [price_share if row["kind"] == "price" else s for row, s in zip(rows, shares)]


def _row_pixels(heights: list[float], chart_height: int, spacing: float = VERTICAL_SPACING) -> list[float]:
    """행별 실제 픽셀 높이 — (전체 - 마진) × 비중 × (1 - 간격 총합)."""
    plot_px = chart_height - CHART_MARGIN["t"] - CHART_MARGIN["b"]
    usable = 1.0 - spacing * (len(heights) - 1)
    return [plot_px * h * usable for h in heights]


def _effective_chart_height(rows: list[dict], heights: list[float], chart_height: int) -> int:
    """하위 패널(가격·거래량 제외)이 MIN_SUBPANEL_PX 미만이면 전체 높이를 올려 잡는다."""
    usable = 1.0 - VERTICAL_SPACING * (len(rows) - 1)
    margins = CHART_MARGIN["t"] + CHART_MARGIN["b"]
    need = chart_height
    for row, h in zip(rows, heights):
        if row["kind"] in ("price", "volume") or h <= 0:
            continue
        need = max(need, int(MIN_SUBPANEL_PX / (h * usable) + margins) + 1)
    return int(need)


def _window_df(df):
    return df.iloc[-RECENT_WINDOW:] if len(df) > RECENT_WINDOW else df


def _padded(lo, hi, pad=0.02):
    if pd.isna(lo) or pd.isna(hi):
        return None
    span = (hi - lo) or abs(hi) or 1.0
    return [lo - span * pad, hi + span * pad]


def _fit_yaxes_to_window(fig, df, rows):
    """초기 렌더의 y 범위를 표시 창(최근 RECENT_WINDOW 봉)에 밀착.

    Plotly autorange 는 x 범위를 무시하고 전체 데이터로 y 를 잡는다(1000봉 적재 시 가격 축이
    61k~83k 처럼 넓어짐). 가격·거래량·MACD 는 창 안 값으로 range 를 명시한다. 더블클릭(reset)은
    이 초기 range 로 돌아온다. 스토캐·RSI 는 고정 스케일이라 대상 아님.
    """
    win = _window_df(df)
    for row_index, row in enumerate(rows, start=1):
        kind = row["kind"]
        rng = None
        if kind == "price" and {"low", "high"}.issubset(win.columns):
            cols = [c for c in win.columns if c in ("low", "high") or (c.startswith("MA") and c[2:].isdigit())]
            rng = _padded(win[cols].min().min(), win[cols].max().max())
        elif kind == "volume" and "volume" in win.columns:
            hi = win["volume"].max()
            rng = None if pd.isna(hi) else [0, float(hi) * 1.05]
        elif kind == "macd" and "macd" in win.columns:
            cols = [c for c in ("macd", "macd_signal", "macd_hist") if c in win.columns]
            rng = _padded(win[cols].min().min(), win[cols].max().max(), pad=0.05)
        if rng is not None:
            fig.update_yaxes(range=rng, autorange=False, row=row_index, col=1)


def _apply_recent_window(fig, df):
    if len(df) > RECENT_WINDOW:
        fig.update_xaxes(range=[df.index[-RECENT_WINDOW], df.index[-1]])


def _create_synced_chart_figure(
    df,
    symbol,
    display_interval,
    show_stochastic=True,
    stochastic_view_mode="Stacked",
    show_stoch_fill=True,
    show_macd=True,
    show_rsi=True,
    show_rsi_fill=True,
    show_ma_patterns=False,
    show_ma_dispersion=False,
    chart_height=DEFAULT_CHART_HEIGHT,
    layout_mode=DEFAULT_LAYOUT_MODE,
):
    chart_df = _prepare_chart_df(df)
    show_marker_text = SUBPANEL_MARKER_TEXT_BY_MODE[layout_mode]
    rows = _get_synced_chart_rows(
        show_stochastic,
        stochastic_view_mode,
        show_macd,
        show_rsi,
        show_ma_dispersion,
    )

    heights = _row_heights(rows, layout_mode)
    # 서브플롯 제목 annotation 없음 — 좌측 y축 라벨(Price/Volume/Stoch/MACD/RSI)이 이미 있어 중복이고
    # 패널 사이에서 겹치던 원인. 심볼·TF 는 페이지 상단 알람 헤더가 이미 보여준다.
    fig = make_subplots(
        rows=len(rows),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=VERTICAL_SPACING,
        row_heights=heights,
    )

    for row_index, row in enumerate(rows, start=1):
        kind = row["kind"]
        if kind == "price":
            add_price_panel(fig, chart_df, row_index, symbol)
            if show_ma_patterns:
                add_ma_pattern_markers(fig, chart_df, row_index)
            fig.update_yaxes(title_text="Price", row=row_index, col=1)
        elif kind == "volume":
            add_volume_panel(fig, chart_df, row_index)
            # 눈금 3개 이하, SI(~k) 포맷, 0 에서 시작(거래량은 음수 없음).
            fig.update_yaxes(title_text="Volume", nticks=3, tickformat="~s", rangemode="tozero", row=row_index, col=1)
        elif kind == "stoch_stacked":
            add_stacked_stochastic_panel(fig, chart_df, row_index, show_fill=show_stoch_fill,
                                         show_marker_text=show_marker_text)
            fig.update_yaxes(title_text="Stoch", range=[0, STOCH_MAX_Y], showgrid=False, row=row_index, col=1)
        elif kind == "stoch_layer":
            add_single_stochastic_layer_panel(
                fig,
                chart_df,
                row_index,
                row["suffix"],
                row["title"],
                show_fill=show_stoch_fill,
                show_marker_text=show_marker_text,
            )
            fig.update_yaxes(title_text="Stoch", range=[0, 100], showgrid=False, row=row_index, col=1)
        elif kind == "macd":
            add_macd_panel(fig, chart_df, row_index, show_marker_text=show_marker_text)
            fig.update_yaxes(title_text="MACD", row=row_index, col=1)
        elif kind == "rsi":
            add_rsi_panel(fig, chart_df, row_index, show_fill=show_rsi_fill, show_marker_text=show_marker_text)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=row_index, col=1)
        elif kind == "ma_dispersion":
            add_ma_dispersion_panel(fig, chart_df, row_index)
            fig.update_yaxes(title_text="Dispersion", row=row_index, col=1)
    fig.update_layout(
        height=_effective_chart_height(rows, heights, int(chart_height)),
        template="plotly_white",
        paper_bgcolor=TV_BACKGROUND,
        plot_bgcolor=TV_BACKGROUND,
        font=dict(color=TV_TEXT),
        hovermode="x unified",
        dragmode="pan",   # 휠이 줌을 담당(scrollZoom) → 드래그는 이동
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=CHART_MARGIN,
        # 재실행 사이 줌·이동 상태 유지, 심볼·TF 가 바뀌면 리셋.
        uirevision=f"{symbol}|{display_interval}",
    )
    fig.update_xaxes(
        type="date",
        showgrid=True,
        gridcolor=TV_GRID,
        zeroline=False,
        showline=False,
        rangeslider_visible=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="rgba(25, 28, 36, 0.35)",
        spikethickness=1,
    )
    # 모든 서브플롯 y축을 명시적으로 조작 가능하게(fixedrange=False): 휠·드래그·축 위 휠이 세로로도 듣는다.
    fig.update_yaxes(gridcolor=TV_GRID, zeroline=False, showline=False, fixedrange=False)
    _apply_recent_window(fig, chart_df)
    _fit_yaxes_to_window(fig, chart_df, rows)
    return fig


def render_chart(
    df,
    symbol,
    display_interval,
    show_stochastic=True,
    stochastic_view_mode="Stacked",
    show_stoch_fill=True,
    show_macd=True,
    show_rsi=True,
    show_rsi_fill=True,
    show_ma_patterns=False,
    show_ma_dispersion=False,
    chart_height=DEFAULT_CHART_HEIGHT,
    layout_mode=DEFAULT_LAYOUT_MODE,
):
    """Renders price, volume, and indicators in one synchronized Plotly chart.

    chart_height: 전체 px 높이(사이드바 선택). 조작법 캡션을 차트 아래에 같이 낸다.
    layout_mode: 표시 모드(LAYOUT_MODES) — 패널 비중 세트와 하위 패널 마커 텍스트 표시 여부.
    """
    if df is None or df.empty:
        return

    fig = _create_synced_chart_figure(
        df,
        symbol,
        display_interval,
        show_stochastic=show_stochastic,
        stochastic_view_mode=stochastic_view_mode,
        show_stoch_fill=show_stoch_fill,
        show_macd=show_macd,
        show_rsi=show_rsi,
        show_rsi_fill=show_rsi_fill,
        show_ma_patterns=show_ma_patterns,
        show_ma_dispersion=show_ma_dispersion,
        chart_height=chart_height,
        layout_mode=layout_mode,
    )
    # width="stretch" 는 use_container_width=True 의 현행 표기(1.58 에서 후자는 deprecated).
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
    st.caption(CHART_CONTROLS_CAPTION)
