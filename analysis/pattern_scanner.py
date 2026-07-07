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

import numpy as np
import pandas as pd

from config.settings import MA_PATTERN_PARAMS, STOCH_LAYERS, STOCH_PIVOT_PARAMS
from indicators.ma_patterns import _is_declining_before, classify_pattern_kind
from indicators.pattern_clean import classify_clean, ma_neckline_at_confirm

# 확정(confirmed) = 넥라인 돌파 완료. candidate = 두 번째 바닥/천장 형성 + 넥라인 미돌파(대기).
STAGE_CONFIRMED = "confirmed"
STAGE_CANDIDATE = "candidate"

# 스캔 대상 MA (MA5·MA10 중심; MA20은 문맥용). 필요 시 CORE 전체로 확장 가능.
DEFAULT_MA_PERIODS: List[int] = [5, 10, 20]
STOCH_SUFFIXES: List[str] = [layer["label"] for layer in STOCH_LAYERS]

# 방향 매핑: 바닥 패턴 → 매수(long), 봉 패턴 → 매도(short).
_LONG = "long"
_SHORT = "short"

# 부호 반전 kind 매핑 (쌍바닥 공간 → 쌍봉 공간). ma_patterns._INVERT_KIND_MAP과 동일.
_INVERT_KIND = {"HL": "LH", "LL": "HH", "EQ": "EQ"}


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
    confirmed_pos: int         # iloc 위치 (candidate는 두 번째 극점 봉 위치)
    price_at_confirm: float     # 확정 봉 종가 (candidate는 극점 봉 종가)
    strength: Optional[float]   # 검출기 확정값 (db/dt/tb/tt 컬럼값). candidate는 None
    # [4차 위임 B] 2단계 노출. confirmed=넥라인 돌파 확정 / candidate=형성 중·미돌파(승격 불가).
    stage: str = STAGE_CONFIRMED

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


# ---------------------------------------------------------------- candidate (B)
# 검출기 무수정 원칙의 명시적 예외(김박사 승인): 출력에 candidate 단계만 추가한다.
# 내부 판정 로직·확정 정의([F7-a] kind+넥라인)는 불변 — 아래는 검출기가 이미 산출한
# 피봇 컬럼(ma{p}_pivot_low/high)만 소비해 '형성 중 미돌파' 구조를 방출한다(스캐너 레이어).


def _is_rising_before(values: np.ndarray, pos: int, decline_lookback: int) -> bool:
    """_is_declining_before의 쌍봉 미러: pos가 decline_lookback 봉 전보다 높음(상승 중)."""
    ref = pos - decline_lookback
    if ref < 0 or np.isnan(values[pos]) or np.isnan(values[ref]):
        return False
    return values[pos] > values[ref]


def _pivot_positions(full_df: pd.DataFrame, col: str) -> List[int]:
    if col not in full_df.columns:
        return []
    s = full_df[col]
    return [i for i in range(len(full_df)) if not pd.isna(s.iloc[i])]


def ma_first_pivot_pos(full_df: pd.DataFrame, period: int, pat: str, confirm_pos: int) -> Optional[int]:
    """확정 봉의 첫 바닥(천장) 피봇 위치 = ma{period}_{pat}_first_pos 컬럼값 (5차 위임 앵커)."""
    fp_col = f"ma{period}_{pat}_first_pos"
    if fp_col not in full_df.columns:
        return None
    raw = full_df[fp_col].iloc[confirm_pos]
    if raw is None or pd.isna(raw):
        return None
    return int(raw)


def _second_extreme_pos(
    full_df: pd.DataFrame, period: int, pat: str, first_pos: int, confirm_pos: int
) -> Optional[int]:
    """확정 봉 기준 두 번째 극점(저점2/천장2) 위치 재구성 (ma_neckline_at_confirm과 동일 규칙)."""
    piv_col = f"ma{period}_pivot_low" if pat == "db" else f"ma{period}_pivot_high"
    if piv_col not in full_df.columns:
        return None
    s = full_df[piv_col]
    ext = [i for i in range(first_pos + 1, confirm_pos) if not pd.isna(s.iloc[i])]
    return ext[-1] if ext else None


def scan_ma_candidates(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    periods: Optional[List[int]] = None,
    *,
    lookback: Optional[int] = None,
    decline_lookback: Optional[int] = None,
) -> List[PatternEvent]:
    """형성 중(두 번째 극점 확정 + 넥라인 미돌파) MA 쌍바닥/쌍봉을 candidate로 방출.

    검출기 확정 컬럼은 건드리지 않고 피봇 컬럼만 재해석한다. (period, pat)별로 가장 최근
    미돌파 구조 1건만 방출(현재 대기 후보). kind는 잠정(넥라인 돌파 전이라 미확정).
    """
    if full_df is None or full_df.empty:
        return []
    pers = periods if periods is not None else DEFAULT_MA_PERIODS
    lb = MA_PATTERN_PARAMS["lookback"] if lookback is None else lookback
    dlb = MA_PATTERN_PARAMS["decline_lookback"] if decline_lookback is None else decline_lookback
    close = full_df["close"] if "close" in full_df.columns else None
    last = len(full_df) - 1
    events: List[PatternEvent] = []

    for period in pers:
        ma_col = f"MA{period}"
        if ma_col not in full_df.columns:
            continue
        values = full_df[ma_col].to_numpy(dtype="float64")
        low_pos = _pivot_positions(full_df, f"ma{period}_pivot_low")
        high_pos = _pivot_positions(full_df, f"ma{period}_pivot_high")

        for pat, direction in (("db", _LONG), ("dt", _SHORT)):
            ext_pos = low_pos if pat == "db" else high_pos
            mid_pos = high_pos if pat == "db" else low_pos
            best: Optional[PatternEvent] = None
            best_pb = -1
            for i in range(len(ext_pos) - 1):
                pa, pb = ext_pos[i], ext_pos[i + 1]
                if np.isnan(values[pa]) or np.isnan(values[pb]):
                    continue
                trend_ok = (
                    _is_declining_before(values, pa, dlb) if pat == "db"
                    else _is_rising_before(values, pa, dlb)
                )
                if not trend_ok:
                    continue
                mids = [m for m in mid_pos if pa < m < pb]
                if not mids:
                    continue
                if pat == "db":
                    neckline = max(values[m] for m in mids)
                    if neckline <= max(values[pa], values[pb]):
                        continue
                    broken = any(
                        values[p] > neckline for p in range(pb + 1, last + 1) if not np.isnan(values[p])
                    )
                else:
                    neckline = min(values[m] for m in mids)
                    if neckline >= min(values[pa], values[pb]):
                        continue
                    broken = any(
                        values[p] < neckline for p in range(pb + 1, last + 1) if not np.isnan(values[p])
                    )
                if broken:
                    continue  # 넥라인 돌파됨 → confirmed 영역(candidate 아님)
                onset = pb + lb
                if onset > last:
                    continue  # 두 번째 극점 피봇이 아직 as-of로 확정되지 않음
                # 잠정 kind: db는 저점2 vs 저점1(높아지면 HL), dt는 천장2 vs 천장1(낮아지면 LH).
                raw_kind, _ = classify_pattern_kind(values[pa], values[pb])
                kind = raw_kind if pat == "db" else _INVERT_KIND.get(raw_kind, raw_kind)
                if pb > best_pb:
                    best_pb = pb
                    best = PatternEvent(
                        symbol=symbol, tf=tf,
                        kind_pattern=_pattern_name(pat, direction),
                        ma_or_layer=f"MA{period}", direction=direction,
                        confirmed_bar=pd.Timestamp(full_df.index[pb]),
                        neckline_price=float(neckline),
                        kind=kind, source="ma", clean="indeterminate",
                        confirmed_pos=pb,
                        price_at_confirm=float(close.iloc[pb]) if close is not None else float("nan"),
                        strength=None, stage=STAGE_CANDIDATE,
                    )
            if best is not None:
                events.append(best)
    return events


# ---------------------------------------------------------------- 스토캐 candidate (10차 위임 A)
# 스토캐 검출기(indicators/stochastic.py)는 이미 candidate 컬럼을 산출한다:
#   stoch_{db,dt}_candidate_{suffix}  (두 번째 극점 마킹, kind+넥라인 포함, 넥라인 돌파 전).
# PHASE4-B의 MA candidate와 대칭 — 검출기 무수정, 기존 컬럼을 이벤트로 **노출만** 한다.
def _stoch_pat_cols(pat: str, suffix: str) -> dict:
    return {
        "candidate": f"stoch_{pat}_candidate_{suffix}",
        "confirmed": f"stoch_{pat}_{suffix}",
        "neckline": (f"stoch_neckline_{suffix}" if pat == "db" else f"stoch_dt_neckline_{suffix}"),
        "kind": f"stoch_{pat}_kind_{suffix}",
    }


def scan_stoch_candidates(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    suffixes: Optional[List[str]] = None,
) -> List[PatternEvent]:
    """형성 중(두 번째 극점 마킹 + 넥라인 미돌파) 스토캐 쌍바닥/쌍봉을 candidate로 방출.

    검출기가 이미 산출한 `stoch_{db,dt}_candidate_{suffix}` 컬럼을 노출만 한다(정본, 무수정).
    (suffix, pat)별 가장 최근 마킹 1건 — 그 뒤로 확정(넥라인 돌파)이 없으면 '대기 후보'로 방출.
    ★ 표시·저널 전용 — 승격·판정 금지(stage=candidate).
    """
    if full_df is None or full_df.empty:
        return []
    sfxs = suffixes if suffixes is not None else STOCH_SUFFIXES
    close = full_df["close"] if "close" in full_df.columns else None
    last = len(full_df) - 1
    events: List[PatternEvent] = []

    for sfx in sfxs:
        for pat, direction in (("db", _LONG), ("dt", _SHORT)):
            cols = _stoch_pat_cols(pat, sfx)
            if cols["candidate"] not in full_df.columns or cols["confirmed"] not in full_df.columns:
                continue
            cand = full_df[cols["candidate"]]
            conf = full_df[cols["confirmed"]]
            cand_pos = [i for i in range(len(full_df)) if not pd.isna(cand.iloc[i])]
            if not cand_pos:
                continue
            pb = cand_pos[-1]   # 가장 최근 두 번째 극점 마킹
            # 그 뒤로 확정(넥라인 돌파)이 있으면 이미 confirmed → 대기 후보 아님.
            if any(not pd.isna(conf.iloc[p]) for p in range(pb + 1, last + 1)):
                continue
            neck = None
            if cols["neckline"] in full_df.columns:
                seg = full_df[cols["neckline"]].iloc[pb:last + 1].dropna()
                if not seg.empty:
                    neck = float(seg.iloc[-1])
            kind = None
            if cols["kind"] in full_df.columns and not pd.isna(full_df[cols["kind"]].iloc[pb]):
                kind = str(full_df[cols["kind"]].iloc[pb])
            events.append(PatternEvent(
                symbol=symbol, tf=tf,
                kind_pattern=_pattern_name(pat, direction),
                ma_or_layer=sfx, direction=direction,
                confirmed_bar=pd.Timestamp(full_df.index[pb]),
                neckline_price=neck, kind=kind, source="stoch", clean="indeterminate",
                confirmed_pos=pb,
                price_at_confirm=float(close.iloc[pb]) if close is not None else float("nan"),
                strength=None, stage=STAGE_CANDIDATE,
            ))
    return events


def stoch_candidate_lead_bars(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    suffixes: Optional[List[str]] = None,
) -> List[dict]:
    """적시성 계측(스토캐): confirmed 이벤트별 candidate 선행 봉수 (MA 채널과 동일 정의).

    lead_bars = confirm_pos − (두번째극점 pb + 피봇 lookback). 양수=candidate 선행 관측 가능,
    ≤0 = 넥라인 확정의 구조적 후행성(빠른 돌파). candidate 마킹 pb는 검출기 candidate 컬럼에서 취한다.
    """
    if full_df is None or full_df.empty:
        return []
    sfxs = suffixes if suffixes is not None else STOCH_SUFFIXES
    lb = STOCH_PIVOT_PARAMS["lookback"]
    out: List[dict] = []
    for sfx in sfxs:
        for pat, direction in (("db", _LONG), ("dt", _SHORT)):
            cols = _stoch_pat_cols(pat, sfx)
            if cols["candidate"] not in full_df.columns or cols["confirmed"] not in full_df.columns:
                continue
            cand = full_df[cols["candidate"]]
            conf = full_df[cols["confirmed"]]
            cand_pos = [i for i in range(len(full_df)) if not pd.isna(cand.iloc[i])]
            if not cand_pos:
                continue
            for pos in range(len(full_df)):
                if pd.isna(conf.iloc[pos]):
                    continue
                prev = [c for c in cand_pos if c <= pos]
                if not prev:
                    continue
                pb = prev[-1]
                out.append({
                    "symbol": symbol, "tf": tf, "suffix": sfx, "pat": pat,
                    "direction": direction, "confirm_pos": pos,
                    "candidate_onset_pos": pb + lb, "lead_bars": pos - (pb + lb),
                })
    return out


def candidate_lead_bars(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    periods: Optional[List[int]] = None,
    *,
    lookback: Optional[int] = None,
) -> List[dict]:
    """적시성 계측: confirmed MA db/dt 이벤트별 candidate 선행 봉수.

    lead_bars = confirm_pos − (두번째극점 pb + lookback). 양수 = candidate가 확정보다 N봉
    먼저 관측 가능, 음수/0 = 넥라인 확정의 구조적 후행성(빠른 돌파로 candidate 관측 창이 없음).
    """
    if full_df is None or full_df.empty:
        return []
    pers = periods if periods is not None else DEFAULT_MA_PERIODS
    lb = MA_PATTERN_PARAMS["lookback"] if lookback is None else lookback
    out: List[dict] = []
    for period in pers:
        for pat, direction in (("db", _LONG), ("dt", _SHORT)):
            sig_col = f"ma{period}_{pat}"
            fp_col = f"ma{period}_{pat}_first_pos"
            if sig_col not in full_df.columns or fp_col not in full_df.columns:
                continue
            sig = full_df[sig_col]
            for pos in range(len(full_df)):
                if pd.isna(sig.iloc[pos]):
                    continue
                raw_fp = full_df[fp_col].iloc[pos]
                if raw_fp is None or pd.isna(raw_fp):
                    continue
                pb = _second_extreme_pos(full_df, period, pat, int(raw_fp), pos)
                if pb is None:
                    continue
                out.append({
                    "symbol": symbol, "tf": tf, "period": period, "pat": pat,
                    "direction": direction, "confirm_pos": pos,
                    "candidate_onset_pos": pb + lb, "lead_bars": pos - (pb + lb),
                })
    return out


def scan_dataframe(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    ma_periods: Optional[List[int]] = None,
    stoch_suffixes: Optional[List[str]] = None,
) -> List[PatternEvent]:
    """한 (symbol, tf)의 전 이력 확정 이벤트 (MA + 스토캐). confirmed_bar 오름차순 정렬.

    stage=confirmed만 반환한다(기존 동작 불변). candidate는 scan_ma_candidates로 별도 조회.
    """
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
                "confirmed_pos", "price_at_confirm", "strength", "stage",
            ]
        )
    return pd.DataFrame([e.as_dict() for e in events])
