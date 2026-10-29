"""HT1의 장기 기준·하위 움직임·마감 계약을 검증한다."""
import numpy as np
import pandas as pd
import pytest

from analysis.trend_context import build_trend_context, classify_trend_move


ASOF = pd.Timestamp("2026-10-29 12:00")


def _frame(interval, direction="up", n=None, last_close=None):
    period, step = (10, pd.Timedelta(days=4)) if interval == "4d" else (60, pd.Timedelta(days=1))
    n = n or period + 5
    last_close = pd.Timestamp(last_close or "2026-10-29")
    closes = pd.date_range(end=last_close, periods=n, freq=step)
    values = np.arange(100, 100+n, dtype=float)
    if direction == "down":
        values = values[::-1].copy()
    elif direction == "flat":
        values[:] = 100
    frame = pd.DataFrame({"close": values}, index=closes-step)
    frame.attrs["energy_bar_closes"] = closes
    frame.attrs["energy_chart_labels"] = frame.index + (pd.Timedelta(days=3) if interval == "4d" else pd.Timedelta(0))
    frame.attrs["energy_issue"] = ""
    if interval == "4d":
        frame.attrs["energy_origin"] = frame.index[0] - pd.Timedelta(days=1)
    return frame


def _context(primary="down", reference="down"):
    return build_trend_context({"4d": _frame("4d", primary), "1d": _frame("1d", reference)}, ASOF)


def test_downward_primary_and_reference_classify_hourly_rise_as_countertrend_rally():
    ctx = _context()
    assert ctx["version"] == "HT1" and ctx["status"] == "ALIGNED" and ctx["direction"] == "down"
    assert ctx["primary"]["interval"] == "4d" and ctx["primary"]["period"] == 10
    assert ctx["reference"]["interval"] == "1d" and ctx["reference"]["period"] == 60
    assert classify_trend_move("1h", "up", ctx)["code"] == "COUNTER_RALLY"
    assert classify_trend_move("4h", "down", ctx)["code"] == "WITH_TREND"


def test_upward_consensus_classifies_hourly_fall_as_a_pullback():
    ctx = _context("up", "up")
    assert classify_trend_move("12h", "down", ctx)["code"] == "COUNTER_PULLBACK"
    assert classify_trend_move("1h", "up", ctx)["code"] == "WITH_TREND"


def test_opposed_reference_directions_are_a_conflict_not_a_new_trend():
    ctx = _context("down", "up")
    assert ctx["status"] == "CONFLICT" and ctx["direction"] == "unknown"
    assert ctx["primary"]["direction"] == "down" and ctx["reference"]["direction"] == "up"
    assert classify_trend_move("1h", "up", ctx)["code"] == "CONFLICT"


def test_flat_reference_or_local_direction_defers_a_strong_interpretation():
    flat = _context("flat", "down")
    assert flat["status"] == "FLAT" and flat["direction"] == "unknown"
    assert classify_trend_move("1h", "down", flat)["code"] == "HOLD"
    for direction in ("flat", "unknown"):
        assert classify_trend_move("1h", direction, _context())["code"] == "HOLD"


def test_ma_direction_and_price_position_are_independent_observations():
    four = _frame("4d", n=11)
    four["close"] = [100] + [130]*9 + [110]
    ctx = build_trend_context({"4d": four, "1d": _frame("1d")}, ASOF)
    point = ctx["primary"]
    assert point["direction"] == "up" and point["ma_delta"] == 1
    assert point["price_position"] == "below" and point["close_price"] == 110
    assert point["ma_value"] == 128


@pytest.mark.parametrize("interval,field", [("4d", "primary"), ("1d", "reference")])
def test_constant_decimal_prices_are_equal_to_their_mean_without_roundoff_bias(interval, field):
    frame = _frame(interval)
    frame["close"] = 10.1
    point = build_trend_context({interval: frame}, ASOF)[field]
    assert point["direction"] == "flat" and point["price_position"] == "equal"
    assert point["ma_value"] == 10.1


def test_missing_one_or_both_references_never_claims_an_agreed_trend():
    partial = build_trend_context({"4d": _frame("4d")}, ASOF)
    assert partial["status"] == "PARTIAL" and partial["direction"] == "unknown"
    assert classify_trend_move("1h", "up", partial)["code"] == "HOLD"
    absent = build_trend_context({}, ASOF)
    assert absent["status"] == "UNAVAILABLE" and absent["next_check_at"] is None


def test_earlier_four_day_close_is_normal_until_its_next_close_and_daily_expires_first():
    ctx = build_trend_context({"4d": _frame("4d", last_close="2026-10-26"), "1d": _frame("1d")}, ASOF)
    assert ctx["status"] == "ALIGNED"
    assert ctx["primary"]["last_close"] == pd.Timestamp("2026-10-26")
    assert ctx["primary"]["next_close"] == pd.Timestamp("2026-10-30")
    assert ctx["next_check_at"] == pd.Timestamp("2026-10-30")


def test_next_check_uses_daily_update_even_if_four_day_or_local_candle_is_later():
    ctx = _context()
    assert ctx["primary"]["next_close"] == pd.Timestamp("2026-11-02")
    assert ctx["reference"]["next_close"] == pd.Timestamp("2026-10-30")
    assert ctx["next_check_at"] == pd.Timestamp("2026-10-30")


@pytest.mark.parametrize("interval,close", [("4d", "2026-10-25"), ("1d", "2026-10-28")])
def test_stale_reference_is_deferred_at_the_next_expected_close(interval, close):
    frames = {"4d": _frame("4d"), "1d": _frame("1d")}
    frames[interval] = _frame(interval, last_close=close)
    ctx = build_trend_context(frames, ASOF)
    point = ctx["primary"] if interval == "4d" else ctx["reference"]
    assert point["issue"] == "STALE" and point["direction"] == "unknown"
    assert ctx["status"] == "PARTIAL"


def test_future_bar_is_not_accepted_even_when_the_other_reference_is_valid():
    ctx = build_trend_context({"4d": _frame("4d", last_close="2026-10-30"), "1d": _frame("1d")}, ASOF)
    assert ctx["primary"]["issue"] == "UNCONFIRMED_BAR" and ctx["status"] == "PARTIAL"


@pytest.mark.parametrize("damage,expected", [
    ("metadata", "MISSING_CLOSE_METADATA"), ("close_metadata", "INVALID_CLOSE_METADATA"),
    ("gap", "MISSING_BARS"), ("nan", "NONFINITE_CLOSE"), ("order", "INVALID_INDEX"),
    ("short", "INSUFFICIENT_BARS"), ("upstream", "UPSTREAM_ISSUE"),
])
def test_invalid_reference_data_is_not_silently_used(damage, expected):
    frame = _frame("4d")
    if damage == "metadata":
        frame.attrs.pop("energy_bar_closes")
    elif damage == "close_metadata":
        frame.attrs["energy_bar_closes"] = frame.attrs["energy_bar_closes"] + pd.Timedelta(hours=1)
    elif damage == "gap":
        pos = 7
        frame = frame.drop(frame.index[pos])
        frame.attrs["energy_bar_closes"] = frame.attrs["energy_bar_closes"].delete(pos)
        frame.attrs["energy_chart_labels"] = frame.attrs["energy_chart_labels"].delete(pos)
    elif damage == "nan":
        frame.iloc[-4, 0] = np.nan
    elif damage == "order":
        frame = frame.iloc[::-1]
    elif damage == "short":
        frame = _frame("4d", n=10)
    elif damage == "upstream":
        frame.attrs["energy_issue"] = "source gap"
    ctx = build_trend_context({"4d": frame, "1d": _frame("1d")}, ASOF)
    assert ctx["primary"]["issue"] == expected and ctx["status"] == "PARTIAL"


@pytest.mark.parametrize("interval,period", [("4d", 10), ("1w", 10), ("1M", 10), ("1d", 60), ("1h", 960)])
def test_reference_or_longer_observation_is_not_labeled_as_a_lower_timeframe_move(interval, period):
    assert classify_trend_move(interval, "up", _context(), period)["code"] == "REFERENCE_OR_HIGHER"


def test_snapshot_ignores_price_levels_and_scan_clock_but_preserves_direction_and_grid():
    frames = {"4d": _frame("4d"), "1d": _frame("1d")}
    first = build_trend_context(frames, ASOF)
    for frame in frames.values():
        frame["close"] += 200
    second = build_trend_context(frames, ASOF + pd.Timedelta(hours=1))
    assert first["snapshot"] == second["snapshot"]
    frames["4d"].attrs["energy_origin"] += pd.Timedelta(days=1)
    third = build_trend_context(frames, ASOF)
    assert second["snapshot"] != third["snapshot"]


def test_four_day_ma10_has_different_value_from_daily_ma40_but_aligned_change_has_same_sign():
    closes = pd.Series(range(1, 45), dtype=float)
    four_day = closes.iloc[3::4]
    assert closes.iloc[:40].mean() == 20.5 and four_day.iloc[:10].mean() == 22
    delta_four = four_day.iloc[-10:].mean() - four_day.iloc[-11:-1].mean()
    delta_daily = closes.iloc[-40:].mean() - closes.iloc[-41:-1].mean()
    assert delta_four == 4 and delta_daily == 1
    assert delta_four > 0 and delta_daily > 0


def test_aware_asof_is_the_same_utc_instant_and_does_not_mutate_inputs():
    frames = {"4d": _frame("4d"), "1d": _frame("1d")}
    original = frames["4d"].copy()
    aware = build_trend_context(frames, "2026-10-29T21:00:00+09:00")
    normal = build_trend_context(frames, ASOF)
    assert aware == normal
    pd.testing.assert_frame_equal(frames["4d"], original)


@pytest.mark.parametrize("interval,period", [("bad", 10), ("0h", 10), ("1h", 0), ("1h", "10")])
def test_invalid_local_scope_is_held(interval, period):
    assert classify_trend_move(interval, "up", _context(), period)["code"] == "HOLD"
