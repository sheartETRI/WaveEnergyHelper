# indicators/ma_patterns.py
"""이평선 시계열 자체의 쌍바닥(W)/쌍봉(M) 패턴 검출기.

설계 원칙:
- 스토캐스틱 검출기를 재사용하지 않는다. 스토캐스틱은 0~100 고정 스케일 전제
  (middle_zone=50, 과매도 20 등)라 가격 스케일인 이평선에 맞지 않는다.
- 같은 개념 구조(피봇 -> 상태머신)를 '스케일 프리'로 새로 구현한다.
- 쌍봉은 -series(부호 반전) 호출 + kind 매핑(HL<->LH, LL<->HH)으로 처리한다.
- 코어 6개 이평(CORE_MA_PERIODS)에 대해서만 산출한다. 공식 판정용 체계이기 때문이다.
"""
import numpy as np
import pandas as pd
import streamlit as st

from config.settings import CORE_MA_PERIODS, MA_PATTERN_PARAMS

# 부호 반전 공간(쌍바닥)의 kind -> 원공간(쌍봉)의 kind
_INVERT_KIND_MAP = {"HL": "LH", "LL": "HH", "EQ": "EQ"}


def classify_pattern_kind(first_value: float, second_value: float) -> tuple[str, float]:
    """두 극값을 비교해 (kind, delta)를 반환한다 (바닥 기준: 높아지면 HL)."""
    delta = float(second_value) - float(first_value)
    if second_value > first_value:
        return "HL", delta
    if second_value < first_value:
        return "LL", delta
    return "EQ", delta


def _is_centered_extreme(window: np.ndarray, center_pos: int, is_low: bool, tol: float) -> bool:
    """중심이 윈도우의 극값 영역 한가운데에 있는지 (스케일 프리, 상대 허용오차)."""
    if is_low:
        extreme = window.min()
        near = window <= extreme + tol
    else:
        extreme = window.max()
        near = window >= extreme - tol

    if not bool(near[center_pos]):
        return False

    start = center_pos
    while start > 0 and bool(near[start - 1]):
        start -= 1
    end = center_pos
    last = len(near) - 1
    while end < last and bool(near[end + 1]):
        end += 1

    midpoint = (start + end) / 2.0
    return abs(center_pos - midpoint) <= 0.5


def _select_from_run(run: list[int], values: np.ndarray, is_low: bool) -> int:
    sub = values[run]
    target = sub.min() if is_low else sub.max()
    best = [idx for idx in run if values[idx] == target]
    return best[len(best) // 2]


def _collapse_runs(candidates: list[int], values: np.ndarray, is_low: bool) -> list[int]:
    if not candidates:
        return []
    collapsed = []
    run = [candidates[0]]
    for c in candidates[1:]:
        if c == run[-1] + 1:
            run.append(c)
            continue
        collapsed.append(_select_from_run(run, values, is_low))
        run = [c]
    collapsed.append(_select_from_run(run, values, is_low))
    return collapsed


def _apply_min_gap(pivot: pd.Series, indices: list[int], values: np.ndarray, min_gap: int, is_low: bool) -> None:
    prev = None
    for idx in indices:
        val = values[idx]
        if prev is None or idx - prev >= min_gap:
            pivot.iloc[idx] = val
            prev = idx
            continue
        prev_val = values[prev]
        more_extreme = val < prev_val if is_low else val > prev_val
        if more_extreme:
            pivot.iloc[prev] = pd.NA
            pivot.iloc[idx] = val
            prev = idx


def compute_series_pivots(series: pd.Series, lookback: int = 3, min_gap: int = 3, rel_tolerance: float = 0.02):
    """스케일 프리 중심 극값 피봇. middle_zone 필터는 없다.

    허용오차는 절대값이 아니라 윈도우 (max-min)에 비례한다.
    """
    pivot_lows = pd.Series(pd.NA, index=series.index, dtype="Float64")
    pivot_highs = pd.Series(pd.NA, index=series.index, dtype="Float64")
    if series is None or series.empty or lookback < 1:
        return pivot_lows, pivot_highs

    values = series.to_numpy(dtype="float64")
    n = len(values)
    low_candidates: list[int] = []
    high_candidates: list[int] = []

    for center in range(lookback, n - lookback):
        window = values[center - lookback:center + lookback + 1]
        c = values[center]
        if np.isnan(c) or np.isnan(window).any():
            continue
        span = float(window.max() - window.min())
        tol = rel_tolerance * span
        if c <= window.min() + tol and _is_centered_extreme(window, lookback, is_low=True, tol=tol):
            low_candidates.append(center)
        if c >= window.max() - tol and _is_centered_extreme(window, lookback, is_low=False, tol=tol):
            high_candidates.append(center)

    low_candidates = _collapse_runs(low_candidates, values, is_low=True)
    high_candidates = _collapse_runs(high_candidates, values, is_low=False)
    _apply_min_gap(pivot_lows, low_candidates, values, max(int(min_gap), 1), is_low=True)
    _apply_min_gap(pivot_highs, high_candidates, values, max(int(min_gap), 1), is_low=False)
    return pivot_lows, pivot_highs


def _is_declining_before(values: np.ndarray, pos: int, decline_lookback: int) -> bool:
    """[F3] 첫 바닥 이전에 이평선이 하락 중이었는지: pos가 decline_lookback 봉 전보다 낮음."""
    ref = pos - decline_lookback
    if ref < 0:
        return False
    if np.isnan(values[pos]) or np.isnan(values[ref]):
        return False
    return values[pos] < values[ref]


def _detect_series_double_bottom(df: pd.DataFrame, value_col: str, pivot_low_col: str, pivot_high_col: str,
                                 db_col: str, db_kind_col: str, decline_lookback: int,
                                 first_pos_col: str | None = None,
                                 prev_opp_col: str | None = None) -> pd.DataFrame:
    """이평선 쌍바닥 상태머신.

    구조: (하락 전제) 피봇저점1 -> 사이 피봇고점(넥라인) -> 피봇저점2 -> 넥라인 상향 돌파 시 확정.
    저점2 vs 저점1로 kind(HL/LL/EQ) 기록. higher-low 제약은 없다(LL도 유효한 쌍바닥).
    """
    df[db_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[db_kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
    if first_pos_col is not None:
        df[first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if prev_opp_col is not None:
        df[prev_opp_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if value_col not in df.columns:
        return df

    values = df[value_col].to_numpy(dtype="float64")
    n = len(values)
    low_pos = [i for i in range(n) if not pd.isna(df[pivot_low_col].iloc[i])]
    high_pos = [i for i in range(n) if not pd.isna(df[pivot_high_col].iloc[i])]

    next_start = 0
    for i in range(len(low_pos) - 1):
        pa = low_pos[i]
        pb = low_pos[i + 1]
        if pa < next_start:
            continue
        if not _is_declining_before(values, pa, decline_lookback):
            continue
        mids = [h for h in high_pos if pa < h < pb]
        if not mids:
            continue
        neckline = max(values[h] for h in mids)
        if neckline <= max(values[pa], values[pb]):
            continue
        # 넥라인 상향 돌파 봉에서 확정
        for pos in range(pb + 1, n):
            v = values[pos]
            if np.isnan(v):
                continue
            if v > neckline:
                df.at[df.index[pos], db_col] = float(v)
                kind, _ = classify_pattern_kind(values[pa], values[pb])
                df.at[df.index[pos], db_kind_col] = kind
                if first_pos_col is not None:
                    df.at[df.index[pos], first_pos_col] = float(pa)
                if prev_opp_col is not None and pa > 0:
                    ph_seg = df[pivot_high_col].iloc[:pa].dropna()
                    if not ph_seg.empty:
                        df.at[df.index[pos], prev_opp_col] = float(ph_seg.iloc[-1])
                next_start = pb  # 다음 패턴은 저점2 이후부터
                break
    return df


def _detect_series_double_top(df: pd.DataFrame, value_col: str, db_col: str, dt_col: str,
                              params: dict) -> pd.DataFrame:
    """이평선 쌍봉 = -series에 쌍바닥 검출 후 kind 반전 매핑."""
    dt_kind_col = f"{dt_col}_kind"
    dt_first_pos_col = f"{dt_col}_first_pos"
    dt_prev_opp_col = f"{dt_col}_prev_opp"
    df[dt_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
    df[dt_first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_prev_opp_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if value_col not in df.columns:
        return df

    inv = pd.DataFrame(index=df.index)
    inv["v"] = -df[value_col]
    pl, ph = compute_series_pivots(
        inv["v"], lookback=params["lookback"], min_gap=params["min_gap"], rel_tolerance=params["rel_tolerance"]
    )
    inv["pl"] = pl
    inv["ph"] = ph
    inv = _detect_series_double_bottom(
        inv, "v", "pl", "ph", "db", "db_kind", params["decline_lookback"],
        first_pos_col="db_first_pos",
        prev_opp_col="db_prev_opp",
    )

    # 원공간 복원: 위치는 동일, 값은 원 시리즈 값, kind는 반전 매핑
    db_mask = inv["db"].notna()
    df.loc[db_mask, dt_col] = df.loc[db_mask, value_col]
    df.loc[db_mask, dt_kind_col] = inv.loc[db_mask, "db_kind"].map(_INVERT_KIND_MAP)
    df.loc[db_mask, dt_first_pos_col] = inv.loc[db_mask, "db_first_pos"]
    # 부호 복원: -series 반전 공간 prev_opp -> 원공간 T0
    df.loc[db_mask, dt_prev_opp_col] = (-inv.loc[db_mask, "db_prev_opp"]).astype("Float64")
    return df


@st.cache_data(ttl=600)
def add_ma_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """코어 이평(CORE_MA_PERIODS) 각각에 대해 쌍바닥/쌍봉 패턴 컬럼을 추가한다."""
    if df is None or df.empty:
        return df

    params = MA_PATTERN_PARAMS
    for n in CORE_MA_PERIODS:
        ma_col = f"MA{n}"
        if ma_col not in df.columns:
            continue

        pl, ph = compute_series_pivots(
            df[ma_col],
            lookback=params["lookback"],
            min_gap=params["min_gap"],
            rel_tolerance=params["rel_tolerance"],
        )
        df[f"ma{n}_pivot_low"] = pl
        df[f"ma{n}_pivot_high"] = ph
        df = _detect_series_double_bottom(
            df, ma_col, f"ma{n}_pivot_low", f"ma{n}_pivot_high",
            f"ma{n}_db", f"ma{n}_db_kind", params["decline_lookback"],
            first_pos_col=f"ma{n}_db_first_pos",
            prev_opp_col=f"ma{n}_db_prev_opp",
        )
        df = _detect_series_double_top(df, ma_col, f"ma{n}_db", f"ma{n}_dt", params)
    return df
