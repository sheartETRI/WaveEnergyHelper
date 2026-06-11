import requests
import pandas as pd
import mplfinance as mpf
import os
import sys
import argparse

"""
Binance Market Data Visualization Prototype (v6)
- Refined resample_timeframe function with robust error handling and TradingView-like '2W-MON' rule.
- MA10 included, TradingView MA colors, CLI arguments, enhanced visualization, and MA alignment status retained.
"""

# TradingView MA Color Scheme
MA_COLORS = {
    5:   "#3B3F4C",  # Dark Gray
    10:  "#FFA000",  # Orange
    20:  "#FF5252",  # Red
    40:  "#FF5252",  # Red (for future MA40 - same as MA20 for now, can be changed later for linestyle)
    60:  "#3867F2",  # Blue
    80:  "#3867F2",  # Blue (for future MA80 - same as MA60 for now)
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

def fetch_klines(symbol, interval, limit):
    """
    Fetches raw OHLCV data from Binance Public API.
    Handles network errors and empty data responses.
    """
    base_url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f"Error: No data returned for {symbol} with interval {interval}.")
            return None
        return data
    except Exception as e:
        print(f"Network/API Error fetching {symbol} {interval}: {e}")
        return None

def build_dataframe(raw_klines):
    """
    Converts raw klines into a processed pandas DataFrame.
    Sets 'open_time' as datetime index and converts numeric columns.
    """
    if not raw_klines: return None
    try:
        columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore']
        df = pd.DataFrame(raw_klines, columns=columns)
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']].copy()
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        return df
    except Exception as e:
        print(f"DataFrame Error during build: {e}")
        return None

def resample_timeframe(df, interval):
    """
    Resamples a DataFrame to a custom interval (e.g., "2d", "4d", "2w").
    Aggregates OHLCV data: open (first), high (max), low (min), close (last), volume (sum).
    Raises ValueError or TypeError for invalid input or empty resampled output.
    """
    if df is None or df.empty:
        raise ValueError("Empty DataFrame provided for resampling.")
    
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index is not a DatetimeIndex. Cannot resample.")

    rule_map = {
        "2d": "2D",
        "4d": "4D",
        "2w": "2W-MON"  # Monthly based 2-week candles starting on Monday
    }

    if interval not in rule_map:
        # This case implies an interval not intended for resampling, so return original df
        return df
    
    rule = rule_map[interval]

    try:
        df_resampled = df.resample(
            rule,
            label="right", # Label the interval with the right (end) bin edge
            closed="right" # Close the interval on the right side
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        })
        
        df_resampled = df_resampled.dropna() # Drop rows where any OHLCV is NaN

        if df_resampled.empty:
            raise ValueError(f"Resampling to {interval} resulted in an empty DataFrame after dropping NaNs.")

        return df_resampled
    except Exception as e:
        # Catch any other pandas-related resampling errors
        raise RuntimeError(f"Error during resampling to {interval}: {e}") from e

def add_moving_averages(df):
    """
    Calculates MA5, MA10, MA20, MA40, MA60, MA80, MA120, and MA240 for the DataFrame.
    """
    if df is None: return None
    windows = [5, 10, 20, 40, 60, 80, 120, 240]
    for w in windows:
        df[f'MA{w}'] = df['close'].rolling(window=w).mean()
    return df

def get_ma_alignment(df):
    """
    Determines if MAs are in Bullish, Bearish, or Mixed alignment.
    Requires MA5, MA10, MA20, MA40, MA60, MA80, MA120, MA240 to be present.
    """
    last = df.iloc[-1]
    ma_periods_for_alignment = [5, 10, 20, 40, 60, 80, 120, 240]
    ma_vals = []
    for p in ma_periods_for_alignment:
        ma_col = f'MA{p}'
        if ma_col in last.index:
            ma_vals.append(last[ma_col])
        else:
            return "Incomplete MA data for alignment check"
    
    if any(pd.isna(ma_vals)) or len(ma_vals) != len(ma_periods_for_alignment):
        return "Insufficient data for full alignment check"
    
    if all(ma_vals[i] > ma_vals[i+1] for i in range(len(ma_vals)-1)):
        return "Bullish Alignment (정배열) 🚀"
    elif all(ma_vals[i] < ma_vals[i+1] for i in range(len(ma_vals)-1)):
        return "Bearish Alignment (역배열) 📉"
    else:
        return "Mixed / Consolidation (혼조세) ⚖️"

def plot_chart(df, symbol, interval, output_path):
    """
    Plots an enhanced candlestick chart with MAs and saves it to a file.
    Supports custom MA colors and widths defined globally.
    MA40 and MA80 are plotted with dashed linestyles.
    """
    if df is None or df.empty: 
        print("Error: No data available to plot chart.")
        return False
    
    try:
        ma_periods_to_plot = [5, 10, 20, 40, 60, 80, 120, 240]
        
        addplots = []
        for period in ma_periods_to_plot:
            col_name = f'MA{period}'
            color = MA_COLORS.get(period, '#000000') 
            width = MA_LINE_WIDTHS.get(period, 1.0)
            
            linestyle = 'solid'
            if period in [40, 80]:
                linestyle = 'dashed'
            
            if col_name in df.columns and not df[col_name].dropna().empty:
                addplots.append(mpf.make_addplot(df[col_name], color=color, width=width, linestyle=linestyle, panel=0)) # panel=0 ensures it's on main chart
        
        # mc = mpf.make_marketcolors(
        #     up='#FF3B3B',        # 상승 → 빨강
        #     down='#2979FF',     # 하락 → 파랑
        #     edge='inherit',
        #     wick='inherit',
        #     volume='inherit'
        # )
        mc = mpf.make_marketcolors(
            up=(1.0, 0.2, 0.2, 0.7),
            down=(0.2, 0.4, 1.0, 0.7),
            edge='inherit',
            wick={'up': '#ff3b3b', 'down': '#2979ff'},
            volume='inherit'
        )
        
        custom_style = mpf.make_mpf_style(
            base_mpf_style='charles',
            marketcolors=mc,
            gridstyle='--',
            facecolor='#f0f0f0',
            edgecolor='black',
            y_on_right=True
        )
        # custom_style = mpf.make_mpf_style(
        #     base_mpf_style='charles',
        #     gridstyle='--',
        #     facecolor='#f0f0f0',
        #     edgecolor='black',
        #     y_on_right=True
        # )

        title = f"{symbol} Market Overview ({interval})\nMoving Averages: {', '.join(map(str, ma_periods_to_plot))}"
        
        mpf.plot(
            df,
            type='candle',
            addplot=addplots,
            style=custom_style,
            title=title,
            ylabel='Price (USDT)',
            volume=True,
            ylabel_lower='Volume',
            savefig=output_path,
            figsize=(14, 10),
            tight_layout=True
        )
        return True
    except Exception as e:
        print(f"Plotting Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Binance BTCUSDT MA Visualizer with Custom Timeframes")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol (e.g., BTCUSDT)")
    parser.add_argument("--interval", type=str, default="1h", help="Timeframe (e.g., 1m, 5m, 1h, 1d, 2d, 4d, 2w)")
    parser.add_argument("--limit", type=int, default=500, help="Number of candles to fetch/process.")
    parser.add_argument("--output", type=str, default=None, help="Output image path. Default: [symbol]_[interval]_ma_chart.png")
    
    args = parser.parse_args()
    
    if not args.output:
        args.output = f"{args.symbol.lower()}_{args.interval}_ma_chart.png"

    print(f"--- Processing {args.symbol} ({args.interval}) ---")
    
    custom_intervals = ["2d", "4d", "2w"]
    df = None

    try:
        if args.interval in custom_intervals:
            print(f"Fetching 1d data for custom interval {args.interval}...")
            raw_data = fetch_klines(args.symbol, "1d", args.limit)
            if raw_data is None: # fetch_klines already prints error
                sys.exit(1)

            df = build_dataframe(raw_data)
            if df is None: # build_dataframe already prints error
                sys.exit(1)
            
            original_num_candles = len(df)
            df = resample_timeframe(df, args.interval) # This function now raises exceptions
            
            if len(df) < 50 and original_num_candles > 0: 
                print(f"Warning: Only {len(df)} candles remain after resampling from {original_num_candles} daily candles. Consider increasing --limit.")

        else:
            raw_data = fetch_klines(args.symbol, args.interval, args.limit)
            if raw_data is None: # fetch_klines already prints error
                sys.exit(1)
            df = build_dataframe(raw_data)
            if df is None: # build_dataframe already prints error
                sys.exit(1)
        
        # Proceed with MA calculation and plotting if DataFrame is valid
        if df is not None and not df.empty:
            df = add_moving_averages(df)
            
            print("\n[ Data Summary ]")
            print(f"Symbol: {args.symbol}")
            print(f"Timeframe: {args.interval}")
            print(f"Data points after processing: {len(df)}")

            last_candle = df.iloc[-1]
            print("\n[ Market Status ]")
            print(f"Current Price: {last_candle['close']:,.2f} USDT")
            
            ma_labels_to_report = [5, 10, 20, 40, 60, 80, 120, 240]
            for m in ma_labels_to_report:
                val = last_candle[f'MA{m}']
                print(f"MA{m: <3}: {val:,.2f} USDT" if not pd.isna(val) else f"MA{m: <3}: N/A (Insufficient data)")
            
            alignment = get_ma_alignment(df)
            print(f"Alignment: {alignment}")
            
            if plot_chart(df, args.symbol, args.interval, args.output):
                print(f"\nSuccess: Chart saved to '{args.output}'")
            else:
                print("\nError: Could not generate chart.")
        else:
            print("Fatal Error: No valid data available after all processing. Exiting.")
            sys.exit(1)
            
    except (ValueError, TypeError, RuntimeError) as e:
        print(f"Processing Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
