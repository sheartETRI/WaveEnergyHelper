"""SPEC_WAVE_MM_STRUCT_STOP 실행기 — SS-R0 관문 / SS-R1 판정.

    python validation/wave_mm_struct_stop_sweep.py --r0
    python validation/wave_mm_struct_stop_sweep.py --r1
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
    STOP_PCT,
    counterfactual_stopped,
    growth,
    load_bars,
    load_gate_events,
    simulate,
    trade_metrics,
)
from analysis.wave_mm_struct_stop import (
    BUFFER,
    DETECT_MIN,
    DIVERGE_MIN,
    DIVERGE_PP,
    REASON_DEGENERATE,
    REASON_NO_LOW,
    detection_gate,
    mechanism,
    struct_stop_map,
    struct_stops,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_CSV = os.path.join(OUT_DIR, "wave_mm_struct_stop.csv")
STOPS_CSV = os.path.join(OUT_DIR, "wave_mm_struct_stop_events.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_MM_STRUCT_STOP.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_mm_struct_stop.png")

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260904
CI_ALPHA = 0.05
MIN_TRADES = 100

HONESTY = (
    "이 가설은 **같은 표본의 진단에서 동기를 얻었다**. MM §5 폭 곡선에서 값을 고른 것은 "
    "아니지만(곡선은 % 손절 계열, 본 가설은 다른 계열), 같은 데이터 위의 검정이라는 한계는 "
    "남는다. 확인의 최종 수단은 전방 섀도 추적이며, 본 라운드의 ACCEPT 효력은 "
    "**섀도 추적 대상 승격까지**다. 실규칙 교체 권고는 전방 데이터 이후로 유보한다."
)


def _fmt(v, d=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return str(int(v))
    return f"{v:.{d}f}"


def _pct(v, d=2):
    return "—" if v is None else f"{v * 100:.{d}f}%"


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def month_cluster_delta_ci(a: pd.DataFrame, b: pd.DataFrame,
                           n_boot=BOOTSTRAP_N, seed=BOOTSTRAP_SEED) -> dict:
    """Δ = G(a) − G(b) 의 월 클러스터 부트스트랩 (MM-R1 과 동일 방식)."""
    def by_month(tr):
        if tr.empty:
            return {}
        t = tr.copy()
        t["m"] = pd.to_datetime(t["exit_ts"]).dt.to_period("M").astype(str)
        return t.groupby("m")["log_growth"].sum().to_dict()

    ma, mb = by_month(a), by_month(b)
    months = sorted(set(ma) | set(mb))
    point = (growth(a) or 0.0) - (growth(b) or 0.0)
    if not months:
        return {"delta": None, "ci_low": None, "ci_high": None, "n_boot": 0,
                "n_months": 0, "seed": seed}
    rng = np.random.default_rng(seed)
    av = np.array([ma.get(m, 0.0) for m in months])
    bv = np.array([mb.get(m, 0.0) for m in months])
    k = len(months)
    vals = [av[i].sum() - bv[i].sum()
            for i in (rng.integers(0, k, k) for _ in range(n_boot))]
    arr = np.asarray(vals)
    return {"delta": round(float(point), 6),
            "ci_low": round(float(np.percentile(arr, CI_ALPHA / 2 * 100)), 6),
            "ci_high": round(float(np.percentile(arr, (1 - CI_ALPHA / 2) * 100)), 6),
            "n_boot": n_boot, "n_months": k, "seed": seed}


def _delta(a, b):
    if a.empty and b.empty:
        return None
    return round(float((growth(a) or 0.0) - (growth(b) or 0.0)), 6)


def half_split(a, b):
    allt = pd.concat([a, b])
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
        x, y = cut(a), cut(b)
        rows.append({"split": name, "struct_trades": len(x), "base_trades": len(y),
                     "g_struct": growth(x), "g_base": growth(y), "delta": _delta(x, y)})
    return rows


def stream_split(a, b):
    rows = []
    for ltf in ("1h", "6h"):
        x = a[a["ltf"] == ltf] if not a.empty else a
        y = b[b["ltf"] == ltf] if not b.empty else b
        rows.append({"ltf": ltf, "struct_trades": len(x), "base_trades": len(y),
                     "g_struct": growth(x), "g_base": growth(y), "delta": _delta(x, y)})
    return rows


def yearly(a, b):
    rows = []
    allt = pd.concat([a, b])
    if allt.empty:
        return rows
    for y in sorted(set(pd.to_datetime(allt["exit_ts"]).dt.year)):
        x = a[pd.to_datetime(a["exit_ts"]).dt.year == y]
        z = b[pd.to_datetime(b["exit_ts"]).dt.year == y]
        rows.append({"year": int(y), "struct_trades": len(x), "base_trades": len(z),
                     "delta": _delta(x, z)})
    return rows


def judge(struct, base, streams, halves):
    boot = month_cluster_delta_ci(struct, base)
    delta = boot.get("delta")
    sign = np.sign(delta) if delta is not None else 0
    c1 = bool(delta is not None and boot.get("ci_low") is not None
              and (boot["ci_low"] > 0 or boot["ci_high"] < 0))
    c2 = len(struct) >= MIN_TRADES and len(base) >= MIN_TRADES
    c3 = bool(halves) and sign != 0 and all(
        h["delta"] is not None and np.sign(h["delta"]) == sign for h in halves)
    c4 = bool(streams) and sign != 0 and all(
        s["delta"] is not None and np.sign(s["delta"]) == sign for s in streams)
    criteria = [
        {"id": 1, "text": "Δ ≠ 0 & 월 클러스터 부트스트랩 95% CI가 0 배제", "passed": c1,
         "detail": f"Δ={_fmt(delta, 6)} CI=[{_fmt(boot.get('ci_low'), 6)}, "
                   f"{_fmt(boot.get('ci_high'), 6)}]"},
        {"id": 2, "text": f"트레이드 ≥ {MIN_TRADES} (양쪽)", "passed": c2,
         "detail": f"STRUCT={len(struct)}, BASE={len(base)}"},
        {"id": 3, "text": "half-split 양쪽 같은 부호", "passed": c3,
         "detail": ", ".join(f"{h['split']}={_fmt(h['delta'], 6)}" for h in halves)},
        {"id": 4, "text": "1h·6h 스트림 같은 부호", "passed": c4,
         "detail": ", ".join(f"{s['ltf']}={_fmt(s['delta'], 6)}" for s in streams)},
    ]
    ok = all(c["passed"] for c in criteria)
    if not c2:
        verdict = "판정 불가 (표본 부족)"
    elif ok and delta > 0:
        verdict = "STRUCT 우위 — 섀도 추적 승격"
    elif ok and delta < 0:
        verdict = "STRUCT 열위"
    else:
        verdict = "식별 불가"
    return {"verdict": verdict, "criteria": criteria, "bootstrap": boot,
            "halves": halves, "streams": streams}


def _plot(struct, base, nostop, result, gate, stops):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    ax = axes[0]
    for tr, lab, col in ((base, "BASE -3%", "#3867F2"), (struct, "STRUCT", "#2E7D32"),
                         (nostop, "NOSTOP", "#EF5350")):
        if not tr.empty:
            t = tr.sort_values("exit_ts")
            ax.plot(pd.to_datetime(t["exit_ts"]), t["log_growth"].cumsum(), label=lab, color=col)
    ax.axhline(0, color="black", lw=0.8)
    ax.legend(fontsize=8)
    ax.set_title("cumulative log growth")

    ax = axes[1]
    labels = [h["split"] for h in result["halves"]] + \
             [s["ltf"] for s in result["streams"]] + ["pooled"]
    vals = [h["delta"] or 0 for h in result["halves"]] + \
           [s["delta"] or 0 for s in result["streams"]] + [result["bootstrap"].get("delta") or 0]
    ax.bar(labels, vals, color=["#2E7D32" if v > 0 else "#EF5350" for v in vals])
    b = result["bootstrap"]
    if b.get("ci_low") is not None:
        ax.errorbar([len(labels) - 1], [b["delta"]],
                    yerr=[[b["delta"] - b["ci_low"]], [b["ci_high"] - b["delta"]]],
                    fmt="o", color="black", capsize=5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"delta = G(STRUCT) - G(BASE)   {result['verdict']}")

    ax = axes[2]
    d = stops.loc[stops["applied_struct"].fillna(False).astype(bool), "struct_pct"]
    if len(d):
        ax.hist(d.clip(upper=30), bins=40, color="#9E9E9E")
    ax.axvline(STOP_PCT, color="black", ls="--", lw=1, label="-3% base")
    ax.legend(fontsize=8)
    ax.set_title("structural stop distance (% from entry)")
    fig.suptitle("WAVE MM STRUCT STOP", fontsize=13)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=110)
    plt.close(fig)


def write_report(events, stops, gate, struct, base, nostop, result,
                 mech, base_mech, years, run_r1):
    sm, bm = trade_metrics(struct), trade_metrics(base)
    b = result["bootstrap"] if result else {}
    L = ["# REPORT_WAVE_MM_STRUCT_STOP", "",
         f"SPEC_WAVE_MM_STRUCT_STOP — 자금 관리 3라운드. 구간 {WINDOW_MAIN[0]} ~ "
         f"{WINDOW_MAIN[1]}, {', '.join(SYMBOLS_V2)}.", "",
         "## 0. 정직성 조항", "", HONESTY, ""]

    L += ["## 1. 판정", ""]
    if not run_r1:
        L += [f"**SS-R0 {'GO' if gate['go'] else 'NO-GO'}** — 판정 없음 (관문 단계).", ""]
        if not gate["go"]:
            L += ["기록: **이 모집단에서 구조 손절은 고정 −3% 와 구별될 만큼 다른 손절선을 "
                  "만들지 않음.**", ""]
    else:
        L += [f"**{result['verdict']}**", "",
              "| # | 기준 (§3) | 결과 | 값 |", "|---|---|---|---|"]
        for c in result["criteria"]:
            L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
        L += ["", f"주 비교: Δ = G(STRUCT) − G(BASE) = **{_fmt(b.get('delta'), 6)}** "
                  f"(월 클러스터 부트스트랩 {b.get('n_boot')}회, 95% CI "
                  f"[{_fmt(b.get('ci_low'), 6)}, {_fmt(b.get('ci_high'), 6)}], "
                  f"월 {b.get('n_months')}개, seed={b.get('seed')})", "",
              "ACCEPT 의 효력은 섀도 추적의 주 감시 대상 지정이다. "
              "실규칙 교체 권고는 전방 데이터 이후로 유보한다 (§3).", ""]

    L += ["## 2. 고정 정의 (§1)", "",
          f"- reference_low = 신호봉 기준 확정된 마지막 swing low "
          f"(find_swing_lows + _confirmed, PIVOT 상속, 신규 검출기 없음)",
          f"- 손절선 = reference_low × (1 − {BUFFER:.3f}) — 버퍼 {BUFFER * 100:.1f}% 고정",
          f"- 미검출·퇴화(손절선 ≥ 진입가)는 BASE(−{STOP_PCT:g}%) 적용",
          "- 시뮬레이터·체결·비용·1포지션·20봉 청산·사이징 5% 고정: MM/SZ 라운드와 동일", ""]

    L += ["## 3. SS-R0 — 검정력 관문", "",
          f"체결 트레이드 {gate['n']}건 기준.", "",
          "| 항목 | 값 | 조건 | 충족 |", "|---|---|---|---|",
          f"| reference_low 검출률 | {_pct(gate['detect_rate'])} | ≥ {DETECT_MIN:.0%} | "
          f"{_mark(gate['cond_detect'])} |",
          f"| −3% 와 {DIVERGE_PP:g}%p 초과 이격 비율 | {_pct(gate['diverge_share'])} | "
          f"≥ {DIVERGE_MIN:.0%} | {_mark(gate['cond_diverge'])} |", "",
          f"구조 손절 거리(진입가 대비 %): P25 {_fmt(gate['dist_p25'], 3)} · "
          f"중앙값 {_fmt(gate['dist_p50'], 3)} · P75 {_fmt(gate['dist_p75'], 3)} · "
          f"평균 {_fmt(gate['dist_mean'], 3)} (최소 {_fmt(gate['dist_min'], 3)} / "
          f"최대 {_fmt(gate['dist_max'], 3)})", "",
          f"구조 손절 적용 {gate['applied_struct']}건 · 미검출 {gate['no_reference_low']}건 · "
          f"퇴화 {gate['degenerate']}건", "",
          f"**관문 판정: {'GO' if gate['go'] else 'NO-GO'}**", ""]

    if run_r1:
        L += ["## 4. 시나리오 비교", "", "| 지표 | BASE −3% | STRUCT | NOSTOP |",
              "|---|---|---|---|"]
        nm = trade_metrics(nostop)
        for key, lab, f in (("trades", "체결 트레이드", lambda v: _fmt(v)),
                            ("stop_rate", "손절 발동률", _pct),
                            ("win_rate", "승률", _pct),
                            ("net_mean_pct", "트레이드당 순기대값(%)", lambda v: _fmt(v, 4)),
                            ("growth", "G", lambda v: _fmt(v, 6)),
                            ("max_drawdown", "최대 드로다운", _pct),
                            ("exposure", "노출률", _pct),
                            ("bars_held_mean", "평균 보유봉", lambda v: _fmt(v, 2))):
            L.append(f"| {lab} | {f(bm.get(key))} | {f(sm.get(key))} | {f(nm.get(key))} |")
        L.append("")

        L += ["## 5. 보조 보고 (판정 미사용)", "",
              "### 5.1 메커니즘 재계측 — '되돌림 직전 매도'가 줄었는가", "",
              "| 구성 | 손절 건수 | 실현 평균(%) | 20봉 반사실 평균(%) | 격차(%p) | 반사실 양수 비율 |",
              "|---|---|---|---|---|---|"]
        for lab, m in (("BASE −3% (MM-R1 재계산)", base_mech), ("STRUCT", mech)):
            if m.get("stopped"):
                L.append(f"| {lab} | {m['stopped']} | {_fmt(m.get('realized_mean_pct') or m.get('stopped_net_mean_pct'), 4)} | "
                         f"{_fmt(m.get('counterfactual_mean_pct') or m.get('counterfactual_net_mean_pct'), 4)} | "
                         f"{_fmt(m.get('gap_pp'), 4)} | {_pct(m.get('would_be_positive_rate'))} |")
            else:
                L.append(f"| {lab} | 0 | — | — | — | — |")
        L += ["", "격차가 0 에 가까울수록 '되돌림 직전 매도'가 줄었다는 뜻이다. "
              "MM-R1 의 BASE 격차는 −0.4677%p 였다.", "",
              "### 5.2 G(STRUCT) vs G(NOSTOP)", "",
              f"- G(STRUCT) = {_fmt(growth(struct), 6)} · G(NOSTOP) = {_fmt(growth(nostop), 6)} "
              f"· 차이 {_fmt(_delta(struct, nostop), 6)}",
              "- 참고: MM-R0 에서 G(NOSTOP) = 0.1227. NOSTOP 은 판정에 쓰지 않는다 (§5).", "",
              "### 5.3 half-split · 스트림별", "",
              "| 구분 | STRUCT | BASE | G(STRUCT) | G(BASE) | Δ |", "|---|---|---|---|---|---|"]
        for h in result["halves"]:
            L.append(f"| {h['split']} | {h['struct_trades']} | {h['base_trades']} | "
                     f"{_fmt(h['g_struct'], 6)} | {_fmt(h['g_base'], 6)} | {_fmt(h['delta'], 6)} |")
        for s in result["streams"]:
            L.append(f"| {s['ltf']} | {s['struct_trades']} | {s['base_trades']} | "
                     f"{_fmt(s['g_struct'], 6)} | {_fmt(s['g_base'], 6)} | {_fmt(s['delta'], 6)} |")
        L += ["", "### 5.4 연도별 Δ", "", "| year | STRUCT | BASE | Δ |", "|---|---|---|---|"]
        for y in years:
            L.append(f"| {y['year']} | {y['struct_trades']} | {y['base_trades']} | "
                     f"{_fmt(y['delta'], 6)} |")
        L += ["", "### 5.5 퇴화·미검출 케이스", "",
              f"- 미검출(reference_low 없음): {int((stops['reason'] == REASON_NO_LOW).sum())}건",
              f"- 퇴화(손절선 ≥ 진입가): {int((stops['reason'] == REASON_DEGENERATE).sum())}건",
              "- 두 경우 모두 BASE(−3%)로 떨어졌다. 이벤트 목록은 "
              f"`{os.path.basename(STOPS_CSV)}` 의 reason 컬럼 참조.", ""]

    L += ["## 6. 한계 (§6)", "",
          "- **같은 표본 동기 가설**: §0 그대로. 전방 검증은 섀도 추적으로만 가능하다.",
          "- **단일 진입 가정**: 실규칙은 재량 하이브리드 분할이다.",
          "- **swing 검출기 파라미터 상속**: PIVOT 등 기존 값을 그대로 썼고 최적성을 주장하지 않는다.",
          f"- **버퍼 {BUFFER * 100:.1f}% 의 사전 선택성**: SZ-R0 실측 atrp 중앙값의 절반이라는 "
          "근거로 사전 고정했으나, 대안 값을 탐색하지 않았으므로 최적성은 알 수 없다.",
          "- **갭 미반영**: 손절은 봉 내 low 도달 시 손절선에 체결된다고 가정한다.",
          "- **게이트 개방기 편중 · 백테스트 한정**.", ""]
    L.append(f"산출물: `{os.path.basename(SUMMARY_CSV)}`, `{os.path.basename(STOPS_CSV)}`, "
             f"`{os.path.basename(PNG_PATH)}`")
    L.append("")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT_PATH


def main():
    args = sys.argv[1:]
    run_r1 = "--r1" in args
    if not args or not (run_r1 or "--r0" in args):
        raise SystemExit(__doc__)

    events = load_gate_events()
    keys = {(s, l) for s, l in zip(events["symbol"], events["ltf"])}
    bars = {k: load_bars(*k) for k in keys}
    if any(v.empty for v in bars.values()):
        raise SystemExit("OHLCV 캐시 없음")
    print(f"[pop] 게이트 통과 이벤트 {len(events)}건")

    stops = struct_stops(events, bars)
    print(f"[struct] 손절선 산출 {len(stops)}건")
    smap = struct_stop_map(stops)

    base = simulate(events, bars)
    struct = simulate(events, bars, stop_pct=smap)
    nostop = simulate(events, bars, use_stop=False)
    print(f"[sim] BASE {len(base)} / STRUCT {len(struct)} / NOSTOP {len(nostop)}")

    gate = detection_gate(stops, base)
    print(f"[gate] detect={gate['detect_rate']} diverge={gate['diverge_share']} "
          f"-> {'GO' if gate['go'] else 'NO-GO'}")

    result = years = mech = base_mech = None
    if run_r1:
        if not gate["go"]:
            raise SystemExit("SS-R0 NO-GO — §2 에 따라 본 검정을 진행하지 않는다.")
        halves = half_split(struct, base)
        streams = stream_split(struct, base)
        result = judge(struct, base, streams, halves)
        years = yearly(struct, base)
        mech = mechanism(struct, nostop)
        base_mech = counterfactual_stopped(base, nostop)
        print(f"[judge] {result['verdict']} delta={result['bootstrap'].get('delta')} "
              f"CI=[{result['bootstrap'].get('ci_low')}, {result['bootstrap'].get('ci_high')}]")
        _plot(struct, base, nostop, result, gate, stops)

    stops.to_csv(STOPS_CSV, index=False)
    rows = [{"section": "gate", **gate},
            {"section": "metrics", "scenario": "BASE", **trade_metrics(base)},
            {"section": "metrics", "scenario": "STRUCT", **trade_metrics(struct)},
            {"section": "metrics", "scenario": "NOSTOP", **trade_metrics(nostop)}]
    if run_r1:
        rows += [{"section": "criterion", "label": c["text"], "passed": c["passed"],
                  "detail": c["detail"]} for c in result["criteria"]]
        rows += [{"section": "half_split", **h} for h in result["halves"]]
        rows += [{"section": "stream", **s} for s in result["streams"]]
        rows += [{"section": "year", **y} for y in years]
        rows.append({"section": "mechanism_struct", **mech})
        rows.append({"section": "mechanism_base", **base_mech})
        rows.append({"section": "verdict", "label": result["verdict"], **result["bootstrap"]})
    pd.DataFrame(rows).to_csv(SUMMARY_CSV, index=False)
    path = write_report(events, stops, gate, struct, base, nostop, result,
                        mech, base_mech, years, run_r1)
    print(f"[report] -> {path}")


if __name__ == "__main__":
    main()
