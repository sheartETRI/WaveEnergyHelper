"""Wave HTF Gate V2 — SPEC_WAVE_HTF_GATE_V2 (R0 기저율 관문 + 본 검정, 관측 전용).

v1(analysis.wave_htf_gate)의 게이트·판정 로직은 삭제하지 않고 그대로 재사용한다.
v2에서 바뀌는 것은 G_ALIGN 정의뿐이며, 그 교체가 R1 결과(1d 완전정배열 기저율 0)를
본 뒤의 **사후 완화**라는 사실을 GATE_NOTE 로 코드에 남긴다 (스펙 C1).

v1 G_ALIGN : engine.get_ma_alignment == 6개 코어 이평 완전 정배열
v2 G_ALIGN : [F2-b] MA60·120·240 이 모두 상승 (MA(t) > MA(t-1), 기울기 창 1봉 고정)
"""
from __future__ import annotations

import math
import os
from contextlib import contextmanager
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from analysis import wave_energy as wave_energy_mod
from analysis import wave_tracker
from analysis.wave_htf_gate import (
    CALIB_THRESHOLD,
    MA_WARMUP,
    _cache_dir,
    close_time_of,
    interval_delta,
    is_bullish_alignment,
    is_wave_bottom_state,
)
from analysis.wave_htf_gate import alignment_timeline as _v1_alignment_timeline

GATE_VERSION_V1 = "v1_full_alignment"
GATE_VERSION_V2 = "v2_f2b"
GATE_NOTE = (
    "v2 G_ALIGN(F2-b)은 R1에서 1d 완전정배열 기저율이 260봉 중 0으로 관측된 뒤 "
    "교체된 사후 완화 게이트다 (SPEC_V2 C1). 임계값 튜닝이 아니라 책 공식 교체이며, "
    "R1을 본 뒤의 변경이라는 사실은 리포트에 명기한다."
)

# --- §2.1 TF쌍 (4배 고정, 추가 탐색 금지) ---
PAIRS_V2: Dict[str, Tuple[str, str]] = {
    "PAIR_B": ("4h", "1h"),
    "PAIR_C": ("1d", "6h"),
}
SYMBOLS_V2 = ("BTCUSDT", "ETHUSDT", "BNBUSDT")

# --- §2.2 F2-b ---
F2B_MA_PERIODS = (60, 120, 240)
F2B_SLOPE_BARS = 1  # 자유 파라미터 금지 — 1봉 고정 (§2.2)

# --- §2.4 관측 구간 ---
WINDOW_MAIN = ("2021-01-01", "2026-09-01")
WINDOW_EXTENDED = ("2017-09-01", "2026-09-01")  # §3.3 1회 연장용

# --- §3 R0 ---
R0_MIN_EXPECTED_N = 30
# §3.2: event_rate 는 R1 실측치로 고정한다 (심볼별 이벤트수 / R1 관측봉수).
R1_EVENT_COUNTS_1H = {"BNBUSDT": 180, "BTCUSDT": 142, "ETHUSDT": 119}
R1_EVENT_COUNTS_4H = {"BNBUSDT": 182, "BTCUSDT": 133, "ETHUSDT": 138}
R1_OBS_BARS_1H = 505   # 2026-05-22 13:00 ~ 2026-06-12 06:00
R1_OBS_BARS_4H = 528   # 2026-03-23 08:00 ~ 2026-06-12 04:00

# --- 구현 파라미터 (판정 무관, 패리티 테스트로 강제) ---
STATE_WINDOW_BARS = 600  # 봉별 재계산 시 후행 절단 폭
_MEMO_MAX = 8


def _v2_state_path(symbol: str, htf: str) -> str:
    return os.path.join(_cache_dir(), f"htf_state_v2_{symbol}_{htf}.csv")


# ------------------------------------------------------------------ F2-b
def f2b_rising_flags(pipe: pd.DataFrame) -> pd.Series:
    """[F2-b] MA60·120·240 이 모두 직전 봉 대비 상승인가 (봉별 bool).

    경계: MA(t) == MA(t-1) 은 상승이 아니므로 게이트를 닫는다.
    MA 는 인과적 rolling 이라 전체 프레임 1회 계산으로 봉별 값이 확정된다.
    """
    if pipe is None or pipe.empty:
        return pd.Series(dtype=bool)
    flags = pd.Series(True, index=pipe.index)
    for period in F2B_MA_PERIODS:
        col = f"MA{period}"
        if col not in pipe.columns:
            return pd.Series(False, index=pipe.index)
        ma = pd.to_numeric(pipe[col], errors="coerce")
        prev = ma.shift(F2B_SLOPE_BARS)
        rising = (ma > prev) & ma.notna() & prev.notna()
        flags &= rising
    return flags.astype(bool)


def is_f2b_rising_at(pipe: pd.DataFrame, pos: int) -> bool:
    """단일 봉 F2-b 판정 (pos 는 정수 위치)."""
    if pipe is None or pipe.empty or pos < F2B_SLOPE_BARS or pos >= len(pipe):
        return False
    for period in F2B_MA_PERIODS:
        col = f"MA{period}"
        if col not in pipe.columns:
            return False
        cur = pd.to_numeric(pd.Series([pipe[col].iloc[pos]]), errors="coerce").iloc[0]
        prev = pd.to_numeric(
            pd.Series([pipe[col].iloc[pos - F2B_SLOPE_BARS]]), errors="coerce",
        ).iloc[0]
        if pd.isna(cur) or pd.isna(prev) or not (cur > prev):
            return False
    return True


# -------------------------------------------------- 윈도 절단 상태 타임라인
@contextmanager
def _patched_windowed_loader(
    symbol: str,
    as_of: pd.Timestamp,
    ohlcv_cache: Dict[str, pd.DataFrame],
    window: Optional[int],
    memo: dict,
):
    """analyze_wave_energy 의 상위/추세 프레임 로딩을 as-of 절단 + 윈도 + 메모이제이션.

    display.asof.patch_load_frame_for_asof 와 동일한 의미이되,
    (1) 후행 window 봉만 재계산하고 (2) 절단 결과가 같으면 재사용한다.
    """
    from display.asof import run_indicator_pipeline

    original = wave_energy_mod._load_frame

    def _patched(sym: str, iv: str):
        if sym != symbol:
            return original(sym, iv)
        bare = ohlcv_cache.get(iv)
        if bare is None:
            return None
        cut = bare.loc[bare.index <= as_of]
        if cut.empty:
            return None
        if window:
            cut = cut.iloc[-window:]
        key = (iv, cut.index[-1], len(cut))
        hit = memo.get(key)
        if hit is not None:
            return hit
        out = run_indicator_pipeline(cut)
        if len(memo) >= _MEMO_MAX:
            memo.clear()
        memo[key] = out
        return out

    wave_energy_mod._load_frame = _patched
    try:
        yield
    finally:
        wave_energy_mod._load_frame = original


def run_state_timeline(
    symbol: str,
    interval: str,
    bare: pd.DataFrame,
    ohlcv_cache: Dict[str, pd.DataFrame],
    *,
    warmup: int = MA_WARMUP,
    window: Optional[int] = STATE_WINDOW_BARS,
    progress_every: int = 0,
) -> pd.DataFrame:
    """wave_tracker 상태 타임라인 (윈도 절단판).

    wave_tracker.run_timeline 과 동일한 상태머신·신호 추출을 사용한다.
    window=None 이면 run_timeline 과 완전히 같은 계산이고, 정수면 후행 window 봉만
    재계산한다. 두 결과의 동일성은 tests 의 패리티 테스트로 강제한다.
    """
    from display.asof import run_indicator_pipeline

    ctx = wave_tracker._MachineContext()
    memo: dict = {}
    rows: List[dict] = []
    start = min(warmup, len(bare) - 1)

    for i in range(start, len(bare)):
        as_of = bare.index[i]
        lo = 0 if not window else max(0, i + 1 - window)
        cut = bare.iloc[lo:i + 1]
        if cut.empty:
            continue
        base_df = run_indicator_pipeline(cut.copy())
        with _patched_windowed_loader(symbol, as_of, ohlcv_cache, window, memo):
            report = wave_energy_mod.analyze_wave_energy(base_df, symbol, interval)
        sig = wave_tracker.extract_bar_signals(
            report, base_df, ctx.prev_major_oversold, ctx.prev_major_k,
        )
        snap = wave_tracker.step_tracker(ctx, sig, pd.Timestamp(as_of), i)
        rows.append({
            "timestamp": as_of,
            "state": snap.state,
            "duration": snap.duration,
            "reason": snap.reason,
            "invalidated": snap.invalidated,
        })
        if progress_every and (i - start) % progress_every == 0:
            print(f"    [{symbol} {interval}] {i - start + 1}/{len(bare) - start}", flush=True)

    return pd.DataFrame(rows)


# ------------------------------------------------------------ 상태 캐시 빌드
def _bars_between(start: pd.Timestamp, end: pd.Timestamp, interval: str) -> int:
    return int(math.ceil((end - start) / interval_delta(interval)))


def fetch_window_bare(
    symbol: str,
    interval: str,
    start: str,
    end: str,
    *,
    pad_bars: int,
) -> pd.DataFrame:
    """[start - pad_bars봉, end] 구간 OHLCV. pad 는 MA 워밍업 + 트래커 번인용."""
    from display.asof import fetch_ohlcv_bare

    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    now = pd.Timestamp.utcnow().tz_localize(None)
    need = _bars_between(s, min(e, now), interval) + pad_bars + 5
    bare = fetch_ohlcv_bare(symbol, interval, need, paginated=need > 1000)
    if bare is None or bare.empty:
        raise RuntimeError(f"fetch failed: {symbol} {interval}")
    return bare.loc[bare.index <= e]


def cache_limits(htf: str, bare: pd.DataFrame, end: str) -> Dict[str, int]:
    """추세(1d)·상위 프레임도 구간 전체를 덮도록 fetch 한도를 키운다.

    build_ohlcv_cache 의 기본값(get_auto_limit)은 1d 500봉이라, 2021년 시작 구간에서는
    추세 프레임이 구간 앞부분을 못 덮는다. 커스텀 인터벌(4d 등)은 베이스 봉수 기준이다.
    """
    from analysis.wave_energy import resolve_upper_frame
    from config.settings import WAVE_ENERGY_PARAMS
    from data.processor import get_fetch_interval

    span_start = pd.Timestamp(bare.index.min())
    span_end = min(pd.Timestamp(end), pd.Timestamp(bare.index.max()))
    limits: Dict[str, int] = {htf: len(bare)}
    for iv in (WAVE_ENERGY_PARAMS["trend_interval"], resolve_upper_frame(htf)):
        if not iv or iv == htf:
            continue
        base_iv = get_fetch_interval(iv)
        limits[iv] = _bars_between(span_start, span_end, base_iv) + 300
    return limits


def build_htf_states_v2(
    symbol: str,
    htf: str,
    *,
    start: str = WINDOW_MAIN[0],
    end: str = WINDOW_MAIN[1],
    window: Optional[int] = STATE_WINDOW_BARS,
    warmup: int = MA_WARMUP,
    burn_in: int = MA_WARMUP,
    progress_every: int = 0,
) -> pd.DataFrame:
    """[start, end] 구간의 HTF 닫힌 봉 상태 + v1/v2 게이트 플래그."""
    from display.asof import build_ohlcv_cache, run_indicator_pipeline

    pad = warmup + burn_in
    bare = fetch_window_bare(symbol, htf, start, end, pad_bars=pad)
    cache = build_ohlcv_cache(
        symbol, htf, bare, extra_limits=cache_limits(htf, bare, end),
    )

    timeline = run_state_timeline(
        symbol, htf, bare, cache,
        warmup=warmup, window=window, progress_every=progress_every,
    )
    if timeline.empty:
        return pd.DataFrame()

    pipe = run_indicator_pipeline(bare)
    align_v1 = pd.Series(_v1_alignment_timeline(pipe), index=pipe.index)
    align_v2 = f2b_rising_flags(pipe)

    out = timeline.rename(columns={"timestamp": "htf_open_time", "state": "htf_state"})
    out["htf_open_time"] = pd.to_datetime(out["htf_open_time"])
    out["htf_alignment"] = out["htf_open_time"].map(align_v1)
    out["align_v1"] = out["htf_alignment"].map(is_bullish_alignment)
    out["align_v2"] = out["htf_open_time"].map(align_v2).fillna(False).astype(bool)
    out["g_wave"] = out["htf_state"].map(is_wave_bottom_state)
    out["htf_close_time"] = close_time_of(out["htf_open_time"], htf).to_numpy()
    out["symbol"] = symbol
    out["htf"] = htf
    out = out[out["htf_open_time"] >= pd.Timestamp(start)]
    cols = [
        "symbol", "htf", "htf_open_time", "htf_close_time", "htf_state",
        "htf_alignment", "align_v1", "align_v2", "g_wave",
    ]
    return out[cols].sort_values("htf_close_time").reset_index(drop=True)


def load_htf_states_v2(symbol: str, htf: str) -> pd.DataFrame:
    path = _v2_state_path(symbol, htf)
    if not os.path.isfile(path):
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["htf_open_time", "htf_close_time"])
    for col in ("align_v1", "align_v2", "g_wave"):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].map(lambda x: str(x).lower() in ("true", "1", "yes"))
    return df


def apply_gate_version(states: pd.DataFrame, version: str = GATE_VERSION_V2) -> pd.DataFrame:
    """선택한 게이트 버전을 g_align / g_both 컬럼으로 확정한다."""
    if states.empty:
        return states
    out = states.copy()
    col = "align_v2" if version == GATE_VERSION_V2 else "align_v1"
    out["gate_version"] = version
    out["g_align"] = out[col].astype(bool)
    out["g_wave"] = out["g_wave"].astype(bool)
    out["g_both"] = out["g_align"] & out["g_wave"]
    return out


# ----------------------------------------------------------- R0 기저율 관문
def baseline_rates(
    version: str = GATE_VERSION_V2,
    pairs: Optional[Dict[str, Tuple[str, str]]] = None,
    symbols: Sequence[str] = SYMBOLS_V2,
) -> List[dict]:
    """§3.1 — (pair, symbol)별 P(G_ALIGN), P(G_WAVE), P(G_BOTH) 봉 비율."""
    pairs = pairs or PAIRS_V2
    rows: List[dict] = []
    for pair, (htf, ltf) in pairs.items():
        for sym in symbols:
            st = apply_gate_version(load_htf_states_v2(sym, htf), version)
            if st.empty:
                rows.append({"pair": pair, "htf": htf, "ltf": ltf, "symbol": sym, "bars": 0})
                continue
            n = len(st)
            rows.append({
                "pair": pair,
                "htf": htf,
                "ltf": ltf,
                "symbol": sym,
                "bars": n,
                "first_bar": st["htf_open_time"].min(),
                "last_bar": st["htf_open_time"].max(),
                "p_align": round(float(st["g_align"].mean()), 6),
                "p_wave": round(float(st["g_wave"].mean()), 6),
                "p_both": round(float(st["g_both"].mean()), 6),
                "n_align": int(st["g_align"].sum()),
                "n_wave": int(st["g_wave"].sum()),
                "n_both": int(st["g_both"].sum()),
            })
    return rows


def event_rate(ltf: str, symbol: str) -> Optional[float]:
    """§3.2 — R1 실측 이벤트 발생률 (건/LTF봉). 6h 는 4h 실측의 봉수 비례 환산."""
    if ltf == "1h":
        cnt = R1_EVENT_COUNTS_1H.get(symbol)
        return None if cnt is None else cnt / R1_OBS_BARS_1H
    if ltf in ("4h", "6h"):
        cnt = R1_EVENT_COUNTS_4H.get(symbol)
        if cnt is None:
            return None
        rate_4h = cnt / R1_OBS_BARS_4H
        if ltf == "4h":
            return rate_4h
        # 6h 봉은 4h 봉보다 1.5배 길다 → 봉당 발생률을 봉 길이에 비례 환산 (근사)
        return rate_4h * 1.5
    return None


def expected_sample(
    rates: List[dict],
    start: str,
    end: str,
    pairs: Optional[Dict[str, Tuple[str, str]]] = None,
) -> List[dict]:
    """§3.2 — n̂(pair) = Σ_sym [event_rate × LTF봉수 × P(G_BOTH)]."""
    pairs = pairs or PAIRS_V2
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out: List[dict] = []
    for pair, (htf, ltf) in pairs.items():
        ltf_bars = _bars_between(s, e, ltf)
        total = 0.0
        detail = []
        for r in rates:
            if r["pair"] != pair or not r.get("bars"):
                continue
            rate = event_rate(ltf, r["symbol"])
            if rate is None:
                continue
            n_hat = rate * ltf_bars * r["p_both"]
            total += n_hat
            detail.append({
                "pair": pair, "symbol": r["symbol"], "ltf": ltf,
                "event_rate": round(rate, 6), "ltf_bars": ltf_bars,
                "p_both": r["p_both"], "n_hat": round(n_hat, 2),
            })
        out.append({
            "pair": pair, "htf": htf, "ltf": ltf, "ltf_bars": ltf_bars,
            "n_hat": round(total, 2), "detail": detail,
        })
    return out


def r0_verdict(
    expected: List[dict],
    surviving_pairs: Sequence[str],
    window_label: str,
) -> dict:
    """§3.3 — GO / 1회 연장 / NO-GO."""
    total = sum(e["n_hat"] for e in expected if e["pair"] in surviving_pairs)
    go = total >= R0_MIN_EXPECTED_N
    return {
        "window": window_label,
        "surviving_pairs": list(surviving_pairs),
        "n_hat_total": round(total, 2),
        "threshold": R0_MIN_EXPECTED_N,
        "verdict": "GO" if go else "SHORT",
        "per_pair": {e["pair"]: e["n_hat"] for e in expected},
    }


def load_v2_journal(ltf: str) -> pd.DataFrame:
    """§2.4 로 재생성한 LTF forward journal."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation", "_htf_gate_v2_cache", f"forward_journal_{ltf}.csv",
    )
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["timestamp"])


def build_pair_events_v2(
    pair: str,
    version: str = GATE_VERSION_V2,
    symbols: Sequence[str] = SYMBOLS_V2,
) -> pd.DataFrame:
    """TF쌍 하나의 gate 플래그 부착 이벤트 (v2 게이트 · v2 이벤트 캐시)."""
    from analysis.wave_htf_gate import attach_htf_gates, trigger_events

    htf, ltf = PAIRS_V2[pair]
    journal = load_v2_journal(ltf)
    if journal.empty:
        return pd.DataFrame()
    events = trigger_events(journal, ltf, tuple(symbols))
    if events.empty:
        return pd.DataFrame()
    frames = [
        apply_gate_version(load_htf_states_v2(s, htf), version) for s in symbols
    ]
    frames = [f for f in frames if not f.empty]
    states = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out = attach_htf_gates(events, states, htf)
    if out.empty:
        return out
    out["pair"] = pair
    out["ltf"] = ltf
    out["gate_version"] = version
    return out


def reject_reason(result: dict) -> str:
    """§4.1 — REJECT 를 '유효 검정에서의 반증' vs '여전히 표본 부족' 으로 구분."""
    if result.get("verdict") == "ACCEPT":
        return "accepted"
    n_both = result.get("bootstrap", {}).get("n_both", 0) or 0
    return "refuted_with_power" if n_both >= 30 else "still_underpowered"


def yearly_open_rates(
    version: str = GATE_VERSION_V2,
    pairs: Optional[Dict[str, Tuple[str, str]]] = None,
    symbols: Sequence[str] = SYMBOLS_V2,
) -> List[dict]:
    """§4.2 — 연도별 게이트 개방 비율 (사이클 편중 확인)."""
    pairs = pairs or PAIRS_V2
    rows: List[dict] = []
    for pair, (htf, _ltf) in pairs.items():
        for sym in symbols:
            st = apply_gate_version(load_htf_states_v2(sym, htf), version)
            if st.empty:
                continue
            st = st.assign(year=st["htf_open_time"].dt.year)
            for year, grp in st.groupby("year"):
                rows.append({
                    "pair": pair, "symbol": sym, "year": int(year), "bars": len(grp),
                    "p_align": round(float(grp["g_align"].mean()), 6),
                    "p_wave": round(float(grp["g_wave"].mean()), 6),
                    "p_both": round(float(grp["g_both"].mean()), 6),
                    "n_both": int(grp["g_both"].sum()),
                })
    return rows
