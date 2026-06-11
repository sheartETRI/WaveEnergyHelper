"""대파동 3파 하락 종료 추적 — 가설(Hypothesis) 레이어.

기존 검출기·verdict·dynamics 엔진과 독립. 신규 검출기 없음.
wave_energy._wave_state / analyze_wave_energy 신호만 소비.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from analysis.wave_energy import analyze_wave_energy
from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES

# --- 상태 상수 ---
NONE = "NONE"
WAVE3_CANDIDATE = "WAVE3_CANDIDATE"
WAVE3_ACTIVE = "WAVE3_ACTIVE"
DOUBLE_BOTTOM_CANDIDATE = "DOUBLE_BOTTOM_CANDIDATE"
WAVE3_COMPLETED = "WAVE3_COMPLETED"
TRIPLE_BOTTOM_REQUIRED = "TRIPLE_BOTTOM_REQUIRED"
TRIPLE_BOTTOM_CONFIRMED = "TRIPLE_BOTTOM_CONFIRMED"
INVALIDATED = "INVALIDATED"

ALL_STATES = (
    NONE,
    WAVE3_CANDIDATE,
    WAVE3_ACTIVE,
    DOUBLE_BOTTOM_CANDIDATE,
    WAVE3_COMPLETED,
    TRIPLE_BOTTOM_REQUIRED,
    TRIPLE_BOTTOM_CONFIRMED,
    INVALIDATED,
)

STATE_COLORS = {
    NONE: "#BDBDBD",
    WAVE3_CANDIDATE: "#FFF176",
    WAVE3_ACTIVE: "#FFB74D",
    DOUBLE_BOTTOM_CANDIDATE: "#C8E6C9",
    TRIPLE_BOTTOM_REQUIRED: "#CE93D8",
    TRIPLE_BOTTOM_CONFIRMED: "#81C784",
    WAVE3_COMPLETED: "#2E7D32",
    INVALIDATED: "#EF5350",
}

_LAYER_LARGE = WAVE_LAYER_ROLES["large"]
_LAYER_SMALL = WAVE_LAYER_ROLES["small"]


@dataclass
class WaveTrackerState:
    """가설 레이어 출력 (파동 추적 상태)."""
    state: str = NONE
    state_start: Optional[pd.Timestamp] = None
    duration: int = 0
    reason: str = ""
    invalidated: bool = False
    notes: List[str] = field(default_factory=list)


# 하위 호환 alias (wave_energy.WaveState 와 별개)
WaveState = WaveTrackerState


@dataclass
class _BarSignals:
    major_oversold: bool = False
    oversold_entry: bool = False
    major_ll: bool = False
    major_ll_new: bool = False
    major_k: float = 0.0
    major_k_falling: bool = False
    major_k_rising: bool = False
    small_db: bool = False
    small_db_new: bool = False
    small_tb: bool = False
    small_tb_new: bool = False


@dataclass
class _MachineContext:
    state: str = NONE
    state_start_ts: Optional[pd.Timestamp] = None
    state_start_idx: int = 0
    reason: str = ""
    oversold_count: int = 0
    prev_major_oversold: bool = False
    prev_major_k: Optional[float] = None
    oversold_at_candidate: int = 0
    prev_major_db: bool = False
    prev_small_db: bool = False
    prev_small_tb: bool = False
    notes: List[str] = field(default_factory=list)


def _pattern_on_last_bar(df: pd.DataFrame, suffix: str, pattern: str) -> tuple[bool, Optional[str]]:
    col = f"stoch_{pattern}_{suffix}"
    kind_col = f"stoch_{pattern}_kind_{suffix}"
    if df is None or df.empty or col not in df.columns:
        return False, None
    if not pd.notna(df[col].iloc[-1]):
        return False, None
    kind = None
    if kind_col in df.columns and pd.notna(df[kind_col].iloc[-1]):
        kind = str(df[kind_col].iloc[-1])
    return True, kind


def _pattern_edge(df: pd.DataFrame, suffix: str, pattern: str) -> tuple[bool, Optional[str]]:
    col = f"stoch_{pattern}_{suffix}"
    kind_col = f"stoch_{pattern}_kind_{suffix}"
    if df is None or len(df) < 1 or col not in df.columns:
        return False, None
    cur_hit = pd.notna(df[col].iloc[-1])
    prev_hit = pd.notna(df[col].iloc[-2]) if len(df) >= 2 else False
    if not cur_hit or prev_hit:
        return False, None
    kind = None
    if kind_col in df.columns and pd.notna(df[kind_col].iloc[-1]):
        kind = str(df[kind_col].iloc[-1])
    return True, kind


def extract_bar_signals(
    report,
    base_df: pd.DataFrame,
    prev_major_oversold: bool,
    prev_major_k: Optional[float],
) -> _BarSignals:
    """analyze_wave_energy report + 절단 df에서 기존 신호만 추출."""
    bl = report.base_large
    bs = report.base_small
    params = WAVE_ENERGY_PARAMS
    oversold_thr = params["oversold"]

    k_col = f"stoch_k_{_LAYER_LARGE}"
    major_k = float(bl.k) if bl.valid else 0.0
    if base_df is not None and k_col in base_df.columns and base_df[k_col].notna().any():
        major_k = float(base_df[k_col].dropna().iloc[-1])

    major_oversold = bl.valid and bl.zone == "과매도"
    oversold_entry = major_oversold and not prev_major_oversold

    major_ll = bl.valid and bl.db_kind == "LL"
    ll_new, ll_kind = _pattern_edge(base_df, _LAYER_LARGE, "db")
    if ll_new and ll_kind == "LL":
        major_ll_new = True
    else:
        major_ll_new = ll_new and major_ll

    major_k_falling = (
        prev_major_k is not None and bl.valid and major_k < prev_major_k
    )
    major_k_rising = (
        prev_major_k is not None and bl.valid and major_k > prev_major_k
    )

    small_db = bs.valid and bs.double_bottom in ("확정", "후보")
    db_new, _ = _pattern_edge(base_df, _LAYER_SMALL, "db")
    small_db_new = db_new or (
        small_db and not (bs.double_bottom == "없음")
    )

    small_tb = bs.valid and bs.triple_bottom == "확정"
    tb_new, _ = _pattern_edge(base_df, _LAYER_SMALL, "tb")
    small_tb_new = tb_new or small_tb

    return _BarSignals(
        major_oversold=major_oversold,
        oversold_entry=oversold_entry,
        major_ll=major_ll,
        major_ll_new=major_ll_new,
        major_k=major_k,
        major_k_falling=major_k_falling,
        major_k_rising=major_k_rising,
        small_db=small_db,
        small_db_new=small_db_new,
        small_tb=small_tb,
        small_tb_new=small_tb_new,
    )


def _snapshot(
    ctx: _MachineContext,
    ts: pd.Timestamp,
    bar_idx: int,
    reason: str,
    invalidated: bool = False,
) -> WaveTrackerState:
    dur = bar_idx - ctx.state_start_idx + 1 if ctx.state_start_ts is not None else 0
    return WaveTrackerState(
        state=ctx.state,
        state_start=ctx.state_start_ts,
        duration=max(dur, 1) if ctx.state != NONE else 0,
        reason=reason,
        invalidated=invalidated,
        notes=list(ctx.notes),
    )


def _set_state(
    ctx: _MachineContext,
    new_state: str,
    ts: pd.Timestamp,
    bar_idx: int,
    reason: str,
) -> None:
    if ctx.state != new_state:
        ctx.state = new_state
        ctx.state_start_ts = ts
        ctx.state_start_idx = bar_idx
    ctx.reason = reason


def step_tracker(
    ctx: _MachineContext,
    sig: _BarSignals,
    ts: pd.Timestamp,
    bar_idx: int,
) -> WaveTrackerState:
    """한 봉 advance — 상태 머신."""
    reason = ""

    if sig.oversold_entry:
        ctx.oversold_count += 1

    active_states = (
        WAVE3_ACTIVE,
        DOUBLE_BOTTOM_CANDIDATE,
        TRIPLE_BOTTOM_REQUIRED,
        WAVE3_COMPLETED,
        TRIPLE_BOTTOM_CONFIRMED,
    )
    if ctx.state in active_states:
        oversold_re = sig.oversold_entry and ctx.oversold_count > ctx.oversold_at_candidate
        if sig.major_ll_new or oversold_re:
            inv_reason = (
                "New LL detected" if sig.major_ll_new else "Major oversold re-entry"
            )
            ctx.notes.append(f"restart: {WAVE3_CANDIDATE}")
            _set_state(ctx, INVALIDATED, ts, bar_idx, inv_reason)
            ctx.prev_major_oversold = sig.major_oversold
            ctx.prev_major_k = sig.major_k
            return _snapshot(ctx, ts, bar_idx, inv_reason, invalidated=True)

    if ctx.state == INVALIDATED:
        if ctx.oversold_count >= 2 and sig.major_ll:
            _set_state(ctx, WAVE3_CANDIDATE, ts, bar_idx, "2nd Oversold + LL")
            ctx.oversold_at_candidate = ctx.oversold_count
            reason = "2nd Oversold + LL"
        else:
            _set_state(ctx, NONE, ts, bar_idx, "")
            reason = ""
    elif ctx.state == NONE:
        if ctx.oversold_count >= 2 and sig.major_ll:
            _set_state(ctx, WAVE3_CANDIDATE, ts, bar_idx, "2nd Oversold + LL")
            ctx.oversold_at_candidate = ctx.oversold_count
            reason = "2nd Oversold + LL"
    elif ctx.state == WAVE3_CANDIDATE:
        if sig.major_k_falling or sig.major_ll_new:
            r = "Major K falling" if sig.major_k_falling else "Major low updated (LL)"
            _set_state(ctx, WAVE3_ACTIVE, ts, bar_idx, r)
            reason = r
        else:
            reason = "2nd Oversold + LL"
    elif ctx.state == WAVE3_ACTIVE:
        if sig.small_db or sig.small_db_new:
            _set_state(ctx, DOUBLE_BOTTOM_CANDIDATE, ts, bar_idx, "Sub-wave Double Bottom")
            reason = "Sub-wave Double Bottom"
        else:
            reason = ctx.reason or "3-wave in progress"
    elif ctx.state == DOUBLE_BOTTOM_CANDIDATE:
        if sig.major_k_rising:
            _set_state(ctx, WAVE3_COMPLETED, ts, bar_idx, "Major K turned upward")
            reason = "Major K turned upward"
        elif sig.major_k_falling:
            _set_state(
                ctx,
                TRIPLE_BOTTOM_REQUIRED,
                ts,
                bar_idx,
                "DB detected but Major K still falling",
            )
            reason = "DB detected but Major K still falling"
        else:
            reason = "Sub-wave Double Bottom"
    elif ctx.state == TRIPLE_BOTTOM_REQUIRED:
        if sig.small_tb or sig.small_tb_new:
            _set_state(
                ctx,
                TRIPLE_BOTTOM_CONFIRMED,
                ts,
                bar_idx,
                "Sub-wave Triple Bottom confirmed",
            )
            reason = "Sub-wave Triple Bottom confirmed"
        else:
            reason = "DB detected but Major K still falling"
    elif ctx.state in (WAVE3_COMPLETED, TRIPLE_BOTTOM_CONFIRMED):
        reason = ctx.reason or ctx.state

    ctx.prev_major_oversold = sig.major_oversold
    ctx.prev_major_k = sig.major_k
    if not reason:
        reason = ctx.reason or ctx.state
    return _snapshot(ctx, ts, bar_idx, reason, invalidated=(ctx.state == INVALIDATED))


def run_timeline(
    symbol: str,
    interval: str,
    bare: pd.DataFrame,
    ohlcv_cache: dict,
    *,
    warmup: int = 240,
    analyze_fn=None,
    pipeline_fn=None,
) -> pd.DataFrame:
    """봉별 Wave Tracker 타임라인 (룩어헤드 없음)."""
    from display.asof import patch_load_frame_for_asof, run_indicator_pipeline, truncate_to_asof

    if analyze_fn is None:
        analyze_fn = analyze_wave_energy
    if pipeline_fn is None:
        pipeline_fn = run_indicator_pipeline

    ctx = _MachineContext()
    rows = []
    start = min(warmup, len(bare) - 1)

    for i in range(start, len(bare)):
        as_of = bare.index[i]
        cut = truncate_to_asof(bare, as_of)
        if cut is None or cut.empty:
            continue
        base_df = pipeline_fn(cut)
        with patch_load_frame_for_asof(symbol, as_of, ohlcv_cache):
            report = analyze_fn(base_df, symbol, interval)
        sig = extract_bar_signals(
            report,
            base_df,
            ctx.prev_major_oversold,
            ctx.prev_major_k,
        )
        snap = step_tracker(ctx, sig, pd.Timestamp(as_of), i)
        rows.append({
            "timestamp": as_of,
            "state": snap.state,
            "duration": snap.duration,
            "reason": snap.reason,
            "invalidated": snap.invalidated,
            "notes": " | ".join(snap.notes) if snap.notes else "",
        })

    return pd.DataFrame(rows)
