"""TP1 변곡 준비의 기울기·선 위치·실제 교차 시각과 마감 계약."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from analysis.trend_context import _observation
from analysis.trend_turning import build_turning_context
from config.settings import MACD_PARAMS


_STEP = pd.Timedelta(days=4)
_BASE = list(np.arange(100., 180., 2)) + [175, 174, 173, 172, 171]


def _frame(values=None):
    values = _BASE if values is None else values
    closes = pd.date_range(start="2026-01-05", periods=len(values), freq="4D")
    frame = pd.DataFrame({"close": values}, index=closes - _STEP)
    frame.attrs["energy_bar_closes"] = closes
    frame.attrs["energy_issue"] = ""
    return frame


def _primary(frame):
    at = frame.attrs["energy_bar_closes"][-1] + pd.Timedelta(hours=1)
    if at.tzinfo is not None:
        at = at.tz_convert("UTC").tz_localize(None)
    return _observation(frame, "4d", 10, at)


def _run(values=None):
    frame = _frame(values)
    return build_turning_context(frame, _primary(frame))


def _prefix(frame, count):
    result = frame.iloc[:count].copy()
    result.attrs["energy_bar_closes"] = frame.attrs["energy_bar_closes"][:count]
    return result


def test_upward_ma10_can_prepare_a_bearish_turn_without_changing_its_direction():
    frame = _frame()
    primary = _primary(frame)
    result = build_turning_context(frame, primary)
    assert result["version"] == "TP1" and result["state"] == "BEARISH_PREP"
    assert result["issue"] == ""
    assert primary["direction"] == "up"
    assert result["ma10_delta"] == .3 and result["ma10_prev_delta"] == .6
    assert result["ma10_slowing"] is True
    assert result["ma_relation"] == result["macd_relation"] == "below"
    assert result["ma5_value"] == 173 and result["ma10_value"] == 173.5


def test_dead_crosses_on_different_bars_combine_and_use_actual_close_times():
    frame = _frame()
    result = build_turning_context(frame, _primary(frame))
    closes = frame.attrs["energy_bar_closes"]
    assert result["ma_cross"] == {"kind": "dead", "time": closes[-1], "bars_ago": 0}
    assert result["macd_cross"] == {"kind": "dead", "time": closes[-4], "bars_ago": 3}
    assert result["ma_cross"]["time"] != frame.index[-1]


def test_same_bar_dead_crosses_are_also_recognized():
    values = [98.88, 99.58, 102.8, 102.96, 106.29, 107.64, 107.94, 108.47, 102.94, 106.28,
              108.59, 110.22, 111.24, 108.6, 109.25, 106.89, 105.56, 102.36, 101.59, 105.05,
              106.72, 104.26, 101.94, 105.54, 105.11, 108.02, 113.32, 116.69, 113.78, 107.24,
              112.36, 108.52, 104.51, 103.14, 102.36, 104.43, 102.65, 100.24, 103.05, 100.42,
              108.9, 104.96, 105.45, 109.27, 109.64, 105.03, 105.23, 108.79, 106.9, 102.3]
    result = _run(values)
    assert result["state"] == "BEARISH_PREP"
    assert result["ma_cross"]["kind"] == result["macd_cross"]["kind"] == "dead"
    assert result["ma_cross"]["bars_ago"] == result["macd_cross"]["bars_ago"] == 0


def test_existing_below_alignment_does_not_repeat_a_new_dead_cross():
    first, later = _run(), _run(_BASE + [171])
    assert later["state"] == "BEARISH_PREP"
    assert later["ma_cross"]["time"] == first["ma_cross"]["time"]
    assert later["macd_cross"]["time"] == first["macd_cross"]["time"]
    assert later["ma_cross"]["bars_ago"] == 1
    assert later["macd_cross"]["bars_ago"] == 4
    assert later["snapshot"] == first["snapshot"]


def test_reacceleration_keeps_downside_evidence_but_clears_the_preparation_state():
    result = _run(_BASE + [174])
    assert result["ma10_delta"] > result["ma10_prev_delta"] > 0
    assert result["ma10_slowing"] is False
    assert result["ma_relation"] == result["macd_relation"] == "below"
    assert result["state"] == "DOWNSIDE_EVIDENCE"


def test_golden_recrosses_clear_bearish_preparation_and_replace_prior_events():
    result = _run(_BASE + [200])
    assert result["state"] == "NO_PREP"
    assert result["ma_relation"] == result["macd_relation"] == "above"
    assert result["ma_cross"]["kind"] == result["macd_cross"]["kind"] == "golden"
    assert result["ma_cross"]["bars_ago"] == result["macd_cross"]["bars_ago"] == 0


@pytest.mark.parametrize("tail,state", [([160], "MA10_DOWN"), ([170], "NO_PREP")])
def test_actual_downturn_and_flat_slope_are_separate_from_upward_preparation(tail, state):
    result = _run(_BASE + tail)
    assert result["state"] == state and result["ma10_slowing"] is False
    assert result["ma10_delta"] < 0 if state == "MA10_DOWN" else result["ma10_delta"] == 0


def test_slowing_with_only_one_below_relationship_is_partial_evidence():
    result = _run(_BASE[:-1])
    assert result["state"] == "SLOWING" and result["ma10_slowing"] is True
    assert result["ma_relation"] == "above" and result["macd_relation"] == "below"


def test_constant_decimal_values_do_not_create_crosses_from_roundoff():
    result = _run([10.1] * 45)
    assert result["state"] == "NO_PREP"
    assert result["ma_relation"] == result["macd_relation"] == "equal"
    assert result["ma_cross"] is result["macd_cross"] is None
    assert result["ma10_delta"] == result["ma10_prev_delta"] == 0


@pytest.mark.parametrize("last,kind", [(110., "golden"), (90., "dead")])
def test_a_cross_can_leave_equality_but_must_finish_strictly_on_one_side(last, kind):
    result = _run([100.] * 40 + [last])
    assert result["ma_cross"]["kind"] == result["macd_cross"]["kind"] == kind
    assert result["ma_cross"]["bars_ago"] == result["macd_cross"]["bars_ago"] == 0
    equal = _run([100.] * 40 + [90., 110.])
    assert equal["ma_relation"] == "equal"
    assert equal["ma_cross"]["kind"] == "dead" and equal["ma_cross"]["bars_ago"] == 1


def test_existing_indicator_columns_are_ignored_and_inputs_are_not_mutated():
    frame = _frame()
    frame["ma_5"], frame["ma_10"], frame["macd"], frame["macd_signal"] = 999., -999., 99., -99.
    original = deepcopy(frame)
    result = build_turning_context(frame, _primary(frame))
    assert result == _run()
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_index_equal(frame.attrs["energy_bar_closes"], original.attrs["energy_bar_closes"])
    assert frame.attrs["energy_issue"] == original.attrs["energy_issue"]


def test_macd_matches_existing_chart_formula_and_config():
    frame = _frame()
    result = build_turning_context(frame, _primary(frame))
    close = frame["close"]
    macd = close.ewm(span=MACD_PARAMS["fast"], adjust=False).mean() - close.ewm(span=MACD_PARAMS["slow"], adjust=False).mean()
    signal = macd.ewm(span=MACD_PARAMS["signal"], adjust=False).mean()
    assert result["macd_value"] == macd.iloc[-1]
    assert result["signal_value"] == signal.iloc[-1]
    assert result["macd_basis"] == "closed_only" and result["minimum_bars"] == 35


def test_chart_partial_bar_seeds_ema_without_counting_as_an_observation():
    frame = _frame()
    first_close = frame.attrs["energy_bar_closes"][0]
    frame.attrs["energy_macd_seed"] = {"close": 50., "close_time": first_close - _STEP}
    result = build_turning_context(frame, _primary(frame))
    series = pd.Series([50.] + frame["close"].tolist())
    macd = series.ewm(span=12, adjust=False).mean() - series.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    assert result["macd_basis"] == "chart_seed"
    assert result["macd_value"] == macd.iloc[-1] and result["signal_value"] == signal.iloc[-1]
    assert result["last_close"] == frame.attrs["energy_bar_closes"][-1]
    short = _prefix(frame, 34)
    assert build_turning_context(short, _primary(short))["issue"] == "INSUFFICIENT_BARS"


@pytest.mark.parametrize("seed", [{}, {"close": float("nan"), "close_time": "2026-01-01"},
                                  {"close": 100, "close_time": "2026-01-02"}, "bad"])
def test_invalid_chart_ema_seed_defers_instead_of_silently_changing_basis(seed):
    frame = _frame()
    frame.attrs["energy_macd_seed"] = seed
    result = build_turning_context(frame, _primary(frame))
    assert result["state"] == "HOLD" and result["issue"] == "INVALID_MACD_SEED"


def test_less_than_35_complete_bars_holds_and_initialization_cross_is_not_dated():
    assert _run(list(range(100, 134)))["issue"] == "INSUFFICIENT_BARS"
    result = _run(list(range(100, 135)))
    assert result["issue"] == "" and result["macd_relation"] == "above"
    assert result["macd_cross"] is None


@pytest.mark.parametrize("issue", ["STALE", "UNCONFIRMED_BAR", "UPSTREAM_ISSUE"])
def test_primary_hold_prevents_using_unconfirmed_or_expired_values(issue):
    frame = _frame()
    primary = _primary(frame)
    primary["issue"] = issue
    result = build_turning_context(frame, primary)
    assert result["state"] == "HOLD" and result["issue"] == issue
    assert result["macd_value"] is None and result["ma10_slowing"] is None


@pytest.mark.parametrize("damage,issue", [("nan", "NONFINITE_CLOSE"), ("gap", "MISSING_BARS"),
                                          ("metadata", "MISSING_CLOSE_METADATA"), ("offset", "INVALID_CLOSE_METADATA"),
                                          ("mismatch", "PRIMARY_FRAME_MISMATCH")])
def test_entire_ema_history_and_actual_close_metadata_must_be_valid(damage, issue):
    frame = _frame()
    primary = _primary(frame)
    if damage == "nan":
        frame.iloc[1, 0] = float("nan")  # HT1 최근 11봉 밖이어도 EMA에는 영향
    elif damage == "gap":
        frame = frame.drop(frame.index[1])
        frame.attrs["energy_bar_closes"] = frame.attrs["energy_bar_closes"].delete(1)
    elif damage == "metadata":
        frame.attrs.pop("energy_bar_closes")
    elif damage == "offset":
        frame.attrs["energy_bar_closes"] += pd.Timedelta(hours=1)
    else:
        primary["last_close"] += pd.Timedelta(days=4)
    result = build_turning_context(frame, primary)
    assert result["state"] == "HOLD" and result["issue"] == issue


def test_prefixes_do_not_anticipate_future_crosses_or_rewrite_saved_evidence():
    frame = _frame(_BASE + [200])
    before_ma_cross = _prefix(frame, len(_BASE) - 1)
    before = build_turning_context(before_ma_cross, _primary(before_ma_cross))
    assert before["state"] == "SLOWING" and before["ma_cross"] is None
    saved = deepcopy(before)
    for count in range(35, len(frame) + 1):
        prefix = _prefix(frame, count)
        result = build_turning_context(prefix, _primary(prefix))
        for cross in (result["ma_cross"], result["macd_cross"]):
            assert cross is None or cross["time"] <= prefix.attrs["energy_bar_closes"][-1]
        close = prefix["close"]
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        assert result["macd_value"] == macd.iloc[-1]
    assert before == saved
    assert build_turning_context(before_ma_cross, _primary(before_ma_cross)) == saved


def test_snapshot_ignores_level_changes_but_tracks_new_crosses_and_preparation():
    first = _run()
    translated = _run([value + 200 for value in _BASE])
    assert first["snapshot"] == translated["snapshot"]
    assert first["ma5_value"] != translated["ma5_value"]
    assert _run(_BASE + [200])["snapshot"] != first["snapshot"]


def test_aware_utc_metadata_preserves_the_same_instants():
    frame = _frame()
    baseline = build_turning_context(frame, _primary(frame))
    frame.index = frame.index.tz_localize("UTC").tz_convert("Asia/Seoul")
    frame.attrs["energy_bar_closes"] = frame.attrs["energy_bar_closes"].tz_localize("UTC").tz_convert("Asia/Seoul")
    assert build_turning_context(frame, _primary(frame)) == baseline
