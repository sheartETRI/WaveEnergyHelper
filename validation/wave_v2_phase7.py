"""v2 PHASE7 (7차 위임 A 재주석 + B 추세 의존성 판정) — 기술통계 단발, 엔진/게이트 무수정.

선행: REPORT_V2_PHASE6 (A NO-GO). 7차 위임:
- A: 동결 스펙(docs/기법0_추세레이어_동결스펙.md) 확보 → trend_layer 스펙 우선 교정(별도 커밋).
     본 스크립트는 교정된 trend_state_at 으로 저널 trend_state_at_entry 를 **전체 재주석**하고,
     PHASE6 즉흥 스냅샷(상승87/하락60/바닥41/천장29/미정6) 대비 분포 변화를 보고한다.
- B: 재주석 저널(전체 캠페인 — 필터 무관)로 표1·표2 산출 + 사전 등록 판정 H-T1/H-T2.

판정 기준(사전 등록 — 결과 확인 후 변경 금지, 위임 원문):
- H-T1 (추세 조건부 엣지): 상승 상태(T3 이상) 진입군 n ≥ 30 이고, 비상승 진입군 대비
  net mean·median **모두** 우위.
- H-T2 (감쇠의 추세 설명력): 후반 한정 상승 상태 진입군 n ≥ 15 이고 net mean ≥ 0%.
- 둘 다 통과 → v3 가설 생존, C 진행. 둘 다 기각 → v3 가설 사망, 시그널 검증 경로 종료.
  하나만 통과 → C 미수행, 김박사 에스컬레이션.

산출물: validation/REPORT_V2_PHASE7.md
실행: `python validation/wave_v2_phase7.py`
"""
import logging
import os
import sys
import warnings
from collections import Counter, defaultdict
from statistics import mean, median

import numpy as np

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.trend_layer import (  # noqa: E402
    TREND_FLOW,
    UPTREND_STATES,
    add_macd_line_patterns,
    bottom_width,
    ma_slope,
    macd_double_top_lh_at,
    slope_sign,
    trend_state_at,
    trend_state_label,
)
from config.settings import TREND_LAYER_PARAMS  # noqa: E402
from validation.wave_v2_phase2 import _pct, build  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE7.md")

# 사전 등록 판정 상수 (위임 원문 — 변경 금지)
HT1_UPTREND_MIN_N = 30
HT2_LATE_UPTREND_MIN_N = 15
HT2_LATE_MIN_MEAN = 0.0

# 상태 표시 순서
STATE_ORDER = ["T0", "T1", "T2", "T3", "T4"]
# PHASE6 즉흥 스냅샷(폐기 대상, 분포 변화 대조용 인용)
PHASE6_SNAPSHOT = {"하락": 60, "바닥형성": 41, "상승전환": 0, "상승": 87, "천장형성": 29, "미정": 6}


def _agg(nets):
    nets = [x for x in nets if x is not None]
    if not nets:
        return {"n": 0, "mean": None, "median": None, "win": None}
    return {"n": len(nets), "mean": mean(nets), "median": median(nets),
            "win": sum(1 for x in nets if x > 0) / len(nets)}


def _lb_rate(rs):
    lbs = [r["low_break"] for r in rs if r["low_break"] is not None]
    return (sum(1 for x in lbs if x) / len(lbs)) if lbs else None


# ---------------------------------------------------------------- A: 재주석
def annotate(records, frames):
    """complete 캠페인에 스펙 기준 trend_state_at_entry 부착. 반환 = 재주석 comp 리스트."""
    comp = [r for r in records if r["status"] == ST_COMPLETE]
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        state = trend_state_at(full, r["res"].setup_pos) if full is not None else None
        r["_tstate"] = state                      # T0..T4 또는 None
        r["_tlabel"] = trend_state_label(state)
    return comp


# ---------------------------------------------------------------- B: 표
def table1(comp):
    """trend_state_at_entry별 성적."""
    by = defaultdict(list)
    for r in comp:
        by[r["_tstate"]].append(r)
    rows = []
    for st in STATE_ORDER + [None]:
        rs = by.get(st, [])
        a = _agg([r["net"] for r in rs])
        a["low_break_rate"] = _lb_rate(rs)
        a["label"] = trend_state_label(st) if st else ""
        a["state"] = st or "미정"
        rows.append(a)
    return rows


def temporal_halves(comp):
    """전체 comp 를 setup_ts 기준 50:50 분할(결정론적 tie-break=cid)."""
    rs = sorted(comp, key=lambda r: (r["setup_ts"], r["cid"]))
    mid = len(rs) // 2
    return rs[:mid], rs[mid:]


def table2(comp):
    """전/후반 50:50 × trend_state_at_entry 교차 (n, net mean, median)."""
    early, late = temporal_halves(comp)
    out = {"early": {}, "late": {}}
    for half_name, half in (("early", early), ("late", late)):
        by = defaultdict(list)
        for r in half:
            by[r["_tstate"]].append(r)
        for st in STATE_ORDER + [None]:
            out[half_name][st] = _agg([r["net"] for r in by.get(st, [])])
    return out, len(early), len(late)


# ---------------------------------------------------------------- B: 판정
def verdict_ht1(comp):
    up = [r for r in comp if r["_tstate"] in UPTREND_STATES]
    non = [r for r in comp if r["_tstate"] in ("T0", "T1", "T2")]  # 비상승(정의된 상태만; 미정 제외)
    a_up, a_non = _agg([r["net"] for r in up]), _agg([r["net"] for r in non])
    passed = (
        a_up["n"] >= HT1_UPTREND_MIN_N
        and a_up["mean"] is not None and a_non["mean"] is not None
        and a_up["median"] is not None and a_non["median"] is not None
        and a_up["mean"] > a_non["mean"] and a_up["median"] > a_non["median"]
    )
    return {"up": a_up, "non": a_non, "pass": passed}


def verdict_ht2(comp):
    _early, late = temporal_halves(comp)
    late_up = [r for r in late if r["_tstate"] in UPTREND_STATES]
    a = _agg([r["net"] for r in late_up])
    passed = (a["n"] >= HT2_LATE_UPTREND_MIN_N and a["mean"] is not None
              and a["mean"] >= HT2_LATE_MIN_MEAN)
    return {"late_up": a, "pass": passed}


# ---------------------------------------------------------------- 부가 기록
def _width_of(full, r):
    pat = "db" if r["direction"] == "long" else "dt"
    return bottom_width(full, 10, pat, r["res"].setup_pos)


def _reached_60ma_turn(full, r):
    """캠페인 창[setup_pos, exit] 내 60MA 턴(slope60>0) 도달 여부."""
    sp = r["res"].setup_pos
    ep = r["res"].exit_final.pos if r["res"].exit_final else len(full) - 1
    for pos in range(sp, ep + 1):
        if slope_sign(ma_slope(full, pos, TREND_LAYER_PARAMS["trend_ma_fast"])) == "up":
            return True
    return False


def addendum(comp, frames, macd_frames):
    # (a) bottom_width 사분위 × 성적, (b) 폭 사분위별 60MA 턴 도달률
    rows = []
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        w = _width_of(full, r)
        if w is None or r["net"] is None:
            continue
        rows.append((w, r["net"], _reached_60ma_turn(full, r)))
    quart = {"buckets": [], "n": len(rows)}
    if rows:
        ws = np.array([x[0] for x in rows], dtype=float)
        q1, q2, q3 = (float(np.percentile(ws, p)) for p in (25, 50, 75))
        edges = [(-np.inf, q1, "Q1(최소~25%)"), (q1, q2, "Q2(25~50%)"),
                 (q2, q3, "Q3(50~75%)"), (q3, np.inf, "Q4(75%~최대)")]
        for lo, hi, name in edges:
            sub = [x for x in rows if (x[0] > lo or lo == -np.inf) and (x[0] <= hi)]
            nets = [x[1] for x in sub]
            reach = [x[2] for x in sub]
            a = _agg(nets)
            a["name"] = name
            a["turn_rate"] = (sum(1 for x in reach if x) / len(reach)) if reach else None
            a["w_lo"] = None if lo == -np.inf else lo
            a["w_hi"] = None if hi == np.inf else hi
            quart["buckets"].append(a)
        quart["edges"] = (q1, q2, q3)

    # (c) MACD 쌍봉(LH) 발생과 캠페인 청산 시점 근접도
    gaps = []
    n_with_lh = 0
    for r in comp:
        res = r["res"]
        if res.exit_final is None:
            continue
        mf = macd_frames.get((r["symbol"], r["tf"]))
        if mf is None:
            continue
        sp, ep = res.setup_pos, res.exit_final.pos
        last_lh = None
        for pos in range(sp, ep + 1):
            if macd_double_top_lh_at(mf, pos):
                last_lh = pos
        if last_lh is not None:
            n_with_lh += 1
            gaps.append(ep - last_lh)   # 청산봉 − 마지막 LH 쌍봉봉 (봉수)
    macd_prox = {
        "n_exited": sum(1 for r in comp if r["res"].exit_final is not None),
        "n_with_lh": n_with_lh,
        "gap_median": int(median(gaps)) if gaps else None,
        "gap_min": min(gaps) if gaps else None,
        "gap_max": max(gaps) if gaps else None,
    }
    return quart, macd_prox


# ---------------------------------------------------------------- 리포트
def _r1(a):
    if a["mean"] is None:
        return f"| {a['state']} {a['label']} | {a['n']} | — | — | — | — |"
    return (f"| {a['state']} {a['label']} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | "
            f"{(a['win'] or 0)*100:.0f}% | {_pct(a.get('low_break_rate'))} |")


def _c2(a):
    if a["mean"] is None:
        return "— / — (0)"
    return f"{_pct(a['mean'])} / {_pct(a['median'])} (n={a['n']})"


def write_report(records, frames):
    comp = annotate(records, frames)
    # 관측 계기(MACD선 패턴) 부착 프레임 캐시
    macd_frames = {k: add_macd_line_patterns(v.copy()) for k, v in frames.items()}

    t1 = table1(comp)
    t2, n_early, n_late = table2(comp)
    ht1 = verdict_ht1(comp)
    ht2 = verdict_ht2(comp)
    quart, macd_prox = addendum(comp, frames, macd_frames)

    both_pass = ht1["pass"] and ht2["pass"]
    one_pass = (ht1["pass"] != ht2["pass"])

    # 재주석 분포 (스펙 기준)
    dist = Counter(r["_tlabel"] for r in comp)

    L = [
        "# REPORT_V2_PHASE7 — 기법0 스펙 정합(A) + 추세 의존성 판정(B)\n",
        "선행: REPORT_V2_PHASE6 (A NO-GO — 기법1+상응필터 forward 종료). **엔진·검출기·게이트 무수정.**",
        "A는 trend_layer 스펙 교정 + 저널 재주석, B는 재주석 저널의 단발 기술통계다(필터 적용 없음).\n",
        "## A. 기법0 스펙 정합 (교차표의 전제)\n",
        "동결 스펙 `docs/기법0_추세레이어_동결스펙.md` 확보 → PHASE6 즉흥 구현을 스펙 우선 교정.",
        "",
        "### A-1. 스펙 vs 즉흥 구현 대조 · 교정 내역",
        "",
        "| 항목 | 스펙 §2 | PHASE6 즉흥 구현 | 교정 |",
        "|---|---|---|---|",
        "| slope | (MA[t]−MA[t−N]) **부호**, N=5, flat 없음 | 정규화 + flat 밴드 0.1% | `slope_flat_pct=0.0`(순수 부호) |",
        "| T0 | slope(60)<0 (배열 무관) | MA60<MA120 AND slope down | slope-only 로 교정 |",
        "| T1 | 급3(MA10)쌍바닥 확정 + 60MA 하락기울기 약화 | MA60<MA120 & slope up/flat | 전면 교정(쌍바닥+약화) |",
        "| T2 | 계단식 GC: MA10×MA20 → **MA20×MA60** | **MA60×MA120** 상향교차 | MA쌍 교정 |",
        "| T3 | slope(60)>0 | MA60>MA120 & slope up/flat | slope-only 로 교정 |",
        "| T4 | **MA60×MA120 GC + slope(120)>0 = 완연상승** | MA60>MA120 & slope **down = 천장형성** | **의미 반전 교정** |",
        "| MACD 쌍봉 | MACD선 **LH** 단독 | kind 무필터 | LH 필터(`macd_double_top_lh_at`) |",
        "| 상응 4층 | (40,20,20)↔MA20 | (40,20,20) | 일치(무변경) |",
        "| bottom_width | 두 바닥 피봇 간 봉수(급3) | 동일 | 일치(무변경) |",
        "",
        "> 최대 결함은 **T4 의미 반전**(즉흥=천장형성 ↔ 스펙=완연상승)과 **T2의 엉뚱한 MA쌍**",
        "> (즉흥 MA60×MA120 은 스펙상 T4)이다. 단위 테스트(`tests/test_trend_layer.py`)를 스펙 §2 원문",
        "> 기준으로 갱신(T0/T3 slope-only, T2 계단식 GC, T1 쌍바닥+약화, slope 순수 부호).",
        "",
        "### A-2. 재주석 전후 상태 분포 변화 (complete 캠페인 n=" + str(len(comp)) + ")",
        "",
        "PHASE6 스냅샷은 즉흥 정의 기준 → 폐기. 아래는 스펙 기준 재산출.",
        "",
        "| 상태 | PHASE6 즉흥(폐기) | 스펙 재주석 |",
        "|---|---|---|",
    ]
    label_by_state = {t["state"]: t["label"] for t in TREND_FLOW}
    phase6_map = dict(PHASE6_SNAPSHOT)
    for st in STATE_ORDER:
        lab = label_by_state[st]
        old = phase6_map.get(lab, 0)
        # PHASE6 라벨과 스펙 라벨이 다른 T4(천장형성→완연상승)은 별도 주석
        old_disp = str(old)
        if st == "T4":
            old_disp = f"{phase6_map.get('천장형성', 0)} (‘천장형성’ 라벨)"
        L.append(f"| {st} {lab} | {old_disp} | {dist.get(lab, 0)} |")
    L.append(f"| 미정 | {phase6_map.get('미정', 0)} | {dist.get('미정', 0)} |")

    L += [
        "",
        "> ⚠ 모델링 결정(스펙 미지정 — 미결에 질문): 진입봉 1점 주석을 위해 **봉 단위 우선순위 분류기**",
        "> (강도순 T4>T3>T2>T1>T0)로 실현. 순차 상태 워크(파괴 트리거 히스테리시스)·T1 최근성 창·T2",
        "> 지속성은 스펙 미지정 → 아래 미결 참조. 단, **B 판정(T3 이상 vs 비상승)은 스펙 문언 그대로인",
        "> slope(60) 임계·T4 정의만 사용하므로 이 미지정부와 무관하게 강건**하다.",
        "",
        "## B. 추세 의존성 교차표 (기술통계 단발 — 사전 등록 판정)\n",
        "> **판정 기준(사전 등록, 결과 확인 후 변경 금지 — 원문 인용)**:",
        "> - **H-T1 (추세 조건부 엣지)**: 상승 상태(T3 이상) 진입군 n ≥ 30 이고, 비상승 진입군 대비",
        ">   net mean·median **모두** 우위.",
        "> - **H-T2 (감쇠의 추세 설명력)**: 후반 한정 상승 상태 진입군 n ≥ 15 이고 net mean ≥ 0%.",
        "> - 둘 다 통과 → v3 가설 생존, C 진행. 둘 다 기각 → v3 가설 사망, 시그널 검증 경로 종료.",
        ">   하나만 통과 → C 미수행, 김박사 에스컬레이션.\n",
        "재주석 저널(전체 캠페인 — 필터 무관, n=" + str(len(comp)) + "):",
        "",
        "### 표1. trend_state_at_entry별 성적",
        "",
        "| 상태 | n | net mean | net median | 승률 | 저점이탈율 |",
        "|---|---|------|--------|------|------|",
    ]
    for a in t1:
        L.append(_r1(a))

    L += [
        "",
        "### 표2. 전/후반 50:50 × trend_state_at_entry (net mean / median (n))",
        f"- 분할: 전체 {len(comp)}건 setup_ts 정렬 → 전반 {n_early} · 후반 {n_late}",
        "",
        "| 상태 | 전반 (mean/median) | 후반 (mean/median) |",
        "|---|---|---|",
    ]
    for st in STATE_ORDER + [None]:
        lab = trend_state_label(st)
        name = f"{st} {lab}" if st else "미정"
        L.append(f"| {name} | {_c2(t2['early'][st])} | {_c2(t2['late'][st])} |")

    # 판정
    up, non = ht1["up"], ht1["non"]
    lu = ht2["late_up"]
    ht1_mean_ok = up["mean"] is not None and non["mean"] is not None and up["mean"] > non["mean"]
    ht1_med_ok = up["median"] is not None and non["median"] is not None and up["median"] > non["median"]

    L += [
        "",
        "### 판정",
        "",
        "**H-T1 (추세 조건부 엣지)** — 상승(T3+) vs 비상승(T0/T1/T2):",
        "",
        "| 군 | n | net mean | net median |",
        "|---|---|------|--------|",
        f"| 상승(T3 이상) | {up['n']} | {_pct(up['mean'])} | {_pct(up['median'])} |",
        f"| 비상승(T0/T1/T2) | {non['n']} | {_pct(non['mean'])} | {_pct(non['median'])} |",
        "",
        f"- 상승군 n={up['n']} (필요 ≥{HT1_UPTREND_MIN_N}: {'충족' if up['n']>=HT1_UPTREND_MIN_N else '미달'}) · "
        f"mean 우위={'예' if ht1_mean_ok else '아니오'} · median 우위={'예' if ht1_med_ok else '아니오'}",
        f"- **H-T1 판정: {'통과' if ht1['pass'] else '기각'}**",
        "",
        "**H-T2 (감쇠의 추세 설명력)** — 후반 한정 상승(T3+) 진입군:",
        "",
        f"- 후반 상승군 n={lu['n']} (필요 ≥{HT2_LATE_UPTREND_MIN_N}: {'충족' if lu['n']>=HT2_LATE_UPTREND_MIN_N else '미달'}) · "
        f"net mean {_pct(lu['mean'])} (필요 ≥0%: {'충족' if (lu['mean'] is not None and lu['mean']>=0) else '미달'})",
        f"- **H-T2 판정: {'통과' if ht2['pass'] else '기각'}**",
        "",
        "### 종합 (사전 등록 기준)",
    ]
    if both_pass:
        L += [
            "**H-T1·H-T2 모두 통과 → v3 가설 생존.** C(v3 게이트 설계 초안) 진행. "
            "초안: `validation/V3_GATE_DRAFT.md`.",
        ]
    elif one_pass:
        only = "H-T1" if ht1["pass"] else "H-T2"
        L += [
            f"**{only}만 통과 (하나만 통과).** 사전 등록 규정: C 미수행, 결과를 정리해 **김박사 에스컬레이션**",
            "(판단 위임 금지). 아래 미결·에스컬레이션 참조.",
        ]
    else:
        L += [
            "**H-T1·H-T2 모두 기각 → v3 가설 사망.** 사전 등록 규정에 따라 C 미수행.",
            "",
            "> **시그널 검증 경로 종료 — 시스템은 관측·의사결정 보조 도구로 확정.**",
            "",
            "v1 규칙(6.85→1.42)·v2 baseline(+2.78→+0.17)·사전 등록 필터(+4.79→−0.44)에 이어, 추세",
            "상태 조건부 가설도 현 데이터에서 상승 상태 진입의 우위(H-T1)와 후반 상승 진입의 양(+) 성적",
            "(H-T2)을 내지 못했다. 네 번째 형식화의 기각. 인프라(검출·저널·관측 컬럼·추세 상태 기계)는",
            "보존하되 트레이딩 엣지 주장은 하지 않는다.",
        ]

    # 부가 기록
    L += [
        "",
        "## 부가 기록 (판정 아님 — 관측)\n",
        "### (1) bottom_width 사분위별 성적 · 60MA 턴 도달률",
    ]
    if quart["buckets"]:
        q1, q2, q3 = quart["edges"]
        L += [
            f"- 폭 경계(봉): Q1={q1:.0f} · Q2(중앙)={q2:.0f} · Q3={q3:.0f} (n={quart['n']})",
            "- 스펙 §0: 쌍바닥 폭이 클수록 60MA 턴 힘↑ 가설의 실측(관찰).",
            "",
            "| 폭 사분위 | n | net mean | net median | 승률 | 60MA 턴 도달률 |",
            "|---|---|------|--------|------|------|",
        ]
        for b in quart["buckets"]:
            L.append(f"| {b['name']} | {b['n']} | {_pct(b['mean'])} | {_pct(b['median'])} | "
                     f"{(b['win'] or 0)*100:.0f}% | {_pct(b['turn_rate'])} |")
    else:
        L.append("- 계측 가능한 bottom_width 없음.")

    # T1군 성적 (표1 인용)
    t1_row = next((a for a in t1 if a["state"] == "T1"), None)
    L += [
        "",
        "### (2) T1(바닥형성) 진입군 성적 — '관찰 후 확인 대기' 국면 실측",
    ]
    if t1_row and t1_row["mean"] is not None:
        L.append(f"- T1 진입 n={t1_row['n']} · net mean {_pct(t1_row['mean'])} · "
                 f"median {_pct(t1_row['median'])} · 승률 {(t1_row['win'] or 0)*100:.0f}% "
                 f"· 저점이탈율 {_pct(t1_row.get('low_break_rate'))}")
    else:
        L.append(f"- T1 진입군 표본 없음(n={t1_row['n'] if t1_row else 0}). 스펙 T1(급3 쌍바닥+약화) 조건이 "
                 "진입봉에서 성립하는 캠페인이 희소함을 시사(관찰).")

    L += [
        "",
        "### (3) MACD 쌍봉(LH) 발생과 캠페인 청산 시점 근접도",
        f"- 청산된 캠페인 {macd_prox['n_exited']}건 중 창 내 MACD 쌍봉(LH) 보유 {macd_prox['n_with_lh']}건.",
    ]
    if macd_prox["gap_median"] is not None:
        L.append(f"- (청산봉 − 마지막 LH 쌍봉봉) 봉수: median {macd_prox['gap_median']} · "
                 f"min {macd_prox['gap_min']} · max {macd_prox['gap_max']}. "
                 "스펙 §2 'MACD 쌍봉 = T3 파괴/빠른 익절 신호' 서사와의 정합 관찰(판정 아님).")
    else:
        L.append("- 창 내 LH 쌍봉 표본 없음.")

    # 미결
    L += [
        "",
        "## 미결 · 질문 (스펙 미지정 — 임의 해석 금지, 김박사 확정 대상)\n",
        "1. **상태 실현 방식**: 스펙은 '상태 기계'(전이·파괴 트리거)로 서술하나, 저널 진입봉 1점 주석엔",
        "   상태 분류가 필요 → 본 구현은 **봉 단위 우선순위 분류기**(강도순)로 실현. 순차 워크(파괴",
        "   트리거 히스테리시스 포함) 방식이 맞는가? (B 판정에는 영향 없음 — T3 임계·T4 정의만 사용.)",
        "2. **T4와 slope(60)**: 스펙 T4 문언은 slope60 미제약(MA60>MA120 & slope120>0). slope60<0 이면서",
        "   MA60>MA120 & slope120>0 인 봉(초기 천장)도 T4로 분류됨. 의도대로인가, slope60>0 병행 요구인가?",
        "3. **T0의 배타성**: MA60>MA120 이지만 slope120≤0·slope60<0 인 '하강하는 강배열' 봉은 스펙 문언상",
        "   T0(slope60<0)로 귀속됨. 스펙은 별도 '천장/하강전환' 상태를 두지 않음(파괴 트리거로만 서술).",
        "   이 귀속이 맞는가?",
        "4. **T1 최근성 창·약화 정의**: '급3 쌍바닥 확정' 최근성 창을 기존 `db_recent_bars`(=12)로,",
        "   '|slope| 축소 추세'를 1창(N봉) 비교로 실현. 스펙은 창 길이·약화 측정을 미지정 → 확정 요망.",
        "5. **T2 지속성**: 계단식 GC를 ②MA20×MA60 교차 봉의 순간 이벤트로 실현(①MA10>MA20 전제).",
        "   '전환 국면'을 slope60>0 전까지 지속 상태로 볼지 미지정.",
        "6. **slope==0 tie**: 스펙은 <0/>0 만 정의. 정확한 tie(측도 0)는 비상승으로 귀속(순수 부호).",
        "",
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return {
        "n_comp": len(comp), "dist": dict(dist),
        "ht1": ht1, "ht2": ht2, "both_pass": both_pass, "one_pass": one_pass,
    }


def main():
    frames, records, _ = build()
    out = write_report(records, frames)
    print(f"complete={out['n_comp']}  dist={out['dist']}")
    print(f"H-T1 pass={out['ht1']['pass']} (up n={out['ht1']['up']['n']}, "
          f"up mean={out['ht1']['up']['mean']}, non mean={out['ht1']['non']['mean']})")
    print(f"H-T2 pass={out['ht2']['pass']} (late_up n={out['ht2']['late_up']['n']}, "
          f"mean={out['ht2']['late_up']['mean']})")
    verdict = "BOTH PASS → C" if out["both_pass"] else ("ONE PASS → 에스컬레이션" if out["one_pass"] else "BOTH REJECT → 경로 종료")
    print(f"VERDICT: {verdict}")
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
