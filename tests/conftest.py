"""테스트 공용 — OHLCV 로컬 저장소를 실제 data/cache 가 아닌 임시 폴더로 돌린다 (SPEC §12).

data/binance.fetch_klines 가 저장소를 거치므로, 테스트가 작업 트리의 data/cache 에 쓰거나
앞 테스트의 저장본·st.cache_data 결과·저장소 상태를 물려받지 않게 한다.

  · 임포트 시점  WEH_OHLCV_STORE_DIR = 세션 임시 폴더 — 수집 단계·서브프로세스까지 적용 (2026-10-02 오염 사고 재발 방지)
  · 테스트마다   같은 환경변수(+ settings 의 dir)를 그 테스트의 tmp_path 로 — 테스트끼리 저장본을 나누지 않는다
  · 트립와이어   그래도 실제 data/cache 에 쓰려 하면 data/ohlcv_store.save_rows 가 RuntimeError
"""
import atexit
import os
import shutil
import sys
import tempfile

# 다른 무엇보다 먼저 — 이 프로세스와 자식 프로세스의 저장 경로를 세션 임시 폴더로 (기존 값이 있어도 덮는다).
_SESSION_STORE = tempfile.mkdtemp(prefix="weh_ohlcv_store_")
os.environ["WEH_OHLCV_STORE_DIR"] = _SESSION_STORE
atexit.register(shutil.rmtree, _SESSION_STORE, ignore_errors=True)

import pytest  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from data.ohlcv_store import STORE_DIR_ENV  # noqa: E402


def _reset_fetch_state():
    binance = sys.modules.get("data.binance")
    if binance is None:             # 아직 임포트 전 — 비울 캐시가 없다
        return
    binance.fetch_klines.clear()
    binance.fetch_klines_paginated.clear()
    binance._STORE_STATUS.clear()


@pytest.fixture(autouse=True)
def _isolated_ohlcv_store(tmp_path, monkeypatch):
    store_dir = str(tmp_path / "ohlcv_cache")
    monkeypatch.setenv(STORE_DIR_ENV, store_dir)                        # 경로 해석 최우선 — 자식 프로세스도 이것
    monkeypatch.setitem(settings.OHLCV_STORE_PARAMS, "dir", store_dir)  # 환경변수를 지운 테스트도 임시 폴더
    _reset_fetch_state()
    yield
    _reset_fetch_state()
