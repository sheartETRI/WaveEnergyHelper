"""섀도 추적 배선 테스트 — 기록 전용 규율의 검증.

- lookahead 차단 (STRUCT reference_low 는 이벤트 시점 이전 확정 swing 만)
- append-only 불변식 (재실행 시 기존 행 불변)
- 세 변형이 동일 이벤트 집합을 소비 (손절만 다름)
- 미검출·퇴화 폴백
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.mm_shadow import (
    LTF_TO_PAIR,
    SHADOW_COLS,
    VARIANTS,
    append_shadow,
    load_shadow_events,
    simulate_variants,
    variant_summary,
)
from analysis.wave_align_gate_forward import INTEGRITY_FILES, TRACKING_START
from analysis.wave_mm_simulator import EXIT_STOP, EXIT_TIME, STOP_PCT, TRANCHE_PCT
from analysis.wave_mm_struct_stop import BUFFER, REASON_DEGENERATE, REASON_NO_LOW, struct_stops
from analysis.wave_structure_confirmation import PIVOT


def _ramp(n, step=0.1, base=100.0):
    """동률 pivot 을 피하는 단조 증가 저가 baseline."""
    return [base + i * step for i in range(n)]


def _bars(lows, closes=None, opens=None, freq="6h", start="2026-09-01"):
    n = len(lows)
    closes = closes if closes is not None else [100.0] * n
    opens = opens if opens is not None else closes
    df = pd.DataFrame({
        "open": opens, "high": [c * 1.02 for c in closes], "low": lows,
        "close": closes, "volume": [1.0] * n,
    }, index=pd.date_range(start, periods=n, freq=freq))
    df.index.name = "open_time"
    return df


def _events(idxs, bars, symbol="BTCUSDT", ltf="6h"):
    return pd.DataFrame({
        "event_id": [f"E{i}" for i in idxs],
        "timestamp": [bars.index[i] for i in idxs],
        "symbol": symbol, "ltf": ltf, "pair": LTF_TO_PAIR[ltf],
    })


# ------------------------------------------------------------ 헌장·구성 동결
def test_variants_and_sizing_are_frozen():
    assert VARIANTS == ("BASE", "NOSTOP", "STRUCT")
    assert TRANCHE_PCT == 5.0
    assert STOP_PCT == 3.0
    assert BUFFER == 0.005


def test_shadow_module_is_not_part_of_the_f2b_integrity_surface():
    """섀도는 신규 파일이며 §6 전방 추적의 감사 대상에 끼어들지 않는다."""
    assert "analysis/mm_shadow.py" not in INTEGRITY_FILES
    assert "validation/wave_mm_shadow.csv" not in INTEGRITY_FILES


def test_mini_charter_is_frozen_in_the_module_docstring():
    import analysis.mm_shadow as MS

    doc = MS.__doc__
    assert "판정이 아니며 임계값을 갖지 않는다" in doc
    assert "2027-03" in doc
    assert "섀도 리셋 사유" in doc
    assert "append-only" in doc


# ------------------------------------------------------ lookahead 차단 (필수)
def test_struct_reference_low_never_uses_unconfirmed_or_future_lows():
    """F2-b 배선의 close_time < t 테스트와 같은 형식의 차단 검증."""
    lows = _ramp(40)
    lows[10] = 90.0            # 확정에 PIVOT 봉이 더 필요
    lows[30] = 50.0            # 신호 이후의 더 깊은 저점 — 절대 참조 금지
    bars = _bars(lows)

    early = struct_stops(_events([10 + PIVOT - 1], bars), {("BTCUSDT", "6h"): bars}).iloc[0]
    assert early["reference_low"] != pytest.approx(90.0)

    late = struct_stops(_events([10 + PIVOT], bars), {("BTCUSDT", "6h"): bars}).iloc[0]
    assert late["reference_low"] == pytest.approx(90.0)

    after = struct_stops(_events([20], bars), {("BTCUSDT", "6h"): bars}).iloc[0]
    assert after["reference_low"] == pytest.approx(90.0)   # 30번 저점은 미참조


def test_struct_reference_index_is_always_before_the_signal_bar():
    lows = _ramp(60)
    for i in (8, 20, 35):
        lows[i] = 90.0 - i * 0.1
    bars = _bars(lows)
    ev = _events([25, 40, 50], bars)
    out = struct_stops(ev, {("BTCUSDT", "6h"): bars})
    for row in out.itertuples():
        pos = int(bars.index.get_loc(pd.Timestamp(row.timestamp)))
        assert row.reference_idx + PIVOT <= pos, row.event_id


# ------------------------------------------- 세 변형이 같은 이벤트를 소비
def test_all_variants_consume_the_same_candidate_events():
    lows = _ramp(80)
    lows[5] = 88.0
    for i in range(25, 35):
        lows[i] = 96.0          # −4% 하락 — BASE 는 손절, STRUCT 는 미도달
    bars = _bars(lows, opens=[100.0] * 80)
    ev = _events([10], bars)
    out = simulate_variants(ev, {("BTCUSDT", "6h"): bars})

    assert set(out["variant"]) == set(VARIANTS)
    # 진입 후보가 하나뿐이므로 세 변형 모두 같은 event_id 를 체결한다
    for variant in VARIANTS:
        sub = out[out["variant"] == variant]
        assert list(sub["event_id"]) == ["E10"]
        assert sub.iloc[0]["entry_ts"] == bars.index[11]
        assert sub.iloc[0]["size_pct"] == pytest.approx(TRANCHE_PCT)

    reasons = dict(zip(out["variant"], out["exit_reason"]))
    assert reasons["BASE"] == EXIT_STOP        # −3% 는 걸린다
    assert reasons["STRUCT"] == EXIT_TIME      # 구조선(88×0.995)은 미도달
    assert reasons["NOSTOP"] == EXIT_TIME


def test_variants_differ_only_in_the_stop_rule():
    lows = _ramp(60)
    lows[5] = 80.0
    bars = _bars(lows, opens=[100.0] * 60)
    ev = _events([10], bars)
    out = simulate_variants(ev, {("BTCUSDT", "6h"): bars}).set_index("variant")
    # 진입가·사이즈는 동일, 손절선만 다르다
    assert out.loc["BASE", "entry_price"] == out.loc["STRUCT", "entry_price"]
    assert out.loc["BASE", "stop_pct_used"] == pytest.approx(STOP_PCT)
    assert out.loc["STRUCT", "stop_pct_used"] > STOP_PCT   # 깊은 저점 → 더 넓은 손절
    assert pd.isna(out.loc["NOSTOP", "stop_pct_used"])


# ------------------------------------------------------------ 폴백 케이스
def test_struct_falls_back_to_base_when_no_confirmed_low():
    bars = _bars(_ramp(60), opens=[100.0] * 60)   # 확정 저점 없음
    ev = _events([3], bars)
    stops = struct_stops(ev, {("BTCUSDT", "6h"): bars})
    assert stops.iloc[0]["reason"] == REASON_NO_LOW
    out = simulate_variants(ev, {("BTCUSDT", "6h"): bars}).set_index("variant")
    assert out.loc["STRUCT", "stop_pct_used"] == pytest.approx(STOP_PCT)


def test_struct_falls_back_to_base_on_degenerate_stop():
    # 20봉 시간 청산이 프레임 안에 들어오도록 충분히 길게
    lows = _ramp(60, base=101.0)
    lows[5] = 99.9                                 # 저점이 진입가 위
    bars = _bars(lows, closes=[100.0] * 60, opens=[99.0] * 60)
    ev = _events([20], bars)
    stops = struct_stops(ev, {("BTCUSDT", "6h"): bars})
    assert stops.iloc[0]["reason"] == REASON_DEGENERATE
    out = simulate_variants(ev, {("BTCUSDT", "6h"): bars}).set_index("variant")
    assert out.loc["STRUCT", "stop_pct_used"] == pytest.approx(STOP_PCT)


# ------------------------------------------------------- append-only 불변식
def _rows(n, variant="BASE", offset=0):
    return pd.DataFrame({
        "variant": variant,
        "event_id": [f"E{i + offset}" for i in range(n)],
        "net_ret": [0.01] * n, "log_growth": [0.0005] * n,
        "exit_reason": [EXIT_TIME] * n,
        "signal_ts": pd.date_range("2026-09-01", periods=n, freq="6h"),
        "exit_ts": pd.date_range("2026-09-06", periods=n, freq="6h"),
    })


def test_append_only_never_changes_existing_rows(tmp_path):
    path = str(tmp_path / "shadow.csv")
    first = _rows(3)
    r1 = append_shadow(first, path)
    assert (r1["existing"], r1["appended"], r1["total"]) == (0, 3, 3)
    before = pd.read_csv(path)

    # 같은 행을 다시 넣어도 아무것도 바뀌지 않는다
    r2 = append_shadow(first, path)
    assert (r2["appended"], r2["total"]) == (0, 3)
    pd.testing.assert_frame_equal(pd.read_csv(path), before)


def test_append_only_adds_new_rows_and_preserves_old(tmp_path):
    path = str(tmp_path / "shadow.csv")
    append_shadow(_rows(3), path)
    before = pd.read_csv(path)
    r = append_shadow(_rows(2, offset=10), path)
    assert (r["existing"], r["appended"], r["total"]) == (3, 2, 5)
    after = pd.read_csv(path)
    pd.testing.assert_frame_equal(after.iloc[:3].reset_index(drop=True), before)


def test_append_key_is_variant_plus_event_id(tmp_path):
    """같은 event_id 라도 변형이 다르면 별개 행이다."""
    path = str(tmp_path / "shadow.csv")
    append_shadow(_rows(2, variant="BASE"), path)
    r = append_shadow(_rows(2, variant="STRUCT"), path)
    assert r["appended"] == 2
    df = pd.read_csv(path)
    assert set(df["variant"]) == {"BASE", "STRUCT"}
    assert len(df) == 4


def test_append_of_empty_frame_is_a_noop(tmp_path):
    path = str(tmp_path / "shadow.csv")
    append_shadow(_rows(2), path)
    before = pd.read_csv(path)
    r = append_shadow(pd.DataFrame(), path)
    assert r["appended"] == 0
    pd.testing.assert_frame_equal(pd.read_csv(path), before)


# ------------------------------------------------------------ 모집단 필터
def test_shadow_events_take_only_gate_open_promoted_rows_after_start(tmp_path, monkeypatch):
    import analysis.mm_shadow as MS

    sidecar = pd.DataFrame({
        "event_id": ["A", "B", "C", "D"],
        "timestamp": [TRACKING_START + pd.Timedelta(days=1)] * 3
                     + [TRACKING_START - pd.Timedelta(days=1)],
        "symbol": "BTCUSDT",
        "timeframe": ["1h", "1h", "6h", "1h"],
        "gate_align": ["True", "False", "True", "True"],
        "gate_scope": ["PROMOTED", "PROMOTED", "NOT_PROMOTED", "PROMOTED"],
    })
    path = str(tmp_path / "gate.csv")
    sidecar.to_csv(path, index=False)
    monkeypatch.setattr(MS, "gate_sidecar_path", lambda: path)

    ev = load_shadow_events()
    assert list(ev["event_id"]) == ["A"]      # 게이트 닫힘·비승격·추적 이전 제외
    assert ev.iloc[0]["pair"] == "PAIR_B"


def test_variant_summary_reports_the_charter_fields():
    lows = _ramp(60)
    lows[5] = 80.0
    bars = _bars(lows, opens=[100.0] * 60)
    out = simulate_variants(_events([10], bars), {("BTCUSDT", "6h"): bars})
    rows = variant_summary(out)
    assert [r["variant"] for r in rows] == list(VARIANTS)
    for r in rows:
        assert set(("trades", "stop_rate", "growth")) <= set(r) or r["trades"] == 0
