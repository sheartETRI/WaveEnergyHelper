import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Constants ---
# TradingView MA Color Scheme
MA_COLORS = {
    5:   "#3B3F4C",  # Dark Gray
    10:  "#FFA000",  # Orange
    20:  "#FF5252",  # Red
    40:  "#FF5252",  # Red (for future MA40)
    60:  "#3867F2",  # Blue
    80:  "#3867F2",  # Blue (for future MA80)
    120: "#4CAF50",  # Green
    240: "#B0B4BE",  # Light Gray
    480: "#7ED6DF",  # Light Blue (for future MA480)
    960: "#C58AD9",  # Purple (for future MA960)
}

MA_LINE_WIDTHS = {
    5:   1.0,
    10:  1.0,
    20:  1.2,
    40:  1.2,
    60:  1.4,
    80:  1.4,
    120: 1.6,
    240: 1.8,
    480: 1.8,
    960: 1.8,
}

BINANCE_BASE_URL = "https://api.binance.com/api/v3/klines"
CUSTOM_INTERVALS = ["2d", "4d", "2w"]
SUPPORTED_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# User-defined order for all timeframes in the UI
TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "2d", "3d", "4d",
    "1w", "2w",
    "1M"
]

STOCH_LAYERS = [
    {"name": "Top", "label": "(20,10,10)", "k_len": 20, "k_smooth": 10, "d_len": 10, "k_color": "#00FFFF", "d_color": "#000000", "offset": 220.0},
    {"name": "Mid", "label": "(10,5,5)",  "k_len": 10, "k_smooth": 5,  "d_len": 5,  "k_color": "#800080", "d_color": "#000000", "offset": 110.0},
    {"name": "Bot", "label": "(5,3,3)",   "k_len": 5,  "k_smooth": 3,  "d_len": 3,  "k_color": "#FF0000", "d_color": "#000000", "offset": 0.0},
]
STOCH_BAND = 100.0
STOCH_GAP = 10.0
STOCH_MAX_Y = STOCH_BAND * 3 + STOCH_GAP * 2


# --- Utility Functions ---
@st.cache_data(ttl=600)
def get_auto_limit(interval):
    """Determines the appropriate Binance API limit for the requested interval."""
    limit_map = {
        "1m": 1000, "3m": 1000, "5m": 1000, "15m": 1000, "30m": 1000,
        "1h": 1000, "2h": 1000, "4h": 1000, "6h": 1000, "8h": 1000, "12h": 1000,
        "1d": 500, "3d": 500, "1w": 300, "1M": 240,
        "2d": 1000, "4d": 1000, "2w": 1000,
    }
    return limit_map.get(interval, 500)


@st.cache_data(ttl=600)
def fetch_klines(symbol, interval, limit):
    """Fetches raw OHLCV data from the Binance public API."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(BINANCE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            st.warning(f"No data returned for {symbol} with interval {interval}. Please try a different selection.")
            return None
        return data
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error fetching {symbol} {interval}: {e}. Please check symbol/interval validity.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("Connection Error: Could not connect to Binance API. Please check your internet connection.")
        return None
    except requests.exceptions.Timeout:
        st.error("Request Timeout: Binance API took too long to respond.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during data fetching: {e}")
        return None


@st.cache_data(ttl=600)
def build_dataframe(raw_klines):
    """Converts raw klines into a processed pandas DataFrame."""
    if not raw_klines:
        return None
    try:
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
        ]
        df = pd.DataFrame(raw_klines, columns=columns)
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()

        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        return df
    except Exception as e:
        st.error(f"DataFrame Error during build: {e}")
        return None


@st.cache_data(ttl=600)
def resample_timeframe(df, interval):
    """Resamples a DataFrame to a custom interval."""
    if df is None or df.empty:
        raise ValueError("Empty DataFrame provided for resampling.")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index is not a DatetimeIndex. Cannot resample.")

    rule_map = {
        "2d": "2D",
        "4d": "4D",
        "2w": "2W-MON"
    }

    if interval not in rule_map:
        return df

    rule = rule_map[interval]

    try:
        df_resampled = df.resample(
            rule,
            label="right",
            closed="right",
            origin="start"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        })

        df_resampled = df_resampled.dropna()

        if df_resampled.empty:
            raise ValueError(f"Resampling to {interval} resulted in an empty DataFrame after dropping NaNs.")

        return df_resampled
    except Exception as e:
        raise RuntimeError(f"Error during resampling to {interval}: {e}") from e


@st.cache_data(ttl=600)
def add_moving_averages(df):
    """Calculates MA5, MA10, MA20, MA40, MA60, MA80, MA120, and MA240."""
    if df is None:
        return None
    windows = [5, 10, 20, 40, 60, 80, 120, 240]
    for w in windows:
        if len(df) >= w:
            df[f'MA{w}'] = df['close'].rolling(window=w).mean()
        else:
            df[f'MA{w}'] = pd.NA
    return df


@st.cache_data(ttl=600)
def add_stochastic_slow_layers(df):
    """Adds 3-layer stacked stochastic slow values based on the Pine reference script."""
    if df is None or df.empty:
        return df

    for layer in STOCH_LAYERS:
        k_len = layer["k_len"]
        k_smooth = layer["k_smooth"]
        d_len = layer["d_len"]
        offset = layer["offset"]
        suffix = layer["label"]

        lowest_low = df['low'].rolling(window=k_len, min_periods=k_len).min()
        highest_high = df['high'].rolling(window=k_len, min_periods=k_len).max()
        denominator = highest_high - lowest_low

        fast_k = ((df['close'] - lowest_low) / denominator.replace(0, pd.NA)) * 100.0
        fast_k = fast_k.fillna(0.0)

        slow_k = fast_k.rolling(window=k_smooth, min_periods=k_smooth).mean()
        slow_d = slow_k.rolling(window=d_len, min_periods=d_len).mean()

        df[f'stoch_k_{suffix}'] = slow_k
        df[f'stoch_d_{suffix}'] = slow_d
        df[f'stoch_k_shifted_{suffix}'] = slow_k + offset
        df[f'stoch_d_shifted_{suffix}'] = slow_d + offset

    return df


def get_ma_alignment(df):
    """Determines if MAs are in Bullish, Bearish, or Mixed alignment."""
    if df is None or df.empty:
        return "No data for alignment check"

    last = df.iloc[-1]
    ma_periods_for_alignment = [5, 10, 20, 40, 60, 80, 120, 240]
    ma_vals = []
    for p in ma_periods_for_alignment:
        ma_col = f'MA{p}'
        if ma_col in last.index and not pd.isna(last[ma_col]):
            ma_vals.append(last[ma_col])
        else:
            return "Incomplete MA data for alignment check"

    if all(ma_vals[i] > ma_vals[i + 1] for i in range(len(ma_vals) - 1)):
        return "Bullish Alignment (정배열) 🚀"
    if all(ma_vals[i] < ma_vals[i + 1] for i in range(len(ma_vals) - 1)):
        return "Bearish Alignment (역배열) 📉"
    return "Mixed / Consolidation (혼조세) ⚖️"



def get_tick_format(interval):
    """Returns a suitable tickformat string for the plotly x-axis."""
    if interval in ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h"]:
        return '%m-%d %H:%M'
    if interval in ["1d", "2d", "3d", "4d", "1w", "2w"]:
        return '%Y-%m-%d'
    if interval == "1M":
        return '%Y-%m'
    return '%Y-%m-%d'


def add_horizontal_line_trace(fig, x_index, y_value, row_index, color='rgba(120,120,120,0.9)', dash='dash', width=1.2):
    """Adds a horizontal line as a Scatter trace so it renders reliably above fills."""
    fig.add_trace(
        go.Scatter(
            x=x_index,
            y=[y_value] * len(x_index),
            mode='lines',
            line=dict(color=color, dash=dash, width=width),
            hoverinfo='skip',
            showlegend=False,
        ),
        row=row_index,
        col=1,
    )


def add_stochastic_panel(fig, df, row_index, show_fill=True):
    """Adds stacked 3-layer stochastic slow traces to the target subplot row."""
    for layer in STOCH_LAYERS:
        label = layer["label"]
        offset = layer["offset"]
        k_col = f'stoch_k_shifted_{label}'
        d_col = f'stoch_d_shifted_{label}'
        raw_k_col = f'stoch_k_{label}'

        if k_col not in df.columns or d_col not in df.columns:
            continue

        # Oversold / overbought fills driven by K only, following the Pine script semantics
        if show_fill:
            below_mask = df[raw_k_col] < 20
            above_mask = df[raw_k_col] > 80

            oversold_series = df[k_col].where(below_mask)
            overbought_series = df[k_col].where(above_mask)

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=[20 + offset] * len(df),
                    mode='lines',
                    line=dict(width=0),
                    hoverinfo='skip',
                    showlegend=False,
                ),
                row=row_index,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=oversold_series,
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor='rgba(0, 0, 255, 0.22)',
                    hoverinfo='skip',
                    name=f"{layer['name']} Oversold",
                    showlegend=False,
                ),
                row=row_index,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=[80 + offset] * len(df),
                    mode='lines',
                    line=dict(width=0),
                    hoverinfo='skip',
                    showlegend=False,
                ),
                row=row_index,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=overbought_series,
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor='rgba(255, 0, 0, 0.22)',
                    hoverinfo='skip',
                    name=f"{layer['name']} Overbought",
                    showlegend=False,
                ),
                row=row_index,
                col=1,
            )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[k_col],
                mode='lines',
                name=f"K {label}",
                line=dict(color=layer['k_color'], width=2),
            ),
            row=row_index,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[d_col],
                mode='lines',
                name=f"D {label}",
                line=dict(color=layer['d_color'], width=1),
            ),
            row=row_index,
            col=1,
        )

        # 20 / 50 / 80 guide lines for each band: add after fills and K/D so they remain visible
        for guide_value in (20, 50, 80):
            add_horizontal_line_trace(
                fig,
                df.index,
                guide_value + offset,
                row_index,
                color='rgba(120,120,120,0.9)',
                dash='dash',
                width=1.2,
            )

    # Band separator lines
    for separator in [STOCH_BAND + STOCH_GAP / 2, STOCH_BAND * 2 + STOCH_GAP * 1.5]:
        add_horizontal_line_trace(
            fig,
            df.index,
            separator,
            row_index,
            color='rgba(80,80,80,0.7)',
            dash='solid',
            width=1.0,
        )



def render_chart(df, symbol, display_interval, fetched_interval, show_stochastic=True, show_stoch_fill=True):
    """Renders candlestick, volume, and optional stochastic slow panel using Plotly."""
    if df is None or df.empty:
        st.warning("No data to display chart.")
        return

    if show_stochastic:
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.58, 0.16, 0.26],
        )
        volume_row = 2
        stoch_row = 3
    else:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.75, 0.25],
        )
        volume_row = 2
        stoch_row = None

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            increasing_line_color='#FF0000',
            decreasing_line_color='#0000FF',
            name='Candlestick',
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    ma_periods_to_plot = [5, 10, 20, 40, 60, 80, 120, 240]
    for period in ma_periods_to_plot:
        col_name = f'MA{period}'
        if col_name in df.columns and not df[col_name].dropna().empty:
            dash_style = 'dash' if period in [40, 80] else None
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col_name],
                    mode='lines',
                    name=f'MA{period}',
                    line=dict(color=MA_COLORS.get(period, '#000000'), width=MA_LINE_WIDTHS.get(period, 1.0), dash=dash_style),
                ),
                row=1,
                col=1,
            )

    volume_colors = [
        '#FF0000' if df['close'].iloc[i] > df['open'].iloc[i] else '#0000FF'
        for i in range(len(df))
    ]

    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            marker_color=volume_colors,
            name='Volume',
            showlegend=False,
        ),
        row=volume_row,
        col=1,
    )

    if show_stochastic and stoch_row is not None:
        add_stochastic_panel(fig, df, stoch_row, show_fill=show_stoch_fill)

    chart_height = 900 if show_stochastic else 700
    fig.update_layout(
        title=f"{symbol} Market Overview ({display_interval})",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend_title="Indicators",
        template="plotly_white",
        height=chart_height,
        xaxis=dict(showticklabels=False, zeroline=False, showgrid=False),
        yaxis_title="Price (USDT)",
        dragmode="pan",
    )

    tick_format = get_tick_format(display_interval)
    bottom_row = 3 if show_stochastic else 2
    fig.update_xaxes(type="date", nticks=8, tickformat=tick_format, row=bottom_row, col=1)

    fig.update_yaxes(showgrid=False, zeroline=False, row=1, col=1)
    fig.update_yaxes(showgrid=False, zeroline=False, title_text="Volume", row=volume_row, col=1)

    if show_stochastic and stoch_row is not None:
        fig.update_yaxes(
            showgrid=False,
            zeroline=False,
            title_text="Stoch Slow",
            range=[0, STOCH_MAX_Y],
            tickmode='array',
            tickvals=[20, 50, 80, 130, 160, 190, 240, 270, 300],
            ticktext=['20', '50', '80', '20', '50', '80', '20', '50', '80'],
            row=stoch_row,
            col=1,
        )

    config = {
        "scrollZoom": True,
        "displayModeBar": True,
        "doubleClick": "reset",
    }

    st.plotly_chart(fig, use_container_width=True, config=config)



def main():
    """Main Streamlit application function."""
    st.set_page_config(layout="wide", page_title="Binance MA Chart Viewer")
    st.title("Binance MA Chart Viewer")

    st.sidebar.header("Chart Settings")
    selected_symbol = st.sidebar.selectbox("Select Symbol", options=SUPPORTED_SYMBOLS, index=0)
    selected_interval = st.sidebar.selectbox(
        "Select Timeframe",
        options=TIMEFRAMES,
        index=TIMEFRAMES.index("1d")
    )
    show_stochastic = st.sidebar.checkbox("Show Stochastic Slow", value=True)
    show_stoch_fill = st.sidebar.checkbox("Fill 80/20 Zones", value=True, disabled=not show_stochastic)

    st.write(f"### {selected_symbol} ({selected_interval})")

    df = None
    fetched_data_limit = get_auto_limit(selected_interval)
    original_fetch_interval = selected_interval

    with st.spinner(f"Fetching {selected_symbol} {selected_interval} data..."):
        try:
            if selected_interval in CUSTOM_INTERVALS:
                original_fetch_interval = "1d"
                raw_data = fetch_klines(selected_symbol, original_fetch_interval, fetched_data_limit)
                if raw_data is None:
                    return

                df = build_dataframe(raw_data)
                if df is None:
                    return

                if 0 < len(df) < 240:
                    st.warning(
                        f"Fetched only {len(df)} daily candles for resampling {selected_interval}. "
                        "Consider increasing the limit for better results."
                    )

                df = resample_timeframe(df, selected_interval)
            else:
                raw_data = fetch_klines(selected_symbol, selected_interval, fetched_data_limit)
                if raw_data is None:
                    return
                df = build_dataframe(raw_data)
                if df is None:
                    return

            if df is not None and not df.empty:
                df = add_moving_averages(df)
                if show_stochastic:
                    df = add_stochastic_slow_layers(df)

                alignment = get_ma_alignment(df)
                st.caption(f"MA alignment: {alignment}")

                render_chart(
                    df,
                    selected_symbol,
                    selected_interval,
                    original_fetch_interval,
                    show_stochastic=show_stochastic,
                    show_stoch_fill=show_stoch_fill,
                )
            else:
                st.error("No valid data available after processing. Please adjust your selections or try again later.")

        except (ValueError, TypeError, RuntimeError) as e:
            st.error(f"Processing Error: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
