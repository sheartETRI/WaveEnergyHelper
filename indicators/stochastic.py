# indicators/stochastic.py
import pandas as pd
import streamlit as st
from config.settings import STOCH_LAYERS, STOCH_PIVOT_PARAMS


# 반전(100-값) 공간의 쌍바닥 kind를 원공간 쌍봉 kind로 뒤집어 매핑한다.
# 반전 "HL"(반전저점이 높아짐) -> 원공간 "LH"(고점이 낮아짐), "LL" -> "HH".
_INVERT_KIND_MAP = {"HL": "LH", "LL": "HH", "EQ": "EQ"}


def classify_pattern_kind(first_value: float, second_value: float) -> tuple[str, float]:
    """두 극값을 비교해 (kind, delta)를 반환한다.

    바닥 기준: second > first -> "HL", second < first -> "LL", 같으면 "EQ".
    delta = second - first.
    """
    delta = float(second_value) - float(first_value)
    if second_value > first_value:
        kind = "HL"
    elif second_value < first_value:
        kind = "LL"
    else:
        kind = "EQ"
    return kind, delta


def _is_centered_extreme(window: pd.Series, center_pos: int, is_low: bool, tolerance: float) -> bool:
    """Returns True when the center sits in the middle of a local extreme area."""
    if is_low:
        extreme_value = window.min()
        near_extreme = window <= extreme_value + tolerance
    else:
        extreme_value = window.max()
        near_extreme = window >= extreme_value - tolerance

    if not bool(near_extreme.iloc[center_pos]):
        return False

    start = center_pos
    while start > 0 and bool(near_extreme.iloc[start - 1]):
        start -= 1

    end = center_pos
    last_pos = len(near_extreme) - 1
    while end < last_pos and bool(near_extreme.iloc[end + 1]):
        end += 1

    midpoint = (start + end) / 2.0
    return abs(center_pos - midpoint) <= 0.5


def _collapse_candidate_runs(candidates: list[int], series: pd.Series, is_low: bool) -> list[int]:
    """Collapses adjacent pivot candidates into one representative point."""
    if not candidates:
        return []

    collapsed = []
    run = [candidates[0]]

    for candidate in candidates[1:]:
        if candidate == run[-1] + 1:
            run.append(candidate)
            continue

        collapsed.append(_select_candidate_from_run(run, series, is_low))
        run = [candidate]

    collapsed.append(_select_candidate_from_run(run, series, is_low))
    return collapsed


def _select_candidate_from_run(run: list[int], series: pd.Series, is_low: bool) -> int:
    values = series.iloc[run]
    target_value = values.min() if is_low else values.max()
    best_indices = [idx for idx in run if series.iloc[idx] == target_value]
    return best_indices[len(best_indices) // 2]


def _apply_min_gap(
    pivot_series: pd.Series,
    candidate_indices: list[int],
    source_series: pd.Series,
    min_gap: int,
    is_low: bool,
) -> None:
    """Keeps same-type pivots spaced by min_gap, replacing nearby ones only if more extreme."""
    prev_idx = None

    for candidate_idx in candidate_indices:
        candidate_value = source_series.iloc[candidate_idx]

        if prev_idx is None or candidate_idx - prev_idx >= min_gap:
            pivot_series.iloc[candidate_idx] = candidate_value
            prev_idx = candidate_idx
            continue

        prev_value = source_series.iloc[prev_idx]
        is_more_extreme = candidate_value < prev_value if is_low else candidate_value > prev_value
        if is_more_extreme:
            pivot_series.iloc[prev_idx] = pd.NA
            pivot_series.iloc[candidate_idx] = candidate_value
            prev_idx = candidate_idx


def compute_stochastic_pivots(series: pd.Series, lookback: int = 2, middle_zone: float = 50.0, min_gap: int = 4, min_delta: float = 4.0) -> tuple[pd.Series, pd.Series]:
    """Returns confirmed pivot-low and pivot-high values for a smoothed stochastic wave.

    min_delta is retained for settings compatibility, but it is no longer used as
    a required value difference between same-type pivots. Similar double
    bottoms/tops are valid pivots when they are separated by min_gap.
    """
    pivot_lows = pd.Series(pd.NA, index=series.index, dtype="Float64")
    pivot_highs = pd.Series(pd.NA, index=series.index, dtype="Float64")

    if series is None or series.empty or lookback < 1:
        return pivot_lows, pivot_highs

    min_gap = max(int(min_gap), 1)
    local_tolerance = min(max(float(min_delta) * 0.25, 0.0), 1.0)
    center_pos = lookback
    low_candidates = []
    high_candidates = []

    for center in range(lookback, len(series) - lookback):
        window = series.iloc[center - lookback:center + lookback + 1]
        center_value = series.iloc[center]
        if pd.isna(center_value) or window.isna().any():
            continue

        if center_value < middle_zone and _is_centered_extreme(window, center_pos, is_low=True, tolerance=local_tolerance):
            low_candidates.append(center)

        if center_value > middle_zone and _is_centered_extreme(window, center_pos, is_low=False, tolerance=local_tolerance):
            high_candidates.append(center)

    low_candidates = _collapse_candidate_runs(low_candidates, series, is_low=True)
    high_candidates = _collapse_candidate_runs(high_candidates, series, is_low=False)

    _apply_min_gap(pivot_lows, low_candidates, series, min_gap, is_low=True)
    _apply_min_gap(pivot_highs, high_candidates, series, min_gap, is_low=False)

    return pivot_lows, pivot_highs


def detect_double_bottom_patterns(
    df: pd.DataFrame,
    value_col: str,
    pivot_low_col: str,
    db_col: str,
    db_candidate_col: str,
    neckline_col: str,
    kind_col: str | None = None,
    delta_col: str | None = None,
    first_pos_col: str | None = None,
    pivot_high_col: str | None = None,
    prev_opp_col: str | None = None,
) -> pd.DataFrame:
    """Detects double bottoms using higher pivot lows and neckline breaks.

    kind_col/delta_col가 주어지면 두 바닥의 비교 결과(HL/LL/EQ)와 delta를 후보·확정
    봉에 '기록만' 한다. 상태머신의 전이 로직은 전혀 바뀌지 않는다.
    """
    df[db_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[db_candidate_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[neckline_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    record_kind = kind_col is not None and delta_col is not None
    if record_kind:
        df[kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
        df[delta_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if first_pos_col is not None:
        df[first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if prev_opp_col is not None:
        df[prev_opp_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if value_col not in df.columns or pivot_low_col not in df.columns:
        return df

    value_series = df[value_col]
    pivot_lows = df[pivot_low_col]
    pivot_highs = df[pivot_high_col] if pivot_high_col and pivot_high_col in df.columns else None
    previous_bottom_pos = None
    previous_bottom_value = None
    second_bottom_pos = None
    second_bottom_value = None
    candidate_neckline = None
    candidate_first_value = None  # 기록 전용: 후보 활성 시점의 첫 바닥 값 보관
    candidate_first_pos = None    # 기록 전용: 패턴 1번 바닥 위치(iloc)
    active_neckline_positions = []

    def _record_kind_at(pos: int, first_value, second_value) -> None:
        if not record_kind or first_value is None:
            return
        kind, delta = classify_pattern_kind(first_value, second_value)
        df.at[df.index[pos], kind_col] = kind
        df.at[df.index[pos], delta_col] = delta

    def clear_active_candidate() -> None:
        nonlocal second_bottom_pos, second_bottom_value, candidate_neckline, active_neckline_positions
        nonlocal candidate_first_value, candidate_first_pos

        for active_pos in active_neckline_positions:
            df.at[df.index[active_pos], db_candidate_col] = pd.NA
            df.at[df.index[active_pos], neckline_col] = pd.NA
            if record_kind:
                df.at[df.index[active_pos], kind_col] = pd.NA
                df.at[df.index[active_pos], delta_col] = pd.NA

        second_bottom_pos = None
        second_bottom_value = None
        candidate_neckline = None
        candidate_first_value = None
        candidate_first_pos = None
        active_neckline_positions = []

    def set_previous_bottom(pos: int, value: float) -> None:
        nonlocal previous_bottom_pos, previous_bottom_value

        previous_bottom_pos = pos
        previous_bottom_value = value

    def mark_candidate(pos: int, value: float, neckline: float | None) -> None:
        nonlocal active_neckline_positions

        if neckline is None:
            return
        index_value = df.index[pos]
        df.at[index_value, db_candidate_col] = value
        df.at[index_value, neckline_col] = neckline
        active_neckline_positions = [pos]
        _record_kind_at(pos, candidate_first_value, value)

    def get_neckline(first_pos: int, second_pos: int, first_value: float, second_value: float) -> float | None:
        start_pos = first_pos + 1
        end_pos = second_pos
        if start_pos >= end_pos:
            return None

        values = value_series.iloc[start_pos:end_pos].dropna()
        if values.empty:
            return None

        neckline = float(values.max())
        if neckline <= max(first_value, second_value):
            return None
        return neckline

    def is_neckline_break(pos: int, neckline: float | None) -> bool:
        if neckline is None or pos <= 0:
            return False
        current_value = value_series.iloc[pos]
        previous_value = value_series.iloc[pos - 1]
        if pd.isna(current_value) or pd.isna(previous_value):
            return False
        return current_value > neckline and previous_value <= neckline

    def _record_prev_opp(confirm_pos: int, first_pos) -> None:
        """기록 전용: 첫 바닥 직전 반대(고점) 피봇 값."""
        if prev_opp_col is None or pivot_highs is None or first_pos is None:
            return
        fp = int(first_pos)
        if fp <= 0:
            return
        segment = pivot_highs.iloc[:fp].dropna()
        if segment.empty:
            return
        df.at[df.index[confirm_pos], prev_opp_col] = float(segment.iloc[-1])

    def confirm_double_bottom(pos: int) -> None:
        nonlocal previous_bottom_pos, previous_bottom_value
        nonlocal second_bottom_pos, second_bottom_value, candidate_neckline, active_neckline_positions
        nonlocal candidate_first_value, candidate_first_pos

        if candidate_neckline is None:
            return
        db_value = value_series.iloc[pos]
        if pd.isna(db_value):
            return
        df.at[df.index[pos], db_col] = float(db_value)
        df.at[df.index[pos], neckline_col] = candidate_neckline
        _record_kind_at(pos, candidate_first_value, second_bottom_value)
        if first_pos_col is not None and candidate_first_pos is not None:
            df.at[df.index[pos], first_pos_col] = float(candidate_first_pos)
        _record_prev_opp(pos, candidate_first_pos)

        previous_bottom_pos = second_bottom_pos
        previous_bottom_value = second_bottom_value
        second_bottom_pos = None
        second_bottom_value = None
        candidate_neckline = None
        candidate_first_value = None
        candidate_first_pos = None
        active_neckline_positions = []

    def activate_second_bottom_candidate(bottom_pos: int, bottom_value: float, neckline: float) -> None:
        nonlocal second_bottom_pos, second_bottom_value, candidate_neckline
        nonlocal candidate_first_value, candidate_first_pos

        # 기록 전용: mark_candidate 이전에 첫 바닥 값·위치를 보관(이후 set_previous_bottom로 덮어쓰기 됨)
        candidate_first_value = previous_bottom_value
        candidate_first_pos = previous_bottom_pos
        second_bottom_pos = bottom_pos
        second_bottom_value = bottom_value
        candidate_neckline = neckline
        mark_candidate(second_bottom_pos, second_bottom_value, candidate_neckline)

    for pos in range(len(df)):
        if candidate_neckline is not None and second_bottom_pos is not None and pos > second_bottom_pos:
            df.at[df.index[pos], neckline_col] = candidate_neckline
            active_neckline_positions.append(pos)
            if is_neckline_break(pos, candidate_neckline):
                confirm_double_bottom(pos)
                continue

        pivot_value = pivot_lows.iloc[pos]
        if pd.isna(pivot_value):
            continue

        pivot_value = float(pivot_value)
        if previous_bottom_value is None:
            set_previous_bottom(pos, pivot_value)
            continue

        # 두 바닥(이전 저점, 현재 피봇저점) 사이에 넥라인이 있으면 후보를 활성화한다.
        # 두 번째 저점이 더 낮아도(LL) 넥라인 상향 돌파 시 확정한다. get_neckline이
        # neckline > max(first, second)를 요구하므로 W 구조(사이 고점) 조건은 그대로 유지된다.
        # (기존에는 pivot_value <= previous_bottom_value면 후보를 만들지 않아 HL만 검출되었다.)
        clear_active_candidate()
        neckline = get_neckline(previous_bottom_pos, pos, previous_bottom_value, pivot_value)
        if neckline is not None:
            activate_second_bottom_candidate(pos, pivot_value, neckline)
        set_previous_bottom(pos, pivot_value)

    return df


def detect_double_top_patterns(
    df: pd.DataFrame,
    value_col: str,
    pivot_high_col: str,
    dt_col: str,
    dt_candidate_col: str,
    neckline_col: str,
    pivot_low_col: str | None = None,
    prev_opp_col: str | None = None,
) -> pd.DataFrame:
    """Detects double tops using lower pivot highs and neckline breaks."""
    df[dt_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_candidate_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[neckline_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if prev_opp_col is not None:
        df[prev_opp_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if value_col not in df.columns or pivot_high_col not in df.columns:
        return df

    value_series = df[value_col]
    pivot_highs = df[pivot_high_col]
    pivot_lows = df[pivot_low_col] if pivot_low_col and pivot_low_col in df.columns else None
    previous_top_pos = None
    previous_top_value = None
    second_top_pos = None
    second_top_value = None
    candidate_neckline = None
    candidate_first_pos = None
    active_neckline_positions = []

    def clear_active_candidate() -> None:
        nonlocal second_top_pos, second_top_value, candidate_neckline, active_neckline_positions
        nonlocal candidate_first_pos

        for active_pos in active_neckline_positions:
            df.at[df.index[active_pos], dt_candidate_col] = pd.NA
            df.at[df.index[active_pos], neckline_col] = pd.NA

        second_top_pos = None
        second_top_value = None
        candidate_neckline = None
        candidate_first_pos = None
        active_neckline_positions = []

    def set_previous_top(pos: int, value: float) -> None:
        nonlocal previous_top_pos, previous_top_value

        previous_top_pos = pos
        previous_top_value = value

    def mark_candidate(pos: int, value: float, neckline: float | None) -> None:
        nonlocal active_neckline_positions

        if neckline is None:
            return
        index_value = df.index[pos]
        df.at[index_value, dt_candidate_col] = value
        df.at[index_value, neckline_col] = neckline
        active_neckline_positions = [pos]

    def get_neckline(first_pos: int, second_pos: int, first_value: float, second_value: float) -> float | None:
        start_pos = first_pos + 1
        end_pos = second_pos
        if start_pos >= end_pos:
            return None

        values = value_series.iloc[start_pos:end_pos].dropna()
        if values.empty:
            return None

        neckline = float(values.min())
        if neckline >= min(first_value, second_value):
            return None
        return neckline

    def is_neckline_break(pos: int, neckline: float | None) -> bool:
        if neckline is None or pos <= 0:
            return False
        current_value = value_series.iloc[pos]
        previous_value = value_series.iloc[pos - 1]
        if pd.isna(current_value) or pd.isna(previous_value):
            return False
        return current_value < neckline and previous_value >= neckline

    def _record_prev_opp(confirm_pos: int, first_pos) -> None:
        if prev_opp_col is None or pivot_lows is None or first_pos is None:
            return
        fp = int(first_pos)
        if fp <= 0:
            return
        segment = pivot_lows.iloc[:fp].dropna()
        if segment.empty:
            return
        df.at[df.index[confirm_pos], prev_opp_col] = float(segment.iloc[-1])

    def confirm_double_top(pos: int) -> None:
        nonlocal previous_top_pos, previous_top_value
        nonlocal second_top_pos, second_top_value, candidate_neckline, active_neckline_positions
        nonlocal candidate_first_pos

        if candidate_neckline is None:
            return
        dt_value = value_series.iloc[pos]
        if pd.isna(dt_value):
            return
        df.at[df.index[pos], dt_col] = float(dt_value)
        df.at[df.index[pos], neckline_col] = candidate_neckline
        _record_prev_opp(pos, candidate_first_pos)

        previous_top_pos = second_top_pos
        previous_top_value = second_top_value
        second_top_pos = None
        second_top_value = None
        candidate_neckline = None
        candidate_first_pos = None
        active_neckline_positions = []

    def activate_second_top_candidate(top_pos: int, top_value: float, neckline: float) -> None:
        nonlocal second_top_pos, second_top_value, candidate_neckline
        nonlocal candidate_first_pos

        candidate_first_pos = previous_top_pos
        second_top_pos = top_pos
        second_top_value = top_value
        candidate_neckline = neckline
        mark_candidate(second_top_pos, second_top_value, candidate_neckline)

    for pos in range(len(df)):
        if candidate_neckline is not None and second_top_pos is not None and pos > second_top_pos:
            df.at[df.index[pos], neckline_col] = candidate_neckline
            active_neckline_positions.append(pos)
            if is_neckline_break(pos, candidate_neckline):
                confirm_double_top(pos)
                continue

        pivot_value = pivot_highs.iloc[pos]
        if pd.isna(pivot_value):
            continue

        pivot_value = float(pivot_value)
        if previous_top_value is None:
            set_previous_top(pos, pivot_value)
            continue

        if pivot_value >= previous_top_value:
            clear_active_candidate()
            set_previous_top(pos, pivot_value)
            continue

        clear_active_candidate()
        neckline = get_neckline(previous_top_pos, pos, previous_top_value, pivot_value)
        if neckline is not None:
            activate_second_top_candidate(pos, pivot_value, neckline)
        set_previous_top(pos, pivot_value)

    return df


def detect_stochastic_bottom_patterns(df: pd.DataFrame, suffix: str, oversold_level: float = 20.0) -> pd.DataFrame:
    """Detects stochastic double bottoms using higher pivot lows and neckline breaks."""
    # Kept for call compatibility; the pivot/neckline definition does not use
    # an oversold-duration rule.
    _ = oversold_level
    return detect_double_bottom_patterns(
        df,
        f"stoch_k_{suffix}",
        f"stoch_pivot_low_{suffix}",
        f"stoch_db_{suffix}",
        f"stoch_db_candidate_{suffix}",
        f"stoch_neckline_{suffix}",
        kind_col=f"stoch_db_kind_{suffix}",
        delta_col=f"stoch_db_delta_{suffix}",
        first_pos_col=f"stoch_db_first_pos_{suffix}",
        pivot_high_col=f"stoch_pivot_high_{suffix}",
        prev_opp_col=f"stoch_db_prev_opp_{suffix}",
    )


def detect_stochastic_top_patterns(df: pd.DataFrame, suffix: str, overbought_level: float = 80.0) -> pd.DataFrame:
    """Detects stochastic double tops by reusing the double-bottom state machine on an
    inverted (100 - value) wave.

    쌍바닥 상태머신을 복제하지 않고 반전 호출로 구현한다. 이렇게 하면 쌍봉이 쌍바닥과
    봉 단위로 정확히 대칭이 된다. 결과는 기존 컬럼명(stoch_dt_*)에 그대로 기록한다.
    """
    k_col = f"stoch_k_{suffix}"
    pivot_high_col = f"stoch_pivot_high_{suffix}"
    pivot_low_col = f"stoch_pivot_low_{suffix}"
    dt_col = f"stoch_dt_{suffix}"
    dt_candidate_col = f"stoch_dt_candidate_{suffix}"
    dt_neckline_col = f"stoch_dt_neckline_{suffix}"

    dt_kind_col = f"stoch_dt_kind_{suffix}"
    dt_delta_col = f"stoch_dt_delta_{suffix}"

    df[dt_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_candidate_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_neckline_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
    df[dt_delta_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    dt_first_pos_col = f"stoch_dt_first_pos_{suffix}"
    dt_prev_opp_col = f"stoch_dt_prev_opp_{suffix}"
    df[dt_first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[dt_prev_opp_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if k_col not in df.columns or pivot_high_col not in df.columns or pivot_low_col not in df.columns:
        return df

    # 1) 임시 df에 100 - K, 피봇 고/저를 교환해 구성
    inverted = pd.DataFrame(index=df.index)
    inverted[k_col] = 100.0 - df[k_col]
    inverted[pivot_low_col] = 100.0 - df[pivot_high_col]
    inverted[pivot_high_col] = 100.0 - df[pivot_low_col]

    # 2) 기존 쌍바닥 검출을 oversold_level = 100 - overbought_level로 호출 (kind도 반전 공간에서 산출)
    inverted = detect_stochastic_bottom_patterns(inverted, suffix, oversold_level=100.0 - overbought_level)

    # 3) 결과를 100 - 값으로 되돌려 쌍봉 컬럼에 기록
    df[dt_col] = (100.0 - inverted[f"stoch_db_{suffix}"]).astype("Float64")
    df[dt_candidate_col] = (100.0 - inverted[f"stoch_db_candidate_{suffix}"]).astype("Float64")
    df[dt_neckline_col] = (100.0 - inverted[f"stoch_neckline_{suffix}"]).astype("Float64")

    # 4) kind는 반전 공간(HL/LL) -> 원공간(LH/HH)으로 뒤집어 매핑, delta는 부호 반전
    inv_kind = inverted[f"stoch_db_kind_{suffix}"]
    df[dt_kind_col] = inv_kind.map(_INVERT_KIND_MAP).astype("object")
    df[dt_delta_col] = (-inverted[f"stoch_db_delta_{suffix}"]).astype("Float64")
    # 위치는 반전 불변량 — 반전 공간 db first_pos를 그대로 복사
    df[dt_first_pos_col] = inverted[f"stoch_db_first_pos_{suffix}"].astype("Float64")
    # 값은 반전 복원 — neckline과 동일 패턴 (100 − v)
    db_prev_opp = inverted[f"stoch_db_prev_opp_{suffix}"]
    df[dt_prev_opp_col] = (100.0 - db_prev_opp).astype("Float64")
    return df


def detect_triple_bottom_patterns(
    df: pd.DataFrame,
    value_col: str,
    pivot_low_col: str,
    tb_col: str,
    kind_col: str,
    delta_col: str,
    oversold_level: float,
    first_pos_col: str | None = None,
) -> pd.DataFrame:
    """침체권 바닥 3개 + 넥라인(바닥1~3 사이 최고점) 상향 돌파로 쓰리바닥을 검출한다.

    구조적 검출만 한다(너비·독수리·애매함 해석은 공식 엔진의 몫). 기존 쌍바닥(db)
    검출과 독립적인 별도 컬럼에만 기록하므로 db/dt 출력에는 전혀 영향이 없다.

    - 침체권: 피봇 저점 값 <= oversold_level (경계 동치는 침체권에 포함).
    - kind/delta: 바닥3 vs 바닥2 비교(HL/LL/EQ). [F7-f] 독수리 패턴 대비용.
    """
    df[tb_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
    df[delta_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if first_pos_col is not None:
        df[first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if value_col not in df.columns or pivot_low_col not in df.columns:
        return df

    value_series = df[value_col]
    pivot_lows = df[pivot_low_col]
    bottoms: list[tuple[int, float]] = []   # 침체권 바닥(pos, value), 최근 3개만 유지
    neckline = None

    def compute_neckline(first_pos: int, third_pos: int):
        segment = value_series.iloc[first_pos + 1:third_pos].dropna()
        if segment.empty:
            return None
        peak = float(segment.max())
        # W·W 구조: 사이 최고점이 세 바닥보다 높아야 의미 있는 넥라인이다.
        if peak <= max(value for _, value in bottoms):
            return None
        return peak

    for pos in range(len(df)):
        # 1) 바닥 3개 확보 후 넥라인 상향 돌파 시 확정
        if len(bottoms) >= 3 and neckline is not None and pos > bottoms[2][0]:
            current = value_series.iloc[pos]
            previous = value_series.iloc[pos - 1] if pos > 0 else pd.NA
            if not pd.isna(current) and not pd.isna(previous) and current > neckline and previous <= neckline:
                df.at[df.index[pos], tb_col] = float(current)
                kind, delta = classify_pattern_kind(bottoms[1][1], bottoms[2][1])  # 바닥3 vs 바닥2
                df.at[df.index[pos], kind_col] = kind
                df.at[df.index[pos], delta_col] = delta
                if first_pos_col is not None:
                    df.at[df.index[pos], first_pos_col] = float(bottoms[0][0])
                bottoms = []
                neckline = None
                continue

        pivot_value = pivot_lows.iloc[pos]
        if pd.isna(pivot_value):
            continue
        pivot_value = float(pivot_value)
        if pivot_value > oversold_level:
            continue  # 침체권 밖 저점은 바닥 후보가 아니다(상승 파동의 일부)

        bottoms.append((pos, pivot_value))
        if len(bottoms) > 3:
            bottoms = bottoms[-3:]   # 침체권 복귀가 반복되면 최근 3개로 슬라이드
        neckline = compute_neckline(bottoms[0][0], bottoms[2][0]) if len(bottoms) >= 3 else None

    return df


def detect_stochastic_triple_bottom_patterns(df: pd.DataFrame, suffix: str, oversold_level: float = 20.0) -> pd.DataFrame:
    """스토캐스틱 %K 파동의 쓰리바닥 검출 (oversold_level은 쌍바닥 검출기와 동일 기본값)."""
    return detect_triple_bottom_patterns(
        df,
        f"stoch_k_{suffix}",
        f"stoch_pivot_low_{suffix}",
        f"stoch_tb_{suffix}",
        f"stoch_tb_kind_{suffix}",
        f"stoch_tb_delta_{suffix}",
        oversold_level=oversold_level,
        first_pos_col=f"stoch_tb_first_pos_{suffix}",
    )


def detect_stochastic_triple_top_patterns(df: pd.DataFrame, suffix: str, overbought_level: float = 80.0) -> pd.DataFrame:
    """쓰리봉 = 쌍봉과 동일하게 반전(100-값) 공간의 쓰리바닥 검출로 구현한다(완전 대칭).

    kind는 반전 공간(HL/LL) -> 원공간(LH/HH)으로 뒤집어 매핑, delta는 부호 반전한다.
    """
    k_col = f"stoch_k_{suffix}"
    pivot_high_col = f"stoch_pivot_high_{suffix}"
    pivot_low_col = f"stoch_pivot_low_{suffix}"
    tt_col = f"stoch_tt_{suffix}"
    tt_kind_col = f"stoch_tt_kind_{suffix}"
    tt_delta_col = f"stoch_tt_delta_{suffix}"

    df[tt_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    df[tt_kind_col] = pd.Series(pd.NA, index=df.index, dtype="object")
    df[tt_delta_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    tt_first_pos_col = f"stoch_tt_first_pos_{suffix}"
    df[tt_first_pos_col] = pd.Series(pd.NA, index=df.index, dtype="Float64")

    if k_col not in df.columns or pivot_high_col not in df.columns or pivot_low_col not in df.columns:
        return df

    inverted = pd.DataFrame(index=df.index)
    inverted[k_col] = 100.0 - df[k_col]
    inverted[pivot_low_col] = 100.0 - df[pivot_high_col]
    inverted[pivot_high_col] = 100.0 - df[pivot_low_col]

    inverted = detect_stochastic_triple_bottom_patterns(inverted, suffix, oversold_level=100.0 - overbought_level)

    df[tt_col] = (100.0 - inverted[f"stoch_tb_{suffix}"]).astype("Float64")
    inv_kind = inverted[f"stoch_tb_kind_{suffix}"]
    df[tt_kind_col] = inv_kind.map(_INVERT_KIND_MAP).astype("object")
    df[tt_delta_col] = (-inverted[f"stoch_tb_delta_{suffix}"]).astype("Float64")
    df[tt_first_pos_col] = inverted[f"stoch_tb_first_pos_{suffix}"].astype("Float64")
    return df


@st.cache_data(ttl=600)
def add_stochastic_slow_layers(df: pd.DataFrame) -> pd.DataFrame:
    """Adds 3-layer stacked stochastic slow values."""
    if df is None or df.empty:
        return df

    for layer in STOCH_LAYERS:
        k_len = layer["k_len"]
        k_smooth = layer["k_smooth"]
        d_len = layer["d_len"]
        offset = layer["offset"]
        suffix = layer["label"]

        lowest_low = df['low'].rolling(window=k_len, min_periods=k_len).min()
        highest_high = df['high'].rolling(window=k_len, min_periods=k_len).max()
        denominator = highest_high - lowest_low

        fast_k = ((df['close'] - lowest_low) / denominator.replace(0, pd.NA)) * 100.0
        # denominator가 정확히 0인 완전 평탄 구간만 0으로 채운다.
        # 워밍업(min_periods)으로 인한 NaN은 보존해야 상하 반전에 대해 %K가 대칭이 된다.
        # (워밍업 구간은 RECENT_WINDOW 밖이라 차트 표시에는 영향이 없다.)
        fast_k = fast_k.where(denominator != 0, 0.0)

        slow_k = fast_k.rolling(window=k_smooth, min_periods=k_smooth).mean()
        slow_d = slow_k.rolling(window=d_len, min_periods=d_len).mean()

        df[f'stoch_k_{suffix}'] = slow_k
        df[f'stoch_d_{suffix}'] = slow_d
        df[f'stoch_k_shifted_{suffix}'] = slow_k + offset
        df[f'stoch_d_shifted_{suffix}'] = slow_d + offset

        pivot_low, pivot_high = compute_stochastic_pivots(
            slow_k,
            lookback=STOCH_PIVOT_PARAMS["lookback"],
            middle_zone=STOCH_PIVOT_PARAMS["middle_zone"],
            min_gap=STOCH_PIVOT_PARAMS["min_gap"],
            min_delta=STOCH_PIVOT_PARAMS["min_delta"],
        )
        df[f'stoch_pivot_low_{suffix}'] = pivot_low
        df[f'stoch_pivot_high_{suffix}'] = pivot_high
        df[f'stoch_pivot_low_shifted_{suffix}'] = pivot_low + offset
        df[f'stoch_pivot_high_shifted_{suffix}'] = pivot_high + offset
        df = detect_stochastic_bottom_patterns(df, suffix)
        df = detect_stochastic_top_patterns(df, suffix)
        df = detect_stochastic_triple_bottom_patterns(df, suffix)
        df = detect_stochastic_triple_top_patterns(df, suffix)

    return df
