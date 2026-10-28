"""앱·CLI·구형 알림이 공유하는 OHLCV 적재와 지표 계산."""
from config.settings import CUSTOM_INTERVALS
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, get_fetch_interval, resample_timeframe
from indicators.moving_averages import add_moving_averages
from indicators.oscillators import add_macd, add_rsi
from indicators.stochastic import add_stochastic_slow_layers


def load_frame(symbol: str, interval: str, with_macd: bool = True):
    """OHLCV 적재 → 지표 계산. 실패 시 None.

    with_macd=False 면 add_macd 를 건너뛴다 → MACD 컬럼이 없어 알람 레이어가 MACD 4종을 조용히
    건너뛰고 차트에도 MACD 패널이 없다("MACD 패널" 토글 꺼짐).
    fetch/build/지표는 각자 st.cache_data(ttl=600)를 갖고 있어 여기서 추가 캐시는 두지 않는다.
    """
    fetch_interval = get_fetch_interval(interval)
    raw = fetch_klines(symbol, fetch_interval, get_auto_limit(interval))
    if not raw:
        return None

    df = build_dataframe(raw)
    if df is None or df.empty:
        return None
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)

    df = add_moving_averages(df)
    df = add_stochastic_slow_layers(df)
    if with_macd:
        df = add_macd(df)
    df = add_rsi(df)
    return df
