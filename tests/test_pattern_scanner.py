"""L1 패턴 스캐너 회귀 테스트.

검출기 자체는 test_ma_patterns / test_stoch_kind / test_triple_patterns 가 검증한다.
여기서는 스캐너의 래핑 로직만 검증한다:
- 확정 컬럼(non-NA) → PatternEvent 방출, NA → 미방출
- 방향 매핑 (바닥→long, 봉→short), 삼중→n/a clean, 넥라인 소스 분기
- classify_clean 위임 (kind HL + 넥라인 스윙 = clean)
- scan_latest 마지막 봉 필터, events_to_dataframe 스키마

실행: `python -m pytest tests/test_pattern_scanner.py` 또는 직접 실행
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.pattern_scanner import (
    events_to_dataframe,
    scan_dataframe,
    scan_latest,
    scan_ma_patterns,
    scan_stoch_patterns,
)


def _empty_df(n=8):
    idx = pd.date_range("2024-01-01", periods=n, freq="4h")
    return pd.DataFrame({"close": np.arange(100.0, 100.0 + n)}, index=idx)


def _ma_db_df():
    """MA10 HL 쌍바닥이 pos6에서 확정, 넥라인=105(pos2 고점) > prev_opp=90 → clean."""
    df = _empty_df(8)
    na = pd.array([pd.NA] * 8, dtype="Float64")
    df["ma10_pivot_high"] = na.copy()
    df["ma10_pivot_low"] = na.copy()
    df["ma10_db"] = na.copy()
    df["ma10_pivot_high"] = df["ma10_pivot_high"].astype("Float64")
    df.loc[df.index[2], "ma10_pivot_high"] = 105.0
    df.loc[df.index[4], "ma10_pivot_low"] = 95.0
    df.loc[df.index[6], "ma10_db"] = 96.0
    df["ma10_db_kind"] = pd.array([pd.NA] * 8, dtype="object")
    df.loc[df.index[6], "ma10_db_kind"] = "HL"
    df["ma10_db_first_pos"] = na.copy()
    df.loc[df.index[6], "ma10_db_first_pos"] = 1.0
    df["ma10_db_prev_opp"] = na.copy()
    df.loc[df.index[6], "ma10_db_prev_opp"] = 90.0
    return df


def test_ma_double_bottom_event_fields_and_clean():
    df = _ma_db_df()
    events = scan_ma_patterns(df, "BTCUSDT", "4h", periods=[10])
    assert len(events) == 1
    ev = events[0]
    assert ev.kind_pattern == "double_bottom"
    assert ev.direction == "long"
    assert ev.ma_or_layer == "MA10"
    assert ev.source == "ma"
    assert ev.kind == "HL"
    assert ev.confirmed_pos == 6
    assert ev.confirmed_bar == df.index[6]
    assert ev.neckline_price == 105.0       # pos2 고점
    assert ev.clean == "clean"              # HL + 넥라인(105) > prev_opp(90)
    assert ev.strength == 96.0


def test_ma_not_clean_when_neckline_below_prev_opp():
    df = _ma_db_df()
    # prev_opp를 넥라인보다 높게 → swing_ok False → not-clean
    df.loc[df.index[6], "ma10_db_prev_opp"] = 200.0
    ev = scan_ma_patterns(df, "BTCUSDT", "4h", periods=[10])[0]
    assert ev.clean == "not-clean"


def _stoch_df():
    """스토캐 (5,3,3) 층: db(HL, clean) pos3, dt(HH, not-clean) pos5, tb pos6."""
    sfx = "(5,3,3)"
    df = _empty_df(8)
    na = pd.array([pd.NA] * 8, dtype="Float64")
    for col in (f"stoch_db_{sfx}", f"stoch_neckline_{sfx}", f"stoch_db_prev_opp_{sfx}",
                f"stoch_dt_{sfx}", f"stoch_dt_neckline_{sfx}", f"stoch_dt_prev_opp_{sfx}",
                f"stoch_tb_{sfx}"):
        df[col] = na.copy()
    df[f"stoch_db_kind_{sfx}"] = pd.array([pd.NA] * 8, dtype="object")
    df[f"stoch_dt_kind_{sfx}"] = pd.array([pd.NA] * 8, dtype="object")
    df[f"stoch_tb_kind_{sfx}"] = pd.array([pd.NA] * 8, dtype="object")
    # db 확정 pos3: HL, neckline 60 > prev_opp 40 → clean
    df.loc[df.index[3], f"stoch_db_{sfx}"] = 25.0
    df.loc[df.index[3], f"stoch_db_kind_{sfx}"] = "HL"
    df.loc[df.index[3], f"stoch_neckline_{sfx}"] = 60.0
    df.loc[df.index[3], f"stoch_db_prev_opp_{sfx}"] = 40.0
    # dt 확정 pos5: HH → kind_ok False → not-clean (봉은 LH가 clean)
    df.loc[df.index[5], f"stoch_dt_{sfx}"] = 78.0
    df.loc[df.index[5], f"stoch_dt_kind_{sfx}"] = "HH"
    df.loc[df.index[5], f"stoch_dt_neckline_{sfx}"] = 45.0
    df.loc[df.index[5], f"stoch_dt_prev_opp_{sfx}"] = 55.0
    # tb 확정 pos6: 넥라인 미저장, clean n/a
    df.loc[df.index[6], f"stoch_tb_{sfx}"] = 22.0
    df.loc[df.index[6], f"stoch_tb_kind_{sfx}"] = "HL"
    return df


def test_stoch_direction_neckline_and_triple_na():
    df = _stoch_df()
    events = scan_stoch_patterns(df, "ETHUSDT", "1h", suffixes=["(5,3,3)"])
    by = {e.kind_pattern: e for e in events}
    assert set(by) == {"double_bottom", "double_top", "triple_bottom"}

    db = by["double_bottom"]
    assert db.direction == "long" and db.clean == "clean" and db.neckline_price == 60.0

    dt = by["double_top"]
    assert dt.direction == "short" and dt.clean == "not-clean" and dt.neckline_price == 45.0

    tb = by["triple_bottom"]
    assert tb.direction == "long"
    assert tb.neckline_price is None      # 삼중 넥라인 미저장 (§10 gap)
    assert tb.clean == "n/a"


def test_na_rows_emit_no_events():
    df = _empty_df(8)
    df["ma10_db"] = pd.array([pd.NA] * 8, dtype="Float64")
    assert scan_ma_patterns(df, "X", "4h", periods=[10]) == []


def test_scan_latest_filters_to_last_bar():
    df = _stoch_df()
    # 마지막 확정은 pos6(tb). pos6가 마지막 봉이 아니면 latest는 비어야.
    latest = scan_latest(df, "ETHUSDT", "1h", stoch_suffixes=["(5,3,3)"])
    assert latest == []  # 확정들은 pos3/5/6, 마지막 봉은 pos7 → 없음
    # pos7에 확정 추가하면 그것만 잡힘
    df.loc[df.index[7], "stoch_db_(5,3,3)"] = 20.0
    df.loc[df.index[7], "stoch_db_kind_(5,3,3)"] = "HL"
    latest = scan_latest(df, "ETHUSDT", "1h", stoch_suffixes=["(5,3,3)"])
    assert len(latest) == 1 and latest[0].confirmed_pos == 7


def test_events_to_dataframe_schema():
    empty = events_to_dataframe([])
    assert "confirmed_bar" in empty.columns and "clean" in empty.columns
    df = _stoch_df()
    out = events_to_dataframe(scan_dataframe(df, "ETHUSDT", "1h", stoch_suffixes=["(5,3,3)"]))
    assert len(out) == 3
    assert list(out["confirmed_bar"]) == sorted(out["confirmed_bar"])  # 정렬 보증


if __name__ == "__main__":
    test_ma_double_bottom_event_fields_and_clean()
    test_ma_not_clean_when_neckline_below_prev_opp()
    test_stoch_direction_neckline_and_triple_na()
    test_na_rows_emit_no_events()
    test_scan_latest_filters_to_last_bar()
    test_events_to_dataframe_schema()
    print("ALL PATTERN SCANNER TESTS PASSED")
