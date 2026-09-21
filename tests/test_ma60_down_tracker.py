"""60MA 하방 전환 추적(display/ma60_down_tracker) — 검출기 import 단언 · 합성 케이스(전환/소멸/확정 시 이미 하방) ·
거울상 대칭(가격 반전 → 상승 쪽과 대응) · 상승 쪽 무접촉 · 권고 어휘 부재 · main 배선."""
import hashlib
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.ma60_down_tracker as D  # noqa: E402
import display.ma60_turn_tracker as T  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402
from indicators.moving_averages import add_moving_averages  # noqa: E402
from indicators.stochastic import add_stochastic_slow_layers  # noqa: E402

# 권고·방향성 어휘 — 본문(독스트링 제외)·렌더 문자열·요약 텍스트 어디에도 없어야 한다
FORBIDDEN_WORDS = ("매도", "매수", "숏", "공매도", "청산", "진입", "추천", "권고", "하라")


def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


# ------------------------------------------------------------ 검출기 import 소비 · 상승 쪽 무접촉
def test_down_tracker_imports_probe_double_top_path_and_does_not_reimplement():
    assert D.probe is probe and D.up is T
    body = open(D.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "probe.extract_signals(" in body and 'sig["stoch_tops"]' in body       # probe 의 쌍봉 경로 소비
    assert "up.lifecycle_rows(" in body and "up.tracker_pipe(" in body            # 창·경과 규칙은 상승 쪽 함수 호출
    for banned in ("compute_stochastic_pivots", "compute_series_pivots", "detect_double_top", "detect_stochastic_top",
                   "find_swing", "np.roll", "shift(", "rolling(", "< prev", "> prev", "diff("):
        assert banned not in body, banned
    # 알람 계층 DT 검출은 쓰지 않는다(probe 경로가 있으므로)
    assert "alarm_signals" not in body
    # 파라미터 신설 없음 — 창·최근 구간은 상승 쪽 값 그대로
    assert D.OBS_BARS == T.OBS_BARS == 20 and D.RECENT_BARS == T.RECENT_BARS == 120
    assert "OBS_BARS = up.OBS_BARS" in body and "RECENT_BARS = up.RECENT_BARS" in body


def test_up_side_module_and_probe_untouched():
    """상승 쪽 모듈은 이 라운드에서 무수정 — 직전 커밋 blob 과 동일. probe 는 매니페스트와 동일."""
    for rel, sha in T.CHERRYPICK_PROBE.items():
        local = _norm(open(os.path.join(ROOT, rel), "rb").read())
        assert hashlib.sha256(local).hexdigest() == sha
    try:
        blob = subprocess.run(["git", "show", "bc4f001:display/ma60_turn_tracker.py"], cwd=ROOT,
                              capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git 또는 원본 커밋을 읽을 수 없음")
    assert _norm(blob) == _norm(open(T.__file__, "rb").read()), "상승 쪽 display/ma60_turn_tracker.py 가 변경됨"


# ------------------------------------------------------------ 합성 프레임
def _raw(n: int = 1600, seed: int = 7) -> pd.DataFrame:
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
    return df


def _pipeline(raw: pd.DataFrame) -> pd.DataFrame:
    return add_stochastic_slow_layers(add_moving_averages(raw.copy()))


def _invert(raw: pd.DataFrame) -> pd.DataFrame:
    """가격 반전: 고·저 교환·부호 반전. 스토캐 %K 는 100−K, MA 는 −MA 가 되어 쌍봉↔쌍바닥·하방↔상방이 대응한다."""
    inv = pd.DataFrame({"open": -raw["open"], "high": -raw["low"], "low": -raw["high"], "close": -raw["close"],
                        "volume": raw["volume"]}, index=raw.index)
    inv.index.name = raw.index.name
    return inv


# ------------------------------------------------------------ 거울상 대칭 (같은 입력을 가격 반전 → 상승 쪽과 대응)
@pytest.mark.parametrize("seed", [7, 11, 23])
def test_price_inversion_maps_down_tracker_onto_up_tracker(seed):
    raw = _raw(seed=seed)
    down = D.track_candidates(_pipeline(raw), recent_bars=len(raw)).set_index("확정 시각")
    up_inv = T.track_candidates(_pipeline(_invert(raw)), recent_bars=len(raw)).set_index("확정 시각")
    assert len(down) >= 20 and set(down.index) == set(up_inv.index)
    for ts in down.index:
        a, b = down.loc[ts], up_inv.loc[ts]
        assert a["상태"] == b["상태"] and a[D.ELAPSED_COL] == b[T.ELAPSED_COL]
        assert a[D.HIGH_COL] == pytest.approx(-b["패턴 저점"])
        assert (a["확정 시 60MA"] == D.ALREADY_DOWN_MARK) == (b["확정 시 60MA"] == T.ALREADY_UP_MARK)
        assert D._DIR_MIRROR[b["60MA 현재"]] == a["60MA 현재"]
        if a["상태"] == D.STATUS_TURNED:
            assert pd.Timestamp(a["전환 시각"]) == pd.Timestamp(b["전환 시각"])
            assert a["전환 시 가격"] == pytest.approx(-b["전환 시 가격"])
        if a["상태"] == D.STATUS_EXPIRED:
            assert pd.Timestamp(a["소멸 시각"]) == pd.Timestamp(b["소멸 시각"])
    # 창 안 '전환 발생' 과 '소멸' 이 모두 표본에 있어야 대칭 검사가 의미 있다
    assert (down["상태"] == D.STATUS_TURNED).sum() >= 3 and (down["상태"] == D.STATUS_EXPIRED).sum() >= 3


def test_mirror_signal_direction_is_exact_negation_of_probe_flags():
    """MA60 부호 반전 프레임의 probe 출력 = 실제 하방·하방 전환. 표시 계층이 기울기를 다시 계산하지 않음을 값으로 확인."""
    pipe = D.tracker_pipe(_pipeline(_raw()))
    sig_up = probe.extract_signals(pipe)
    sig_dn = D.extract_mirror_signals(pipe)
    ma = pd.to_numeric(pipe["MA60"], errors="coerce").to_numpy(dtype=float)
    valid = sig_up["ma60_valid"]
    # 유효 구간에서 상방·하방은 배타적이며 (MA60 == 직전 값 인 봉만 둘 다 아님), 전환은 하방 시작 봉
    assert not (sig_up["ma60_up"] & sig_dn["ma60_up"]).any()
    strictly_down = np.zeros_like(valid); strictly_down[1:] = ma[1:] < ma[:-1]
    assert np.array_equal(sig_dn["ma60_up"] & valid, strictly_down & valid)
    assert np.array_equal(sig_dn["ma60_valid"], valid)
    assert sig_dn["ma60_turn"].sum() > 0 and not (sig_dn["ma60_turn"] & sig_up["ma60_turn"]).any()
    # 후보는 probe 의 쌍봉 경로(stoch_tops) 부분집합이며 패턴 고점은 첫~둘째 봉우리 구간 high 최대
    tops = {t["confirm_pos"]: t for t in sig_up["stoch_tops"]}
    high = pipe["high"].to_numpy(dtype=float)
    assert len(sig_dn["cands"]) >= 20
    for cd in sig_dn["cands"]:
        assert cd["confirm_pos"] in tops and cd["known_pos"] == tops[cd["confirm_pos"]]["known_pos"]
        assert cd["p1"] < cd["p2"] <= cd["confirm_pos"]
        assert cd["pattern_low"] == pytest.approx(np.nanmax(high[cd["p1"]:cd["p2"] + 1]))


# ------------------------------------------------------------ 합성 케이스 — 전환 / 소멸 / 확정 시 이미 하방
def _sig(n, cands, down_at=(), turn_at=()):
    """거울 공간 sig: ma60_up = 실제 하방, ma60_turn = 실제 하방 전환."""
    up = np.zeros(n, dtype=bool); up[list(down_at)] = True
    turn = np.zeros(n, dtype=bool); turn[list(turn_at)] = True
    return {"cands": cands, "ma60_up": up, "ma60_turn": turn, "ma60_valid": np.ones(n, dtype=bool)}


def _cand(c, lag=0, high=100.0):
    return {"confirm_pos": c, "known_pos": c + lag, "lag": lag, "p1": c - 5, "p2": c - 1, "pattern_low": high}


def test_synthetic_cases_turned_expired_waiting_and_already_down():
    n = 60
    idx = pd.date_range("2026-09-18 00:00", periods=n, freq="h")
    close = np.linspace(110, 100, n)
    # A: 확정 c=10, 하방 전환 t=14 → 전환 발생, 소요 4/20
    # B: 확정 c=20, 창 안 전환 없음, 창 종료 40 ≤ last → 소멸 20/20
    # C: 확정 c=50, 아직 창 안(last=59) → 대기 9/20
    # D: 확정 c=42, 가용 지연 1(k=43), 전환 t=47 → 소요 5/21 (가용 +1봉)
    # E: 확정 c=22, 가용 시점에 이미 하방(down_at 22) → '이미 하방' 표기, 창 [22,42] 안 새 전환 없음 → 소멸
    rows = D.lifecycle_rows(
        _sig(n, [_cand(10), _cand(20), _cand(50), _cand(42, lag=1), _cand(22, high=123.0)],
             down_at=(14, 15, 22, 23, 47, 59), turn_at=(14, 47)),
        idx, close, recent_bars=n)
    by = {int(r["_confirm_pos"]): r for r in rows}
    assert by[10]["상태"] == D.STATUS_TURNED and by[10][D.ELAPSED_COL] == "4/20"
    assert by[10]["전환 시각"] == idx[14] and by[10]["전환 시 가격"] == pytest.approx(close[14])
    assert by[20]["상태"] == D.STATUS_EXPIRED and by[20][D.ELAPSED_COL] == "20/20" and by[20]["소멸 시각"] == idx[40]
    assert by[50]["상태"] == D.STATUS_WAITING and by[50][D.ELAPSED_COL] == "9/20" and by[50]["60MA 현재"] == "하방"
    assert by[42]["상태"] == D.STATUS_TURNED and by[42][D.ELAPSED_COL] == "5/21 (가용 +1봉)"
    assert by[22]["확정 시 60MA"] == D.ALREADY_DOWN_MARK and by[22]["상태"] == D.STATUS_EXPIRED
    assert by[22][D.HIGH_COL] == 123.0 and "패턴 저점" not in by[22] and "기준선(×0.995)" not in by[22]
    assert by[10]["확정 시 60MA"] == "상방" and by[20]["확정 시 60MA"] == "상방"     # 확정 시 상방이던 건(거울 라벨 복원)
    assert set(D.COLUMNS) - {D.TF_COL} <= set(by[10])
    # 상승 쪽 함수를 같은 sig 로 호출한 결과와 상태·경과·시각이 동일(라벨만 다름)
    ref = {int(r["_confirm_pos"]): r for r in T.lifecycle_rows(
        _sig(n, [_cand(10), _cand(20), _cand(50), _cand(42, lag=1), _cand(22, high=123.0)],
             down_at=(14, 15, 22, 23, 47, 59), turn_at=(14, 47)), idx, close, recent_bars=n)}
    for c, r in by.items():
        assert (r["상태"], r[D.ELAPSED_COL], r["전환 시각"], r["소멸 시각"]) == \
               (ref[c]["상태"], ref[c][T.ELAPSED_COL], ref[c]["전환 시각"], ref[c]["소멸 시각"])
        assert r[D.HIGH_COL] == ref[c]["패턴 저점"]
        assert (r["확정 시 60MA"] == D.ALREADY_DOWN_MARK) == (ref[c]["확정 시 60MA"] == T.ALREADY_UP_MARK)


def test_summary_counts_already_down_separately_and_rate_uses_finished_only():
    f = pd.DataFrame({
        "상태": [D.STATUS_TURNED, D.STATUS_EXPIRED, D.STATUS_EXPIRED, D.STATUS_WAITING],
        "확정 시 60MA": [D.ALREADY_DOWN_MARK, "상방", "상방", "상방"],
    })
    s = D.summarize(f)
    assert (s["turned"], s["expired"], s["waiting"], s["already_down"]) == (1, 2, 1, 1)
    assert s["rate"] == pytest.approx(1 / 3)
    line = D.summary_line(f)
    assert "하방 전환 1건 / 소멸 2건 / 대기 1건" in line and "1/3 = 33%" in line and "이미 하방 1건" in line
    assert D.summarize(pd.DataFrame(columns=D.COLUMNS))["rate"] is None


# ------------------------------------------------------------ 표기 규율
def test_labels_unverified_no_up_side_rate_and_no_recommendation_words():
    assert D.SECTION_TITLE == "60MA 하방 전환 추적 (미검증)"
    assert D.FIXED_CAPTION == "현물 보유 시 참고용 관측입니다. 하방 전환의 전환율은 측정된 바 없습니다."
    body = open(D.__file__, encoding="utf-8").read().split('"""', 2)[2]
    # 상승 쪽 계측 수치(40.7% / 41.3% / 60%)를 이쪽에 쓰지 않는다
    for s in ("40.7", "41.3", "60%", "PROBE_RATES", "FIXED_CAPTION = up."):
        assert s not in body, s
    for w in FORBIDDEN_WORDS:
        assert w not in body, w
    df = _pipeline(_raw())
    text = "\n".join(D.build_lines(D.track_candidates(df, recent_bars=len(df))))
    for w in FORBIDDEN_WORDS:
        assert w not in text, w
    assert "(미검증)" in text and D.FIXED_CAPTION in text and "하방 전환 " in text
    assert D.STATUS_TURNED == "전환 발생"


def test_display_frame_columns_and_formats():
    f = pd.DataFrame([{
        "상태": D.STATUS_TURNED, "확정 시각": pd.Timestamp("2026-09-18 08:00"), D.ELAPSED_COL: "1/20",
        "60MA 현재": "하방", "확정 시 60MA": "상방", "전환 시각": pd.Timestamp("2026-09-18 12:00"),
        "전환 시 가격": 80725.6, D.HIGH_COL: 84967.97, "소멸 시각": pd.NaT,
    }])
    d = D.display_frame(f, "BTCUSDT", "4h")
    assert list(d.columns) == list(D.COLUMNS) and "패턴 저점" not in d.columns and "기준선(×0.995)" not in d.columns
    assert d.iloc[0].tolist()[:4] == ["BTCUSDT 4h", D.STATUS_TURNED, "2026-09-18 17:00", "1/20"]
    assert d.loc[0, D.HIGH_COL] == "84,967.97" and d.loc[0, "소멸 시각"] == ""
    assert "None" not in d.to_string() and set(D.TABLE_COLUMN_WIDTHS) <= set(D.COLUMNS)


def test_empty_or_unprepared_frame_is_safe():
    assert D.track_candidates(None).empty and D.track_candidates(pd.DataFrame()).empty
    raw = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    assert D.track_candidates(raw).empty
    assert D.build_lines(D.track_candidates(raw))[2] == "해당 구간에 대파동 쌍봉 후보 없음"


# ------------------------------------------------------------ main 배선 · 알람 정의 무접촉
def test_main_wires_down_section_next_to_up_section_without_chart_or_alarm_hooks():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    assert "from display.ma60_down_tracker import render_down_tracker_section" in src
    alarm_block = src.split("with tab_alarm:", 1)[1].split("with tab_chart:", 1)[0]
    i_up = alarm_block.index("render_tracker_section(df, symbol, interval)")
    i_dn = alarm_block.index("render_down_tracker_section(df, symbol, interval)")
    assert i_up < i_dn < alarm_block.index("render_structure_section(")
    chart_block = src.split("with tab_chart:", 1)[1]
    assert "down" not in chart_block                        # 차트 가격선·마커 연동 없음
    for fn in ("analysis/alarm_signals.py", "display/alarm_panel.py"):
        assert "ma60_down" not in open(os.path.join(ROOT, fn), encoding="utf-8").read()
