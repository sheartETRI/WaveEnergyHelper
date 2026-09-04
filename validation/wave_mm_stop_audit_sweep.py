"""SPEC_WAVE_MM_STOP_AUDIT 실행기 — MM-R0 계측 / MM-R1 손절 규칙 감사.

    python validation/wave_mm_stop_audit_sweep.py --r0   # 시뮬레이터 계측 (판정 없음)
    python validation/wave_mm_stop_audit_sweep.py --r1   # 손절 규칙 판정 1개
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

from analysis.wave_htf_gate_v2 import SYMBOLS_V2, WINDOW_MAIN
from analysis.wave_mm_simulator import (
    CAPITAL_KRW,
    COST_ROUNDTRIP_PCT,
    EXIT_STOP,
    STOP_PCT,
    STOP_SLIPPAGE_PCT,
    TIME_EXIT_BARS,
    TRANCHE_PCT,
    counterfactual_stopped,
    growth,
    load_bars,
    load_gate_events,
    monthly_returns,
    simulate,
    trade_metrics,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRADES_CSV = os.path.join(OUT_DIR, "wave_mm_stop_audit_trades.csv")
SUMMARY_CSV = os.path.join(OUT_DIR, "wave_mm_stop_audit.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_MM_STOP_AUDIT.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_mm_stop_audit.png")

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260904
CI_ALPHA = 0.05
MIN_TRADES = 100

# §5 보조 — 탐색 표시. 판정·권고에 사용 금지.
STOP_CURVE_PCT = (2.0, 3.0, 4.0, 5.0)
ATR_MULT = 2.0

HONESTY = (
    "자금 관리는 엣지를 만들지 못한다. 분포의 형태(성장률·드로다운·노출)를 바꿀 뿐이며, "
    "진입 엣지의 상한은 이전 라운드들이 측정한 그대로다. 본 라운드의 질문은 파산 위험이 "
    "아니라 기회비용이다 (트랜치당 자본 위험 ≈ 0.15% + 비용)."
)


def _fmt(v, d=4):
    if v is None or (isinstance(v, float) and (np.isnan(v))):
        return "—"
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return str(int(v))
    return f"{v:.{d}f}"


def _pct(v, d=2):
    return "—" if v is None else f"{v * 100:.{d}f}%"


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def load_all():
    events = load_gate_events()
    keys = {(s, l) for s, l in zip(events["symbol"], events["ltf"])}
    bars = {k: load_bars(*k) for k in keys}
    missing = [k for k, v in bars.items() if v.empty]
    if missing:
        raise SystemExit(f"OHLCV 캐시 없음: {missing} — load_bars(build=True) 선행 필요")
    return events, bars


# ------------------------------------------------------------ 부트스트랩
def month_cluster_delta_ci(base: pd.DataFrame, nostop: pd.DataFrame,
                           n_boot=BOOTSTRAP_N, seed=BOOTSTRAP_SEED) -> dict:
    """Δ = G(BASE) − G(NOSTOP) 의 월 클러스터 부트스트랩 CI.

    두 시나리오를 **같은 달력 월 블록**으로 짝지어 재표집한다 (달을 뽑고, 그 달의
    양쪽 트레이드를 함께 가져온다). 1포지션 경로 의존 때문에 트레이드 집합이
    다르므로 트레이드 단위 짝짓기는 불가능하다.
    """
    def by_month(tr):
        if tr.empty:
            return {}
        t = tr.copy()
        t["m"] = pd.to_datetime(t["exit_ts"]).dt.to_period("M").astype(str)
        return t.groupby("m")["log_growth"].sum().to_dict()

    b, n = by_month(base), by_month(nostop)
    months = sorted(set(b) | set(n))
    point = (growth(base) or 0.0) - (growth(nostop) or 0.0)
    if not months:
        return {"delta": None, "ci_low": None, "ci_high": None, "n_boot": 0,
                "n_months": 0, "seed": seed}

    rng = np.random.default_rng(seed)
    bv = np.array([b.get(m, 0.0) for m in months])
    nv = np.array([n.get(m, 0.0) for m in months])
    k = len(months)
    deltas = []
    for _ in range(n_boot):
        idx = rng.integers(0, k, k)
        deltas.append(bv[idx].sum() - nv[idx].sum())
    arr = np.asarray(deltas)
    return {
        "delta": round(float(point), 6),
        "ci_low": round(float(np.percentile(arr, CI_ALPHA / 2 * 100)), 6),
        "ci_high": round(float(np.percentile(arr, (1 - CI_ALPHA / 2) * 100)), 6),
        "n_boot": n_boot, "n_months": k, "seed": seed,
    }


def _delta(base: pd.DataFrame, nostop: pd.DataFrame):
    if base.empty and nostop.empty:
        return None
    return round(float((growth(base) or 0.0) - (growth(nostop) or 0.0)), 6)


def half_split_delta(base: pd.DataFrame, nostop: pd.DataFrame) -> list[dict]:
    allt = pd.concat([base, nostop])
    if allt.empty:
        return []
    mid = pd.to_datetime(allt["exit_ts"]).median()
    rows = []
    for name, lo, hi in (("first_half", None, mid), ("second_half", mid, None)):
        def cut(tr):
            if tr.empty:
                return tr
            ts = pd.to_datetime(tr["exit_ts"])
            m = pd.Series(True, index=tr.index)
            if lo is not None:
                m &= ts > lo
            if hi is not None:
                m &= ts <= hi
            return tr[m]
        b, n = cut(base), cut(nostop)
        rows.append({"split": name, "base_trades": len(b), "nostop_trades": len(n),
                     "g_base": growth(b), "g_nostop": growth(n), "delta": _delta(b, n)})
    return rows


def stream_delta(base: pd.DataFrame, nostop: pd.DataFrame) -> list[dict]:
    rows = []
    for ltf in ("1h", "6h"):
        b = base[base["ltf"] == ltf] if not base.empty else base
        n = nostop[nostop["ltf"] == ltf] if not nostop.empty else nostop
        rows.append({"ltf": ltf, "base_trades": len(b), "nostop_trades": len(n),
                     "g_base": growth(b), "g_nostop": growth(n), "delta": _delta(b, n)})
    return rows


def yearly_delta(base: pd.DataFrame, nostop: pd.DataFrame) -> list[dict]:
    rows = []
    years = sorted(set(pd.to_datetime(pd.concat([base, nostop])["exit_ts"]).dt.year))
    for y in years:
        b = base[pd.to_datetime(base["exit_ts"]).dt.year == y]
        n = nostop[pd.to_datetime(nostop["exit_ts"]).dt.year == y]
        rows.append({"year": int(y), "base_trades": len(b), "nostop_trades": len(n),
                     "delta": _delta(b, n)})
    return rows


def judge(base: pd.DataFrame, nostop: pd.DataFrame) -> dict:
    boot = month_cluster_delta_ci(base, nostop)
    halves = half_split_delta(base, nostop)
    streams = stream_delta(base, nostop)
    delta = boot.get("delta")
    sign = np.sign(delta) if delta is not None else 0

    c1 = bool(delta is not None and boot.get("ci_low") is not None
              and (boot["ci_low"] > 0 or boot["ci_high"] < 0))
    c2 = len(base) >= MIN_TRADES and len(nostop) >= MIN_TRADES
    c3 = bool(halves) and all(h["delta"] is not None and np.sign(h["delta"]) == sign
                              for h in halves) and sign != 0
    c4 = bool(streams) and all(s["delta"] is not None and np.sign(s["delta"]) == sign
                               for s in streams) and sign != 0

    criteria = [
        {"id": 1, "text": "Δ ≠ 0 & 월 클러스터 부트스트랩 95% CI가 0 배제", "passed": c1,
         "detail": f"Δ={_fmt(delta, 6)} CI=[{_fmt(boot.get('ci_low'), 6)}, "
                   f"{_fmt(boot.get('ci_high'), 6)}]"},
        {"id": 2, "text": f"체결 트레이드 수 ≥ {MIN_TRADES} (양쪽)", "passed": c2,
         "detail": f"BASE={len(base)}, NOSTOP={len(nostop)}"},
        {"id": 3, "text": "half-split 양쪽에서 Δ 같은 부호", "passed": c3,
         "detail": ", ".join(f"{h['split']}={_fmt(h['delta'], 6)}" for h in halves)},
        {"id": 4, "text": "1h·6h 스트림에서 Δ 같은 부호", "passed": c4,
         "detail": ", ".join(f"{s['ltf']}={_fmt(s['delta'], 6)}" for s in streams)},
    ]
    passed_all = all(c["passed"] for c in criteria)
    if not c2:
        verdict = "판정 불가 (표본 부족)"
    elif passed_all and delta > 0:
        verdict = "손절 유지"
    elif passed_all and delta < 0:
        verdict = "손절 해로움"
    else:
        verdict = "식별 불가"
    return {"verdict": verdict, "criteria": criteria, "bootstrap": boot,
            "halves": halves, "streams": streams}


# ------------------------------------------------------------ §5 보조 곡선
def atr_stop_map(events: pd.DataFrame, mult: float = ATR_MULT) -> dict:
    """신호봉 ATR14 기준 손절 폭 (%). 기존 add_confluence_indicators 재사용."""
    from analysis.wave_confluence import add_confluence_indicators
    from display.asof import run_indicator_pipeline

    out: dict = {}
    for (sym, ltf), grp in events.groupby(["symbol", "ltf"]):
        bars = load_bars(sym, ltf)
        if bars.empty:
            continue
        pipe = add_confluence_indicators(run_indicator_pipeline(bars))
        atr_pct = pipe["atr_pct"]
        for ev in grp.itertuples():
            ts = pd.Timestamp(ev.timestamp)
            if ts in atr_pct.index:
                v = atr_pct.loc[ts]
                if pd.notna(v):
                    out[ev.event_id] = float(v) * mult
    return out


def stop_curve(events, bars) -> list[dict]:
    rows = []
    for pct in STOP_CURVE_PCT:
        tr = simulate(events, bars, stop_pct=pct)
        m = trade_metrics(tr)
        rows.append({"stop": f"{pct:.0f}%", **m})
    amap = atr_stop_map(events)
    if amap:
        tr = simulate(events, bars, stop_pct=amap)
        used = tr["stop_pct_used"].dropna()
        m = trade_metrics(tr)
        rows.append({"stop": f"ATR14×{ATR_MULT:g}", **m,
                     "atr_stop_median_pct": round(float(used.median()), 3) if len(used) else None})
    return rows


# ------------------------------------------------------------------ 리포트
def _plot(base, nostop, result, curve, years) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    ax = axes[0]
    for tr, lab, col in ((base, "BASE (-3% stop)", "#3867F2"), (nostop, "NOSTOP", "#EF5350")):
        if not tr.empty:
            t = tr.sort_values("exit_ts")
            ax.plot(pd.to_datetime(t["exit_ts"]), t["log_growth"].cumsum(), label=lab, color=col)
    ax.axhline(0, color="black", lw=0.8)
    ax.legend(fontsize=8)
    ax.set_title("cumulative log growth")

    ax = axes[1]
    labels = [h["split"] for h in result["halves"]] + [s["ltf"] for s in result["streams"]] + ["pooled"]
    vals = [h["delta"] or 0 for h in result["halves"]] + \
           [s["delta"] or 0 for s in result["streams"]] + [result["bootstrap"].get("delta") or 0]
    ax.bar(labels, vals, color=["#2E7D32" if v > 0 else "#EF5350" for v in vals])
    b = result["bootstrap"]
    if b.get("ci_low") is not None:
        ax.errorbar([len(labels) - 1], [b["delta"]],
                    yerr=[[b["delta"] - b["ci_low"]], [b["ci_high"] - b["delta"]]],
                    fmt="o", color="black", capsize=5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"delta = G(BASE) - G(NOSTOP)   {result['verdict']}")

    ax = axes[2]
    if curve:
        ax.bar([c["stop"] for c in curve], [c.get("growth") or 0 for c in curve], color="#9E9E9E")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("stop width curve G (exploratory, not used)")
    fig.suptitle("WAVE MM STOP AUDIT", fontsize=13)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=110)
    plt.close(fig)
    return PNG_PATH


def write_report(events, base, nostop, result, curve, years, cf, run_r1: bool) -> str:
    bm, nm = trade_metrics(base), trade_metrics(nostop)
    b = result["bootstrap"] if result else {}
    L = ["# REPORT_WAVE_MM_STOP_AUDIT", "",
         f"SPEC_WAVE_MM_STOP_AUDIT — 자금 관리 1라운드. 구간 {WINDOW_MAIN[0]} ~ {WINDOW_MAIN[1]}, "
         f"{', '.join(SYMBOLS_V2)}.", "",
         "## 0. 정직성 조항", "", HONESTY, ""]

    L += ["## 1. 판정 (MM-R1)", ""]
    if not run_r1:
        L += ["MM-R0 단계 — 판정 없음. 계측만 수행했다.", ""]
    else:
        L += [f"**{result['verdict']}**", "",
              "| # | 기준 (§4) | 결과 | 값 |", "|---|---|---|---|"]
        for c in result["criteria"]:
            L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
        L += ["", f"주 비교: Δ = G(BASE) − G(NOSTOP) = **{_fmt(b.get('delta'), 6)}** "
                  f"(월 클러스터 부트스트랩 {b.get('n_boot')}회, 95% CI "
                  f"[{_fmt(b.get('ci_low'), 6)}, {_fmt(b.get('ci_high'), 6)}], "
                  f"월 블록 {b.get('n_months')}개, seed={b.get('seed')})", "",
              "판정 결과는 규칙 권고이지 자동 적용이 아니다. 실운용 반영은 사용자 결정이다.", ""]

    L += ["## 2. 체결 가정 (§2 고정)", "",
          f"- 진입 이벤트 봉 다음 봉 시가 · 시간 청산 신호봉+{TIME_EXIT_BARS}봉 종가",
          f"- 손절 −{STOP_PCT:g}% (평단 기준, 단일 진입 가정) · 체결 슬리피지 {STOP_SLIPPAGE_PCT:g}%",
          f"- 왕복 비용 {COST_ROUNDTRIP_PCT:g}% · 트랜치 {TRANCHE_PCT:g}% · 자본 {CAPITAL_KRW:,}원",
          "- 동시 1포지션, 보유 중 이벤트 건너뜀 · 손절·시간청산 동시 충족 봉은 손절 우선", ""]

    L += ["## 3. MM-R0 계측 (판정 없음)", "",
          f"게이트 통과 이벤트 {len(events)}건 → 1포지션 제약 후 체결 "
          f"{bm.get('trades', 0)}건 (축소율 {1 - bm.get('trades', 0) / max(len(events), 1):.4f})", "",
          "| 지표 | BASE | NOSTOP |", "|---|---|---|"]
    for key, lab, f in (("trades", "체결 트레이드", lambda v: _fmt(v)),
                        ("stop_rate", "손절 발동률", _pct),
                        ("win_rate", "승률", _pct),
                        ("net_mean_pct", "트레이드당 순기대값(%)", lambda v: _fmt(v, 4)),
                        ("growth", "G (로그 성장률 합)", lambda v: _fmt(v, 6)),
                        ("max_drawdown", "최대 드로다운", _pct),
                        ("exposure", "노출률", _pct),
                        ("bars_held_mean", "평균 보유봉", lambda v: _fmt(v, 2))):
        L.append(f"| {lab} | {f(bm.get(key))} | {f(nm.get(key))} |")
    L += ["", "### 손절 트레이드 반사실 추적", ""]
    if cf.get("stopped"):
        L += [f"- 짝지어진 이벤트 {cf['paired']}건 중 BASE 에서 손절된 것 {cf['stopped']}건",
              f"- 그중 손절 없었다면 20봉 시점 순수익이 **양수였을 비율: "
              f"{_pct(cf['would_be_positive_rate'])}** ({cf['would_be_positive']}건)",
              f"- 손절 실현 평균 {_fmt(cf['stopped_net_mean_pct'], 4)}% vs "
              f"반사실 평균 {_fmt(cf['counterfactual_net_mean_pct'], 4)}%",
              "", "왼꼬리 절단(음수 유지)과 승자 조기 청산(양수 전환)의 직접 계측이다."]
    else:
        L.append("손절 트레이드 없음.")
    L.append("")

    if run_r1:
        L += ["## 4. 보조 보고 (판정 미사용)", "", "### 4.1 half-split · 스트림별", "",
              "| 구분 | BASE 트레이드 | NOSTOP 트레이드 | G(BASE) | G(NOSTOP) | Δ |",
              "|---|---|---|---|---|---|"]
        for h in result["halves"]:
            L.append(f"| {h['split']} | {h['base_trades']} | {h['nostop_trades']} | "
                     f"{_fmt(h['g_base'], 6)} | {_fmt(h['g_nostop'], 6)} | {_fmt(h['delta'], 6)} |")
        for s in result["streams"]:
            L.append(f"| {s['ltf']} | {s['base_trades']} | {s['nostop_trades']} | "
                     f"{_fmt(s['g_base'], 6)} | {_fmt(s['g_nostop'], 6)} | {_fmt(s['delta'], 6)} |")
        L += ["", "### 4.2 연도별 Δ", "", "| year | BASE | NOSTOP | Δ |", "|---|---|---|---|"]
        for y in years:
            L.append(f"| {y['year']} | {y['base_trades']} | {y['nostop_trades']} | "
                     f"{_fmt(y['delta'], 6)} |")
        L += ["", "### 4.3 손절 폭 참고 곡선", "",
              "**탐색 표시다. 차기 스펙의 가설 재료일 뿐 이번 판정·권고에 사용하지 않는다.**", "",
              "| 손절 | 트레이드 | 손절률 | G | 최대DD | 순기대값(%) |", "|---|---|---|---|---|---|"]
        for c in curve:
            L.append(f"| {c['stop']} | {c.get('trades')} | {_pct(c.get('stop_rate'))} | "
                     f"{_fmt(c.get('growth'), 6)} | {_pct(c.get('max_drawdown'))} | "
                     f"{_fmt(c.get('net_mean_pct'), 4)} |")
        L.append("")

    L += ["## 5. 한계 (§7)", "",
          "- **단일 진입 가정**: 실제는 고정 기준 없는 재량 하이브리드 분할(물타기·불타기 병용)이다. "
          "특히 평단 기준 손절은 물타기와 결합하면 최초 진입가 대비 실질 손절 폭이 −3%보다 깊어지고 "
          "위험 자본이 트랜치 수만큼 커진다. **본 라운드의 손절 판정은 단일 진입 하에서만 유효하다.**",
          "- **체결 모형의 단순성**: 지정가·부분 체결 없음. 손절은 봉 내 low 도달 시 정확히 "
          "기준가에 체결된다고 가정하며 갭 하락을 반영하지 않는다(슬리피지 고정 0.05%만 가산).",
          "- **1포지션 순차 체결의 경로 의존성**: 어떤 이벤트가 체결되는지가 직전 보유 상태에 "
          "종속되므로, BASE 와 NOSTOP 의 트레이드 집합이 다르다. 트레이드 단위 짝짓기가 불가능해 "
          "부트스트랩을 월 블록으로 짝지었다.",
          "- **표본의 게이트 개방기 편중**: F2-b 개방률이 2021년 최고·2022년 최저였다(ALIGN_GATE §4.2).",
          "- **전방 미검증**: 백테스트 한정이다. §6 전방 추적과 무관하며 실거래 연동은 여전히 금지다.", ""]
    L.append(f"산출물: `{os.path.basename(SUMMARY_CSV)}`, `{os.path.basename(TRADES_CSV)}`, "
             f"`{os.path.basename(PNG_PATH)}`")
    L.append("")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT_PATH


def main() -> None:
    args = sys.argv[1:]
    run_r1 = "--r1" in args
    if not args or not (run_r1 or "--r0" in args):
        raise SystemExit(__doc__)

    events, bars = load_all()
    print(f"[pop] 게이트 통과 이벤트 {len(events)}건")
    base = simulate(events, bars)
    nostop = simulate(events, bars, use_stop=False)
    print(f"[sim] BASE {len(base)} trades / NOSTOP {len(nostop)} trades")
    cf = counterfactual_stopped(base, nostop)

    result = curve = years = None
    if run_r1:
        result = judge(base, nostop)
        curve = stop_curve(events, bars)
        years = yearly_delta(base, nostop)
        print(f"[judge] {result['verdict']} delta={result['bootstrap'].get('delta')} "
              f"CI=[{result['bootstrap'].get('ci_low')}, {result['bootstrap'].get('ci_high')}]")

    base.assign(scenario="BASE").to_csv(TRADES_CSV, index=False)
    rows = [{"section": "metrics", "scenario": "BASE", **trade_metrics(base)},
            {"section": "metrics", "scenario": "NOSTOP", **trade_metrics(nostop)},
            {"section": "counterfactual", **cf}]
    if run_r1:
        rows += [{"section": "criterion", "label": c["text"], "passed": c["passed"],
                  "detail": c["detail"]} for c in result["criteria"]]
        rows += [{"section": "half_split", **h} for h in result["halves"]]
        rows += [{"section": "stream", **s} for s in result["streams"]]
        rows += [{"section": "year", **y} for y in years]
        rows += [{"section": "stop_curve", **c} for c in curve]
        rows.append({"section": "verdict", "label": result["verdict"], **result["bootstrap"]})
        for m in monthly_returns(base).to_dict("records"):
            rows.append({"section": "monthly_base", **m})
        _plot(base, nostop, result, curve, years)
    pd.DataFrame(rows).to_csv(SUMMARY_CSV, index=False)
    path = write_report(events, base, nostop, result, curve, years, cf, run_r1)
    print(f"[report] -> {path}")


if __name__ == "__main__":
    main()
