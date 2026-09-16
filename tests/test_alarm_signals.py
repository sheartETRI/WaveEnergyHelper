"""알람 신호 추출 테스트 — 검출기 컬럼 → 이벤트 행 환산 계약."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.alarm_signals import (
    KIND_MACD_DEAD,
    KIND_MACD_GOLDEN,
    KIND_MACD_ZERO_DOWN,
    KIND_MACD_ZERO_UP,
    KIND_RSI_OVERBOUGHT,
    KIND_RSI_OVERSOLD,
    KIND_STOCH_DB,
    KIND_STOCH_DB_CANDIDATE,
    KIND_STOCH_DT,
    SEV_CANDIDATE,
    SEV_CONFIRMED,
    MACD_KINDS,
    macd_event_positions,
    recent_signals,
    rsi_zone,
    scan_alarm_signals,
    signals_to_frame,
)
from config.settings import RSI_PARAMS, STOCH_LAYERS

LARGE = STOCH_LAYERS[0]["label"]   # "(20,10,10)"
SMALL = STOCH_LAYERS[-1]["label"]  # "(5,3,3)"


def _index(n):
    return pd.date_range("2026-01-01", periods=n, freq="h")


def _stoch_frame(n=10, suffix=LARGE):
    """한 레이어의 쌍바닥/쌍봉 컬럼만 가진 최소 프레임(검출기 출력 모사)."""
    idx = _index(n)
    nan = pd.Series(pd.NA, index=idx, dtype="Float64")
    return pd.DataFrame(
        {
            f"stoch_k_{suffix}": pd.Series(np.linspace(10, 90, n), index=idx),
            f"stoch_db_{suffix}": nan.copy(),
            f"stoch_db_candidate_{suffix}": nan.copy(),
            f"stoch_db_kind_{suffix}": pd.Series([None] * n, index=idx, dtype="object"),
            f"stoch_dt_{suffix}": nan.copy(),
            f"stoch_dt_candidate_{suffix}": nan.copy(),
            f"stoch_dt_kind_{suffix}": pd.Series([None] * n, index=idx, dtype="object"),
        },
        index=idx,
    )


def _rsi_frame(values):
    """RSI 레벨 플래그를 add_rsi와 같은 규칙(strict 비교)으로 만든 프레임."""
    idx = _index(len(values))
    rsi = pd.Series(np.asarray(values, dtype=float), index=idx)
    return pd.DataFrame(
        {
            "rsi": rsi,
            "rsi_oversold_flag": rsi < RSI_PARAMS["oversold"],
            "rsi_overbought_flag": rsi > RSI_PARAMS["overbought"],
        },
        index=idx,
    )


def _macd_frame(macd, signal):
    """add_macd 와 같은 컬럼 규칙(hist = macd - signal, hist_prev = hist.shift(1))의 프레임.

    macd / signal 값을 직접 주어 교차 봉을 결정론적으로 심는다. 첫 봉의 hist_prev 는
    add_macd 와 마찬가지로 NaN.
    """
    idx = _index(len(macd))
    macd_s = pd.Series(np.asarray(macd, dtype=float), index=idx)
    signal_s = pd.Series(np.asarray(signal, dtype=float), index=idx)
    hist = macd_s - signal_s
    return pd.DataFrame(
        {"macd": macd_s, "macd_signal": signal_s, "macd_hist": hist, "macd_hist_prev": hist.shift(1)},
        index=idx,
    )


def _macd_kinds(df):
    return {kind: [s.timestamp for s in scan_alarm_signals(df, layers=[]) if s.kind == kind] for kind in MACD_KINDS}


def test_macd_golden_cross_once_at_cross_bar():
    """hist 가 음→양으로 바뀌는 봉에서 정확히 1건. 양수 유지 구간엔 0건."""
    # hist: nan, -2, -1, +1, +2, +3  (idx3 에서 상향 교차, 이후 양수 유지)
    df = _macd_frame(macd=[1, 1, 1, 3, 4, 5], signal=[1, 3, 2, 2, 2, 2])
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_GOLDEN] == [df.index[3]]
    assert kinds[KIND_MACD_DEAD] == []
    golden = [s for s in scan_alarm_signals(df, layers=[]) if s.kind == KIND_MACD_GOLDEN][0]
    assert golden.layer is None and golden.layer_name == "MACD" and golden.metric_name == "hist"
    assert golden.severity == SEV_CONFIRMED and golden.direction == "bull"
    assert golden.value == float(df["macd_hist"].iloc[3])   # 이벤트 봉의 hist
    assert golden.detail == "MACD 3"                         # 반대편 값(0선 위)


def test_macd_dead_cross_symmetric():
    """hist 양→음 전이 봉에서 데드크로스 1건, 골든 0건."""
    # hist: nan, +2, +1, -1, -2
    df = _macd_frame(macd=[5, 5, 5, 5, 5], signal=[5, 3, 4, 6, 7])
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_DEAD] == [df.index[3]]
    assert kinds[KIND_MACD_GOLDEN] == []
    dead = [s for s in scan_alarm_signals(df, layers=[]) if s.kind == KIND_MACD_DEAD][0]
    assert dead.direction == "bear" and dead.value == float(df["macd_hist"].iloc[3])


def test_macd_zero_line_transitions():
    """macd 부호 전이 봉에서만 0선 상향/하향 각 1건. value 는 그 봉의 macd."""
    # macd: -2, -1, +1, +2, -1, -3  → 상향 idx2, 하향 idx4. signal = macd 로 hist 0 고정(크로스 없음).
    macd = [-2, -1, 1, 2, -1, -3]
    df = _macd_frame(macd=macd, signal=macd)
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_ZERO_UP] == [df.index[2]]
    assert kinds[KIND_MACD_ZERO_DOWN] == [df.index[4]]
    assert kinds[KIND_MACD_GOLDEN] == [] and kinds[KIND_MACD_DEAD] == []
    up = [s for s in scan_alarm_signals(df, layers=[]) if s.kind == KIND_MACD_ZERO_UP][0]
    assert up.value == 1.0 and up.metric_name == "MACD" and up.layer_name == "MACD"
    assert up.detail == "hist 0"


def test_macd_no_cross_region_is_silent():
    """부호가 안 바뀌면 0건 — 단조 구간·평행 구간 모두."""
    df = _macd_frame(macd=[1, 2, 3, 4, 5], signal=[0, 1, 2, 3, 4])   # hist 항상 +1, macd 항상 +
    assert all(v == [] for v in _macd_kinds(df).values())
    df = _macd_frame(macd=[-5, -4, -3], signal=[-1, -1, -1])          # hist 항상 -, macd 항상 -
    assert all(v == [] for v in _macd_kinds(df).values())


def test_macd_repeated_crosses_fire_each_time():
    """0 근처 진동 — 교차마다 1건씩, 교차 사이 유지 봉에서는 안 울린다(채터링 억제 없음)."""
    # hist: nan, -1, +1, +1, -1, -1, +1, -1  → 골든 idx2, idx6 / 데드 idx4, idx7
    macd = [0, 0, 0, 0, 0, 0, 0, 0]
    signal = [0, 1, -1, -1, 1, 1, -1, 1]
    df = _macd_frame(macd=macd, signal=signal)
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_GOLDEN] == [df.index[2], df.index[6]]
    assert kinds[KIND_MACD_DEAD] == [df.index[4], df.index[7]]
    # macd 는 0 고정 → 부호 전이 없음
    assert kinds[KIND_MACD_ZERO_UP] == [] and kinds[KIND_MACD_ZERO_DOWN] == []

    # 0선도 같은 규칙: -,+,-,+ 교대면 매 전이마다.
    df = _macd_frame(macd=[-1, 1, -1, 1], signal=[-1, 1, -1, 1])
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_ZERO_UP] == [df.index[1], df.index[3]]
    assert kinds[KIND_MACD_ZERO_DOWN] == [df.index[2]]


def test_macd_zero_boundary_fires_once():
    """정확히 0 에 닿는 봉은 '도달한 쪽' 1회만 — 다음 봉엔 직전값이 0 이라 재발화 없음."""
    # hist: nan, -1, 0, +1 → 골든 idx2 한 번. 데드는 없음.
    df = _macd_frame(macd=[0, 0, 0, 0], signal=[0, 1, 0, -1])
    kinds = _macd_kinds(df)
    assert kinds[KIND_MACD_GOLDEN] == [df.index[2]]
    assert kinds[KIND_MACD_DEAD] == []


def test_macd_nan_warmup_is_not_an_event():
    """EMA 워밍업이 NaN 으로 남는 변형을 물려도 결측→값 경계에서 알람이 안 난다."""
    # 앞 3봉 결측 후 hist 가 +1 로 시작 (직전 결측): 골든 아님. macd 도 +2 로 시작: 0선 상향 아님.
    df = _macd_frame(macd=[np.nan, np.nan, np.nan, 2, 3], signal=[np.nan, np.nan, np.nan, 1, 1])
    assert all(v == [] for v in _macd_kinds(df).values())
    # 결측 후 첫 유효값이 음수여도 마찬가지(하향 아님).
    df = _macd_frame(macd=[np.nan, np.nan, -2, -3], signal=[np.nan, np.nan, -1, -1])
    assert all(v == [] for v in _macd_kinds(df).values())
    # 첫 봉(hist_prev NaN)이 양수여도 골든 아님 — add_macd 첫 봉과 같은 상황.
    df = _macd_frame(macd=[3, 4], signal=[1, 1])
    assert _macd_kinds(df)[KIND_MACD_GOLDEN] == []


def test_macd_missing_columns_skipped_and_positions_shared():
    """macd 컬럼이 없으면 조용히 건너뛰고, macd_event_positions 는 스캔 결과와 같은 봉을 준다."""
    idx = _index(4)
    assert macd_event_positions(pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=idx)) == {}
    df = _macd_frame(macd=[-1, 1, -1, 1], signal=[0, 0, 0, 0])   # hist = macd
    positions = macd_event_positions(df)
    kinds = _macd_kinds(df)
    for kind in MACD_KINDS:
        assert list(positions[kind]) == kinds[kind]
    # hist_prev 컬럼만 빠지면 크로스 2종만 빠지고 0선은 남는다.
    partial = df.drop(columns=["macd_hist_prev"])
    kinds = _macd_kinds(partial)
    assert kinds[KIND_MACD_GOLDEN] == [] and kinds[KIND_MACD_DEAD] == []
    assert kinds[KIND_MACD_ZERO_UP] == [df.index[1], df.index[3]]


def test_stoch_confirmed_events_only_on_valued_bars():
    """쌍바닥/쌍봉 컬럼은 확정 봉에만 값 → 그 봉에서만 신호가 나온다."""
    df = _stoch_frame(n=10)
    df.loc[df.index[3], f"stoch_db_{LARGE}"] = 18.0
    df.loc[df.index[3], f"stoch_db_kind_{LARGE}"] = "HL"
    df.loc[df.index[7], f"stoch_dt_{LARGE}"] = 85.0
    df.loc[df.index[7], f"stoch_dt_kind_{LARGE}"] = "LH"

    signals = scan_alarm_signals(df, layers=[LARGE], include_candidates=False)
    assert [s.kind for s in signals] == [KIND_STOCH_DB, KIND_STOCH_DT]
    assert [s.timestamp for s in signals] == [df.index[3], df.index[7]]
    assert [s.detail for s in signals] == ["HL", "LH"]
    assert all(s.severity == SEV_CONFIRMED for s in signals)
    # 지표값은 이벤트 봉의 %K에서 읽는다(쌍바닥 컬럼값이 아니라).
    assert signals[0].value == float(df[f"stoch_k_{LARGE}"].iloc[3])


def test_candidates_toggle():
    """include_candidates=False면 후보는 빠지고, True면 후보가 candidate severity로 붙는다."""
    df = _stoch_frame(n=8)
    df.loc[df.index[5], f"stoch_db_candidate_{LARGE}"] = 15.0

    assert scan_alarm_signals(df, layers=[LARGE], include_candidates=False) == []
    signals = scan_alarm_signals(df, layers=[LARGE], include_candidates=True)
    assert [s.kind for s in signals] == [KIND_STOCH_DB_CANDIDATE]
    assert signals[0].severity == SEV_CANDIDATE


def test_rsi_zone_entry_edge_not_level():
    """구역 '유지'는 중복 신호가 아니다 — 진입 봉에서만 울린다."""
    # oversold=30, overbought=70 기준. 25가 3봉 이어지고(진입 1회), 이후 75 2봉(진입 1회).
    df = _rsi_frame([50, 40, 25, 22, 26, 45, 75, 78, 60])
    signals = scan_alarm_signals(df, layers=[])

    oversold = [s for s in signals if s.kind == KIND_RSI_OVERSOLD]
    overbought = [s for s in signals if s.kind == KIND_RSI_OVERBOUGHT]
    assert [s.timestamp for s in oversold] == [df.index[2]]   # 40 → 25 진입만
    assert [s.timestamp for s in overbought] == [df.index[6]]  # 45 → 75 진입만
    assert oversold[0].layer is None and oversold[0].layer_name == "RSI"


def test_rsi_reentry_fires_again():
    """구역을 벗어난 뒤 재진입하면 다시 울린다."""
    df = _rsi_frame([50, 25, 50, 25, 25])
    oversold = [s for s in scan_alarm_signals(df, layers=[]) if s.kind == KIND_RSI_OVERSOLD]
    assert [s.timestamp for s in oversold] == [df.index[1], df.index[3]]


def test_rsi_warmup_nan_is_not_entry():
    """플래그가 결측인 워밍업 구간은 False로 간주 — 경계에서 가짜 진입이 안 생긴다.

    실제 add_rsi는 bool dtype(결측 없음)을 내지만, 워밍업을 NaN으로 남기는 변형
    (indicators.rsi_wilder 계열)을 물려도 엣지 추출이 깨지지 않아야 한다.
    """
    df = _rsi_frame([50, 50, 25, 25])
    df["rsi_oversold_flag"] = pd.array([pd.NA, pd.NA, True, True], dtype="boolean")
    oversold = [s for s in scan_alarm_signals(df, layers=[]) if s.kind == KIND_RSI_OVERSOLD]
    # idx0·idx1은 결측→False, 실제 진입은 idx2 하나뿐.
    assert [s.timestamp for s in oversold] == [df.index[2]]


def test_missing_columns_are_skipped_quietly():
    """지표 토글이 꺼져 컬럼이 없어도 예외 없이 빈 목록."""
    idx = _index(5)
    bare = pd.DataFrame({"close": np.arange(5.0)}, index=idx)
    assert scan_alarm_signals(bare) == []
    assert rsi_zone(bare) == "-"
    assert scan_alarm_signals(None) == []
    assert scan_alarm_signals(pd.DataFrame()) == []


def test_signals_sorted_and_layer_named():
    """여러 레이어 섞여도 시간순. layer_name은 대/중/소 접두."""
    df_large = _stoch_frame(n=6, suffix=LARGE)
    df_small = _stoch_frame(n=6, suffix=SMALL)
    df = pd.concat([df_large, df_small], axis=1)
    df.loc[df.index[4], f"stoch_db_{LARGE}"] = 20.0
    df.loc[df.index[1], f"stoch_db_{SMALL}"] = 12.0

    signals = scan_alarm_signals(df, layers=[LARGE, SMALL], include_candidates=False)
    assert [s.timestamp for s in signals] == [df.index[1], df.index[4]]
    assert signals[0].layer_name == f"소{SMALL}"
    assert signals[1].layer_name == f"대{LARGE}"


def test_recent_signals_window():
    """최근 bars 봉 경계 — 창 밖 이벤트는 제외, bars<=0이면 전 구간."""
    df = _stoch_frame(n=20)
    df.loc[df.index[2], f"stoch_db_{LARGE}"] = 10.0    # 오래된 것
    df.loc[df.index[18], f"stoch_db_{LARGE}"] = 11.0   # 최근

    recent = recent_signals(df, bars=5, layers=[LARGE], include_candidates=False)
    assert [s.timestamp for s in recent] == [df.index[18]]
    assert len(recent_signals(df, bars=0, layers=[LARGE], include_candidates=False)) == 2


def test_rsi_zone_boundaries():
    """경계는 add_rsi의 strict 비교와 일치 — 정확히 30/70은 중립."""
    assert rsi_zone(_rsi_frame([50, 29.9])) == "과매도"
    assert rsi_zone(_rsi_frame([50, 70.1])) == "과매수"
    assert rsi_zone(_rsi_frame([50, float(RSI_PARAMS["oversold"])])) == "중립"
    assert rsi_zone(_rsi_frame([50, float(RSI_PARAMS["overbought"])])) == "중립"
    assert rsi_zone(_rsi_frame([50, np.nan])) == "-"


def test_signals_to_frame_newest_first():
    """표는 최신이 위. 빈 목록도 같은 컬럼으로 빈 표를 준다."""
    df = _stoch_frame(n=6)
    df.loc[df.index[1], f"stoch_db_{LARGE}"] = 10.0
    df.loc[df.index[4], f"stoch_dt_{LARGE}"] = 90.0
    frame = signals_to_frame(scan_alarm_signals(df, layers=[LARGE], include_candidates=False))

    assert list(frame.columns) == ["시각", "신호", "레이어", "구분", "지표값", "비고"]
    assert frame["시각"].tolist() == [df.index[4], df.index[1]]
    assert frame["구분"].tolist() == ["확정", "확정"]
    assert signals_to_frame([]).empty
    assert list(signals_to_frame([]).columns) == list(frame.columns)


def test_real_pipeline_smoke():
    """실제 파이프라인(add_stochastic_slow_layers + add_macd + add_rsi) 출력에서도 동작한다."""
    from indicators.oscillators import add_macd, add_rsi
    from indicators.stochastic import add_stochastic_slow_layers

    rng = np.random.default_rng(20260911)
    n = 600
    idx = _index(n)
    close = 100 + np.cumsum(rng.normal(0, 1.2, n))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(rng.normal(0, 0.6, n)),
            "low": close - np.abs(rng.normal(0, 0.6, n)),
            "close": close,
            "volume": rng.uniform(1, 10, n),
        },
        index=idx,
    )
    df = add_stochastic_slow_layers(df)
    df = add_macd(df)
    df = add_rsi(df)

    signals = scan_alarm_signals(df)
    assert signals, "랜덤워크 600봉에서 신호가 하나도 없으면 환산 레이어가 컬럼을 못 읽은 것"
    # MACD 4종이 실제 add_macd 컬럼에서 나오고, 각 이벤트 봉은 정의대로 부호가 바뀐 봉이다.
    macd_signals = [s for s in signals if s.kind in MACD_KINDS]
    assert {s.kind for s in macd_signals} == set(MACD_KINDS)
    for s in macd_signals:
        pos = df.index.get_loc(s.timestamp)
        assert pos > 0
        if s.kind == KIND_MACD_GOLDEN:
            assert df["macd_hist_prev"].iloc[pos] < 0 <= df["macd_hist"].iloc[pos]
        elif s.kind == KIND_MACD_DEAD:
            assert df["macd_hist_prev"].iloc[pos] > 0 >= df["macd_hist"].iloc[pos]
        elif s.kind == KIND_MACD_ZERO_UP:
            assert df["macd"].iloc[pos - 1] < 0 <= df["macd"].iloc[pos]
        elif s.kind == KIND_MACD_ZERO_DOWN:
            assert df["macd"].iloc[pos - 1] > 0 >= df["macd"].iloc[pos]
    # 크로스 봉 수 == hist 부호 전이 수 (교차마다 1건, 유지 봉 0건)
    sign = np.sign(df["macd_hist"].fillna(0))
    flips = int(((sign != sign.shift(1)) & sign.shift(1).notna() & (sign != 0) & (sign.shift(1) != 0)).sum())
    n_cross = sum(1 for s in macd_signals if s.kind in (KIND_MACD_GOLDEN, KIND_MACD_DEAD))
    assert n_cross == flips
    # 시간순 보장 + 모든 신호가 df 인덱스 위에 있어야 한다.
    stamps = [s.timestamp for s in signals]
    assert stamps == sorted(stamps)
    assert all(ts in df.index for ts in stamps)
    assert rsi_zone(df) in {"과매도", "과매수", "중립"}
    # 확정 신호는 해당 봉의 쌍바닥/쌍봉 컬럼에 실제로 값이 있어야 한다.
    for s in signals:
        if s.kind == KIND_STOCH_DB:
            assert pd.notna(df.at[s.timestamp, f"stoch_db_{s.layer}"])
        elif s.kind == KIND_STOCH_DT:
            assert pd.notna(df.at[s.timestamp, f"stoch_dt_{s.layer}"])


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("ALL ALARM SIGNAL TESTS PASSED")
