"""알람 신호 추출 — 기존 검출기 출력 컬럼을 "이벤트 행"으로 환산한다.

검출 로직은 새로 만들지 않는다. indicators.stochastic.add_stochastic_slow_layers 와
indicators.oscillators.add_rsi 가 이미 기록한 컬럼을 읽어, 알람으로 띄울 수 있는
시점 이벤트 목록으로 변환하는 얇은 레이어다(검출기 무수정).

다루는 네 가지:
  · 스토캐 쌍바닥  stoch_db_{suffix}        (넥라인 돌파 확정 봉에만 값)
  · 스토캐 쌍봉    stoch_dt_{suffix}        (동, 반전 공간 대칭)
  · RSI 과매도     rsi_oversold_flag        (구역 진입 교차 봉)
  · RSI 과매수     rsi_overbought_flag      (동)

알람은 상태가 아니라 엣지다. 쌍바닥/쌍봉 컬럼은 확정 봉에만 값이 들어오므로 그 자체가
엣지다. 반면 RSI 구역 플래그는 레벨 상태이므로 False→True 전이만 뽑는다 — 과매도 구간이
30봉 이어질 때 30번 울리지 않게 하려는 것.

streamlit 의존 없음(순수 pandas) — 테스트 가능. 표시는 display.alarm_panel 담당.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from config.settings import RSI_PARAMS, STOCH_LAYERS, WAVE_LAYER_ROLES

# 신호 종류 키 (표시 라벨·방향은 _KIND_META 참조).
KIND_STOCH_DB = "stoch_db"
KIND_STOCH_DT = "stoch_dt"
KIND_STOCH_DB_CANDIDATE = "stoch_db_candidate"
KIND_STOCH_DT_CANDIDATE = "stoch_dt_candidate"
KIND_RSI_OVERSOLD = "rsi_oversold"
KIND_RSI_OVERBOUGHT = "rsi_overbought"

# severity: confirmed = 넥라인 돌파/구역 진입 확정, candidate = 두 번째 피봇까지 성립(돌파 전).
SEV_CONFIRMED = "confirmed"
SEV_CANDIDATE = "candidate"

# direction: bull = 바닥/과매도 계열, bear = 천장/과매수 계열.
DIR_BULL = "bull"
DIR_BEAR = "bear"

_KIND_META = {
    KIND_STOCH_DB: ("스토캐 쌍바닥", DIR_BULL, SEV_CONFIRMED),
    KIND_STOCH_DT: ("스토캐 쌍봉", DIR_BEAR, SEV_CONFIRMED),
    KIND_STOCH_DB_CANDIDATE: ("스토캐 쌍바닥 후보", DIR_BULL, SEV_CANDIDATE),
    KIND_STOCH_DT_CANDIDATE: ("스토캐 쌍봉 후보", DIR_BEAR, SEV_CANDIDATE),
    KIND_RSI_OVERSOLD: ("RSI 과매도 진입", DIR_BULL, SEV_CONFIRMED),
    KIND_RSI_OVERBOUGHT: ("RSI 과매수 진입", DIR_BEAR, SEV_CONFIRMED),
}

# 레이어 label -> 역할 이름(대/중/소). WAVE_LAYER_ROLES 역방향.
_LAYER_ROLE = {label: role for role, label in WAVE_LAYER_ROLES.items()}
_ROLE_KO = {"large": "대", "mid": "중", "small": "소"}


@dataclass(frozen=True)
class AlarmSignal:
    """알람 한 건. timestamp는 해당 봉의 open_time(df 인덱스)."""

    timestamp: pd.Timestamp
    kind: str
    label: str
    direction: str
    severity: str
    layer: Optional[str] = None    # 스토캐 레이어 label, RSI 신호는 None
    value: Optional[float] = None  # 이벤트 봉의 지표값(%K 또는 RSI)
    detail: str = ""               # 부가정보(쌍바닥 kind HL/LL 등)

    @property
    def layer_name(self) -> str:
        """사람이 읽는 레이어 이름 — 대(20,10,10) 형태. RSI 신호는 RSI."""
        if self.layer is None:
            return "RSI"
        role = _LAYER_ROLE.get(self.layer)
        if role is None:
            return self.layer
        return f"{_ROLE_KO.get(role, role)}{self.layer}"


def _layer_labels(layers: Optional[Iterable[str]]) -> list[str]:
    """대상 레이어 label 목록. None이면 STOCH_LAYERS 전체(대→중→소 선언 순서)."""
    if layers is None:
        return [layer["label"] for layer in STOCH_LAYERS]
    return list(layers)


def _event_positions(series: pd.Series) -> pd.Index:
    """값이 들어온(notna) 인덱스 — 쌍바닥/쌍봉 컬럼은 확정 봉에만 값이 있다."""
    return series.index[series.notna()]


def _flag_entry_positions(flag: pd.Series) -> pd.Index:
    """레벨 플래그의 False→True 전이 인덱스(구역 진입 봉만).

    NaN을 False로 간주한다 — 워밍업 구간이 진입으로 오검출되지 않게 하고, 첫 봉은
    직전 상태가 없으므로 전이 대상에서 빠진다.
    """
    truthy = flag.fillna(False).astype(bool)
    prev = truthy.shift(1, fill_value=False)
    return truthy.index[truthy & ~prev]


def _stoch_signals_for_layer(
    df: pd.DataFrame, suffix: str, include_candidates: bool
) -> list[AlarmSignal]:
    """한 스토캐 레이어의 쌍바닥·쌍봉(+후보) 이벤트."""
    out: list[AlarmSignal] = []
    k_col = f"stoch_k_{suffix}"

    specs = [
        (KIND_STOCH_DB, f"stoch_db_{suffix}", f"stoch_db_kind_{suffix}"),
        (KIND_STOCH_DT, f"stoch_dt_{suffix}", f"stoch_dt_kind_{suffix}"),
    ]
    if include_candidates:
        specs += [
            (KIND_STOCH_DB_CANDIDATE, f"stoch_db_candidate_{suffix}", f"stoch_db_kind_{suffix}"),
            (KIND_STOCH_DT_CANDIDATE, f"stoch_dt_candidate_{suffix}", f"stoch_dt_kind_{suffix}"),
        ]

    for kind, value_col, kind_col in specs:
        if value_col not in df.columns:
            continue
        label, direction, severity = _KIND_META[kind]
        for ts in _event_positions(df[value_col]):
            raw_kind = df.at[ts, kind_col] if kind_col in df.columns else None
            detail = "" if raw_kind is None or pd.isna(raw_kind) else str(raw_kind)
            k_value = df.at[ts, k_col] if k_col in df.columns else None
            out.append(
                AlarmSignal(
                    timestamp=ts,
                    kind=kind,
                    label=label,
                    direction=direction,
                    severity=severity,
                    layer=suffix,
                    value=None if k_value is None or pd.isna(k_value) else float(k_value),
                    detail=detail,
                )
            )
    return out


def _rsi_signals(df: pd.DataFrame) -> list[AlarmSignal]:
    """RSI 과매도·과매수 구역 진입 이벤트(레벨→엣지 변환)."""
    out: list[AlarmSignal] = []
    specs = [
        (KIND_RSI_OVERSOLD, "rsi_oversold_flag", RSI_PARAMS["oversold"], "<"),
        (KIND_RSI_OVERBOUGHT, "rsi_overbought_flag", RSI_PARAMS["overbought"], ">"),
    ]
    for kind, flag_col, threshold, op in specs:
        if flag_col not in df.columns:
            continue
        label, direction, severity = _KIND_META[kind]
        for ts in _flag_entry_positions(df[flag_col]):
            rsi_value = df.at[ts, "rsi"] if "rsi" in df.columns else None
            out.append(
                AlarmSignal(
                    timestamp=ts,
                    kind=kind,
                    label=label,
                    direction=direction,
                    severity=severity,
                    layer=None,
                    value=None if rsi_value is None or pd.isna(rsi_value) else float(rsi_value),
                    detail=f"기준 {op}{threshold}",
                )
            )
    return out


def scan_alarm_signals(
    df: pd.DataFrame,
    layers: Optional[Iterable[str]] = None,
    include_candidates: bool = True,
) -> list[AlarmSignal]:
    """df 전 구간의 알람 이벤트를 시간순으로 반환.

    df는 add_stochastic_slow_layers / add_rsi 를 거친 것이어야 한다. 필요한 컬럼이 없으면
    그 종류만 조용히 건너뛴다(지표 토글을 끈 상태에서도 패널이 죽지 않게).
    """
    if df is None or df.empty:
        return []

    signals: list[AlarmSignal] = []
    for suffix in _layer_labels(layers):
        signals.extend(_stoch_signals_for_layer(df, suffix, include_candidates))
    signals.extend(_rsi_signals(df))

    signals.sort(key=lambda s: (s.timestamp, s.kind))
    return signals


def recent_signals(
    df: pd.DataFrame,
    bars: int = 50,
    layers: Optional[Iterable[str]] = None,
    include_candidates: bool = True,
) -> list[AlarmSignal]:
    """최근 `bars` 봉 안에서 발생한 알람만. bars<=0이면 전 구간."""
    signals = scan_alarm_signals(df, layers=layers, include_candidates=include_candidates)
    if bars <= 0 or df is None or df.empty:
        return signals
    cutoff = df.index[max(0, len(df) - bars)]
    return [s for s in signals if s.timestamp >= cutoff]


def rsi_zone(df: pd.DataFrame) -> str:
    """마지막 봉의 RSI 구역 — 과매도 | 과매수 | 중립 | - (RSI 미계산)."""
    if df is None or df.empty or "rsi" not in df.columns:
        return "-"
    value = df["rsi"].iloc[-1]
    if pd.isna(value):
        return "-"
    if value < RSI_PARAMS["oversold"]:
        return "과매도"
    if value > RSI_PARAMS["overbought"]:
        return "과매수"
    return "중립"


def signals_to_frame(signals: list[AlarmSignal]) -> pd.DataFrame:
    """표시용 표. 최신이 위로 오도록 역순 정렬한다."""
    columns = ["시각", "신호", "레이어", "구분", "지표값", "비고"]
    if not signals:
        return pd.DataFrame(columns=columns)
    rows = [
        {
            "시각": s.timestamp,
            "신호": s.label,
            "레이어": s.layer_name,
            "구분": "확정" if s.severity == SEV_CONFIRMED else "후보",
            "지표값": None if s.value is None else round(s.value, 2),
            "비고": s.detail,
        }
        for s in reversed(signals)
    ]
    return pd.DataFrame(rows, columns=columns)
