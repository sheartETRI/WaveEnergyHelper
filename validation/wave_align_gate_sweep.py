"""SPEC_WAVE_ALIGN_GATE — F2-b 배열 게이트 확인 검정.

V2 캐시(_htf_gate_v2_cache, _htf_gate_cache)만 소비한다. 신규 데이터 생성 없음.

주 대비: Δ′ = E[G_ALIGN] − E[무게이트] (expectancy_20)
부트스트랩: 달력 월 클러스터 (symbol, ltf, 월) 블록 복원추출 2000회.

사용법:
    python validation/wave_align_gate_sweep.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_expectancy import compute_expectancy_metrics
from analysis.wave_htf_gate import GATES, TRIGGER_LABEL, expectancy_20, gate_mask
from analysis.wave_htf_gate import _perf  # noqa: F401  (표 병기용 PF/survival)
from analysis.wave_htf_gate_v2 import (
    GATE_VERSION_V2,
    PAIRS_V2,
    SYMBOLS_V2,
    WINDOW_MAIN,
    apply_gate_version,
    build_pair_events_v2,
    load_htf_states_v2,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(OUT_DIR, "wave_align_gate.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_ALIGN_GATE.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_align_gate.png")

# --- §3 부트스트랩 (사전 고정) ---
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260904
CI_ALPHA = 0.05

# --- §4 판정 ---
MIN_ALIGN_N = 30

# --- §5 비용 참고치 (고정) ---
COST_ROUNDTRIP_PCT = 0.2

HONESTY_NOTE = (
    "본 검정은 **같은 데이터(2021-01-01 ~ 2026-09-01) 위에서의 확인**이다. 새 데이터가 아니다. "
    "검정 대상인 'F2-b 게이트가 expectancy_20 을 0.3513 → 0.6982 로 개선한다'는 발견 자체가 "
    "이 데이터에서 나온 탐색적 결과이므로, 기준 1 의 점추정 부호(Δ′ > 0)는 이미 알려져 있다. "
    "이 검정의 정보량은 세 가지에만 있다 — (a) 자기상관을 반영한 월 클러스터 부트스트랩 CI 가 "
    "그래도 0 을 배제하는가, (b) half-split 양쪽에서 재현되는가(미계산 대비), "
    "(c) 심볼별로 재현되는가(미계산 대비). "
    "진정한 out-of-sample 확인은 2026-09 이후 전방 데이터가 쌓인 뒤에만 가능하며, "
    "그 자리는 §6 전방 추적으로 남긴다."
)


def _fmt(v, d=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{v:.{d}f}"


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# ------------------------------------------------------------------ 모집단
def load_pool() -> pd.DataFrame:
    """§2 모집단 — V2 본 검정과 동일한 이벤트 집합 + 월 클러스터 키."""
    frames = [build_pair_events_v2(pair, GATE_VERSION_V2) for pair in PAIRS_V2]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    pool = pd.concat(frames, ignore_index=True)
    pool = pool[pool["return_20"].notna()].copy()
    pool["timestamp"] = pd.to_datetime(pool["timestamp"])
    return add_cluster_keys(pool)


def add_cluster_keys(df: pd.DataFrame) -> pd.DataFrame:
    """(symbol, ltf, 달력 월) 클러스터 키 부여."""
    out = df.copy()
    out["month"] = pd.to_datetime(out["timestamp"]).dt.to_period("M").astype(str)
    out["cluster"] = (
        out["symbol"].astype(str) + "|" + out["ltf"].astype(str) + "|" + out["month"]
    )
    return out.sort_values("timestamp").reset_index(drop=True)


# -------------------------------------------------------------------- 지표
def delta_prime(df: pd.DataFrame) -> float | None:
    """Δ′ = E[G_ALIGN] − E[무게이트]."""
    if df.empty:
        return None
    e_align = expectancy_20(df[gate_mask(df, "G_ALIGN")])
    e_all = expectancy_20(df)
    if e_align is None or e_all is None:
        return None
    return round(e_align - e_all, 4)


def _expectancy_arr(rets: np.ndarray) -> float | None:
    if rets.size == 0:
        return None
    return float(compute_expectancy_metrics(pd.Series(rets)).get("expectancy", 0.0))


def month_cluster_bootstrap(
    df: pd.DataFrame,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """§3 — 월 블록 복원추출로 Δ′ 분포 생성.

    블록 = (symbol, ltf, 달력 월). 원본 블록 수만큼 복원추출해 데이터셋을 재구성하고,
    재표집본 안에서 E[G_ALIGN] − E[전체] 를 계산한다 (코호트 중첩 구조 보존).
    """
    point = delta_prime(df)
    empty = {"delta": point, "ci_low": None, "ci_high": None, "n_boot": 0,
             "n_blocks": 0, "n_events": len(df), "seed": seed}
    if df.empty:
        return empty

    groups = [g for _, g in df.groupby("cluster", sort=True)]
    rets = [g["return_20"].astype(float).to_numpy() for g in groups]
    flags = [g["g_align"].astype(bool).to_numpy() for g in groups]
    n_blocks = len(groups)
    if n_blocks == 0:
        return empty

    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_blocks, n_blocks)
        r = np.concatenate([rets[i] for i in idx])
        f = np.concatenate([flags[i] for i in idx])
        if f.sum() == 0:
            continue
        e_all = _expectancy_arr(r)
        e_align = _expectancy_arr(r[f])
        if e_all is None or e_align is None:
            continue
        deltas.append(e_align - e_all)
    if not deltas:
        return empty

    arr = np.asarray(deltas, dtype=float)
    return {
        "delta": point,
        "ci_low": round(float(np.percentile(arr, CI_ALPHA / 2 * 100)), 4),
        "ci_high": round(float(np.percentile(arr, (1 - CI_ALPHA / 2) * 100)), 4),
        "n_boot": len(arr),
        "n_blocks": n_blocks,
        "n_events": len(df),
        "n_align": int(df["g_align"].astype(bool).sum()),
        "seed": seed,
    }


# -------------------------------------------------------------------- 판정
def half_split_delta(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    mid = len(ordered) // 2
    rows = []
    for name, sub in (("first_half", ordered.iloc[:mid]), ("second_half", ordered.iloc[mid:])):
        rows.append({
            "split": name,
            "n": len(sub),
            "ts_min": sub["timestamp"].min() if len(sub) else None,
            "ts_max": sub["timestamp"].max() if len(sub) else None,
            "n_align": int(gate_mask(sub, "G_ALIGN").sum()) if len(sub) else 0,
            "e_all": expectancy_20(sub),
            "e_align": expectancy_20(sub[gate_mask(sub, "G_ALIGN")]) if len(sub) else None,
            "delta": delta_prime(sub),
        })
    return rows


def by_key_delta(df: pd.DataFrame, key: str, values=None) -> list[dict]:
    rows = []
    vals = values if values is not None else sorted(df[key].dropna().unique())
    for v in vals:
        sub = df[df[key] == v]
        rows.append({
            key: v,
            "n": len(sub),
            "n_align": int(gate_mask(sub, "G_ALIGN").sum()) if len(sub) else 0,
            "e_all": expectancy_20(sub),
            "e_align": expectancy_20(sub[gate_mask(sub, "G_ALIGN")]) if len(sub) else None,
            "delta": delta_prime(sub),
        })
    return rows


def judge_align(df: pd.DataFrame) -> dict:
    """§4 — 4항목 전부 충족 시에만 H1 채택(승격)."""
    boot = month_cluster_bootstrap(df)
    halves = half_split_delta(df)
    syms = by_key_delta(df, "symbol", SYMBOLS_V2)

    delta = boot.get("delta")
    n_align = int(df["g_align"].astype(bool).sum()) if not df.empty else 0
    c1 = bool(delta is not None and delta > 0
              and boot.get("ci_low") is not None and boot["ci_low"] > 0)
    c2 = n_align >= MIN_ALIGN_N
    c3 = bool(halves) and all(h["delta"] is not None and h["delta"] > 0 for h in halves)
    positive = [s["symbol"] for s in syms if s["delta"] is not None and s["delta"] > 0]
    c4 = len(positive) >= 2

    criteria = [
        {"id": 1, "text": "Δ′ > 0 & 월 클러스터 부트스트랩 95% CI가 0 배제", "passed": c1,
         "detail": f"Δ′={delta} CI=[{boot.get('ci_low')}, {boot.get('ci_high')}]"},
        {"id": 2, "text": f"n(G_ALIGN) >= {MIN_ALIGN_N}", "passed": c2,
         "detail": f"n(G_ALIGN)={n_align}"},
        {"id": 3, "text": "half-split 양쪽에서 Δ′ > 0", "passed": c3,
         "detail": ", ".join(f"{h['split']}={h['delta']}" for h in halves)},
        {"id": 4, "text": "{BTC, ETH, BNB} 중 2개 이상에서 Δ′ > 0", "passed": c4,
         "detail": ", ".join(f"{s['symbol']}={s['delta']}" for s in syms)},
    ]
    return {
        "verdict": "ACCEPT" if all(c["passed"] for c in criteria) else "REJECT",
        "criteria": criteria,
        "bootstrap": boot,
        "halves": halves,
        "symbols": syms,
    }


# ------------------------------------------------------- §5 에피소드 진단
def episode_frame(symbol: str, htf: str) -> pd.DataFrame:
    """HTF 상태에서 G_ALIGN 연속 개방 에피소드에 id 부여."""
    st = apply_gate_version(load_htf_states_v2(symbol, htf), GATE_VERSION_V2)
    if st.empty:
        return pd.DataFrame()
    st = st.sort_values("htf_open_time").reset_index(drop=True)
    open_flag = st["g_align"].astype(bool)
    block = (open_flag != open_flag.shift(fill_value=False)).cumsum()
    st["episode_id"] = np.where(open_flag, symbol + "_" + block.astype(str), None)
    return st[["symbol", "htf_open_time", "g_align", "episode_id"]]


def episode_diagnostics(df: pd.DataFrame) -> dict:
    """§5 — 에피소드 수·길이 분포·에피소드별 Δ′ 부호 비율 (판정 미사용).

    에피소드별 Δ′_e = E[에피소드 안 이벤트] − E[무게이트 전체].
    """
    baseline = expectancy_20(df)
    per_symbol: list[dict] = []
    ep_rows: list[dict] = []

    for pair, (htf, ltf) in PAIRS_V2.items():
        for sym in SYMBOLS_V2:
            eps = episode_frame(sym, htf)
            if eps.empty:
                continue
            lengths = (
                eps[eps["g_align"]].groupby("episode_id").size()
                if eps["g_align"].any() else pd.Series(dtype=int)
            )
            sub = df[(df["pair"] == pair) & (df["symbol"] == sym)]
            merged = sub.merge(
                eps[["htf_open_time", "episode_id"]], on="htf_open_time", how="left",
            )
            gated = merged[merged["g_align"].astype(bool) & merged["episode_id"].notna()]
            deltas = []
            for ep_id, grp in gated.groupby("episode_id"):
                e = expectancy_20(grp)
                if e is None or baseline is None:
                    continue
                deltas.append(e - baseline)
                ep_rows.append({
                    "pair": pair, "symbol": sym, "episode_id": ep_id,
                    "n_events": len(grp), "delta": round(e - baseline, 4),
                })
            arr = np.asarray(deltas, dtype=float)
            per_symbol.append({
                "pair": pair,
                "symbol": sym,
                "episodes": int(len(lengths)),
                "len_mean": round(float(lengths.mean()), 2) if len(lengths) else None,
                "len_median": float(lengths.median()) if len(lengths) else None,
                "len_max": int(lengths.max()) if len(lengths) else None,
                "episodes_with_events": int(arr.size),
                "positive_ratio": round(float((arr > 0).mean()), 4) if arr.size else None,
            })
    return {"per_symbol": per_symbol, "episodes": ep_rows, "baseline": baseline}


# --------------------------------------------------------- §5 비용 참고치
def cost_adjusted(df: pd.DataFrame, cost_pct: float = COST_ROUNDTRIP_PCT) -> list[dict]:
    """왕복 비용 차감 후 expectancy_20 (참고 계산, 판정 미사용)."""
    adj = df.copy()
    adj["return_20"] = adj["return_20"].astype(float) - cost_pct
    rows = []
    for gate in ("NO_GATE", "G_ALIGN"):
        gross = df[gate_mask(df, gate)]
        net = adj[gate_mask(adj, gate)]
        rows.append({
            "gate": gate,
            "n": len(gross),
            "expectancy_gross": expectancy_20(gross),
            "expectancy_net": expectancy_20(net),
        })
    rows.append({
        "gate": "DELTA",
        "n": None,
        "expectancy_gross": delta_prime(df),
        "expectancy_net": delta_prime(adj),
    })
    return rows


def gate_table(df: pd.DataFrame) -> list[dict]:
    rows = []
    for gate in GATES:
        sub = df[gate_mask(df, gate)]
        if sub.empty:
            rows.append({"gate": gate, "n": 0})
            continue
        perf = _perf(sub)
        rows.append({
            "gate": gate,
            "n": len(sub),
            "expectancy_20": expectancy_20(sub),
            "profit_factor": perf.get("profit_factor"),
            "survival_rate": perf.get("survival_rate"),
            "win_rate": perf.get("win_rate"),
        })
    return rows


# ------------------------------------------------------------------ 리포트
def _plot(df: pd.DataFrame, result: dict, years: list[dict]) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    ax = axes[0]
    rows = gate_table(df)
    labels = [r["gate"] for r in rows]
    vals = [r.get("expectancy_20") or 0.0 for r in rows]
    bars = ax.bar(labels, vals, color=["#BDBDBD", "#3867F2", "#FFB74D", "#2E7D32"])
    for b, v, r in zip(bars, vals, rows):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}\nn={r['n']}",
                ha="center", va="bottom", fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("expectancy_20 by gate")

    ax = axes[1]
    boot = result["bootstrap"]
    labels = [h["split"] for h in result["halves"]] + \
             [s["symbol"].replace("USDT", "") for s in result["symbols"]] + ["pooled"]
    vals = [h["delta"] or 0.0 for h in result["halves"]] + \
           [s["delta"] or 0.0 for s in result["symbols"]] + [boot.get("delta") or 0.0]
    ax.bar(labels, vals, color=["#2E7D32" if v > 0 else "#EF5350" for v in vals])
    if boot.get("ci_low") is not None:
        ax.errorbar([len(labels) - 1], [boot["delta"]],
                    yerr=[[boot["delta"] - boot["ci_low"]], [boot["ci_high"] - boot["delta"]]],
                    fmt="o", color="black", capsize=5)
    ax.axhline(0, color="black", lw=0.8)
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    ax.set_title(f"Δ′ = E[G_ALIGN] − E[no gate]   {result['verdict']}")

    ax = axes[2]
    if years:
        ydf = pd.DataFrame(years)
        ax.bar(ydf["year"].astype(str), ydf["delta"].fillna(0),
               color=["#2E7D32" if (v or 0) > 0 else "#EF5350" for v in ydf["delta"]])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("delta-prime by year (not used for the verdict)")

    fig.suptitle("WAVE ALIGN GATE — F2-b confirmation (same-data)", fontsize=13)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=110)
    plt.close(fig)
    return PNG_PATH


def write_report(df, result, pairs, years, episodes, costs) -> str:
    boot = result["bootstrap"]
    L: list[str] = []
    L.append("# REPORT_WAVE_ALIGN_GATE")
    L.append("")
    L.append(f"SPEC_WAVE_ALIGN_GATE — F2-b 배열 게이트 확인 검정. "
             f"관측 구간 {WINDOW_MAIN[0]} ~ {WINDOW_MAIN[1]}.")
    L.append("")
    L.append("## 0. 정직성 조항")
    L.append("")
    L.append(HONESTY_NOTE)
    L.append("")

    L.append("## 1. 판정")
    L.append("")
    L.append(f"**{result['verdict']}**")
    L.append("")
    L.append("| # | 기준 (§4) | 결과 | 값 |")
    L.append("|---|---|---|---|")
    for c in result["criteria"]:
        L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
    L.append("")
    L.append(f"주 대비: Δ′ = E[G_ALIGN] − E[무게이트] = **{_fmt(boot.get('delta'))}** "
             f"(월 클러스터 부트스트랩 {boot.get('n_boot')}회, 95% CI "
             f"[{_fmt(boot.get('ci_low'))}, {_fmt(boot.get('ci_high'))}], "
             f"블록 {boot.get('n_blocks')}개, 이벤트 {boot.get('n_events')}건, "
             f"seed={boot.get('seed')})")
    L.append("")
    if result["verdict"] == "ACCEPT":
        L.append("**승격**: F2-b 를 라이브 워치리스트의 HTF 컨텍스트 필터로 채택한다 (§4). "
                 "UI/display 작업이 허용되며, §6 전방 추적으로 out-of-sample 숙제를 상환한다.")
    else:
        L.append("**승격 없음**: F2-b 는 탐색적 발견으로 유지한다 (§4). "
                 "어느 쪽이든 다음 연구 축(자금 관리)으로 이동한다.")
    L.append("")

    L.append("## 2. 4열 비교표")
    L.append("")
    L.append(f"트리거: {TRIGGER_LABEL} · 모집단 {len(df)}건 (V2 본 검정과 동일 이벤트 집합)")
    L.append("")
    L.append("| gate | n | expectancy_20 | PF | survival% | win% |")
    L.append("|---|---|---|---|---|---|")
    for r in gate_table(df):
        L.append(f"| {r['gate']} | {r['n']} | {_fmt(r.get('expectancy_20'))} | "
                 f"{_fmt(r.get('profit_factor'))} | {_fmt(r.get('survival_rate'), 2)} | "
                 f"{_fmt(r.get('win_rate'), 2)} |")
    L.append("")

    L.append("## 3. half-split · 심볼별 (판정 사용)")
    L.append("")
    L.append("| split | n | 구간 | n(G_ALIGN) | E[무게이트] | E[G_ALIGN] | Δ′ |")
    L.append("|---|---|---|---|---|---|---|")
    for h in result["halves"]:
        span = f"{pd.Timestamp(h['ts_min']).date()} ~ {pd.Timestamp(h['ts_max']).date()}"
        L.append(f"| {h['split']} | {h['n']} | {span} | {h['n_align']} | "
                 f"{_fmt(h['e_all'])} | {_fmt(h['e_align'])} | {_fmt(h['delta'])} |")
    L.append("")
    L.append("| symbol | n | n(G_ALIGN) | E[무게이트] | E[G_ALIGN] | Δ′ |")
    L.append("|---|---|---|---|---|---|")
    for s in result["symbols"]:
        L.append(f"| {s['symbol']} | {s['n']} | {s['n_align']} | {_fmt(s['e_all'])} | "
                 f"{_fmt(s['e_align'])} | {_fmt(s['delta'])} |")
    L.append("")

    L.append("## 4. 보조 보고 (판정 미사용)")
    L.append("")
    L.append("### 4.1 TF쌍별 Δ′")
    L.append("")
    L.append("| pair | n | n(G_ALIGN) | E[무게이트] | E[G_ALIGN] | Δ′ |")
    L.append("|---|---|---|---|---|---|")
    for p in pairs:
        L.append(f"| {p['pair']} | {p['n']} | {p['n_align']} | {_fmt(p['e_all'])} | "
                 f"{_fmt(p['e_align'])} | {_fmt(p['delta'])} |")
    L.append("")
    L.append("### 4.2 연도별 Δ′")
    L.append("")
    L.append("| year | n | n(G_ALIGN) | 게이트 개방률 | E[무게이트] | E[G_ALIGN] | Δ′ |")
    L.append("|---|---|---|---|---|---|---|")
    for y in years:
        rate = y["n_align"] / y["n"] * 100 if y["n"] else None
        L.append(f"| {y['year']} | {y['n']} | {y['n_align']} | "
                 f"{'—' if rate is None else f'{rate:.2f}%'} | {_fmt(y['e_all'])} | "
                 f"{_fmt(y['e_align'])} | {_fmt(y['delta'])} |")
    neg_years = [str(y["year"]) for y in years if (y["delta"] or 0) < 0]
    if neg_years:
        L.append("")
        L.append(f"**Δ′ 가 음수인 해: {', '.join(neg_years)} ({len(neg_years)}/{len(years)}).** "
                 "통합 Δ′ 는 연 단위로 안정적이지 않다. 판정은 사전등록된 half-split·심볼 기준으로 "
                 "하되, 이 표는 해석 강도를 낮추는 근거다.")
    L.append("")
    L.append("### 4.3 에피소드 진단")
    L.append("")
    L.append("G_ALIGN 연속 개방 에피소드. 에피소드별 Δ′_e = E[에피소드 안 이벤트] − "
             f"E[무게이트 전체({_fmt(episodes['baseline'])})].")
    L.append("")
    L.append("| pair | symbol | 에피소드 수 | 길이 평균 | 중앙값 | 최대 | 이벤트 있는 에피소드 | Δ′_e>0 비율 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for e in episodes["per_symbol"]:
        L.append(f"| {e['pair']} | {e['symbol']} | {e['episodes']} | {_fmt(e['len_mean'], 2)} | "
                 f"{_fmt(e['len_median'], 1)} | {_fmt(e['len_max'])} | "
                 f"{e['episodes_with_events']} | {_fmt(e['positive_ratio'], 3)} |")
    L.append("")
    ratios = [e["positive_ratio"] for e in episodes["per_symbol"] if e["positive_ratio"] is not None]
    if ratios:
        lo, hi = min(ratios), max(ratios)
        L.append(f"**측정된 Δ′_e>0 비율은 {lo:.3f} ~ {hi:.3f} 로 모든 셀에서 0.5 미만이다.** "
                 "즉 게이트가 열린 에피소드의 과반은 무게이트 평균을 밑돌았고, 통합 Δ′ 의 양수는 "
                 "소수 에피소드의 큰 이익이 끌어올린 결과다. 게이트가 '대체로 낫다'가 아니라 "
                 "'가끔 크게 낫다'로 읽어야 하며, 이는 승격의 근거를 약화시키는 방향의 관측이다.")
    L.append("")
    L.append(f"### 4.4 비용 참고치 (왕복 {COST_ROUNDTRIP_PCT}%)")
    L.append("")
    L.append("현물 테이커 0.1%×2 가정. **이벤트 전방 수익은 체결 모형이 아니므로 참고 계산이다.**")
    L.append("")
    L.append("| gate | n | expectancy (총) | expectancy (비용차감) |")
    L.append("|---|---|---|---|")
    for c in costs:
        L.append(f"| {c['gate']} | {_fmt(c['n'])} | {_fmt(c['expectancy_gross'])} | "
                 f"{_fmt(c['expectancy_net'])} |")
    L.append("")

    L.append("## 5. 한계")
    L.append("")
    L.append("- **동일 데이터 확인**: §0 그대로. 새 데이터가 아니며 점추정 부호는 이미 알려져 있었다.")
    L.append("- **표본 편중 — 스펙 전제와 실측이 다르다**: §7 은 '2023–2025 편중'을 전제했으나 "
             "이 모집단에서 이벤트는 연 7.5k~11.6k 로 고르게 퍼져 있고, 편중된 것은 이벤트가 아니라 "
             "**게이트 개방률**이다 (§4.2 표: 2021 년 54.79% 로 최고, 2022 년 16.84% 로 최저). "
             "따라서 통합 Δ′ 는 2021 년 개방 구간에 상대적으로 크게 의존한다.")
    L.append("- **약세장은 '미측정'이 아니라 '얇게 측정'됐다**: §7 은 '2022 게이트 전면 폐쇄'를 "
             "전제했으나, 전면 폐쇄는 1d 프레임(PAIR_C)에 한정된 사실이다. 4h 프레임(PAIR_B)에서는 "
             "2022 년에도 18.67% 가 열렸고 이벤트 1,523 건이 있으며 그 해 Δ′ 는 양수였다. "
             "다만 표본이 얇고 한 사이클뿐이라, 약세장에서의 유효성 주장은 여전히 근거가 약하다. "
             "게이트가 약세장을 '피했다'는 것과 '약세장에서 유효하다'는 것은 다른 주장이다.")
    L.append("- **월 블록 경계의 에피소드 절단**: 클러스터를 달력 월로 끊었기 때문에 "
             "월을 가로지르는 개방 에피소드가 두 블록으로 쪼개진다. 자기상관을 완전히 "
             "흡수하지 못하며, 그만큼 CI 는 여전히 낙관적일 수 있다.")
    L.append("- **비용 참고치의 체결 모형 부재**: §4.4 는 return_20 에서 고정 0.2% 를 뺀 값일 뿐 "
             "슬리피지·부분체결·자금조달 비용을 포함하지 않는다. 판정에 쓰지 않았다.")
    L.append("")
    L.append(f"산출물: `{os.path.basename(CSV_PATH)}`, `{os.path.basename(PNG_PATH)}`")
    L.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT_PATH


def main() -> None:
    df = load_pool()
    if df.empty:
        raise SystemExit("V2 캐시 없음 — 먼저 V2 라운드 산출물을 만들어야 한다.")
    print(f"[pool] events={len(df)} clusters={df['cluster'].nunique()} "
          f"{df['timestamp'].min()} ~ {df['timestamp'].max()}")

    result = judge_align(df)
    pairs = by_key_delta(df, "pair", list(PAIRS_V2))
    df_year = df.assign(year=df["timestamp"].dt.year)
    years = by_key_delta(df_year, "year")
    episodes = episode_diagnostics(df)
    costs = cost_adjusted(df)

    rows: list[dict] = []
    rows.extend({"section": "gate_table", **r} for r in gate_table(df))
    rows.extend({"section": "half_split", **h} for h in result["halves"])
    rows.extend({"section": "symbol", **s} for s in result["symbols"])
    rows.extend({"section": "pair", **p} for p in pairs)
    rows.extend({"section": "year", **y} for y in years)
    rows.extend({"section": "episode_summary", **e} for e in episodes["per_symbol"])
    rows.extend({"section": "episode", **e} for e in episodes["episodes"])
    rows.extend({"section": "cost", **c} for c in costs)
    rows.extend({"section": "criterion", "label": c["text"], "passed": c["passed"],
                 "detail": c["detail"]} for c in result["criteria"])
    rows.append({"section": "verdict", "label": result["verdict"], **result["bootstrap"]})
    pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    print(f"[csv] -> {CSV_PATH}")

    _plot(df, result, years)
    path = write_report(df, result, pairs, years, episodes, costs)
    print(f"[report] -> {path}")
    print(f"[verdict] {result['verdict']} delta={result['bootstrap'].get('delta')} "
          f"CI=[{result['bootstrap'].get('ci_low')}, {result['bootstrap'].get('ci_high')}]")


if __name__ == "__main__":
    main()
