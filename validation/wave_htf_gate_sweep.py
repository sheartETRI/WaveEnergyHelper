"""Wave HTF Gate 스윕 · REPORT_WAVE_HTF_GATE.md · wave_htf_gate.png.

SPEC_WAVE_HTF_GATE R1 실행기.

사용법:
    python validation/wave_htf_gate_sweep.py --states SYMBOL HTF   # HTF 상태 캐시 생성
    python validation/wave_htf_gate_sweep.py --calib               # §2 캘리브레이션만
    python validation/wave_htf_gate_sweep.py                       # R1 전체 (캐시 필요)
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
    GATES,
    MIN_CELL_N,
    PAIR_X,
    PAIRS,
    SYMBOLS,
    TRIGGER_LABEL,
    build_htf_states,
    bnb_core_overlap,
    build_pair_events,
    calibration_verdict,
    export_events_csv,
    fractal_correlation,
    gate_availability,
    gate_table,
    half_split_deltas,
    htf_state_path,
    judge,
    load_forward_journal,
    load_htf_states,
    symbol_deltas,
    trigger_events,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_CSV = os.path.join(OUT_DIR, "wave_htf_gate_calibration.csv")
EVENTS_CSV = os.path.join(OUT_DIR, "wave_htf_gate_events.csv")
TABLE_CSV = os.path.join(OUT_DIR, "wave_htf_gate.csv")
REPORT_PATH = os.path.join(OUT_DIR, "REPORT_WAVE_HTF_GATE.md")
PNG_PATH = os.path.join(OUT_DIR, "wave_htf_gate.png")


def _fmt(v, d=4, pct=False):
    if v is None or (isinstance(v, float) and (np.isnan(v))):
        return "—"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{v:.{d}f}%" if pct else f"{v:.{d}f}"


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# ----------------------------------------------------------------- states
def cmd_states(symbol: str, htf: str) -> None:
    df = build_htf_states(symbol, htf)
    path = htf_state_path(symbol, htf)
    df.to_csv(path, index=False)
    counts = df["htf_state"].value_counts().to_dict() if not df.empty else {}
    print(f"[states] {symbol} {htf} rows={len(df)} -> {path}")
    print(f"[states] {counts}")
    if not df.empty:
        print(f"[states] g_align={int(df['g_align'].sum())} "
              f"g_wave={int(df['g_wave'].sum())} g_both={int(df['g_both'].sum())}")


# ------------------------------------------------------------ calibration
def run_calibration() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    verdicts: dict = {}
    for pair, (htf, ltf) in PAIRS.items():
        pair_rows = []
        for sym in SYMBOLS:
            r = fractal_correlation(sym, htf, ltf)
            r["pair"] = pair
            rows.append(r)
            pair_rows.append(r)
        verdicts[pair] = calibration_verdict(pair_rows)
    return rows, verdicts


# ------------------------------------------------------------------ main
def build_all_events() -> pd.DataFrame:
    journal = load_forward_journal()
    frames = []
    for pair in PAIRS:
        ev = build_pair_events(pair, journal)
        if not ev.empty:
            frames.append(ev)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _plot(pooled: pd.DataFrame, tables: dict, result: dict) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))

    ax = axes[0, 0]
    pooled_rows = tables["POOLED"]
    vals = [r["expectancy_20"] or 0.0 for r in pooled_rows]
    ns = [r["n"] for r in pooled_rows]
    bars = ax.bar(GATES, vals, color=["#BDBDBD", "#3867F2", "#FFB74D", "#2E7D32"])
    for b, v, n in zip(bars, vals, ns):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}\nn={n}",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("expectancy_20 by gate (PAIR_A + PAIR_B pooled)")
    ax.set_ylabel("expectancy_20 (%)")

    ax = axes[0, 1]
    pairs = list(PAIRS)
    width = 0.2
    xs = np.arange(len(pairs))
    for i, gate in enumerate(GATES):
        ys = []
        for p in pairs:
            row = next((r for r in tables[p] if r["gate"] == gate), None)
            ys.append((row or {}).get("expectancy_20") or 0.0)
        ax.bar(xs + (i - 1.5) * width, ys, width, label=gate)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{p}\n{PAIRS[p][0]}→{PAIRS[p][1]}" for p in pairs])
    ax.axhline(0, color="black", lw=0.8)
    ax.legend(fontsize=8)
    ax.set_title("expectancy_20 by pair × gate")

    ax = axes[1, 0]
    syms = result["symbols"]
    xs = np.arange(len(syms))
    ax.bar(xs - 0.2, [s["e_align"] or 0.0 for s in syms], 0.4, label="G_ALIGN", color="#3867F2")
    ax.bar(xs + 0.2, [s["e_both"] or 0.0 for s in syms], 0.4, label="G_BOTH", color="#2E7D32")
    ax.set_xticks(xs)
    ax.set_xticklabels([s["symbol"].replace("USDT", "") for s in syms])
    ax.axhline(0, color="black", lw=0.8)
    ax.legend(fontsize=8)
    ax.set_title("symbol: G_ALIGN vs G_BOTH")

    ax = axes[1, 1]
    halves = result["halves"]
    labels = [h["split"] for h in halves] + ["pooled"]
    deltas = [h["delta"] or 0.0 for h in halves] + [result["bootstrap"].get("delta") or 0.0]
    colors = ["#2E7D32" if d > 0 else "#EF5350" for d in deltas]
    ax.bar(labels, deltas, color=colors)
    ci = result["bootstrap"]
    if ci.get("ci_low") is not None:
        ax.errorbar(
            [len(labels) - 1], [ci["delta"]],
            yerr=[[ci["delta"] - ci["ci_low"]], [ci["ci_high"] - ci["delta"]]],
            fmt="o", color="black", capsize=5,
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"Δ = E[G_BOTH] − E[G_ALIGN]   verdict={result['verdict']}")
    if ci.get("delta") is None:
        ax.text(0.5, 0.5,
                f"Δ undefined\nn(G_ALIGN)={ci.get('n_align', 0)}, n(G_BOTH)={ci.get('n_both', 0)}",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=13, color="#EF5350", weight="bold")

    fig.suptitle(f"WAVE HTF GATE R1 — trigger: {TRIGGER_LABEL}", fontsize=13)
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
    calib_rows: list[dict],
    calib_verdicts: dict,
    tables: dict,
    result: dict,
    result_literal: dict,
    surviving: list[str],
    pooled: pd.DataFrame,
    pair_x_note: str,
) -> str:
    L: list[str] = []
    L.append("# REPORT_WAVE_HTF_GATE")
    L.append("")
    L.append("SPEC_WAVE_HTF_GATE R1 — 상위 TF 파동 상태 게이트의 배열 게이트 대비 증분 검증.")
    L.append("")

    # 1. 판정
    L.append("## 1. 판정")
    L.append("")
    L.append(f"**{result['verdict']}**")
    L.append("")
    discarded = [p for p in PAIRS if p not in surviving]
    L.append(
        f"주 비교 대상: {' + '.join(surviving) if surviving else '(없음)'} 통합. "
        + (f"§2 캘리브레이션에서 {', '.join(discarded)} 는 corr < 0.90 으로 폐기되어 "
           "주 비교에서 제외했다 (§2 규칙 그대로 적용, 대체 쌍 탐색 없음). "
           "§4.1 문면의 'PAIR_A + PAIR_B 통합' 값도 아래에 함께 보고한다."
           if discarded else "두 쌍 모두 §2 를 통과했다.")
    )
    L.append("")
    L.append("| # | 기준 (§4.1) | 결과 | 값 |")
    L.append("|---|---|---|---|")
    for c in result["criteria"]:
        L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
    L.append("")
    if discarded:
        L.append("### 참고: §4.1 문면 그대로 (PAIR_A + PAIR_B 통합, §2 폐기쌍 포함)")
        L.append("")
        L.append(f"판정: **{result_literal['verdict']}**")
        L.append("")
        L.append("| # | 기준 (§4.1) | 결과 | 값 |")
        L.append("|---|---|---|---|")
        for c in result_literal["criteria"]:
            L.append(f"| {c['id']} | {c['text']} | {_mark(c['passed'])} | {c['detail']} |")
        L.append("")
    boot = result["bootstrap"]
    L.append(
        f"주 비교: Δ = E[G_BOTH] − E[G_ALIGN] = **{_fmt(boot.get('delta'))}** "
        f"(bootstrap {boot.get('n_boot')}회, 95% CI "
        f"[{_fmt(boot.get('ci_low'))}, {_fmt(boot.get('ci_high'))}], "
        f"n_G_ALIGN={boot.get('n_align')}, n_G_BOTH={boot.get('n_both')})"
    )
    L.append("")
    unidentifiable = not boot.get("n_align")
    if unidentifiable:
        L.append("**REJECT 사유는 '증분 없음'이 아니라 '식별 불가'다.** "
                 "관측 창 안에서 베이스라인 게이트 G_ALIGN 이 걸린 이벤트가 0건이므로 "
                 "E[G_ALIGN] · E[G_BOTH] 가 정의되지 않고, 기준 1·3·4 는 값 부재로 FAIL 처리됐다. "
                 "즉 이번 라운드는 H1 을 반증한 것이 아니라 **검정할 표본이 없었다**. "
                 "원인은 §6 진단표에 있다.")
        L.append("")
    if result["verdict"] == "REJECT" and result_literal["verdict"] == "REJECT":
        L.append("**결론(§4.1 사전등록 문구): TF 연계 게이트는 배열 게이트의 재포장 — 기록 후 종료.** "
                 "주 비교와 §4.1 문면 통합값이 모두 REJECT 이다. "
                 "§5 정지점에 따라 라운드를 종료하고 관측 도구 포지셔닝을 유지한다."
                 + (" 다만 위 식별 불가 사유상 이 기록은 '재포장임이 입증됐다'가 아니라 "
                    "'재포장이 아님을 보이지 못했다'로 읽어야 한다." if unidentifiable else ""))
    elif result["verdict"] == "REJECT":
        L.append("**결론: H0 유지 (REJECT).** §5 정지점에 따라 라운드를 종료한다.")
    else:
        L.append("**결론: H1 채택.** 산출물은 라이브 워치리스트의 후보 필터 승격까지로 한정한다 (§5).")
    L.append("")

    # 2. 캘리브레이션
    L.append("## 2. §2 F5-c 캘리브레이션 상관표")
    L.append("")
    L.append("corr( HTF 소파동 %K(5,3,3) , HTF 봉 마감 시점으로 asof-align 한 LTF 대파동 %K(20,10,10) )")
    L.append("")
    L.append("| pair | HTF→LTF | symbol | n | corr | 구간 |")
    L.append("|---|---|---|---|---|---|")
    for r in calib_rows:
        span = ""
        if r.get("overlap_start") is not None:
            span = f"{pd.Timestamp(r['overlap_start']).date()} ~ {pd.Timestamp(r['overlap_end']).date()}"
        L.append(
            f"| {r['pair']} | {r['htf']}→{r['ltf']} | {r['symbol']} | {r['n']} | "
            f"{_fmt(r.get('corr'))} | {span} |"
        )
    L.append("")
    L.append("| pair | mean corr | min corr | 임계 | 판정 |")
    L.append("|---|---|---|---|---|")
    for pair, v in calib_verdicts.items():
        L.append(
            f"| {pair} | {_fmt(v['mean_corr'])} | {_fmt(v['min_corr'])} | "
            f"{v['threshold']:.2f} | {'쌍 유지' if v['keep_pair'] else '쌍 폐기(보고만)'} |"
        )
    L.append("")

    # 3. 4열 비교표
    L.append("## 3. 4열 비교표 (무게이트 / G_ALIGN / G_WAVE / G_BOTH)")
    L.append("")
    L.append(f"트리거: {TRIGGER_LABEL} (기존 Filter_C ∪ Filter_Q 코호트, 신규 검출 없음)")
    L.append("")
    for key in ["POOLED"] + list(PAIRS):
        title = "PAIR_A + PAIR_B 통합" if key == "POOLED" else f"{key} (HTF={PAIRS[key][0]}, LTF={PAIRS[key][1]})"
        L.append(f"### {title}")
        L.append("")
        L.extend(_gate_table_md(tables[key]))
        L.append("")
    for key in sorted(k for k in tables if "|" in k):
        L.append(f"### {key}")
        L.append("")
        L.extend(_gate_table_md(tables[key]))
        L.append("")

    L.append("### PAIR_X (HTF=1d, LTF=6h) — 참고, 판정 미사용")
    L.append("")
    L.append(pair_x_note)
    L.append("")

    L.append("### BNB 단독 — Filter_BNB_CORE 중첩률 (§4.2)")
    L.append("")
    L.append("G_BOTH 가 기존 BNB 필터의 대리변수인지 확인. "
             "Filter_BNB_CORE = BNBUSDT & mf>=5 & struct>=5.")
    L.append("")
    L.append("| 범위 | n(BNB) | n(BNB_CORE) | n(G_BOTH) | 교집합 | Jaccard | "
             "P(CORE\\|BOTH) | P(BOTH\\|CORE) | E[BNB_CORE] | E[G_BOTH] |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for scope, sub in [("주 비교", pooled[pooled["pair"].isin(surviving)] if surviving else pooled.iloc[0:0])] \
            + [(p, pooled[pooled["pair"] == p]) for p in PAIRS]:
        o = bnb_core_overlap(sub)
        if not o.get("n_bnb"):
            L.append(f"| {scope} | 0 | — | — | — | — | — | — | — | — |")
            continue
        L.append(
            f"| {scope} | {o['n_bnb']} | {o['n_bnb_core']} | {o['n_g_both']} | "
            f"{o['n_intersection']} | {_fmt(o['jaccard'])} | {_fmt(o['p_core_given_both'])} | "
            f"{_fmt(o['p_both_given_core'])} | {_fmt(o['e_bnb_core'])} | {_fmt(o['e_g_both'])} |"
        )
    L.append("")

    # 4. half-split
    L.append("## 4. half-split 표")
    L.append("")
    L.append("| split | n | 구간 | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |")
    L.append("|---|---|---|---|---|---|---|---|")
    for h in result["halves"]:
        span = ""
        if h.get("ts_min") is not None:
            span = f"{pd.Timestamp(h['ts_min']).date()} ~ {pd.Timestamp(h['ts_max']).date()}"
        L.append(
            f"| {h['split']} | {h['n']} | {span} | {h['n_align']} | {h['n_both']} | "
            f"{_fmt(h['e_align'])} | {_fmt(h['e_both'])} | {_fmt(h['delta'])} |"
        )
    L.append("")
    L.append("### 심볼별 Δ")
    L.append("")
    L.append("| symbol | n | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |")
    L.append("|---|---|---|---|---|---|---|")
    for s in result["symbols"]:
        L.append(
            f"| {s['symbol']} | {s['n']} | {s['n_align']} | {s['n_both']} | "
            f"{_fmt(s['e_align'])} | {_fmt(s['e_both'])} | {_fmt(s['delta'])} |"
        )
    L.append("")
    L.append("### 셀별 G_BOTH 표본 수 (§4.1-2)")
    L.append("")
    L.append("| cell | level | n(G_ALIGN) | n(G_BOTH) | n>=30 |")
    L.append("|---|---|---|---|---|")
    for c in result["cells"]:
        L.append(
            f"| {c['cell'].replace('|', ' / ')} | {c['level']} | {c['n_align']} | "
            f"{c['n_both']} | {_mark(c['n_both'] >= MIN_CELL_N)} |"
        )
    L.append("")

    # 5. 한계
    L.append("## 5. 한계")
    L.append("")
    L.append("- **게이트 지연 1 HTF봉**: §3.4 asof 규칙상 이벤트 시각 t 에 대해 "
             "close_time < t 인 마감봉만 사용한다. 진행 중 HTF 봉의 상태는 반영되지 않으며, "
             "게이트는 최대 1 HTF 봉만큼 지연된다 (설계 비용으로 수용).")
    L.append("- **이벤트 정의 상속**: 트리거는 기존 forward journal 이벤트(RULE_C ∪ quality>=4)를 "
             "그대로 상속한다. 신규 검출기·신규 이벤트 정의는 만들지 않았다.")
    if boot.get("ci_low") is not None:
        L.append("- **표본 축소에 따른 CI 폭**: G_ALIGN → G_BOTH 로 좁히면서 표본이 "
                 f"{boot.get('n_align')} → {boot.get('n_both')} 로 줄었고, "
                 f"Δ 의 95% CI 폭은 {_fmt(boot['ci_high'] - boot['ci_low'])} 이다. "
                 "이 폭 안에서는 방향성 주장을 하지 않는다.")
    else:
        L.append("- **표본 축소가 아니라 표본 부재**: G_ALIGN 코호트가 0건이라 CI 자체를 낼 수 없다. "
                 "관측 창을 넓히지 않는 한 이 비교는 표본 수 문제로 계속 식별 불가다.")
    L.append("- **관측 창 불일치**: LTF 이벤트는 기존 journal 의 관측 창(1h: 약 3주, 4h: 약 3개월)에 "
             "묶여 있다. TF쌍별 표본 기간이 다르므로 PAIR_A/PAIR_B 통합값은 기간 가중이 균등하지 않다.")
    L.append("- **§4.1-2 셀 정의**: 스펙의 '셀'을 TF쌍 단위로 읽었다. TF쌍×심볼 단위 표본 수도 "
             "위 표에 함께 보고한다.")
    L.append("- **베이스라인 게이트 공집합**: 본 라운드 관측 창에서 G_ALIGN 이 걸린 이벤트가 0건이라 "
             "주 비교가 식별되지 않았다. 이는 게이트의 효과 크기가 아니라 관측 창 커버리지 문제이며, "
             "§6 부록에 봉 단위 가용성을 실었다." if not boot.get("n_align") else
             "- **베이스라인 게이트 희소성**: G_ALIGN 이 열린 이벤트는 "
             f"{boot.get('n_align')}건이다. §6 부록에 봉 단위 가용성을 실었다.")
    L.append("- **§4.3 부차 연구 미실행**: §5 가 정의한 R1 범위는 §2 캘리브레이션 + §4.1 주 비교다. "
             "§4.3(LTF 중파동 쌍봉 청산 vs POLICY_H)은 선택 실행 항목이므로 R1 에 포함하지 않았다.")
    L.append("- **§2 와 §4.1 의 문면 충돌**: §2 는 corr < 0.90 인 쌍을 폐기하라고 하고, "
             "§4.1 은 'PAIR_A + PAIR_B 통합'을 주 비교로 지정한다. 본 라운드에서 PAIR_A 가 "
             "폐기되었으므로 주 비교는 잔존 쌍만으로 계산하고, §4.1 문면 그대로의 통합값도 "
             "§1 에 함께 실었다. 기준·게이트·TF쌍 정의는 변경하지 않았다.")
    L.append("")
    L.append("")
    # 6. 진단 (스펙 §7 고정 순서 뒤에 붙이는 부록)
    L.append("## 6. 부록 — 게이트 가용성 진단 (판정 미사용)")
    L.append("")
    L.append("게이트가 애초에 열리는 구간이 있었는지, 그 구간이 LTF 이벤트 관측 창과 겹치는지 확인한다. "
             "HTF 봉 단위 카운트이며 이벤트 가중이 아니다.")
    L.append("")
    L.append("| pair | HTF | symbol | HTF봉 | align | wave | both | 이벤트창 봉 | 창내 align | 창내 wave | 창내 both |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for pair, (htf, ltf) in PAIRS.items():
        sub = pooled[pooled["pair"] == pair]
        for r in gate_availability(htf, sub):
            if not r.get("bars"):
                L.append(f"| {pair} | {htf} | {r['symbol']} | 0 | — | — | — | — | — | — | — |")
                continue
            L.append(
                f"| {pair} | {htf} | {r['symbol']} | {r['bars']} | {r['bars_align']} | "
                f"{r['bars_wave']} | {r['bars_both']} | {r.get('win_bars', '—')} | "
                f"{r.get('win_align', '—')} | {r.get('win_wave', '—')} | {r.get('win_both', '—')} |"
            )
    L.append("")
    L.append("이벤트 관측 창은 각 TF쌍의 LTF 이벤트 시각 범위다 "
             "(PAIR_A 4h 이벤트: 약 3개월, PAIR_B 1h 이벤트: 약 3주).")
    L.append("")

    L.append(f"산출물: `{os.path.basename(EVENTS_CSV)}`, `{os.path.basename(TABLE_CSV)}`, "
             f"`{os.path.basename(CALIB_CSV)}`, `{os.path.basename(PNG_PATH)}`")
    L.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return REPORT_PATH


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--states":
        cmd_states(args[1], args[2])
        return

    calib_rows, calib_verdicts = run_calibration()
    pd.DataFrame(calib_rows).to_csv(CALIB_CSV, index=False)
    print(f"[calib] -> {CALIB_CSV}")
    for pair, v in calib_verdicts.items():
        print(f"[calib] {pair} mean={v['mean_corr']} min={v['min_corr']} keep={v['keep_pair']}")
    if args and args[0] == "--calib":
        return

    missing = [
        (s, htf) for htf, _ in PAIRS.values() for s in SYMBOLS
        if load_htf_states(s, htf).empty
    ]
    if missing:
        raise SystemExit(
            "HTF 상태 캐시 없음: "
            + ", ".join(f"{s}/{t}" for s, t in missing)
            + "\n먼저 `python validation/wave_htf_gate_sweep.py --states SYMBOL HTF` 실행."
        )

    pooled = build_all_events()
    if pooled.empty:
        raise SystemExit("이벤트 없음")
    export_events_csv(pooled, EVENTS_CSV)
    print(f"[events] rows={len(pooled)} -> {EVENTS_CSV}")

    tables = {"POOLED": gate_table(pooled, "POOLED")}
    for pair in PAIRS:
        sub = pooled[pooled["pair"] == pair]
        tables[pair] = gate_table(sub, pair)
        for sym in SYMBOLS:
            tables[f"{pair}|{sym}"] = gate_table(sub[sub["symbol"] == sym], f"{pair}|{sym}")

    # §2 에서 폐기된 TF쌍은 주 비교에서 제외한다 (기준 변경 아님 — §2 규칙 적용).
    surviving = [p for p, v in calib_verdicts.items() if v["keep_pair"]]
    primary = pooled[pooled["pair"].isin(surviving)] if surviving else pooled.iloc[0:0]
    result = judge(primary) if not primary.empty else judge(pooled.iloc[0:0])
    result_literal = judge(pooled)
    print(f"[judge] surviving={surviving} primary_n={len(primary)}")

    flat = []
    for label, rows in tables.items():
        for r in rows:
            flat.append({"section": "gate_table", **r, "label": label})
    for h in result["halves"]:
        flat.append({"section": "half_split", **h})
    for s in result["symbols"]:
        flat.append({"section": "symbol_delta", **s})
    for c in result["cells"]:
        flat.append({"section": "cell_count", **c})
    for c in result["criteria"]:
        flat.append({"section": "criterion", "label": c["text"],
                     "passed": c["passed"], "detail": c["detail"]})
    for c in result_literal["criteria"]:
        flat.append({"section": "criterion_literal_pooled", "label": c["text"],
                     "passed": c["passed"], "detail": c["detail"]})
    flat.append({"section": "verdict", "label": result["verdict"],
                 "detail": "+".join(surviving), **result["bootstrap"]})
    flat.append({"section": "verdict_literal_pooled", "label": result_literal["verdict"],
                 "detail": "PAIR_A+PAIR_B", **result_literal["bootstrap"]})
    pd.DataFrame(flat).to_csv(TABLE_CSV, index=False)
    print(f"[table] -> {TABLE_CSV}")

    journal = load_forward_journal()
    x_events = trigger_events(journal, PAIR_X[1])
    pair_x_note = (
        f"NOT EVALUABLE — 현재 파이프라인 산출물에 {PAIR_X[1]} 이벤트가 없다 "
        f"(forward journal timeframe = 1h/4h/1d, {PAIR_X[1]} = {len(x_events)}건). "
        "신규 이벤트 검출 로직 작성은 §3.3에서 금지되어 있고 PAIR_X 는 판정에 미사용이므로, "
        "R1 에서는 미평가로 기록한다."
    )

    _plot(pooled, tables, result)
    print(f"[png] -> {PNG_PATH}")
    path = write_report(calib_rows, calib_verdicts, tables, result, result_literal,
                        surviving, pooled, pair_x_note)
    print(f"[report] -> {path}")
    print(f"[verdict] {result['verdict']}")


if __name__ == "__main__":
    main()
