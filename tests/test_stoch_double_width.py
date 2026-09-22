"""스토캐 쌍봉/쌍바닥 — 폭 비교 정의(2026-09-22) 단위 테스트.

정의(indicators/stochastic.py 모듈 주석):
  쌍봉 = 과매수권(K ≥ 80)에 들어간 첫 봉우리가 과매수권을 벗어난 뒤 두 번째 봉우리를 만들되, 두 번째 봉우리의
  폭(정점 전후 대칭 폭: K ≥ 정점 − width_drop 에 머문 연속 봉 수)이 첫 번째보다 짧아야 한다. 두 번째 봉우리는
  과매수권 재진입이 필수가 아니다. 확정 봉 = K < min(80, 정점2 − width_drop) 이 처음 성립하는 봉. 쌍바닥은 대칭.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import STOCH_DOUBLE_PARAMS, STOCH_PIVOT_PARAMS  # noqa: E402
from indicators.stochastic import (  # noqa: E402
    compute_stochastic_pivots,
    detect_stochastic_bottom_patterns,
    detect_stochastic_top_patterns,
)

S = "x"
DROP = STOCH_DOUBLE_PARAMS["width_drop"]


def _seg(*parts):
    return np.concatenate([np.asarray(p, dtype=float) for p in parts])


def _plateau(v, n):
    return np.full(n, float(v))


def _ramp(a, b, n):
    return np.linspace(a, b, n, endpoint=False)


def _frame(k):
    df = pd.DataFrame({f"stoch_k_{S}": k}, index=pd.date_range("2026-01-01", periods=len(k), freq="h"))
    lo, hi = compute_stochastic_pivots(df[f"stoch_k_{S}"], **STOCH_PIVOT_PARAMS)
    df[f"stoch_pivot_low_{S}"] = lo
    df[f"stoch_pivot_high_{S}"] = hi
    return df


def _tops(k):
    df = detect_stochastic_top_patterns(_frame(k), S)
    hits = df[df[f"stoch_dt_{S}"].notna()]
    return df, [(int(df.index.get_loc(ts)), float(r[f"stoch_dt_{S}"]), r[f"stoch_dt_kind_{S}"],
                 float(r[f"stoch_dt_neckline_{S}"]), int(r[f"stoch_dt_first_pos_{S}"])) for ts, r in hits.iterrows()]


def _bottoms(k):
    df = detect_stochastic_bottom_patterns(_frame(k), S)
    hits = df[df[f"stoch_db_{S}"].notna()]
    return df, [(int(df.index.get_loc(ts)), float(r[f"stoch_db_{S}"]), r[f"stoch_db_kind_{S}"],
                 float(r[f"stoch_neckline_{S}"]), int(r[f"stoch_db_first_pos_{S}"])) for ts, r in hits.iterrows()]


# 김박사 화면 사례: 과매수권 둥근 봉우리 하나 — 쌍봉 아님
SINGLE = _seg(_ramp(30, 92, 15), _plateau(92, 12), _ramp(92, 60, 12), _plateau(60, 5))
# 고전적 쌍봉: 첫 봉우리 정점 92·폭 12, 골 70(과매수 이탈), 두 번째 정점 88·폭 5
CLASSIC = _seg(_ramp(30, 92, 15), _plateau(92, 12), _ramp(92, 70, 8), _plateau(70, 3),
               _ramp(70, 88, 6), _plateau(88, 5), _ramp(88, 50, 12), _plateau(50, 5))
# 두 번째 봉우리가 더 넓다(정점 92·폭 5 → 정점 88·폭 12)
WIDE_SECOND = _seg(_ramp(30, 92, 15), _plateau(92, 5), _ramp(92, 70, 8), _plateau(70, 3),
                   _ramp(70, 88, 6), _plateau(88, 12), _ramp(88, 50, 12), _plateau(50, 5))
# 두 번째 봉우리가 과매수 미달(정점 74·폭 4)
SUB80_SECOND = _seg(_ramp(30, 92, 15), _plateau(92, 12), _ramp(92, 55, 10), _plateau(55, 3),
                    _ramp(55, 74, 6), _plateau(74, 4), _ramp(74, 40, 12), _plateau(40, 5))
# 골이 얕아(85) 과매수권을 벗어나지 않음 → 별개 봉우리가 아니다
SHALLOW = _seg(_ramp(30, 92, 15), _plateau(92, 12), _ramp(92, 85, 4), _plateau(85, 2),
               _ramp(85, 90, 3), _plateau(90, 3), _ramp(90, 50, 12), _plateau(50, 5))


def test_single_overbought_peak_is_not_double_top():
    assert _tops(SINGLE)[1] == []


def test_classic_double_top_confirms_at_exit_bar_with_width_rule():
    df, hits = _tops(CLASSIC)
    assert len(hits) == 1
    pos, k_at, kind, neck, first_pos = hits[0]
    assert kind == "LH" and first_pos == 15                  # 첫 봉우리 정점(92)의 첫 봉
    assert neck == min(80.0, 88.0 - DROP)                    # 확정 기준선 = min(80, 정점2 − drop)
    assert CLASSIC[pos] < neck <= CLASSIC[pos - 1]           # 기준선을 처음 하향 이탈한 봉
    # 후보 표기는 두 번째 정점 봉에, 확정 전까지만
    cand = df[df[f"stoch_dt_candidate_{S}"].notna()]
    assert len(cand) == 1 and cand[f"stoch_dt_{S}"].isna().all()
    assert int(df.index.get_loc(cand.index[0])) < pos


def test_wider_second_peak_is_rejected():
    assert _tops(WIDE_SECOND)[1] == []


def test_second_peak_below_overbought_still_counts_and_confirms_at_width_edge():
    df, hits = _tops(SUB80_SECOND)
    assert len(hits) == 1
    pos, k_at, kind, neck, first_pos = hits[0]
    assert neck == 74.0 - DROP and kind == "LH"
    assert SUB80_SECOND[pos] < neck <= SUB80_SECOND[pos - 1]


def test_shallow_valley_that_stays_overbought_is_one_peak():
    assert _tops(SHALLOW)[1] == []


def test_bottom_is_exact_mirror_of_top():
    _, tops = _tops(CLASSIC)
    _, bottoms = _bottoms(100.0 - CLASSIC)
    assert [(p, round(100 - k, 6), fp) for p, k, _, _, fp in tops] == \
           [(p, round(k, 6), fp) for p, k, _, _, fp in bottoms]
    assert [kind for _, _, kind, _, _ in bottoms] == ["HL"]
    assert [round(100 - n, 6) for _, _, _, n, _ in tops] == [round(n, 6) for _, _, _, n, _ in bottoms]


def test_width_drop_parameter_changes_width_measurement():
    """width_drop 를 키우면 폭 구간이 넓어져 같은 파동이라도 판정이 달라질 수 있다 — 파라미터가 실제로 쓰인다."""
    df = _frame(CLASSIC)
    tight = detect_stochastic_top_patterns(df.copy(), S)
    loose = detect_stochastic_top_patterns(df.copy(), S, overbought_level=80.0)
    assert tight[f"stoch_dt_{S}"].equals(loose[f"stoch_dt_{S}"])
    from indicators.stochastic import detect_double_top_patterns
    wide = detect_double_top_patterns(df.copy(), f"stoch_k_{S}", f"stoch_pivot_high_{S}", "dt", "c", "n",
                                      width_drop=40.0)
    # drop=40 이면 두 번째 봉우리 폭 구간(K≥48)이 골(70)을 삼켜 첫 봉우리와 이어진다 → 별개 봉우리 아님
    assert wide["dt"].notna().sum() == 0
