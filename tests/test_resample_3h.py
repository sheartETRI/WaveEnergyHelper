"""3h 리샘플 회귀 테스트.

확정 규칙:
- 경계는 UTC 00/03/06... (시각이 3의 배수)
- 라벨은 캔들 시작 시각(open time): label="left", closed="left", origin="epoch"
- 시작 시각이 어긋난 1h 데이터를 넣어도 경계는 00/03/06에 정렬된다.

실행: `python -m pytest tests/test_resample_3h.py` 또는 `python tests/test_resample_3h.py`
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.processor import resample_timeframe


def _make_1h(start, periods):
    idx = pd.date_range(start, periods=periods, freq="1h")
    # open=시각의 시(hour) 기반 결정적 값, 변동폭을 둬 high/low/close 구분
    base = idx.hour.astype(float) + 1.0
    df = pd.DataFrame(
        {
            "open": base,
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base + 0.1,
            "volume": base * 10.0,
        },
        index=idx,
    )
    return df


def test_boundaries_are_multiples_of_three():
    df = _make_1h("2024-01-01 00:00", 48)
    out = resample_timeframe(df, "3h")
    assert not out.empty
    assert all(ts.hour % 3 == 0 for ts in out.index), [str(t) for t in out.index]
    # 인덱스가 1970 epoch 기준 3h 격자에 정렬되어 있는지 (분/초 0)
    assert all(ts.minute == 0 and ts.second == 0 for ts in out.index)


def test_first_candle_ohlcv_aggregation():
    df = _make_1h("2024-01-01 00:00", 48)
    out = resample_timeframe(df, "3h")

    first_ts = pd.Timestamp("2024-01-01 00:00")
    assert first_ts in out.index
    first = out.loc[first_ts]
    src = df.loc["2024-01-01 00:00":"2024-01-01 02:00"]  # 00,01,02 = 첫 3h 구간

    assert first["open"] == src["open"].iloc[0]
    assert first["high"] == src["high"].max()
    assert first["low"] == src["low"].min()
    assert first["close"] == src["close"].iloc[-1]
    assert first["volume"] == src["volume"].sum()


def test_misaligned_start_still_snaps_to_grid():
    # 01:00 시작 -> 첫 캔들은 00:00 라벨의 부분 캔들(01,02)이지만 경계는 여전히 00/03/06
    df = _make_1h("2024-01-01 01:00", 47)
    out = resample_timeframe(df, "3h")
    assert not out.empty
    assert all(ts.hour % 3 == 0 for ts in out.index)
    # 첫 라벨은 00:00 (origin=epoch 격자), 부분 캔들은 01,02 1h봉만 포함
    first_ts = pd.Timestamp("2024-01-01 00:00")
    assert first_ts in out.index
    src = df.loc["2024-01-01 01:00":"2024-01-01 02:00"]
    assert out.loc[first_ts, "open"] == src["open"].iloc[0]
    assert out.loc[first_ts, "close"] == src["close"].iloc[-1]


def test_2d_resample_unchanged():
    # 2d/4d/2w 동작은 절대 변경 금지: label/closed=right, origin=start
    idx = pd.date_range("2024-01-01", periods=10, freq="1D")
    df = pd.DataFrame(
        {
            "open": range(10),
            "high": [x + 1 for x in range(10)],
            "low": [x - 1 for x in range(10)],
            "close": [x + 0.5 for x in range(10)],
            "volume": [1.0] * 10,
        },
        index=idx,
    ).astype(float)

    expected = df.resample("2D", label="right", closed="right", origin="start").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    out = resample_timeframe(df, "2d")
    pd.testing.assert_frame_equal(out, expected)


if __name__ == "__main__":
    test_boundaries_are_multiples_of_three()
    test_first_candle_ohlcv_aggregation()
    test_misaligned_start_still_snaps_to_grid()
    test_2d_resample_unchanged()
    print("ALL 3H RESAMPLE TESTS PASSED")
