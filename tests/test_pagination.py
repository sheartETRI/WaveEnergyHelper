"""fetch_klines_paginated 단위 테스트 (네트워크 없음)."""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import binance as binance_mod


def _kline(open_time, close=100.0):
    return [open_time, "1", "1", "1", str(close), "1", open_time + 3599999,
            "0", 0, "0", "0", "0"]


@patch.object(binance_mod, "time")
@patch.object(binance_mod, "_fetch_klines_page")
def test_three_page_merge_sort_dedup(mock_page, mock_time):
    mock_time.sleep = MagicMock()
    p1 = [_kline(3000), _kline(4000)]
    p2 = [_kline(1000), _kline(2000), _kline(3000)]
    p3 = [_kline(0), _kline(1000)]

    def side_effect(symbol, interval, limit, end_time=None):
        if end_time is None:
            return p1
        if end_time == p1[0][0] - 1:
            return p2
        if end_time == p2[0][0] - 1:
            return p3
        return []

    mock_page.side_effect = side_effect
    binance_mod.fetch_klines_paginated.clear()
    result = binance_mod.fetch_klines_paginated("ETHUSDT", "1h", 2500)

    opens = [r[0] for r in result]
    assert opens == [0, 1000, 2000, 3000, 4000]
    assert mock_page.call_count >= 3


@patch.object(binance_mod, "fetch_klines")
def test_total_limit_le_1000_delegates_to_fetch_klines(mock_single):
    mock_single.return_value = [_kline(0), _kline(1000)]
    binance_mod.fetch_klines_paginated.clear()
    result = binance_mod.fetch_klines_paginated("BTCUSDT", "4h", 500)
    mock_single.assert_called_once_with("BTCUSDT", "4h", 500)
    assert result == mock_single.return_value


@patch.object(binance_mod, "time")
@patch.object(binance_mod, "_fetch_klines_page")
def test_middle_page_failure_partial_with_warning(mock_page, mock_time, caplog):
    mock_time.sleep = MagicMock()
    first_page = [_kline(2000), _kline(3000)]

    def side_effect(symbol, interval, limit, end_time=None):
        if end_time is None:
            return first_page
        raise ConnectionError("network down")

    mock_page.side_effect = side_effect
    binance_mod.fetch_klines_paginated.clear()

    with caplog.at_level("WARNING", logger="data.binance"):
        result = binance_mod.fetch_klines_paginated("ETHUSDT", "4h", 2500)

    assert len(result) == 2
    assert result[0][0] == 2000
    assert any("partial" in r.message.lower() for r in caplog.records)


def test_merge_sort_dedup():
    rows = [_kline(3000), _kline(1000), _kline(2000), _kline(1000)]
    merged = binance_mod._merge_klines(rows, "1h")
    assert [r[0] for r in merged] == [1000, 2000, 3000]
