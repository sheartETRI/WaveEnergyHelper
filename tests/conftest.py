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
from pathlib import Path  # noqa: E402

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


# 이름이 아니라 현재 실행 경로를 기준으로 관리하는 운영 검사 목록.
RUNTIME_FILES = set("""
test_alarm_cli test_alarm_signals test_alarm_tab_layout test_analysis_cache test_app_lazy_tabs test_binance_fallback
test_binance_store_wiring test_code_version test_core_ma
test_divergence_flag test_fetch_1h test_frame_loading test_lw_builder test_lw_crosshair test_lw_gate_context
test_lw_structure_markers test_lw_time_format test_ma60_down_tracker test_ma60_slope
test_ma60_turn_tracker test_ma_patterns test_notify_port test_ohlcv_store test_pagination
test_page_render_smoke test_pattern_candidate test_push_alarms test_push_daily_summary
test_refresh_button test_resample_3h test_rsi_wilder test_slim_app_smoke
test_stoch_double_width test_stoch_kind test_sweep_alarm_rows test_sweep_confluence
test_sweep_reclaim test_tf_radar test_trend_structure test_triple_patterns test_tz_label
test_wave_basis_radar test_tracking_extraction test_refactor_provenance test_chart_browser
""".split())

NETWORK_TESTS = {
    "test_dispersion_annotation.py::test_zone_hit_set_unchanged_with_annotation",
    "test_pattern_clean.py::test_zone_hit_snapshot_unchanged",
    "test_wave_forward_observation.py::test_full_summary_runs",
    "test_wave_grade_failure.py::test_funnel_calculation",
    "test_wave_grade_failure.py::test_path_analysis",
    "test_wave_grade_post_event.py::test_grade_a_event_extraction",
    "test_completion_event_parity.py::test_z2_f6_5cb_cross_matches_engine_hits",
    "test_radar_display.py::test_gt_hit_snapshot_unchanged",
    "test_fetch_1h.py::test_load_frame_btcusdt_1h_live",
    "test_verdict_asof.py::test_sweep_bar_matches_isolated_asof_recompute",
    "test_panel_smoke.py::test_context_panels_render_fast",
    "test_panel_smoke.py::test_precomputed_panels_render_slow",
}


def pytest_addoption(parser):
    parser.addoption("--suite", choices=("all", "runtime"), default="all",
                     help="runtime은 연구 테스트 모듈을 import하기 전에 수집에서 제외합니다.")


def pytest_ignore_collect(collection_path, config):
    return (config.getoption("--suite") == "runtime" and collection_path.name.startswith("test_")
            and collection_path.suffix == ".py" and collection_path.stem not in RUNTIME_FILES)


def pytest_collection_modifyitems(items):
    for item in items:
        path = Path(str(item.path))
        item.add_marker("runtime" if path.stem in RUNTIME_FILES else "research")
        if f"{path.name}::{item.originalname}" in NETWORK_TESTS:
            item.add_marker("network")
        if any(word in item.name for word in ("manifest", "origin_commit", "cherrypick", "fixed_doc")):
            item.add_marker("integrity")


@pytest.fixture(autouse=True)
def _offline_http(request, monkeypatch):
    """오프라인 검사에서 실제 전송이 발생하면 실패. Mock transport는 그대로 사용."""
    if request.node.get_closest_marker("network"):
        return
    import requests

    def reject(*args, **kwargs):
        pytest.fail("실제 HTTP 요청: network 마커를 지정하거나 transport를 mock 해야 합니다.")

    monkeypatch.setattr(requests.sessions.Session, "send", reject)
