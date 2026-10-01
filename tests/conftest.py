"""테스트 공용 — OHLCV 로컬 저장소(data/cache)를 테스트마다 임시 폴더로 돌린다 (SPEC §12).

data/binance.fetch_klines 가 저장소를 거치므로, 테스트가 작업 트리의 data/cache 에 쓰거나
앞 테스트의 저장본·st.cache_data 결과·저장소 상태를 물려받지 않게 한다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402


def _reset_fetch_state():
    binance = sys.modules.get("data.binance")
    if binance is None:             # 아직 임포트 전 — 비울 캐시가 없다
        return
    binance.fetch_klines.clear()
    binance.fetch_klines_paginated.clear()
    binance._STORE_STATUS.clear()


@pytest.fixture(autouse=True)
def _isolated_ohlcv_store(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.OHLCV_STORE_PARAMS, "dir", str(tmp_path / "ohlcv_cache"))
    _reset_fetch_state()
    yield
    _reset_fetch_state()
