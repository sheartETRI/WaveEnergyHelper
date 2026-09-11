"""§6 필수 검증 — 룩어헤드 방지.

1. (필수) 전체 구간으로 만든 상태에서 읽은 KeyChartScore(s, f, t)가,
   df[:t+1]만 잘라서 처음부터 다시 계산한 값과 **모든 t에서 일치**할 것.
   불일치가 1건이라도 나오면 백테스트를 실행하지 않는다.
2. (보조) score.add_large_stoch_layer가 원본 add_stochastic_slow_layers의
   (20,10,10) 레이어와 봉 단위로 동일할 것 — 성능을 위한 복제가 정의를 바꾸지 않았음을 강제.
3. (보조) backtest.gate_vec(벡터)와 FrameState.gate_at(스칼라)가 일치할 것.

실행: python validation/keychart/test_no_lookahead.py  (pytest로도 수집된다)
"""
from __future__ import annotations

import logging
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from indicators.stochastic import add_stochastic_slow_layers  # noqa: E402

from validation.keychart import backtest as B  # noqa: E402
from validation.keychart import data_io, score as S  # noqa: E402
from validation.keychart import params_v0 as P  # noqa: E402

# 테스트 셀 — 절단 재계산이 O(n^2)이라 구간을 제한한다(정의 검증에는 충분).
CASES = [("BTCUSDT", "1d", 1200, 900), ("BTCUSDT", "4h", 1400, 1100)]


def _state_from(df: pd.DataFrame, frame: str) -> S.FrameState:
    d = S.prepare(df)
    ev = S.extract_events(d)
    struct = S.structure_codes(d)
    lb, lt = S.last_event_maps(ev, len(d))
    bars = pd.DataFrame({
        "open_time": d.index,
        "close_time": data_io.bar_close_times(frame, d.index),
        "open": d["open"].to_numpy(float), "high": d["high"].to_numpy(float),
        "low": d["low"].to_numpy(float), "close": d["close"].to_numpy(float),
        "struct": struct, "last_bot": lb, "last_top": lt,
    })
    return S.FrameState("_", frame, bars, ev)


def _gate_tuple(state: S.FrameState, pos: int):
    g = state.gate_at(pos)
    if g is None:
        return (False, 0, float("nan"))
    return (True, g["direction"], round(g["score"], 12))


def test_layer_conformance():
    """복제한 (20,10,10) %K·피봇·패턴이 원본 3레이어 계산과 일치한다."""
    raw = data_io.load("BTCUSDT", "1d").iloc[:1500]
    mine = S.prepare(raw)
    orig = getattr(add_stochastic_slow_layers, "__wrapped__", add_stochastic_slow_layers)
    ref = orig(raw.copy())
    sfx = S.LARGE_SFX
    cols = [f"stoch_k_{sfx}", f"stoch_d_{sfx}", f"stoch_pivot_low_{sfx}",
            f"stoch_pivot_high_{sfx}", f"stoch_db_{sfx}", f"stoch_dt_{sfx}",
            f"stoch_tb_{sfx}", f"stoch_tt_{sfx}", f"stoch_neckline_{sfx}",
            f"stoch_dt_neckline_{sfx}", f"stoch_db_first_pos_{sfx}",
            f"stoch_dt_first_pos_{sfx}", f"stoch_tb_first_pos_{sfx}",
            f"stoch_tt_first_pos_{sfx}"]
    bad = []
    for c in cols:
        a = pd.to_numeric(mine[c], errors="coerce").to_numpy(float)
        b = pd.to_numeric(ref[c], errors="coerce").to_numpy(float)
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            bad.append((c, "nan-pattern"))
        elif not np.allclose(a[~np.isnan(a)], b[~np.isnan(b)], rtol=0, atol=1e-9):
            bad.append((c, "value"))
    assert not bad, f"레이어 복제 불일치: {bad}"
    print("[OK] layer conformance (14 columns)")


def test_gate_vec_matches_scalar():
    raw = data_io.load("BTCUSDT", "1d")
    st = _state_from(raw, "1d")
    pos = np.arange(len(st))
    ok, direction, sc, _e = B.gate_vec(st, pos, P.DB_RECENT_BARS, False)
    bad = 0
    for p in range(len(st)):
        want = _gate_tuple(st, p)
        got = (bool(ok[p]), int(direction[p]) if ok[p] else 0,
               round(float(sc[p]), 12) if ok[p] else float("nan"))
        if want[0] != got[0] or (want[0] and (want[1] != got[1] or abs(want[2] - got[2]) > 1e-12)):
            bad += 1
    assert bad == 0, f"gate_vec vs gate_at 불일치 {bad}건"
    print(f"[OK] gate_vec == gate_at over {len(st)} bars")


def test_no_lookahead():
    """§6-1. 전체 계산본과 t까지 절단 재계산본의 KeyChartScore가 모든 t에서 일치."""
    total_bad = 0
    for symbol, frame, n_bars, t0 in CASES:
        raw = data_io.load(symbol, frame).iloc[:n_bars]
        full = _state_from(raw, frame)
        mismatches = []
        for t in range(t0, n_bars):
            cut = _state_from(raw.iloc[:t + 1], frame)
            a, b = _gate_tuple(full, t), _gate_tuple(cut, t)
            same = a[0] == b[0] and (not a[0] or (a[1] == b[1] and abs(a[2] - b[2]) < 1e-12))
            if not same:
                mismatches.append((t, str(raw.index[t]), a, b))
        print(f"[{'OK' if not mismatches else 'FAIL'}] {symbol} {frame}: "
              f"t={t0}..{n_bars - 1} ({n_bars - t0}점) 불일치 {len(mismatches)}건")
        for m in mismatches[:10]:
            print("   ", m)
        total_bad += len(mismatches)
    assert total_bad == 0, f"룩어헤드 테스트 실패: 총 {total_bad}건 불일치"


if __name__ == "__main__":
    test_layer_conformance()
    test_gate_vec_matches_scalar()
    test_no_lookahead()
    print("\nALL PASS — 백테스트 실행 가능")
