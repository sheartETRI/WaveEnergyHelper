"""SPEC_WAVE_MM_SIZING §2 — 고정 5% vs 변동성 기반 사이징 (ATR 역비례).

시뮬레이터(wave_mm_simulator)를 그대로 재사용한다. 체결·비용·1포지션·20봉 청산·
평단 −3% 손절은 전부 동일하고, 사이즈 입력만 확장한다. 신규 체결 가정 없음.

VOLSIZE: size_i = min(5%, 5% × ref_i / atrp_i)
  atrp_i = ATR14(신호봉) ÷ 진입가            — 진입 시점에 확정된 값만 사용
  ref_i  = 신호봉 **이전** 180일 atrp 중앙값 — 룩어헤드 금지
상한 5%는 사용자 실규칙("트랜치당 5% 이하")과의 정합. VOLSIZE 는 줄이기만 한다.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from analysis.wave_mm_simulator import (
    TRANCHE_PCT,
    _cache_dir,
    load_bars,
)

# --- §2 고정 파라미터 (대안 탐색 금지) ---
ATR_PERIOD = 14
REF_WINDOW_DAYS = 180
SIZE_CAP_PCT = TRANCHE_PCT      # 5%

# --- §3 SZ-R0 관문 ---
DISPERSION_MIN = 1.5            # atrp P75/P25
REDUCED_SHARE_MIN = 0.20        # 5% 미만으로 줄어드는 트레이드 비율

# --- §4 판정 ---
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260904
CI_ALPHA = 0.05
MIN_TRADES = 100
MIN_ACTIVE_MONTHS = 40


def atrp_path(symbol: str, ltf: str) -> str:
    return os.path.join(_cache_dir(), f"atrp_{symbol}_{ltf}.csv")


def atrp_series(symbol: str, ltf: str, *, build: bool = False) -> pd.Series:
    """프레임의 atrp 시계열 = ATR14 ÷ 종가 (기존 add_confluence_indicators 재사용).

    지표 계산은 인과적 rolling/ewm 이므로 봉별 절단 재계산과 동치다.
    """
    path = atrp_path(symbol, ltf)
    if os.path.isfile(path):
        s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        s.index.name = "open_time"
        return s
    if not build:
        return pd.Series(dtype=float)
    from analysis.wave_confluence import add_confluence_indicators
    from display.asof import run_indicator_pipeline

    bars = load_bars(symbol, ltf)
    if bars.empty:
        return pd.Series(dtype=float)
    pipe = add_confluence_indicators(run_indicator_pipeline(bars))
    s = (pipe["atr_pct"] / 100.0).rename("atrp")   # atr_pct = atr14/close*100
    s.to_frame().to_csv(path)
    return s


def _ref_median(series: pd.Series, ts: pd.Timestamp) -> Optional[float]:
    """신호봉 이전 REF_WINDOW_DAYS 의 atrp 중앙값 (ts 미포함 — 룩어헤드 금지).

    180일 미만 이력이면 가용 전체를 쓴다.
    """
    prior = series.loc[series.index < ts]
    if prior.empty:
        return None
    lo = ts - pd.Timedelta(days=REF_WINDOW_DAYS)
    win = prior.loc[prior.index >= lo]
    if win.empty:
        win = prior
    win = win.dropna()
    return float(win.median()) if len(win) else None


def event_atrp(events: pd.DataFrame, bars_by_key: Dict[Tuple[str, str], pd.DataFrame],
               *, build: bool = False) -> pd.DataFrame:
    """이벤트별 atrp_i · ref_i · VOLSIZE 사이즈. 진입가는 신호봉 다음 봉 시가."""
    rows = []
    for (sym, ltf), grp in events.groupby(["symbol", "ltf"]):
        s = atrp_series(sym, ltf, build=build)
        bars = bars_by_key.get((sym, ltf))
        if s.empty or bars is None or bars.empty:
            continue
        atr14 = s * pd.to_numeric(bars["close"], errors="coerce")  # atrp -> ATR14 복원
        for ev in grp.itertuples():
            ts = pd.Timestamp(ev.timestamp)
            if ts not in bars.index:
                continue
            pos = int(bars.index.get_loc(ts))
            if pos + 1 >= len(bars):
                continue
            entry_price = float(bars["open"].iloc[pos + 1])
            a = atr14.get(ts, np.nan)
            if not np.isfinite(a) or entry_price <= 0:
                continue
            atrp_i = float(a) / entry_price
            ref = _ref_median(s, ts)
            if ref is None or not np.isfinite(ref) or atrp_i <= 0:
                continue
            size = min(SIZE_CAP_PCT, SIZE_CAP_PCT * ref / atrp_i)
            rows.append({
                "event_id": ev.event_id, "symbol": sym, "ltf": ltf, "timestamp": ts,
                "atrp": atrp_i, "ref_atrp": ref, "size_pct": size,
                "reduced": bool(size < SIZE_CAP_PCT - 1e-12),
            })
    return pd.DataFrame(rows)


def volsize_map(atrp_df: pd.DataFrame) -> Dict[str, float]:
    if atrp_df.empty:
        return {}
    return dict(zip(atrp_df["event_id"], atrp_df["size_pct"]))


# ------------------------------------------------------------ §3 관문
def dispersion_gate(atrp_df: pd.DataFrame, trades: Optional[pd.DataFrame] = None) -> dict:
    """SZ-R0 — 체결 트레이드의 atrp 산포와 VOLSIZE 축소 비율."""
    df = atrp_df
    if trades is not None and not trades.empty:
        df = atrp_df[atrp_df["event_id"].isin(set(trades["event_id"]))]
    if df.empty:
        return {"n": 0, "go": False}
    q = df["atrp"].quantile([0.25, 0.5, 0.75])
    p25, p50, p75 = float(q.loc[0.25]), float(q.loc[0.5]), float(q.loc[0.75])
    dispersion = p75 / p25 if p25 > 0 else np.inf
    reduced = df["reduced"].mean()
    sizes = df["size_pct"]
    return {
        "n": len(df),
        "atrp_p25": round(p25, 6), "atrp_p50": round(p50, 6), "atrp_p75": round(p75, 6),
        "dispersion": round(float(dispersion), 4),
        "reduced_share": round(float(reduced), 4),
        "size_mean_pct": round(float(sizes.mean()), 4),
        "size_p25_pct": round(float(sizes.quantile(0.25)), 4),
        "size_median_pct": round(float(sizes.median()), 4),
        "size_min_pct": round(float(sizes.min()), 4),
        "cond_dispersion": bool(dispersion >= DISPERSION_MIN),
        "cond_reduced": bool(reduced >= REDUCED_SHARE_MIN),
        "go": bool(dispersion >= DISPERSION_MIN and reduced >= REDUCED_SHARE_MIN),
    }


# ------------------------------------------------------------ §4 지표
def monthly_log_series(trades: pd.DataFrame, months: Optional[list] = None) -> pd.Series:
    """월별 로그 수익 계열. months 를 주면 그 달력에 맞춰 0 으로 채운다."""
    if trades.empty:
        idx = months or []
        return pd.Series([0.0] * len(idx), index=idx, dtype=float)
    t = trades.copy()
    t["m"] = pd.to_datetime(t["exit_ts"]).dt.to_period("M").astype(str)
    s = t.groupby("m")["log_growth"].sum()
    if months is not None:
        s = s.reindex(months, fill_value=0.0)
    return s.astype(float)


def sharpe(monthly: pd.Series) -> Optional[float]:
    """S = 월별 로그 수익의 평균 / 표준편차 (무위험 0). 사이즈 상수배에 근사 불변."""
    m = monthly.dropna()
    if len(m) < 2:
        return None
    sd = float(m.std(ddof=1))
    if sd == 0 or not np.isfinite(sd):
        return None
    return round(float(m.mean()) / sd, 6)


def paired_months(a: pd.DataFrame, b: pd.DataFrame) -> list:
    """두 시나리오의 월 달력 합집합 (짝지어 비교하기 위한 공통 축)."""
    def ms(tr):
        if tr.empty:
            return set()
        return set(pd.to_datetime(tr["exit_ts"]).dt.to_period("M").astype(str))
    return sorted(ms(a) | ms(b))


def delta_sharpe(volsize: pd.DataFrame, base: pd.DataFrame) -> Optional[float]:
    months = paired_months(volsize, base)
    if not months:
        return None
    sv = sharpe(monthly_log_series(volsize, months))
    sb = sharpe(monthly_log_series(base, months))
    if sv is None or sb is None:
        return None
    return round(sv - sb, 6)


def bootstrap_delta_sharpe(volsize: pd.DataFrame, base: pd.DataFrame,
                           n_boot=BOOTSTRAP_N, seed=BOOTSTRAP_SEED) -> dict:
    """월 블록 부트스트랩 — 같은 달을 양쪽에서 함께 뽑아 짝을 유지한다."""
    months = paired_months(volsize, base)
    point = delta_sharpe(volsize, base)
    out = {"delta": point, "ci_low": None, "ci_high": None, "n_boot": 0,
           "n_months": len(months), "seed": seed}
    if len(months) < 3:
        return out
    mv = monthly_log_series(volsize, months).to_numpy()
    mb = monthly_log_series(base, months).to_numpy()
    rng = np.random.default_rng(seed)
    k = len(months)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, k, k)
        v, b = mv[idx], mb[idx]
        sdv, sdb = v.std(ddof=1), b.std(ddof=1)
        if sdv == 0 or sdb == 0 or not np.isfinite(sdv) or not np.isfinite(sdb):
            continue
        vals.append(v.mean() / sdv - b.mean() / sdb)
    if not vals:
        return out
    arr = np.asarray(vals)
    out.update({
        "ci_low": round(float(np.percentile(arr, CI_ALPHA / 2 * 100)), 6),
        "ci_high": round(float(np.percentile(arr, (1 - CI_ALPHA / 2) * 100)), 6),
        "n_boot": len(arr),
    })
    return out


def active_months(volsize: pd.DataFrame, base: pd.DataFrame) -> int:
    return len(paired_months(volsize, base))


def half_split(volsize: pd.DataFrame, base: pd.DataFrame) -> list[dict]:
    months = paired_months(volsize, base)
    if len(months) < 4:
        return []
    mid = len(months) // 2
    rows = []
    for name, sel in (("first_half", months[:mid]), ("second_half", months[mid:])):
        def cut(tr):
            if tr.empty:
                return tr
            m = pd.to_datetime(tr["exit_ts"]).dt.to_period("M").astype(str)
            return tr[m.isin(sel)]
        v, b = cut(volsize), cut(base)
        rows.append({
            "split": name, "months": len(sel),
            "volsize_trades": len(v), "base_trades": len(b),
            "s_volsize": sharpe(monthly_log_series(v, sel)),
            "s_base": sharpe(monthly_log_series(b, sel)),
            "delta": delta_sharpe(v, b),
        })
    return rows


def skew_diagnostic(base: pd.DataFrame, atrp_df: pd.DataFrame,
                    top_frac: float = 0.05) -> dict:
    """§5-2 — 상위 수익 트레이드가 고변동 진입에서 나오는가."""
    if base.empty or atrp_df.empty:
        return {"n": 0}
    # base 에도 size_pct 가 있으므로 충돌을 피해 이름을 바꿔 붙인다
    cols = atrp_df[["event_id", "atrp", "size_pct"]].rename(
        columns={"size_pct": "volsize_pct"})
    m = base.merge(cols, on="event_id", how="inner")
    m["size_pct"] = m["volsize_pct"]
    if m.empty:
        return {"n": 0}
    m["atrp_q"] = m["atrp"].rank(pct=True)
    k = max(int(len(m) * top_frac), 1)
    top = m.nlargest(k, "net_ret")
    return {
        "n": len(m),
        "top_n": k,
        "top_atrp_quantile_mean": round(float(top["atrp_q"].mean()), 4),
        "top_atrp_quantile_median": round(float(top["atrp_q"].median()), 4),
        "all_atrp_quantile_mean": round(float(m["atrp_q"].mean()), 4),
        "top_size_mean_pct": round(float(top["size_pct"].mean()), 4),
        "top_size_reduction_pct": round(
            float((1 - top["size_pct"] / SIZE_CAP_PCT).mean() * 100), 4),
        "all_size_reduction_pct": round(
            float((1 - m["size_pct"] / SIZE_CAP_PCT).mean() * 100), 4),
    }
