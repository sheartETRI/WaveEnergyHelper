"""화면 캐시가 계산 결과·입력 변경·반환값 격리를 보존하는지 검증한다."""
import pandas as pd
import pytest

from display import analysis_cache as cache
from tracking import ma60_down, ma60_turn, structure


@pytest.fixture(autouse=True)
def isolated_cache():
    cache.clear_analysis_cache()
    yield
    cache.clear_analysis_cache()


def _frame():
    return pd.DataFrame({"open": [1., 2., 3.], "high": [2., 3., 4.], "low": [0., 1., 2.],
                         "close": [1., 2., 3.], "MA60": [1., 1.5, 2.],
                         "rsi": [30., 40., 50.], "macd": [0., 1., 2.]},
                        index=pd.date_range("2024-01-01", periods=3, freq="h"))


def test_cache_reuses_only_equivalent_tracking_input_and_returns_copies(monkeypatch):
    calls = []
    def compute(frame, recent_bars):
        calls.append((frame.copy(), recent_bars))
        return pd.DataFrame({"value": [float(frame.close.sum())]})
    monkeypatch.setattr(ma60_turn, "track_candidates", compute)
    frame = _frame()
    first = cache.upward_candidates(frame)
    first.iloc[0, 0] = -100
    pd.testing.assert_frame_equal(cache.upward_candidates(frame), pd.DataFrame({"value": [6.]}))
    irrelevant = frame.assign(rsi=90., macd=-50.)
    cache.upward_candidates(irrelevant.drop(columns="macd").reindex(columns=list(reversed(irrelevant.drop(columns="macd").columns))))
    assert len(calls) == 1
    changed = frame.copy()
    changed.iloc[0, changed.columns.get_loc("close")] = 20.
    assert cache.upward_candidates(changed).iloc[0, 0] == 25.
    assert len(calls) == 2  # 마지막 봉이 같아도 과거 봉 수정은 반영
    cache.upward_candidates(frame, recent_bars=50)
    assert len(calls) == 3
    shifted = frame.copy()
    shifted.index += pd.Timedelta(hours=1)
    cache.upward_candidates(shifted)
    assert len(calls) == 4


def test_cached_outputs_match_original_tracking_on_real_pipeline():
    from test_ma60_down_tracker import _pipeline, _raw
    frame = _pipeline(_raw(n=700, seed=49))
    before = frame.copy(deep=True)
    pd.testing.assert_frame_equal(cache.upward_candidates(frame), ma60_turn.track_candidates(frame))
    pd.testing.assert_frame_equal(cache.downward_candidates(frame), ma60_down.track_candidates(frame))
    assert cache.structure_analysis(frame) == structure.analyze(frame)
    pd.testing.assert_frame_equal(frame, before)
