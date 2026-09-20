"""60MA 기울기 실측 — 표시 전용 (관측, 알림 제외, signal-alarm 표시 계층).

기울기 = (MA60(t) − MA60(t−1)) / MA60(t−1) × 100, 단위 %/봉. 현재 값과 1·3·5봉 전 값, 최근 20봉 안의 부호 변경 시각을
**숫자와 방향만** 보여 준다. 임계값·판정·예측 표기는 없다("평평/전환 임박" 류 금지 — 테스트가 어휘 부재를 단언).
방향은 60MA 전환 추적의 규칙(MA60(t) > MA60(t−1) = 상방, 아니면 하방)과 같은 부호 기준이며 판정 기준 변경이 아니다.

다중 TF 요약(1h·4h·1d): 현재 TF 는 적재된 프레임을 그대로 쓰고, 다른 TF 는 기존 로딩 경로
(``display.asof.fetch_ohlcv_bare`` → ``indicators.moving_averages.add_moving_averages``)로 MA 까지만 계산한다
(fetch 는 data/binance 의 st.cache_data ttl=600 캐시). 정의 파일·알람·게이트 무접촉.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from display.tz_label import KST_LABEL, to_kst

SLOPE_LAGS: Tuple[int, ...] = (1, 3, 5)     # 표시 오프셋(봉) — 추이 확인용
SIGN_LOOKBACK = 20                          # 부호 변경 탐색 창(봉) — 60MA 전환 추적 창과 같은 길이(표시용)
SUMMARY_TFS: Tuple[str, ...] = ("1h", "4h", "1d")
UNIT = "%/봉"
BLOCK_TITLE = f"60MA 기울기 실측 ({UNIT})"
DIR_UP, DIR_DOWN, DIR_NA = "상방", "하방", "—"
FORBIDDEN_WORDS = ("평평", "임박", "곧 돈", "예측", "완만")   # 판정·예측 어휘 — 표시 문자열에 쓰지 않는다(테스트)

COLUMNS = ("TF", "현재", "1봉 전", "3봉 전", "5봉 전", "방향", f"부호 변경 (최근 {SIGN_LOOKBACK}봉) {KST_LABEL}")


# ------------------------------------------------------------------ 계산 (순수 함수)
def slope_series(ma60: pd.Series) -> pd.Series:
    """(MA60(t) − MA60(t−1)) / MA60(t−1) × 100 — %/봉. 미산출 구간은 NaN."""
    s = pd.to_numeric(ma60, errors="coerce").astype(float)
    return s.pct_change() * 100.0


def _val(s: pd.Series, pos: int) -> float:
    if pos < 0 or pos >= len(s):
        return float("nan")
    return float(s.iloc[pos])


def direction(slope: float) -> str:
    """부호만: > 0 상방 · ≤ 0 하방 · NaN —. (60MA 전환 추적의 '상방 = MA60(t) > MA60(t−1)' 과 같은 기준)"""
    if not np.isfinite(slope):
        return DIR_NA
    return DIR_UP if slope > 0 else DIR_DOWN


def last_sign_change(s: pd.Series, lookback: int = SIGN_LOOKBACK) -> Optional[Tuple[int, pd.Timestamp]]:
    """최근 lookback 봉 안에서 마지막으로 부호가 바뀐 봉 (위치, 시각). 없으면 None.

    비교는 방향(direction)이 바뀐 봉 — 0 은 하방 쪽으로 세므로 +→0 도 변경, 0→0 은 아님. NaN 이 낀 곳은 건너뛴다.
    """
    n = len(s)
    if n < 2:
        return None
    start = max(1, n - int(lookback))
    for pos in range(n - 1, start - 1, -1):
        cur, prev = _val(s, pos), _val(s, pos - 1)
        if not (np.isfinite(cur) and np.isfinite(prev)):
            continue
        if direction(cur) != direction(prev):
            return pos, pd.Timestamp(s.index[pos])
    return None


def slope_snapshot(df: Optional[pd.DataFrame]) -> Optional[dict]:
    """프레임(MA60 포함)의 마지막 봉 기준 실측. MA60 이 없거나 프레임이 비면 None."""
    if df is None or df.empty or "MA60" not in df.columns:
        return None
    s = slope_series(df["MA60"])
    last = len(s) - 1
    now = _val(s, last)
    change = last_sign_change(s)
    return {
        "now": now,
        "lags": {k: _val(s, last - k) for k in SLOPE_LAGS},
        "direction": direction(now),
        "sign_change_at": change[1] if change else None,
        "sign_change_bars_ago": (last - change[0]) if change else None,
        "last_ts": pd.Timestamp(df.index[-1]),
    }


# ------------------------------------------------------------------ 다중 TF
def load_ma_frame(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """다른 TF 의 60MA 용 프레임 — 기존 로딩 경로(bare fetch → MA). 스토캐·MACD·RSI 는 계산하지 않는다."""
    from display.asof import fetch_ohlcv_bare
    from indicators.moving_averages import add_moving_averages

    bare = fetch_ohlcv_bare(symbol, interval)
    if bare is None or bare.empty:
        return None
    return add_moving_averages(bare)


def multi_tf_snapshots(symbol: str, interval: str, df: pd.DataFrame, tfs: Sequence[str] = SUMMARY_TFS,
                       loader: Optional[Callable[[str, str], Optional[pd.DataFrame]]] = None) -> List[Tuple[str, Optional[dict]]]:
    """TF 별 (tf, snapshot). 현재 TF 는 적재 프레임 재사용(재fetch 없음). 로딩 실패 TF 는 (tf, None)."""
    loader = load_ma_frame if loader is None else loader
    out: List[Tuple[str, Optional[dict]]] = []
    for tf in tfs:
        if tf == interval:
            out.append((tf, slope_snapshot(df)))
            continue
        try:
            out.append((tf, slope_snapshot(loader(symbol, tf))))
        except Exception:   # noqa: BLE001 — 보조 표시가 알람 탭을 깨뜨리지 않는다
            out.append((tf, None))
    return out


# ------------------------------------------------------------------ 표시 변환
def fmt_slope(v: float) -> str:
    return "—" if v is None or not np.isfinite(v) else f"{v:+.4f}"


def _fmt_change(snap: dict) -> str:
    if snap["sign_change_at"] is None:
        return "없음"
    return f"{to_kst(snap['sign_change_at']):%m-%d %H:%M} ({snap['sign_change_bars_ago']}봉 전)"


def snapshot_row(tf: str, snap: Optional[dict], current: bool = False) -> dict:
    """표 1행(문자열). 값 없음은 '—'."""
    label = f"{tf} ◀ 현재" if current else tf
    if snap is None:
        return dict(zip(COLUMNS, (label, "—", "—", "—", "—", DIR_NA, "—")))
    return dict(zip(COLUMNS, (
        label, fmt_slope(snap["now"]), *(fmt_slope(snap["lags"][k]) for k in SLOPE_LAGS),
        snap["direction"], _fmt_change(snap),
    )))


def summary_frame(rows: Sequence[Tuple[str, Optional[dict]]], interval: str) -> pd.DataFrame:
    return pd.DataFrame([snapshot_row(tf, snap, current=(tf == interval)) for tf, snap in rows], columns=list(COLUMNS))


def build_lines(rows: Sequence[Tuple[str, Optional[dict]]], interval: str) -> List[str]:
    """텍스트 요약(테스트·검수용) — TF 당 한 줄."""
    lines = [BLOCK_TITLE]
    for tf, snap in rows:
        r = snapshot_row(tf, snap, current=(tf == interval))
        if snap is None:
            lines.append(f"{r['TF']}: 데이터 없음")
            continue
        lines.append(f"{r['TF']}: 현재 {r['현재']} · 1봉 전 {r['1봉 전']} · 3봉 전 {r['3봉 전']} · 5봉 전 {r['5봉 전']} · "
                     f"방향 {r['방향']} · 부호 변경 {r[COLUMNS[-1]]}")
    return lines


FOOTNOTE = (f"기울기 = (MA60(t) − MA60(t−1)) / MA60(t−1) × 100 ({UNIT}) · 방향은 부호만(> 0 상방, ≤ 0 하방) · "
            f"부호 변경은 최근 {SIGN_LOOKBACK}봉 안의 마지막 변경 봉 · 임계·판정 없음 · 각 TF 의 마지막 봉은 진행 중일 수 있음")


# ------------------------------------------------------------------ streamlit
def render_slope_block(df: pd.DataFrame, symbol: str, interval: str) -> List[Tuple[str, Optional[dict]]]:
    """60MA 전환 추적 섹션 상단에 들어가는 블록. 반환값은 (tf, snapshot) 목록(검수용)."""
    import streamlit as st

    rows = multi_tf_snapshots(symbol, interval, df)
    if interval not in SUMMARY_TFS:                     # 현재 TF 가 요약 3종 밖이면 그 행을 맨 앞에 더한다
        rows = [(interval, slope_snapshot(df))] + rows
    st.markdown(f"**{BLOCK_TITLE}** · {symbol}")
    st.dataframe(summary_frame(rows, interval), hide_index=True, width="stretch",
                 column_config={c: st.column_config.TextColumn(c, width="small" if c in ("TF", "방향") else None)
                                for c in COLUMNS})
    st.caption(FOOTNOTE)
    return rows
