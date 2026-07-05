"""기법1 캠페인 상태 기계 리플레이 테스트 (§5).

합성 파이프라인+MACD 프레임으로 S0→S7 전 전이를 구동한다. MACD signal=0 고정,
macd 부호 전환으로 GC/DC를 결정론적으로 발생시킨다.

실행: `python -m pytest tests/test_campaign_state_machine.py` 또는 직접 실행
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_state_machine import (
    DONE,
    S1_CONFIRM,
    S5_WAVE2,
    S7_WAVE3,
    macd_cross_at,
    replay_campaign,
)

N = 30
SFX_MID = "(10,5,5)"
SFX_LARGE = "(20,10,10)"


def _base_frame(macd_vals):
    idx = pd.date_range("2026-01-01", periods=N, freq="4h")
    df = pd.DataFrame(
        {
            "close": 100.0 + np.arange(N),
            "high": 110.0,
            "low": 60.0,
            "macd": macd_vals,
            "macd_signal": 0.0,
            "MA10": 55.0,
            "MA20": 50.0,
            "MA60": 30.0,
            "MA120": 20.0,
        },
        index=idx,
    )
    return df


def _na_col():
    return pd.array([pd.NA] * N, dtype="Float64")


def _long_full_frame():
    # GC@5, DC@8, GC@11 (signal=0 기준 부호전환)
    m = [-1.0] * N
    for p in range(5, 8):
        m[p] = 1.0        # 5,6,7 양수 → GC@5
    m[8] = -1.0; m[9] = -1.0; m[10] = -1.0   # DC@8, 이후 음수
    for p in range(11, N):
        m[p] = 1.0        # GC@11, 이후 양수
    df = _base_frame(m)
    # 조정 주도 스토캐 쌍봉(중파동)@10 → grade mid, 구간 MA20~60(얕은 MA20)
    df[f"stoch_dt_{SFX_MID}"] = _na_col()
    df.loc[df.index[10], f"stoch_dt_{SFX_MID}"] = 78.0
    # 구간 도달: 저가 ≤ MA20(50) @12 (그 전엔 60 > 50)
    df.loc[df.index[12], "low"] = 40.0
    # S7 청산: 대파동 스토캐 쌍봉@16
    df[f"stoch_dt_{SFX_LARGE}"] = _na_col()
    df.loc[df.index[16], f"stoch_dt_{SFX_LARGE}"] = 82.0
    return df


def test_macd_cross_detection():
    df = _base_frame([-1.0, -1.0, 1.0, 1.0, -1.0] + [0.0] * (N - 5))
    assert macd_cross_at(df, 2) == "gc"    # -1 → 1
    assert macd_cross_at(df, 4) == "dc"    # 1 → -1
    assert macd_cross_at(df, 3) is None
    assert macd_cross_at(df, 0) is None    # 이전봉 없음


def test_long_full_cycle_reaches_done():
    df = _long_full_frame()
    res = replay_campaign(df, "BTCUSDT", "4h", "long", setup_pos=3,
                          setup_layer="MA10", setup_first_pos=1)
    assert res.state == DONE and res.is_closed()
    assert res.entry1 is not None and res.entry1.pos == 5 and res.entry1.action == "BUY"
    assert res.exit1 is not None and res.exit1.pos == 8 and res.exit1.action == "SELL"
    assert res.predicted_grade == "mid"
    assert res.predicted_region_ma == (20, 60)
    assert res.predicted_region_label == "MA20~60"
    assert res.entry2 is not None and res.entry2.pos == 12 and res.entry2.action == "BUY"
    assert res.exit_final is not None and res.exit_final.pos == 16
    # 상태 순서 보증
    states = [s for s, _ in res.timeline]
    for st in ("S0_SETUP", "S1_CONFIRM", "S2_ENTRY1", "S3_WAVE1",
               "S4_EXIT1", "S5_WAVE2", "S6_ENTRY2", "S7_WAVE3", DONE):
        assert st in states


def test_no_gc_stays_in_confirm():
    # macd 계속 음수 → GC 없음 → S1 정체, 진입 없음
    df = _base_frame([-1.0] * N)
    res = replay_campaign(df, "BTCUSDT", "4h", "long", setup_pos=3, setup_layer="MA10")
    assert res.state == S1_CONFIRM
    assert res.entry1 is None


def test_reentry_has_no_invalidation_on_low_break():
    # 저점 이탈(저가 40 < setup_low 60)에도 재진입은 취소되지 않는다 (★무효화 없음)
    df = _long_full_frame()
    res = replay_campaign(df, "BTCUSDT", "4h", "long", setup_pos=3,
                          setup_layer="MA10", setup_first_pos=1)
    assert res.setup_pattern_low == 60.0
    assert res.entry2 is not None            # setup_low 아래로 이탈했어도 재진입 발생
    assert res.entry2.price < res.setup_pattern_low + 1000  # 재진입은 발생함이 핵심


def test_region_undetermined_without_correction_stoch():
    # 조정 스토캐 쌍봉이 없으면 구간 "미정", 재진입 불가(구간 도달 판정 자체가 스킵)
    df = _long_full_frame()
    df[f"stoch_dt_{SFX_MID}"] = _na_col()      # 조정 주도(중) 제거
    df[f"stoch_dt_{SFX_LARGE}"] = _na_col()    # S7용 대파동 dt도 제거(S5서 조정으로 소비되므로)
    res = replay_campaign(df, "BTCUSDT", "4h", "long", setup_pos=3, setup_layer="MA10")
    assert res.predicted_grade is None
    assert res.predicted_region_label == "미정"
    assert res.entry2 is None
    assert res.state == S5_WAVE2             # S5에서 무기한 대기


def test_strength_flag_from_stoch_triple():
    # setup 봉에 스토캐 삼중바닥(대체 강화 신호) 동시 확정
    df = _long_full_frame()
    df[f"stoch_tb_{SFX_LARGE}"] = _na_col()
    df.loc[df.index[3], f"stoch_tb_{SFX_LARGE}"] = 15.0
    res = replay_campaign(df, "BTCUSDT", "4h", "long", setup_pos=3, setup_layer="MA10")
    assert res.strength_flag is True
    assert res.strength_layer == SFX_LARGE


def _short_full_frame():
    # 매도(현물) 미러: confirm=DC, exit1=GC, reentry=GC
    # DC@5, GC@8, GC@11
    m = [1.0] * N
    for p in range(5, 8):
        m[p] = -1.0       # DC@5
    m[8] = 1.0; m[9] = 1.0; m[10] = 1.0      # GC@8
    for p in range(11, N):
        m[p] = 1.0
    # pos10을 음수로 만들어 GC@11 성립
    m[10] = -1.0
    df = _base_frame(m)
    # 조정 주도 스토캐 쌍바닥(중)@10, 상단 도달(고가 ≥ MA20) @12
    df[f"stoch_db_{SFX_MID}"] = _na_col()
    df.loc[df.index[10], f"stoch_db_{SFX_MID}"] = 22.0
    df.loc[df.index[12], "high"] = 60.0      # ≥ MA20(50)
    # S7 청산: 대파동 스토캐 쌍바닥@16
    df[f"stoch_db_{SFX_LARGE}"] = _na_col()
    df.loc[df.index[16], f"stoch_db_{SFX_LARGE}"] = 18.0
    return df


def test_short_campaign_mirror_cycle():
    df = _short_full_frame()
    res = replay_campaign(df, "ETHUSDT", "1d", "short", setup_pos=3,
                          setup_layer="MA10", setup_first_pos=1)
    assert res.entry1 is not None and res.entry1.action == "SELL"   # 청산
    assert res.exit1 is not None and res.exit1.action == "WAYPOINT"  # 무매매 웨이포인트
    assert res.predicted_grade == "mid"
    assert res.entry2 is not None and res.entry2.action == "BUY"    # 재매수(보류 해제)
    assert res.state == DONE


if __name__ == "__main__":
    test_macd_cross_detection()
    test_long_full_cycle_reaches_done()
    test_no_gc_stays_in_confirm()
    test_reentry_has_no_invalidation_on_low_break()
    test_region_undetermined_without_correction_stoch()
    test_strength_flag_from_stoch_triple()
    test_short_campaign_mirror_cycle()
    print("ALL CAMPAIGN STATE MACHINE TESTS PASSED")
