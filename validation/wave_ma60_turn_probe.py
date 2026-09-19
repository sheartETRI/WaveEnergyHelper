"""후보 1 — 60MA 전환 전략, 탐색적 계측 1회 (판정 없음).

> 탐색적 계측이며 판정이 아니다. 사전등록 커밋 a01fd41
> (docs/CANDIDATES_POST_2027_03.md, 원격 main) 이후에 수행하는 계측이다.
> BASE 대비 비교·기대값 우위·ACCEPT/REJECT를 산출하지 않는다. 이 수치는
> 후보 1 스펙의 설계 근거(표본 규모·관찰 창 타당성)로만 사용하며, 실제
> 검정은 2027-03 이후 전방 데이터를 포함해 사전등록 스펙으로 수행한다.
> 같은 표본에서 나온 탐색 결과이므로 그 자체로는 전략의 근거가 되지 않는다.

기존 검출기·지표·시뮬레이터 상수를 **소비만** 한다 (정의 파일 무수정):
- 스토캐 대파동(20,10,10) 쌍바닥/쌍봉 : indicators.stochastic (앱 파이프라인 그대로)
- 가격 10MA 쌍봉                       : indicators.ma_patterns (ma10_dt)
- 60MA 방향                            : MA60(t) > MA60(t-1), 창 1봉 (F2-b 기울기 정의 승계)
- 체결·비용·사이징 상수                : analysis.wave_mm_simulator (STOP_SLIPPAGE_PCT,
                                         COST_ROUNDTRIP_PCT, TRANCHE_PCT, STOP_PCT 폴백)
- 손절 버퍼                            : analysis.wave_mm_struct_stop.BUFFER (0.5%)
- MDD                                  : analysis.wave_mm_simulator.max_drawdown

파라미터는 단일 고정 (관찰 창 20봉, 매도 결합 (a)). 스윕 없음.

실행: `python validation/wave_ma60_turn_probe.py`
산출: validation/REPORT_MA60_TURN_PROBE.md, validation/wave_ma60_turn_probe_trades.csv,
      validation/wave_ma60_turn_probe_candidates.csv
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import random
import sys
import time
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_htf_gate_v2 import WINDOW_MAIN, fetch_window_bare  # noqa: E402
from analysis.wave_mm_simulator import (  # noqa: E402
    COST_ROUNDTRIP_PCT,
    STOP_PCT,
    STOP_SLIPPAGE_PCT,
    TRANCHE_PCT,
    max_drawdown,
)
from analysis.wave_mm_struct_stop import BUFFER  # noqa: E402
from config.settings import MA_PATTERN_PARAMS, STOCH_PIVOT_PARAMS, WAVE_LAYER_ROLES  # noqa: E402
from display.asof import run_indicator_pipeline  # noqa: E402
from indicators.ma_patterns import compute_series_pivots  # noqa: E402

# ---------------------------------------------------------------- 고정 정의
SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")
TFS = ("1h", "4h")
WINDOW = WINDOW_MAIN                     # ("2021-01-01", "2026-09-01")
OBS_BARS = 20                            # 관찰 창 — 사전등록 고정값, 변경 금지
PAD_BARS = 300                           # 지표 워밍업 (MA240 + 스토캐)
LARGE = WAVE_LAYER_ROLES["large"]        # "(20,10,10)"
STOCH_LAG = STOCH_PIVOT_PARAMS["lookback"]   # 2 — 피봇 확정에 필요한 후행 봉 수
MA_LAG = MA_PATTERN_PARAMS["lookback"]       # 3
PARITY_SAMPLES = 12                      # (심볼, TF, 신호종류)당 as-of 재현 표본 (파이프라인 재계산 비용 제약)
PARITY_WINDOW = 600                      # as-of 재계산 시 후행 절단 폭 — V2 STATE_WINDOW_BARS 와 동일
N_WORKERS = 6                            # 셀(심볼×TF) 병렬 실행
SEED = 20260919

REASON_STOP = "STOP"
REASON_STOCH_DT = "STOCH_DT"
REASON_MA10_DT = "MA10_DT"
REASON_BOTH = "BOTH_DT"
REASON_OPEN = "OPEN"

CAND_ENTERED = "ENTERED"
CAND_EXPIRED = "EXPIRED"          # 20봉 내 60MA 전환 없음
CAND_BUSY = "BUSY"                # 전환은 왔으나 보유 중이라 스킵
CAND_NO_MA = "NO_MA60"            # 창 안에 MA60 미산출
CAND_END = "DATA_END"             # 창이 자료 끝을 넘음

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "_ma60_turn_cache")
REPORT_PATH = os.path.join(HERE, "REPORT_MA60_TURN_PROBE.md")
TRADES_PATH = os.path.join(HERE, "wave_ma60_turn_probe_trades.csv")
CANDS_PATH = os.path.join(HERE, "wave_ma60_turn_probe_candidates.csv")


# ---------------------------------------------------------------- 데이터
def load_bars(symbol: str, tf: str) -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"ohlcv_{symbol}_{tf}.csv")
    if os.path.isfile(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index.name = "open_time"
        return df
    bare = fetch_window_bare(symbol, tf, WINDOW[0], WINDOW[1], pad_bars=PAD_BARS)
    bare.to_csv(path)
    return bare


# ---------------------------------------------------------------- 신호 추출
def _last_pos_leq(mask: np.ndarray, c: int) -> Optional[int]:
    idx = np.flatnonzero(mask[: c + 1])
    return int(idx[-1]) if len(idx) else None


def extract_signals(pipe: pd.DataFrame) -> dict:
    """전체 이력 파이프라인 컬럼에서 신호 위치를 뽑고, as-of 가용 시점(known)을 붙인다.

    known = max(확정봉, 두 번째 극점 + 피봇 lookback). 검출기는 피봇 확정에 후행 봉이
    필요하므로 확정봉이 그보다 앞설 수 있다 — 그 차이만큼 신호를 늦게 안 것으로 취급.
    """
    n = len(pipe)
    low = pipe["low"].to_numpy(dtype=float)

    db = pipe[f"stoch_db_{LARGE}"].notna().to_numpy()
    db_first = pipe[f"stoch_db_first_pos_{LARGE}"].astype("Float64").to_numpy(dtype="float64", na_value=np.nan)
    piv_low = pipe[f"stoch_pivot_low_{LARGE}"].notna().to_numpy()
    piv_high = pipe[f"stoch_pivot_high_{LARGE}"].notna().to_numpy()
    dt = pipe[f"stoch_dt_{LARGE}"].notna().to_numpy()

    ma10_dt = pipe["ma10_dt"].notna().to_numpy()
    # 10MA 쌍봉은 -MA10 공간의 피봇저점(=원공간 고점) 상태머신이므로 같은 경로로 두 번째 고점을 복원
    inv_pl, _ = compute_series_pivots(
        -pd.to_numeric(pipe["MA10"], errors="coerce"),
        lookback=MA_PATTERN_PARAMS["lookback"], min_gap=MA_PATTERN_PARAMS["min_gap"],
        rel_tolerance=MA_PATTERN_PARAMS["rel_tolerance"],
    )
    ma10_piv_high = inv_pl.notna().to_numpy()

    cands: List[dict] = []
    for c in np.flatnonzero(db):
        c = int(c)
        p2 = _last_pos_leq(piv_low, c)
        p1 = int(db_first[c]) if np.isfinite(db_first[c]) else None
        if p2 is None or p1 is None or p1 >= p2:
            continue
        known = max(c, p2 + STOCH_LAG)
        cands.append({
            "confirm_pos": c, "known_pos": min(known, n - 1), "lag": known - c,
            "p1": p1, "p2": p2,
            "pattern_low": float(np.nanmin(low[p1:p2 + 1])),
        })

    def _tops(mask: np.ndarray, piv: np.ndarray, lag: int) -> List[dict]:
        out = []
        for c in np.flatnonzero(mask):
            c = int(c)
            p2 = _last_pos_leq(piv, c)
            if p2 is None:
                continue
            known = max(c, p2 + lag)
            out.append({"confirm_pos": c, "known_pos": min(known, n - 1), "lag": known - c})
        return out

    stoch_tops = _tops(dt, piv_high, STOCH_LAG)
    ma10_tops = _tops(ma10_dt, ma10_piv_high, MA_LAG)

    sell_stoch = np.zeros(n, dtype=bool)
    sell_ma10 = np.zeros(n, dtype=bool)
    for s in stoch_tops:
        sell_stoch[s["known_pos"]] = True
    for s in ma10_tops:
        sell_ma10[s["known_pos"]] = True

    ma60 = pd.to_numeric(pipe["MA60"], errors="coerce").to_numpy(dtype=float)
    prev = np.roll(ma60, 1); prev[0] = np.nan
    up = (ma60 > prev) & np.isfinite(ma60) & np.isfinite(prev)
    up_prev = np.roll(up, 1); up_prev[0] = False
    prev2 = np.roll(ma60, 2); prev2[:2] = np.nan
    valid_turn = np.isfinite(prev2) & np.isfinite(prev) & np.isfinite(ma60)
    turn = up & ~up_prev & valid_turn

    return {
        "cands": cands, "stoch_tops": stoch_tops, "ma10_tops": ma10_tops,
        "sell_stoch": sell_stoch, "sell_ma10": sell_ma10,
        "ma60_up": up, "ma60_turn": turn, "ma60_valid": np.isfinite(ma60) & np.isfinite(prev),
    }


# ---------------------------------------------------------------- 시뮬레이션
def simulate(symbol: str, tf: str, bars: pd.DataFrame, sig: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    n = len(bars)
    idx = bars.index
    o = bars["open"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    cl = bars["close"].to_numpy(dtype=float)
    up, turn, ma_valid = sig["ma60_up"], sig["ma60_turn"], sig["ma60_valid"]
    sell_stoch, sell_ma10 = sig["sell_stoch"], sig["sell_ma10"]

    w_start, w_end = pd.Timestamp(WINDOW[0]), pd.Timestamp(WINDOW[1])
    slip = STOP_SLIPPAGE_PCT / 100.0
    cost = COST_ROUNDTRIP_PCT / 100.0
    weight = TRANCHE_PCT / 100.0

    cand_rows, trade_rows = [], []
    exit_pos = -1   # 현재/직전 포지션 청산 봉. 시뮬레이터 규약: 신호봉 < 청산봉 이면 보유 중

    for cd in sorted(sig["cands"], key=lambda d: d["known_pos"]):
        k = cd["known_pos"]
        ts_c = idx[cd["confirm_pos"]]
        if ts_c < w_start or ts_c > w_end:
            continue
        rec = {
            "symbol": symbol, "tf": tf, "confirm_ts": ts_c, "known_ts": idx[k],
            "lag_bars": cd["lag"], "pattern_low": cd["pattern_low"],
            "ma60_up_at_known": bool(up[k]),
        }
        w_hi = k + OBS_BARS
        if w_hi >= n - 1:
            rec.update({"status": CAND_END, "turn_pos_offset": None})
            cand_rows.append(rec)
            continue
        if not ma_valid[k:w_hi + 1].all():
            rec.update({"status": CAND_NO_MA, "turn_pos_offset": None})
            cand_rows.append(rec)
            continue
        hits = np.flatnonzero(turn[k:w_hi + 1])
        if len(hits) == 0:
            rec.update({"status": CAND_EXPIRED, "turn_pos_offset": None})
            cand_rows.append(rec)
            continue
        t = k + int(hits[0])
        rec["turn_pos_offset"] = int(hits[0])
        if t < exit_pos:
            rec["status"] = CAND_BUSY
            cand_rows.append(rec)
            continue
        e = t + 1
        if e >= n:
            rec["status"] = CAND_END
            cand_rows.append(rec)
            continue
        rec["status"] = CAND_ENTERED
        cand_rows.append(rec)

        entry = o[e]
        stop = cd["pattern_low"] * (1.0 - BUFFER)
        stop_kind = "PATTERN_LOW"
        if not (stop < entry):
            stop = entry * (1.0 - STOP_PCT / 100.0)   # SS 규약: 퇴화 시 BASE 폴백
            stop_kind = "FALLBACK_-3%"

        reason, x_pos, x_price = REASON_OPEN, n - 1, cl[n - 1]
        pending = None   # 직전 봉 매도 신호 → 이번 봉 시가 매도
        ma60_down_seen = False
        for j in range(e, n):
            if pending is not None:
                if o[j] <= stop:            # 갭 하락으로 손절선 아래 시가 — 손절 우선
                    reason, x_pos, x_price = REASON_STOP, j, stop * (1.0 - slip)
                else:
                    reason, x_pos, x_price = pending, j, o[j]
                break
            if lo[j] <= stop:
                reason, x_pos, x_price = REASON_STOP, j, stop * (1.0 - slip)
                break
            if not up[j]:
                ma60_down_seen = True
            s1, s2 = bool(sell_stoch[j]), bool(sell_ma10[j])
            if s1 and s2:
                pending = REASON_BOTH
            elif s1:
                pending = REASON_STOCH_DT
            elif s2:
                pending = REASON_MA10_DT
        gross = (x_price - entry) / entry
        net = gross - cost
        trade_rows.append({
            "symbol": symbol, "tf": tf, "year": int(idx[e].year),
            "confirm_ts": ts_c, "known_ts": idx[k], "turn_ts": idx[t],
            "confirm_to_turn_bars": t - k,
            "entry_ts": idx[e], "entry_price": entry,
            "stop_price": stop, "stop_kind": stop_kind,
            "stop_dist_pct": (entry - stop) / entry * 100.0,
            "exit_ts": idx[x_pos], "exit_price": x_price, "exit_reason": reason,
            "bars_held": x_pos - e,
            "ma60_down_before_exit": ma60_down_seen,
            "gross_ret": gross, "net_ret": net,
            "log_growth": float(np.log1p(weight * net)) if reason != REASON_OPEN else np.nan,
        })
        exit_pos = x_pos   # 자료 끝까지 보유(OPEN)면 이후 후보는 BUSY 로 기록된다

    return pd.DataFrame(cand_rows), pd.DataFrame(trade_rows)


# ---------------------------------------------------------------- as-of 재현 점검
def parity_check(bars: pd.DataFrame, sig: dict, rng: random.Random) -> List[dict]:
    """표본 신호를 known 시점까지 절단(후행 1500봉)해 재계산했을 때 같은 확정봉에 신호가 있는가."""
    n = len(bars)
    checks = [
        ("stoch_db", sig["cands"], f"stoch_db_{LARGE}"),
        ("stoch_dt", sig["stoch_tops"], f"stoch_dt_{LARGE}"),
        ("ma10_dt", sig["ma10_tops"], "ma10_dt"),
    ]
    out = []
    for kind, items, col in checks:
        pool = [it for it in items if it["known_pos"] >= PARITY_WINDOW and it["known_pos"] < n]
        sample = rng.sample(pool, min(PARITY_SAMPLES, len(pool)))
        ok = 0
        for it in sample:
            k = it["known_pos"]
            cut = bars.iloc[k + 1 - PARITY_WINDOW: k + 1]
            pipe = run_indicator_pipeline(cut, include_dispersion=False)
            ts = bars.index[it["confirm_pos"]]
            ok += int(ts in pipe.index and pd.notna(pipe.at[ts, col]))
        out.append({"kind": kind, "sampled": len(sample), "reproduced": ok,
                    "rate": (ok / len(sample)) if sample else None})
    return out


# ---------------------------------------------------------------- 집계
def _q(s: pd.Series, q: float) -> float:
    return float(s.quantile(q)) if len(s) else float("nan")


def metrics(tr: pd.DataFrame) -> dict:
    closed = tr[tr["exit_reason"] != REASON_OPEN]
    if closed.empty:
        return {"n": 0}
    net = closed["net_ret"].astype(float)
    wins, losses = net[net > 0], net[net <= 0]
    avg_w = float(wins.mean() * 100) if len(wins) else float("nan")
    avg_l = float(losses.mean() * 100) if len(losses) else float("nan")
    payoff = (avg_w / abs(avg_l)) if (len(wins) and len(losses) and avg_l != 0) else float("nan")
    held = closed["bars_held"]
    reasons = closed["exit_reason"].value_counts()
    return {
        "n": int(len(closed)),
        "win_rate": float((net > 0).mean()),
        "avg_win_pct": avg_w, "avg_loss_pct": avg_l, "payoff": payoff,
        "max_pct": float(net.max() * 100), "min_pct": float(net.min() * 100),
        "held_mean": float(held.mean()), "held_p10": _q(held, .1), "held_p25": _q(held, .25),
        "held_p50": _q(held, .5), "held_p75": _q(held, .75), "held_p90": _q(held, .9),
        "held_max": int(held.max()),
        "n_stop": int(reasons.get(REASON_STOP, 0)),
        "n_stoch_dt": int(reasons.get(REASON_STOCH_DT, 0)),
        "n_ma10_dt": int(reasons.get(REASON_MA10_DT, 0)),
        "n_both": int(reasons.get(REASON_BOTH, 0)),
        "n_open": int((tr["exit_reason"] == REASON_OPEN).sum()),
        "G": float(closed["log_growth"].sum()),
        "mdd": max_drawdown(closed[["exit_ts", "log_growth"]]),
        "ma60_down_before_exit_rate": float(closed["ma60_down_before_exit"].mean()),
        "fallback_stops": int((closed["stop_kind"] != "PATTERN_LOW").sum()),
    }


def _f(x, d=2, suf=""):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{d}f}{suf}"


# ---------------------------------------------------------------- 리포트
HEADER = """# REPORT_MA60_TURN_PROBE — 후보 1(60MA 전환 전략) 탐색적 계측 1회

> 탐색적 계측이며 판정이 아니다. 사전등록 커밋 a01fd41
> (docs/CANDIDATES_POST_2027_03.md, 원격 main) 이후에 수행하는 계측이다.
> BASE 대비 비교·기대값 우위·ACCEPT/REJECT를 산출하지 않는다. 이 수치는
> 후보 1 스펙의 설계 근거(표본 규모·관찰 창 타당성)로만 사용하며, 실제
> 검정은 2027-03 이후 전방 데이터를 포함해 사전등록 스펙으로 수행한다.
> 같은 표본에서 나온 탐색 결과이므로 그 자체로는 전략의 근거가 되지 않는다.
"""


def write_report(cands: pd.DataFrame, trades: pd.DataFrame, parity: Dict[Tuple[str, str], List[dict]],
                 data_meta: Dict[Tuple[str, str], dict], elapsed: float) -> None:
    L = [HEADER]
    L.append(f"실행: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} · 소요 {elapsed/60:.1f}분 · "
             f"재현 `python validation/wave_ma60_turn_probe.py`\n")

    L.append("## 1. 정의 (사전등록 후보 1 그대로, 단일 고정 — 스윕 없음)\n")
    L.append(f"- 모집단: {WINDOW[0]} ~ {WINDOW[1]}, {', '.join(SYMBOLS)}, TF {' / '.join(TFS)} 각각 별도. "
             f"워밍업 {PAD_BARS}봉을 앞에 붙여 받았고 확정봉이 구간 안인 후보만 센다.")
    L.append(f"- 진입 후보: 스토캐 대파동{LARGE} 쌍바닥 확정봉 (앱 검출기 `stoch_db_{LARGE}` 그대로).")
    L.append(f"- 진입 트리거: 후보 가용 시점 k 이후 **[k, k+{OBS_BARS}] 안**에 60MA 전환 "
             "(MA60(t) > MA60(t−1) 이고 직전 봉은 그렇지 않음; MA60(t−2) 필요). 창 안 미전환 시 후보 소멸. "
             "k 시점에 MA60이 이미 상방이면 전환이 아니므로 창 안의 새 전환만 인정한다.")
    L.append("- 진입가: 전환봉 다음 봉 시가. 손절: 패턴 저점(첫 바닥~둘째 바닥 구간 최저가) × "
             f"(1 − {BUFFER}) — SS 라운드 버퍼 승계. 손절선이 진입가 이상이면 SS 규약대로 −{STOP_PCT:.0f}% 폴백(건수 보고).")
    L.append(f"- 청산: 60MA 상태와 무관하게 보유하다가 **대파동 쌍봉(`stoch_dt_{LARGE}`) OR 가격 10MA 쌍봉(`ma10_dt`)** "
             "가용 봉의 다음 봉 시가 매도 (사전등록 (a) 결합). 봉 내 손절선 터치는 손절 우선; "
             "매도 예정 봉 시가가 손절선 이하(갭)면 손절로 처리.")
    L.append(f"- 1포지션(전환봉이 직전 청산봉보다 앞이면 스킵), 사이징 {TRANCHE_PCT:.0f}% 고정, "
             f"왕복 비용 {COST_ROUNDTRIP_PCT}%, 손절 슬리피지 {STOP_SLIPPAGE_PCT}% — 시뮬레이터 상수 승계. "
             f"G = Σ log(1 + {TRANCHE_PCT/100:.2f}·net).")
    L.append("- 자료 끝 미청산 건은 G·승률에서 제외하고 건수·미실현 상태만 §5에 보고.")
    L.append("- **as-of 처리**: 검출기는 피봇 확정에 후행 봉(스토캐 2봉, MA 3봉)이 필요해 확정봉이 실제 가용 "
             "시점보다 앞설 수 있다. 모든 신호(쌍바닥·쌍봉)는 known = max(확정봉, 둘째 극점 + lookback) 봉에 "
             "안 것으로 취급했다. 재현 점검은 §6.\n")

    L.append("## 2. 데이터\n")
    L.append("| 심볼 | TF | 봉 수 | 시작 | 끝 |")
    L.append("|---|---|---|---|---|")
    for (sym, tf), m in data_meta.items():
        L.append(f"| {sym} | {tf} | {m['n']} | {m['start']} | {m['end']} |")
    L.append("")
    short = [(sym, tf, m["start"]) for (sym, tf), m in data_meta.items()
             if pd.Timestamp(m["start"]) > pd.Timestamp(WINDOW[0])]
    if short:
        L.append("워밍업 부족 셀 (페이지네이션 한도로 구간 시작 이전 봉이 부족): "
                 + ", ".join(f"{sym} {tf} 시작 {st}" for sym, tf, st in short)
                 + ". 이 셀은 MA60 이 시작 + 60봉부터 유효하다. 그 이전 구간(약 2~3일)에 후보가 "
                 "있었다면 §3 'MA60 미산출' 행으로 분류된다(0건이면 영향 없음). "
                 "구간 5.7년 대비 무시할 수준이나 기록해 둔다.")
        L.append("")

    for tf in TFS:
        c = cands[cands["tf"] == tf]
        t = trades[trades["tf"] == tf]
        L.append(f"## 3. TF {tf} — 후보 → 진입 전환율 (최우선 항목)\n")
        n_c = len(c)
        st = c["status"].value_counts()
        n_e = int(st.get(CAND_ENTERED, 0))
        n_busy = int(st.get(CAND_BUSY, 0))
        n_turn = n_e + n_busy
        L.append("| 항목 | 건수 | 비율(후보 대비) |")
        L.append("|---|---|---|")
        L.append(f"| 대파동 쌍바닥 후보 | {n_c} | 100% |")
        L.append(f"| ├ 창 안 60MA 전환 발생 (진입+보유중 스킵) | {n_turn} | {_f(n_turn/n_c*100 if n_c else None,1,'%')} |")
        L.append(f"| │ ├ 진입 | {n_e} | {_f(n_e/n_c*100 if n_c else None,1,'%')} |")
        L.append(f"| │ └ 보유 중이라 스킵 | {n_busy} | {_f(n_busy/n_c*100 if n_c else None,1,'%')} |")
        L.append(f"| ├ 창 안 미전환 (소멸) | {int(st.get(CAND_EXPIRED,0))} | {_f(st.get(CAND_EXPIRED,0)/n_c*100 if n_c else None,1,'%')} |")
        L.append(f"| ├ 창이 자료 끝을 넘음 | {int(st.get(CAND_END,0))} | |")
        L.append(f"| └ 창 안 MA60 미산출 | {int(st.get(CAND_NO_MA,0))} | |")
        already = int(c["ma60_up_at_known"].sum())
        L.append(f"| (참고) 후보 가용 시점에 MA60이 이미 상방 | {already} | {_f(already/n_c*100 if n_c else None,1,'%')} |")
        L.append("")
        ent = c[c["status"] == CAND_ENTERED]
        if not ent.empty:
            off = ent["turn_pos_offset"].astype(float)
            L.append(f"- 전환까지 봉 수(진입 건): 평균 {off.mean():.1f}, 중앙 {off.median():.0f}, "
                     f"p90 {off.quantile(.9):.0f}, 0봉(확정봉과 동시) {int((off==0).sum())}건")
            lag = ent["lag_bars"].astype(float)
            L.append(f"- as-of 지연(known − 확정봉, 진입 건): 0봉 {int((lag==0).sum())}건, "
                     f"1봉 {int((lag==1).sum())}건, 2봉 {int((lag==2).sum())}건")
        L.append("")
        L.append("심볼별:\n")
        L.append("| 심볼 | 후보 | 진입 | 전환율(진입/후보) | 보유중 스킵 | 소멸 |")
        L.append("|---|---|---|---|---|---|")
        for sym in SYMBOLS:
            cs = c[c["symbol"] == sym]
            s = cs["status"].value_counts()
            L.append(f"| {sym} | {len(cs)} | {int(s.get(CAND_ENTERED,0))} | "
                     f"{_f(s.get(CAND_ENTERED,0)/len(cs)*100 if len(cs) else None,1,'%')} | "
                     f"{int(s.get(CAND_BUSY,0))} | {int(s.get(CAND_EXPIRED,0))} |")
        L.append("")

        L.append(f"## 4. TF {tf} — 체결 트레이드 (단독 수치, 비교 없음)\n")
        m = metrics(t)
        if m["n"] == 0:
            L.append("체결 트레이드 없음.\n")
            continue
        L.append("| 지표 | 값 |")
        L.append("|---|---|")
        L.append(f"| 청산 완료 트레이드 n | {m['n']} (미청산 {m['n_open']}건 별도) |")
        L.append(f"| 승률 (net > 0) | {_f(m['win_rate']*100,1,'%')} |")
        L.append(f"| 평균 이익 / 평균 손실 (net) | {_f(m['avg_win_pct'],2,'%')} / {_f(m['avg_loss_pct'],2,'%')} |")
        L.append(f"| 손익비 (평균 이익 ÷ \\|평균 손실\\|) | {_f(m['payoff'],2)} |")
        L.append(f"| 최대 / 최소 단일 net | {_f(m['max_pct'],2,'%')} / {_f(m['min_pct'],2,'%')} |")
        L.append(f"| 보유 봉 수 평균 / p10 / p25 / p50 / p75 / p90 / max | {m['held_mean']:.1f} / {m['held_p10']:.0f} / {m['held_p25']:.0f} / "
                 f"{m['held_p50']:.0f} / {m['held_p75']:.0f} / {m['held_p90']:.0f} / {m['held_max']} |")
        L.append(f"| 청산 사유: 손절 / 대파동 쌍봉 / 10MA 쌍봉 / 동시 | {m['n_stop']} / {m['n_stoch_dt']} / {m['n_ma10_dt']} / {m['n_both']} "
                 f"({_f(m['n_stop']/m['n']*100,0,'%')} / {_f(m['n_stoch_dt']/m['n']*100,0,'%')} / "
                 f"{_f(m['n_ma10_dt']/m['n']*100,0,'%')} / {_f(m['n_both']/m['n']*100,0,'%')}) |")
        L.append(f"| 누적 로그 성장률 G (사이징 {TRANCHE_PCT:.0f}%, 비용 차감) | {m['G']:+.4f} |")
        L.append(f"| 최대 드로다운 (로그 자산곡선) | {_f(m['mdd']*100 if m['mdd'] is not None else None,2,'%')} |")
        L.append(f"| 손절선 폴백(−{STOP_PCT:.0f}%) 적용 건 | {m['fallback_stops']} |")
        L.append(f"| (참고) 청산 전 MA60이 한 번이라도 하방이었던 비율 | {_f(m['ma60_down_before_exit_rate']*100,1,'%')} |")
        L.append("")
        d = t[t["exit_reason"] != REASON_OPEN]["stop_dist_pct"]
        L.append(f"- 진입가 대비 손절 거리(%): 중앙 {d.median():.2f}, p25 {d.quantile(.25):.2f}, p75 {d.quantile(.75):.2f}, 최대 {d.max():.2f}")
        L.append("")
        L.append("심볼 × 연도 트레이드 수(청산 완료):\n")
        cl = t[t["exit_reason"] != REASON_OPEN]
        pv = cl.pivot_table(index="symbol", columns="year", values="net_ret", aggfunc="size", fill_value=0)
        years = sorted(cl["year"].unique())
        L.append("| 심볼 | " + " | ".join(str(y) for y in years) + " | 계 |")
        L.append("|---|" + "---|" * (len(years) + 1))
        for sym in SYMBOLS:
            if sym in pv.index:
                row = pv.loc[sym]
                L.append(f"| {sym} | " + " | ".join(str(int(row.get(y, 0))) for y in years) + f" | {int(row.sum())} |")
        L.append("")
        L.append("연도별 승률·손익비:\n")
        L.append("| 연도 | n | 승률 | 평균 이익 | 평균 손실 | 손익비 | G |")
        L.append("|---|---|---|---|---|---|---|")
        for y in years:
            my = metrics(t[t["year"] == y])
            if my["n"] == 0:
                continue
            L.append(f"| {y} | {my['n']} | {_f(my['win_rate']*100,1,'%')} | {_f(my['avg_win_pct'],2,'%')} | "
                     f"{_f(my['avg_loss_pct'],2,'%')} | {_f(my['payoff'],2)} | {my['G']:+.4f} |")
        L.append("")
        L.append("심볼별:\n")
        L.append("| 심볼 | n | 승률 | 손익비 | 보유 p50 | 손절 비율 | G |")
        L.append("|---|---|---|---|---|---|---|")
        for sym in SYMBOLS:
            ms = metrics(t[t["symbol"] == sym])
            if ms["n"] == 0:
                continue
            L.append(f"| {sym} | {ms['n']} | {_f(ms['win_rate']*100,1,'%')} | {_f(ms['payoff'],2)} | "
                     f"{ms['held_p50']:.0f} | {_f(ms['n_stop']/ms['n']*100,0,'%')} | {ms['G']:+.4f} |")
        L.append("")

    L.append("## 5. 미청산 포지션 (자료 끝 시점)\n")
    op = trades[trades["exit_reason"] == REASON_OPEN]
    if op.empty:
        L.append("없음.\n")
    else:
        L.append("| 심볼 | TF | 진입 | 진입가 | 마지막 종가 기준 미실현(gross) | 보유 봉 |")
        L.append("|---|---|---|---|---|---|")
        for r in op.itertuples():
            L.append(f"| {r.symbol} | {r.tf} | {r.entry_ts} | {r.entry_price:.2f} | {r.gross_ret*100:+.2f}% | {r.bars_held} |")
        L.append("")

    L.append("## 6. as-of 재현 점검 (측정 무결성)\n")
    L.append(f"표본 신호를 known 시점까지 절단(후행 {PARITY_WINDOW}봉)해 파이프라인을 다시 돌렸을 때 같은 확정봉에 "
             "신호가 재현되는 비율. 100% 미만이면 (i) 피봇 lookback 을 넘는 후행 의존(min_gap 치환 등) 또는 "
             "(ii) 절단 창 왼쪽 경계의 상태머신 초기화 차이다. 신호 정의는 건드리지 않았다.\n")
    L.append("| 심볼 | TF | 신호 | 표본 | 재현 | 비율 |")
    L.append("|---|---|---|---|---|---|")
    for (sym, tf), rows in parity.items():
        for r in rows:
            L.append(f"| {sym} | {tf} | {r['kind']} | {r['sampled']} | {r['reproduced']} | {_f(r['rate']*100 if r['rate'] is not None else None,1,'%')} |")
    L.append("")

    L.append("## 7. R0 설계 시사점 (표본 규모만)\n")
    for tf in TFS:
        m = metrics(trades[trades["tf"] == tf])
        c = cands[cands["tf"] == tf]
        n_c = len(c)
        rate = (c["status"] == CAND_ENTERED).mean() if n_c else float("nan")
        L.append(f"- **{tf}**: 이 표본(2021-01~2026-09, 3심볼)에서 청산 완료 트레이드 n = {m.get('n',0)} — "
                 f"사전등록 관문 n ≥ 100 을 {'넘는다' if m.get('n',0) >= 100 else '넘지 못한다'}. "
                 f"후보 {n_c}건 중 진입 전환율 {_f(rate*100,1,'%')}. "
                 f"전방 구간에서 같은 비율이 유지된다면 후보 발생률로 기대 n 을 추정할 수 있다.")
    L.append("")
    L.append("이 절은 표본 규모의 관측이며, 전략의 성과·타당성에 대한 판단을 담지 않는다. "
             "후속 변형·파라미터 조정 제안 없음 — 계측은 여기서 멈춘다.\n")

    L.append("## 8. 무접촉 확인\n")
    L.append("- 정의 파일(indicators/·analysis/·config/) 무수정. 신규 파일: 본 스크립트, 본 리포트, 트레이드·후보 CSV, "
             "`validation/_ma60_turn_cache/`(OHLCV, 본 계측 전용 캐시).")
    L.append("- 전방 추적 산출물(watchlist·journal·F2-b 사이드카·MM 섀도)·헌장·INTEGRITY_FILES 미접촉.")
    L.append("- 시도한 파라미터: 관찰 창 20봉, 매도 결합 (a) — 각 1값. 다른 값 시도 없음.")
    L.append("")

    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


# ---------------------------------------------------------------- main
def run_cell(cell: Tuple[str, str]) -> dict:
    """셀(심볼, TF) 하나 — 워커 프로세스에서 실행. 셀별 고정 시드로 재현 가능."""
    sym, tf = cell
    t1 = time.time()
    rng = random.Random(f"{SEED}:{sym}:{tf}")
    bars = load_bars(sym, tf)
    meta = {"n": len(bars), "start": bars.index[0], "end": bars.index[-1]}
    pipe = run_indicator_pipeline(bars, include_dispersion=False)
    sig = extract_signals(pipe)
    c, t = simulate(sym, tf, bars, sig)
    par = parity_check(bars, sig, rng)
    print(f"{sym} {tf}: bars={len(bars)} cands={len(c)} trades={len(t)} "
          f"parity={[(r['kind'], r['reproduced'], r['sampled']) for r in par]} "
          f"({time.time()-t1:.0f}s)", flush=True)
    return {"cell": cell, "cands": c, "trades": t, "parity": par, "meta": meta}


def main() -> None:
    t0 = time.time()
    cells = [(sym, tf) for sym in SYMBOLS for tf in TFS]
    for cell in cells:            # 네트워크 fetch 는 직렬로 (캐시 채우기)
        load_bars(*cell)
    with mp.Pool(min(N_WORKERS, len(cells))) as pool:
        results = pool.map(run_cell, cells)
    results.sort(key=lambda r: cells.index(r["cell"]))
    parity = {r["cell"]: r["parity"] for r in results}
    meta = {r["cell"]: r["meta"] for r in results}
    cands = pd.concat([r["cands"] for r in results], ignore_index=True)
    trades = pd.concat([r["trades"] for r in results], ignore_index=True)
    cands.to_csv(CANDS_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    write_report(cands, trades, parity, meta, time.time() - t0)
    print(f"report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
