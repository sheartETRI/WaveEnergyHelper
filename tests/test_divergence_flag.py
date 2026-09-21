"""다이버전스 플래그(display/divergence_flag) — 단일 정의 고정(스토캐 HL ∧ 피봇 봉 저가 둘째 < 첫째) · 기존 검출 결과 소비 ·
60MA 전환 추적 표 '다이버전스' 열·집계 줄 · 재구현 금지 · 정의 문서 대조."""
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.divergence_flag as DV  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402
from indicators.moving_averages import add_moving_averages  # noqa: E402
from indicators.stochastic import add_stochastic_slow_layers  # noqa: E402


# ------------------------------------------------------------ 정의 (합성 sig — 네 조합 전부)
def _pipe(n, kind_at, lows):
    idx = pd.date_range("2026-09-01", periods=n, freq="h")
    pipe = pd.DataFrame({"low": lows, "close": lows, "high": lows, "open": lows}, index=idx)
    pipe[DV.KIND_COL] = pd.Series([None] * n, index=idx, dtype="object")
    for pos, k in kind_at.items():
        pipe.iloc[pos, pipe.columns.get_loc(DV.KIND_COL)] = k
    return pipe


def test_definition_requires_stoch_hl_and_lower_pivot_bar_low():
    n = 40
    lows = np.full(n, 100.0)
    lows[5], lows[15] = 90.0, 85.0      # 후보 A: 가격 저점 낮아짐(둘째 < 첫째)
    lows[25], lows[35] = 80.0, 88.0     # 후보 B: 가격 저점 높아짐
    pipe = _pipe(n, {18: "HL", 20: "LL", 38: "HL", 39: "HL"}, lows)
    sig = {"cands": [
        {"confirm_pos": 18, "p1": 5, "p2": 15},     # HL + 가격 LL → 있음
        {"confirm_pos": 20, "p1": 5, "p2": 15},     # 스토캐 LL + 가격 LL → 없음
        {"confirm_pos": 38, "p1": 25, "p2": 35},    # HL + 가격 HL → 없음
        {"confirm_pos": 39, "p1": 25, "p2": 35},    # HL + 가격 HL → 없음
    ]}
    flags = DV.divergence_flags(pipe, sig)
    assert flags == {18: True, 20: False, 38: False, 39: False}
    assert DV.label(True) == "있음" and DV.label(False) == "없음" and DV.label(None) == ""
    # 비교는 '피봇 봉의 저가' — 구간 최저가가 아니다: 첫~둘째 피봇 사이 더 낮은 봉이 있어도 무관
    lows2 = lows.copy(); lows2[10] = 50.0
    assert DV.divergence_flags(_pipe(n, {18: "HL"}, lows2), {"cands": [{"confirm_pos": 18, "p1": 5, "p2": 15}]}) == {18: True}
    lows3 = lows.copy(); lows3[5], lows3[15] = 85.0, 85.0      # 같으면 없음(둘째 < 첫째 아님)
    assert DV.divergence_flags(_pipe(n, {18: "HL"}, lows3), {"cands": [{"confirm_pos": 18, "p1": 5, "p2": 15}]}) == {18: False}


def test_kind_column_missing_means_no_divergence_and_no_error():
    pipe = _pipe(10, {}, np.arange(10, dtype=float)).drop(columns=[DV.KIND_COL])
    assert DV.divergence_flags(pipe, {"cands": [{"confirm_pos": 8, "p1": 2, "p2": 6}]}) == {8: False}


# ------------------------------------------------------------ 기존 검출 결과 소비 (합성 프레임 → 앱 파이프라인)
def _frame(n=1600, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    steps = rng.normal(0, 0.004, n) + 0.02 * np.sin(np.arange(n) / 37.0) * 0.004
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.003, n))
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": rng.uniform(1, 9, n)}, index=idx)
    df.index.name = "open_time"
    return add_stochastic_slow_layers(add_moving_averages(df))


def test_flags_consume_detector_kind_and_probe_pivots_on_pipeline():
    pipe = T.tracker_pipe(_frame())
    sig = probe.extract_signals(pipe)
    flags = DV.divergence_flags(pipe, sig)
    assert set(flags) == {int(cd["confirm_pos"]) for cd in sig["cands"]} and len(flags) >= 20
    kind = pipe[DV.KIND_COL].to_numpy(dtype=object)
    low = pipe["low"].to_numpy(dtype=float)
    first = pipe[f"stoch_db_first_pos_{probe.LARGE}"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    piv_low = pipe[f"stoch_pivot_low_{probe.LARGE}"].notna().to_numpy()
    for cd in sig["cands"]:
        c, p1, p2 = int(cd["confirm_pos"]), int(cd["p1"]), int(cd["p2"])
        assert p1 == int(first[c]) and piv_low[p2] and p2 <= c and not piv_low[p2 + 1:c + 1].any()   # 검출기 기록·마지막 피봇
        assert flags[c] == ((kind[c] == "HL") and (low[p2] < low[p1]))
    assert any(flags.values()) and not all(flags.values())                     # 두 값 모두 표본에 있음
    assert DV.divergence_flags(pipe) == flags                                   # sig 생략 시 probe 재호출 결과 동일


def test_no_reimplementation_in_flag_module():
    body = open(DV.__file__, encoding="utf-8").read().split('"""', 2)[2]
    for banned in ("compute_stochastic_pivots", "compute_series_pivots", "detect_double_bottom", "np.roll", "shift(",
                   "rolling(", "argrelextrema", "min()", "nanmin"):
        assert banned not in body, banned
    assert "probe.extract_signals(" in body and "stoch_db_kind_" in body and "stoch_pivot" not in body


# ------------------------------------------------------------ 표 열 · 집계 줄
def test_tracker_table_has_divergence_column_and_cohort_summary_line():
    assert DV.DIVERGENCE_COL in T.COLUMNS and T.COLUMNS.index(DV.DIVERGENCE_COL) == T.COLUMNS.index("확정 시 60MA") + 1
    df = _frame()
    frame = T.track_candidates(df, recent_bars=len(df))
    assert set(frame[DV.DIVERGENCE_COL]) <= {"있음", "없음"} and (frame[DV.DIVERGENCE_COL] == "있음").any()
    flags = DV.divergence_flags(T.tracker_pipe(df))
    for d in frame.to_dict("records"):
        assert d[DV.DIVERGENCE_COL] == DV.label(flags[int(d["_confirm_pos"])])
    s = T.divergence_summary(frame)
    y = frame[frame[DV.DIVERGENCE_COL] == "있음"]; n_ = frame[frame[DV.DIVERGENCE_COL] == "없음"]
    assert s["있음"] == {"turned": int((y["상태"] == T.STATUS_TURNED).sum()), "expired": int((y["상태"] == T.STATUS_EXPIRED).sum())}
    assert s["없음"] == {"turned": int((n_["상태"] == T.STATUS_TURNED).sum()), "expired": int((n_["상태"] == T.STATUS_EXPIRED).sum())}
    line = T.divergence_summary_line(frame)
    assert line.startswith("다이버전스 있음: 전환 ") and " · 없음: 전환 " in line and line.endswith("(미검증, 표본 적음)")
    lines = T.build_lines(frame)
    assert lines[-1] == line and lines[-2] == T.summary_line(frame)
    assert all("다이버전스 " in l for l in lines[2:-2])
    # 표시 표는 열 유지, 렌더 코드가 집계 줄을 캡션으로 낸다
    d = T.display_frame(frame, "BTCUSDT", "1h")
    assert list(d.columns) == list(T.COLUMNS) and set(d[DV.DIVERGENCE_COL]) <= {"있음", "없음"}
    src = open(T.__file__, encoding="utf-8").read()
    assert "st.caption(divergence_summary_line(frame))" in src
    assert T.divergence_summary(pd.DataFrame(columns=T.COLUMNS)) == {"있음": {"turned": 0, "expired": 0}, "없음": {"turned": 0, "expired": 0}}


def test_divergence_summary_line_from_fixed_frame():
    f = pd.DataFrame({"상태": [T.STATUS_TURNED, T.STATUS_EXPIRED, T.STATUS_EXPIRED, T.STATUS_WAITING, T.STATUS_TURNED],
                      DV.DIVERGENCE_COL: ["있음", "있음", "없음", "있음", "없음"]})
    assert T.divergence_summary_line(f) == "다이버전스 있음: 전환 1 / 소멸 1 · 없음: 전환 1 / 소멸 1 (미검증, 표본 적음)"


# ------------------------------------------------------------ 정의 문서 대조 (main 870f025)
def test_definition_matches_fixed_doc_on_main():
    try:
        doc = subprocess.run(["git", "show", "870f025:docs/CANDIDATES_POST_2027_03.md"], cwd=ROOT,
                             capture_output=True, check=True, timeout=30).stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git 또는 정의 커밋을 읽을 수 없음")
    for s in ("(20,10,10)", "`stoch_db_kind` = HL", "피봇 봉의 저가", "두 번째 < 첫 번째", "앱 표시·전방 기록이 모두 공유"):
        assert s in doc, s
    head = open(DV.__file__, encoding="utf-8").read().split('"""', 2)[1]
    assert "870f025" in head and "피봇 봉의 저가" in head and '"HL"' in head
