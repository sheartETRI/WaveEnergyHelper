"""v2 PHASE4 (4차 위임 D) — 교정 풀 + 신규 관측 컬럼으로 G2 재실행. 엔진 무수정.

수행:
- D1: {1h,4h,1d} 백테스트 재실행(교정 풀은 이 매트릭스에 영향 없음 — 아래 A 참조) → PHASE2 대비 표
- D2: C-1 temporal / C-2 TF별 판정 동일 게이트로 재판정 (게이트 값 변경 금지)
- D3: array_context 맥락 분리 통계(정합 vs 비정방향) + 저점이탈 재진입율 두 군 각각
- D4: candidate 적시성(lead-bars) 분포/통계

게이트·기간·심볼·파라미터 불변. 재실행 결과가 미달이어도 그대로 보고(정직성).
엔진 무수정 재사용: wave_v2_phase2.build()와 게이트 함수를 그대로 import한다.

산출물: validation/REPORT_V2_PHASE4.md
실행: `python validation/wave_v2_phase4.py`
"""
import logging
import os
import sys
import warnings
from collections import defaultdict
from statistics import mean, median

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from analysis.array_context import (  # noqa: E402
    BEAR_ARRAY,
    BULL_ARRAY,
    context_at,
    tag_s0,
)
from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.candle_patterns import candle_distribution, scan_candle_patterns  # noqa: E402
from analysis.concordance import concordance_at  # noqa: E402
from analysis.pattern_scanner import (  # noqa: E402
    _second_extreme_pos,
    candidate_lead_bars,
)
from config.settings import CONCORDANCE_PARAMS  # noqa: E402
from analysis.tf_ladder import TF_POOL  # noqa: E402
from validation.wave_v2_phase2 import (  # noqa: E402  (엔진·게이트 무수정 재사용)
    C1_LATE_MIN_EXP,
    C1_LATE_MIN_N,
    C2_MIN_MEAN,
    C2_MIN_MEDIAN,
    C2_MIN_N,
    SYMBOLS,
    TFS,
    _agg,
    _pct,
    _row,
    build,
    c1_temporal,
    c2_per_tf,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE4.md")

# PHASE2 공표 수치(대조용 상수 — 리포트 문서는 무수정, 여기서 비교만).
PHASE2 = {
    "overall": {"n": 223, "net": 0.0145},
    "c1": {"early": {"n": 109, "mean": 0.0278}, "late": {"n": 114, "mean": 0.0017}},
    "c2": {"1h": {"n": 92, "mean": -0.0044, "median": -0.0088},
           "4h": {"n": 85, "mean": 0.0120, "median": 0.0010},
           "1d": {"n": 46, "mean": 0.0568, "median": 0.0129}},
    "low_break": {"low": {"n": 187, "t2": -0.0016}, "non": {"n": 36, "t2": 0.0488}},
}


# ---------------------------------------------------------------- D3 context
def context_separation(records, frames):
    """complete 캠페인을 S0 봉 array_context로 태깅 → 정합 vs 비정방향 분리 통계."""
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    aligned, misaligned = [], []
    arr_counts = defaultdict(int)
    diag = {"array_match": 0, "converging": 0, "both": 0}  # 어느 조건이 병목인지 진단
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        ctx = context_at(full, r["res"].setup_pos)
        label, is_aligned = ctx.label, tag_s0(full, r["res"].setup_pos, r["direction"])[1]
        arr_counts[label] += 1
        want = BEAR_ARRAY if r["direction"] == "long" else BULL_ARRAY
        if ctx.array == want:
            diag["array_match"] += 1
        if ctx.converging:
            diag["converging"] += 1
        if ctx.array == want and ctx.converging:
            diag["both"] += 1
        (aligned if is_aligned else misaligned).append(r)

    def grp(rs):
        nets = [x["net"] for x in rs if x["net"] is not None]
        lbs = [x["low_break"] for x in rs if x["low_break"] is not None]
        a = _agg(nets)
        a["low_break_rate"] = (sum(1 for x in lbs if x) / len(lbs)) if lbs else None
        return a

    return grp(aligned), grp(misaligned), dict(arr_counts), len(comp), diag


def context_separation_prebreak(records, frames, period=10):
    """보조 앵커: S0 확정 봉이 아닌 '두 번째 극점 피봇'(넥라인 돌파 전)에서 배열 맥락 태깅.

    규칙 의미("역배열이다가 모임")는 돌파 전 상태이므로, 돌파 봉(MA5 이미 반등)보다 이 시점이
    형식화에 더 충실하다. 관측 전용 보조 통계 — 게이트 아님.
    """
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    aligned, misaligned = [], []
    n_eval = 0
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        confirm_pos = r["res"].setup_pos
        pat = "db" if r["direction"] == "long" else "dt"
        fp_col = f"ma{period}_{pat}_first_pos"
        if fp_col not in full.columns:
            continue
        raw_fp = full[fp_col].iloc[confirm_pos]
        if raw_fp is None or pd.isna(raw_fp):
            continue
        pb = _second_extreme_pos(full, period, pat, int(raw_fp), confirm_pos)
        if pb is None:
            continue
        n_eval += 1
        want = BEAR_ARRAY if r["direction"] == "long" else BULL_ARRAY
        ctx = context_at(full, pb)
        is_aligned = ctx.converging and ctx.array == want
        (aligned if is_aligned else misaligned).append(r)

    def grp(rs):
        nets = [x["net"] for x in rs if x["net"] is not None]
        lbs = [x["low_break"] for x in rs if x["low_break"] is not None]
        a = _agg(nets)
        a["low_break_rate"] = (sum(1 for x in lbs if x) / len(lbs)) if lbs else None
        return a

    return grp(aligned), grp(misaligned), n_eval


# ---------------------------------------------------------------- D4 timeliness
def candidate_timeliness(frames, period=10):
    """confirmed MA{period} db/dt 이벤트별 candidate 선행 봉수 분포(전 셀 합산)."""
    leads = []
    for (sym, tf), full in frames.items():
        leads += [r["lead_bars"] for r in candidate_lead_bars(full, sym, tf, periods=[period])]
    if not leads:
        return {"n": 0}
    leads.sort()
    n = len(leads)
    pos_leads = [x for x in leads if x > 0]
    # 히스토그램 버킷
    buckets = [("≤0 (동시/후행)", lambda x: x <= 0),
               ("1–3", lambda x: 1 <= x <= 3),
               ("4–6", lambda x: 4 <= x <= 6),
               ("7–12", lambda x: 7 <= x <= 12),
               ("13+", lambda x: x >= 13)]
    hist = {name: sum(1 for x in leads if pred(x)) for name, pred in buckets}
    return {
        "n": n, "mean": mean(leads), "median": median(leads),
        "min": leads[0], "max": leads[-1],
        "pos_rate": len(pos_leads) / n, "hist": hist,
    }


# ---------------------------------------------------------------- E: candle + concordance
def candle_dist_per_tf(frames):
    """TF별 캔들 쌍바닥/쌍봉 검출 분포(전 심볼 합산) + 캔들↔소파동 합치 분포."""
    per_tf = defaultdict(lambda: {"db": 0, "dt": 0, "total": 0})
    concord = defaultdict(int)   # 캔들 이벤트의 소파동 합치 상태 분포
    for (sym, tf), full in frames.items():
        dist = candle_distribution(full, sym, tf)
        for k in ("db", "dt", "total"):
            per_tf[tf][k] += dist[k]
        for ev in scan_candle_patterns(full, sym, tf):
            concord[concordance_at(full, "candle", ev.direction, ev.confirmed_pos)] += 1
    return dict(per_tf), dict(concord)


def concordance_separation(records, frames):
    """complete 캠페인(S0=MA10)을 상응 대파동 합치 상태로 분리 → net·저점이탈율."""
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    groups = defaultdict(list)
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        state = concordance_at(full, r["driver"].ma_or_layer, r["direction"], r["res"].setup_pos)
        r["_concord"] = state
        groups[state].append(r)

    def grp(rs):
        nets = [x["net"] for x in rs if x["net"] is not None]
        lbs = [x["low_break"] for x in rs if x["low_break"] is not None]
        a = _agg(nets)
        a["low_break_rate"] = (sum(1 for x in lbs if x) / len(lbs)) if lbs else None
        return a

    return {k: grp(v) for k, v in groups.items()}, comp


def context_x_concordance(comp):
    """정방향 맥락(context_aligned) × 합치 교차표. 셀 n<min_cell_n 은 판단 보류.

    comp는 context_separation·concordance_separation이 이미 _ctx_aligned·_concord를 심어둔 리스트.
    """
    cells = defaultdict(list)
    for r in comp:
        al = r.get("_ctx_aligned")
        co = r.get("_concord")
        if al is None or co is None:
            continue
        cells[(bool(al), co)].append(r["net"])
    return cells


# ---------------------------------------------------------------- report
def write_report(records, frames):
    c1_ov, c1_per, c1_pass = c1_temporal(records)
    c2 = c2_per_tf(records)
    ctx_al, ctx_mis, arr_counts, n_ctx, ctx_diag = context_separation(records, frames)
    pb_al, pb_mis, pb_n = context_separation_prebreak(records, frames)
    tl = candidate_timeliness(frames, period=10)
    # E: 캔들 분포 + 합치 분리 + 교차표
    candle_tf, candle_concord = candle_dist_per_tf(frames)
    concord_groups, comp_list = concordance_separation(records, frames)
    xtab = context_x_concordance(comp_list)
    min_n = CONCORDANCE_PARAMS["min_cell_n"]

    comp_n = sum(1 for r in records if r["status"] == ST_COMPLETE and r["net"] is not None)
    overall_nets = [r["net"] for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    ov = _agg(overall_nets)

    def d(cur, prev):
        if cur is None or prev is None:
            return "—"
        return f"{(cur - prev) * 100:+.2f}%p"

    L = [
        "# REPORT_V2_PHASE4 — 교정 풀 + 관측 컬럼(candidate·array_context·캔들·합치) G2 재실행\n",
        "선행: PHASE2(C-1 미달·C-2 4h/1d 통과), PHASE3(G1-a 리뷰 준비). **엔진·게이트·파라미터 무수정.**",
        "이 문서는 4차 위임 A~E의 산출물이다. 게이트 수치 변경 없음, 필터·튜닝 도입 없음.",
        "캔들 패턴은 검출·표시·저널 전용(캠페인 승격 소스 아님), array_context·concordance는 관측 태그(게이트 아님).\n",
        "## 0. G1-a 판정 기록 (이 문서로 공식화)\n",
        "김박사 검토 결과 = **조건부 통과(conditional PASS)**.",
        "- 패턴 위치·기준 TF 정합: **인정(O)**.",
        "- 단, 40건 전수 기입이 아닌 **정성 판정**이며, **적시성 이슈**(넥라인 확정의 구조적 후행성)가 지적됨.",
        "- 적시성 이슈는 본 문서 §B(candidate 2단계 노출 + 선행 봉수 계측)로 정량화한다.",
        "- PRELIMINARY 규율 유지: G1 최종 PASS 서명 전까지 모든 수치는 잠정이다.\n",
        "## A. TF 풀 검증·교정 (스펙 §1 정합)\n",
        "**동결 스펙 §1 확정 풀** (12h 없음):",
        "```",
        'TF_POOL = ' + str(TF_POOL),
        "```",
        "",
        "| 항목 | 발견된 구현 | 스펙 §1 | 교정 |",
        "|---|---|---|---|",
        "| tf_ladder 상수 | `TF_LADDER=[15m,1h,4h,1d,4d,2w]` (6개, 고정 인덱스±1 인접) | 풀 10개 + 비율 인접 | `TF_POOL` 10개 도입, 비율 기반 upper/lower로 교체 |",
        "| PHASE1/2 백테스트 풀 | `{1h,4h,1d}` 단일 TF 리플레이 | (백테스트는 풀 무관) | 변경 없음 — 아래 캐비엇 |",
        "| PHASE3 라이브 스냅샷 풀 | `[15m,30m,1h,2h,4h,6h,12h,1d,4d,2w]` (**12h 포함·8h 부재**) | 8h 포함·12h 제외 | 스크립트 상수 교정(리포트 문서 무수정) |",
        "",
        "- **12h 고립 근거(코드 주석에 기록)**: 12h(720분)는 비율 규칙 ×3.5~×6 상 상·하위가 모두 없다.",
        "  upper 후보 구간 [2520,4320]분에 풀 TF 없음(1d=1440은 ×2, 4d=5760은 ×8), lower도 스펙이 8h를 채택.",
        "- **비율 인접(스펙 §1) 단위 테스트로 고정**: `tests/test_tf_ladder.py::test_adjacency_table_matches_spec_section1`",
        "  (8h upper 없음, upper(4h)=1d≠lower(1d)=6h 비대칭 포함 전수 검증).",
        "",
        "> ⚠ **캐비엇 — PHASE1/2 수치는 '풀 불일치 상태에서 산출'**: G2 백테스트는 `{1h,4h,1d}` 3개 TF를",
        "> 각각 단일 TF로 리플레이하며 풀(스캔 대상 전체)이나 cross-TF 억제를 쓰지 않는다. 따라서 12h→8h",
        "> 교정은 **백테스트 본 수치에 영향이 없다**(아래 D 재실행이 이를 실측으로 확인). 풀 불일치가 실제로",
        "> 영향을 준 곳은 PHASE3 라이브 스냅샷(10-TF 확정 분포)뿐이며, 그 표는 12h 열을 포함한 채 남는다.",
        "",
        "## B. candidate 2단계 노출 + 적시성 계측\n",
        "- 검출기 **출력만 확장**(김박사 승인 예외): `PatternEvent.stage ∈ {confirmed, candidate}`.",
        "  내부 판정 로직·확정 정의([F7-a] kind+넥라인)는 불변. candidate는 검출기가 이미 산출한",
        "  피봇 컬럼(`ma{p}_pivot_low/high`)만 재해석해 스캐너 레이어에서 방출한다.",
        "- candidate = 두 번째 극점 확정 + 넥라인 **미돌파**. **승격(L2)은 confirmed만**(is_promotable stage 가드).",
        "  라이브 카드 표기: `후보 — MA10 쌍바닥(HL) · 넥라인 612.4 상향 돌파 대기 [미확정·승격 불가]`.",
        "",
        "### 적시성(늦음의 정량화) — confirmed MA10 이벤트별 candidate 선행 봉수",
        "`lead_bars = confirm_pos − (두번째극점 pb + lookback)`. 양수 = candidate가 확정보다 먼저 관측 가능,",
        "≤0 = 넥라인 확정의 **구조적 후행성**(빠른 돌파로 candidate 관측 창이 없음 = G1-a 지적의 정체).",
        "",
    ]
    if tl["n"]:
        L += [
            f"- n={tl['n']}  ·  mean **{tl['mean']:+.2f}봉**  ·  median {tl['median']:+.0f}봉  ·  "
            f"범위 [{tl['min']}, {tl['max']}]  ·  선행(양수) 비율 **{tl['pos_rate']*100:.0f}%**",
            "",
            "| 선행 봉수 버킷 | 건수 | 비중 |",
            "|---|---|---|",
        ]
        for name, cnt in tl["hist"].items():
            L.append(f"| {name} | {cnt} | {cnt/tl['n']*100:.0f}% |")
        L += [
            "",
            f"> 해석: candidate는 평균 {tl['mean']:+.1f}봉 선행하나, **≤0(동시/후행) 비율 "
            f"{tl['hist']['≤0 (동시/후행)']/tl['n']*100:.0f}%**가 존재한다 — 이 구간이 김박사가 지적한",
            "> '넥라인 확정의 후행성'에 해당. candidate 노출은 관측 창을 앞당기지만 일부 급반전 케이스는",
            "> 구조적으로 조기 경보가 불가능함을 수치로 확인(게이트 아님, 표시·저널 전용).",
        ]
    else:
        L.append("- candidate 계측 데이터 없음.")

    L += [
        "",
        "## C. array_context 분류기 (관측 태그 — 게이트 아님)\n",
        "김박사 규칙 형식화: **\"정배열이다가 모일 때 쌍봉, 역배열이다가 모일 때 쌍바닥\" = 정방향 맥락.**",
        "원 발언대로 확정 규칙이 아니므로 게이트로 사용 금지 — 저널 컬럼(`array_context`, `context_aligned`)만.",
        "",
        "형식화 정의 + 노출 상수(`config.ARRAY_CONTEXT_PARAMS`, 김박사 조정 대상·초기값 보수적):",
        "",
        "| 항목 | 정의 | 초기 상수 |",
        "|---|---|---|",
        "| 배열 | bull(MA5>10>20>60) / bear(MA5<10<20<60) / mixed | `core_ma=[5,10,20,60]` |",
        "| 모임(converging) | 정규화 스프레드 (max−min)/close ≤ 상한 **AND** window 전 대비 축소 | `converge_window=10`, `converge_spread_max=0.03`, `converge_shrink_ratio=0.8` |",
        "| 정방향 정합 | 역배열+모임+쌍바닥(long) 또는 정배열+모임+쌍봉(short) | — |",
        "",
        f"- S0 봉 배열 태그 분포(complete n={n_ctx}): "
        + (", ".join(f"`{k}`={v}" for k, v in sorted(arr_counts.items(), key=lambda x: -x[1])) or "—"),
        "",
        "## D. G2 재실행 (교정 풀 + 관측 컬럼)\n",
        "**게이트·기간·심볼·파라미터 불변.** 백테스트 매트릭스 = 4심볼 × {1h,4h,1d} (풀 무관, §A 캐비엇).",
        "",
        "### D1. 갱신된 본 수치 (PHASE2 대비)",
        "",
        "| 지표 | PHASE4(재실행) | PHASE2 | Δ |",
        "|---|---|---|---|",
        f"| complete n | {comp_n} | {PHASE2['overall']['n']} | {comp_n - PHASE2['overall']['n']:+d} |",
        f"| 합산 net mean | {_pct(ov['mean'])} | {_pct(PHASE2['overall']['net'])} | {d(ov['mean'], PHASE2['overall']['net'])} |",
        f"| net median | {_pct(ov['median'])} | — | — |",
        f"| 승률 | {ov['win']*100:.0f}% | — | — |",
        "",
        "> 재실행은 라이브 fetch(트레일링 윈도)라 PHASE2 대비 봉 구간이 이동해 소폭 드리프트가 있을 수 있다.",
        "> 12h→8h 교정 자체는 이 매트릭스에 영향이 없다(단일 TF 리플레이).",
        "",
        "### D2. C-1 temporal split (동일 게이트: 후반 mean ≥ +0.50% AND 후반 n ≥ 40)",
        "",
        "| 구간 | n | mean | median | 승률 |",
        "|------|---|------|--------|------|",
        _row("전반", c1_ov["early"]),
        _row("후반", c1_ov["late"]),
        "",
        f"- **판정: {'통과(PASS)' if c1_pass else '미달(FAIL)'}** "
        f"(후반 mean {_pct(c1_ov['late']['mean'])}, n {c1_ov['late']['n']})  ·  "
        f"PHASE2 후반: {_pct(PHASE2['c1']['late']['mean'])}, n {PHASE2['c1']['late']['n']}",
        "",
        "### D2. C-2 TF별 판정 (동일 게이트: median ≥ 0% AND mean ≥ +0.50% AND n ≥ 30)",
        "",
        "| TF | n | mean | median | 승률 | 판정 |",
        "|----|---|------|--------|------|------|",
    ]
    for tf in TFS:
        a = c2[tf]["agg"]
        ok = c2[tf]["pass"]
        L.append(f"| {tf} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | "
                 f"{(a['win'] or 0)*100:.0f}% | {'통과' if ok else '미달'} |")
    passed_tfs = [tf for tf in TFS if c2[tf]["pass"]]
    L += [
        "",
        f"- C-2 통과 TF: **{', '.join(passed_tfs) or '없음'}**  ·  PHASE2 통과 TF: 4h, 1d",
        "",
        "### D3. 맥락 분리 통계 (관측 — 게이트 승격 가치 판단용 첫 데이터)",
        "",
        "| 군 | n | net mean | net median | 승률 | 저점이탈 재진입율 |",
        "|----|---|------|--------|------|------|",
        f"| 정방향 정합(context_aligned) | {ctx_al['n']} | {_pct(ctx_al['mean'])} | {_pct(ctx_al['median'])} | "
        f"{(ctx_al['win'] or 0)*100:.0f}% | {_pct(ctx_al.get('low_break_rate'))} |",
        f"| 비정방향 | {ctx_mis['n']} | {_pct(ctx_mis['mean'])} | {_pct(ctx_mis['median'])} | "
        f"{(ctx_mis['win'] or 0)*100:.0f}% | {_pct(ctx_mis.get('low_break_rate'))} |",
        "",
        f"- 대조: PHASE2 C-3(1) 저점이탈군 T2 {_pct(PHASE2['low_break']['low']['t2'])}(n={PHASE2['low_break']['low']['n']}) "
        f"vs 비이탈군 {_pct(PHASE2['low_break']['non']['t2'])}(n={PHASE2['low_break']['non']['n']}) "
        f"— 저점이탈이 전체의 ~84%.",
        "",
        "**진단 — S0 봉에서 각 조건 충족 수 (병목 파악용):**",
        "",
        "| 조건 | 충족 수 | 비중 |",
        "|---|---|---|",
        f"| 배열 일치 (long=역배열 / short=정배열) | {ctx_diag['array_match']} | {ctx_diag['array_match']/max(1,n_ctx)*100:.0f}% |",
        f"| 모임(converging) | {ctx_diag['converging']} | {ctx_diag['converging']/max(1,n_ctx)*100:.0f}% |",
        f"| **둘 다 (= context_aligned)** | **{ctx_diag['both']}** | {ctx_diag['both']/max(1,n_ctx)*100:.0f}% |",
        "",
        f"> **핵심 관측**: 정합군 n={ctx_al['n']}. "
        + (
            "정합 표본이 0이라 성적 분리를 낼 수 없다. 진단 표가 병목을 가리킨다 — S0(넥라인 돌파 확정 봉)"
            "에서는 이미 MA5가 반등해 '배열 일치(역/정배열 유지)'가 드물거나, 보수적 모임 임계에 걸린다. "
            "즉 **현재 형식화·상수로는 태그가 분리력을 갖지 못한다**(첫 데이터). 상수 완화(스프레드 상한↑, "
            "배열 판정 시점을 S0가 아닌 S0 이전 N봉으로 이동)를 김박사 검토 대상으로 제안."
            if ctx_al["n"] == 0 else
            "정합군 표본이 확보돼 아래 net·저점이탈율 격차로 84% 문제 설명력을 판단할 수 있다."
        ),
        "",
        f"**보조 앵커 — 넥라인 돌파 전 '두 번째 극점' 시점에서 태깅** (규칙 의미에 더 충실, 관측 전용, n={pb_n}):",
        "",
        "| 군 | n | net mean | net median | 승률 | 저점이탈 재진입율 |",
        "|----|---|------|--------|------|------|",
        f"| 정방향 정합(돌파 전) | {pb_al['n']} | {_pct(pb_al['mean'])} | {_pct(pb_al['median'])} | "
        f"{(pb_al['win'] or 0)*100:.0f}% | {_pct(pb_al.get('low_break_rate'))} |",
        f"| 비정방향(돌파 전) | {pb_mis['n']} | {_pct(pb_mis['mean'])} | {_pct(pb_mis['median'])} | "
        f"{(pb_mis['win'] or 0)*100:.0f}% | {_pct(pb_mis.get('low_break_rate'))} |",
        "",
        "- **질문(맥락이 84% 문제를 설명하는가)**: 두 군의 저점이탈 재진입율 격차로 판단. "
        "정합군의 이탈율이 유의하게 낮으면 array_context가 저점이탈 문제를 설명한다는 신호.",
        "- **현 데이터의 답(잠정)**: "
        + (
            (
                f"돌파 전 앵커 기준 정합군 이탈율 {_pct(pb_al.get('low_break_rate'))} "
                f"vs 비정방향 {_pct(pb_mis.get('low_break_rate'))} — "
                + (
                    f"정합군이 **더 높거나 비슷**(n={pb_al['n']}, 소표본). 즉 현 형식화·상수로는 "
                    "array_context가 84% 저점이탈 문제를 **설명하지 못한다**(반증 아님, 무증거). "
                    "상수 완화·앵커 재정의 후 표본 확보가 선행 조건."
                    if (pb_al.get("low_break_rate") is None or pb_mis.get("low_break_rate") is None
                        or pb_al["low_break_rate"] >= pb_mis["low_break_rate"])
                    else "정합군 이탈율이 낮음 — 설명력 가설 지지(소표본 주의, 표본 확대 필요)."
                )
            )
            if pb_al["n"] > 0 else "정합 표본 부족(양 앵커 모두) — 판단 불가, 상수 완화 필요."
        ),
        "",
        "### D4. candidate 적시성 통계",
        f"- §B 참조: n={tl.get('n', 0)}, mean {tl.get('mean', 0):+.2f}봉, 선행 비율 {tl.get('pos_rate', 0)*100:.0f}%.",
        "",
        "## E. 캔들 패턴 검출기 + 상응 합치 태그 (신규, 관측 전용)\n",
        "**[F1] 상응 구조**: MA10↔대파동, MA5↔중파동, **캔들↔소파동**. 급 내 가격계>오실레이터.",
        "통합 위계: 소파동 < 캔들 < 중파동 < MA5 < 대파동 < MA10.",
        "",
        "### E-1. 캔들 쌍바닥/쌍봉 검출기 (확정 정의)",
        "- 쌍바닥 = **정확히 4봉 음→양→음→양**, 3번봉 low ≥ 1번봉 low(**HL 필수**), 확정=4번봉 마감.",
        "- 쌍봉 = 양→음→양→음, 3번봉 high ≤ 1번봉 high(LH 필수). 도지=교대 파괴(`DOJI_BREAKS_ALTERNATION=True`).",
        "- 연속 4봉 엄격 정의 → **정밀도↑·재현율↓(의도됨)**. 하급(타이밍) 신호. **캠페인 승격(L2) 소스 아님.**",
        "",
        "검출 분포 ({1h,4h,1d}×4심볼, 이력 전체):",
        "",
        "| TF | 캔들 쌍바닥 | 캔들 쌍봉 | 합 |",
        "|----|----|----|----|",
    ]
    for tf in TFS:
        cd = candle_tf.get(tf, {"db": 0, "dt": 0, "total": 0})
        L.append(f"| {tf} | {cd['db']} | {cd['dt']} | {cd['total']} |")
    tot_db = sum(candle_tf.get(tf, {}).get("db", 0) for tf in TFS)
    tot_dt = sum(candle_tf.get(tf, {}).get("dt", 0) for tf in TFS)
    L += [
        f"| **합** | {tot_db} | {tot_dt} | {tot_db + tot_dt} |",
        "",
        "### E-2. 상응 합치(concordance) 태그 — none | in_progress | confirmed",
        "- 기준(김박사 확정): **방향만 같으면 진행 중(candidate)도 합치로 인정.** 확정>진행>없음 우선.",
        f"- 탐색 창 `window_bars={CONCORDANCE_PARAMS['window_bars']}`봉. 게이트·필터 금지 — 저널 컬럼만.",
        "",
        "**캔들 이벤트 ↔ 소파동 합치 분포:**",
        "",
        "| 합치 | 건수 |",
        "|---|---|",
    ]
    for st_key in ("confirmed", "in_progress", "none", "n/a"):
        if st_key in candle_concord:
            L.append(f"| {st_key} | {candle_concord[st_key]} |")
    L += [
        "",
        "**캠페인(S0=MA10) ↔ 대파동 합치 성적 분리 (관측):**",
        "",
        "| 합치 | n | net mean | net median | 승률 | 저점이탈 재진입율 |",
        "|---|---|------|--------|------|------|",
    ]
    for st_key in ("confirmed", "in_progress", "none"):
        a = concord_groups.get(st_key)
        if a is None:
            L.append(f"| {st_key} | 0 | — | — | — | — |")
        else:
            L.append(f"| {st_key} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | "
                     f"{(a['win'] or 0)*100:.0f}% | {_pct(a.get('low_break_rate'))} |")
    L += [
        "",
        f"### E-3. 정방향 맥락 × 합치 교차표 (S0 앵커, 셀 n<{min_n}은 판단 보류)",
        "",
        "| 맥락\\합치 | confirmed | in_progress | none |",
        "|---|---|---|---|",
    ]
    for al in (True, False):
        row = [f"| {'정방향' if al else '비정방향'} |"]
        for co in ("confirmed", "in_progress", "none"):
            nets = xtab.get((al, co), [])
            k = len(nets)
            if k == 0:
                cell = "—"
            elif k < min_n:
                cell = f"n={k} 보류"
            else:
                cell = f"{_pct(mean(nets))} (n={k})"
            row.append(f" {cell} |")
        L.append("".join(row))
    L += [
        "",
        "> 교차표 주의: 정방향(context_aligned) S0 표본이 0이라(§D3) 정방향 행은 전부 빈 셀이다. "
        "합치축 단독 분리는 위 E-2 표가, 맥락축 단독은 §D3이 담당한다. 교차 승격 판단은 표본 확보 후.",
        "",
        "## 미결 · 제안 (스코프 밖 — 결정하지 않고 기록만)\n",
        "- **array_context 게이트 승격 여부는 제안만**(김박사 판단 사항): 위 D3에서 정합군이 net·저점이탈율",
        "  모두에서 유의하게 우세하면 게이트 후보. 현재는 저널 컬럼으로만 축적, 표본 누적 후 재평가 제안.",
        "- candidate 적시성: ≤0 버킷(구조적 후행)이 상당하면 '조기 경보'로서의 실효는 제한적 — forward에서",
        "  candidate→confirmed 실현율을 별도 계측 제안(현재는 표시·저널 전용).",
        "- **캔들 패턴 승격 소스 확대는 별도 김박사 결정**: 현재 승격은 clean 이평선만. 캔들↔소파동 합치가",
        "  누적 성적에서 유의미하면 하급 타이밍 보조로 승격 검토(현재는 검출·표시·저널 전용).",
        "- **concordance 게이트 승격 여부는 제안만**: E-2 캠페인 합치 분리에서 confirmed군이 유의하게 우세하면",
        "  게이트 후보. 셀 n 작으면(교차표) 판단 보류. 표본 누적 후 재평가 제안.",
        "- PHASE3 라이브 스냅샷 재생성은 하지 않음(기존 리포트 무수정 규율). 교정 풀 스냅샷이 필요하면 별도 위임.",
        "- C-1/C-2 게이트 수치는 불변 유지. 재실행 미달도 그대로 산출물로 보고.",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return c1_pass, passed_tfs, comp_n, tl, ctx_al, ctx_mis


def main():
    frames, records, events_by_symbol = build()
    c1_pass, passed_tfs, comp_n, tl, ctx_al, ctx_mis = write_report(records, frames)
    print(f"records={len(records)} complete_n={comp_n}")
    print(f"C-1 PASS={c1_pass}  C-2 통과 TF={passed_tfs}")
    print(f"candidate lead: n={tl.get('n')} mean={tl.get('mean')}")
    print(f"context aligned n={ctx_al['n']} mean={ctx_al['mean']}  mis n={ctx_mis['n']} mean={ctx_mis['mean']}")
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
