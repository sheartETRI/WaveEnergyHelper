"""캠페인 백테스트 오케스트레이터 테스트 (§7·§8).

합성 파이프라인+MACD 프레임에 실제 승격 가능한 MA10 쌍바닥 setup을 심어
scan→promote→replay→score→journal 전 경로와 순차 캠페인(중첩 방지)을 검증한다.

실행: `python -m pytest tests/test_campaign_backtest.py` 또는 직접 실행
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_backtest import (
    format_campaign_trace,
    run_matrix,
    run_symbol_tf,
)
from analysis.campaign_score import ST_COMPLETE

N = 30
SFX_MID = "(10,5,5)"
SFX_LARGE = "(20,10,10)"


def _na():
    return pd.array([pd.NA] * N, dtype="Float64")


def _obj_na():
    return pd.array([pd.NA] * N, dtype="object")


def _frame(second_setup=False):
    idx = pd.date_range("2026-01-01", periods=N, freq="4h")
    m = [-1.0] * N
    for p in range(5, 8):
        m[p] = 1.0                 # GC@5
    m[8] = m[9] = m[10] = -1.0     # DC@8
    for p in range(11, N):
        m[p] = 1.0                 # GC@11
    df = pd.DataFrame(
        {
            "close": 100.0 + np.arange(N), "high": 110.0, "low": 60.0,
            "macd": m, "macd_signal": 0.0,
            "MA10": 55.0, "MA20": 50.0, "MA60": 30.0, "MA120": 20.0,
        },
        index=idx,
    )
    # MA10 clean HL 쌍바닥 setup @3 (넥라인 105 > prev_opp 90)
    for c in ("ma10_pivot_high", "ma10_pivot_low", "ma10_db",
              "ma10_db_first_pos", "ma10_db_prev_opp"):
        df[c] = _na()
    df["ma10_db_kind"] = _obj_na()
    df.loc[idx[1], "ma10_pivot_high"] = 105.0
    df.loc[idx[2], "ma10_pivot_low"] = 95.0
    df.loc[idx[3], "ma10_db"] = 96.0
    df.loc[idx[3], "ma10_db_kind"] = "HL"
    df.loc[idx[3], "ma10_db_first_pos"] = 0.0
    df.loc[idx[3], "ma10_db_prev_opp"] = 90.0
    # 조정 스토캐 쌍봉(중)@10 + 구간 도달@12 + S7 대파동 쌍봉@16
    df[f"stoch_dt_{SFX_MID}"] = _na()
    df.loc[idx[10], f"stoch_dt_{SFX_MID}"] = 78.0
    df.loc[idx[12], "low"] = 40.0
    df[f"stoch_dt_{SFX_LARGE}"] = _na()
    df.loc[idx[16], f"stoch_dt_{SFX_LARGE}"] = 82.0
    if second_setup:
        # 첫 캠페인 구간(3..16) 안 @9에 두 번째 clean 쌍바닥 → 중첩으로 건너뛰어야
        df.loc[idx[7], "ma10_pivot_high"] = 105.0
        df.loc[idx[8], "ma10_pivot_low"] = 95.0
        df.loc[idx[9], "ma10_db"] = 96.0
        df.loc[idx[9], "ma10_db_kind"] = "HL"
        df.loc[idx[9], "ma10_db_first_pos"] = 6.0
        df.loc[idx[9], "ma10_db_prev_opp"] = 90.0
    return df


def test_run_symbol_tf_single_complete_campaign():
    df = _frame()
    r = run_symbol_tf("BTCUSDT", "4h", full_df=df)
    assert len(r.campaigns) == 1
    res, score = r.campaigns[0]
    assert score.status == ST_COMPLETE
    assert res.setup_pos == 3 and res.exit_final is not None
    assert len(r.journal_rows) == 1
    assert r.journal_rows[0]["obs_grade"] == "관측"


def test_overlapping_second_setup_skipped():
    df = _frame(second_setup=True)
    r = run_symbol_tf("BTCUSDT", "4h", full_df=df)
    # 두 번째 setup@9는 첫 캠페인(3..16) 안이라 순차 규칙으로 건너뜀
    assert len(r.campaigns) == 1
    assert r.campaigns[0][0].setup_pos == 3


def test_run_matrix_aggregates_via_frame_provider():
    frames = {("BTCUSDT", "4h"): _frame(), ("ETHUSDT", "1d"): _frame()}
    out = run_matrix(
        ["BTCUSDT", "ETHUSDT"], ["4h", "1d"],
        frame_provider=lambda s, t: frames.get((s, t)),
    )
    # 프레임 있는 셀만 캠페인 생성 (4h/1d 각 1개 심볼당)
    assert out["overall"]["n_complete"] == 2
    assert out["per_cell"]["BTCUSDT/4h"]["n_complete"] == 1
    assert out["per_cell"]["BTCUSDT/1d"]["n_complete"] == 0   # 프레임 없음
    assert not out["journal"].empty


def test_format_trace_is_human_readable():
    df = _frame()
    r = run_symbol_tf("BTCUSDT", "4h", full_df=df)
    res, score = r.campaigns[0]
    txt = format_campaign_trace(res, score)
    assert "S0 SETUP" in txt and "ENTRY-1" in txt and "ENTRY-2" in txt
    assert "T1=" in txt


if __name__ == "__main__":
    test_run_symbol_tf_single_complete_campaign()
    test_overlapping_second_setup_skipped()
    test_run_matrix_aggregates_via_frame_provider()
    test_format_trace_is_human_readable()
    print("ALL CAMPAIGN BACKTEST TESTS PASSED")
