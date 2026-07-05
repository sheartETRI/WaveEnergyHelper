"""L1 패턴 스캐너 (v2) — 전 TF × 심볼 상시 스캔 → PatternEvent 스트림.

v2의 입력 레이어. 기존 검출기(add_ma_patterns / add_stochastic_slow_layers)를
전 TF 루프로 래핑만 한다 — 검출기는 재작성하지 않고 소비만 한다.

확정 의미론 (v1 [F7-a]과 동일):
- 검출기의 확정 컬럼(ma{n}_db, stoch_db_{suffix} 등)이 non-NA인 봉 = 넥라인 돌파 확정 봉.
- 추가로 pattern_clean.classify_clean 으로 "clean"(kind 일치 + 넥라인 스윙) 여부를 기록한다.
- candidate(추적 중)는 확정 컬럼이 NA이므로 이벤트로 방출하지 않는다 → 승격 불가.

MA 쓰리바닥/쓰리봉: 리포에 MA 삼중 검출기가 없다(스토캐만 존재). §10 미결로 김박사
에스컬레이션 대상. 현재 스캐너는 존재하는 검출기만 방출한다 (MA db/dt + 스토캐 db/dt/tb/tt).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

import pandas as pd

from config.settings import STOCH_LAYERS
from indicators.pattern_clean import classify_clean, ma_neckline_at_confirm

# 스캔 대상 MA (MA5·MA10 중심; MA20은 문맥용). 필요 시 CORE 전체로 확장 가능.
DEFAULT_MA_PERIODS: List[int] = [5, 10, 20]
STOCH_SUFFIXES: List[str] = [layer["label"] for layer in STOCH_LAYERS]

# 방향 매핑: 바닥 패턴 → 매수(long), 봉 패턴 → 매도(short).
_LONG = "long"
_SHORT = "short"


@dataclass
class PatternEvent:
    symbol: str
    tf: str
    kind_pattern: str          # double_bottom | double_top | triple_bottom | triple_top
    ma_or_layer: str           # "MA5".."MA240" | 스토캐 라벨 "(20,10,10)" 등
    direction: str             # long | short
    confirmed_bar: pd.Timestamp
    neckline_price: Optional[float]
    kind: Optional[str]        # HL/LL (바닥) | HH/LH (봉) | None
    source: str                # "ma" | "stoch"
    clean: str                 # clean | not-clean | indeterminate | n/a
    confirmed_pos: int         # iloc 위치
    price_at_confirm: float     # 확정 봉 종가
    strength: Optional[float]   # 검출기 확정값 (db/dt/tb/tt 컬럼값)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["confirmed_bar"] = pd.Timestamp(self.confirmed_bar)
        return d


def _pattern_name(pat: str, direction: str) -> str:
    return {
        ("db", _LONG): "double_bottom",
        ("dt", _SHORT): "double_top",
        ("tb", _LONG): "triple_bottom",
        ("tt", _SHORT): "triple_top",
    }[(pat, direction)]


def scan_ma_patterns(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    periods: Optional[List[int]] = None,
) -> List[PatternEvent]:
    """MA 쌍바닥/쌍봉 확정 봉 → PatternEvent. full_df는 run_indicator_pipeline 결과."""
    if full_df is None or full_df.empty:
        return []
    pers = periods if periods is not None else DEFAULT_MA_PERIODS
    events: List[PatternEvent] = []
    close = full_df["close"] if "close" in full_df.columns else None

    for period in pers:
        for pat, direction in (("db", _LONG), ("dt", _SHORT)):
            sig_col = f"ma{period}_{pat}"
            if sig_col not in full_df.columns:
                continue
            kind_col = f"ma{period}_{pat}_kind"
            prev_col = f"ma{period}_{pat}_prev_opp"
            sig = full_df[sig_col]
            for pos in range(len(full_df)):
                val = sig.iloc[pos]
                if pd.isna(val):
                    continue
                kind = full_df[kind_col].iloc[pos] if kind_col in full_df.columns else None
                prev_opp = full_df[prev_col].iloc[pos] if prev_col in full_df.columns else None
                neckline = ma_neckline_at_confirm(full_df, period, pat, pos)
                clean = classify_clean(pat, kind, neckline, prev_opp)
                events.append(
                    PatternEvent(
                        symbol=symbol,
                        tf=tf,
                        kind_pattern=_pattern_name(pat, direction),
                        ma_or_layer=f"MA{period}",
                        direction=direction,
                        confirmed_bar=pd.Timestamp(full_df.index[pos]),
                        neckline_price=neckline,
                        kind=None if kind is None or pd.isna(kind) else str(kind),
                        source="ma",
                        clean=clean,
                        confirmed_pos=pos,
                        price_at_confirm=float(close.iloc[pos]) if close is not None else float("nan"),
                        strength=float(val),
                    )
                )
    return events


def scan_stoch_patterns(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    suffixes: Optional[List[str]] = None,
) -> List[PatternEvent]:
    """스토캐 3층 쌍바닥/쌍봉/쓰리바닥/쓰리봉 확정 봉 → PatternEvent."""
    if full_df is None or full_df.empty:
        return []
    sfx = suffixes if suffixes is not None else STOCH_SUFFIXES
    events: List[PatternEvent] = []
    close = full_df["close"] if "close" in full_df.columns else None

    for suffix in sfx:
        for pat, direction in (("db", _LONG), ("dt", _SHORT), ("tb", _LONG), ("tt", _SHORT)):
            sig_col = f"stoch_{pat}_{suffix}"
            if sig_col not in full_df.columns:
                continue
            kind_col = f"stoch_{pat}_kind_{suffix}"
            # 넥라인: db/dt만 저장됨. db는 stoch_neckline_{suffix}, dt는 stoch_dt_neckline_{suffix}.
            if pat == "db":
                nl_col = f"stoch_neckline_{suffix}"
            elif pat == "dt":
                nl_col = f"stoch_dt_neckline_{suffix}"
            else:
                nl_col = None  # tb/tt 넥라인 미저장 (§10 gap)
            prev_col = f"stoch_{pat}_prev_opp_{suffix}"
            sig = full_df[sig_col]
            for pos in range(len(full_df)):
                val = sig.iloc[pos]
                if pd.isna(val):
                    continue
                kind = full_df[kind_col].iloc[pos] if kind_col in full_df.columns else None
                neckline = None
                if nl_col and nl_col in full_df.columns:
                    raw_nl = full_df[nl_col].iloc[pos]
                    neckline = None if pd.isna(raw_nl) else float(raw_nl)
                if pat in ("db", "dt"):
                    prev_opp = full_df[prev_col].iloc[pos] if prev_col in full_df.columns else None
                    clean = classify_clean(pat, kind, neckline, prev_opp)
                else:
                    clean = "n/a"  # classify_clean은 db/dt 전용
                events.append(
                    PatternEvent(
                        symbol=symbol,
                        tf=tf,
                        kind_pattern=_pattern_name(pat, direction),
                        ma_or_layer=suffix,
                        direction=direction,
                        confirmed_bar=pd.Timestamp(full_df.index[pos]),
                        neckline_price=neckline,
                        kind=None if kind is None or pd.isna(kind) else str(kind),
                        source="stoch",
                        clean=clean,
                        confirmed_pos=pos,
                        price_at_confirm=float(close.iloc[pos]) if close is not None else float("nan"),
                        strength=float(val),
                    )
                )
    return events


def scan_dataframe(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    ma_periods: Optional[List[int]] = None,
    stoch_suffixes: Optional[List[str]] = None,
) -> List[PatternEvent]:
    """한 (symbol, tf)의 전 이력 확정 이벤트 (MA + 스토캐). confirmed_bar 오름차순 정렬."""
    events = scan_ma_patterns(full_df, symbol, tf, ma_periods)
    events += scan_stoch_patterns(full_df, symbol, tf, stoch_suffixes)
    events.sort(key=lambda e: (e.confirmed_bar, e.source, e.ma_or_layer))
    return events


def scan_latest(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    **kwargs,
) -> List[PatternEvent]:
    """마지막(최신 마감) 봉에서 확정된 이벤트만 (봉 마감마다 검출용)."""
    if full_df is None or full_df.empty:
        return []
    last_ts = pd.Timestamp(full_df.index[-1])
    return [e for e in scan_dataframe(full_df, symbol, tf, **kwargs) if e.confirmed_bar == last_ts]


def scan_symbol_tf(
    symbol: str,
    tf: str,
    limit: Optional[int] = None,
    **kwargs,
) -> List[PatternEvent]:
    """라이브 진입점: fetch → run_indicator_pipeline → 전 이력 스캔.

    검출기 파이프라인만 소비한다(display.asof 재사용). 네트워크 없는 테스트는
    scan_dataframe에 사전 계산된 df를 직접 넘길 것.
    """
    from display.asof import fetch_ohlcv_bare, run_indicator_pipeline

    bare = fetch_ohlcv_bare(symbol, tf, limit)
    if bare is None or bare.empty:
        return []
    full_df = run_indicator_pipeline(bare)
    return scan_dataframe(full_df, symbol, tf, **kwargs)


def events_to_dataframe(events: List[PatternEvent]) -> pd.DataFrame:
    """PatternEvent 리스트 → DataFrame (저널·표시·백테스트 공용)."""
    if not events:
        return pd.DataFrame(
            columns=[
                "symbol", "tf", "kind_pattern", "ma_or_layer", "direction",
                "confirmed_bar", "neckline_price", "kind", "source", "clean",
                "confirmed_pos", "price_at_confirm", "strength",
            ]
        )
    return pd.DataFrame([e.as_dict() for e in events])
