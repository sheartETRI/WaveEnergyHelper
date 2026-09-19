"""추세 구조 추적(display/trend_structure) — probe·swing import 소비 단언, 합성 케이스(유지/경고/훼손), 되돌림, 표기 규율, 배선."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.ma60_turn_tracker as MT  # noqa: E402
import display.trend_structure as TS  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402
from analysis import wave_structure_confirmation as WSC  # noqa: E402

DOC_END = '"""'


def _body(module) -> str:
    src = open(module.__file__, encoding="utf-8").read()
    return src.split(DOC_END, 2)[2]


# ------------------------------------------------------------ import 소비 단언
def test_consumes_probe_and_existing_swing_detector_without_reimplementation():
    assert TS.probe is probe and TS.probe is MT.probe
    body = _body(TS)
    assert "from analysis.wave_structure_confirmation import PIVOT, _confirmed, find_swing_highs, find_swing_lows" in body
    assert "probe.extract_signals(" in body and "MT.tracker_pipe(" in body and "MT.lifecycle_rows(" in body
    for banned in ("def find_swing", "rolling(", "argrelextrema", "stoch_pivot", "compute_series_pivots", "shift("):
        assert banned not in body, banned
    assert TS.swing_chain.__module__ == "display.trend_structure"
    assert WSC.PIVOT == 3


# ------------------------------------------------------------ 합성 케이스: 지그재그 가격으로 스윙을 만든다
def _zigzag(points, spacing=6, start="2026-09-01"):
    """points = [(kind, price)] 순서대로 극점을 두고 사이를 선형 보간. PIVOT=3 이라 spacing≥4 면 스윙이 확정된다."""
    prices = []
    for i in range(len(points) - 1):
        a, b = points[i][1], points[i + 1][1]
        prices += list(np.linspace(a, b, spacing, endpoint=False))
    prices.append(points[-1][1])
    back = -2.0 if points[-1][0] == "H" else 2.0      # 마지막 극점이 확정되도록 반대 방향 후행 봉(평탄하면 EQ 피봇이 생긴다)
    prices += list(np.linspace(points[-1][1], points[-1][1] + back, 5)[1:])
    idx = pd.date_range(start, periods=len(prices), freq="h")
    p = np.array(prices)
    return pd.Series(p + 0.5, index=idx), pd.Series(p - 0.5, index=idx)   # high, low


def _chain(points, base_low):
    high, low = _zigzag(points)
    return TS.swing_chain(high, low, base_pos=0, base_low=base_low, last_pos=len(high) - 1)


def test_intact_hh_hl_chain():
    # 기준 저점 → 고점 110 → 저점 104(HL) → 고점 118(HH) → 저점 111(HL) → 고점 125(HH)
    chain = _chain([("L", 100), ("H", 110), ("L", 104), ("H", 118), ("L", 111), ("H", 125)], base_low=99.5)
    kinds = [(r["kind"], r["cls"]) for r in chain]
    assert kinds == [("고점", "—"), ("저점", "HL"), ("고점", "HH"), ("저점", "HL"), ("고점", "HH")]
    st = TS.structure_state(chain)
    assert st["state"] == TS.STATE_INTACT and st["last_ll_at"] is None
    assert chain[1]["pct"] == pytest.approx((103.5 - 99.5) / 99.5 * 100)   # 직전 동종(기준 저점) 대비 %


def test_warning_when_latest_high_is_lower_high():
    chain = _chain([("L", 100), ("H", 110), ("L", 104), ("H", 118), ("L", 111), ("H", 115)], base_low=99.5)
    assert [r["cls"] for r in chain if r["kind"] == "고점"][-1] == "LH"
    st = TS.structure_state(chain)
    assert st["state"] == TS.STATE_WARN and st["last_ll_at"] is None


def test_broken_when_low_makes_lower_low_and_history_kept():
    chain = _chain([("L", 100), ("H", 110), ("L", 104), ("H", 118), ("L", 102)], base_low=99.5)
    lows = [r for r in chain if r["kind"] == "저점"]
    assert lows[-1]["cls"] == "LL"
    st = TS.structure_state(chain)
    assert st["state"] == TS.STATE_BROKEN and st["last_ll_at"] == lows[-1]["ts"]
    # 그 뒤 HH·HL 이 다시 이어지면 현재 구조는 유지, 마지막 훼손 시각은 남는다(상태 고정 아님, 번호 없음)
    chain2 = _chain([("L", 100), ("H", 110), ("L", 104), ("H", 118), ("L", 102), ("H", 120), ("L", 108), ("H", 126)],
                    base_low=99.5)
    st2 = TS.structure_state(chain2)
    assert st2["state"] == TS.STATE_INTACT and st2["last_ll_at"] is not None


def test_retracement_measured_against_previous_rise_not_judged():
    chain = _chain([("L", 100), ("H", 120), ("L", 110)], base_low=99.5)
    rt = TS.retracement(chain, 99.5)
    # 직전 저점 = 기준 저점 99.5, 고점 120.5, 저점 109.5 → (120.5−109.5)/(120.5−99.5) = 52.4%
    assert rt["pct"] == pytest.approx((120.5 - 109.5) / (120.5 - 99.5) * 100)
    assert TS.retracement(_chain([("L", 100), ("H", 120)], 99.5), 99.5) is None   # 고점 뒤 확정 저점 없음
    assert TS.RETRACE_REFS == (38.2, 50.0, 61.8)


# ------------------------------------------------------------ 표기 규율 · 표 · 마커
def _result(chain, turn_on=None):
    turn = ({"ts": chain[turn_on]["ts"], "price": 104.0, "pos": chain[turn_on]["pos"], "swings_before": turn_on + 1,
             "status": MT.STATUS_TURNED} if turn_on is not None
            else {"ts": None, "price": None, "pos": None, "swings_before": None, "status": MT.STATUS_EXPIRED})
    return {"base": {"ts": chain[0]["ts"], "low": 99.5, "p2_ts": chain[0]["ts"], "confirm_ts": chain[0]["ts"]},
            "chain": chain, "state": TS.structure_state(chain), "close": 118.0, "gain_pct": 18.6,
            "retrace": None, "turn": turn}


def test_labels_no_wave_numbers_no_recommendation():
    assert "(미검증)" in TS.SECTION_TITLE
    assert TS.FIXED_CAPTION == "고점·저점 연쇄를 그대로 표시합니다. 파동 번호는 사후 해석이므로 붙이지 않습니다."
    body = _body(TS).replace("권고 없음", "")
    for banned in ("1파", "2파", "3파", "목표가", "매수", "진입", "추천", "권고"):
        assert banned not in body, banned
    chain = _chain([("L", 100), ("H", 110), ("L", 104), ("H", 118)], base_low=99.5)
    result = _result(chain, turn_on=1)
    text = " | ".join(TS.build_lines(result))
    for banned in ("1파", "2파", "3파", "목표", "매수", "진입"):
        assert banned not in text, banned
    assert "연쇄 2번째 스윙 뒤" in text
    frame = TS.chain_frame(result)
    assert list(frame.columns) == list(TS.COLUMNS)
    assert frame["종류"].tolist() == ["고점", "저점", "60MA 전환", "고점"]   # 60MA 전환이 연쇄의 어느 지점인지 행으로
    marks = TS.structure_markers(result)
    assert [m["text"] for m in marks] == ["—", "HL", "HH", "60MA"] and marks[1]["position"] == "belowBar"
    dense = dict(result, chain=chain * 15)
    assert all(m["text"] == "" for m in TS.structure_markers(dense))            # 밀집 시 텍스트 생략
    empty = dict(_result(chain), chain=[], turn={"ts": None, "price": None, "pos": None, "swings_before": None,
                                                    "status": MT.STATUS_EXPIRED})
    assert TS.structure_markers(None) == [] and TS.structure_markers(empty) == [] and TS.chain_frame(empty).empty


def test_analyze_on_synthetic_frame_and_empty_frames():
    from indicators.moving_averages import add_moving_averages
    from indicators.stochastic import add_stochastic_slow_layers
    rng = np.random.default_rng(3)
    n = 1200
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.004, n) + 0.02 * np.sin(np.arange(n) / 37.0) * 0.004))
    df = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998, "close": close, "volume": 1.0}, index=idx)
    df = add_stochastic_slow_layers(add_moving_averages(df))
    r = TS.analyze(df)
    assert r is not None and r["base"]["low"] > 0 and r["state"]["state"] in (
        TS.STATE_FORMING, TS.STATE_PARTIAL, TS.STATE_INTACT, TS.STATE_WARN, TS.STATE_BROKEN)
    # 기준 저점 = 해당 후보의 probe.pattern_low 와 동일값 (재구현 아님)
    sig = probe.extract_signals(MT.tracker_pipe(df))
    cand = max(sig["cands"], key=lambda c: c["known_pos"])
    assert r["base"]["low"] == pytest.approx(cand["pattern_low"])
    assert TS.analyze(pd.DataFrame()) is None and TS.build_lines(None)[2].startswith("대파동 쌍바닥 후보 없음")


def test_main_wires_section_after_ma60_tracker_and_markers_into_chart():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    assert "from display.trend_structure import render_structure_section, structure_markers" in src
    alarm = src.split("with tab_alarm:", 1)[1].split("with tab_chart:", 1)[0]
    assert alarm.index("render_tracker_section(") < alarm.index("render_structure_section(df, symbol, interval)")
    assert "structure_markers=structure_markers(structure_result)" in src
    for rel in ("analysis/alarm_signals.py", "display/alarm_panel.py"):
        assert "trend_structure" not in open(os.path.join(ROOT, rel), encoding="utf-8").read()   # 알람 푸시·정의 무접촉
