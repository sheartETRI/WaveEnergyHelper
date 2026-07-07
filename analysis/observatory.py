"""v2 관측 계기판 로직 (9차 위임 B·C·D) — 표시·저널 전용. 판정·게이트·추천 아님.

순수 계산부(테스트 가능). streamlit 렌더는 display/observatory.py, 스냅샷은
validation/observatory_snapshot.py 가 소비한다.

- C 추세 slope 계기판: 1d/4d 60MA slope 3단(상승/평탄/하락). 평탄 = |정규화 slope| 히스토리
  하위 pctile 이하(8차 부가기록 정의 재사용, 상수 노출). 종합 라벨은 김박사 규칙(표시 전용).
- B 월봉 대파동 위치: 스토캐 4층(40,20,20) K 위치(바닥권/중간/고점권) + 방향(K vs D).
- D 전조 채널 디스패처(스펙 §2.5): 배열 상태(정배열 10>20>60>120 / 비정배열 120>60 / 기타)에
  따라 활성 전조 채널(정배열=이평선 10MA 쌍봉 / 비정배열=대파동 스토캐 쌍봉)을 고른다.

★ 어떤 함수도 캠페인 필터·승격·시그널 등급에 쓰이지 않는다(관측 라벨 유지).
"""
from __future__ import annotations

import csv
import os
from typing import Optional

import numpy as np
import pandas as pd

from analysis.array_context import _ma_values
from analysis.trend_layer import TREND_STOCH_SUFFIX, ma_slope
from config.settings import (
    OBSERVATORY_PARAMS,
    TREND_LAYER_PARAMS,
    WAVE_LAYER_ROLES,
)

LARGE_STOCH_SUFFIX = WAVE_LAYER_ROLES["large"]   # 대파동 = "(20,10,10)"


# ---------------------------------------------------------------- C. slope 계기판
def slope_state(
    full: pd.DataFrame,
    period: int = 60,
    n: Optional[int] = None,
    flat_pctile: Optional[float] = None,
    pos: Optional[int] = None,
) -> Optional[dict]:
    """MA{period} slope 3단 상태 + 평탄 임계.

    평탄 = |정규화 slope(=ma_slope)| 가 심볼·TF 히스토리 하위 flat_pctile 분위 이하.
    아니면 부호로 상승/하락. 관측 전용.
    """
    nn = TREND_LAYER_PARAMS["TREND_SLOPE_N"] if n is None else n
    fp = OBSERVATORY_PARAMS["slope_flat_pctile"] if flat_pctile is None else flat_pctile
    col = f"MA{period}"
    if full is None or col not in full.columns or len(full) == 0:
        return None
    p = len(full) - 1 if pos is None else pos
    mags = []
    for t in range(nn, len(full)):
        s = ma_slope(full, t, period, nn)
        if s is not None:
            mags.append(abs(s))
    if not mags:
        return None
    thr = float(np.quantile(np.array(mags), fp))
    cur = ma_slope(full, p, period, nn)
    if cur is None:
        return None
    if abs(cur) <= thr:
        state = "flat"
    elif cur > 0:
        state = "up"
    else:
        state = "down"
    return {"state": state, "slope": float(cur), "flat_thr": thr,
            "n_hist": len(mags), "pctile": fp}


_STATE_KO = {"up": "상승", "flat": "평탄", "down": "하락"}


def slope_state_ko(state: Optional[str]) -> str:
    return _STATE_KO.get(state, "미정") if state else "미정"


def composite_trend_label(state_1d: Optional[str], state_4d: Optional[str]) -> dict:
    """종합 라벨 (김박사 규칙, 표시 전용). 1d 하락은 김박사 규칙 미정의 → 중립 관찰 라벨.

    반환: {label, note}. note는 툴팁(8차 관측 인용 포함).
    """
    if state_1d is None:
        return {"label": "판정 데이터 부족", "note": "1d 60MA slope 산출 불가"}
    if state_1d == "flat":
        return {"label": "횡보 주의",
                "note": "1d 60MA 평탄 — 8차 관측: 평탄(|slope| 하위20%) 국면 fwd20 mean 음수(BTC−2.27%/ETH−3.43%)"}
    if state_1d == "up":
        if state_4d == "up":
            return {"label": "강한 추세 후보", "note": "1d·4d 60MA 동반 상승(김박사 규칙)"}
        return {"label": "초기 전환 관찰", "note": "1d 상승 · 4d 비상승 — 초기 전환 국면(김박사 규칙)"}
    # state_1d == "down" — 김박사 규칙 미정의, 중립 관찰 라벨
    return {"label": "하락 국면 (관찰)", "note": "1d 60MA 하락 — 김박사 종합 규칙 미정의(중립 관찰 표기)"}


# ---------------------------------------------------------------- B. 월봉 대파동 위치
def monthly_stoch_position(full_obs: pd.DataFrame, pos: Optional[int] = None) -> Optional[dict]:
    """스토캐 4층(40,20,20) K 현재 위치 구간 + 방향. full_obs = add_trend_observation 적용본."""
    sfx = TREND_STOCH_SUFFIX
    kcol, dcol = f"stoch_k_{sfx}", f"stoch_d_{sfx}"
    if full_obs is None or kcol not in full_obs.columns or len(full_obs) == 0:
        return None
    p = len(full_obs) - 1 if pos is None else pos
    k = full_obs[kcol].iloc[p]
    d = full_obs[dcol].iloc[p] if dcol in full_obs.columns else None
    if pd.isna(k):
        return None
    k = float(k)
    lo, hi = OBSERVATORY_PARAMS["stoch_bottom_zone"], OBSERVATORY_PARAMS["stoch_top_zone"]
    if k < lo:
        zone = "바닥권"
    elif k > hi:
        zone = "고점권"
    else:
        zone = "중간"
    if d is None or pd.isna(d):
        direction = "미정"
    else:
        direction = "상승" if k >= float(d) else "하락"
    return {"k": k, "d": (None if d is None or pd.isna(d) else float(d)),
            "zone": zone, "direction": direction}


# ---------------------------------------------------------------- D. 전조 채널 디스패처 (스펙 §2.5)
def array_state(full: pd.DataFrame, pos: Optional[int] = None) -> str:
    """스펙 §2.5 배열 상태: 정배열(10>20>60>120) / 비정배열(120>60) / 기타.

    MA120 부재(예: 월봉 히스토리 부족) 등으로 판정 불가면 '기타'.
    """
    if full is None or len(full) == 0:
        return "기타"
    p = len(full) - 1 if pos is None else pos
    vals = _ma_values(full, p, [10, 20, 60, 120])
    if vals is None:
        return "기타"
    m10, m20, m60, m120 = vals
    if m10 > m20 > m60 > m120:
        return "정배열"
    if m120 > m60:
        return "비정배열"
    return "기타"


# 배열 상태 → 활성 전조 채널 (스펙 §2.5 표). 10차 위임: 스토캐 채널 candidate 노출 추가.
PRECURSOR_CHANNELS = {
    "정배열": {
        "channel": "이평선 10MA 쌍봉",
        "reason": "이평선이 살아 움직이는 국면 — 힘이 센 계기가 실제로 형성됨",
        "source": "ma",
        "confirmed_col": "ma10_dt",
        "candidate_period": 10,
    },
    "비정배열": {
        "channel": "대파동 스토캐 쌍봉",
        "reason": "10MA가 눌린 국면 — 이평선 쌍봉은 형성이 어렵거나 늦으므로 빠른 계기를 읽음",
        "source": "stoch",
        "confirmed_col": f"stoch_dt_{LARGE_STOCH_SUFFIX}",
        "stoch_suffix": LARGE_STOCH_SUFFIX,   # 대파동 (20,10,10)
        "stoch_pat": "dt",                     # 쌍봉(하락 전조)
    },
}


def _recent_confirmed(full: pd.DataFrame, col: str, pos: int, window: int) -> Optional[pd.Timestamp]:
    """col 패턴이 최근 window봉 이내 확정된 마지막 시각(없으면 None)."""
    if col not in full.columns:
        return None
    lo = max(0, pos - window + 1)
    seg = full[col].iloc[lo:pos + 1]
    hits = seg[seg.notna()]
    return None if hits.empty else hits.index[-1]


def precursor_channel(
    full: pd.DataFrame,
    symbol: str,
    tf: str,
    pos: Optional[int] = None,
    window: int = 12,
) -> dict:
    """배열 상태 판정 → 활성 전조 채널 + 최근 확정/후보. 표시·저널 전용(스펙 §2.5).

    반환 dict: state, channel, reason, confirmed_ts, candidates(list of PatternEvent).
    """
    p = (len(full) - 1) if (pos is None and full is not None) else pos
    st = array_state(full, p)
    out = {"state": st, "channel": None, "reason": None, "source": None,
           "confirmed_ts": None, "candidates": [], "active": st in PRECURSOR_CHANNELS}
    if st not in PRECURSOR_CHANNELS:
        out["reason"] = "정/비정배열 아님 — 활성 전조 채널 없음(관측)"
        return out
    cfg = PRECURSOR_CHANNELS[st]
    out["channel"] = cfg["channel"]
    out["reason"] = cfg["reason"]
    out["source"] = cfg["source"]
    out["confirmed_ts"] = _recent_confirmed(full, cfg["confirmed_col"], p, window)
    # 전조 = 하락 전환 → 쌍봉(short) 후보만.
    try:
        if cfg["source"] == "ma":
            from analysis.pattern_scanner import scan_ma_candidates
            cands = scan_ma_candidates(full, symbol, tf, periods=[cfg["candidate_period"]])
        else:  # stoch: 검출기 candidate 컬럼 노출(10차 위임 A)
            from analysis.pattern_scanner import scan_stoch_candidates
            cands = scan_stoch_candidates(full, symbol, tf, suffixes=[cfg["stoch_suffix"]])
        out["candidates"] = [c for c in cands if getattr(c, "direction", None) == "short"]
    except Exception:
        out["candidates"] = []
    return out


# ---------------------------------------------------------------- 관측 저널 (표시 시점 상태 누적)
OBS_JOURNAL_COLUMNS = [
    "ts", "symbol", "tf", "kind",
    "slope_1d_state", "slope_4d_state", "composite_label",
    "monthly_zone", "monthly_direction",
    "array_state", "active_channel", "precursor_confirmed_ts", "n_candidates",
]


def append_observatory_journal(row: dict, path: Optional[str] = None) -> bool:
    """관측 스냅샷 1행을 CSV에 누적(신규 (symbol,tf,ts,kind)만). 반환=기록 여부.

    표시 시점 상태의 관측 누적용. 판정·게이트 아님. streamlit 재실행 스팸 방지 위해
    동일 키가 이미 있으면 건너뛴다.
    """
    path = path or OBSERVATORY_PARAMS["journal_path"]
    key = (str(row.get("symbol")), str(row.get("tf")), str(row.get("ts")), str(row.get("kind")))
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    if (r.get("symbol"), r.get("tf"), r.get("ts"), r.get("kind")) == key:
                        return False
        except Exception:
            pass
    else:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    write_header = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OBS_JOURNAL_COLUMNS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in OBS_JOURNAL_COLUMNS})
    return True
