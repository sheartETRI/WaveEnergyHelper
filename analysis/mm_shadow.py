"""자금 관리 섀도 추적 — 전방 이벤트에 3변형 가상 체결을 **기록 전용**으로 병기한다.

================================ 미니 헌장 (동결) ================================

1. **이 기록은 판정이 아니며 임계값을 갖지 않는다.** 성공/실패 기준도, 관문도,
   자동 트리거도 없다. 어떤 규칙 변경도 이 파일이 촉발하지 않는다.

2. **1차 열람은 F2-b 6개월 보고(2027-03)와 동시에 한다.** 그때 보고할 항목은
   3변형의 G · 트레이드 수 · 손절 발동률 · STRUCT vs BASE 부호, 그리고
   표본이 허용하면 월 클러스터 CI 뿐이다. **전부 참고 자료이며 규칙 권고가 아니다.**
   그 이전에 중간 수치를 근거로 규칙을 논하지 않는다.

3. **추적 중 이 모듈의 손절 로직 변경은 섀도 리셋 사유다.** 고쳐야 할 실제
   사유가 생기면 고치되, 섀도 기간을 처음부터 다시 세고 그 사실을 보고에 남긴다.
   조용히 이어가지 않는다.

무개입 규율:
- 사이드카(validation/wave_mm_shadow.csv)는 **append-only**. 기존 행은 재실행해도
  변하지 않는다. 원본 저널·F2-b 사이드카·워치리스트는 읽기만 한다.
- 손절·게이트·트리거 정의는 기존 모듈 상수를 import 만 한다. 재정의 없음.
- STRUCT reference_low 는 이벤트 시점 **이전 확정** swing 만 사용한다
  (find_swing_lows + _confirmed, PIVOT 상속). lookahead 차단은 테스트로 강제한다.
- 이 모듈은 §6 전방 추적(F2-b 게이트)의 INTEGRITY_FILES 에 속하지 않으며,
  그 배선을 일절 건드리지 않는다.

================================================================================

3변형 (SPEC_WAVE_MM_STRUCT_STOP §1 · SPEC_WAVE_MM_STOP_AUDIT §2 정의 그대로):
- BASE   : 평단 −3% 손절
- NOSTOP : 손절 없음, 20봉 시간 청산 단독
- STRUCT : 직전 확정 swing low × (1 − 0.005), 미검출·퇴화 시 BASE 폴백

변형별로 1포지션 순차 포트폴리오를 **독립 시뮬레이션**한다. 사이징 고정 5%.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import pandas as pd

from analysis.wave_align_gate_forward import TRACKING_START
from analysis.wave_htf_gate_v2 import PAIRS_V2
from analysis.wave_mm_simulator import (
    STOP_PCT,
    TRANCHE_PCT,
    growth,
    load_bars,
    simulate,
    trade_metrics,
)
from analysis.wave_mm_struct_stop import struct_stop_map, struct_stops

VARIANTS = ("BASE", "NOSTOP", "STRUCT")

# 승격 TF쌍의 LTF → 쌍 이름 (PAIRS_V2 에서 유도, 재정의 아님)
LTF_TO_PAIR = {ltf: pair for pair, (_htf, ltf) in PAIRS_V2.items()}

SHADOW_COLS = (
    "variant", "event_id", "pair", "ltf", "symbol", "signal_ts", "entry_ts",
    "entry_price", "exit_ts", "exit_price", "exit_reason", "bars_held",
    "stop_pct_used", "size_pct", "gross_ret", "net_ret", "log_growth",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation",
    )


def shadow_path() -> str:
    return os.path.join(_validation_dir(), "wave_mm_shadow.csv")


def gate_sidecar_path() -> str:
    return os.path.join(_validation_dir(), "wave_align_gate_forward.csv")


# ------------------------------------------------------------------ 모집단
def load_shadow_events(start: pd.Timestamp = TRACKING_START) -> pd.DataFrame:
    """F2-b 사이드카에서 게이트 통과 전방 이벤트만 읽는다 (읽기 전용).

    사이드카는 §6 배선이 만든 기록이며 여기서는 절대 쓰지 않는다.
    """
    path = gate_sidecar_path()
    if not os.path.isfile(path):
        return pd.DataFrame()
    sc = pd.read_csv(path, parse_dates=["timestamp"])
    if sc.empty:
        return pd.DataFrame()
    gate_open = sc["gate_align"].astype(str).str.lower().eq("true")
    mask = (
        gate_open
        & sc["gate_scope"].eq("PROMOTED")
        & (sc["timestamp"] >= pd.Timestamp(start))
    )
    ev = sc[mask].copy()
    if ev.empty:
        return ev
    ev["ltf"] = ev["timeframe"].astype(str)
    ev["pair"] = ev["ltf"].map(LTF_TO_PAIR)
    # 자의성 고정: 이벤트 시각 순, 동시각이면 심볼 사전순 (MM 라운드와 동일)
    return ev.sort_values(["timestamp", "symbol"], kind="mergesort").reset_index(drop=True)


BAR_PAD = 60   # swing 검출·지표 워밍업용 선행 봉


def load_shadow_bars(
    events: pd.DataFrame,
    start: pd.Timestamp = TRACKING_START,
) -> Dict[Tuple[str, str], pd.DataFrame]:
    """전방 구간 OHLCV 를 **매번 새로 받는다**.

    MM 라운드의 _mm_cache 는 백테스트 창(~2026-09-01)에서 끝나므로 섀도에 쓸 수 없다.
    또 전방 추적은 봉이 계속 쌓이는 구간이라 캐시를 고정하면 안 된다 —
    20봉 청산이 아직 안 끝난 이벤트는 이번 실행에서 건너뛰고, 봉이 차면 다음
    실행에서 append 된다.
    """
    from analysis.wave_htf_gate_v2 import fetch_window_bare

    end = (pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    keys = {(s, l) for s, l in zip(events["symbol"], events["ltf"])}
    out: Dict[Tuple[str, str], pd.DataFrame] = {}
    for sym, ltf in keys:
        out[(sym, ltf)] = fetch_window_bare(
            sym, ltf, pd.Timestamp(start).strftime("%Y-%m-%d"), end, pad_bars=BAR_PAD,
        )
    return out


# ------------------------------------------------------------------ 시뮬레이션
def simulate_variants(
    events: pd.DataFrame,
    bars_by_key: Dict[Tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    """3변형 각각을 독립 1포지션 포트폴리오로 시뮬레이션한다.

    진입 후보 이벤트 집합은 세 변형에서 동일하다 — 손절 규칙만 다르다.
    (실제 체결 집합은 1포지션 경로 의존 때문에 달라질 수 있으며, 그것이 규칙
    차이의 결과다.)
    """
    if events.empty:
        return pd.DataFrame(columns=list(SHADOW_COLS))

    stops = struct_stops(events, bars_by_key)
    smap = struct_stop_map(stops)

    frames = []
    for variant in VARIANTS:
        if variant == "BASE":
            tr = simulate(events, bars_by_key, use_stop=True, stop_pct=STOP_PCT,
                          tranche_pct=TRANCHE_PCT)
        elif variant == "NOSTOP":
            tr = simulate(events, bars_by_key, use_stop=False, tranche_pct=TRANCHE_PCT)
        else:
            tr = simulate(events, bars_by_key, use_stop=True, stop_pct=smap,
                          tranche_pct=TRANCHE_PCT)
        if tr.empty:
            continue
        tr = tr.copy()
        tr["variant"] = variant
        frames.append(tr)

    if not frames:
        return pd.DataFrame(columns=list(SHADOW_COLS))
    out = pd.concat(frames, ignore_index=True)
    cols = [c for c in SHADOW_COLS if c in out.columns]
    return out[cols].sort_values(["variant", "signal_ts"]).reset_index(drop=True)


# ------------------------------------------------------------ append-only 기록
def _key(df: pd.DataFrame) -> pd.Series:
    return df["variant"].astype(str) + "|" + df["event_id"].astype(str)


def append_shadow(new_rows: pd.DataFrame, path: Optional[str] = None) -> dict:
    """사이드카에 새 행만 덧붙인다. **기존 행은 절대 수정하지 않는다.**

    같은 (variant, event_id) 가 이미 있으면 건너뛴다 — 재실행이 기존 기록을
    바꾸지 못하게 하는 append-only 불변식이다.
    """
    path = path or shadow_path()
    existing = pd.DataFrame()
    if os.path.isfile(path):
        existing = pd.read_csv(path)

    if new_rows.empty:
        return {"existing": len(existing), "appended": 0, "total": len(existing)}

    if existing.empty:
        merged = new_rows.copy()
        appended = len(new_rows)
    else:
        have = set(_key(existing))
        fresh = new_rows[~_key(new_rows).isin(have)]
        appended = len(fresh)
        merged = pd.concat([existing, fresh], ignore_index=True) if appended else existing

    merged.to_csv(path, index=False)
    return {"existing": len(existing), "appended": appended, "total": len(merged)}


def load_shadow(path: Optional[str] = None) -> pd.DataFrame:
    path = path or shadow_path()
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["signal_ts", "entry_ts", "exit_ts"])


# ------------------------------------------------------------------ 요약 (참고)
def variant_summary(shadow: pd.DataFrame) -> list[dict]:
    """헌장 §2 가 정한 열람 항목. **참고 자료이며 규칙 권고가 아니다.**"""
    rows = []
    for variant in VARIANTS:
        sub = shadow[shadow["variant"] == variant] if not shadow.empty else shadow
        if sub.empty:
            rows.append({"variant": variant, "trades": 0})
            continue
        m = trade_metrics(sub)
        rows.append({
            "variant": variant,
            "trades": m.get("trades"),
            "stop_rate": m.get("stop_rate"),
            "growth": growth(sub),
            "net_mean_pct": m.get("net_mean_pct"),
            "first_signal": sub["signal_ts"].min(),
            "last_exit": sub["exit_ts"].max(),
        })
    return rows
