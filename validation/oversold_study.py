"""12차 위임 — 조건부 과매도 forward 분포 연구 (시간 홀드아웃).

성격: 조건부 분포 연구. 시그널 검증 아님. forward 등록·필터화·매매 시뮬 없음(김박사 확정).

연구 질문(김박사 가설, 데이터 확인 전 사전 등록): 과매도 매수는 승률이 높은 편이나 무조건은
아니다 — ① 완전 역배열의 과매도는 오히려 나쁘다(C1), ② 장기(120MA) 상승 중 과매도는 좋다(C2),
③ 상위 프레임(4d) MACD GC 이후 과매도는 확률이 높다(C3).

정의(동결):
- 과매도 = Wilder RSI(14) ≤ 30. 이벤트 = RSI가 30을 상→하 교차한 봉(진입 봉만).
- 대상: BTC/ETH/BNB/SOL 일봉. 표본 희소로 4심볼 이벤트를 **풀링**(다중비교 억제, 위임).
- forward = 익일 시가 진입 → k일 뒤 시가 청산 로그수익(8차 통일). 주 창 k=20, 부가 5·60.
- 조건: C0 무조건 / C1 10<20<60<120MA(완전 역배열) / C2 sign(MA120[t]−MA120[t−5])>0(기법0 slope)
        / C3 4d MACD선>시그널선(as-of, 봉 마감 기준).

홀드아웃(이 프로젝트 최초): 심볼별 시간 50:50 분할(mid=n//2). 전반=탐색(자유 비교),
후반=확인(선정 조건 단발). **후반은 탐색 단계에서 로드 금지** — explore는 full.iloc[:mid]만
로드한다. confirm은 full을 로드하되(지표 워밍업 연속성) idx≥mid 이벤트만 채점하고 forward는
후반 시가만 사용한다(선견 없음). 지표는 인과적이라 전반 구간 값은 두 방식에서 동일하다.

실행:
  python validation/oversold_study.py explore   # 전반만 → oversold_explore.json + 표
  # (리포트에 선정 규칙·선정 결과·근거·타임스탬프 기록 후 커밋)
  python validation/oversold_study.py confirm    # 후반 단발 → oversold_confirm.json

엔진·검출기·기존 리포트·스펙 무수정 (RSI 지표 추가만). SEED 고정.
"""
import json
import logging
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import MACD_PARAMS, TREND_LAYER_PARAMS  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402
from indicators.rsi_wilder import (  # noqa: E402
    OVERSOLD_THRESHOLD,
    WILDER_RSI_PERIOD,
    oversold_downcross,
    wilder_rsi,
)

HERE = os.path.dirname(os.path.abspath(__file__))
EXPLORE_JSON = os.path.join(HERE, "oversold_explore.json")
CONFIRM_JSON = os.path.join(HERE, "oversold_confirm.json")
SELECTION_JSON = os.path.join(HERE, "oversold_selection.json")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
FETCH_LIMIT = 5000                                  # 일봉 전체 역사(페이지네이션)
N_SLOPE = TREND_LAYER_PARAMS["TREND_SLOPE_N"]       # 기법0 slope N = 5
FWD_WINDOWS = {"fwd5": 5, "fwd20": 20, "fwd60": 60}
FWD_MAIN = 20
OVERLAP_BARS = 20                                   # 비중복 유효표본 근사(주 창 기준)


# ------------------------------------------------------------------ 데이터·지표
def load_full(symbol: str) -> pd.DataFrame:
    """일봉 전체 역사(OHLCV). 인과적 지표라 전반 값은 전반-only 계산과 동일하다."""
    bare = fetch_ohlcv_bare(symbol, "1d", FETCH_LIMIT, paginated=True)
    bare = bare[["open", "high", "low", "close", "volume"]].astype(float).dropna()
    return bare


def _fourd_macd_gc(bare: pd.DataFrame) -> pd.Series:
    """1d→4d 리샘플(app resample_timeframe와 동일 파라미터) MACD선>시그널 상태를 1d로 as-of.

    4d 바는 우측 라벨(블록 종료일)=봉 마감 시점. ffill로 이후 1d봉에 상태 전파(선견 없음).
    """
    d4 = bare.resample("4D", label="right", closed="right", origin="start").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    if len(d4) < MACD_PARAMS["slow"] + MACD_PARAMS["signal"]:
        return pd.Series(np.nan, index=bare.index)
    ema_fast = d4["close"].ewm(span=MACD_PARAMS["fast"], adjust=False).mean()
    ema_slow = d4["close"].ewm(span=MACD_PARAMS["slow"], adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=MACD_PARAMS["signal"], adjust=False).mean()
    gc = (macd > signal)
    return gc.reindex(bare.index, method="ffill")


def add_features(bare: pd.DataFrame) -> pd.DataFrame:
    """RSI·MA(10/20/60/120)·slope120·4d MACD GC·이벤트 플래그. 모두 인과적(선견 없음)."""
    out = bare.copy()
    close = out["close"]
    out["rsi"] = wilder_rsi(close)
    for p in (10, 20, 60, 120):
        out[f"ma{p}"] = close.rolling(window=p).mean()
    ma120 = out["ma120"]
    out["slope120"] = np.sign(ma120 - ma120.shift(N_SLOPE))   # 부호(기법0). NaN=정의불가
    out["gc4d"] = _fourd_macd_gc(out)
    out["event"] = oversold_downcross(out["rsi"], OVERSOLD_THRESHOLD)
    return out


def _forward_logret(open_: np.ndarray, k: int) -> np.ndarray:
    """익일 시가 진입 → k일 뒤 시가 청산 로그수익(8차 regime_forward와 동일). 범위 밖 NaN."""
    n = len(open_)
    out = np.full(n, np.nan)
    for t in range(n):
        e, x = t + 1, t + 1 + k
        if x > n - 1:
            continue
        out[t] = np.log(open_[x] / open_[e])
    return out


def _mae_window(open_: np.ndarray, low: np.ndarray, k: int) -> np.ndarray:
    """진입(익일 시가) 대비 보유창[e..e+k] 최저 저가까지 로그수익(최대 역행폭, ≤0)."""
    n = len(open_)
    out = np.full(n, np.nan)
    for t in range(n):
        e, x = t + 1, t + 1 + k
        if x > n - 1:
            continue
        out[t] = np.log(low[e:x + 1].min() / open_[e])
    return out


def _condition_flags(feat: pd.DataFrame, t: int) -> dict:
    """이벤트 봉 t의 조건 충족 여부(정의 불가는 False = 해당 군 미포함)."""
    r = feat.iloc[t]
    c1 = bool(
        r["ma10"] < r["ma20"] < r["ma60"] < r["ma120"]
    ) if not pd.isna(r["ma120"]) else False
    c2 = bool(r["slope120"] > 0) if not pd.isna(r["slope120"]) else False
    c3 = bool(r["gc4d"]) if not pd.isna(r["gc4d"]) else False
    return {"C1": c1, "C2": c2, "C3": c3}


def collect_events(symbol: str, phase: str) -> list:
    """phase='explore'(전반만) / 'confirm'(후반 이벤트만, 전반은 워밍업). 이벤트 행 리스트."""
    full = load_full(symbol)
    n = len(full)
    mid = n // 2
    split_ts = full.index[mid]

    if phase == "explore":
        feat = add_features(full.iloc[:mid].copy())     # ★ 후반 미로드
        lo, hi = 0, len(feat)
    elif phase == "confirm":
        feat = add_features(full.copy())                 # 전반=워밍업, 후반=채점
        lo, hi = mid, n
    else:
        raise ValueError(phase)

    open_ = feat["open"].to_numpy()
    low = feat["low"].to_numpy()
    fwd = {name: _forward_logret(open_, k) for name, k in FWD_WINDOWS.items()}
    mae = _mae_window(open_, low, FWD_MAIN)

    ev_pos = np.where(feat["event"].fillna(False).to_numpy())[0]
    rows = []
    for t in ev_pos:
        if not (lo <= t < hi):
            continue
        if np.isnan(fwd[f"fwd{FWD_MAIN}"][t]):           # 주 창 미확보 이벤트 제외
            continue
        ts = feat.index[t]
        # 홀드아웃 불변식: explore 이벤트+forward는 split_ts 이전, confirm은 이후.
        if phase == "explore":
            assert ts < split_ts
        else:
            assert ts >= split_ts
        flags = _condition_flags(feat, t)
        rows.append({
            "symbol": symbol, "ts": ts.isoformat(), "phase": phase,
            "fwd5": _f(fwd["fwd5"][t]), "fwd20": _f(fwd["fwd20"][t]),
            "fwd60": _f(fwd["fwd60"][t]), "mae20": _f(mae[t]),
            **flags,
        })
    return rows, {"symbol": symbol, "n_bars": n, "mid": mid,
                  "split_ts": split_ts.isoformat(),
                  "first_ts": full.index[0].isoformat(), "last_ts": full.index[-1].isoformat()}


def _f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


# ------------------------------------------------------------------ 집계
def _effective_n(rows: list) -> int:
    """비중복 유효표본 근사: 심볼별 시간순 그리디로 ≥OVERLAP_BARS(주창)일 간격 이벤트만 count."""
    total = 0
    by_sym = {}
    for r in rows:
        by_sym.setdefault(r["symbol"], []).append(pd.Timestamp(r["ts"]))
    for sym, ts_list in by_sym.items():
        ts_list.sort()
        last = None
        for ts in ts_list:
            if last is None or (ts - last).days >= OVERLAP_BARS:
                total += 1
                last = ts
    return total


def group_stats(rows: list, key: str = "fwd20") -> dict:
    """한 조건군 이벤트들의 n/유효n/mean/median/승률(>0). fwd5·fwd60 mean 병기."""
    vals = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
    if len(vals) == 0:
        return {"n": 0, "eff_n": 0, "mean": None, "median": None, "winrate": None,
                "fwd5_mean": None, "fwd60_mean": None}
    f5 = np.array([r["fwd5"] for r in rows if r["fwd5"] is not None], dtype=float)
    f60 = np.array([r["fwd60"] for r in rows if r["fwd60"] is not None], dtype=float)
    return {
        "n": int(len(vals)),
        "eff_n": _effective_n(rows),
        "mean": float(vals.mean()),
        "median": float(np.median(vals)),
        "winrate": float((vals > 0).mean()),
        "fwd5_mean": float(f5.mean()) if len(f5) else None,
        "fwd60_mean": float(f60.mean()) if len(f60) else None,
    }


def partition(rows: list) -> dict:
    """조건군별 이벤트 부분집합. C0 전체, C1/C2/C3 및 교차 C2∩C3."""
    return {
        "C0": rows,
        "C1": [r for r in rows if r["C1"]],
        "C2": [r for r in rows if r["C2"]],
        "C3": [r for r in rows if r["C3"]],
        "C2&C3": [r for r in rows if r["C2"] and r["C3"]],
    }


# ------------------------------------------------------------------ 실행 단계
def run_explore():
    all_rows, meta = [], []
    for sym in SYMBOLS:
        rows, m = collect_events(sym, "explore")
        all_rows += rows
        meta.append(m)
    groups = partition(all_rows)
    stats = {g: group_stats(rs) for g, rs in groups.items()}
    out = {"phase": "explore", "n_events_pooled": len(all_rows),
           "meta": meta, "stats": stats,
           "per_symbol_counts": {s: sum(1 for r in all_rows if r["symbol"] == s) for s in SYMBOLS}}
    with open(EXPLORE_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _print_stats("탐색(전반)", stats, out["n_events_pooled"], out["per_symbol_counts"])
    print(f"\n분할 메타: " + " | ".join(f"{m['symbol']} n={m['n_bars']} split={m['split_ts'][:10]}" for m in meta))
    print(f"→ {EXPLORE_JSON}")


def run_confirm():
    if not os.path.exists(SELECTION_JSON):
        print(f"선정 파일 없음: {SELECTION_JSON} — 탐색 후 선정을 먼저 기록/커밋하세요.")
        sys.exit(1)
    with open(SELECTION_JSON, encoding="utf-8") as f:
        selection = json.load(f)
    selected = selection["selected_conditions"]          # 예: ["C2","C2&C3"]
    test_groups = ["C0"] + selected + (["C1"] if "C1" not in selected else [])

    all_rows, meta = [], []
    for sym in SYMBOLS:
        rows, m = collect_events(sym, "confirm")
        all_rows += rows
        meta.append(m)
    groups = partition(all_rows)
    stats = {g: group_stats(groups[g]) for g in test_groups}

    # 부가(관측, 홀드아웃 무관): C2∩과매도 MAE 분포 — 전 표본(양 반) 풀링.
    mae_rows = _all_c2_oversold_mae()
    out = {"phase": "confirm", "selected": selected, "test_groups": test_groups,
           "n_events_pooled": len(all_rows), "meta": meta, "stats": stats,
           "mae_c2_oversold": mae_rows}
    with open(CONFIRM_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    _print_stats("확인(후반)", stats, out["n_events_pooled"], None)
    print(f"\nMAE(C2∩과매도, 전표본): {mae_rows['n']}건 "
          f"median={mae_rows['median']:.4f} p10={mae_rows['p10']:.4f} p90={mae_rows['p90']:.4f}")
    print(f"→ {CONFIRM_JSON}")


def _all_c2_oversold_mae() -> dict:
    """C2∩과매도 이벤트 MAE20 분포(전 표본 풀링, 관측 전용 — 판정 아님)."""
    vals = []
    for sym in SYMBOLS:
        full = load_full(sym)
        feat = add_features(full.copy())
        open_ = feat["open"].to_numpy()
        low = feat["low"].to_numpy()
        mae = _mae_window(open_, low, FWD_MAIN)
        ev = np.where(feat["event"].fillna(False).to_numpy())[0]
        for t in ev:
            if np.isnan(mae[t]):
                continue
            if not pd.isna(feat.iloc[t]["slope120"]) and feat.iloc[t]["slope120"] > 0:
                vals.append(float(mae[t]))
    vals = np.array(vals, dtype=float)
    if len(vals) == 0:
        return {"n": 0}
    return {"n": int(len(vals)), "median": float(np.median(vals)),
            "mean": float(vals.mean()), "p10": float(np.percentile(vals, 10)),
            "p25": float(np.percentile(vals, 25)), "p90": float(np.percentile(vals, 90)),
            "worst": float(vals.min())}


def _print_stats(title, stats, n_pool, per_sym):
    print(f"\n=== {title} · 풀 이벤트 {n_pool}건" + (f" {per_sym}" if per_sym else "") + " ===")
    print(f"{'군':7s} {'n':>4s} {'유효n':>5s} {'fwd20 mean':>11s} {'median':>9s} {'승률':>6s} "
          f"{'fwd5 m':>8s} {'fwd60 m':>8s}")
    for g, s in stats.items():
        if s["n"] == 0:
            print(f"{g:7s} {0:>4d}    -           -         -      -        -        -")
            continue
        print(f"{g:7s} {s['n']:>4d} {s['eff_n']:>5d} {s['mean']*100:>10.2f}% {s['median']*100:>8.2f}% "
              f"{s['winrate']*100:>5.1f}% {s['fwd5_mean']*100:>7.2f}% {s['fwd60_mean']*100:>7.2f}%")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "explore"
    if mode == "explore":
        run_explore()
    elif mode == "confirm":
        run_confirm()
    else:
        print("usage: oversold_study.py [explore|confirm]")
        sys.exit(1)
