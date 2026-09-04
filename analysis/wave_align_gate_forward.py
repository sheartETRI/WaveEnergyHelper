"""§6 전방 추적 — F2-b 게이트 개방 여부를 이벤트에 **기록 전용**으로 부착한다.

SPEC_WAVE_ALIGN_GATE §6 / docs/SPEC_WAVE_ALIGN_GATE_FORWARD.md (동결 헌장).

무개입 원칙:
- gate_align 은 기록 전용 플래그다. 어떤 필터·정렬·점수에도 쓰지 않는다.
- 원본 wave_live_forward_journal.csv 는 수정하지 않는다. 사이드카 CSV 로만 쓴다.
- 추적 기간 중 게이트/이벤트 정의를 바꾸는 커밋은 추적을 무효화한다
  (tests/test_align_gate_forward_integrity.py 가 회귀로 강제).
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from analysis.wave_htf_gate import attach_htf_gates, close_time_of
from analysis.wave_htf_gate_v2 import PAIRS_V2, SYMBOLS_V2, f2b_rising_flags

# --- §6 동결 조항 (결과를 보고 고를 수 없도록 코드에 박는다) ---
TRACKING_START = pd.Timestamp("2026-09-01")
# 헌장이 동결된 시점. 무개입 커밋 감사는 이 시점부터가 의미 있다
# (그 이전 커밋은 헌장·배선을 수립한 작업 자체다).
CHARTER_FROZEN_AT = pd.Timestamp("2026-09-04")
TRACKING_MONTHS = 6
REVIEW_DUE = TRACKING_START + pd.DateOffset(months=TRACKING_MONTHS)

RETRACT_REVIEW = "RETRACT_REVIEW"   # 승격 회수 논의 개시
EXTEND = "EXTEND"                   # 추적 6개월 연장
KEEP = "KEEP"                       # 승격 유지

REVIEW_RULE = (
    "6개월 시점 1회 보고에서 전방 Δ′ 의 월 클러스터 부트스트랩 95% CI **상한이 0 미만**일 때만 "
    "승격 회수 논의를 연다. 부호만 음수이고 CI 가 0 을 포함하면 추적을 6개월 연장한다. "
    "그 외에는 승격을 유지한다."
)

# 승격된 TF쌍만 게이트를 평가한다 (PAIRS_V2 그대로: LTF → HTF).
PROMOTED_LTF_TO_HTF: Dict[str, str] = {ltf: htf for htf, ltf in PAIRS_V2.values()}

# 무개입 감사 대상 — 이 파일들이 추적 기간 중 바뀌면 추적은 무효다.
INTEGRITY_FILES = (
    "analysis/wave_htf_gate_v2.py",        # F2-b 게이트 정의
    "analysis/wave_htf_gate.py",           # asof 조인 · 트리거 정의
    "analysis/wave_align_gate_forward.py",  # 플래그 배선 (본 파일)
    "analysis/wave_live_watchlist.py",     # 이벤트 검출
    "analysis/wave_live_forward_journal.py",  # 이벤트 저널
    "indicators/moving_averages.py",       # MA 계산
    "config/settings.py",                  # MA 기간 · 레이어 정의
)

SIDECAR_COLS = (
    "event_id", "timestamp", "symbol", "timeframe", "gate_htf",
    "gate_align", "gate_scope", "gate_htf_open_time", "gate_htf_close_time",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation",
    )


def sidecar_path() -> str:
    return os.path.join(_validation_dir(), "wave_align_gate_forward.csv")


# ------------------------------------------------------------ 게이트 상태
def gate_states(symbol: str, htf: str, pipe: pd.DataFrame) -> pd.DataFrame:
    """F2-b 게이트 상태 시계열. MA 만 쓰므로 인과적이고 절단 재계산과 동치다.

    attach_htf_gates 가 요구하는 컬럼 형태로 맞춘다 (감사된 asof 코드를 그대로 재사용).
    """
    if pipe is None or pipe.empty:
        return pd.DataFrame()
    opens = pd.to_datetime(pd.Series(pipe.index))
    out = pd.DataFrame({
        "symbol": symbol,
        "htf_open_time": opens.to_numpy(),
        "htf_close_time": close_time_of(opens, htf).to_numpy(),
        "g_align": f2b_rising_flags(pipe).to_numpy(),
    })
    out["htf_state"] = None       # §6 은 파동 상태를 쓰지 않는다
    out["htf_alignment"] = None
    out["g_wave"] = False
    out["g_both"] = False
    return out.sort_values("htf_close_time").reset_index(drop=True)


def load_htf_pipe(symbol: str, htf: str, limit: Optional[int] = None) -> pd.DataFrame:
    """게이트 평가용 HTF 파이프라인 (네트워크)."""
    from data.binance import get_auto_limit
    from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

    lim = limit or max(get_auto_limit(htf), 600)
    bare = fetch_ohlcv_bare(symbol, htf, lim, paginated=lim > 1000)
    if bare is None or bare.empty:
        return pd.DataFrame()
    return run_indicator_pipeline(bare)


# ------------------------------------------------------------- 플래그 부착
def annotate_gate_align(
    journal: pd.DataFrame,
    states_by_key: Dict[tuple, pd.DataFrame],
) -> pd.DataFrame:
    """이벤트에 gate_align 을 asof 부착한다 (기록 전용 사이드카).

    승격 TF쌍(LTF∈PROMOTED_LTF_TO_HTF)만 평가하고, 나머지는 NOT_PROMOTED 로 남긴다.
    states_by_key: {(symbol, htf): gate_states(...)}
    """
    if journal.empty:
        return pd.DataFrame(columns=list(SIDECAR_COLS))

    j = journal.copy()
    j["timestamp"] = pd.to_datetime(j["timestamp"])
    parts = []

    for ltf, sub in j.groupby("timeframe", sort=False):
        htf = PROMOTED_LTF_TO_HTF.get(str(ltf))
        if htf is None:
            out = sub.copy()
            out["gate_htf"] = None
            out["gate_align"] = pd.NA
            out["gate_scope"] = "NOT_PROMOTED"
            out["gate_htf_open_time"] = pd.NaT
            out["gate_htf_close_time"] = pd.NaT
            parts.append(out)
            continue

        frames = [
            states_by_key[(s, htf)]
            for s in sub["symbol"].unique()
            if (s, htf) in states_by_key and not states_by_key[(s, htf)].empty
        ]
        states = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        joined = attach_htf_gates(sub, states, htf)
        joined["gate_htf"] = htf
        evaluated = joined["htf_close_time"].notna()
        joined["gate_scope"] = np.where(evaluated, "PROMOTED", "NO_HTF_BAR")
        # 평가되지 않은 이벤트는 False 가 아니라 결측이어야 한다 (object dtype 유지)
        joined["gate_align"] = pd.Series(
            [bool(v) if ok else pd.NA
             for v, ok in zip(joined["g_align"], evaluated)],
            index=joined.index, dtype=object,
        )
        joined["gate_htf_open_time"] = joined["htf_open_time"]
        joined["gate_htf_close_time"] = joined["htf_close_time"]
        parts.append(joined)

    out = pd.concat(parts, ignore_index=True).sort_values("timestamp")
    keep = [c for c in SIDECAR_COLS if c in out.columns]
    extra = [c for c in ("return_20", "return_40", "status", "rule",
                         "quality_score", "bars_elapsed") if c in out.columns]
    return out[keep + extra].reset_index(drop=True)


def forward_slice(sidecar: pd.DataFrame, start: pd.Timestamp = TRACKING_START) -> pd.DataFrame:
    """§6 전방 구간 — 추적 시작 이후 · 승격 쌍 · 게이트 평가된 이벤트."""
    if sidecar.empty:
        return sidecar
    df = sidecar.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    mask = (df["timestamp"] >= start) & (df["gate_scope"] == "PROMOTED")
    return df[mask].reset_index(drop=True)


# -------------------------------------------------------------- 재검토 판정
def review_decision(bootstrap: dict) -> dict:
    """§6 동결 규칙 — 결과를 보고 기준을 고를 수 없도록 코드에 고정.

    CI 상한 < 0            → RETRACT_REVIEW (승격 회수 논의)
    Δ′ < 0 이고 CI 가 0 포함 → EXTEND (6개월 연장)
    그 외                   → KEEP (승격 유지)
    """
    delta = bootstrap.get("delta")
    lo, hi = bootstrap.get("ci_low"), bootstrap.get("ci_high")
    if delta is None or lo is None or hi is None:
        return {"decision": EXTEND, "reason": "CI 산출 불가 (표본 부족) — 연장", "rule": REVIEW_RULE}
    if hi < 0:
        return {"decision": RETRACT_REVIEW,
                "reason": f"CI 상한 {hi} < 0", "rule": REVIEW_RULE}
    if delta < 0 and lo <= 0 <= hi:
        return {"decision": EXTEND,
                "reason": f"Δ′={delta} < 0 이지만 CI [{lo}, {hi}] 가 0 을 포함", "rule": REVIEW_RULE}
    return {"decision": KEEP,
            "reason": f"Δ′={delta}, CI [{lo}, {hi}] — 회수 조건 미충족", "rule": REVIEW_RULE}


def tracking_status(now: Optional[pd.Timestamp] = None) -> dict:
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow().tz_localize(None)
    elapsed_days = (now - TRACKING_START).days
    return {
        "start": TRACKING_START,
        "due": REVIEW_DUE,
        "now": now,
        "elapsed_days": elapsed_days,
        "due_reached": now >= REVIEW_DUE,
        "months": TRACKING_MONTHS,
    }


# ------------------------------------------------------------ 현재 게이트 상태
def trailing_run(flags: np.ndarray) -> int:
    """끝에서부터 연속 True 개수 (게이트 연속 개방 봉 수)."""
    run = 0
    for v in flags[::-1]:
        if not bool(v):
            break
        run += 1
    return run


def current_gate_status(
    symbols: Sequence[str] = SYMBOLS_V2,
    htfs: Sequence[str] = tuple(sorted(set(PROMOTED_LTF_TO_HTF.values()))),
) -> list[dict]:
    """표시 전용 — 심볼×HTF 의 마지막 닫힌 봉 기준 F2-b 개방 여부."""
    rows: list[dict] = []
    for htf in htfs:
        for sym in symbols:
            pipe = load_htf_pipe(sym, htf)
            st = gate_states(sym, htf, pipe)
            if st.empty or len(st) < 2:
                rows.append({"symbol": sym, "htf": htf, "gate_align": None})
                continue
            # 마지막 봉은 진행 중일 수 있으므로 직전 닫힌 봉을 쓴다
            last_closed = st.iloc[-2]
            open_run = trailing_run(st["g_align"].to_numpy(dtype=bool)[:-1])
            rows.append({
                "symbol": sym,
                "htf": htf,
                "gate_align": bool(last_closed["g_align"]),
                "htf_open_time": last_closed["htf_open_time"],
                "htf_close_time": last_closed["htf_close_time"],
                "open_bars": open_run,
                "open_rate_recent": round(float(st["g_align"].tail(120).mean()), 4),
            })
    return rows
