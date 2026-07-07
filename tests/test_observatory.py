"""v2 관측 계기판 로직 회귀 테스트 (9차 위임 B·C·D) — 표시·저널 전용.

- C slope_state: 상승/평탄/하락 3단, 평탄=|slope| 히스토리 하위 pctile.
- C composite_trend_label: 김박사 규칙(강한 추세 후보 / 초기 전환 관찰 / 횡보 주의).
- B monthly_stoch_position: 스토캐 4층 K 위치(바닥권/중간/고점권)+방향.
- D array_state(스펙 §2.5): 정배열(10>20>60>120)/비정배열(120>60)/기타 + 채널 디스패치.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile

from analysis.observatory import (
    PRECURSOR_CHANNELS,
    append_observatory_journal,
    array_state,
    composite_trend_label,
    monthly_stoch_position,
    precursor_channel,
    slope_state,
)
from analysis.trend_layer import TREND_STOCH_SUFFIX


def _df(cols):
    n = len(next(iter(cols.values())))
    idx = pd.date_range("2020-01-01", periods=n, freq="1D")
    return pd.DataFrame(cols, index=idx)


# ---------------------------------------------------------------- C slope_state
def test_slope_state_up_down_flat():
    # 강한 상승: 오래 수평(slope 히스토리 하위) 후 최근 급상승 → 최근 |slope| 큼 → up
    up = _df({"MA60": [100.0] * 55 + [102, 104, 106, 108, 110]})
    assert slope_state(up, period=60)["state"] == "up"
    # 강한 하락
    down = _df({"MA60": [100.0] * 55 + [98, 96, 94, 92, 90]})
    assert slope_state(down, period=60)["state"] == "down"
    # 평탄: 오래 급상승(slope 히스토리 상위) 후 최근 수평 → 최근 |slope|≈0 → 하위20% → flat
    flat = _df({"MA60": [100 + 10 * i for i in range(55)] + [640.0] * 5})
    st = slope_state(flat, period=60)
    assert st["state"] == "flat"
    assert st["flat_thr"] > 0


def test_composite_trend_label_rules():
    assert composite_trend_label("up", "up")["label"] == "강한 추세 후보"
    assert composite_trend_label("up", "down")["label"] == "초기 전환 관찰"
    assert composite_trend_label("up", "flat")["label"] == "초기 전환 관찰"
    # 1d 평탄이면 4d 무관 횡보 주의
    assert composite_trend_label("flat", "up")["label"] == "횡보 주의"
    assert composite_trend_label("flat", "down")["label"] == "횡보 주의"
    # 1d 하락은 규칙 미정의 → 중립 관찰 라벨
    assert "관찰" in composite_trend_label("down", "down")["label"]
    # 툴팁에 8차 관측 인용
    assert "fwd20" in composite_trend_label("flat", "flat")["note"]


# ---------------------------------------------------------------- B monthly stoch
def test_monthly_stoch_position_zones():
    sfx = TREND_STOCH_SUFFIX
    # 바닥권 + 상승(K>D)
    df = _df({f"stoch_k_{sfx}": [50, 10.0], f"stoch_d_{sfx}": [55, 8.0]})
    pos = monthly_stoch_position(df)
    assert pos["zone"] == "바닥권" and pos["direction"] == "상승"
    # 고점권 + 하락(K<D)
    df2 = _df({f"stoch_k_{sfx}": [50, 90.0], f"stoch_d_{sfx}": [40, 95.0]})
    p2 = monthly_stoch_position(df2)
    assert p2["zone"] == "고점권" and p2["direction"] == "하락"
    # 중간
    df3 = _df({f"stoch_k_{sfx}": [50, 50.0], f"stoch_d_{sfx}": [50, 50.0]})
    assert monthly_stoch_position(df3)["zone"] == "중간"
    # 컬럼 부재 시 None
    assert monthly_stoch_position(_df({"close": [1, 2]})) is None


# ---------------------------------------------------------------- D array_state (스펙 §2.5)
def test_array_state_2p5():
    # 정배열: 10>20>60>120
    bull = _df({"MA10": [4], "MA20": [3], "MA60": [2], "MA120": [1]})
    assert array_state(bull) == "정배열"
    # 비정배열: 120>60 (10 눌림)
    bear = _df({"MA10": [2], "MA20": [2.5], "MA60": [3], "MA120": [4]})
    assert array_state(bear) == "비정배열"
    # 기타: 120<60 이지만 완전 정배열 아님
    mixed = _df({"MA10": [3], "MA20": [4], "MA60": [2], "MA120": [1]})
    assert array_state(mixed) == "기타"
    # MA120 부재(월봉 부족) → 기타
    nom120 = _df({"MA10": [4], "MA20": [3], "MA60": [2]})
    assert array_state(nom120) == "기타"


def test_precursor_channel_dispatch():
    # 정배열 → 이평선 10MA 쌍봉 채널
    bull = _df({"MA10": [4, 4], "MA20": [3, 3], "MA60": [2, 2], "MA120": [1, 1]})
    bull["ma10_dt"] = pd.Series([pd.NA, 3.9], index=bull.index, dtype="Float64")
    out = precursor_channel(bull, "BTCUSDT", "1d")
    assert out["state"] == "정배열"
    assert out["channel"] == PRECURSOR_CHANNELS["정배열"]["channel"]
    assert out["confirmed_ts"] is not None   # 최근봉 ma10_dt 확정
    # 비정배열 → 대파동 스토캐 쌍봉 채널
    bear = _df({"MA10": [2, 2], "MA20": [2.5, 2.5], "MA60": [3, 3], "MA120": [4, 4]})
    out2 = precursor_channel(bear, "BTCUSDT", "1d")
    assert out2["state"] == "비정배열"
    assert out2["channel"] == PRECURSOR_CHANNELS["비정배열"]["channel"]
    assert out2["candidates"] == []   # 스토캐 candidate 스캐너 부재
    # 기타 → 활성 채널 없음
    other = _df({"MA10": [3, 3], "MA20": [4, 4], "MA60": [2, 2], "MA120": [1, 1]})
    out3 = precursor_channel(other, "BTCUSDT", "1d")
    assert out3["active"] is False and out3["channel"] is None


def test_scan_stoch_candidates_pending_vs_confirmed():
    from analysis.pattern_scanner import scan_stoch_candidates
    sfx = "(20,10,10)"
    n = 10
    idx = pd.date_range("2020-01-01", periods=n, freq="1D")
    base = {"close": [100.0] * n,
            f"stoch_dt_candidate_{sfx}": [pd.NA] * n,
            f"stoch_dt_{sfx}": [pd.NA] * n,
            f"stoch_dt_neckline_{sfx}": [pd.NA] * n,
            f"stoch_dt_kind_{sfx}": [pd.NA] * n}
    df = pd.DataFrame(base, index=idx)
    # 대기 후보: 두 번째 천장 마킹(pos7), 이후 확정 없음 → pending 방출.
    df.iloc[7, df.columns.get_loc(f"stoch_dt_candidate_{sfx}")] = 80.0
    df.iloc[7, df.columns.get_loc(f"stoch_dt_neckline_{sfx}")] = 60.0
    df.iloc[7, df.columns.get_loc(f"stoch_dt_kind_{sfx}")] = "LH"
    ev = scan_stoch_candidates(df, "BTCUSDT", "1d", suffixes=[sfx])
    short = [e for e in ev if e.direction == "short"]
    assert len(short) == 1
    assert short[0].stage == "candidate" and short[0].kind == "LH"
    assert short[0].ma_or_layer == sfx and short[0].source == "stoch"
    assert short[0].neckline_price == 60.0
    # 확정이 마킹 뒤에 오면 대기 후보 아님(방출 안 함).
    df.iloc[9, df.columns.get_loc(f"stoch_dt_{sfx}")] = 85.0
    ev2 = scan_stoch_candidates(df, "BTCUSDT", "1d", suffixes=[sfx])
    assert [e for e in ev2 if e.direction == "short"] == []


def test_stoch_candidate_lead_bars_definition():
    from analysis.pattern_scanner import stoch_candidate_lead_bars
    from config.settings import STOCH_PIVOT_PARAMS
    sfx = "(20,10,10)"
    n = 12
    idx = pd.date_range("2020-01-01", periods=n, freq="1D")
    df = pd.DataFrame({"close": [100.0] * n,
                       f"stoch_dt_candidate_{sfx}": [pd.NA] * n,
                       f"stoch_dt_{sfx}": [pd.NA] * n}, index=idx)
    df.iloc[5, df.columns.get_loc(f"stoch_dt_candidate_{sfx}")] = 80.0   # 두 번째 극점 pos5
    df.iloc[9, df.columns.get_loc(f"stoch_dt_{sfx}")] = 85.0             # 확정 pos9
    rows = stoch_candidate_lead_bars(df, "BTCUSDT", "1d", suffixes=[sfx])
    dt = [r for r in rows if r["pat"] == "dt"]
    assert len(dt) == 1
    lb = STOCH_PIVOT_PARAMS["lookback"]
    assert dt[0]["lead_bars"] == 9 - (5 + lb)   # confirm − (pb + lookback)


def test_observatory_journal_append_dedup():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "obs.csv")
        row = {"ts": "2026-07-08T00:00:00", "symbol": "BTCUSDT", "tf": "1d/4d",
               "kind": "slope_dash", "composite_label": "하락 국면 (관찰)"}
        assert append_observatory_journal(row, path) is True    # 최초 기록
        assert append_observatory_journal(row, path) is False   # 동일 키 중복 → 스킵
        row2 = dict(row, symbol="ETHUSDT")
        assert append_observatory_journal(row2, path) is True   # 다른 심볼 → 기록
        df = pd.read_csv(path)
        assert len(df) == 2 and "composite_label" in df.columns


if __name__ == "__main__":
    test_slope_state_up_down_flat()
    test_composite_trend_label_rules()
    test_monthly_stoch_position_zones()
    test_array_state_2p5()
    test_precursor_channel_dispatch()
    test_scan_stoch_candidates_pending_vs_confirmed()
    test_stoch_candidate_lead_bars_definition()
    test_observatory_journal_append_dedup()
    print("ALL OBSERVATORY TESTS PASSED")
