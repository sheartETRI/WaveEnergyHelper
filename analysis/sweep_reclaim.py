"""스윕 재탈환 검출기 — 뻔한 레벨(Donchian 경계) 이탈이 스윕인지 진짜 이탈인지 기록한다.

배경: 채널 경계처럼 모두가 보는 레벨의 이탈은 두 갈래다 — 손절 물량을 걷어가는
유동성 사냥(스윕: 이탈 후 빠른 재탈환)이거나, 진짜 붕괴/돌파(이탈 지속)다.
본 모듈은 그 판별에 쓸 이벤트를 기록만 한다(기록 전용) — 게이팅·알람 발송·
백테스트 판정은 하지 않는다. docs/SPEC_SWEEP_RECLAIM.md 동결 스펙 상응.

판정 규칙(하단 기준, 상단은 전부 미러):
  · 레벨   L_t = min(low[t-N..t-1]) — 당봉 제외(shift 1), 워밍업 N봉.
  · 시작   low_s < L_s 인 첫 봉 s. 레벨은 이 시점 값으로 동결(이탈이 만든 신저가가
           레벨을 끌어내리지 않게).
  · 재탈환 close_r ≥ L 인 첫 봉 r (s 자신일 수 있음 — 봉내 스윕, dwell 0).
  · 확정   r+1 봉 종가도 ≥ L 일 때만 발화, timestamp = r+1. MACD 알람의 t+1 확정
           규칙과 동형 — 왕복(재탈환 직후 재이탈)은 발화하지 않고 에피소드가
           이어지며 왕복 횟수만 기록. r 이 마지막 봉이면 보류(lookahead 없음).
  · 붕괴   에피소드 중 종가 기준 레벨 밖 체류(dwell)가 reclaim_max_bars 를 초과하는
           봉에서 발화(하단 붕괴 / 상단 돌파 지속). 이후 종가가 롤링 레벨 안으로
           돌아올 때까지 신규 에피소드를 열지 않는다.

기록 필드는 판별 변수(이탈 깊이·체류·왕복·터치 수·레벨 나이·거래량 비율)를 남기되
이벤트를 거르는 데 쓰지 않는다 — 해석은 열람 시점의 일이다.

순수 pandas/numpy, streamlit 무의존 — 테스트 가능.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import SWEEP_RECLAIM_PARAMS

KIND_SWEEP_LOW_RECLAIM = "sweep_low_reclaim"
KIND_SWEEP_LOW_BREAKDOWN = "sweep_low_breakdown"
KIND_SWEEP_HIGH_RECLAIM = "sweep_high_reclaim"
KIND_SWEEP_HIGH_BREAKOUT = "sweep_high_breakout"

SWEEP_KINDS = (
    KIND_SWEEP_LOW_RECLAIM,
    KIND_SWEEP_LOW_BREAKDOWN,
    KIND_SWEEP_HIGH_RECLAIM,
    KIND_SWEEP_HIGH_BREAKOUT,
)

DIR_BULL = "bull"
DIR_BEAR = "bear"

SIDE_LOW = "low"
SIDE_HIGH = "high"

# kind -> (한국어 label, direction)
_KIND_META = {
    KIND_SWEEP_LOW_RECLAIM: ("하단 스윕 재탈환", DIR_BULL),
    KIND_SWEEP_LOW_BREAKDOWN: ("하단 붕괴 지속", DIR_BEAR),
    KIND_SWEEP_HIGH_RECLAIM: ("상단 페이크 돌파", DIR_BEAR),
    KIND_SWEEP_HIGH_BREAKOUT: ("상단 돌파 지속", DIR_BULL),
}

# side -> (확정(재탈환) kind, 진짜 이탈 kind)
_SIDE_KINDS = {
    SIDE_LOW: (KIND_SWEEP_LOW_RECLAIM, KIND_SWEEP_LOW_BREAKDOWN),
    SIDE_HIGH: (KIND_SWEEP_HIGH_RECLAIM, KIND_SWEEP_HIGH_BREAKOUT),
}


@dataclass(frozen=True)
class SweepEvent:
    """스윕/이탈 이벤트 한 건. timestamp 는 판정(확정) 봉의 open_time(df 인덱스)."""

    timestamp: pd.Timestamp
    kind: str
    label: str
    direction: str
    side: str                            # "low" | "high"
    level: float                         # 에피소드 시작 시점에 동결된 레벨
    start_ts: pd.Timestamp               # 이탈 시작 봉
    reclaim_ts: Optional[pd.Timestamp]   # 재탈환 봉 (진짜 이탈이면 None)
    depth_pct: float                     # 레벨 대비 최대 이탈 깊이 %
    dwell_bars: int                      # 종가 기준 레벨 밖 체류 봉 수
    bars_from_start: int                 # 시작 봉 -> 판정 봉 거리(봉)
    level_age_bars: int                  # 레벨 극값 형성 후 이탈까지 경과 봉 수
    touch_count: int                     # 직전 N봉 창에서 레벨 근접 터치 봉 수(뻔함 프록시)
    dev_vol_ratio: Optional[float]       # 이탈 시작 봉 거래량 / 직전 vol_ma_n 평균
    reclaim_vol_ratio: Optional[float]   # 재탈환 봉 거래량 / 직전 vol_ma_n 평균
    detail: str = ""


_FRAME_COLUMNS = [
    "timestamp", "kind", "label", "direction", "side", "level",
    "start_ts", "reclaim_ts", "depth_pct", "dwell_bars", "bars_from_start",
    "level_age_bars", "touch_count", "dev_vol_ratio", "reclaim_vol_ratio", "detail",
]


def _merged_params(params: Optional[dict]) -> dict:
    merged = dict(SWEEP_RECLAIM_PARAMS)
    if params:
        merged.update(params)
    return merged


def _vol_ratio(vol_v, vol_ma_v, i: int) -> Optional[float]:
    """봉 i 의 거래량 / 직전 vol_ma_n 평균. 계산 불가(결측·0)면 None."""
    if vol_v is None or vol_ma_v is None:
        return None
    ma = vol_ma_v[i]
    if np.isnan(ma) or ma <= 0:
        return None
    v = vol_v[i]
    if np.isnan(v):
        return None
    return float(v / ma)


def _scan_side(
    index: pd.Index,
    pierce_v: np.ndarray,
    close_v: np.ndarray,
    lvl_v: np.ndarray,
    vol_v: Optional[np.ndarray],
    vol_ma_v: Optional[np.ndarray],
    p: dict,
    side: str,
) -> list[SweepEvent]:
    """한쪽(하단/상단) 상태기계. pierce_v 는 하단이면 low, 상단이면 high."""
    n = int(p["donchian_n"])
    tol = float(p["touch_tol_pct"])
    max_dwell = int(p["reclaim_max_bars"])
    is_low = side == SIDE_LOW
    reclaim_kind, timeout_kind = _SIDE_KINDS[side]

    state = "normal"          # normal | episode | broken
    ep: Optional[dict] = None
    events: list[SweepEvent] = []

    for i in range(len(index)):
        lvl_roll = lvl_v[i]

        if state == "broken":
            # 종가가 롤링 레벨 안으로 돌아오면 재무장.
            if not np.isnan(lvl_roll):
                back = close_v[i] >= lvl_roll if is_low else close_v[i] <= lvl_roll
                if back:
                    state = "normal"
            continue

        if state == "normal":
            if np.isnan(lvl_roll):
                continue
            pierced = pierce_v[i] < lvl_roll if is_low else pierce_v[i] > lvl_roll
            if not pierced:
                continue
            # 에피소드 시작 — 레벨 동결 + 뻔함 프록시 계산 (창 = [i-n, i-1]).
            win = pierce_v[i - n:i]
            if is_low:
                pos = len(win) - 1 - int(np.argmin(win[::-1]))   # 최저가 마지막 위치
                touches = int(np.sum(win <= lvl_roll * (1.0 + tol)))
            else:
                pos = len(win) - 1 - int(np.argmax(win[::-1]))
                touches = int(np.sum(win >= lvl_roll * (1.0 - tol)))
            ep = {
                "level": float(lvl_roll),
                "start_i": i,
                "extreme": pierce_v[i],
                "dwell": 0,
                "pending": False,
                "reclaim_i": None,
                "rejects": 0,
                "age": n - pos,
                "touches": touches,
                "dev_vol": _vol_ratio(vol_v, vol_ma_v, i),
            }
            state = "episode"
            # 시작 봉 자신도 아래 에피소드 처리로 이어진다 (봉내 스윕 대응).

        # state == "episode"
        level = ep["level"]
        if is_low:
            ep["extreme"] = min(ep["extreme"], pierce_v[i])
            inside = close_v[i] >= level
            depth_pct = (level - ep["extreme"]) / level * 100.0
        else:
            ep["extreme"] = max(ep["extreme"], pierce_v[i])
            inside = close_v[i] <= level
            depth_pct = (ep["extreme"] - level) / level * 100.0

        if ep["pending"]:
            # 이번 봉이 확정 봉(t+1).
            ep["pending"] = False
            if inside:
                r = ep["reclaim_i"]
                events.append(SweepEvent(
                    timestamp=index[i],
                    kind=reclaim_kind,
                    label=_KIND_META[reclaim_kind][0],
                    direction=_KIND_META[reclaim_kind][1],
                    side=side,
                    level=level,
                    start_ts=index[ep["start_i"]],
                    reclaim_ts=index[r],
                    depth_pct=depth_pct,
                    dwell_bars=ep["dwell"],
                    bars_from_start=i - ep["start_i"],
                    level_age_bars=ep["age"],
                    touch_count=ep["touches"],
                    dev_vol_ratio=ep["dev_vol"],
                    reclaim_vol_ratio=_vol_ratio(vol_v, vol_ma_v, r),
                    detail=f"왕복 {ep['rejects']}회" if ep["rejects"] else "",
                ))
                state = "normal"
                ep = None
                continue
            # 확정 실패(왕복) — 발화 없이 에피소드 지속.
            ep["rejects"] += 1

        if inside:
            ep["reclaim_i"] = i
            ep["pending"] = True
            continue

        # 종가 기준 레벨 밖 체류.
        ep["dwell"] += 1
        if ep["dwell"] > max_dwell:
            events.append(SweepEvent(
                timestamp=index[i],
                kind=timeout_kind,
                label=_KIND_META[timeout_kind][0],
                direction=_KIND_META[timeout_kind][1],
                side=side,
                level=level,
                start_ts=index[ep["start_i"]],
                reclaim_ts=None,
                depth_pct=depth_pct,
                dwell_bars=ep["dwell"],
                bars_from_start=i - ep["start_i"],
                level_age_bars=ep["age"],
                touch_count=ep["touches"],
                dev_vol_ratio=ep["dev_vol"],
                reclaim_vol_ratio=None,
                detail=f"왕복 {ep['rejects']}회" if ep["rejects"] else "",
            ))
            state = "broken"
            ep = None

    return events


def scan_sweep_events(df: pd.DataFrame, params: Optional[dict] = None) -> list[SweepEvent]:
    """df 전 구간의 스윕/이탈 이벤트를 시간순으로 반환.

    필요한 컬럼: high/low/close (volume 은 선택 — 없으면 거래량 비율 None).
    컬럼이 없거나 df 가 비면 빈 목록(조용히 건너뜀 — 알람 레이어와 같은 태도).
    params 로 SWEEP_RECLAIM_PARAMS 일부를 덮어쓸 수 있다(테스트·탐색용).
    """
    if df is None or df.empty:
        return []
    if not {"high", "low", "close"}.issubset(df.columns):
        return []

    p = _merged_params(params)
    n = int(p["donchian_n"])
    vol_n = int(p["vol_ma_n"])

    low = df["low"].astype(float)
    high = df["high"].astype(float)
    close_v = df["close"].astype(float).to_numpy()

    lvl_low = low.rolling(n).min().shift(1).to_numpy()
    lvl_high = high.rolling(n).max().shift(1).to_numpy()

    if "volume" in df.columns:
        vol = df["volume"].astype(float)
        vol_v = vol.to_numpy()
        vol_ma_v = vol.rolling(vol_n).mean().shift(1).to_numpy()
    else:
        vol_v = None
        vol_ma_v = None

    events = _scan_side(df.index, low.to_numpy(), close_v, lvl_low, vol_v, vol_ma_v, p, SIDE_LOW)
    events += _scan_side(df.index, high.to_numpy(), close_v, lvl_high, vol_v, vol_ma_v, p, SIDE_HIGH)
    events.sort(key=lambda e: (e.timestamp, e.kind))
    return events


def events_to_frame(events: list[SweepEvent]) -> pd.DataFrame:
    """이벤트 목록 -> 기록용 DataFrame (전방 저널 CSV 등에 쓰는 평탄화)."""
    if not events:
        return pd.DataFrame(columns=_FRAME_COLUMNS)
    return pd.DataFrame([asdict(e) for e in events], columns=_FRAME_COLUMNS)
