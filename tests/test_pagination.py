"""fetch_klines_paginated 단위 테스트 (네트워크 없음).

페이지네이션은 OHLCV 저장소(data/ohlcv_store.py)가 한다 — 여기서는 관측 가능한 계약만 본다:
총 봉 수, 오름차순·중복 없음, 최신 봉까지, ≤1000 위임, 중간 페이지 실패 시 부분 반환 + 경고.
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import binance as binance_mod
from data import ohlcv_store

H = 3_600_000


def _kline(open_time, close=100.0):
    return [open_time, "1", "1", "1", str(close), "1", open_time + 3599999,
            "0", 0, "0", "0", "0"]


def _exchange(n_bars, step=H):
    """바이낸스 /klines 규약 흉내: startTime 은 그 이후 첫 limit 봉, endTime 만 있으면 그 이전 최신 limit 봉."""
    bars = [_kline(i * step) for i in range(n_bars)]

    def page(symbol, interval, limit, start_time=None, end_time=None):
        rows = [r for r in bars
                if (start_time is None or r[0] >= start_time) and (end_time is None or r[0] <= end_time)]
        return rows[:limit] if start_time is not None else rows[-limit:]

    return page


@patch.object(binance_mod, "time")
@patch.object(binance_mod, "_fetch_klines_page")
def test_three_page_merge_sort_dedup(mock_page, mock_time):
    mock_time.sleep = MagicMock()
    exchange = _exchange(3500)

    def side_effect(symbol, interval, limit, start_time=None, end_time=None):
        rows = exchange(symbol, interval, limit, start_time, end_time)
        return list(reversed(rows)) + rows[:1]          # 역순 + 중복 행이 와도 결과는 정렬·중복 제거

    mock_page.side_effect = side_effect
    binance_mod.fetch_klines_paginated.clear()
    result = binance_mod.fetch_klines_paginated("ETHUSDT", "1h", 2500)

    opens = [r[0] for r in result]
    assert len(result) == 2500 and opens == sorted(set(opens))
    assert opens[-1] == 3499 * H                        # 최신 봉까지
    assert mock_page.call_count == 3                    # 빈 저장소 첫 적재: 1000 × 3 페이지


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
    exchange = _exchange(3500, step=4 * H)

    def side_effect(symbol, interval, limit, start_time=None, end_time=None):
        if start_time is None and end_time is None:
            return exchange(symbol, interval, limit)    # 최신 페이지는 성공
        raise ConnectionError("network down")

    mock_page.side_effect = side_effect
    binance_mod.fetch_klines_paginated.clear()

    with caplog.at_level("WARNING", logger="data.binance"):
        result = binance_mod.fetch_klines_paginated("ETHUSDT", "4h", 2500)

    assert len(result) == 1000                          # 진행분(최신 1000봉)만
    assert result[-1][0] == 3499 * 4 * H
    assert mock_page.call_count == 1 + 2                # 실패 페이지는 1회 재시도
    assert any("partial" in r.message.lower() for r in caplog.records)


def test_merge_sort_dedup():
    """병합은 저장소가 한다 — open_time 정렬·중복 제거, 같은 봉은 나중 것이 이긴다(미완성 봉 덮어쓰기)."""
    rows = [_kline(3000), _kline(1000), _kline(2000), _kline(1000, close=101.0)]
    merged = ohlcv_store.merge_rows([], rows)
    assert [r[0] for r in merged] == [1000, 2000, 3000] and merged[0][4] == "101.0"
