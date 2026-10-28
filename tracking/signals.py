"""고정 계측 원본에서 추출한 순수 신호 계산.

원본 validation/wave_ma60_turn_probe.py는 보존한다. 출처·함수 AST 대조는
config/refactor_provenance.json과 test_refactor_provenance.py가 관리한다.
"""
from __future__ import annotations
from typing import List, Optional
import numpy as np
import pandas as pd
from analysis.wave_mm_struct_stop import BUFFER
from config.settings import MA_PATTERN_PARAMS, STOCH_PIVOT_PARAMS, WAVE_LAYER_ROLES
from indicators.ma_patterns import compute_series_pivots

OBS_BARS = 20
LARGE = WAVE_LAYER_ROLES["large"]
STOCH_LAG = STOCH_PIVOT_PARAMS["lookback"]
MA_LAG = MA_PATTERN_PARAMS["lookback"]

def _last_pos_leq(mask: np.ndarray, c: int) -> Optional[int]:
    idx = np.flatnonzero(mask[: c + 1])
    return int(idx[-1]) if len(idx) else None


def extract_signals(pipe: pd.DataFrame) -> dict:
    """전체 이력 파이프라인 컬럼에서 신호 위치를 뽑고, as-of 가용 시점(known)을 붙인다.

    known = max(확정봉, 두 번째 극점 + 피봇 lookback). 검출기는 피봇 확정에 후행 봉이
    필요하므로 확정봉이 그보다 앞설 수 있다 — 그 차이만큼 신호를 늦게 안 것으로 취급.
    """
    n = len(pipe)
    low = pipe["low"].to_numpy(dtype=float)

    db = pipe[f"stoch_db_{LARGE}"].notna().to_numpy()
    db_first = pipe[f"stoch_db_first_pos_{LARGE}"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    piv_low = pipe[f"stoch_pivot_low_{LARGE}"].notna().to_numpy()
    piv_high = pipe[f"stoch_pivot_high_{LARGE}"].notna().to_numpy()
    dt = pipe[f"stoch_dt_{LARGE}"].notna().to_numpy()

    ma10_dt = pipe["ma10_dt"].notna().to_numpy()
    # 10MA 쌍봉은 -MA10 공간의 피봇저점(=원공간 고점) 상태머신이므로 같은 경로로 두 번째 고점을 복원
    inv_pl, _ = compute_series_pivots(
        -pd.to_numeric(pipe["MA10"], errors="coerce"),
        lookback=MA_PATTERN_PARAMS["lookback"], min_gap=MA_PATTERN_PARAMS["min_gap"],
        rel_tolerance=MA_PATTERN_PARAMS["rel_tolerance"],
    )
    ma10_piv_high = inv_pl.notna().to_numpy()

    cands: List[dict] = []
    for c in np.flatnonzero(db):
        c = int(c)
        p2 = _last_pos_leq(piv_low, c)
        p1 = int(db_first[c]) if np.isfinite(db_first[c]) else None
        if p2 is None or p1 is None or p1 >= p2:
            continue
        known = max(c, p2 + STOCH_LAG)
        cands.append({
            "confirm_pos": c, "known_pos": min(known, n - 1), "lag": known - c,
            "p1": p1, "p2": p2,
            "pattern_low": float(np.nanmin(low[p1:p2 + 1])),
        })

    def _tops(mask: np.ndarray, piv: np.ndarray, lag: int) -> List[dict]:
        out = []
        for c in np.flatnonzero(mask):
            c = int(c)
            p2 = _last_pos_leq(piv, c)
            if p2 is None:
                continue
            known = max(c, p2 + lag)
            out.append({"confirm_pos": c, "known_pos": min(known, n - 1), "lag": known - c})
        return out

    stoch_tops = _tops(dt, piv_high, STOCH_LAG)
    ma10_tops = _tops(ma10_dt, ma10_piv_high, MA_LAG)

    sell_stoch = np.zeros(n, dtype=bool)
    sell_ma10 = np.zeros(n, dtype=bool)
    for s in stoch_tops:
        sell_stoch[s["known_pos"]] = True
    for s in ma10_tops:
        sell_ma10[s["known_pos"]] = True

    ma60 = pd.to_numeric(pipe["MA60"], errors="coerce").to_numpy(dtype=float)
    prev = np.roll(ma60, 1); prev[0] = np.nan
    up = (ma60 > prev) & np.isfinite(ma60) & np.isfinite(prev)
    up_prev = np.roll(up, 1); up_prev[0] = False
    prev2 = np.roll(ma60, 2); prev2[:2] = np.nan
    valid_turn = np.isfinite(prev2) & np.isfinite(prev) & np.isfinite(ma60)
    turn = up & ~up_prev & valid_turn

    return {
        "cands": cands, "stoch_tops": stoch_tops, "ma10_tops": ma10_tops,
        "sell_stoch": sell_stoch, "sell_ma10": sell_ma10,
        "ma60_up": up, "ma60_turn": turn, "ma60_valid": np.isfinite(ma60) & np.isfinite(prev),
    }
