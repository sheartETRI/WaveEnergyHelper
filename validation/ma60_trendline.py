"""8차 위임 — 일봉 60MA '추세선' 속성 검증 (구조 속성, 시그널/엣지 아님).

검증 명제(김박사): "일봉 60MA는 추세선 역할을 한다."
조작화: ① slope 상태가 우연보다 오래 지속(H-1 지속성), ② 상태별 이후 가격 거동 분리(H-2 분류력),
        ③ 60이 분류력 있는 MA 구간에 속함(H-3 자리).

데이터: BTCUSDT·ETHUSDT 일봉 전체 역사(바이낸스).
정의: MA = SMA(close, p) (엔진 add_moving_averages와 동일). slope = sign(MA[t]−MA[t−N]),
      N=TREND_SLOPE_N. 모든 상태는 봉 마감 확정(as-of), forward 수익은 익일 시가부터(선견 방지).

판정 기준(사전 등록 — 결과 확인 후 변경 금지, 위임 원문):
- H-1: 실측 런 길이 median > 셔플 분포 95퍼센타일 (두 심볼 모두).
- H-2: (상승 mean − 하락 mean) > 0 이고 부트스트랩 95% CI가 0 제외 (두 심볼 모두).
- H-3: MA60 스프레드가 그리드 6개 median 이상(두 심볼 중 ≥1), 나머지 1개는 양수.

★ 매매 시뮬레이션·수익 곡선·필터 탐색 금지. 엔진·검출기·기존 리포트 무수정.
산출물: validation/REPORT_MA60_TRENDLINE.md
실행: `python validation/ma60_trendline.py`
"""
import logging
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import TREND_LAYER_PARAMS  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_MA60_TRENDLINE.md")

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
N = TREND_LAYER_PARAMS["TREND_SLOPE_N"]      # 기법0 스펙 기준값 = 5
FETCH_LIMIT = 5000                            # 일봉 전체 역사 커버(페이지네이션)
FWD_MAIN = 20                                 # forward 주 창(일)
FWD_ADD = [5, 60]                             # 부가 창
GRID = [20, 40, 60, 80, 100, 120]            # H-3 MA 기간 그리드
BLOCK = 20                                    # H-1 블록 셔플 길이
N_SHUFFLE = 1000
N_BOOT = 10000
SEED = 20260708                               # 재현성 고정 시드(리포트 명시)


# ---------------------------------------------------------------- 데이터
def load(symbol):
    bare = fetch_ohlcv_bare(symbol, "1d", FETCH_LIMIT, paginated=True)
    bare = bare[["open", "high", "low", "close"]].astype(float).dropna()
    return bare


def sma(close: np.ndarray, p: int) -> np.ndarray:
    s = pd.Series(close).rolling(window=p).mean().to_numpy()
    return s


def slope_sign(ma: np.ndarray, n: int) -> np.ndarray:
    """sign(MA[t]−MA[t−n]); 정의 불가 구간은 np.nan. 부호만(스펙)."""
    out = np.full(len(ma), np.nan)
    for t in range(n, len(ma)):
        a, b = ma[t], ma[t - n]
        if np.isnan(a) or np.isnan(b):
            continue
        d = a - b
        out[t] = 0.0 if d == 0 else np.sign(d)
    return out


# ---------------------------------------------------------------- A. 지속성
def run_lengths(signs: np.ndarray) -> list:
    """유효(비 NaN) 부호열의 연속 동일부호 런 길이 목록."""
    vals = signs[~np.isnan(signs)]
    if len(vals) == 0:
        return []
    runs = []
    cur = vals[0]
    length = 1
    for v in vals[1:]:
        if v == cur:
            length += 1
        else:
            runs.append(length)
            cur = v
            length = 1
    runs.append(length)
    return runs


def block_shuffle_close(close: np.ndarray, rng) -> np.ndarray:
    """일수익률 블록 셔플(블록=BLOCK)로 재구성한 가격."""
    logp = np.log(close)
    ret = np.diff(logp)                     # 일 로그수익
    nb = len(ret) // BLOCK
    if nb < 2:
        return close.copy()
    trimmed = ret[:nb * BLOCK].reshape(nb, BLOCK)
    order = rng.permutation(nb)
    shuffled = trimmed[order].reshape(-1)
    recon_logp = np.concatenate([[logp[0]], logp[0] + np.cumsum(shuffled)])
    return np.exp(recon_logp)


def h1_persistence(close: np.ndarray, rng):
    obs_runs = run_lengths(slope_sign(sma(close, 60), N))
    obs_median = float(np.median(obs_runs)) if obs_runs else float("nan")
    null_medians = []
    for _ in range(N_SHUFFLE):
        rc = block_shuffle_close(close, rng)
        r = run_lengths(slope_sign(sma(rc, 60), N))
        if r:
            null_medians.append(np.median(r))
    null_medians = np.array(null_medians, dtype=float)
    p95 = float(np.percentile(null_medians, 95))
    return {
        "obs_median": obs_median,
        "obs_n_runs": len(obs_runs),
        "obs_mean_run": float(np.mean(obs_runs)) if obs_runs else float("nan"),
        "obs_max_run": int(np.max(obs_runs)) if obs_runs else 0,
        "null_p95": p95,
        "null_median": float(np.median(null_medians)),
        "pass": obs_median > p95,
    }


# ---------------------------------------------------------------- B/C. 분류력
def regime_forward(bare: pd.DataFrame, period: int, k: int):
    """봉 t의 slope(period) 부호와 forward k일 로그수익(익일 시가→k일 뒤 시가). 선견 방지."""
    close = bare["close"].to_numpy()
    open_ = bare["open"].to_numpy()
    ma = sma(close, period)
    signs = slope_sign(ma, N)
    n = len(close)
    up, down = [], []
    for t in range(n):
        s = signs[t]
        if np.isnan(s) or s == 0.0:
            continue
        e = t + 1            # 익일 시가 진입
        x = e + k            # k일 뒤 시가 청산
        if x > n - 1:
            continue
        fwd = np.log(open_[x] / open_[e])
        (up if s > 0 else down).append(fwd)
    return np.array(up), np.array(down)


def boot_ci_diff(up: np.ndarray, down: np.ndarray, rng, b=N_BOOT):
    """부트스트랩 (up.mean − down.mean) 95% CI."""
    if len(up) == 0 or len(down) == 0:
        return None, None
    diffs = np.empty(b)
    nu, nd = len(up), len(down)
    for i in range(b):
        du = up[rng.integers(0, nu, nu)].mean()
        dd = down[rng.integers(0, nd, nd)].mean()
        diffs[i] = du - dd
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def h2_classification(bare: pd.DataFrame, rng):
    up, down = regime_forward(bare, 60, FWD_MAIN)
    diff = float(up.mean() - down.mean())
    lo, hi = boot_ci_diff(up, down, rng)
    ci_excludes_0 = (lo is not None) and (lo > 0 or hi < 0)
    add = {}
    for k in FWD_ADD:
        u, d = regime_forward(bare, 60, k)
        add[k] = {"n_up": len(u), "n_down": len(d),
                  "mean_diff": float(u.mean() - d.mean()) if len(u) and len(d) else None,
                  "median_diff": float(np.median(u) - np.median(d)) if len(u) and len(d) else None}
    return {
        "n_up": len(up), "n_down": len(down),
        "up_mean": float(up.mean()), "down_mean": float(down.mean()),
        "up_median": float(np.median(up)), "down_median": float(np.median(down)),
        "up_vol": float(up.std(ddof=1)), "down_vol": float(down.std(ddof=1)),
        "mean_diff": diff, "median_diff": float(np.median(up) - np.median(down)),
        "ci_lo": lo, "ci_hi": hi, "ci_excludes_0": ci_excludes_0,
        "pass": diff > 0 and ci_excludes_0,
        "add": add,
    }


def h3_grid(bare: pd.DataFrame):
    spreads = {}
    for p in GRID:
        up, down = regime_forward(bare, p, FWD_MAIN)
        spreads[p] = float(up.mean() - down.mean()) if len(up) and len(down) else float("nan")
    vals = np.array([spreads[p] for p in GRID], dtype=float)
    med = float(np.median(vals))
    ma60 = spreads[60]
    return {"spreads": spreads, "median": med,
            "ma60_ge_median": ma60 >= med, "ma60_positive": ma60 > 0}


# ---------------------------------------------------------------- D. 부가: 평탄 국면
def flat_regime(bare: pd.DataFrame, k=FWD_MAIN, q=0.20):
    """slope 정규화 절대값 하위 q 구간(평탄)의 forward k일 수익·변동성."""
    close = bare["close"].to_numpy()
    open_ = bare["open"].to_numpy()
    ma = sma(close, 60)
    n = len(close)
    recs = []
    for t in range(N, n):
        a, b = ma[t], ma[t - N]
        if np.isnan(a) or np.isnan(b) or b == 0:
            continue
        e, x = t + 1, t + 1 + k
        if x > n - 1:
            continue
        mag = abs(a - b) / abs(b)
        recs.append((mag, np.log(open_[x] / open_[e])))
    if not recs:
        return None
    mags = np.array([r[0] for r in recs])
    fwd = np.array([r[1] for r in recs])
    thr = np.quantile(mags, q)
    flat = fwd[mags <= thr]
    rest = fwd[mags > thr]
    return {"thr": float(thr), "n_flat": len(flat),
            "flat_mean": float(flat.mean()), "flat_vol": float(flat.std(ddof=1)),
            "rest_mean": float(rest.mean()), "rest_vol": float(rest.std(ddof=1))}


# ---------------------------------------------------------------- 실행 + 리포트
def _pct(x, dp=2):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:+.{dp}f}%"


LIMIT_TEXT = (
    "본 결과는 60MA 국면 분류의 통계적 유효성에 대한 것이며, 수수료·진입규칙을 포함한 매매 엣지의 "
    "존재를 의미하지 않는다. PHASE7의 시그널 검증 종료 결정은 본 결과와 무관하게 유효하다."
)


def main():
    data = {}
    for sym in SYMBOLS:
        rng = np.random.default_rng(SEED)     # 심볼마다 동일 시드로 결정론적
        bare = load(sym)
        data[sym] = {
            "bare": bare,
            "period": (bare.index[0], bare.index[-1], len(bare)),
            "h1": h1_persistence(bare["close"].to_numpy(), np.random.default_rng(SEED)),
            "h2": h2_classification(bare, np.random.default_rng(SEED + 1)),
            "h3": h3_grid(bare),
            "flat": flat_regime(bare),
        }

    h1_pass = all(data[s]["h1"]["pass"] for s in SYMBOLS)
    h2_pass = all(data[s]["h2"]["pass"] for s in SYMBOLS)
    # H-3: 두 심볼 중 ≥1이 ma60≥median, 나머지 1개는 양수
    ge = [s for s in SYMBOLS if data[s]["h3"]["ma60_ge_median"]]
    pos = all(data[s]["h3"]["ma60_positive"] for s in SYMBOLS)
    h3_pass = len(ge) >= 1 and pos
    all_pass = h1_pass and h2_pass and h3_pass

    L = [
        "# REPORT_MA60_TRENDLINE — 일봉 60MA '추세선' 속성 검증 (8차 위임)\n",
        "성격: **구조 속성 검증**(시그널/엣지 아님). PHASE7의 시그널 검증 경로 종료 결정은 유효하며,",
        "본 결과가 어떻든 시그널 검증을 자동 재개하지 않는다(재개는 김박사 별도 결정).\n",
        "## 방법",
        f"- 데이터: {', '.join(SYMBOLS)} 일봉 전체 역사(바이낸스). "
        + " · ".join(f"{s}: {data[s]['period'][0]:%Y-%m-%d}~{data[s]['period'][1]:%Y-%m-%d} "
                     f"({data[s]['period'][2]}봉)" for s in SYMBOLS),
        f"- MA = SMA(close, p) (엔진 `add_moving_averages`와 동일). slope = sign(MA[t]−MA[t−N]), "
        f"**N=TREND_SLOPE_N={N}** (기법0 스펙 기준값).",
        "- as-of: 모든 상태는 봉 마감 확정값. **forward 수익은 익일 시가 진입→k일 뒤 시가 청산**(선견 방지).",
        f"- H-1 대조군: 일 로그수익 블록 셔플(블록={BLOCK}일, {N_SHUFFLE}회), 재구성 가격에서 동일 계산.",
        f"- 부트스트랩 {N_BOOT}회. 재현성 고정 시드 SEED={SEED}(numpy default_rng).",
        "",
        "## A. H-1 지속성 (slope60 부호 런 길이)\n",
        "> **판정(사전 등록)**: 실측 런 길이 median이 셔플 분포의 95퍼센타일 초과 (두 심볼 모두) → 통과.\n",
        "| 심볼 | 실측 median | 실측 mean | 실측 max | 런 수 | 셔플 median | 셔플 p95 | 실측>p95 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in SYMBOLS:
        h = data[s]["h1"]
        L.append(f"| {s} | {h['obs_median']:.1f} | {h['obs_mean_run']:.1f} | {h['obs_max_run']} | "
                 f"{h['obs_n_runs']} | {h['null_median']:.1f} | {h['null_p95']:.1f} | "
                 f"{'예' if h['pass'] else '아니오'} |")
    L += [
        "",
        f"- **H-1 판정: {'통과' if h1_pass else '미달'}** "
        f"(두 심볼 모두 실측 median > 셔플 p95: {'예' if h1_pass else '아니오'})",
        "",
        "## B. H-2 분류력 (forward 20일 로그수익)\n",
        "> **판정(사전 등록)**: (상승국면 mean − 하락국면 mean) > 0 이고 부트스트랩 95% CI가 0 제외 "
        "(두 심볼 모두) → 통과.\n",
        "| 심볼 | 상승 n | 하락 n | 상승 mean | 하락 mean | 차(mean) | 95% CI | CI 0제외 | 판정 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in SYMBOLS:
        h = data[s]["h2"]
        ci = f"[{_pct(h['ci_lo'])}, {_pct(h['ci_hi'])}]"
        L.append(f"| {s} | {h['n_up']} | {h['n_down']} | {_pct(h['up_mean'])} | {_pct(h['down_mean'])} | "
                 f"{_pct(h['mean_diff'])} | {ci} | {'예' if h['ci_excludes_0'] else '아니오'} | "
                 f"{'통과' if h['pass'] else '미달'} |")
    L += [
        "",
        f"- **H-2 판정: {'통과' if h2_pass else '미달'}** (두 심볼 모두 차>0 AND CI 0제외)",
        "",
        "부가 기록(판정 아님) — forward 5·60일 mean 차, median 차, 국면별 변동성:",
        "",
        "| 심볼 | fwd5 차 | fwd20 median차 | fwd60 차 | 상승 vol(20d) | 하락 vol(20d) |",
        "|---|---|---|---|---|---|",
    ]
    for s in SYMBOLS:
        h = data[s]["h2"]
        L.append(f"| {s} | {_pct(h['add'][5]['mean_diff'])} | {_pct(h['median_diff'])} | "
                 f"{_pct(h['add'][60]['mean_diff'])} | {_pct(h['up_vol'])} | {_pct(h['down_vol'])} |")

    L += [
        "",
        "## C. H-3 60의 자리 (MA 기간 그리드 스프레드)\n",
        "> **판정(사전 등록)**: MA60의 스프레드(상승−하락 fwd20 mean 차)가 그리드 6개 median 이상 "
        "(두 심볼 중 최소 1개), 나머지 1개는 양수 → 통과. (특권성은 요구하지 않음.)\n",
        "| 심볼 | " + " | ".join(f"MA{p}" for p in GRID) + " | 그리드 median | MA60≥median | MA60>0 |",
        "|---|" + "---|" * (len(GRID) + 3),
    ]
    for s in SYMBOLS:
        h = data[s]["h3"]
        cells = " | ".join(_pct(h["spreads"][p]) for p in GRID)
        L.append(f"| {s} | {cells} | {_pct(h['median'])} | {'예' if h['ma60_ge_median'] else '아니오'} | "
                 f"{'예' if h['ma60_positive'] else '아니오'} |")
    L += [
        "",
        f"- MA60≥median 심볼: {', '.join(ge) if ge else '없음'} · 두 심볼 MA60>0: {'예' if pos else '아니오'}",
        f"- **H-3 판정: {'통과' if h3_pass else '미달'}**",
        "",
        "### 그리드 스프레드 곡선 (fwd20 상승−하락 mean 차, %)",
        "",
        "```",
    ]
    # ASCII 곡선
    all_vals = [data[s]["h3"]["spreads"][p] for s in SYMBOLS for p in GRID]
    vmax = max(abs(v) for v in all_vals if not np.isnan(v)) or 1.0
    for s in SYMBOLS:
        L.append(f"{s}:")
        for p in GRID:
            v = data[s]["h3"]["spreads"][p]
            bar = int(round((v / vmax) * 30)) if not np.isnan(v) else 0
            b = ("█" * bar) if bar >= 0 else ("░" * (-bar))
            mark = "  <-MA60" if p == 60 else ""
            L.append(f"  MA{p:>3} {v*100:+6.2f}% {b}{mark}")
        L.append("")
    L.append("```")

    L += [
        "",
        "## D. 종합 판정과 한계",
        "",
        "| 항목 | 판정 |",
        "|---|---|",
        f"| H-1 지속성 | {'통과' if h1_pass else '미달'} |",
        f"| H-2 분류력 | {'통과' if h2_pass else '미달'} |",
        f"| H-3 60의 자리 | {'통과' if h3_pass else '미달'} |",
        "",
    ]
    if all_pass:
        L += ["**A·B·C 전부 통과 → '일봉 60MA는 추세 상태의 유효한 분류자' 확정.**", ""]
    else:
        fails = [name for name, ok in
                 [("H-1", h1_pass), ("H-2", h2_pass), ("H-3", h3_pass)] if not ok]
        L += [f"**미달 항목: {', '.join(fails)}.** 통과 항목은 통과대로, 미달 항목은 미달대로 그대로 보고"
              "(각색 없음). 전부 통과가 아니므로 '유효한 분류자' 확정은 성립하지 않는다.", ""]

    L += [
        "### 한계 명시 (원문)",
        "",
        f"> {LIMIT_TEXT}",
        "",
        "## 부가 기록 (판정 아님)\n",
        "### 평탄 국면 (slope 정규화 절대값 하위 20%) forward 20일 — 김박사 횡보 가설 관측용",
        "",
        "| 심볼 | 평탄 임계(|slope|) | 평탄 n | 평탄 mean | 평탄 vol | 그 외 mean | 그 외 vol |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in SYMBOLS:
        f = data[s]["flat"]
        if f is None:
            L.append(f"| {s} | — | 0 | — | — | — | — |")
            continue
        L.append(f"| {s} | {f['thr']*100:.3f}% | {f['n_flat']} | {_pct(f['flat_mean'])} | "
                 f"{_pct(f['flat_vol'])} | {_pct(f['rest_mean'])} | {_pct(f['rest_vol'])} |")

    L += [
        "",
        "## 미결 · 캐비엇\n",
        "- **forward 창 중첩**: 인접 t의 forward 20일 창이 겹쳐 표본이 독립이 아니다(자기상관). 사전 등록",
        "  부트스트랩은 iid 가정이라 H-2 CI는 실제보다 좁을 수 있음(과신 위험) — 판정 기준 원문 유지, 캐비엇만 기록.",
        "- **H-1 방향 해석(중요)**: 실측 런 median이 셔플 p95보다 **낮게** 나왔다(예상과 반대). 블록 셔플은",
        "  일수익 **총드리프트를 보존**(순서만 섞음)하므로 대조군은 '동일 드리프트 랜덤워크'가 되고, 그 MA60",
        "  기울기는 드리프트 탓에 매우 오래 한 방향을 유지한다. 반면 실측 가격은 강세·약세 사이클(2018/2021/",
        "  2022 등)로 기울기가 더 자주 뒤집힌다 → 실측 런이 더 짧다. 즉 이 사전 등록 검정은 '동일 드리프트",
        "  랜덤워크보다 더 지속적인가'를 물으며, 사이클을 가진 실물 추세자산은 이를 통과하기 구조적으로 어렵다.",
        "  (판정 기준 원문 유지 — 미달로 보고. 해석 캐비엇만 기록.)",
        "- 두 심볼 상관(BTC·ETH 동조)으로 '두 심볼 모두' 조건은 완전 독립 반복이 아님(공통 시장요인) — 기록만.",
        "- MA=SMA·N=" + str(N) + " 고정. 다른 MA 종류(EMA)·N 민감도는 스코프 밖(탐색 금지).",
        "",
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"H-1 pass={h1_pass}  H-2 pass={h2_pass}  H-3 pass={h3_pass}  ALL={all_pass}")
    for s in SYMBOLS:
        h1, h2, h3 = data[s]["h1"], data[s]["h2"], data[s]["h3"]
        print(f"  {s}: run_med={h1['obs_median']:.1f}>p95={h1['null_p95']:.1f}={h1['pass']} | "
              f"h2_diff={h2['mean_diff']:.4f} CI=[{h2['ci_lo']:.4f},{h2['ci_hi']:.4f}] {h2['pass']} | "
              f"ma60_spread={h3['spreads'][60]:.4f} median={h3['median']:.4f}")
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
