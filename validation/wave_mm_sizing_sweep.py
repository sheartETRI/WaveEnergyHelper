"""SPEC_WAVE_MM_SIZING 실행기 — SZ-R0 검정력 관문 / SZ-R1 사이징 판정.

    python validation/wave_mm_sizing_sweep.py --r0   # 변동성 산포 관문 (판정 없음)
    python validation/wave_mm_sizing_sweep.py --r1   # BASE5 vs VOLSIZE 판정 1개
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
    growth,
    load_bars,
    load_gate_events,
    max_drawdown,
    exposure_rate,
    simulate,
    trade_metrics,
)
from analysis.wave_mm_sizing import (
    ATR_PERIOD,
    BOOTSTRAP_N,
    BOOTSTRAP_SEED,
    DISPERSION_MIN,
    MIN_ACTIVE_MONTHS,
    MIN_TRADES,
    REDUCED_SHARE_MIN,
    REF_WINDOW_DAYS,
    SIZE_CAP_PCT,
    active_months,
    bootstrap_delta_sharpe,
    delta_sharpe,
    dispersion_gate,
    event_atrp,
    half_split,
    monthly_log_series,
    paired_months,
    sharpe,
    skew_diagnostic,
    volsize_map,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_CSV = os.path.join(OUT_DIR, "wave_mm_sizing.csv")
SIZES_CSV = os.path.join(OUT_DIR, "wave_mm_sizing_events.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_MM_SIZING.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_mm_sizing.png")

HONESTY = (
    "사이징은 엣지를 만들지 못한다. 배분이 분포를 바꿀 뿐이다. "
    "−3% 고정 손절 + 고정 5% 사이징은 이미 손절 위험(자본 대비 0.15%)이 균등하므로, "
    "변동성 사이징이 바꾸는 것은 손절 위험이 아니라 **보유 기간 손익의 변동성**이다."
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


def load_all():
    events = load_gate_events()
    keys = {(s, l) for s, l in zip(events["symbol"], events["ltf"])}
    bars = {k: load_bars(*k) for k in keys}
    missing = [k for k, v in bars.items() if v.empty]
    if missing:
        raise SystemExit(f"OHLCV 캐시 없음: {missing}")
    return events, bars


def build_scenarios(events, bars, sizes, *, use_stop=True, subset_ltf=None):
    ev = events if subset_ltf is None else events[events["ltf"] == subset_ltf]
    base = simulate(ev, bars, use_stop=use_stop)
    vol = simulate(ev, bars, use_stop=use_stop, tranche_pct=sizes)
    return base, vol


def judge(base: pd.DataFrame, vol: pd.DataFrame,
          streams: list[dict]) -> dict:
    boot = bootstrap_delta_sharpe(vol, base)
    hs = half_split(vol, base)
    delta = boot.get("delta")
    sign = np.sign(delta) if delta is not None else 0
    months = active_months(vol, base)

    c1 = bool(delta is not None and boot.get("ci_low") is not None
              and (boot["ci_low"] > 0 or boot["ci_high"] < 0))
    c2 = (len(base) >= MIN_TRADES and len(vol) >= MIN_TRADES
          and months >= MIN_ACTIVE_MONTHS)
    c3 = bool(hs) and sign != 0 and all(
        h["delta"] is not None and np.sign(h["delta"]) == sign for h in hs)
    c4 = bool(streams) and sign != 0 and all(
        s["delta"] is not None and np.sign(s["delta"]) == sign for s in streams)

    criteria = [
        {"id": 1, "text": "Δ ≠ 0 & 월 블록 부트스트랩 95% CI가 0 배제", "passed": c1,
         "detail": f"Δ={_fmt(delta, 6)} CI=[{_fmt(boot.get('ci_low'), 6)}, "
                   f"{_fmt(boot.get('ci_high'), 6)}]"},
        {"id": 2, "text": f"트레이드 ≥ {MIN_TRADES} (양쪽) & 수익 발생 월 ≥ {MIN_ACTIVE_MONTHS}",
         "passed": c2, "detail": f"BASE5={len(base)}, VOLSIZE={len(vol)}, 월={months}"},
        {"id": 3, "text": "half-split 양쪽에서 Δ 같은 부호", "passed": c3,
         "detail": ", ".join(f"{h['split']}={_fmt(h['delta'], 6)}" for h in hs)},
        {"id": 4, "text": "1h·6h 단독 포트폴리오에서 Δ 같은 부호", "passed": c4,
         "detail": ", ".join(f"{s['ltf']}={_fmt(s['delta'], 6)}" for s in streams)},
    ]
    ok = all(c["passed"] for c in criteria)
    if not c2:
        verdict = "판정 불가 (표본 부족)"
    elif ok and delta > 0:
        verdict = "VOLSIZE 우위"
    elif ok and delta < 0:
        verdict = "고정 5% 우위"
    else:
        verdict = "식별 불가"
    return {"verdict": verdict, "criteria": criteria, "bootstrap": boot,
            "halves": hs, "streams": streams, "months": months}


def yearly_delta(base: pd.DataFrame, vol: pd.DataFrame) -> list[dict]:
    rows = []
    if base.empty and vol.empty:
        return rows
    allt = pd.concat([base, vol])
    for y in sorted(set(pd.to_datetime(allt["exit_ts"]).dt.year)):
        b = base[pd.to_datetime(base["exit_ts"]).dt.year == y]
        v = vol[pd.to_datetime(vol["exit_ts"]).dt.year == y]
        rows.append({"year": int(y), "base_trades": len(b), "vol_trades": len(v),
                     "delta": delta_sharpe(v, b)})
    return rows


def _plot(base, vol, result, gate, years) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    ax = axes[0]
    for tr, lab, col in ((base, "BASE5", "#3867F2"), (vol, "VOLSIZE", "#2E7D32")):
        if not tr.empty:
            t = tr.sort_values("exit_ts")
            ax.plot(pd.to_datetime(t["exit_ts"]), t["log_growth"].cumsum(), label=lab, color=col)
    ax.axhline(0, color="black", lw=0.8)
    ax.legend(fontsize=8)
    ax.set_title("cumulative log growth (G: size-contaminated)")

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
    ax.set_title(f"delta Sharpe = S(VOLSIZE) - S(BASE5)   {result['verdict']}")

    ax = axes[2]
    if not vol.empty:
        ax.hist(vol["size_pct"].dropna(), bins=25, color="#9E9E9E")
    ax.axvline(SIZE_CAP_PCT, color="black", ls="--", lw=1)
    ax.set_title(f"VOLSIZE size distribution (cap {SIZE_CAP_PCT:g}%)")
    fig.suptitle("WAVE MM SIZING — fixed 5% vs ATR-inverse", fontsize=13)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=110)
    plt.close(fig)
    return PNG_PATH


def write_report(events, base, vol, gate, result, streams, years, skew,
                 nostop_check, run_r1: bool) -> str:
    bm, vm = trade_metrics(base), trade_metrics(vol)
    months = paired_months(vol, base)
    b = result["bootstrap"] if result else {}
    L = ["# REPORT_WAVE_MM_SIZING", "",
         f"SPEC_WAVE_MM_SIZING — 자금 관리 2라운드. 구간 {WINDOW_MAIN[0]} ~ {WINDOW_MAIN[1]}, "
         f"{', '.join(SYMBOLS_V2)}. 방향 (a) 트레이드당 위험 균등화 (ATR 역비례).", "",
         "## 0. 정직성 조항", "", HONESTY, ""]

    L += ["## 1. 판정", ""]
    if not run_r1:
        L += [f"**SZ-R0 {'GO' if gate['go'] else 'NO-GO'}** — 판정 없음 (검정력 관문 단계).", ""]
        if not gate["go"]:
            L += ["기록: **이 모집단에서 변동성 사이징은 고정 사이징과 구별될 만큼 다르게 "
                  "배분하지 않음.** 판정 없이 다음 축으로 이동한다 (§3).", ""]
    else:
        L += [f"**{result['verdict']}**", "",
              "| # | 기준 (§4) | 결과 | 값 |", "|---|---|---|---|"]
        for c in result["criteria"]:
            L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
        L += ["", f"주 비교: Δ = S(VOLSIZE) − S(BASE5) = **{_fmt(b.get('delta'), 6)}** "
                  f"(월 블록 부트스트랩 {b.get('n_boot')}회, 95% CI "
                  f"[{_fmt(b.get('ci_low'), 6)}, {_fmt(b.get('ci_high'), 6)}], "
                  f"월 {b.get('n_months')}개, seed={b.get('seed')})", "",
              "S = 월별 로그 수익의 평균/표준편차 (무위험 0). 사이즈 상수배에 근사 불변이라 "
              "투입 규모 차이가 아닌 **배분 효과**만 잰다.", "",
              "어떤 판정이든 실운용 반영은 사용자 결정이다.", ""]

    L += ["## 2. 고정 정의 (§2)", "",
          f"- VOLSIZE: size_i = min({SIZE_CAP_PCT:g}%, {SIZE_CAP_PCT:g}% × ref_i / atrp_i)",
          f"- atrp_i = ATR{ATR_PERIOD}(신호봉) ÷ 진입가 · "
          f"ref_i = 신호봉 이전 {REF_WINDOW_DAYS}일 atrp 중앙값 (룩어헤드 금지)",
          f"- 상한 {SIZE_CAP_PCT:g}%, 하한 없음 — VOLSIZE 는 줄이기만 한다",
          f"- 시뮬레이터·체결·비용·1포지션·20봉 청산·평단 −{STOP_PCT:g}% 손절은 MM 라운드와 동일", ""]

    L += ["## 3. SZ-R0 — 검정력 관문", "",
          f"체결 트레이드 {gate['n']}건 기준.", "",
          "| 항목 | 값 | 조건 | 충족 |", "|---|---|---|---|",
          f"| atrp P25 / P50 / P75 | {_fmt(gate['atrp_p25'], 5)} / {_fmt(gate['atrp_p50'], 5)} "
          f"/ {_fmt(gate['atrp_p75'], 5)} | — | — |",
          f"| 산포 P75/P25 | {_fmt(gate['dispersion'], 3)} | ≥ {DISPERSION_MIN} | "
          f"{_mark(gate['cond_dispersion'])} |",
          f"| 5% 미만 축소 비율 | {_pct(gate['reduced_share'])} | ≥ {REDUCED_SHARE_MIN:.0%} | "
          f"{_mark(gate['cond_reduced'])} |", "",
          f"VOLSIZE 사이즈 분포: 평균 {_fmt(gate['size_mean_pct'], 3)}% · "
          f"중앙값 {_fmt(gate['size_median_pct'], 3)}% · "
          f"P25 {_fmt(gate['size_p25_pct'], 3)}% · 최소 {_fmt(gate['size_min_pct'], 3)}%", "",
          f"**관문 판정: {'GO' if gate['go'] else 'NO-GO'}**", ""]

    if run_r1:
        L += ["## 4. 시나리오 비교", "",
              "| 지표 | BASE5 | VOLSIZE |", "|---|---|---|"]
        for key, lab, f in (("trades", "체결 트레이드", lambda v: _fmt(v)),
                            ("stop_rate", "손절 발동률", _pct),
                            ("win_rate", "승률", _pct),
                            ("net_mean_pct", "트레이드당 순기대값(%)", lambda v: _fmt(v, 4)),
                            ("max_drawdown", "최대 드로다운", _pct),
                            ("exposure", "노출률", _pct)):
            L.append(f"| {lab} | {f(bm.get(key))} | {f(vm.get(key))} |")
        sv = sharpe(monthly_log_series(vol, months))
        sb = sharpe(monthly_log_series(base, months))
        L += [f"| S (월별 로그 Sharpe) | {_fmt(sb, 6)} | {_fmt(sv, 6)} |",
              f"| G (로그 성장률 합) | {_fmt(growth(base), 6)} | {_fmt(growth(vol), 6)} |", "",
              "**G 는 판정에 쓰지 않는다.** VOLSIZE 는 상한 5%로 줄이기만 하므로 "
              "G 비교는 투입량 차이에 오염된다 (§4).", ""]

        L += ["## 5. 보조 보고 (판정 미사용)", "", "### 5.1 NOSTOP 부호 재현 (사전등록 보조 점검)", ""]
        L += [f"- 주 판정 Δ (BASE 손절 하) = {_fmt(b.get('delta'), 6)}",
              f"- NOSTOP 구성 Δ = {_fmt(nostop_check.get('delta'), 6)} "
              f"(BASE5 {nostop_check.get('base_trades')}건 / VOLSIZE "
              f"{nostop_check.get('vol_trades')}건)"]
        same = nostop_check.get("same_sign")
        L += ["", ("두 부호가 같다 — 사이징 결론이 손절 규칙에 종속되지 않는다."
                   if same else
                   "**두 부호가 다르다 — 사이징 결론이 손절 규칙에 종속된다.** "
                   "판정 변경 사유가 아니라 발견으로 기록한다 (§5-1)."), ""]

        L += ["### 5.2 왜도 진단 — 큰 승리는 고변동에서 나오는가", ""]
        if skew.get("n"):
            L += [f"- 상위 5% 수익 트레이드 {skew['top_n']}건의 atrp 분위: "
                  f"평균 {_fmt(skew['top_atrp_quantile_mean'], 3)} · "
                  f"중앙값 {_fmt(skew['top_atrp_quantile_median'], 3)} "
                  f"(전체 평균 {_fmt(skew['all_atrp_quantile_mean'], 3)})",
                  f"- VOLSIZE 가 그 트레이드들을 평균 "
                  f"**{_fmt(skew['top_size_reduction_pct'], 2)}%** 축소 "
                  f"(전체 평균 축소 {_fmt(skew['all_size_reduction_pct'], 2)}%)", "",
                  "분위가 0.5 를 크게 넘으면 §0 의 긴장이 실재한다 — "
                  "VOLSIZE 가 왜도의 원천을 깎는다는 뜻이다."]
        else:
            L.append("진단 불가.")
        L.append("")

        L += ["### 5.3 half-split · 스트림 단독 포트폴리오", "",
              "| 구분 | BASE5 | VOLSIZE | S(BASE5) | S(VOLSIZE) | Δ |", "|---|---|---|---|---|---|"]
        for h in result["halves"]:
            L.append(f"| {h['split']} | {h['base_trades']} | {h['volsize_trades']} | "
                     f"{_fmt(h['s_base'], 6)} | {_fmt(h['s_volsize'], 6)} | {_fmt(h['delta'], 6)} |")
        for s in result["streams"]:
            L.append(f"| {s['ltf']} 단독 | {s['base_trades']} | {s['vol_trades']} | "
                     f"{_fmt(s['s_base'], 6)} | {_fmt(s['s_vol'], 6)} | {_fmt(s['delta'], 6)} |")
        L += ["", "### 5.4 연도별 Δ", "", "| year | BASE5 | VOLSIZE | Δ |", "|---|---|---|---|"]
        for y in years:
            L.append(f"| {y['year']} | {y['base_trades']} | {y['vol_trades']} | "
                     f"{_fmt(y['delta'], 6)} |")
        L.append("")

    L += ["## 6. 한계 (§7)", "",
          "- **단일 진입 가정**: MM 라운드와 동일. 실규칙은 고정 기준 없는 재량 하이브리드 분할이다.",
          "- **손절 규칙 미확정 상태의 BASE 전제**: MM-R1 이 식별 불가로 끝나 −3% 손절이 "
          "확정되지 않았다. 주 판정은 그 기본값 위에서 돌렸고, §5-1 로 종속성을 감시한다.",
          f"- **ATR{ATR_PERIOD}·{REF_WINDOW_DAYS}일 참조창의 자의성**: 고정으로 튜닝은 차단했으나 "
          "최적성을 주장할 수 없다. 다른 기간에서 부호가 바뀔 여지는 측정하지 않았다.",
          "- **Sharpe형 지표의 왜도 둔감성**: 양의 왜도 전략에서 꼬리 정보를 잃는다. "
          "S 가 개선돼도 큰 승리를 깎았을 수 있다 — §5.2 로 보완 관찰한다.",
          "- **표본의 게이트 개방기 편중**: F2-b 개방률이 2021년 최고·2022년 최저였다.",
          "- **백테스트 한정**: 전방 미검증이며 §6 전방 추적과 무관하다.", ""]
    L.append(f"산출물: `{os.path.basename(SUMMARY_CSV)}`, `{os.path.basename(SIZES_CSV)}`, "
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
    atrp_df = event_atrp(events, bars, build=True)
    print(f"[atrp] 이벤트별 atrp/ref 산출 {len(atrp_df)}건")
    sizes = volsize_map(atrp_df)

    base = simulate(events, bars)
    vol = simulate(events, bars, tranche_pct=sizes)
    print(f"[sim] BASE5 {len(base)} / VOLSIZE {len(vol)} trades")

    gate = dispersion_gate(atrp_df, base)
    print(f"[gate] dispersion={gate['dispersion']} reduced={gate['reduced_share']} "
          f"-> {'GO' if gate['go'] else 'NO-GO'}")

    result = streams = years = skew = nostop_check = None
    if run_r1:
        if not gate["go"]:
            raise SystemExit("SZ-R0 NO-GO — §3 에 따라 본 검정을 진행하지 않는다.")
        streams = []
        for ltf in ("1h", "6h"):
            b, v = build_scenarios(events, bars, sizes, subset_ltf=ltf)
            streams.append({"ltf": ltf, "base_trades": len(b), "vol_trades": len(v),
                            "s_base": sharpe(monthly_log_series(b, paired_months(v, b))),
                            "s_vol": sharpe(monthly_log_series(v, paired_months(v, b))),
                            "delta": delta_sharpe(v, b)})
        result = judge(base, vol, streams)
        years = yearly_delta(base, vol)
        skew = skew_diagnostic(base, atrp_df)
        nb, nv = build_scenarios(events, bars, sizes, use_stop=False)
        nd = delta_sharpe(nv, nb)
        md = result["bootstrap"].get("delta")
        nostop_check = {"delta": nd, "base_trades": len(nb), "vol_trades": len(nv),
                        "same_sign": bool(nd is not None and md is not None
                                          and np.sign(nd) == np.sign(md))}
        print(f"[judge] {result['verdict']} delta={md} "
              f"CI=[{result['bootstrap'].get('ci_low')}, {result['bootstrap'].get('ci_high')}]")
        _plot(base, vol, result, gate, years)

    atrp_df.to_csv(SIZES_CSV, index=False)
    rows = [{"section": "gate", **gate},
            {"section": "metrics", "scenario": "BASE5", **trade_metrics(base)},
            {"section": "metrics", "scenario": "VOLSIZE", **trade_metrics(vol)}]
    if run_r1:
        rows += [{"section": "criterion", "label": c["text"], "passed": c["passed"],
                  "detail": c["detail"]} for c in result["criteria"]]
        rows += [{"section": "half_split", **h} for h in result["halves"]]
        rows += [{"section": "stream", **s} for s in streams]
        rows += [{"section": "year", **y} for y in years]
        rows.append({"section": "skew", **skew})
        rows.append({"section": "nostop_check", **nostop_check})
        rows.append({"section": "verdict", "label": result["verdict"], **result["bootstrap"]})
    pd.DataFrame(rows).to_csv(SUMMARY_CSV, index=False)
    path = write_report(events, base, vol, gate, result, streams, years, skew,
                        nostop_check, run_r1)
    print(f"[report] -> {path}")


if __name__ == "__main__":
    main()
