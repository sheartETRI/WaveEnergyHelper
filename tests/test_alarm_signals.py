"""알람 신호 추출 테스트 — 검출기 컬럼 → 이벤트 행 환산 계약."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.alarm_signals import (
    KIND_RSI_OVERBOUGHT,
    KIND_RSI_OVERSOLD,
    KIND_STOCH_DB,
    KIND_STOCH_DB_CANDIDATE,
    KIND_STOCH_DT,
    SEV_CANDIDATE,
    SEV_CONFIRMED,
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
    """실제 파이프라인(add_stochastic_slow_layers + add_rsi) 출력에서도 동작한다."""
    from indicators.oscillators import add_rsi
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
    df = add_rsi(df)

    signals = scan_alarm_signals(df)
    assert signals, "랜덤워크 600봉에서 신호가 하나도 없으면 환산 레이어가 컬럼을 못 읽은 것"
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
