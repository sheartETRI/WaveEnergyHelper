"""1h 로딩 회귀 — API 비정상 응답·실데이터 fetch.

실행: python -m pytest tests/test_fetch_1h.py
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import binance as binance_mod
from data.processor import build_dataframe, get_fetch_interval
from analysis.wave_energy import _load_frame


def test_get_fetch_interval_1h_is_native():
    """1h는 커스텀 베이스(3h용)로 오분기되지 않고 네이티브 1h fetch."""
    assert get_fetch_interval("1h") == "1h"


def test_build_dataframe_rejects_api_error_dict():
    """Binance 오류 JSON(dict) → None (빈 DataFrame 생성 방지)."""
    assert build_dataframe({"code": -1121, "msg": "Invalid symbol."}) is None


@patch.object(binance_mod, "requests")
def test_fetch_klines_rejects_non_list_json(mock_requests):
    """HTTP 200이어도 list가 아니면 None."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"code": -1003, "msg": "Too many requests"}
    mock_requests.get.return_value = resp
    binance_mod.fetch_klines.clear()
    assert binance_mod.fetch_klines("BTCUSDT", "1h", 100) is None


def test_load_frame_btcusdt_1h_live():
    """실 API: BTCUSDT 1h _load_frame 성공."""
    df = _load_frame("BTCUSDT", "1h")
    assert df is not None and not df.empty
    assert len(df) >= 240
