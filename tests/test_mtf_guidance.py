"""마감 설명의 시각 경계·수학·자료 보류 계약을 검사한다."""
import pandas as pd
import pytest

from display.mtf_guidance_model import build_guidance, closed_frame


def _frame(n=70, freq="4h"):
    return pd.DataFrame({"close": range(n)}, index=pd.date_range("2024-01-01", periods=n, freq=freq))


def _guide(df, *, asof=None, candidates=None, frames=None):
    asof = asof if asof is not None else df.index[-1] + pd.Timedelta(hours=4)
    return build_guidance("4h", frames or {"4h": df}, candidates or {}, asof)


def _items(view):
    return dict(view["items"])


def _candidate(df, state="대기 중"):
    return pd.DataFrame([{"상태": state, "확정 시각": df.index[-5], "_known_pos": len(df)-3,
                          "_confirm_pos": len(df)-5, "_lag": 2}])


def test_closed_frame_excludes_progressing_and_future_bars_without_mutation():
    frame = _frame()
    frame["open"] = frame["close"]
    closed = closed_frame(frame, "4h", frame.index[-1] + pd.Timedelta(hours=1))
    assert len(closed) == len(frame)-1
    assert list(closed.columns) == list(frame.columns)
    assert len(closed_frame(frame, "4h", frame.index[-1] + pd.Timedelta(hours=4))) == len(frame)
    assert len(frame) == 70


def test_month_close_uses_calendar_boundary_and_timezone():
    frame = pd.DataFrame({"close": [1, 2, 3]}, index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    closed = closed_frame(frame, "1M", "2024-03-01T09:00:00+09:00")
    assert closed.index.tolist() == frame.index[:2].tolist()
    assert len(closed_frame(frame, "1M", "2024-02-29T23:59:59Z")) == 1


def test_aware_input_index_is_interpreted_as_utc_instant():
    frame = _frame(2)
    frame.index = frame.index.tz_localize("UTC").tz_convert("Asia/Seoul")
    closed = closed_frame(frame, "4h", "2024-01-01T13:00:00+09:00")
    assert len(closed) == 1
    assert str(closed.index.tz) == "Asia/Seoul"


@pytest.mark.parametrize("interval", ["2d", "4d", "2w"])
def test_right_label_custom_intervals_are_explicitly_deferred(interval):
    closed = closed_frame(_frame(), interval, "2030-01-01")
    assert closed.empty
    assert "경계" in closed.attrs["guidance_issue"]
    view = build_guidance(interval, {interval: closed}, {}, "2030-01-01")
    assert "보류" in _items(view)["자료 기준"]


@pytest.mark.parametrize("index", [["2024-01-01", "2024-01-01"], ["2024-01-02", "2024-01-01"]])
def test_duplicate_or_unordered_times_are_deferred(index):
    frame = pd.DataFrame({"close": [1, 2]}, index=pd.to_datetime(index))
    assert closed_frame(frame, "4h", "2024-01-03").empty


def test_next_reference_uses_sixtieth_last_close_and_kst_close_time():
    frame = _frame()
    view = _guide(frame)
    items = _items(view)
    assert view["next_check_at"] == pd.Timestamp("2024-01-12 20:00Z")
    assert "10보다 높으면" in items["다음 확인"]
    assert "2024-01-13 05:00 (KST)" in items["다음 확인"]
    assert "상승" in items["현재 판단"]
    assert "목표가·예측이 아닙니다" in items["해석 범위"]


def test_reference_display_preserves_price_precision_for_strict_comparison():
    frame = _frame()
    frame["close"] = frame["close"].astype(float)
    frame.iloc[-60, 0] = 12345.12345678
    assert "12,345.12345678보다 높으면" in _items(_guide(frame))["다음 확인"]


@pytest.mark.parametrize("last, expected", [(11, "상승"), (9, "하락"), (10, "평탄")])
def test_direction_compares_current_to_sixty_bars_ago(last, expected):
    frame = _frame(61)
    frame.loc[:, "close"] = 10
    frame.iloc[-1, 0] = last
    assert _guide(frame)["snapshot"]["ma60"] == expected


def test_sixty_bars_allow_next_condition_but_not_current_direction():
    view = _guide(_frame(60))
    assert "61봉 필요" in view["snapshot"]["ma60"]
    assert "0보다 높으면" in _items(view)["다음 확인"]


def test_missing_bar_and_nullable_close_do_not_emit_price_condition():
    frame = _frame().drop(_frame().index[-15])
    view = _guide(frame)
    assert "보류" in view["snapshot"]["data"]
    assert "종가가" not in _items(view)["다음 확인"]
    frame = _frame()
    frame["close"] = frame["close"].astype("Float64")
    frame.iloc[-3, 0] = pd.NA
    assert "보류" in _guide(frame)["snapshot"]["data"]


def test_stale_data_requests_refresh_instead_of_past_next_confirmation():
    frame = _frame()
    view = _guide(frame, asof=frame.index[-1] + pd.Timedelta(hours=9))
    assert "지연" in view["snapshot"]["data"]
    assert "새로고침" in _items(view)["다음 확인"]
    assert "종가가" not in _items(view)["다음 확인"]


def test_opposing_candidates_are_both_explained_and_known_lag_is_preserved():
    frame = _frame()
    cand = _candidate(frame)
    view = _guide(frame, candidates={"4h": (cand, cand)})
    items = _items(view)
    assert "쌍바닥" in items["선정 이유"] and "쌍봉" in items["선정 이유"]
    assert "한 방향으로 단정" in items["선정 이유"]
    assert "확정봉 마감" in items["선정 이유"] and "가용봉 마감" in items["선정 이유"]
    assert "잔여 18봉(약 72시간)" in items["관찰 기간"]
    assert "상방 관찰" in items["관찰 기간"] and "하방 관찰" in items["관찰 기간"]


def test_already_direction_remains_in_progressing_trend_explanation():
    frame = _frame()
    view = _guide(frame, candidates={"4h": (_candidate(frame, "해당 없음 (이미 상방)"), None)})
    assert "진행 추세 관찰" in _items(view)["선정 이유"]
    assert "열려 있는 전환 관찰 창 없음" in _items(view)["관찰 기간"]


def test_absent_context_is_explicit_without_inventing_substitute_tf():
    view = _guide(_frame())
    assert view["related"] == {"upper": "1d", "lower": "1h"}
    assert "1d 미적재" in _items(view)["상위 환경"]
    assert "1h 미적재" in _items(view)["하위 진행"]
    assert "후보 없음" in _items(view)["선정 이유"]


def test_context_has_direction_and_data_quality_and_cannot_replace_owner():
    frame = _frame()
    daily = _frame(70, "1D")
    hourly = _frame(70, "1h")
    asof = daily.index[-1] + pd.Timedelta(days=1)
    view = _guide(frame, asof=asof, frames={"4h": frame, "1d": daily, "1h": hourly})
    assert "1d MA60 1봉 변화: 상승" in _items(view)["상위 환경"]
    assert "갱신 지연" in _items(view)["하위 진행"]
    assert "전환을 확정하지 않습니다" in _items(view)["하위 진행"]


def test_semantic_snapshot_ignores_reference_price_and_clock_only_changes():
    frame = _frame()
    view = _guide(frame)
    shifted = frame.copy()
    shifted["close"] += 100
    view2 = _guide(shifted, asof=frame.index[-1]+pd.Timedelta(hours=5))
    assert view["snapshot"] == view2["snapshot"]
    assert _items(view)["다음 확인"] != _items(view2)["다음 확인"]


def test_mapping_matches_current_v1_contract_for_every_supported_tf():
    from display.mtf_guidance_model import _adjacent
    from analysis.wave_energy import resolve_lower_frame, resolve_upper_frame
    from config.settings import TIMEFRAMES

    for interval in TIMEFRAMES:
        assert _adjacent(interval, True) == resolve_upper_frame(interval)
        assert _adjacent(interval, False) == resolve_lower_frame(interval)


def test_empty_data_does_not_claim_absence_of_candidates():
    view = build_guidance("4h", {"4h": None}, {}, "2024-06-01")
    assert "후보 유무 판단을 보류" in _items(view)["선정 이유"]
    assert "후보 없음" not in _items(view)["선정 이유"]


def test_context_relations_explain_conflict_without_predicting_outcome():
    frame = _frame()
    asof = frame.index[-1] + pd.Timedelta(hours=4)
    daily = pd.DataFrame({"close": range(70, 0, -1)}, index=pd.date_range(end=asof-pd.Timedelta(days=1), periods=70, freq="1D"))
    hourly = pd.DataFrame({"close": range(70, 0, -1)}, index=pd.date_range(end=asof-pd.Timedelta(hours=1), periods=70, freq="1h"))
    candidate = _candidate(frame)
    view = _guide(frame, frames={"4h": frame, "1d": daily, "1h": hourly}, candidates={"4h": (candidate, candidate)})
    assert "상방 관찰과 반대 방향" in _items(view)["상위 환경"]
    assert "하방 관찰과 같은 방향" in _items(view)["상위 환경"]
    assert "기준 TF MA60과 반대 방향" in _items(view)["하위 진행"]
    stale = _guide(frame, asof=asof+pd.Timedelta(days=1), frames={"4h": frame, "1d": daily, "1h": hourly}, candidates={"4h": (candidate, None)})
    assert "방향 관계를 확인" in _items(stale)["상위 환경"]
    assert "관찰과 반대 방향" not in _items(stale)["상위 환경"]


def test_gap_during_active_window_defers_remaining_wall_clock_time():
    frame = _frame().drop(_frame().index[-2])
    view = _guide(frame, candidates={"4h": (_candidate(frame), None)})
    assert "잔여 봉·시간 계산 보류" in _items(view)["관찰 기간"]
    assert "약 " not in _items(view)["관찰 기간"]


def test_sliding_window_positions_do_not_change_same_candidate_identity():
    frame = _frame()
    candidate = _candidate(frame)
    original = _guide(frame, candidates={"4h": (candidate, None)})
    shifted = _frame(71).iloc[1:]
    moved = candidate.copy()
    moved["_known_pos"] -= 1
    moved["_confirm_pos"] -= 1
    after = _guide(shifted, candidates={"4h": (moved, None)})
    assert original["snapshot"] == after["snapshot"]
