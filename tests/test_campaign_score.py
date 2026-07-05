"""캠페인 채점 + 저널 스키마 테스트 (§7).

실행: `python -m pytest tests/test_campaign_score.py` 또는 직접 실행
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_score import (
    CAMPAIGN_JOURNAL_COLS,
    ST_COMPLETE,
    ST_NO_ENTRY,
    ST_T1_ONLY,
    campaign_journal_row,
    journal_to_dataframe,
    score_campaign,
    summarize_campaigns,
)
from analysis.campaign_state_machine import DONE, CampaignResult, TradePoint


def _df(n=20, low=None, high=None):
    idx = pd.date_range("2026-01-01", periods=n, freq="4h")
    return pd.DataFrame(
        {
            "close": 100.0 + np.arange(n),
            "low": low if low is not None else 100.0,
            "high": high if high is not None else 130.0,
        },
        index=idx,
    )


def _long_complete():
    res = CampaignResult(
        symbol="BTCUSDT", base_tf="4h", direction="long",
        setup_ts=pd.Timestamp("2026-01-01"), setup_pos=0, setup_layer="MA10",
        state=DONE, predicted_grade="mid", predicted_region_label="MA20~60",
        setup_pattern_low=95.0,
    )
    res.entry1 = TradePoint("S2_ENTRY1", res.setup_ts, 2, 100.0, "BUY")
    res.exit1 = TradePoint("S4_EXIT1", res.setup_ts, 5, 110.0, "SELL")
    res.entry2 = TradePoint("S6_ENTRY2", res.setup_ts, 10, 105.0, "BUY")
    res.exit_final = TradePoint("DONE", res.setup_ts, 15, 126.0, "SELL")
    return res


def test_long_complete_returns_and_fees():
    df = _df()
    res = _long_complete()
    s = score_campaign(res, df, fee_per_fill=0.001)
    assert abs(s.t1_return - 0.10) < 1e-9        # (110-100)/100
    assert abs(s.t2_return - 0.20) < 1e-9        # (126-105)/105
    assert abs(s.combined_gross - (1.1 * 1.2 - 1.0)) < 1e-9   # 0.32
    assert s.num_fills == 4
    expected_net = 1.1 * 1.2 * (0.999 ** 4) - 1.0
    assert abs(s.combined_net - expected_net) < 1e-9
    assert s.status == ST_COMPLETE


def test_mae_and_low_break():
    low = np.full(20, 100.0)
    low[8] = 90.0     # setup_low 95 아래 이탈 (재진입 pos10 이전)
    low[12] = 98.0    # T2 구간(10..15) 최저
    df = _df(low=low)
    res = _long_complete()
    s = score_campaign(res, df)
    # MAE_t2: T2 구간 최저 98 vs 재매수 105 → (98-105)/105
    assert abs(s.mae_t2 - ((98.0 - 105.0) / 105.0)) < 1e-9
    assert s.entry2_after_low_break is True     # pos8 저가 90 < 95


def test_short_complete_mirror_accounting():
    df = _df()
    res = CampaignResult(
        symbol="ETHUSDT", base_tf="1d", direction="short",
        setup_ts=pd.Timestamp("2026-01-01"), setup_pos=0, setup_layer="MA10",
        state=DONE, setup_pattern_high=120.0,
    )
    res.entry1 = TradePoint("S2_ENTRY1", res.setup_ts, 2, 100.0, "SELL")   # 청산
    res.exit1 = TradePoint("S4_EXIT1", res.setup_ts, 5, 108.0, "WAYPOINT")  # 무매매
    res.entry2 = TradePoint("S6_ENTRY2", res.setup_ts, 10, 80.0, "BUY")    # 재매수
    res.exit_final = TradePoint("DONE", res.setup_ts, 15, 100.0, "SELL")
    s = score_campaign(res, df, fee_per_fill=0.001)
    assert abs(s.t1_return - 0.20) < 1e-9        # (100-80)/100 회피 하락폭
    assert abs(s.t2_return - 0.25) < 1e-9        # (100-80)/80
    assert s.num_fills == 3                       # 매도·매수·매도 (X1 무매매 제외)
    assert s.status == ST_COMPLETE


def test_t1_only_and_no_entry_status():
    df = _df()
    res = _long_complete()
    res.entry2 = None
    res.exit_final = None
    res.state = "S5_WAVE2"
    s = score_campaign(res, df)
    assert s.status == ST_T1_ONLY
    assert s.t2_return is None and s.t1_return is not None

    empty = CampaignResult(symbol="X", base_tf="4h", direction="long",
                           setup_ts=pd.Timestamp("2026-01-01"), setup_pos=0, setup_layer="MA10",
                           state="S1_CONFIRM")
    s2 = score_campaign(empty, df)
    assert s2.status == ST_NO_ENTRY and s2.num_fills == 0


def test_journal_row_schema_and_summary():
    df = _df()
    res = _long_complete()
    s = score_campaign(res, df)
    row = campaign_journal_row(res, s, upper_alignment="UP", suppressed_by_upper=None)
    assert set(row.keys()) == set(CAMPAIGN_JOURNAL_COLS)
    assert row["obs_grade"] == "관측"
    assert row["s0_kind"] == "HL"
    assert row["upper_alignment"] == "UP"
    out = journal_to_dataframe([row])
    assert list(out.columns) == list(CAMPAIGN_JOURNAL_COLS)

    summ = summarize_campaigns([s])
    assert summ["n_complete"] == 1
    assert abs(summ["expectancy_net"] - s.combined_net) < 1e-9
    assert summ["win_rate"] == 1.0


if __name__ == "__main__":
    test_long_complete_returns_and_fees()
    test_mae_and_low_break()
    test_short_complete_mirror_accounting()
    test_t1_only_and_no_entry_status()
    test_journal_row_schema_and_summary()
    print("ALL CAMPAIGN SCORE TESTS PASSED")
