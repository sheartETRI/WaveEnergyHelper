"""페이지 렌더 스모크 — main.py 를 Streamlit AppTest 로 실제 실행해 알람 탭 "60MA 전환 추적" 표에 '다이버전스' 열과
있음/없음 코호트 집계 캡션이 **렌더 결과물**에 존재함을 단언한다(단위 테스트가 통과해도 화면에 없던 사례의 재발 방지).

네트워크는 data/binance.requests.get 을 합성 kline 으로 대체한다(모든 심볼·TF 동일 합성 시계열). 검증 대상은 렌더 트리이지
수치가 아니다.
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import data.binance as B  # noqa: E402
import display.divergence_flag as DV  # noqa: E402
import display.ma60_down_tracker as D  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

_STEP_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000, "M": 30 * 86_400_000}


# 검출 정의 개선(ee2ba79) 뒤 최근 120봉(1h) 안에 상승 후보 2건(있음 1·없음 1 — 대기 중 1·'해당 없음 (이미 상방)' 1)·하방 후보 1건('해당 없음 (이미 하방)')
# 이 들어오는 시드 — 표가 실제로 그려져야 검사가 성립. 후보 위치는 가격열만의 함수라 시각 정렬(지금 기준)과 무관하게 재현된다.
SEED = 49


def _synthetic_klines(interval: str, n: int, seed: int = SEED):
    """Binance kline 행 형식의 합성 시계열(계측 테스트와 같은 생성식) — 마지막 봉이 '지금' 진행 중."""
    step = int(interval[:-1]) * _STEP_MS[interval[-1]]
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 0.004, n) + 0.02 * np.sin(np.arange(n) / 37.0) * 0.004
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.003, n))
    now_ms = int(time.time() * 1000)
    first = now_ms - now_ms % step - (n - 1) * step
    rows = []
    for i in range(n):
        o = first + i * step
        rows.append([o, f"{open_[i]:.4f}", f"{high[i]:.4f}", f"{low[i]:.4f}", f"{close[i]:.4f}", "1.0",
                     o + step - 1, "0", 0, "0", "0", "0"])
    return rows


class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


@pytest.fixture
def app(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kw):
        params = params or {}
        return _Resp(_synthetic_klines(params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)))

    monkeypatch.setattr(B.requests, "get", fake_get)
    try:
        B.clear_klines_cache()
    except Exception:   # noqa: BLE001 — 캐시 없으면 무시
        pass
    at = AppTest.from_file(os.path.join(ROOT, "main.py"), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tracker_df(at):
    """렌더 트리의 st.dataframe 중 60MA 전환 추적 표(열 집합이 COLUMNS 와 같은 것)."""
    frames = [d.value for d in at.dataframe]
    hits = [f for f in frames if list(f.columns) == list(T.COLUMNS)]
    assert hits, f"60MA 전환 추적 표를 찾지 못함 — 렌더된 표 열 목록: {[list(f.columns) for f in frames]}"
    return hits[0]


def test_alarm_tab_tracker_table_renders_divergence_column_and_cohort_caption(app):
    df = _tracker_df(app)
    assert DV.DIVERGENCE_COL in df.columns and list(df.columns).index(DV.DIVERGENCE_COL) == list(T.COLUMNS).index(DV.DIVERGENCE_COL)
    assert len(df) >= 2 and set(df[DV.DIVERGENCE_COL]) == {DV.YES, DV.NO}      # 두 값 모두 화면에 있음
    captions = [c.value for c in app.caption]
    cohort = [c for c in captions if c.startswith(f"{DV.DIVERGENCE_COL} 있음: 전환 ")]
    assert len(cohort) == 1 and cohort[0].endswith("(미검증, 표본 적음)"), captions
    # 집계 줄은 표 아래(최근 120봉 집계 줄 바로 다음)에 있다
    summary_idx = next(i for i, c in enumerate(captions) if c.startswith("최근 120봉: 전환 "))
    assert captions[summary_idx + 1] == cohort[0]
    # 하방 추적 표는 열이 없다(변경 없음)
    down = [d.value for d in app.dataframe if list(d.value.columns) == list(D.COLUMNS)]
    assert down and DV.DIVERGENCE_COL not in down[0].columns
    # '확정 시 이미 상방/하방' 상태 분리(908b71c)가 렌더 결과물에 있다: 표 상태 문구 + 5번째 메트릭(건수)
    assert T.STATUS_ALREADY_UP in set(df["상태"]) and D.STATUS_ALREADY_DOWN in set(down[0]["상태"])
    labels = [m.label for m in app.metric]
    assert f"{T.ALREADY_UP_MARK} {T.UNVERIFIED}" in labels and f"{D.ALREADY_DOWN_MARK} {D.UNVERIFIED}" in labels


def test_tracker_table_matches_direct_computation_on_same_frame(app):
    """렌더된 표의 다이버전스 값 = 같은 합성 프레임에서 track_candidates 가 낸 값(렌더 경로에서 열이 빠지거나 바뀌지 않음)."""
    from data.processor import build_dataframe
    from indicators.moving_averages import add_moving_averages
    from indicators.stochastic import add_stochastic_slow_layers

    raw = _synthetic_klines("1h", 1000)
    frame = add_stochastic_slow_layers(add_moving_averages(build_dataframe(raw)))
    expected = T.display_frame(T.track_candidates(frame, recent_bars=T.RECENT_BARS), "BTCUSDT", "1h")
    got = _tracker_df(app)
    assert list(got[DV.DIVERGENCE_COL]) == list(expected[DV.DIVERGENCE_COL])
    assert list(got["확정 시각"]) == list(expected["확정 시각"])
    assert list(got["상태"]) == list(expected["상태"])                      # 상태 분리(해당 없음)도 렌더 경로에서 그대로
