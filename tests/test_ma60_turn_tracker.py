"""60MA 전환 추적 표시(display/ma60_turn_tracker) — 체리픽 동일성 · import 소비 단언 · probe.simulate 상태 일치 ·
미검증 라벨 · 차트 연동 · main 배선 · 알람 푸시 무접촉."""
import hashlib
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import charts.lw_builder as LW  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402
from indicators.moving_averages import add_moving_averages  # noqa: E402
from indicators.stochastic import add_stochastic_slow_layers  # noqa: E402


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


# ------------------------------------------------------------ 체리픽 동일성
def test_probe_script_matches_manifest_and_origin_commit():
    assert set(T.CHERRYPICK_PROBE) == {"validation/wave_ma60_turn_probe.py"}
    for rel, sha in T.CHERRYPICK_PROBE.items():
        with open(os.path.join(ROOT, rel), "rb") as fh:
            local = _norm(fh.read())
        assert hashlib.sha256(local).hexdigest() == sha, f"{rel} 가 매니페스트와 다르다 (내용 무변경 원칙)"
        try:
            blob = subprocess.run(
                ["git", "show", f"{T.CHERRYPICK_PROBE_SOURCE_COMMIT}:{rel}"],
                cwd=ROOT, capture_output=True, check=True, timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            pytest.skip("git 또는 원본 커밋을 읽을 수 없음 — 매니페스트 해시로만 확인")
        assert _norm(blob) == local, f"{rel} 가 원본 커밋 {T.CHERRYPICK_PROBE_SOURCE_COMMIT} 과 diff 있음"


def test_tracker_imports_probe_and_does_not_reimplement_detection():
    src = open(T.__file__, encoding="utf-8").read()
    body = src.split('"""', 2)[2]
    assert "import validation.wave_ma60_turn_probe as probe" in body
    assert "probe.extract_signals(" in body and "probe.OBS_BARS" in body and "probe.BUFFER" in body
    # 검출 재구현 흔적 금지: 피봇·스토캐 쌍바닥·MA 기울기 계산이 표시 계층에 없다
    for banned in ("stoch_pivot", "compute_series_pivots", "find_swing_lows", "np.roll", "shift(", "> prev",
                   "detect_double_bottom"):
        assert banned not in body, banned
    assert T.OBS_BARS == 20 and T.BUFFER == 0.005
    assert T.track_candidates.__module__ == "display.ma60_turn_tracker"


def test_import_restores_logging_and_warnings():
    """probe 는 import 시 logging.disable(CRITICAL)·warnings 무시를 건다 — 표시 모듈이 import 직후 원상 복구한다.

    전체 스위트에서는 다른 테스트가 먼저 logging 을 건드릴 수 있으므로 절대값 대신 '리로드 전후 동일' 을 본다.
    """
    import importlib
    import logging
    import warnings
    before_disable = logging.root.manager.disable
    before_filters = warnings.filters[:]
    importlib.reload(T)                       # probe 의 부작용 재실행 → 복구 코드 재실행
    assert logging.root.manager.disable == before_disable
    assert warnings.filters[:] == before_filters


# ------------------------------------------------------------ 합성 프레임
def _synthetic_frame(n: int = 1600, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    steps = rng.normal(0, 0.004, n) + 0.02 * np.sin(np.arange(n) / 37.0) * 0.004
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.003, n))
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": rng.uniform(1, 9, n)},
                      index=idx)
    df.index.name = "open_time"
    df = add_moving_averages(df)
    return add_stochastic_slow_layers(df)


# ------------------------------------------------------------ probe.simulate 와 상태 일치
def test_lifecycle_matches_probe_simulate_on_synthetic_frame():
    df = _synthetic_frame()
    frame = T.track_candidates(df, recent_bars=len(df))
    assert not frame.empty and len(frame) >= 5, "합성 프레임에 후보가 너무 적다"
    sig = probe.extract_signals(T.tracker_pipe(df))
    bars = df[["open", "high", "low", "close"]]
    cands, trades = probe.simulate("SYN", "1h", bars, sig)
    assert not cands.empty
    mine = frame.set_index("확정 시각")
    sim = cands.set_index("confirm_ts")
    turn_by_confirm = dict(zip(trades["confirm_ts"], trades["turn_ts"]))
    checked = 0
    for ts, row in sim.iterrows():
        assert ts in mine.index, f"probe 후보 {ts} 가 표시 표에 없다"
        status = mine.loc[ts, "상태"]
        if row["status"] in (probe.CAND_ENTERED, probe.CAND_BUSY):
            assert status == T.STATUS_TURNED, (ts, row["status"], status)
            if row["status"] == probe.CAND_ENTERED:
                assert pd.Timestamp(mine.loc[ts, "전환 시각"]) == pd.Timestamp(turn_by_confirm[ts])
            checked += 1
        elif row["status"] == probe.CAND_EXPIRED:
            assert status == T.STATUS_EXPIRED, (ts, status)
            checked += 1
        elif row["status"] == probe.CAND_NO_MA:
            assert status == T.STATUS_NO_MA
    assert checked >= 5
    # 표시 표에만 있는 후보 = 창이 자료 끝을 넘는 최근 건(대기 중) — simulate 의 DATA_END 와 대응
    extra = set(mine.index) - set(sim.index)
    assert all(mine.loc[ts, "상태"] == T.STATUS_WAITING for ts in extra)
    # 이미 상방 표기는 가용 시점의 MA60 방향에서만 나온다
    for ts in mine.index:
        k = int(mine.loc[ts, "_known_pos"])
        assert (mine.loc[ts, "확정 시 60MA"] == T.ALREADY_UP_MARK) == bool(sig["ma60_up"][k])


def test_waiting_elapsed_and_recent_filter():
    df = _synthetic_frame()
    full = T.track_candidates(df, recent_bars=len(df))
    recent = T.track_candidates(df, recent_bars=120)
    assert len(recent) <= len(full)
    assert (recent["_known_pos"] >= len(df) - 120).all()
    for d in full.to_dict("records"):
        e, tot = d["경과"].split("/")
        assert tot == "20" and 0 <= int(e) <= 20
        if d["상태"] == T.STATUS_WAITING:
            assert int(e) < 20
        if d["상태"] == T.STATUS_EXPIRED:
            assert e == "20" and pd.notna(d["소멸 시각"]) and pd.isna(d["전환 시각"])
        if d["상태"] == T.STATUS_TURNED:
            assert pd.notna(d["전환 시각"]) and pd.notna(d["전환 시 가격"]) and pd.isna(d["소멸 시각"])
        assert d["기준선(×0.995)"] == pytest.approx(d["패턴 저점"] * (1 - T.BUFFER))


def test_summary_rate_uses_finished_only():
    f = pd.DataFrame({
        "상태": [T.STATUS_TURNED, T.STATUS_TURNED, T.STATUS_EXPIRED, T.STATUS_WAITING],
        "확정 시 60MA": [T.ALREADY_UP_MARK, "하방", "하방", "하방"],
    })
    s = T.summarize(f)
    assert (s["turned"], s["expired"], s["waiting"], s["already_up"]) == (2, 1, 1, 1)
    assert s["rate"] == pytest.approx(2 / 3)
    line = T.summary_line(f)
    assert "전환 2건 / 소멸 1건 / 대기 1건" in line and "2/3 = 67%" in line and "(미검증)" in line
    assert T.summarize(pd.DataFrame(columns=T.COLUMNS))["rate"] is None


# ------------------------------------------------------------ 표기 규율
def test_labels_are_unverified_and_never_recommend():
    assert "(미검증)" in T.SECTION_TITLE
    assert T.FIXED_CAPTION == ("탐색 계측 기준 후보의 약 60%는 60MA 전환 없이 소멸합니다 "
                               "(전환율 1h 40.7% / 4h 41.3%, 같은 표본 탐색 결과).")
    assert f"{T.PROBE_RATES['1h']*100:.1f}%" in T.FIXED_CAPTION and f"{T.PROBE_RATES['4h']*100:.1f}%" in T.FIXED_CAPTION
    df = _synthetic_frame()
    text = "\n".join(T.build_lines(T.track_candidates(df, recent_bars=len(df))))
    for banned in ("매수", "진입", "추천", "권고"):
        assert banned not in text, banned
    assert T.STATUS_TURNED == "전환 발생" and "(미검증)" in text
    # 렌더 문자열 상수에도 권고 어휘 없음
    src = open(T.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "매수" not in src and "추천" not in src


def test_empty_or_unprepared_frame_is_safe():
    assert T.track_candidates(None).empty and T.track_candidates(pd.DataFrame()).empty
    raw = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    assert T.track_candidates(raw).empty            # MA·스토캐 컬럼 없음 → 빈 표(예외 없음)
    assert T.build_lines(T.track_candidates(raw))[2] == "해당 구간에 대파동 쌍바닥 후보 없음"


# ------------------------------------------------------------ 차트 연동
def test_tracker_lines_only_for_waiting_and_distinct_colors():
    f = pd.DataFrame({
        "상태": [T.STATUS_WAITING, T.STATUS_TURNED, T.STATUS_EXPIRED],
        "패턴 저점": [100.0, 90.0, 80.0], "기준선(×0.995)": [99.5, 89.55, 79.6],
    })
    lines = T.tracker_reference_lines(f)
    assert [l["price"] for l in lines] == [100.0, 99.5]
    assert {l["color"] for l in lines} == {T.TRACKER_LOW_COLOR, T.TRACKER_LINE_COLOR}
    assert {T.TRACKER_LOW_COLOR, T.TRACKER_LINE_COLOR}.isdisjoint({LW.STRUCT_LOW_COLOR, LW.STRUCT_LINE_COLOR})
    assert all(l["title"] == "" and "(미검증)" in l["label"] for l in lines)
    assert T.tracker_reference_lines(pd.DataFrame(columns=T.COLUMNS)) == []


def _ohlc(n=40):
    idx = pd.date_range("2026-09-01", periods=n, freq="h")
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx)


def test_lw_html_draws_tracker_lines_and_caption_only_when_given():
    df = _ohlc()
    base = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    same = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="",
                            tracker_lines=[])
    assert base == same                                   # 후보 없음 → 출력 불변
    lines = [{"price": 101.5, "color": T.TRACKER_LOW_COLOR, "style": LW.LW_LINE_STYLE_DOTTED, "title": "", "label": "x"},
             {"price": 100.99, "color": T.TRACKER_LINE_COLOR, "style": LW.LW_LINE_STYLE_DASHED, "title": "", "label": "y"}]
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="",
                            tracker_lines=lines)
    assert '"price": 101.5' in html and '"price": 100.99' in html and '"label"' not in html
    assert "추적" in html and "(미검증)" in html and "저점 101.50" in html and "기준선 100.99" in html
    two = LW.tracker_caption_html(lines + lines)
    assert "외 1건" in two
    assert LW.tracker_caption_html([]) == ""


# ------------------------------------------------------------ main 배선 · 알람 푸시 무접촉
def test_main_wires_section_in_alarm_tab_and_lines_into_lw_chart():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    assert "from display.ma60_turn_tracker import render_tracker_section, tracker_reference_lines" in src
    alarm_block = src.split("with tab_alarm:", 1)[1].split("with tab_chart:", 1)[0]
    assert "render_tracker_section(df, symbol, interval)" in alarm_block
    assert "tracker_lines=tracker_reference_lines(tracker_frame)" in src


def test_alarm_signal_definitions_untouched_by_tracker():
    sig_src = open(os.path.join(ROOT, "analysis", "alarm_signals.py"), encoding="utf-8").read()
    assert "ma60_turn" not in sig_src and "wave_ma60_turn_probe" not in sig_src
    panel_src = open(os.path.join(ROOT, "display", "alarm_panel.py"), encoding="utf-8").read()
    assert "ma60_turn" not in panel_src


def test_display_frame_formats_without_none_or_truncation_risk():
    f = pd.DataFrame([{
        "상태": T.STATUS_EXPIRED, "확정 시각": pd.Timestamp("2026-09-14 12:00"), "경과": "20/20",
        "60MA 현재": "상방", "확정 시 60MA": "하방", "전환 시각": pd.NaT, "전환 시 가격": np.nan,
        "패턴 저점": 76046.58, "기준선(×0.995)": 75666.347, "소멸 시각": pd.Timestamp("2026-09-17 20:00"),
    }])
    d = T.display_frame(f)
    assert list(d.columns) == list(T.COLUMNS)
    assert d.loc[0, "전환 시각"] == "" and d.loc[0, "전환 시 가격"] == ""
    assert d.loc[0, "확정 시각"] == "2026-09-14 12:00" and d.loc[0, "소멸 시각"] == "2026-09-17 20:00"
    assert d.loc[0, "패턴 저점"] == "76,046.58"
    assert "None" not in d.to_string()
    assert set(T.TABLE_COLUMN_WIDTHS) <= set(T.COLUMNS)
