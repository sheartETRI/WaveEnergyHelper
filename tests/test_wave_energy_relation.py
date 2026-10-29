"""대·소파동 관계의 구간 경계·인과성·실제 폭 비교 정의를 검사한다."""
import numpy as np
import pandas as pd
import pytest

from analysis.wave_energy_relation import analyze_energy_relation
from config.settings import WAVE_LAYER_ROLES
from indicators.moving_averages import add_moving_averages
from indicators.stochastic import add_stochastic_slow_layers, detect_stochastic_bottom_patterns


LARGE = WAVE_LAYER_ROLES["large"]
MID = WAVE_LAYER_ROLES["mid"]
SMALL = WAVE_LAYER_ROLES["small"]
# 첫 바닥은 넓고 둘째 바닥은 좁다. 기존 검출기는 17번에서 25를 초과해 확정한다.
BOTTOM = [50, 40, 30, 20, 10, 10, 10, 10, 10, 10, 20, 30, 40, 30, 22, 15, 20, 30, 40]


def _frame(small=BOTTOM, padding=12):
    n = padding + len(small)
    large = np.r_[np.linspace(30, 80, padding), np.linspace(79, 50, len(small))]
    return pd.DataFrame({
        "close": 200.0 - np.arange(n),
        f"stoch_k_{LARGE}": large,
        f"stoch_k_{MID}": large,
        f"stoch_k_{SMALL}": [50.0] * padding + list(small),
    }, index=pd.date_range("2026-01-01", periods=n, freq="1h"))


def _append(frame, large, small, close=None):
    result = frame.copy()
    result.loc[result.index[-1] + pd.Timedelta(hours=1)] = {
        "close": float(result["close"].iloc[-1] - 1) if close is None else close,
        f"stoch_k_{LARGE}": large, f"stoch_k_{MID}": large,
        f"stoch_k_{SMALL}": small,
    }
    return result


def test_falling_large_and_no_small_double_bottom_wait_for_reversal_evidence():
    frame = _frame([50, 40, 30, 15, 10, 12, 15])
    result = analyze_energy_relation(frame)
    assert result["state"] == "WAIT_SMALL"
    assert result["large_direction"] == result["ma10_direction"] == "down"
    assert result["leg_direction"] == "down" and result["leg_history_complete"]
    assert result["small_pattern"] == "db" and result["small_status"] == "waiting"
    assert result["alignment"] == "same"
    assert result["leg_start_pos"] == 11
    assert result["leg_start_time"] == frame.index[11]


def test_actual_width_detector_candidate_then_confirmation_without_pivot_lag():
    forming = _frame(BOTTOM[:16])
    result = analyze_energy_relation(forming)
    assert result["state"] == "SMALL_FORMING" and result["small_status"] == "forming"
    assert result["small_candidate_level"] == 25.0
    assert result["small_confirm_time"] is None

    confirmed = _frame(BOTTOM[:18])
    result = analyze_energy_relation(confirmed)
    assert result["state"] == "SMALL_CONFIRMED"
    assert result["small_status"] == "confirmed"
    assert result["small_confirm_pos"] == 12 + 17
    assert result["small_confirm_time"] == confirmed.index[-1]
    assert result["small_first_pos"] == 12 + 4
    assert result["small_candidate_level"] is None
    assert result["large_direction"] == "down"


def test_candidate_is_removed_when_second_bottom_becomes_too_wide():
    forming = _frame(BOTTOM[:16])
    assert analyze_energy_relation(forming)["small_status"] == "forming"
    rejected = _frame(BOTTOM[:16] + [15] * 15)
    result = analyze_energy_relation(rejected)
    assert result["state"] == "WAIT_SMALL"
    assert result["small_candidate_level"] is None
    assert result["small_status"] == "waiting"


def test_prefix_observation_is_not_rewritten_by_future_candidate_cancellation():
    original = _frame(BOTTOM[:16] + [15] * 15)
    prefix = original.iloc[:12 + 16].copy()
    before = prefix.copy(deep=True)
    result = analyze_energy_relation(prefix)
    assert result["state"] == "SMALL_FORMING"
    assert analyze_energy_relation(original)["state"] == "WAIT_SMALL"
    assert analyze_energy_relation(original.iloc[:len(prefix)])["small_status"] == "forming"
    pd.testing.assert_frame_equal(prefix, before)


def test_previous_leg_double_bottom_is_not_reused_as_current_leg_evidence():
    frame = _frame(BOTTOM + [50.0] * 8)
    turn = 12 + len(BOTTOM) + 2
    frame[f"stoch_k_{LARGE}"] = np.r_[np.linspace(30, 80, turn), np.linspace(79, 60, len(frame)-turn)]
    full_detection = detect_stochastic_bottom_patterns(frame.copy(), SMALL)
    assert full_detection[f"stoch_db_{SMALL}"].notna().any()
    result = analyze_energy_relation(full_detection)
    assert result["small_status"] == "waiting"
    assert result["small_confirm_time"] is None


def test_first_bottom_before_leg_start_cannot_pair_with_second_bottom_inside_leg():
    frame = _frame(BOTTOM, padding=0)
    frame["close"] = 100.0 + np.arange(len(frame))
    frame[f"stoch_k_{LARGE}"] = np.r_[np.linspace(30, 80, 12), np.linspace(79, 60, len(frame)-12)]
    full_detection = detect_stochastic_bottom_patterns(frame.copy(), SMALL)
    assert full_detection[f"stoch_db_{SMALL}"].notna().any()
    result = analyze_energy_relation(full_detection)
    assert result["leg_start_pos"] == 11
    assert result["small_status"] == "waiting"


def test_large_reversal_records_prior_small_confirmation_as_a_separate_event():
    frame = _frame()
    assert analyze_energy_relation(frame)["small_status"] == "confirmed"
    turned = _append(frame, large=51.0, small=45.0)
    result = analyze_energy_relation(turned)
    assert result["state"] == "LARGE_REVERSED"
    assert result["large_direction"] == "up" and result["ma10_direction"] == "down"
    assert result["alignment"] == "opposed"
    event = result["reversal_event"]
    assert event["from_direction"] == "down" and event["to_direction"] == "up"
    assert event["small_pattern"] == "db" and event["small_confirmed"] is True
    assert event["small_confirm_time"] == frame.index[12 + 17]
    assert event["small_confirmation_timing"] == "before"
    assert event["time"] == turned.index[-1]
    assert result["small_pattern"] == "dt" and result["small_status"] == "waiting"


def test_small_confirmation_on_large_turn_bar_is_simultaneous_not_prior_evidence():
    frame = _frame(BOTTOM[:17])
    assert analyze_energy_relation(frame)["small_status"] == "forming"
    turned = _append(frame, large=51.0, small=30.0)
    result = analyze_energy_relation(turned)
    assert result["state"] == "LARGE_REVERSED"
    assert result["reason_code"] == "SMALL_WITH_LARGE_REVERSAL"
    event = result["reversal_event"]
    assert event["small_confirmed"] is True
    assert event["small_confirmation_timing"] == "same_bar"
    assert event["small_confirm_time"] == event["time"] == turned.index[-1]


def test_large_can_reverse_without_small_confirmation_and_requests_reassessment():
    frame = _frame([50] * 19)
    turned = _append(frame, large=51.0, small=50.0)
    result = analyze_energy_relation(turned)
    assert result["state"] == "REASSESS"
    assert result["reversal_event"]["small_confirmed"] is False


def test_reversal_event_only_uses_information_available_at_its_turn_bar():
    frame = _frame([50] * 19)
    turned = _append(frame, large=51.0, small=50.0)
    original_event = analyze_energy_relation(turned)["reversal_event"]
    extended = turned
    for i, value in enumerate(BOTTOM):
        extended = _append(extended, large=52.0+i, small=value)
    result = analyze_energy_relation(extended)
    assert result["reversal_event"] == original_event
    assert result["reversal_event"]["small_confirmed"] is False
    assert result["state"] == "WAIT_SMALL"  # 현재 상승 구간에서는 쌍봉을 관찰한다.


def test_incomplete_left_boundary_does_not_claim_absence_of_small_reversal_pattern():
    frame = _frame([50] * 19)
    frame[f"stoch_k_{LARGE}"] = np.linspace(80.0, 40.0, len(frame))
    result = analyze_energy_relation(frame)
    assert result["state"] == "HISTORY_PARTIAL"
    assert not result["leg_history_complete"]
    assert result["small_status"] == "unknown"


def test_positive_confirmation_remains_observed_even_when_leg_start_is_truncated():
    frame = _frame()
    frame[f"stoch_k_{LARGE}"] = np.linspace(80.0, 40.0, len(frame))
    result = analyze_energy_relation(frame)
    assert result["state"] == "SMALL_CONFIRMED"
    assert not result["leg_history_complete"]


def test_flat_last_bar_keeps_current_direction_leg_but_reports_flat_curve():
    frame = _frame()
    stable = _append(frame, large=50.0, small=45.0)
    result = analyze_energy_relation(stable)
    assert result["large_direction"] == "flat"
    assert result["leg_direction"] == "down"
    assert result["leg_start_time"] == analyze_energy_relation(frame)["leg_start_time"]
    assert result["state"] == "SMALL_CONFIRMED"


def test_every_large_value_flat_has_no_direction_leg():
    frame = _frame()
    frame[f"stoch_k_{LARGE}"] = 50.0
    result = analyze_energy_relation(frame)
    assert result["state"] == "FLAT"
    assert result["leg_start_pos"] is None


@pytest.mark.parametrize("column", ["close", f"stoch_k_{LARGE}", f"stoch_k_{SMALL}"])
def test_nonfinite_inputs_defer_instead_of_claiming_missing_pattern(column):
    frame = _frame()
    frame.loc[frame.index[-3], column] = np.nan
    result = analyze_energy_relation(frame)
    assert result["state"] == "INSUFFICIENT"


def test_warmup_nulls_before_first_large_value_are_allowed():
    frame = _frame()
    frame.loc[frame.index[:4], f"stoch_k_{LARGE}"] = np.nan
    assert analyze_energy_relation(frame)["state"] == "SMALL_CONFIRMED"


def test_bearish_relation_is_the_exact_mirror_of_bullish_relation():
    original = _frame(BOTTOM[:16])
    mirrored = original.copy()
    for layer in (LARGE, MID, SMALL):
        mirrored[f"stoch_k_{layer}"] = 100.0 - mirrored[f"stoch_k_{layer}"]
    mirrored["close"] = 400.0 - mirrored["close"]
    up, down = analyze_energy_relation(original), analyze_energy_relation(mirrored)
    assert up["state"] == down["state"] == "SMALL_FORMING"
    assert up["small_pattern"] == "db" and down["small_pattern"] == "dt"
    assert up["large_direction"] == "down" and down["large_direction"] == "up"
    assert down["small_candidate_level"] == 100.0 - up["small_candidate_level"]
    assert down["ma10_delta"] == -up["ma10_delta"]


def test_ma10_direction_and_next_reference_are_computed_independently_from_close():
    frame = _frame()
    result = analyze_energy_relation(frame)
    assert result["ma10_delta"] == (frame["close"].iloc[-1] - frame["close"].iloc[-11]) / 10
    assert result["ma10_next_reference"] == frame["close"].iloc[-10]


def test_real_project_indicators_disprove_large_falling_implies_ma10_falling():
    close = np.arange(100.0, 200.0)
    frame = pd.DataFrame({"open": close, "high": close+1, "low": close-1, "close": close,
                          "volume": np.ones(len(close))},
                         index=pd.date_range("2026-01-01", periods=len(close), freq="1h"))
    frame.loc[frame.index[-1], "high"] = 299.0
    actual = add_stochastic_slow_layers(add_moving_averages(frame))
    result = analyze_energy_relation(actual)
    assert actual[f"stoch_k_{LARGE}"].iloc[-1] < actual[f"stoch_k_{LARGE}"].iloc[-2]
    assert actual["MA10"].iloc[-1] > actual["MA10"].iloc[-2]
    assert actual[f"stoch_db_{SMALL}"].notna().sum() == 0
    assert result["large_direction"] == "down" and result["ma10_direction"] == "up"
    assert result["alignment"] == "opposed"
