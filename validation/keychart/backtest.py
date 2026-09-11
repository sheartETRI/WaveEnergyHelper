"""§5 실행 엔트리 — A/B/C1/C2 네 팔을 같은 신호 규칙 위에서 비교한다.

신호 = 대파동 패턴의 **확정**(§6). 확정 봉이 아니라 그 패턴을 '알 수 있게 되는' 봉
(params_v0.PIVOT_STABILITY_LAG 반영)의 마감 시각을 신호 시각 t로 쓰고, 진입가는 그 다음 봉
시가로 한다. 팔은 t 시점에 어느 프레임을 기준 차트로 삼는가만 다르다.

사용법:
  python validation/keychart/backtest.py states       # 프레임 상태 캐시 구축(무거움)
  python validation/keychart/backtest.py run          # 주 분석 + 산출물
  python validation/keychart/backtest.py sens         # §9-5 민감도
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from validation.keychart import arms, data_io  # noqa: E402
from validation.keychart import params_v0 as P  # noqa: E402
from validation.keychart import score as S  # noqa: E402

NS_DAY = 86_400_000_000_000


# --------------------------------------------------------------------- 게이트(벡터)
def gate_vec(st: S.FrameState, pos, db_recent: int, allow_partial: bool):
    """FrameState.gate_at의 벡터판. (통과여부, 방향, 점수, 선택이벤트) 반환.

    스칼라판과 봉 단위로 일치함은 test_no_lookahead.py가 확인한다.
    """
    pos = np.asarray(pos, dtype=np.int64)
    n = len(st)
    ok = (pos >= P.MA_WARMUP_BARS) & (pos < n)
    if st.ev_score.size == 0 or not ok.any():
        z = np.zeros(pos.shape, dtype=np.int64)
        return np.zeros(pos.shape, bool), np.zeros(pos.shape, np.int8), np.zeros(pos.shape), z - 1
    safe = np.where(ok, pos, 0)
    sc = st.struct[safe]
    up = (sc == 3) | (allow_partial & (sc == 2))
    dn = (sc == -3) | (allow_partial & (sc == -2))
    c5 = np.where((sc == 3) | (sc == -3), P.C5_FULL, P.C5_PARTIAL)
    e = np.where(up, st.last_bot[safe], st.last_top[safe]).astype(np.int64)
    ok = ok & (up | dn) & (e >= 0)
    e_safe = np.where(ok, e, 0)
    ok = ok & (st.ev_confirm[e_safe] >= (safe - db_recent))     # G2 최근성
    direction = np.where(up, 1, -1).astype(np.int8)
    val = st.ev_score[e_safe] + 0.2 * c5
    return ok, direction, np.where(ok, val, np.nan), np.where(ok, e, -1)


# --------------------------------------------------------------------- 성과 측정 도구
class Clock:
    """심볼별 벽시계 가격·변동성 척도 (§7.1 / ATR 정규화)."""

    def __init__(self, symbol: str):
        h1 = data_io.load(symbol, "1h")
        self.h_close_ns = data_io.bar_close_times("1h", h1.index).to_numpy(
            "datetime64[ns]").astype("int64")
        self.h_close_px = h1["close"].to_numpy(float)
        d1 = data_io.load(symbol, P.ATR_FRAME)
        self.d_close_ns = data_io.bar_close_times(P.ATR_FRAME, d1.index).to_numpy(
            "datetime64[ns]").astype("int64")
        prev = d1["close"].shift(1)
        tr = pd.concat([(d1["high"] - d1["low"]).abs(),
                        (d1["high"] - prev).abs(),
                        (d1["low"] - prev).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1.0 / P.ATR_PERIOD, adjust=False, min_periods=P.ATR_PERIOD).mean()
        self.d_atr_pct = (atr / d1["close"]).to_numpy(float)

    def mark(self, t_ns: np.ndarray) -> np.ndarray:
        """시각 t의 표시가 = t 이전에 마감된 마지막 1h봉 종가. 데이터 밖이면 NaN."""
        t_ns = np.asarray(t_ns, dtype="int64")
        idx = np.searchsorted(self.h_close_ns, t_ns, side="right") - 1
        px = np.where(idx >= 0, self.h_close_px[np.clip(idx, 0, None)], np.nan)
        stale = t_ns - self.h_close_ns[np.clip(idx, 0, None)]
        bad = (idx < 0) | (t_ns > self.h_close_ns[-1]) | (stale > 2 * NS_DAY)
        return np.where(bad, np.nan, px)

    def atr_pct(self, t_ns: np.ndarray) -> np.ndarray:
        t_ns = np.asarray(t_ns, dtype="int64")
        idx = np.searchsorted(self.d_close_ns, t_ns, side="right") - 1
        val = np.where(idx >= 0, self.d_atr_pct[np.clip(idx, 0, None)], np.nan)
        return np.where(idx < 0, np.nan, val)


# --------------------------------------------------------------------- 후보 신호
def symbol_candidates(symbol: str, states: dict, frames: list, db_recent: int,
                      allow_partial: bool, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """게이트를 통과한 '신선한' 확정 신호 전부(팔 무관). 이후 팔이 이 중에서 채택한다."""
    parts = []
    for f in frames:
        st = states[f]
        if st.events.empty:
            continue
        ks = st.ev_know.astype(np.int64)
        ok, direction, sc, esel = gate_vec(st, ks, db_recent, allow_partial)
        fresh = ok & (esel == np.arange(len(ks)))
        idx = np.flatnonzero(fresh)
        if idx.size == 0:
            continue
        entry_pos = ks[idx] + 1
        keep = entry_pos < len(st)
        idx, entry_pos = idx[keep], entry_pos[keep]
        if idx.size == 0:
            continue
        ev = st.events
        parts.append(pd.DataFrame({
            "symbol": symbol,
            "frame": f,
            "frame_idx": arms.FRAME_INDEX[f],
            "event": idx,
            "kind": ev["kind"].to_numpy()[idx],
            "direction": direction[idx].astype(int),
            "score": sc[idx],
            "c1": ev["c1"].to_numpy()[idx], "c2": ev["c2"].to_numpy()[idx],
            "c3": ev["c3"].to_numpy()[idx], "c4": ev["c4"].to_numpy()[idx],
            "gap": ev["gap"].to_numpy()[idx],
            "confirm_pos": st.ev_confirm[idx],
            "know_pos": ks[idx],
            "t_ns": st.close_ns[ks[idx]],
            # 진입 시각 = 확정(알 수 있게 된) 봉의 마감 = 다음 봉이 열리는 순간.
            # 리샘플 프레임의 index는 라벨(블록 마지막 일봉의 open_time)이라 open_time을
            # 그대로 쓰면 2d/4d/2w에서 시각이 어긋난다.
            "entry_ns": st.close_ns[ks[idx]],
            "entry_px": st.open_px[entry_pos],
        }))
    if not parts:
        return pd.DataFrame()
    cand = pd.concat(parts, ignore_index=True)
    s_ns, e_ns = start.value, end.value
    cand = cand[(cand["entry_ns"] >= s_ns) & (cand["entry_ns"] < e_ns)]
    return cand.sort_values(["t_ns", "frame_idx"]).reset_index(drop=True)


def add_outcomes(cand: pd.DataFrame, clock: Clock) -> pd.DataFrame:
    """§7.1 벽시계 지평별 수익률 + ATR 정규화."""
    entry = cand["entry_ns"].to_numpy("int64")
    px0 = cand["entry_px"].to_numpy(float)
    sign = cand["direction"].to_numpy(float)
    atr = clock.atr_pct(entry)
    cand = cand.copy()
    cand["atr_pct"] = atr
    for name, td in P.HORIZONS.items():
        px1 = clock.mark(entry + int(td.value))
        ret = sign * (px1 / px0 - 1.0)
        cand[f"ret_{name}"] = ret
        cand[f"retn_{name}"] = ret / (atr * np.sqrt(P.HORIZON_DAYS[name]))
    return cand


# --------------------------------------------------------------------- 결정 시점·팔
def decision_table(cand: pd.DataFrame, states: dict, frames: list,
                   db_recent: int, allow_partial: bool):
    """후보가 존재하는 시각별 게이트 통과 집합·점수·B 선택."""
    ts = np.unique(cand["t_ns"].to_numpy("int64"))
    n = len(ts)
    nf = arms.N_FRAMES
    sets = np.full((n, nf), -1, dtype=np.int16)
    scores = np.full((n, nf), np.nan)
    counts = np.zeros(n, dtype=np.int64)
    for f in frames:
        st = states[f]
        pos = np.searchsorted(st.close_ns, ts, side="right") - 1
        ok, _d, sc, _e = gate_vec(st, pos, db_recent, allow_partial)
        rows = np.flatnonzero(ok)
        if rows.size == 0:
            continue
        sets[rows, counts[rows]] = arms.FRAME_INDEX[f]
        scores[rows, counts[rows]] = sc[rows]
        counts[rows] += 1
    # B: 점수 1위(동점은 TIMEFRAMES 순서 앞선 쪽 — sets가 프레임 순서로 채워짐)
    with np.errstate(invalid="ignore"):
        best = np.nanargmax(np.where(np.isnan(scores), -np.inf, scores), axis=1)
    sel_b = np.where(counts > 0, sets[np.arange(n), best], -1).astype(np.int16)
    return ts, sets, counts, scores, sel_b


def accept_masks(cand: pd.DataFrame, ts: np.ndarray, sets: np.ndarray,
                 counts: np.ndarray, sel_b: np.ndarray, seed_base: int):
    """팔별 채택 마스크. C1/C2는 (n_cand, NULL_SEEDS) 불리언."""
    point = np.searchsorted(ts, cand["t_ns"].to_numpy("int64"))
    fidx = cand["frame_idx"].to_numpy(np.int16)
    acc = {
        "A": fidx == arms.select_a(),
        "B": sel_b[point] == fidx,
    }
    d1 = arms.draws_c1(len(ts), P.NULL_SEEDS, seed_base)
    d2 = arms.draws_c2(sets, counts, P.NULL_SEEDS, seed_base)
    acc["C1"] = d1[point] == fidx[:, None]
    acc["C2"] = d2[point] == fidx[:, None]
    return acc, point


# --------------------------------------------------------------------- 집계·통계
def _wmetrics(ret: np.ndarray, retn: np.ndarray, w: np.ndarray,
              years: float, n_seeds: int = 1) -> dict:
    """가중 집계. 팔 A/B는 w=0/1, 귀무 팔은 w=200시드 중 채택 횟수."""
    ok = (~np.isnan(ret)) & (w > 0)
    if not ok.any():
        return {"n": 0.0, "mean_ret": np.nan, "mean_retn": np.nan, "win_rate": np.nan,
                "profit_factor": np.nan, "signals_per_year": 0.0, "ann_sum_ret": np.nan,
                "seed_spread": np.nan}
    r, rn, ww = ret[ok], retn[ok], w[ok].astype(float)
    tot = ww.sum()
    okn = ~np.isnan(rn)
    pos = (ww * np.clip(r, 0, None)).sum()
    neg = (ww * np.clip(-r, 0, None)).sum()
    return {
        "n": float(tot / n_seeds),
        "mean_ret": float((ww * r).sum() / tot),
        "mean_retn": float((ww[okn] * rn[okn]).sum() / ww[okn].sum()) if okn.any() else np.nan,
        "win_rate": float((ww * (r > 0)).sum() / tot),
        "profit_factor": float(pos / neg) if neg > 0 else np.nan,
        "signals_per_year": float(tot / n_seeds / years),
        "ann_sum_ret": float((ww * r).sum() / n_seeds / years),
        "seed_spread": np.nan,
    }


def summarize(cand: pd.DataFrame, acc: dict, years: float) -> pd.DataFrame:
    """팔 × (전체/심볼/프레임) × 지평 집계. §9-3 셀별 표본 수를 그대로 담는다."""
    rows = []
    groups = [("ALL", "ALL", np.ones(len(cand), bool))]
    for sym in sorted(cand["symbol"].unique()):
        groups.append((sym, "ALL", (cand["symbol"] == sym).to_numpy()))
    for fr in sorted(cand["frame"].unique(), key=lambda f: arms.FRAME_INDEX[f]):
        groups.append(("ALL", fr, (cand["frame"] == fr).to_numpy()))
    weights = {}
    for arm in arms.ARMS:
        m = acc[arm]
        weights[arm] = (m.astype(np.int32), 1) if m.ndim == 1 else (m.sum(1).astype(np.int32),
                                                                    m.shape[1])
    for arm in arms.ARMS:
        w_all, n_seeds = weights[arm]
        for sym, fr, gmask in groups:
            for hz in P.HORIZONS:
                ret = cand[f"ret_{hz}"].to_numpy()
                retn = cand[f"retn_{hz}"].to_numpy()
                met = _wmetrics(ret, retn, w_all * gmask, years, n_seeds)
                if sym == "ALL" and fr == "ALL" and acc[arm].ndim == 2:
                    per = []
                    for sd in range(acc[arm].shape[1]):
                        sel = acc[arm][:, sd] & (~np.isnan(retn))
                        per.append(retn[sel].mean() if sel.any() else np.nan)
                    met["seed_spread"] = float(np.nanstd(per))
                rows.append({"arm": arm, "symbol": sym, "frame": fr, "horizon": hz, **met})
    return pd.DataFrame(rows)


def block_bootstrap_diff(values: np.ndarray, mask_b: np.ndarray, mask_c: np.ndarray,
                         blocks: np.ndarray, n_boot: int, seed: int):
    """§7.3 블록 부트스트랩: mean_B - mean_C2 의 분포와 단측 p."""
    ok = ~np.isnan(values)
    uniq = np.unique(blocks[ok])
    if uniq.size == 0:
        return np.array([]), np.nan, np.nan
    sum_b = np.zeros(uniq.size)
    cnt_b = np.zeros(uniq.size)
    sum_c = np.zeros(uniq.size)
    cnt_c = np.zeros(uniq.size)
    mb_all = mask_b if mask_b.ndim == 2 else mask_b[:, None]
    mc_all = mask_c if mask_c.ndim == 2 else mask_c[:, None]
    for i, b in enumerate(uniq):
        inb = ok & (blocks == b)
        v = values[inb]
        mb = mb_all[inb]
        sum_b[i] = (v[:, None] * mb).sum()
        cnt_b[i] = mb.sum()
        mc = mc_all[inb]                                  # (n_in_block, seeds)
        sum_c[i] = (v[:, None] * mc).sum()
        cnt_c[i] = mc.sum()
    obs = (sum_b.sum() / max(cnt_b.sum(), 1)) - (sum_c.sum() / max(cnt_c.sum(), 1))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, uniq.size, size=(n_boot, uniq.size))
    sb = sum_b[pick].sum(1)
    cb = cnt_b[pick].sum(1)
    sc = sum_c[pick].sum(1)
    cc = cnt_c[pick].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        diff = np.where((cb > 0) & (cc > 0), sb / np.maximum(cb, 1) - sc / np.maximum(cc, 1), np.nan)
    good = ~np.isnan(diff)
    p_one = float((diff[good] <= 0).mean()) if good.any() else np.nan
    return diff[good], float(obs), p_one


# --------------------------------------------------------------------- 실행
def run_window(label: str, symbols: list, frames: list, start: pd.Timestamp,
               end: pd.Timestamp, db_recent: int, allow_partial: bool,
               write_ledger: bool = False):
    years = (end - start).days / 365.25
    all_cand, all_acc = [], {a: [] for a in arms.ARMS}
    for si, sym in enumerate(symbols):
        states = {f: S.load_state(sym, f) for f in frames}
        cand = symbol_candidates(sym, states, frames, db_recent, allow_partial, start, end)
        if cand.empty:
            continue
        cand = add_outcomes(cand, Clock(sym))
        ts, sets, counts, scores, sel_b = decision_table(cand, states, frames,
                                                         db_recent, allow_partial)
        acc, point = accept_masks(cand, ts, sets, counts, sel_b, P.SEED_BASE + 1000 * si)
        cand = cand.assign(n_gate=counts[point],
                           sel_b_frame=[arms.FRAMES[i] if i >= 0 else "" for i in sel_b[point]])
        all_cand.append(cand)
        for a in arms.ARMS:
            all_acc[a].append(acc[a])
        del states
    if not all_cand:
        raise SystemExit(f"{label}: 후보 신호 없음")
    cand = pd.concat(all_cand, ignore_index=True)
    acc = {a: (np.concatenate(all_acc[a]) if all_acc[a][0].ndim == 1
               else np.vstack(all_acc[a])) for a in arms.ARMS}

    summary = summarize(cand, acc, years)
    summary.insert(0, "run", label)

    hz = P.PRIMARY_HORIZON
    vals = cand[f"retn_{hz}" if P.PRIMARY_METRIC == "ret_norm" else f"ret_{hz}"].to_numpy()
    blocks = ((cand["entry_ns"].to_numpy("int64") - start.value) //
              (P.BLOCK_DAYS * NS_DAY)).astype(np.int64)

    def arm_mean(mask):
        m = mask if mask.ndim == 2 else mask[:, None]
        tot = (~np.isnan(vals)[:, None] & m).sum()
        if tot == 0:
            return np.nan
        return float(np.nansum(np.where(m, vals[:, None], 0.0)) / tot)

    def compare(other: str) -> dict:
        diff, obs, p_one = block_bootstrap_diff(vals, acc["B"], acc[other], blocks,
                                                P.BOOTSTRAP_N, P.BOOTSTRAP_SEED)
        out = {"vs": other, "obs_diff": obs, "boot_p_one_sided": p_one,
               "boot_ci05": float(np.percentile(diff, 5)) if diff.size else np.nan,
               "boot_ci95": float(np.percentile(diff, 95)) if diff.size else np.nan,
               "other_mean": arm_mean(acc[other]),
               "other_n": float((acc[other] & ~np.isnan(vals)[:, None]).sum() / acc[other].shape[1])
               if acc[other].ndim == 2 else float((acc[other] & ~np.isnan(vals)).sum())}
        if acc[other].ndim == 2:
            sm = np.array([np.nanmean(vals[acc[other][:, s]]) if acc[other][:, s].any() else np.nan
                           for s in range(acc[other].shape[1])])
            out.update({"seed_p05": float(np.nanpercentile(sm, 5)),
                        "seed_p50": float(np.nanpercentile(sm, 50)),
                        "seed_p95": float(np.nanpercentile(sm, 95)),
                        "seeds_beating_B": int(np.nansum(sm >= arm_mean(acc["B"])))})
        return out

    primary = {
        "run": label, "horizon": hz, "metric": P.PRIMARY_METRIC,
        "B_mean": arm_mean(acc["B"]), "B_n": int((acc["B"] & ~np.isnan(vals)).sum()),
        "n_candidates": int(len(cand)), "n_blocks": int(len(np.unique(blocks))),
        "primary_test": compare("C2"),           # §7.4 사전 지정 주 비교
        "secondary": [compare("C1"), compare("A")],   # 탐색적
    }
    if write_ledger:
        ledger = cand.copy()
        ledger["arm_A"] = acc["A"]
        ledger["arm_B"] = acc["B"]
        ledger["c1_accept_seeds"] = acc["C1"].sum(1)
        ledger["c2_accept_seeds"] = acc["C2"].sum(1)
        ledger["t"] = pd.to_datetime(ledger["t_ns"])
        ledger["entry_time"] = pd.to_datetime(ledger["entry_ns"])
        cols = ["symbol", "frame", "kind", "direction", "t", "entry_time", "entry_px",
                "confirm_pos", "know_pos", "score", "c1", "c2", "c3", "c4", "gap",
                "atr_pct", "n_gate", "sel_b_frame", "arm_A", "arm_B",
                "c1_accept_seeds", "c2_accept_seeds"]
        cols += [f"ret_{h}" for h in P.HORIZONS] + [f"retn_{h}" for h in P.HORIZONS]
        ledger[cols].to_csv(os.path.join(HERE, "results_v0_signals.csv"),
                            index=False, float_format="%.6f")
    return cand, acc, summary, primary


def cmd_states(args):
    frames = args.frames or arms.FRAMES
    for sym in args.symbols:
        for f in frames:
            t0 = time.time()
            S.build_state(sym, f, force=args.force)
            print(f"    ({time.time() - t0:.1f}s)", flush=True)


def cmd_run(args):
    frames = arms.FRAMES
    cand, acc, summary, primary = run_window(
        "primary", P.SYMBOLS, frames, P.PRIMARY_START, P.PRIMARY_END,
        P.DB_RECENT_BARS, False, write_ledger=True)

    explore_frames = [f for f in frames
                      if data_io.FRAME_MINUTES[f] >= P.EXPLORE_MIN_FRAME_MINUTES]
    try:
        _c, _a, summary_x, primary_x = run_window(
            "explore_long", P.SYMBOLS, explore_frames, P.EXPLORE_START, P.EXPLORE_END,
            P.DB_RECENT_BARS, False)
    except SystemExit:
        summary_x, primary_x = pd.DataFrame(), None

    out = pd.concat([summary, summary_x], ignore_index=True)
    out.to_csv(os.path.join(HERE, "results_v0_summary.csv"), index=False, float_format="%.6f")
    res = {"primary": primary, "explore_long": primary_x,
           "coverage": coverage_table().to_dict("records")}
    with open(os.path.join(HERE, "results_v0_primary.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2, default=float)
    print(json.dumps(primary, ensure_ascii=False, indent=2, default=float))


def cmd_sens(args):
    rows, prim = [], []
    for db in P.SENSITIVITY_DB_RECENT_BARS:
        _c, _a, s, p = run_window(f"db{db}", P.SYMBOLS, arms.FRAMES, P.PRIMARY_START,
                                  P.PRIMARY_END, db, False)
        rows.append(s)
        prim.append(p)
    _c, _a, s, p = run_window("G1_relaxed_U2D2", P.SYMBOLS, arms.FRAMES, P.PRIMARY_START,
                              P.PRIMARY_END, P.DB_RECENT_BARS, True)
    rows.append(s)
    prim.append(p)
    pd.concat(rows, ignore_index=True).to_csv(
        os.path.join(HERE, "results_v0_sensitivity.csv"), index=False, float_format="%.6f")
    with open(os.path.join(HERE, "results_v0_sensitivity.json"), "w", encoding="utf-8") as fh:
        json.dump(prim, fh, ensure_ascii=False, indent=2, default=float)
    print(json.dumps(prim, ensure_ascii=False, indent=2, default=float))


def coverage_table() -> pd.DataFrame:
    rows = []
    for sym in P.SYMBOLS:
        for f in arms.FRAMES:
            try:
                st = S.load_state(sym, f)
            except FileNotFoundError:
                continue
            rows.append({"symbol": sym, "frame": f, "bars": len(st),
                         "first": str(st.bars["open_time"].iloc[0]),
                         "last": str(st.bars["open_time"].iloc[-1]),
                         "events": len(st.events)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("states")
    sp.add_argument("--symbols", nargs="*", default=P.SYMBOLS)
    sp.add_argument("--frames", nargs="*", default=None)
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_states)
    sp = sub.add_parser("run")
    sp.set_defaults(func=cmd_run)
    sp = sub.add_parser("sens")
    sp.set_defaults(func=cmd_sens)
    sp = sub.add_parser("coverage")
    sp.set_defaults(func=lambda a: print(coverage_table().to_string()))
    a = ap.parse_args()
    a.func(a)
