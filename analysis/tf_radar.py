"""TF 레이더 — 어느 TF에서 전투가 벌어지는지 교차 TF로 요약한다 (표시 전용 관측).

"레벨이 TF를 지정한다": 스윕 에피소드가 열린 TF = 지금 그 TF의 뻔한 레벨에서 손절
사냥이 벌어지는 TF. 사람이 TF를 순회하며 찾는 대신, 전 TF 상태를 한 표로 요약하고
관측 우선순위를 매긴다. 우선순위는 관측 편의이지 판정·게이팅·발송이 아니다 —
docs/SPEC_SWEEP_RECLAIM.md §9.

우선순위(내림차순), 동률이면 입력 순서(= 상위 TF 먼저)로:
  3  전투 중    진행 중 에피소드 (재탈환 확정 대기 포함) — current_sweep_state
  2  판정 직후  마지막 확정 이벤트가 fresh_bars 봉 이내
  1  레벨 접근  현재가가 롤링 레벨의 near_level_pct % 이내 (이탈 전)
  0  조용

순수 pandas — 데이터 적재는 표시 계층(display/tf_radar_panel) 담당.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import SWEEP_RECLAIM_PARAMS, TF_RADAR_PARAMS
from analysis.sweep_reclaim import current_sweep_state, scan_sweep_events

_SIDE_KO = {"low": "하단", "high": "상단"}

STATUS_BATTLE = "전투 중"
STATUS_FRESH = "판정 직후"
STATUS_NEAR = "레벨 접근"
STATUS_QUIET = "조용"
STATUS_NO_DATA = "데이터 없음"


@dataclass(frozen=True)
class RadarRow:
    """TF 한 줄 요약. score 는 관측 우선순위(3 전투 중 > 2 판정 직후 > 1 레벨 접근 > 0)."""

    interval: str
    score: int
    status: str
    side: str            # "하단" | "상단" | "상·하단" | "―"
    level: Optional[float]
    dist_pct: Optional[float]   # 현재가 vs 레벨 부호 있는 거리 % (하단: +위/-아래, 상단: +아래/-위)
    detail: str
    last_event: str      # 마지막 확정 이벤트 요약 ("" 가능)


def _merged(params: Optional[dict]) -> dict:
    merged = dict(TF_RADAR_PARAMS)
    if params:
        merged.update(params)
    return merged


def _rolling_levels(df: pd.DataFrame) -> tuple[Optional[float], Optional[float]]:
    """마지막 봉의 롤링 레벨 (당봉 제외 Donchian — 검출기와 동일 정의)."""
    n = int(SWEEP_RECLAIM_PARAMS["donchian_n"])
    if len(df) <= n:
        return None, None
    lvl_low = df["low"].astype(float).rolling(n).min().shift(1).iloc[-1]
    lvl_high = df["high"].astype(float).rolling(n).max().shift(1).iloc[-1]
    to_f = lambda v: None if pd.isna(v) else float(v)  # noqa: E731
    return to_f(lvl_low), to_f(lvl_high)


def _last_event_summary(df: pd.DataFrame, fresh_bars: int) -> tuple[str, Optional[int], Optional[str], Optional[float]]:
    """마지막 확정 이벤트 (요약문, 경과 봉, 방향측, 레벨). 없으면 ("", None, None, None)."""
    events = scan_sweep_events(df)
    if not events:
        return "", None, None, None
    last = events[-1]
    try:
        pos = df.index.get_loc(last.timestamp)
    except KeyError:
        return "", None, None, None
    age = len(df) - 1 - int(pos)
    summary = f"{last.label} ({age}봉 전)"
    return summary, age, _SIDE_KO.get(last.side, last.side), float(last.level)


def _radar_row(interval: str, df: Optional[pd.DataFrame], p: dict) -> RadarRow:
    if df is None or df.empty or not {"high", "low", "close"}.issubset(df.columns):
        return RadarRow(interval, 0, STATUS_NO_DATA, "―", None, None, "", "")

    close = float(df["close"].astype(float).iloc[-1])
    lvl_low, lvl_high = _rolling_levels(df)
    state = current_sweep_state(df)
    last_event, age, ev_side, ev_level = _last_event_summary(df, int(p["fresh_bars"]))

    # 3 — 전투 중 (진행 중 에피소드).
    live = [state[s] for s in ("low", "high") if state[s]["state"] == "episode"]
    if live:
        if len(live) == 2:
            side, ep = "상·하단", max(live, key=lambda e: e["dwell_bars"])
        else:
            ep = live[0]
            side = _SIDE_KO[ep["side"]]
        level = float(ep["level"])
        dist = (close - level) / level * 100.0 if ep["side"] == "low" else (level - close) / level * 100.0
        detail = f"체류 {ep['dwell_bars']}봉 · 깊이 {ep['depth_pct']:.1f}%"
        if ep["pending_confirm"]:
            detail += " · 재탈환 확정 대기"
        if ep["rejects"]:
            detail += f" · 왕복 {ep['rejects']}회"
        return RadarRow(interval, 3, STATUS_BATTLE, side, level, dist, detail, last_event)

    # 2 — 판정 직후.
    if age is not None and age <= int(p["fresh_bars"]):
        dist = None
        if ev_level:
            dist = (close - ev_level) / ev_level * 100.0
        return RadarRow(interval, 2, STATUS_FRESH, ev_side or "―", ev_level, dist, last_event, last_event)

    # 1 — 레벨 접근 (이탈 전, 더 가까운 쪽).
    near = float(p["near_level_pct"])
    cands = []
    if lvl_low is not None:
        d = (close - lvl_low) / lvl_low * 100.0
        if 0.0 <= d <= near:
            cands.append(("하단", lvl_low, d))
    if lvl_high is not None:
        d = (lvl_high - close) / lvl_high * 100.0
        if 0.0 <= d <= near:
            cands.append(("상단", lvl_high, d))
    if cands:
        side, level, d = min(cands, key=lambda c: c[2])
        return RadarRow(interval, 1, STATUS_NEAR, side, level, d, f"레벨까지 {d:.2f}%", last_event)

    # 0 — 조용 (참고로 가까운 경계까지 거리만 표기).
    detail = ""
    if lvl_low is not None and lvl_high is not None and close > 0:
        d_low = (close - lvl_low) / lvl_low * 100.0
        d_high = (lvl_high - close) / lvl_high * 100.0
        if d_low <= d_high:
            detail = f"하단까지 {d_low:.1f}%"
        else:
            detail = f"상단까지 {d_high:.1f}%"
    return RadarRow(interval, 0, STATUS_QUIET, "―", None, None, detail, last_event)


def build_tf_radar(frames: dict[str, Optional[pd.DataFrame]], params: Optional[dict] = None) -> list[RadarRow]:
    """{interval: df} -> 우선순위 내림차순 RadarRow 목록. frames 의 키 순서 = 동률 시 우선순위(상위 TF 먼저)."""
    p = _merged(params)
    rows = [_radar_row(interval, df, p) for interval, df in frames.items()]
    order = {interval: i for i, interval in enumerate(frames)}
    rows.sort(key=lambda r: (-r.score, order[r.interval]))
    return rows


def pick_focus(rows: list[RadarRow]) -> Optional[RadarRow]:
    """"지금 볼 TF" — score > 0 인 최상위 행. 전부 조용이면 None."""
    for row in rows:
        if row.score > 0:
            return row
    return None
