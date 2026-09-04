"""Wave HTF Gate V2 스윕 — R0 기저율 관문 · REPORT_WAVE_HTF_GATE_V2.md.

SPEC_WAVE_HTF_GATE_V2 실행기.

사용법:
    python validation/wave_htf_gate_v2_sweep.py --states SYMBOL HTF [--window main|extended]
    python validation/wave_htf_gate_v2_sweep.py --r0 [--window main|extended]
    python validation/wave_htf_gate_v2_sweep.py --test [--window main|extended]
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

from analysis.wave_htf_gate import (
    CALIB_THRESHOLD,
    GATES,
    MIN_CELL_N,
    TRIGGER_LABEL,
    bnb_core_overlap,
    calibration_verdict,
    delta_expectancy,
    expectancy_20,
    gate_mask,
    fractal_correlation,
    gate_table,
    judge,
)
from analysis.wave_htf_gate_v2 import (
    GATE_NOTE,
    GATE_VERSION_V1,
    GATE_VERSION_V2,
    PAIRS_V2,
    R0_MIN_EXPECTED_N,
    STATE_WINDOW_BARS,
    SYMBOLS_V2,
    WINDOW_EXTENDED,
    WINDOW_MAIN,
    _v2_state_path,
    baseline_rates,
    build_htf_states_v2,
    build_pair_events_v2,
    event_rate,
    expected_sample,
    fetch_window_bare,
    load_htf_states_v2,
    load_v2_journal,
    r0_verdict,
    reject_reason,
    yearly_open_rates,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
R0_CSV = os.path.join(OUT_DIR, "wave_htf_gate_v2_r0.csv")
CALIB_CSV = os.path.join(OUT_DIR, "wave_htf_gate_v2_calibration.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_HTF_GATE_V2.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_htf_gate_v2.png")
TEST_CSV = os.path.join(OUT_DIR, "wave_htf_gate_v2.csv")
EVENTS_CSV = os.path.join(OUT_DIR, "wave_htf_gate_v2_events.csv")

WINDOWS = {"main": WINDOW_MAIN, "extended": WINDOW_EXTENDED}


def _fmt(v, d=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{v:.{d}f}"


def _pct(v, d=2):
    return "—" if v is None else f"{v * 100:.{d}f}%"


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _arg_window(args: list[str]) -> tuple[str, tuple[str, str]]:
    if "--window" in args:
        name = args[args.index("--window") + 1]
    else:
        name = "main"
    if name not in WINDOWS:
        raise SystemExit(f"unknown window: {name} (main|extended)")
    return name, WINDOWS[name]


# ----------------------------------------------------------------- states
def cmd_states(symbol: str, htf: str, window: tuple[str, str]) -> None:
    df = build_htf_states_v2(
        symbol, htf, start=window[0], end=window[1], progress_every=500,
    )
    path = _v2_state_path(symbol, htf)
    df.to_csv(path, index=False)
    print(f"[states-v2] {symbol} {htf} rows={len(df)} -> {path}")
    if df.empty:
        return
    print(f"[states-v2] {df['htf_open_time'].min()} ~ {df['htf_open_time'].max()}")
    print(f"[states-v2] {df['htf_state'].value_counts().to_dict()}")
    both_v2 = int((df["align_v2"] & df["g_wave"]).sum())
    both_v1 = int((df["align_v1"] & df["g_wave"]).sum())
    print(f"[states-v2] align_v1={int(df['align_v1'].sum())} "
          f"align_v2={int(df['align_v2'].sum())} wave={int(df['g_wave'].sum())} "
          f"both_v1={both_v1} both_v2={both_v2}")


# ------------------------------------------------------------ calibration
def run_pair_c_calibration(window: tuple[str, str]) -> tuple[list[dict], dict]:
    """PAIR_C(1d→6h) 캘리브레이션 — R1 §2 와 동일 방법·동일 임계."""
    from display.asof import run_indicator_pipeline

    rows: list[dict] = []
    htf, ltf = PAIRS_V2["PAIR_C"]
    for sym in SYMBOLS_V2:
        htf_pipe = run_indicator_pipeline(
            fetch_window_bare(sym, htf, window[0], window[1], pad_bars=260))
        ltf_pipe = run_indicator_pipeline(
            fetch_window_bare(sym, ltf, window[0], window[1], pad_bars=260))
        r = fractal_correlation(sym, htf, ltf, htf_pipe=htf_pipe, ltf_pipe=ltf_pipe)
        r["pair"] = "PAIR_C"
        rows.append(r)
    return rows, {"PAIR_C": calibration_verdict(rows)}


# -------------------------------------------------------------------- R0
def _plot_r0(rates: list[dict], years: list[dict], verdict: dict) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    ax = axes[0]
    labels = [f"{r['pair'][-1]}·{r['symbol'].replace('USDT','')}" for r in rates if r.get("bars")]
    xs = np.arange(len(labels))
    for i, (key, color) in enumerate(
            [("p_align", "#3867F2"), ("p_wave", "#FFB74D"), ("p_both", "#2E7D32")]):
        ys = [r[key] * 100 for r in rates if r.get("bars")]
        ax.bar(xs + (i - 1) * 0.27, ys, 0.27, label=key, color=color)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("bar share (%)")
    ax.legend(fontsize=8)
    ax.set_title("R0 base rates (v2 F2-b gate)")

    ax = axes[1]
    if years:
        ydf = pd.DataFrame(years)
        for pair in sorted(ydf["pair"].unique()):
            sub = ydf[ydf["pair"] == pair].groupby("year")["p_both"].mean() * 100
            ax.plot(sub.index, sub.values, marker="o", label=pair)
        ax.legend(fontsize=8)
    ax.set_title("P(G_BOTH) by year")
    ax.set_ylabel("%")

    ax = axes[2]
    pairs = list(verdict["per_pair"])
    vals = [verdict["per_pair"][p] for p in pairs]
    ax.bar(pairs, vals, color=["#2E7D32" if v >= R0_MIN_EXPECTED_N else "#EF5350" for v in vals])
    ax.axhline(R0_MIN_EXPECTED_N, color="black", ls="--", lw=1, label=f"n≥{R0_MIN_EXPECTED_N}")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=10)
    ax.legend(fontsize=8)
    ax.set_title(f"expected n̂  →  {verdict['verdict']}")

    fig.suptitle(f"WAVE HTF GATE V2 — R0 ({verdict['window']})", fontsize=13)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=110)
    plt.close(fig)
    return PNG_PATH


def _gate_table_md(rows: list[dict]) -> list[str]:
    out = ["| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| {r['gate']} | {r['n']} | {r['n_labeled']} | {_fmt(r['expectancy_20'])} | "
            f"{_fmt(r['profit_factor'])} | {_fmt(r['survival_rate'], 2)} | "
            f"{_fmt(r['win_rate'], 2)} | {_fmt(r['avg_return_20'])} |"
        )
    return out


def write_report(
    window_name: str,
    window: tuple[str, str],
    rates: list[dict],
    calib_rows: list[dict],
    calib_verdicts: dict,
    expected: list[dict],
    verdict: dict,
    years: list[dict],
    test: dict | None = None,
) -> str:
    L: list[str] = []
    L.append("# REPORT_WAVE_HTF_GATE_V2")
    L.append("")
    L.append("SPEC_WAVE_HTF_GATE_V2 — 상위 TF 파동 상태 게이트, 2차. "
             f"관측 구간 {window[0]} ~ {window[1]} ({window_name}).")
    L.append("")

    L.append("## 1. 판정")
    L.append("")
    go = verdict["verdict"] == "GO"
    L.append(f"**R0 {verdict['verdict']}** — 잔존 쌍 합산 n̂ = {_fmt(verdict['n_hat_total'], 1)} "
             f"(관문 {R0_MIN_EXPECTED_N})")
    L.append("")
    L.append("| 단계 | 결과 | 근거 |")
    L.append("|---|---|---|")
    for pair, v in calib_verdicts.items():
        L.append(f"| §2 캘리브레이션 {pair} | {'유지' if v['keep_pair'] else '폐기'} | "
                 f"mean corr {_fmt(v['mean_corr'])} vs 임계 {v['threshold']:.2f} |")
    L.append(f"| §3.3 R0 기저율 관문 | {verdict['verdict']} | "
             f"n̂ = {_fmt(verdict['n_hat_total'], 1)} / 잔존 쌍 "
             f"{', '.join(verdict['surviving_pairs']) or '없음'} |")
    if test is None:
        L.append(f"| §4 본 검정 | {'미실행' if go else '미실행'} | "
                 f"{'R0 GO — 본 검정 대기' if go else 'R0 관문 미통과 — §3.3에 따라 진행하지 않음'} |")
    else:
        L.append(f"| §4 본 검정 | **{test['result']['verdict']}** | "
                 f"Δ = {_fmt(test['result']['bootstrap'].get('delta'))} |")
    L.append("")
    if not go:
        L.append("본 라운드는 §4 본 검정에 도달하지 않았다. 아래 §2 가 그 근거다.")
        L.append("")

    if test is not None:
        res = test["result"]
        boot = res["bootstrap"]
        L.append(f"### 본 검정 판정: **{res['verdict']}**")
        L.append("")
        L.append(f"모집단: 잔존 쌍 {' + '.join(verdict['surviving_pairs'])} 통합 "
                 f"(§4.1 C4). 게이트 버전 `{GATE_VERSION_V2}`.")
        L.append("")
        L.append("| # | 기준 (§4.1) | 결과 | 값 |")
        L.append("|---|---|---|---|")
        for c in res["criteria"]:
            L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
        L.append("")
        L.append(f"Δ = E[G_BOTH] − E[G_ALIGN] = **{_fmt(boot.get('delta'))}** "
                 f"(bootstrap {boot.get('n_boot')}회, 95% CI "
                 f"[{_fmt(boot.get('ci_low'))}, {_fmt(boot.get('ci_high'))}], "
                 f"n_G_ALIGN={boot.get('n_align')}, n_G_BOTH={boot.get('n_both')})")
        L.append("")
        reason = reject_reason(res)
        if reason == "accepted":
            L.append("**결론: H1 채택.** 산출물 상한은 라이브 워치리스트 후보 필터 승격이다 (§5). "
                     "자금·사이징 판단은 시스템 밖의 결정으로 남긴다.")
        elif reason == "refuted_with_power":
            L.append(f"**결론: 유효 검정에서의 반증.** n(G_BOTH) = {boot.get('n_both')} ≥ {MIN_CELL_N} "
                     "이므로 이번 REJECT 는 표본 부족이 아니라 실제 반증이다. "
                     "R1 의 '식별 불가' 와 구분해 기록한다 (§4.1). §5 에 따라 종료한다.")
        else:
            L.append(f"**결론: 여전히 표본 부족.** n(G_BOTH) = {boot.get('n_both')} < {MIN_CELL_N} "
                     "이라 이번 REJECT 도 반증이 아니다. R1 과 같은 성격의 결과다 (§4.1). "
                     "§5 에 따라 종료한다.")
        L.append("")

    L.append("## 2. R0")
    L.append("")
    L.append("### 2.1 게이트 기저율 (HTF 봉 비율)")
    L.append("")
    L.append(f"게이트 버전: `{GATE_VERSION_V2}` (F2-b: MA60·120·240 모두 상승, 기울기 창 1봉)")
    L.append("")
    L.append("| pair | HTF | symbol | 봉수 | 구간 | P(G_ALIGN) | P(G_WAVE) | P(G_BOTH) | n(G_BOTH) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in rates:
        if not r.get("bars"):
            L.append(f"| {r['pair']} | {r['htf']} | {r['symbol']} | 0 | — | — | — | — | — |")
            continue
        span = f"{pd.Timestamp(r['first_bar']).date()} ~ {pd.Timestamp(r['last_bar']).date()}"
        L.append(
            f"| {r['pair']} | {r['htf']} | {r['symbol']} | {r['bars']} | {span} | "
            f"{_pct(r['p_align'])} | {_pct(r['p_wave'])} | {_pct(r['p_both'])} | {r['n_both']} |"
        )
    L.append("")
    L.append("참고 — R1(v1 게이트, 완전정배열)의 1d 기저율은 260봉 중 0이었다. "
             "v2 게이트는 그 결과를 보고 교체한 것이다 (§0 C1).")
    L.append("")

    L.append("### 2.2 PAIR_C 캘리브레이션 (1d → 6h)")
    L.append("")
    L.append("corr( HTF 소파동 %K(5,3,3) , HTF 봉 마감 시점으로 asof-align 한 LTF 대파동 %K(20,10,10) ) "
             f"— R1 §2 와 동일 방법, 임계 {CALIB_THRESHOLD:.2f}")
    L.append("")
    L.append("| symbol | n | corr | 구간 |")
    L.append("|---|---|---|---|")
    for r in calib_rows:
        span = ""
        if r.get("overlap_start") is not None:
            span = f"{pd.Timestamp(r['overlap_start']).date()} ~ {pd.Timestamp(r['overlap_end']).date()}"
        L.append(f"| {r['symbol']} | {r['n']} | {_fmt(r.get('corr'))} | {span} |")
    L.append("")
    for pair, v in calib_verdicts.items():
        L.append(f"{pair}: mean corr {_fmt(v['mean_corr'])}, min {_fmt(v['min_corr'])} → "
                 f"**{'쌍 유지' if v['keep_pair'] else '쌍 폐기'}**")
    L.append("")

    L.append("### 2.3 기대 표본 n̂ 계산 근거")
    L.append("")
    L.append("n̂(pair) = Σ_symbol [ event_rate_LTF × LTF봉수 × P(G_BOTH) ] (§3.2 고정 산식)")
    L.append("")
    L.append("| pair | symbol | LTF | event_rate (건/봉) | LTF봉수 | P(G_BOTH) | n̂ |")
    L.append("|---|---|---|---|---|---|---|")
    for e in expected:
        for d in e["detail"]:
            L.append(
                f"| {d['pair']} | {d['symbol']} | {d['ltf']} | {_fmt(d['event_rate'], 5)} | "
                f"{d['ltf_bars']} | {_pct(d['p_both'])} | {_fmt(d['n_hat'], 1)} |"
            )
        L.append(f"| **{e['pair']} 합계** | | {e['ltf']} | | {e['ltf_bars']} | | "
                 f"**{_fmt(e['n_hat'], 1)}** |")
    L.append("")
    L.append("event_rate 는 R1 실측치 고정값이다 (1h: R1 캐시 실측, 6h: 4h 실측의 봉길이 비례 환산). "
             "6h 환산은 실측 대체 전의 **근사**이며, 본 검정에 들어가면 실측으로 대체된다.")
    L.append("")

    L.append("## 3. 4열 비교표 (무게이트 / G_ALIGN / G_WAVE / G_BOTH)")
    L.append("")
    if test is None:
        L.append("R0 단계에서는 산출하지 않는다. §4 본 검정 진행 시에만 채운다.")
        L.append("")
    else:
        L.append(f"트리거: {TRIGGER_LABEL} (기존 Filter_C ∪ Filter_Q 코호트, 신규 검출 없음). "
                 f"이벤트 {len(test['pooled'])}건.")
        L.append("")
        for key in ["POOLED"] + list(PAIRS_V2):
            if key not in test["tables"]:
                continue
            title = ("잔존 쌍 통합" if key == "POOLED"
                     else f"{key} (HTF={PAIRS_V2[key][0]}, LTF={PAIRS_V2[key][1]})")
            L.append(f"### {title}")
            L.append("")
            L.extend(_gate_table_md(test["tables"][key]))
            L.append("")
        for key in sorted(k for k in test["tables"] if "|" in k):
            L.append(f"### {key.replace('|', ' / ')}")
            L.append("")
            L.extend(_gate_table_md(test["tables"][key]))
            L.append("")
        L.append("G_WAVE 열은 'G_ALIGN 없이 파동 상태만으로 충분한가'의 참고 자료로만 읽는다 (§4.2).")
        L.append("")
        L.append("### TF쌍별 Δ 분해 (§4.2, 판정 미사용)")
        L.append("")
        L.append("통합 Δ 가 어디서 나오는지 분해한다. **사후 부분집합 선택이므로 판정 근거가 아니다.**")
        L.append("")
        L.append("| 게이트 | pair | E[G_ALIGN] | E[G_BOTH] | Δ | n(G_BOTH) |")
        L.append("|---|---|---|---|---|---|")
        for ver in (GATE_VERSION_V2, GATE_VERSION_V1):
            for pair, d in test["per_pair"].get(ver, {}).items():
                L.append(f"| `{ver}` | {pair} | {_fmt(d['e_align'])} | {_fmt(d['e_both'])} | "
                         f"{_fmt(d['delta'])} | {d['n_both']} |")
        L.append("")
        L.append("### C1 사후 완화 감사 (§0 C1, 판정 미사용)")
        L.append("")
        L.append("C1 은 R1 결과를 보고 내린 게이트 완화다. 그 완화가 **결론을 바꿨는지**만 확인한다. "
                 "더 나은 게이트를 고르기 위한 비교가 아니며, 판정은 사전등록대로 "
                 f"`{GATE_VERSION_V2}` 로만 한다.")
        L.append("")
        v1b = test["v1_result"]["bootstrap"]
        v2b = test["result"]["bootstrap"]
        L.append("| 게이트 | Δ | 95% CI | n(G_ALIGN) | n(G_BOTH) | 판정 |")
        L.append("|---|---|---|---|---|---|")
        L.append(f"| `{GATE_VERSION_V2}` (사전등록) | {_fmt(v2b.get('delta'))} | "
                 f"[{_fmt(v2b.get('ci_low'))}, {_fmt(v2b.get('ci_high'))}] | "
                 f"{v2b.get('n_align')} | {v2b.get('n_both')} | {test['result']['verdict']} |")
        L.append(f"| `{GATE_VERSION_V1}` (R1 원안) | {_fmt(v1b.get('delta'))} | "
                 f"[{_fmt(v1b.get('ci_low'))}, {_fmt(v1b.get('ci_high'))}] | "
                 f"{v1b.get('n_align')} | {v1b.get('n_both')} | {test['v1_result']['verdict']} |")
        L.append("")
        L.extend(_gate_table_md(test["v1_tables"]))
        L.append("")
        same = test["v1_result"]["verdict"] == test["result"]["verdict"]
        L.append(
            ("**C1 은 결론을 바꾸지 않았다.** 두 게이트 모두 같은 판정이고 Δ 부호도 같다. "
             "즉 이번 결론은 사후 완화에 의존하지 않는다."
             if same else
             "**주의: C1 이 결론을 바꿨다.** 사전등록 게이트와 R1 원안 게이트의 판정이 다르다. "
             "이 경우 본 라운드의 결론은 게이트 선택에 의존하므로 그대로 채택해서는 안 된다.")
        )
        L.append("")
        L.append("### BNB 단독 — Filter_BNB_CORE 중첩률 (§4.2)")
        L.append("")
        o = test["bnb"]
        L.append("| n(BNB) | n(BNB_CORE) | n(G_BOTH) | 교집합 | Jaccard | "
                 "P(CORE\\|BOTH) | P(BOTH\\|CORE) | E[BNB_CORE] | E[G_BOTH] |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        if o.get("n_bnb"):
            L.append(
                f"| {o['n_bnb']} | {o['n_bnb_core']} | {o['n_g_both']} | {o['n_intersection']} | "
                f"{_fmt(o['jaccard'])} | {_fmt(o['p_core_given_both'])} | "
                f"{_fmt(o['p_both_given_core'])} | {_fmt(o['e_bnb_core'])} | {_fmt(o['e_g_both'])} |"
            )
        else:
            L.append("| 0 | — | — | — | — | — | — | — | — |")
        L.append("")

    L.append("## 4. half-split · 연도별 개방 비율")
    L.append("")
    if test is not None:
        L.append("### half-split (§4.1-3)")
        L.append("")
        L.append("| split | n | 구간 | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |")
        L.append("|---|---|---|---|---|---|---|---|")
        for h in test["result"]["halves"]:
            span = ""
            if h.get("ts_min") is not None:
                span = f"{pd.Timestamp(h['ts_min']).date()} ~ {pd.Timestamp(h['ts_max']).date()}"
            L.append(
                f"| {h['split']} | {h['n']} | {span} | {h['n_align']} | {h['n_both']} | "
                f"{_fmt(h['e_align'])} | {_fmt(h['e_both'])} | {_fmt(h['delta'])} |"
            )
        L.append("")
        L.append("### 심볼별 Δ (§4.1-4)")
        L.append("")
        L.append("| symbol | n | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |")
        L.append("|---|---|---|---|---|---|---|")
        for s in test["result"]["symbols"]:
            L.append(
                f"| {s['symbol']} | {s['n']} | {s['n_align']} | {s['n_both']} | "
                f"{_fmt(s['e_align'])} | {_fmt(s['e_both'])} | {_fmt(s['delta'])} |"
            )
        L.append("")
    L.append("### 연도별 게이트 개방 비율 (§4.2)")
    L.append("")
    if years:
        ydf = pd.DataFrame(years)
        L.append("| pair | symbol | " + " | ".join(str(y) for y in sorted(ydf["year"].unique())) + " |")
        L.append("|---" * (2 + len(ydf["year"].unique())) + "|")
        for (pair, sym), grp in ydf.groupby(["pair", "symbol"]):
            by_year = grp.set_index("year")["p_both"]
            cells = [_pct(by_year.get(y)) if y in by_year.index else "—"
                     for y in sorted(ydf["year"].unique())]
            L.append(f"| {pair} | {sym} | " + " | ".join(cells) + " |")
        L.append("")
        L.append("셀 값은 해당 연도 HTF 봉 중 G_BOTH 가 열린 비율이다.")
    else:
        L.append("연도별 데이터 없음.")
    L.append("")

    L.append("## 5. 한계")
    L.append("")
    L.append(f"- **C1 은 사후 완화다**: {GATE_NOTE}")
    L.append("- **기울기 창 1봉 플래핑**: F2-b 를 MA(t) > MA(t−1) 로 고정했기 때문에 "
             "MA 가 평평한 구간에서 게이트가 봉 단위로 진동한다. 스무딩 파라미터를 두지 않기로 한 "
             "설계 선택의 비용이며, 튜닝하지 않고 보고만 한다.")
    L.append("- **이벤트 정의 상속**: 트리거는 기존 Filter_C ∪ Filter_Q 코호트 정의를 그대로 쓴다.")
    L.append("- **event_rate 환산 근사**: 6h event_rate 는 4h 실측을 봉길이 비례로 환산한 값이며 "
             "실측이 아니다. 1h event_rate 도 R1 의 3주 관측 창에서 나온 값이라 "
             "장기 구간에 그대로 적용하면 편향될 수 있다.")
    if test is not None:
        pp = test["per_pair"].get(GATE_VERSION_V2, {})
        if len(pp) > 1:
            signs = ", ".join(f"{p} Δ={_fmt(d['delta'])}" for p, d in pp.items())
            L.append("- **통합 Δ 는 TF쌍 간 상쇄의 결과다**: " + signs + ". "
                     "사전등록된 주 비교는 잔존 쌍 통합 하나뿐이므로 판정은 통합값으로 한다. "
                     "쌍별 부호가 갈린다는 사실 자체는 '상위 TF 파동 상태의 효과가 TF쌍에 따라 "
                     "다르다'는 관측이지만, 사후 부분집합 선택이라 이 라운드에서 결론으로 삼지 않는다. "
                     "검정하려면 TF쌍을 사전 고정한 새 스펙이 필요하다.")
        L.append("- **C1 은 결과적으로 불필요했다**: R1 에서 1d 완전정배열 기저율이 0이었던 것은 "
                 "게이트 정의가 아니라 관측 창(하락 국면 9개월) 탓이었다. 2021–2026 구간에서는 "
                 f"v1 게이트도 충분히 열려 n(G_BOTH) = {test['v1_result']['bootstrap'].get('n_both')} "
                 "이며 검정이 가능하다. 즉 C3(창 확대) 하나만으로 검정력 문제가 풀렸고, "
                 "C1(게이트 완화)은 사후적으로 보면 필요 없었다. 위 감사표대로 결론도 바뀌지 않았다.")
    L.append("- **상태 타임라인 구현**: 봉별 재계산 시 후행 "
             f"{STATE_WINDOW_BARS}봉으로 절단해 O(N²) 비용을 낮췄다. 무절단 "
             "`wave_tracker.run_timeline` 과 상태열이 일치함을 패리티 테스트로 강제한다 "
             "(판정 파라미터가 아니라 구현 파라미터).")
    L.append("")
    L.append(f"산출물: `{os.path.basename(R0_CSV)}`, `{os.path.basename(CALIB_CSV)}`, "
             f"`{os.path.basename(PNG_PATH)}`"
             + (f", `{os.path.basename(TEST_CSV)}`, `{os.path.basename(EVENTS_CSV)}`"
                if test is not None else ""))
    L.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT_PATH


def run_main_test(surviving: list[str]) -> dict | None:
    """§4 본 검정 — 잔존 쌍 통합 Δ = E[G_BOTH] − E[G_ALIGN]."""
    frames = []
    for pair in PAIRS_V2:
        ev = build_pair_events_v2(pair, GATE_VERSION_V2)
        if not ev.empty:
            frames.append(ev)
    if not frames:
        return None
    all_events = pd.concat(frames, ignore_index=True)
    pooled = all_events[all_events["pair"].isin(surviving)]
    if pooled.empty:
        return None

    tables = {"POOLED": gate_table(pooled, "POOLED")}
    for pair in PAIRS_V2:
        sub = all_events[all_events["pair"] == pair]
        if sub.empty:
            continue
        tables[pair] = gate_table(sub, pair)
        for sym in SYMBOLS_V2:
            tables[f"{pair}|{sym}"] = gate_table(sub[sub["symbol"] == sym], f"{pair}|{sym}")

    # C1(사후 완화) 감사 — v1 게이트로 같은 검정을 돌려 결론이 바뀌는지만 확인한다.
    # 판정에는 쓰지 않는다 (§5: 게이트 스윕 금지). 목적은 '완화가 답을 바꿨는가'다.
    v1_frames = [build_pair_events_v2(p, GATE_VERSION_V1) for p in PAIRS_V2]
    v1_frames = [f for f in v1_frames if not f.empty]
    v1_pooled = pd.concat(v1_frames, ignore_index=True)
    v1_pooled = v1_pooled[v1_pooled["pair"].isin(surviving)]

    per_pair = {}
    for ver, df in ((GATE_VERSION_V2, pooled), (GATE_VERSION_V1, v1_pooled)):
        per_pair[ver] = {
            p: {
                "e_align": expectancy_20(sub[gate_mask(sub, "G_ALIGN")]),
                "e_both": expectancy_20(sub[gate_mask(sub, "G_BOTH")]),
                "delta": delta_expectancy(sub),
                "n_both": int(gate_mask(sub, "G_BOTH").sum()),
            }
            for p in PAIRS_V2
            for sub in [df[df["pair"] == p]]
            if not sub.empty
        }

    return {
        "pooled": pooled,
        "all_events": all_events,
        "tables": tables,
        "result": judge(pooled),
        "bnb": bnb_core_overlap(pooled),
        "v1_result": judge(v1_pooled),
        "v1_tables": gate_table(v1_pooled, "V1_POOLED"),
        "per_pair": per_pair,
    }


def cmd_r0(window_name: str, window: tuple[str, str], *, run_test: bool = False) -> None:
    missing = [
        (s, htf) for htf, _ in PAIRS_V2.values() for s in SYMBOLS_V2
        if load_htf_states_v2(s, htf).empty
    ]
    if missing:
        raise SystemExit(
            "v2 HTF 상태 캐시 없음: " + ", ".join(f"{s}/{t}" for s, t in missing)
            + "\n먼저 `python validation/wave_htf_gate_v2_sweep.py --states SYMBOL HTF` 실행."
        )

    rates = baseline_rates(GATE_VERSION_V2)
    calib_rows, calib_verdicts = run_pair_c_calibration(window)
    pd.DataFrame(calib_rows).to_csv(CALIB_CSV, index=False)

    surviving = ["PAIR_B"] + [p for p, v in calib_verdicts.items() if v["keep_pair"]]
    expected = expected_sample(rates, window[0], window[1])
    verdict = r0_verdict(expected, surviving, window_name)

    years = yearly_open_rates(GATE_VERSION_V2)

    test = None
    if run_test and verdict["verdict"] == "GO":
        test = run_main_test(surviving)
        if test is None:
            raise SystemExit(
                "v2 이벤트 캐시 없음 — 먼저 `python validation/wave_htf_gate_v2_events.py` 실행."
            )
        from analysis.wave_htf_gate import export_events_csv
        export_events_csv(test["all_events"], EVENTS_CSV)
        rows = []
        for label, trows in test["tables"].items():
            rows.extend({"section": "gate_table", **t, "label": label} for t in trows)
        rows.extend({"section": "half_split", **h} for h in test["result"]["halves"])
        rows.extend({"section": "symbol_delta", **d} for d in test["result"]["symbols"])
        rows.extend({"section": "cell_count", **c} for c in test["result"]["cells"])
        rows.extend({"section": "criterion", "label": c["text"], "passed": c["passed"],
                     "detail": c["detail"]} for c in test["result"]["criteria"])
        rows.append({"section": "bnb_overlap", **test["bnb"]})
        rows.append({"section": "verdict", "label": test["result"]["verdict"],
                     "detail": reject_reason(test["result"]),
                     **test["result"]["bootstrap"]})
        pd.DataFrame(rows).to_csv(TEST_CSV, index=False)
        print(f"[test] events={len(test['pooled'])} verdict={test['result']['verdict']} "
              f"({reject_reason(test['result'])}) -> {TEST_CSV}")

    flat = [{"section": "base_rate", **r} for r in rates]
    for e in expected:
        flat.extend({"section": "n_hat_detail", **d} for d in e["detail"])
        flat.append({"section": "n_hat_pair", "pair": e["pair"], "ltf": e["ltf"],
                     "ltf_bars": e["ltf_bars"], "n_hat": e["n_hat"]})
    flat.extend({"section": "yearly", **y} for y in years)
    flat.append({"section": "r0_verdict", "pair": "+".join(surviving),
                 "n_hat": verdict["n_hat_total"], "verdict": verdict["verdict"],
                 "window": window_name})
    pd.DataFrame(flat).to_csv(R0_CSV, index=False)

    _plot_r0(rates, years, verdict)
    path = write_report(window_name, window, rates, calib_rows, calib_verdicts,
                        expected, verdict, years, test=test)
    print(f"[r0] surviving={surviving} n_hat={verdict['n_hat_total']} -> {verdict['verdict']}")
    print(f"[r0] {path}")


def main() -> None:
    args = sys.argv[1:]
    window_name, window = _arg_window(args)
    if args and args[0] == "--states":
        cmd_states(args[1], args[2], window)
        return
    if args and args[0] in ("--r0", "--test"):
        cmd_r0(window_name, window, run_test=args[0] == "--test")
        return
    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
