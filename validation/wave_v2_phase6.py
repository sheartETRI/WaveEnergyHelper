"""v2 PHASE6 (6차 위임 A + C) — temporal 사전 점검(A) + 기법0 관측 계기(C).

A(go/no-go) 결과가 NO-GO면 B(forward)를 수행하지 않고 C만 수행한다(위임 규정).
C는 v3 추세 레이어에도 필요한 관측 인프라 — 저널 컬럼·표시 전용, 게이트/필터/승격 금지.

- A: in_progress_p1군(사전 등록 필터) 전/후반 50:50 분할, 후반 mean≥+0.5% AND 후반 n≥20 → GO
- C: 기법0 관측 계기 구현 내역 + 추세상태/바닥폭 분포 스냅샷 (엔진 무수정 확인 포함)

산출물: validation/REPORT_V2_PHASE6.md
실행: `python validation/wave_v2_phase6.py`
"""
import logging
import os
import sys
import warnings
from collections import Counter, defaultdict
from statistics import mean, median

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.campaign_state_machine import ALL_SUFFIXES  # noqa: E402
from analysis.trend_layer import (  # noqa: E402
    TREND_FLOW,
    TREND_STOCH_SUFFIX,
    add_trend_observation,
    bottom_width,
    trend_state_at,
    trend_state_label,
)
from validation.wave_v2_phase2 import _pct, build  # noqa: E402
from validation.wave_v2_phase5 import reannotate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE6.md")

# A go/no-go 기준 (사전 등록, 변경 금지)
A_LATE_MIN_MEAN = 0.005
A_LATE_MIN_N = 20
TFS = ["1h", "4h", "1d"]


def _agg(nets):
    nets = [x for x in nets if x is not None]
    if not nets:
        return {"n": 0, "mean": None, "median": None, "win": None}
    return {"n": len(nets), "mean": mean(nets), "median": median(nets),
            "win": sum(1 for x in nets if x > 0) / len(nets)}


def temporal_split(comp, group_key):
    rs = sorted([r for r in comp if r["_concord_p1"] == group_key and r["net"] is not None],
                key=lambda x: x["res"].setup_ts)
    mid = len(rs) // 2
    return _agg([r["net"] for r in rs[:mid]]), _agg([r["net"] for r in rs[mid:]]), len(rs)


def _row(name, a):
    if a["mean"] is None:
        return f"| {name} | {a['n']} | — | — | — |"
    return f"| {name} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | {(a['win'] or 0)*100:.0f}% |"


def write_report(frames, records):
    comp = reannotate(records, frames)   # _concord_p1, _arr_p1_* 부착
    e_ip, l_ip, n_ip = temporal_split(comp, "in_progress")
    e_cf, l_cf, n_cf = temporal_split(comp, "confirmed")
    e_no, l_no, n_no = temporal_split(comp, "none")
    go = (l_ip["mean"] is not None and l_ip["mean"] >= A_LATE_MIN_MEAN and l_ip["n"] >= A_LATE_MIN_N)

    # TF별 in_progress 분포(부가 기록)
    tf_ip = Counter(r["tf"] for r in comp if r["_concord_p1"] == "in_progress")

    # C 관측 스냅샷: trend_state_at_entry / bottom_width (complete 캠페인)
    comp_all = [r for r in records if r["status"] == ST_COMPLETE]
    tstate = Counter()
    widths = []
    for r in comp_all:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        tstate[trend_state_label(trend_state_at(full, r["res"].setup_pos))] += 1
        pat = "db" if r["direction"] == "long" else "dt"
        bw = bottom_width(full, 10, pat, r["res"].setup_pos)
        if bw is not None:
            widths.append(bw)

    # C 관측 계기 검출 카운트(4층 스토캐 + MACD선 쌍봉), TF별
    obs_counts = defaultdict(lambda: {"stoch4_db": 0, "stoch4_dt": 0, "macd_dt": 0})
    for (sym, tf), full in frames.items():
        f2 = add_trend_observation(full.copy())
        sfx = TREND_STOCH_SUFFIX
        obs_counts[tf]["stoch4_db"] += int(f2[f"stoch_db_{sfx}"].notna().sum()) if f"stoch_db_{sfx}" in f2 else 0
        obs_counts[tf]["stoch4_dt"] += int(f2[f"stoch_dt_{sfx}"].notna().sum()) if f"stoch_dt_{sfx}" in f2 else 0
        obs_counts[tf]["macd_dt"] += int(f2["macd_dt"].notna().sum()) if "macd_dt" in f2 else 0

    w_stat = (min(widths), int(median(widths)), max(widths)) if widths else (0, 0, 0)

    L = [
        "# REPORT_V2_PHASE6 — temporal 사전 점검(A) + 기법0 관측 계기(C)\n",
        "선행: REPORT_V2_PHASE5(H2 통과: concordance_p1=in_progress, n=86). **엔진·검출기·게이트 무수정,",
        "저널 컬럼 추가만.** 사전 등록 필터(동결): `concordance_p1 == in_progress`.\n",
        "## A. temporal split 사전 점검 (go/no-go, 단발 기술통계)\n",
        "> **go/no-go 기준(사전 등록, 변경 금지)**: 후반 net mean ≥ +0.5% **AND** 후반 n ≥ 20.",
        "> GO → B(forward) 진행. NO-GO → B·forward 미수행, C만 수행하고 결론에 '전반 편중' 기록.\n",
        "in_progress군(n=86) 캠페인 시작시각 기준 전/후반 50:50 분할:",
        "",
        "| 구간 | n | net mean | net median | 승률 |",
        "|------|---|------|--------|------|",
        _row("in_progress 전반", e_ip),
        _row("in_progress 후반", l_ip),
        "",
        f"- **판정: {'GO' if go else 'NO-GO'}** — 후반 mean {_pct(l_ip['mean'])} "
        f"({'≥' if go else '<'} +0.50%), 후반 n {l_ip['n']} ({'≥' if l_ip['n'] >= A_LATE_MIN_N else '<'} 20)",
        "",
        "부가 기록(판정 아님) — confirmed·none 동일 분할:",
        "",
        "| 구간 | n | net mean | net median | 승률 |",
        "|------|---|------|--------|------|",
        _row("confirmed 전반", e_cf),
        _row("confirmed 후반", l_cf),
        _row("none 전반", e_no),
        _row("none 후반", l_no),
        "",
        "in_progress TF별 분포: " + (", ".join(f"{tf}={tf_ip.get(tf,0)}" for tf in TFS)),
        "",
    ]

    if go:
        L += [
            "## B. forward 검증 착수 (A GO)\n",
            "A가 GO이므로 B-1(실시간 태그 일치 증명)·B-2(forward 러너)·B-3(창·성공기준)·B-4(운영)를 진행한다.",
            "(본 자동 리포트는 A/C를 산출한다. B 러너는 별도 스크립트로 개시.)",
            "",
        ]
    else:
        L += [
            "## B. forward 검증 — **미수행 (A NO-GO)**\n",
            "사전 등록 규정에 따라 A가 NO-GO이므로 B(forward)·B-1~B-4를 수행하지 않는다.",
            "",
            "> **결론(A 경로)**: **필터 엣지가 전반 편중** — in_progress 필터의 우위(PHASE5 in-sample +2.18%)는",
            f"> 전반(mean {_pct(e_ip['mean'])})에 몰려 있고 후반(mean {_pct(l_ip['mean'])})은 게이트 미달이다.",
            "> **기법 1 + 상응 필터 forward 포기, v3(추세 레이어) 설계로 전환.** 아래 C는 v3에도 필요한",
            "> 관측 인프라이므로 그대로 수행해 데이터 축적을 시작한다.",
            "",
        ]

    L += [
        "## C. 기법0 추세 레이어 관측 계기 (관측·저널·표시 전용 — 게이트/필터 금지)\n",
        "⚠ **원 동결 스펙(`기법0_추세레이어_동결스펙.md`)이 리포에 부재** → 위임 §C 열거에 따른 보수적",
        "형식화로 구현. T0~T4 전이 의미·slope 임계는 스펙 확보 시 재조정(미결). 현재는 관측 컬럼일 뿐이다.",
        "",
        "| §C | 항목 | 구현 | 비고 |",
        "|---|---|---|---|",
        "| 1 | 스토캐 4층 (40,20,20) + 4패턴 | `trend_layer.add_trend_stoch_layer` | ★엔진 STOCH_LAYERS 미변경(관측 suffix) |",
        "| 2 | MA20 이평선 패턴 | 기존 CORE_MA_PERIODS/DEFAULT_MA_PERIODS에 포함(ma20_db/dt) | 신규 코드 불요(확인) |",
        "| 3 | MACD선 피봇 + 쌍봉(LH) | `trend_layer.add_macd_line_patterns` | 시계열 검출 재사용 |",
        "| 4 | slope 판정기 + 계단식 GC | `ma_slope`/`slope_sign`/`stepwise_gc_at` | `TREND_SLOPE_N`, MA60/120 |",
        "| 5 | 추세 상태 기계 T0~T4 | `TREND_FLOW`(데이터 선언) + `trend_state_at` | 전이표=데이터, 관측 |",
        "| 6 | 저널 `trend_state_at_entry`,`bottom_width` | campaign_score/campaign_backtest 배선 | S0 봉 기준 |",
        "",
        f"**엔진 무영향 검증**: 4층 suffix `{TREND_STOCH_SUFFIX}` ∈ ALL_SUFFIXES? "
        f"**{'예(위반!)' if TREND_STOCH_SUFFIX in ALL_SUFFIXES else '아니오(정상 — 상태 기계 불변)'}** "
        "(단위 테스트 `test_trend_layer.py::test_engine_invariant_4th_layer_not_in_engine`).",
        "",
        "### 추세 상태 기계 T0~T4 (전이표 데이터 선언)",
        "",
        "| 상태 | 라벨 | 배열 | 기울기 |",
        "|---|---|---|---|",
    ]
    for t in TREND_FLOW:
        L.append(f"| {t['state']} | {t['label']} | {t['arrange']} | {t['slope']} |")

    L += [
        "",
        "### 관측 스냅샷 — S0 진입 시 추세 상태 분포 (complete 캠페인)",
        "",
        "| 추세 상태 | 건수 |",
        "|---|---|",
    ]
    for lab in ("하락", "바닥형성", "상승전환", "상승", "천장형성", "미정"):
        if tstate.get(lab):
            L.append(f"| {lab} | {tstate[lab]} |")
    L += [
        "",
        f"- **bottom_width**(S0 MA10 패턴 바닥 폭, 봉): min {w_stat[0]} · median {w_stat[1]} · max {w_stat[2]} (n={len(widths)})",
        "",
        "### 관측 계기 검출 카운트 (이력 전체, TF별)",
        "",
        "| TF | 스토캐4층 쌍바닥 | 스토캐4층 쌍봉 | MACD선 쌍봉 |",
        "|---|---|---|---|",
    ]
    for tf in TFS:
        c = obs_counts.get(tf, {})
        L.append(f"| {tf} | {c.get('stoch4_db',0)} | {c.get('stoch4_dt',0)} | {c.get('macd_dt',0)} |")

    L += [
        "",
        "## 미결 · 제안 (스코프 밖 — 기록만)\n",
        "- **기법0 동결 스펙 부재**: `기법0_추세레이어_동결스펙.md`가 리포에 없어 T0~T4 전이 의미·slope 임계·",
        "  계단식 GC 정의를 위임 §C 열거로 보수적 구현했다. 스펙 확보 시 정의 재조정 필요(관측 컬럼이라 안전).",
        "- **C는 관측 전용**: trend_state·bottom_width로 캠페인 필터링/승격 금지(위임 규정). v3 게이트 미정.",
        "- **A NO-GO 확정**: in_progress 필터는 전반 편중 — forward 미개시. B-3 발생률/도달 예상은 미산출(B 스킵).",
        "- 통과 태그(PHASE5 H2)의 in-sample 재채점·필터 백테스트는 하지 않음(약속 유지).",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return go, l_ip, tstate, len(widths)


def main():
    frames, records, _ = build()
    go, l_ip, tstate, nw = write_report(frames, records)
    print(f"A go/no-go: {'GO' if go else 'NO-GO'} (late in_progress mean={l_ip['mean']}, n={l_ip['n']})")
    print(f"trend_state dist(S0): {dict(tstate)}  bottom_width n={nw}")
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
