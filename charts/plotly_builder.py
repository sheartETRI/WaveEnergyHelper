# charts/plotly_builder.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

from config.settings import (
    MA_COLORS,
    MA_LINE_WIDTHS,
    RSI_PARAMS,
    STOCH_BAND,
    STOCH_GAP,
    STOCH_LAYERS,
    STOCH_MAX_Y,
)
from display.stability_verdict import STABLE_COL, STRIP_COLORS, duration_at
from analysis.wave_tracker import STATE_COLORS


COLOR_BULL = "#ff0000"
COLOR_BEAR = "#0000ff"
TV_BACKGROUND = "#ffffff"
TV_TEXT = "#191c24"
TV_GRID = "rgba(42, 46, 57, 0.12)"
RECENT_WINDOW = 150
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


def add_stochastic_db_markers(fig, df, row_index, db_col, y_offset=0.0):
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
            mode="markers+text",
            name="DB",
            text=["DB"] * len(points),
            textposition="top center",
            textfont=dict(color="#0B8F45", size=11),
            marker=dict(symbol="circle", size=8, color="#0B8F45", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_dt_markers(fig, df, row_index, dt_col, y_offset=0.0):
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
            mode="markers+text",
            name="DT",
            text=["DT"] * len(points),
            textposition="bottom center",
            textfont=dict(color="#C62828", size=11),
            marker=dict(symbol="circle", size=8, color="#C62828", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_tb_markers(fig, df, row_index, tb_col, y_offset=0.0):
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
            mode="markers+text",
            name="TB",
            text=["TB"] * len(points),
            textposition="top center",
            textfont=dict(color="#1565C0", size=11),
            marker=dict(symbol="diamond", size=9, color="#1565C0", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_tt_markers(fig, df, row_index, tt_col, y_offset=0.0):
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
            mode="markers+text",
            name="TT",
            text=["TT"] * len(points),
            textposition="bottom center",
            textfont=dict(color="#AD1457", size=11),
            marker=dict(symbol="diamond", size=9, color="#AD1457", line=dict(color="#FFFFFF", width=1)),
        ),
        row=row_index,
        col=1,
    )


def add_stacked_stochastic_panel(fig, df, row_index, show_fill=True):
    """Adds the existing stacked 3-layer stochastic slow traces."""
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

        for guide_value in (20, 50, 80):
            add_horizontal_line_trace(fig, df.index, guide_value + offset, row_index)

        add_stochastic_db_markers(
            fig,
            df,
            row_index,
            f"stoch_db_{label}",
            y_offset=offset,
        )
        add_stochastic_dt_markers(
            fig,
            df,
            row_index,
            f"stoch_dt_{label}",
            y_offset=offset,
        )
        add_stochastic_tb_markers(fig, df, row_index, f"stoch_tb_{label}", y_offset=offset)
        add_stochastic_tt_markers(fig, df, row_index, f"stoch_tt_{label}", y_offset=offset)

    for separator in [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5]:
        add_horizontal_line_trace(fig, df.index, separator, row_index, color="rgba(80,80,80,0.7)", dash="solid", width=1.0)


def add_single_stochastic_layer_panel(fig, df, row_index, layer_suffix, panel_title, show_fill=True):
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

    for guide_value in (20, 50, 80):
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

    add_stochastic_db_markers(fig, df, row_index, db_col)
    add_stochastic_dt_markers(fig, df, row_index, dt_col)
    add_stochastic_tb_markers(fig, df, row_index, f"stoch_tb_{layer_suffix}")
    add_stochastic_tt_markers(fig, df, row_index, f"stoch_tt_{layer_suffix}")


def add_macd_panel(fig, df, row_index):
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


def add_rsi_panel(fig, df, row_index, show_fill=True):
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
    add_stochastic_db_markers(fig, df, row_index, "rsi_db")
    add_stochastic_dt_markers(fig, df, row_index, "rsi_dt")


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


def add_family_strip_panel(
    fig,
    x_index,
    families,
    row_index,
    panel_title: str,
    hover_raw,
    hover_stable,
    hover_duration,
):
    """가로 family 띠 — 마커 스트립 + tooltip."""
    x_list = list(x_index)
    colors = [STRIP_COLORS.get(str(f), "#BDBDBD") if pd.notna(f) else "#f5f5f5" for f in families]
    hover_text = []
    for x, r, s, d in zip(x_list, hover_raw, hover_stable, hover_duration):
        ts = pd.Timestamp(x).strftime("%Y-%m-%d")
        hover_text.append(
            f"{ts}<br>raw:<br>{r}<br>stable:<br>{s}<br>duration:<br>{d} bars"
        )
    fig.add_trace(
        go.Scatter(
            x=x_list,
            y=[1.0] * len(x_list),
            mode="markers",
            marker=dict(symbol="square", size=10, color=colors, line=dict(width=0)),
            text=hover_text,
            hoverinfo="text",
            name=panel_title,
            showlegend=False,
        ),
        row=row_index,
        col=1,
    )
    fig.update_yaxes(visible=False, range=[0, 2], row=row_index, col=1)


def _get_synced_chart_rows(
    show_stochastic: bool,
    stochastic_view_mode: str,
    show_macd: bool,
    show_rsi: bool,
    show_ma_dispersion: bool = False,
    show_stability: bool = False,
    show_wave_tracker: bool = False,
) -> list[dict]:
    rows = [
        {"kind": "price", "title": "Price", "height": 520},
        {"kind": "volume", "title": "Volume", "height": 130},
    ]

    if show_stochastic:
        if stochastic_view_mode == "Separated":
            for layer in STOCH_DISPLAY_LAYERS:
                rows.append(
                    {
                        "kind": "stoch_layer",
                        "title": layer["panel_title"],
                        "height": 240,
                        "suffix": layer["suffix"],
                    }
                )
        else:
            rows.append({"kind": "stoch_stacked", "title": "Stochastic Slow", "height": 270})

    if show_macd:
        rows.append({"kind": "macd", "title": "MACD", "height": 240})

    if show_rsi:
        rows.append({"kind": "rsi", "title": "RSI", "height": 240})

    if show_ma_dispersion:
        rows.append({"kind": "ma_dispersion", "title": "MA Dispersion", "height": 200})

    if show_stability:
        rows.append({"kind": "family_raw", "title": "Raw Family", "height": 56})
        rows.append({"kind": "family_stable", "title": "Stable Family (3)", "height": 56})

    if show_wave_tracker:
        rows.append({"kind": "wave_tracker", "title": "Wave Tracker", "height": 56})

    return rows


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
    show_stability=False,
    stability_aligned=None,
    show_wave_tracker=False,
    wave_tracker_aligned=None,
):
    chart_df = _prepare_chart_df(df)
    rows = _get_synced_chart_rows(
        show_stochastic,
        stochastic_view_mode,
        show_macd,
        show_rsi,
        show_ma_dispersion,
        show_stability,
        show_wave_tracker,
    )

    fig = make_subplots(
        rows=len(rows),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.018,
        row_heights=[row["height"] for row in rows],
        subplot_titles=[f"{symbol} {display_interval}" if row["kind"] == "price" else row["title"] for row in rows],
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
            fig.update_yaxes(title_text="Volume", row=row_index, col=1)
        elif kind == "stoch_stacked":
            add_stacked_stochastic_panel(fig, chart_df, row_index, show_fill=show_stoch_fill)
            fig.update_yaxes(title_text="Stoch", range=[0, STOCH_MAX_Y], row=row_index, col=1)
        elif kind == "stoch_layer":
            add_single_stochastic_layer_panel(
                fig,
                chart_df,
                row_index,
                row["suffix"],
                row["title"],
                show_fill=show_stoch_fill,
            )
            fig.update_yaxes(title_text="Stoch", range=[0, 100], row=row_index, col=1)
        elif kind == "macd":
            add_macd_panel(fig, chart_df, row_index)
            fig.update_yaxes(title_text="MACD", row=row_index, col=1)
        elif kind == "rsi":
            add_rsi_panel(fig, chart_df, row_index, show_fill=show_rsi_fill)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=row_index, col=1)
        elif kind == "ma_dispersion":
            add_ma_dispersion_panel(fig, chart_df, row_index)
            fig.update_yaxes(title_text="Dispersion", row=row_index, col=1)
        elif kind in ("family_raw", "family_stable") and stability_aligned is not None:
            strip_df = stability_aligned.set_index("timestamp").reindex(chart_df.index)
            raw_seq = strip_df["family"].fillna("NEUTRAL").tolist()
            stable_seq = strip_df[STABLE_COL].fillna("NEUTRAL").tolist()
            durations = [
                duration_at(stable_seq, i) for i in range(len(stable_seq))
            ]
            fam_col = "family" if kind == "family_raw" else STABLE_COL
            add_family_strip_panel(
                fig,
                chart_df.index,
                strip_df[fam_col].fillna("NEUTRAL").tolist(),
                row_index,
                row["title"],
                raw_seq,
                stable_seq,
                durations,
            )
        elif kind == "wave_tracker" and wave_tracker_aligned is not None:
            strip_df = wave_tracker_aligned.set_index("timestamp").reindex(chart_df.index)
            states = strip_df["state"].fillna("NONE").tolist()
            reasons = strip_df["reason"].fillna("").tolist()
            durations = strip_df["duration"].fillna(0).astype(int).tolist()
            hover_raw = states
            hover_stable = reasons
            hover_dur = durations
            colors = [STATE_COLORS.get(str(s), "#BDBDBD") for s in states]
            x_list = list(chart_df.index)
            hover_text = [
                f"{pd.Timestamp(x).strftime('%Y-%m-%d')}<br>"
                f"state:<br>{st}<br>reason:<br>{r}<br>duration:<br>{d} bars"
                for x, st, r, d in zip(x_list, states, reasons, durations)
            ]
            fig.add_trace(
                go.Scatter(
                    x=x_list,
                    y=[1.0] * len(x_list),
                    mode="markers",
                    marker=dict(symbol="square", size=10, color=colors, line=dict(width=0)),
                    text=hover_text,
                    hoverinfo="text",
                    name="Wave Tracker",
                    showlegend=False,
                ),
                row=row_index,
                col=1,
            )
            fig.update_yaxes(visible=False, range=[0, 2], row=row_index, col=1)

    total_height = sum(row["height"] for row in rows) + 60
    fig.update_layout(
        height=total_height,
        template="plotly_white",
        paper_bgcolor=TV_BACKGROUND,
        plot_bgcolor=TV_BACKGROUND,
        font=dict(color=TV_TEXT),
        hovermode="x unified",
        dragmode="pan",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=50, r=20, t=45, b=30),
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
    fig.update_yaxes(showgrid=True, gridcolor=TV_GRID, zeroline=False, showline=False)
    _apply_recent_window(fig, chart_df)
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
    show_stability=False,
    stability_aligned=None,
    show_wave_tracker=False,
    wave_tracker_aligned=None,
):
    """Renders price, volume, and indicators in one synchronized Plotly chart."""
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
        show_stability=show_stability,
        stability_aligned=stability_aligned,
        show_wave_tracker=show_wave_tracker,
        wave_tracker_aligned=wave_tracker_aligned,
    )
    st.plotly_chart(fig, width="stretch", config={"scrollZoom": True, "displaylogo": False})
