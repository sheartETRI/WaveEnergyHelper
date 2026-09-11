"""KeyChartScore v0 (§4) — 게이트·깔끔함 점수와 프레임 상태(as-of) 구축.

기존 판정 함수(analysis/structure.py, indicators/stochastic.py)는 import해서 호출만 한다.
유일한 예외는 (20,10,10) 레이어의 %K 산술식으로, add_stochastic_slow_layers가 3개 레이어를
한꺼번에 계산해 대파동만 필요한 이 검증에서 3배 비용이 되기 때문에 동일 식을 옮겨 적었다.
이 복제가 원본과 봉 단위로 일치함은 test_no_lookahead.py의 conformance 테스트가 강제한다.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analysis.structure import classify_structure_at  # noqa: E402
from config.settings import STOCH_LAYERS, STOCH_PIVOT_PARAMS, WAVE_LAYER_ROLES  # noqa: E402
from indicators.moving_averages import add_moving_averages  # noqa: E402
from indicators.stochastic import (  # noqa: E402
    compute_stochastic_pivots,
    detect_stochastic_bottom_patterns,
    detect_stochastic_top_patterns,
    detect_stochastic_triple_bottom_patterns,
    detect_stochastic_triple_top_patterns,
)

from validation.keychart import data_io  # noqa: E402
from validation.keychart import params_v0 as P  # noqa: E402

LARGE_SFX = WAVE_LAYER_ROLES["large"]          # "(20,10,10)"
LARGE_LAYER = next(x for x in STOCH_LAYERS if x["label"] == LARGE_SFX)

STATE_DIR = os.path.join(HERE, "_state_cache")

# 구조 라벨 → int8 코드
STRUCT_CODE = {None: 0, "U1": 1, "U2": 2, "U3": 3, "D1": -1, "D2": -2, "D3": -3}

BOTTOM_TYPES = ("db", "tb")
TOP_TYPES = ("dt", "tt")


# --------------------------------------------------------------------- 지표 계산
def add_large_stoch_layer(df: pd.DataFrame) -> pd.DataFrame:
    """(20,10,10) 대파동 레이어 %K/피봇/패턴만 계산 (add_stochastic_slow_layers 부분집합)."""
    k_len, k_smooth, d_len = LARGE_LAYER["k_len"], LARGE_LAYER["k_smooth"], LARGE_LAYER["d_len"]
    lowest_low = df["low"].rolling(window=k_len, min_periods=k_len).min()
    highest_high = df["high"].rolling(window=k_len, min_periods=k_len).max()
    denominator = highest_high - lowest_low
    fast_k = ((df["close"] - lowest_low) / denominator.replace(0, pd.NA)) * 100.0
    fast_k = fast_k.where(denominator != 0, 0.0)
    slow_k = fast_k.rolling(window=k_smooth, min_periods=k_smooth).mean()
    slow_d = slow_k.rolling(window=d_len, min_periods=d_len).mean()

    df[f"stoch_k_{LARGE_SFX}"] = slow_k
    df[f"stoch_d_{LARGE_SFX}"] = slow_d
    pivot_low, pivot_high = compute_stochastic_pivots(slow_k, **STOCH_PIVOT_PARAMS)
    df[f"stoch_pivot_low_{LARGE_SFX}"] = pivot_low
    df[f"stoch_pivot_high_{LARGE_SFX}"] = pivot_high

    df = detect_stochastic_bottom_patterns(df, LARGE_SFX)
    df = detect_stochastic_top_patterns(df, LARGE_SFX)
    df = detect_stochastic_triple_bottom_patterns(df, LARGE_SFX)
    df = detect_stochastic_triple_top_patterns(df, LARGE_SFX)
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV → MA + 대파동 레이어."""
    ma = getattr(add_moving_averages, "__wrapped__", add_moving_averages)
    out = ma(df.copy())
    for w in (5, 10, 20, 60, 120, 240):
        col = f"MA{w}"
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    return add_large_stoch_layer(out)


# --------------------------------------------------------------------- 이벤트 추출
def _clean_scores(kind: str, v1: float, v2: float, v_all: list,
                  gap: int, neckline: float, breakout: float) -> dict:
    """§4.2 깔끔함 점수 c1~c4. c5는 as-of 구조에 의존하므로 조회 시점에 더한다."""
    c1 = 1.0 - min(1.0, abs(v1 - v2) / P.SYM_SCALE)
    c2 = max(0.0, 1.0 - abs(gap - P.GAP_CENTER) / P.GAP_WIDTH)
    c3 = min(1.0, abs(breakout - neckline) / P.BREAK_SCALE)
    if kind in BOTTOM_TYPES:
        c4 = min(1.0, max(0.0, (P.OVERSOLD - min(v_all)) / P.EXTREME_SCALE))
    else:
        c4 = min(1.0, max(0.0, (max(v_all) - P.OVERBOUGHT) / P.EXTREME_SCALE))
    return {"c1": c1, "c2": c2, "c3": c3, "c4": c4}


def _as_float(series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").astype(float).to_numpy()


def extract_events(d: pd.DataFrame) -> pd.DataFrame:
    """확정 패턴 → 이벤트 표(확정 위치·기하·c1~c4·알 수 있게 되는 위치)."""
    sfx = LARGE_SFX
    k = _as_float(d[f"stoch_k_{sfx}"])
    pl = _as_float(d[f"stoch_pivot_low_{sfx}"])
    ph = _as_float(d[f"stoch_pivot_high_{sfx}"])
    pl_pos = np.flatnonzero(~np.isnan(pl))
    ph_pos = np.flatnonzero(~np.isnan(ph))
    tb_pos = pl_pos[pl[pl_pos] <= P.OVERSOLD]
    tt_pos = ph_pos[ph[ph_pos] >= P.OVERBOUGHT]

    specs = [
        ("db", f"stoch_db_{sfx}", f"stoch_neckline_{sfx}", f"stoch_db_first_pos_{sfx}", pl, pl_pos, 2),
        ("dt", f"stoch_dt_{sfx}", f"stoch_dt_neckline_{sfx}", f"stoch_dt_first_pos_{sfx}", ph, ph_pos, 2),
        ("tb", f"stoch_tb_{sfx}", None, f"stoch_tb_first_pos_{sfx}", pl, tb_pos, 3),
        ("tt", f"stoch_tt_{sfx}", None, f"stoch_tt_first_pos_{sfx}", ph, tt_pos, 3),
    ]

    rows = []
    dropped = 0
    for kind, conf_col, neck_col, first_col, pivots, pivot_pos, n_ext in specs:
        conf = _as_float(d[conf_col])
        first = _as_float(d[first_col])
        neck = _as_float(d[neck_col]) if neck_col is not None else None
        for c in np.flatnonzero(~np.isnan(conf)):
            c = int(c)
            if np.isnan(first[c]):
                dropped += 1
                continue
            p1 = int(first[c])
            # 확정 봉 직전의 극값들 (해당 종류의 피봇 계열에서)
            j = int(np.searchsorted(pivot_pos, c))
            if j < n_ext - 1:
                dropped += 1
                continue
            p_last = int(pivot_pos[j - 1])
            p_prev = int(pivot_pos[j - 2]) if j >= 2 else None
            if n_ext == 2:
                pa, pb = p1, p_last
            else:
                if p_prev is None:
                    dropped += 1
                    continue
                pa, pb = p_prev, p_last            # 마지막 두 극값 (params TRIPLE_USES_LAST_TWO)
            if pb <= pa:
                dropped += 1
                continue
            v1, v2 = float(pivots[pa]), float(pivots[pb])
            v_all = [v1, v2] if n_ext == 2 else [float(pivots[p1]), v1, v2]
            if neck is not None:
                neckline = float(neck[c])
            else:
                seg = k[p1 + 1:p_last]
                seg = seg[~np.isnan(seg)]
                if seg.size == 0:
                    dropped += 1
                    continue
                neckline = float(seg.max() if kind == "tb" else seg.min())
            if np.isnan(neckline) or np.isnan(v1) or np.isnan(v2) or any(np.isnan(v_all)):
                dropped += 1
                continue
            breakout = float(conf[c])
            comps = _clean_scores(kind, v1, v2, v_all, pb - pa, neckline, breakout)
            row = {
                "kind": kind,
                "direction": 1 if kind in BOTTOM_TYPES else -1,
                "confirm_pos": c,
                "first_pos": p1,
                "ext_a_pos": pa,
                "ext_b_pos": pb,
                "v1": v1, "v2": v2, "gap": int(pb - pa),
                "neckline": neckline, "breakout": breakout,
                "knowable_pos": max(c, pb + P.PIVOT_STABILITY_LAG),
            }
            row.update(comps)
            rows.append(row)

    ev = pd.DataFrame(rows, columns=EVENT_COLUMNS[:-1]) if rows else pd.DataFrame(columns=EVENT_COLUMNS)
    if rows:
        ev["score_base"] = 0.2 * (ev["c1"] + ev["c2"] + ev["c3"] + ev["c4"])
        ev = ev.sort_values(["knowable_pos", "confirm_pos"]).reset_index(drop=True)
    ev.attrs["dropped"] = dropped
    return ev


EVENT_COLUMNS = [
    "kind", "direction", "confirm_pos", "first_pos", "ext_a_pos", "ext_b_pos",
    "v1", "v2", "gap", "neckline", "breakout", "knowable_pos",
    "c1", "c2", "c3", "c4", "score_base",
]


def structure_codes(d: pd.DataFrame) -> np.ndarray:
    """봉별 구조 라벨 코드. 기존 classify_structure_at을 그대로 호출한다."""
    small = d[["close", "MA5", "MA10", "MA20", "MA60", "MA120", "MA240"]]
    n = len(small)
    out = np.zeros(n, dtype=np.int8)
    for i in range(min(P.MA_WARMUP_BARS, n), n):   # §6: MA240 워밍업 앞 240봉 제외
        out[i] = STRUCT_CODE[classify_structure_at(small, i)]
    return out


def last_event_maps(ev: pd.DataFrame, n: int):
    """봉 p 시점에 '알 수 있는' 가장 최근 바닥/천정 이벤트 인덱스(-1=없음)."""
    last_bot = np.full(n, -1, dtype=np.int32)
    last_top = np.full(n, -1, dtype=np.int32)
    if ev.empty:
        return last_bot, last_top
    prio = {k: i for i, k in enumerate(P.PATTERN_PRIORITY)}
    ordered = ev.assign(_p=ev["kind"].map(prio)).sort_values(
        ["knowable_pos", "confirm_pos", "_p"]).index.to_numpy()
    kp = ev["knowable_pos"].to_numpy()
    kinds = ev["kind"].to_numpy()
    cur_b = cur_t = -1
    ptr = 0
    for p in range(n):
        while ptr < len(ordered) and kp[ordered[ptr]] <= p:
            e = int(ordered[ptr])
            if kinds[e] in BOTTOM_TYPES:
                cur_b = e
            else:
                cur_t = e
            ptr += 1
        last_bot[p] = cur_b
        last_top[p] = cur_t
    return last_bot, last_top


# --------------------------------------------------------------------- 프레임 상태
class FrameState:
    """as-of 조회용 프레임 상태(봉 배열 + 이벤트 표)."""

    def __init__(self, symbol: str, frame: str, bars: pd.DataFrame, events: pd.DataFrame):
        self.symbol = symbol
        self.frame = frame
        self.bars = bars
        self.events = events
        self.close_ns = bars["close_time"].to_numpy("datetime64[ns]").astype("int64")
        self.open_ns = bars["open_time"].to_numpy("datetime64[ns]").astype("int64")
        self.struct = bars["struct"].to_numpy(np.int8)
        self.last_bot = bars["last_bot"].to_numpy(np.int32)
        self.last_top = bars["last_top"].to_numpy(np.int32)
        self.open_px = bars["open"].to_numpy(float)
        self.close_px = bars["close"].to_numpy(float)
        self.high_px = bars["high"].to_numpy(float)
        self.low_px = bars["low"].to_numpy(float)
        if events.empty:
            self.ev_confirm = np.zeros(0, np.int64)
            self.ev_know = np.zeros(0, np.int64)
            self.ev_score = np.zeros(0, float)
            self.ev_dir = np.zeros(0, np.int8)
        else:
            self.ev_confirm = events["confirm_pos"].to_numpy(np.int64)
            self.ev_know = events["knowable_pos"].to_numpy(np.int64)
            self.ev_score = events["score_base"].to_numpy(float)
            self.ev_dir = events["direction"].to_numpy(np.int8)

    def __len__(self) -> int:
        return len(self.close_ns)

    def pos_asof(self, t_ns: int) -> int:
        """시각 t에 마감이 끝난 마지막 봉의 위치(-1 = 없음)."""
        return int(np.searchsorted(self.close_ns, t_ns, side="right")) - 1

    def gate_at(self, pos: int, db_recent: int = P.DB_RECENT_BARS,
                allow_partial: bool = False):
        """§4.1 G1~G3 통과 시 {event, direction, score}, 아니면 None."""
        if pos < P.MA_WARMUP_BARS or pos >= len(self.struct):
            return None
        sc = int(self.struct[pos])
        if sc == 3:
            direction, c5 = 1, P.C5_FULL
        elif sc == -3:
            direction, c5 = -1, P.C5_FULL
        elif allow_partial and sc == 2:
            direction, c5 = 1, P.C5_PARTIAL
        elif allow_partial and sc == -2:
            direction, c5 = -1, P.C5_PARTIAL
        else:
            return None
        e = int(self.last_bot[pos] if direction > 0 else self.last_top[pos])
        if e < 0:
            return None
        if self.ev_confirm[e] < pos - db_recent:       # G2 최근성
            return None
        return {"event": e, "direction": direction,
                "score": float(self.ev_score[e] + 0.2 * c5)}


def _state_paths(symbol: str, frame: str):
    tag = f"{symbol}_{frame}"
    return (os.path.join(STATE_DIR, f"{tag}__bars.parquet"),
            os.path.join(STATE_DIR, f"{tag}__events.parquet"))


def build_state(symbol: str, frame: str, force: bool = False) -> None:
    bars_path, ev_path = _state_paths(symbol, frame)
    if not force and os.path.exists(bars_path) and os.path.exists(ev_path):
        print(f"  cached state {symbol} {frame}", flush=True)
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    raw = data_io.load(symbol, frame)
    d = prepare(raw)
    ev = extract_events(d)
    struct = structure_codes(d)
    last_bot, last_top = last_event_maps(ev, len(d))
    bars = pd.DataFrame({
        "open_time": d.index,
        "close_time": data_io.bar_close_times(frame, d.index),
        "open": d["open"].to_numpy(float),
        "high": d["high"].to_numpy(float),
        "low": d["low"].to_numpy(float),
        "close": d["close"].to_numpy(float),
        "struct": struct,
        "last_bot": last_bot,
        "last_top": last_top,
    })
    bars.to_parquet(bars_path, index=False)
    ev.to_parquet(ev_path, index=False)
    print(f"  state {symbol} {frame}: bars={len(bars)} events={len(ev)} "
          f"dropped={ev.attrs.get('dropped', 0)}", flush=True)


def load_state(symbol: str, frame: str) -> FrameState:
    bars_path, ev_path = _state_paths(symbol, frame)
    return FrameState(symbol, frame, pd.read_parquet(bars_path), pd.read_parquet(ev_path))
