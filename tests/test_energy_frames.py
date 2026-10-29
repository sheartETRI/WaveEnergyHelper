"""4d 에너지 관측은 차트 그리드와 마감·연속성 계약을 함께 지킨다."""
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from data.processor import resample_timeframe
from display.energy_frames import prepare_energy_frames


def _daily(n=150, start="2024-01-01"):
    close = 100 + np.arange(n) * 0.1 + np.sin(np.arange(n) / 4)
    return pd.DataFrame({"open": close - 0.1, "high": close + 1,
                         "low": close - 1, "close": close, "volume": np.arange(n) + 1.0},
                        index=pd.date_range(start, periods=n, freq="1D", name="open_time"))


def _four(raw, asof="2030-01-01"):
    return prepare_energy_frames({"1d": raw}, asof)["4d"]


def _without_metadata(frame):
    frame = frame.copy()
    frame.attrs = {}
    return frame


def test_complete_groups_match_existing_chart_ohlcv_and_true_boundaries():
    raw = _daily()
    energy = _four(raw)
    chart = resample_timeframe(raw, "4d")
    labels = energy.attrs["energy_chart_labels"]
    actual = energy.loc[:, list(raw.columns)].copy()
    actual.index = labels
    assert_frame_equal(_without_metadata(actual), _without_metadata(chart.loc[labels]), check_names=False)
    assert energy.index[0] == pd.Timestamp("2024-01-02")
    assert labels[0] == pd.Timestamp("2024-01-05")
    assert energy.attrs["energy_bar_closes"][0] == pd.Timestamp("2024-01-06")
    assert "stoch_k_(20,10,10)" in energy and "MA10" in energy


def test_partial_first_and_last_groups_are_excluded():
    raw = _daily(11)
    energy = _four(raw)
    assert energy.attrs["energy_chart_labels"].tolist() == list(pd.to_datetime(["2024-01-05", "2024-01-09"]))
    assert energy.index.tolist() == list(pd.to_datetime(["2024-01-02", "2024-01-06"]))


def test_clock_alone_cannot_promote_cached_unfinished_daily_into_four_day_group():
    raw = _daily(5)
    before = _four(raw, "2024-01-05 12:00")
    after_clock_only = _four(raw, "2024-01-06 12:00")
    assert before.empty and after_clock_only.empty
    received_successor = _four(_daily(6), "2024-01-06 12:00")
    assert len(received_successor) == 1
    assert received_successor.attrs["energy_bar_closes"][0] == pd.Timestamp("2024-01-06")


def test_asof_filter_does_not_shift_original_grid():
    raw = _daily(100)
    first = _four(raw, "2024-02-01")
    later = _four(raw, "2024-02-07")
    assert first.attrs["energy_origin"] == later.attrs["energy_origin"] == raw.index[0]
    assert first.attrs["energy_chart_labels"].equals(later.attrs["energy_chart_labels"][:len(first)])
    assert (first.attrs["energy_bar_closes"] <= pd.Timestamp("2024-02-01")).all()


def test_missing_daily_is_deferred_instead_of_compressing_four_day_groups():
    raw = _daily().drop(pd.Timestamp("2024-02-01"))
    frames = prepare_energy_frames({"1d": raw}, "2030-01-01")
    assert frames["4d"].empty and "누락" in frames["4d"].attrs["energy_issue"]
    assert frames["1d"].empty and "누락" in frames["1d"].attrs["energy_issue"]


def test_nullable_or_nonfinite_daily_does_not_generate_synthetic_energy():
    for invalid in (np.nan, np.inf):
        raw = _daily()
        raw.loc[raw.index[20], "close"] = invalid
        energy = _four(raw)
        assert energy.empty and "비정상" in energy.attrs["energy_issue"]


def test_unfinished_daily_price_changes_cannot_change_any_closed_energy_value():
    raw = _daily()
    changed = raw.copy()
    changed.loc[changed.index[-1], ["high", "close"]] *= 10
    expected, actual = _four(raw), _four(changed)
    assert_frame_equal(_without_metadata(expected), _without_metadata(actual))
    assert expected.attrs["energy_chart_labels"].equals(actual.attrs["energy_chart_labels"])


def test_native_preserves_existing_closed_values_and_provides_close_metadata():
    from display.mtf_guidance import prepare_closed_frames

    raw = _daily(75)
    raw.index = pd.date_range("2024-01-01", periods=len(raw), freq="1h")
    expected = prepare_closed_frames({"1h": raw}, "2024-01-04 02:30")["1h"]
    actual = prepare_energy_frames({"1h": raw}, "2024-01-04 02:30")["1h"]
    assert_frame_equal(_without_metadata(expected), _without_metadata(actual))
    assert actual.attrs["energy_bar_closes"].equals(actual.index + pd.Timedelta(hours=1))
    assert actual.attrs["energy_issue"] == ""


def test_timezone_aware_source_maps_to_the_same_utc_grid_without_mutation():
    raw = _daily()
    aware = raw.copy()
    aware.index = aware.index.tz_localize("UTC").tz_convert("Asia/Seoul")
    actual, expected = _four(aware), _four(raw)
    assert_frame_equal(_without_metadata(actual), _without_metadata(expected))
    assert actual.index.tz is None
    assert aware.index.tz is not None


def test_invalid_times_and_absent_daily_provide_explicit_hold_metadata():
    raw = _daily()
    raw.index = raw.index.to_list()[::-1]
    energy = _four(raw)
    assert energy.empty and "시각" in energy.attrs["energy_issue"]
    energy = prepare_energy_frames({}, "2030-01-01")["4d"]
    assert energy.empty and "없음" in energy.attrs["energy_issue"]
