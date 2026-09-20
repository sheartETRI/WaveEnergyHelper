"""60MA 기울기 실측 표시(display/ma60_slope) — 부호·스케일, 오프셋, 부호 변경 창, 다중 TF 재사용, 판정·예측 어휘 부재,
정의·알람 무접촉, 60MA 전환 추적 섹션 배선."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.ma60_slope as M  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402


def _frame(ma60, start="2026-09-01", freq="4h"):
    idx = pd.date_range(start, periods=len(ma60), freq=freq)
    return pd.DataFrame({"close": ma60, "MA60": ma60}, index=idx)


# ------------------------------------------------------------ 부호·스케일
def test_slope_is_percent_per_bar_with_sign():
    s = M.slope_series(pd.Series([100.0, 101.0, 100.495, 100.495]))
    assert np.isnan(s.iloc[0])
    assert s.iloc[1] == pytest.approx(1.0)              # (101−100)/100 ×100 = +1.0 %/봉
    assert s.iloc[2] == pytest.approx(-0.5)             # (100.495−101)/101 ×100 = −0.5
    assert s.iloc[3] == pytest.approx(0.0)
    assert M.direction(0.3) == M.DIR_UP and M.direction(-0.3) == M.DIR_DOWN
    assert M.direction(0.0) == M.DIR_DOWN                # 60MA 전환 추적과 같은 기준: MA60(t) > MA60(t−1) 만 상방
    assert M.direction(float("nan")) == M.DIR_NA


def test_slope_handles_pd_na_and_short_frames():
    s = M.slope_series(pd.Series([pd.NA, pd.NA, 100.0, 102.0], dtype="object"))
    assert np.isnan(s.iloc[:3]).all() and s.iloc[3] == pytest.approx(2.0)
    assert M.slope_snapshot(None) is None
    assert M.slope_snapshot(pd.DataFrame({"close": [1.0]})) is None      # MA60 없음
    snap = M.slope_snapshot(_frame([100.0]))
    assert np.isnan(snap["now"]) and snap["direction"] == M.DIR_NA and snap["sign_change_at"] is None


# ------------------------------------------------------------ 오프셋·부호 변경
def test_snapshot_lags_map_to_1_3_5_bars_before_last():
    ma = 100.0 * np.cumprod(1 + np.array([0, .01, .02, .03, .04, .05, .06, .07]) / 100)
    snap = M.slope_snapshot(_frame(ma))
    assert snap["now"] == pytest.approx(0.07, rel=1e-6)
    assert snap["lags"][1] == pytest.approx(0.06, rel=1e-6)
    assert snap["lags"][3] == pytest.approx(0.04, rel=1e-6)
    assert snap["lags"][5] == pytest.approx(0.02, rel=1e-6)
    assert M.SLOPE_LAGS == (1, 3, 5) and snap["last_ts"] == pd.Timestamp("2026-09-02 04:00")


def test_sign_change_inside_and_outside_20_bar_window():
    down = [-0.1] * 30
    up = [0.1] * 10
    ma = 100.0 * np.cumprod(1 + np.array([0] + down + up) / 100)     # 31번째 봉(위치 31)에서 −→+
    snap = M.slope_snapshot(_frame(ma))
    assert snap["sign_change_bars_ago"] == 9 and snap["sign_change_at"] == pd.Timestamp("2026-09-06 04:00")
    assert snap["direction"] == M.DIR_UP
    ma2 = 100.0 * np.cumprod(1 + np.array([0] + down + [0.1] * 25) / 100)   # 변경이 24봉 전 → 창 밖
    snap2 = M.slope_snapshot(_frame(ma2))
    assert snap2["sign_change_at"] is None and snap2["sign_change_bars_ago"] is None
    assert M.SIGN_LOOKBACK == 20


def test_sign_change_uses_last_change_and_skips_nan():
    s = pd.Series([np.nan, 0.1, -0.1, np.nan, -0.1, 0.1, 0.1], index=pd.date_range("2026-09-01", periods=7, freq="h"))
    pos, ts = M.last_sign_change(s)
    assert pos == 5 and ts == pd.Timestamp("2026-09-01 05:00")        # NaN 을 건너뛴 뒤 마지막 변경
    assert M.last_sign_change(pd.Series([0.1, 0.1, 0.1])) is None


# ------------------------------------------------------------ 다중 TF
def test_multi_tf_reuses_loaded_frame_for_current_tf_and_loads_others():
    df = _frame([100.0, 101.0, 102.0])
    calls = []

    def loader(symbol, tf):
        calls.append((symbol, tf))
        if tf == "1d":
            raise RuntimeError("network")
        return _frame([100.0, 99.0, 98.0], freq="h")

    rows = M.multi_tf_snapshots("BTCUSDT", "4h", df, loader=loader)
    assert [tf for tf, _ in rows] == ["1h", "4h", "1d"] and calls == [("BTCUSDT", "1h"), ("BTCUSDT", "1d")]
    by = dict(rows)
    assert by["4h"]["direction"] == M.DIR_UP and by["1h"]["direction"] == M.DIR_DOWN and by["1d"] is None
    frame = M.summary_frame(rows, "4h")
    assert list(frame.columns) == list(M.COLUMNS) and frame["TF"].tolist() == ["1h", "4h ◀ 현재", "1d"]
    assert frame.iloc[2].tolist()[1:] == ["—", "—", "—", "—", M.DIR_NA, "—"]
    assert frame.iloc[1]["현재"] == "+0.9901"       # (102−101)/101 ×100, 소수 4자리·부호 표기


def test_load_ma_frame_uses_existing_bare_fetch_and_only_moving_averages(monkeypatch):
    import display.asof as asof
    bare = pd.DataFrame({"open": [1.0] * 70, "high": [1.0] * 70, "low": [1.0] * 70, "close": np.linspace(1, 2, 70),
                         "volume": [1.0] * 70}, index=pd.date_range("2026-01-01", periods=70, freq="h"))
    monkeypatch.setattr(asof, "fetch_ohlcv_bare", lambda symbol, interval: bare.copy())
    out = M.load_ma_frame("ETHUSDT", "1h")
    assert "MA60" in out.columns and not any(c.startswith("stoch") or c.startswith("MACD") or c == "RSI" for c in out.columns)
    monkeypatch.setattr(asof, "fetch_ohlcv_bare", lambda symbol, interval: None)
    assert M.load_ma_frame("ETHUSDT", "1h") is None


# ------------------------------------------------------------ 어휘·무접촉·배선
def test_no_judgement_or_forecast_words_and_no_thresholds():
    rows = [("1h", M.slope_snapshot(_frame(100.0 * np.cumprod(1 + np.r_[0, [-0.1] * 5, [0.1] * 5] / 100), freq="h"))),
            ("4h", None)]
    text = "\n".join(M.build_lines(rows, "1h")) + "\n" + M.FOOTNOTE + "\n" + M.BLOCK_TITLE + "\n" + "\n".join(M.COLUMNS)
    for w in M.FORBIDDEN_WORDS + ("매수", "진입", "매도"):
        assert w not in text, w
    assert "%/봉" in text and "부호 변경 09-01 15:00 (4봉 전)" in text and "방향 상방" in text   # UTC 06:00 → KST
    src = open(M.__file__, encoding="utf-8").read().split('"""', 2)[2]
    for banned in ("THRESHOLD", "임계값 =", "abs(", "< 0.0", "> 0.0"):      # 임계 판정 없음(부호 비교뿐)
        assert banned not in src, banned


def test_slope_module_touches_no_definition_alarm_or_gate_layers():
    src = open(M.__file__, encoding="utf-8").read()
    for banned in ("config.settings", "analysis.", "alarm_signals", "wave_htf_gate", "st.session_state", "probe"):
        assert banned not in src, banned


def test_tracker_section_renders_slope_block_and_keeps_direction_column():
    src = open(T.__file__, encoding="utf-8").read()
    assert "render_slope_block(df, symbol, interval)" in src
    assert "60MA 현재" in T.COLUMNS and T._ma_dir(np.array([True]), np.array([True]), 0) == "상방"
    main_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    assert "ma60_slope" not in main_src                                  # 배선은 섹션 안에서만(main 무변경)
