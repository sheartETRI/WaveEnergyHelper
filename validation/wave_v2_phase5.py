"""v2 PHASE5 (5차 위임 A~C) — 앵커 재측정(첫 바닥 피봇). 번역 충실도 교정 최종 라운드.

가설: PHASE4까지의 관측(G1-a 늦음, candidate +6.9봉, array_context 확정봉 n=0,
concordance confirmed 역전)은 모두 "확정 봉 앵커가 구조적으로 늦다"는 단일 가설을 가리킨다.
이번은 사전 확정된 앵커 하나(첫 바닥/천장 피봇)로 단발 재측정한다.

- A: 기존 데이터(확정봉 앵커 concordance)로 in_progress/confirmed/none 3군 비교 + 사전 예측 대조
- B: 첫 바닥 피봇 앵커로 array_context_p1·context_aligned_p1·concordance_p1 재주석(병존)
- C: 사전 등록 판정 H1/H2/H3 (결과 확인 후 변경 금지)

★ 재주석: 캠페인·점수는 동일 게이트·기간·파라미터로 재현(phase2.build 재사용), 태그만 앵커 이동.
  필터 적용·in-sample 재채점 없음. 앵커는 첫 바닥 피봇 하나만(복수 앵커 비교 금지).

산출물: validation/REPORT_V2_PHASE5.md
실행: `python validation/wave_v2_phase5.py`
"""
import logging
import os
import sys
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.array_context import context_aligned, context_at  # noqa: E402
from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.candle_patterns import scan_candle_patterns  # noqa: E402
from analysis.concordance import concordance_at  # noqa: E402
from analysis.pattern_scanner import ma_first_pivot_pos  # noqa: E402
from validation.wave_v2_phase2 import _agg, _pct, build  # noqa: E402
from validation.wave_v2_phase4 import concordance_separation  # noqa: E402 (확정봉 앵커, A용)

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE5.md")

# 사전 등록 판정 상수 (위임 C — 결과 확인 후 변경 금지)
H_MIN_N = 30
H3_LOW_BREAK_MAX = 0.70
OVERALL_LOW_BREAK = 0.84


def _grp(rs):
    nets = [x["net"] for x in rs if x["net"] is not None]
    lbs = [x["low_break"] for x in rs if x["low_break"] is not None]
    a = _agg(nets)
    a["low_break_rate"] = (sum(1 for x in lbs if x) / len(lbs)) if lbs else None
    return a


# ---------------------------------------------------------------- B: re-annotate at first pivot
def _anchor_p1(full, res, driver):
    lyr = str(driver.ma_or_layer)
    period = int(lyr.replace("MA", "")) if lyr.startswith("MA") else 10
    pat = "db" if res.direction == "long" else "dt"
    fp = ma_first_pivot_pos(full, period, pat, res.setup_pos)
    return res.setup_pos if fp is None else fp


def reannotate(records, frames):
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    for r in comp:
        full = frames.get((r["symbol"], r["tf"]))
        if full is None:
            continue
        anchor = _anchor_p1(full, r["res"], r["driver"])
        ctx = context_at(full, anchor)
        r["_arr_p1_label"] = ctx.label
        r["_arr_p1_aligned"] = context_aligned(ctx, r["direction"])
        r["_concord_p1"] = concordance_at(full, r["driver"].ma_or_layer, r["direction"], anchor)
        r["_anchor_p1"] = anchor
        r["_anchor_lead"] = r["res"].setup_pos - anchor   # 확정봉 대비 앵커 선행 봉수
    return comp


def candle_concord_p1(frames):
    """캔들↔소파동 합치를 첫 바닥(b1=확정-3) 앵커로 재주석한 분포."""
    dist = defaultdict(int)
    for (sym, tf), full in frames.items():
        for ev in scan_candle_patterns(full, sym, tf):
            b1 = max(0, ev.confirmed_pos - 3)
            dist[concordance_at(full, "candle", ev.direction, b1)] += 1
    return dict(dist)


# ---------------------------------------------------------------- C: pre-registered verdicts
def verdict_h1(comp):
    aligned = [r for r in comp if r.get("_arr_p1_aligned") is True]
    other = [r for r in comp if r.get("_arr_p1_aligned") is False]
    a, o = _grp(aligned), _grp(other)
    passed = (
        a["n"] >= H_MIN_N and a["mean"] is not None and o["mean"] is not None
        and a["median"] is not None and o["median"] is not None
        and a["mean"] > o["mean"] and a["median"] > o["median"]
    )
    return {"aligned": a, "other": o, "pass": passed}


def verdict_h2(comp):
    groups = defaultdict(list)
    for r in comp:
        groups[r.get("_concord_p1")].append(r)
    g = {k: _grp(v) for k, v in groups.items()}
    none = g.get("none", _grp([]))
    winners = []
    for key in ("in_progress", "confirmed"):
        cand = g.get(key)
        if cand is None:
            continue
        ok = (
            cand["n"] >= H_MIN_N and cand["mean"] is not None and none["mean"] is not None
            and cand["median"] is not None and none["median"] is not None
            and cand["mean"] > none["mean"] and cand["median"] > none["median"]
        )
        if ok:
            winners.append(key)
    return {"groups": g, "none": none, "winners": winners, "pass": bool(winners)}


def verdict_h3(comp, h1, h2):
    """통과 태그 정합군의 저점이탈 재진입율 ≤ 70% 관측(판정 아님)."""
    out = {}
    if h1["pass"]:
        out["array_context_p1(정합)"] = h1["aligned"].get("low_break_rate")
    if h2["pass"]:
        for key in h2["winners"]:
            out[f"concordance_p1({key})"] = h2["groups"][key].get("low_break_rate")
    return out


# ---------------------------------------------------------------- report
def _row(name, a):
    if a["mean"] is None:
        return f"| {name} | {a['n']} | — | — | — | — |"
    return (f"| {name} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | "
            f"{(a['win'] or 0)*100:.0f}% | {_pct(a.get('low_break_rate'))} |")


def write_report(records, frames):
    # A: 확정봉 앵커 concordance 3군 (기존 데이터)
    a_groups, _ = concordance_separation(records, frames)
    # B: 첫 바닥 피봇 앵커 재주석
    comp = reannotate(records, frames)
    candle_p1 = candle_concord_p1(frames)
    # 앵커 선행 봉수 요약
    leads = [r["_anchor_lead"] for r in comp if "_anchor_lead" in r]
    lead_mean = sum(leads) / len(leads) if leads else 0
    # C: 판정
    h1 = verdict_h1(comp)
    h2 = verdict_h2(comp)
    h3 = verdict_h3(comp, h1, h2)
    both_rejected = (not h1["pass"]) and (not h2["pass"])

    def pred_ok(g):
        ip, cf = g.get("in_progress"), g.get("confirmed")
        if not ip or not cf or ip["mean"] is None or cf["mean"] is None:
            return None
        return ip["mean"] >= cf["mean"]

    a_pred = pred_ok(a_groups)

    L = [
        "# REPORT_V2_PHASE5 — 앵커 재측정(첫 바닥 피봇). 번역 충실도 교정 최종 라운드\n",
        "선행: REPORT_V2_PHASE4(A~E). **엔진·검출기·게이트·파라미터 무수정, 저널 컬럼 추가만.**",
        "가설: PHASE4까지의 관측(G1-a 늦음·candidate +6.9봉·array_context 확정봉 n=0·concordance",
        "confirmed 역전)은 모두 **'확정 봉 앵커가 구조적으로 늦다'**는 단일 가설을 가리킨다. 이번은",
        "사전 확정된 앵커 하나(**첫 바닥/천장 피봇**)로 단발 재측정한다. 복수 앵커 비교 금지.\n",
        "> **사전 등록 판정 기준 원문(위임 C, 결과 확인 후 변경 금지 — 증빙용 인용)**:",
        "> - **H1 (array_context 유효성)**: `context_aligned_p1` n ≥ 30 AND 정합군이 비정합군보다 mean·median",
        ">   **모두** 우위 → array_context는 '게이트 승격 후보'. 어느 하나라도 미충족 → 무효(기각).",
        "> - **H2 (concordance 유효성)**: `concordance_p1` 기준 in_progress 또는 confirmed군이 none군보다",
        ">   mean·median 모두 우위(해당 군 n ≥ 30) → 상응 태그 '게이트 승격 후보'. 미충족 → 기각.",
        "> - **H3 (저점이탈 설명력)**: H1/H2 통과 태그의 정합군에서 저점이탈 재진입율이 전체(84%) 대비 뚜렷이",
        ">   낮은지(≤70%) 기록 — 판정이 아닌 관측.",
        "> - **종합**: H1·H2 모두 기각 시 → '형식화된 기법 1: 현 데이터에서 엣지 없음, 번역 충실도 교정 경로",
        ">   종료'. 어느 하나라도 통과 시 → 해당 태그 필터 사전 등록 + forward 60일 단판 제안(초안). "
        "in-sample 재채점·필터 백테스트 금지.\n",
        "## A. 늦음 가설 1차 검증 (기존 데이터 — 확정봉 앵커 concordance, 코드 변경 없음)\n",
        "사전 예측: 늦음 가설이 맞다면 **in_progress(스토캐 형성 중 MA 확정 = 상대적 이른 진입) ≥ "
        "confirmed(이중 지각)**.",
        "",
        "| 합치(확정봉 앵커) | n | net mean | net median | 승률 | 저점이탈율 |",
        "|---|---|------|--------|------|------|",
        _row("confirmed", a_groups.get("confirmed", _grp([]))),
        _row("in_progress", a_groups.get("in_progress", _grp([]))),
        _row("none", a_groups.get("none", _grp([]))),
        "",
        f"- **예측 대조**: in_progress mean {_pct(a_groups.get('in_progress', {}).get('mean'))} "
        f"vs confirmed {_pct(a_groups.get('confirmed', {}).get('mean'))} → "
        + ("예측 부합(in_progress ≥ confirmed) — 늦음 가설 지지" if a_pred is True
           else "예측과 다름 — 그대로 기록(반증 증거)" if a_pred is False
           else "표본 부족으로 판단 불가"),
        "",
        "## B. 앵커 재측정 (첫 바닥 피봇, 단발 재주석)\n",
        "- 방법: **저널 재주석**. 캠페인·점수는 phase2.build로 동일 게이트·기간·파라미터 재현(재채점 아님),",
        "  태그만 첫 바닥 피봇 앵커(`ma{p}_{db,dt}_first_pos`)로 재계산. 저널에 `array_context_p1`,",
        "  `context_aligned_p1`, `concordance_p1` 컬럼 병존(확정봉 앵커 컬럼 유지).",
        f"- 앵커 선행: 첫 바닥 피봇은 확정봉보다 평균 **{lead_mean:.1f}봉** 앞선다(n={len(leads)}).",
        "- 캔들↔소파동 합치도 동일 앵커(첫 봉 b1=확정−3)로 재주석 — 아래 분포.",
        "",
        "## C. 사전 등록 판정 결과\n",
        "### H1 — array_context 유효성 (첫 바닥 앵커)",
        "",
        "| 군 | n | net mean | net median | 승률 | 저점이탈율 |",
        "|---|---|------|--------|------|------|",
        _row("정합(context_aligned_p1)", h1["aligned"]),
        _row("비정합", h1["other"]),
        "",
        f"- 정합 n={h1['aligned']['n']} (필요 ≥{H_MIN_N}) · "
        f"mean 우위={_bool(h1['aligned']['mean'], h1['other']['mean'])} · "
        f"median 우위={_bool(h1['aligned']['median'], h1['other']['median'])}",
        f"- **H1 판정: {'통과(게이트 승격 후보)' if h1['pass'] else '기각(형식화 무효)'}**",
        "",
        "### H2 — concordance 유효성 (첫 바닥 앵커)",
        "",
        "| 합치(p1) | n | net mean | net median | 승률 | 저점이탈율 |",
        "|---|---|------|--------|------|------|",
        _row("confirmed", h2["groups"].get("confirmed", _grp([]))),
        _row("in_progress", h2["groups"].get("in_progress", _grp([]))),
        _row("none", h2["groups"].get("none", _grp([]))),
        "",
        f"- none 대비 mean·median 모두 우위 & n≥{H_MIN_N}인 군: "
        f"**{', '.join(h2['winners']) if h2['winners'] else '없음'}**",
        f"- **H2 판정: {'통과(게이트 승격 후보)' if h2['pass'] else '기각'}**",
        "",
        "### H3 — 저점이탈 설명력 (관측, 판정 아님)",
    ]
    if h3:
        L.append("")
        L.append("| 통과 태그 정합군 | 저점이탈 재진입율 | 전체(84%) 대비 |")
        L.append("|---|---|---|")
        for k, v in h3.items():
            note = "뚜렷이 낮음(≤70%)" if (v is not None and v <= H3_LOW_BREAK_MAX) else "낮지 않음"
            L.append(f"| {k} | {_pct(v)} | {note} |")
    else:
        L.append("- H1·H2 모두 기각 → 해당 관측 없음.")

    L += [
        "",
        "### 캔들↔소파동 합치 (첫 봉 앵커 재주석) 분포",
        "",
        "| 합치(p1) | 건수 |",
        "|---|---|",
    ]
    for key in ("confirmed", "in_progress", "none", "n/a"):
        if key in candle_p1:
            L.append(f"| {key} | {candle_p1[key]} |")

    # 종합 결론
    L += [
        "",
        "## 종합 결론 (사전 등록 기준에 의한 최종 판정)\n",
    ]
    if both_rejected:
        L += [
            "**H1·H2 모두 기각.** 사전 등록 기준(위임 C)에 따라:",
            "",
            "> **형식화된 기법 1: 현 데이터에서 엣지 없음. 번역 충실도 교정 경로 종료.**",
            "",
            "첫 바닥 피봇으로 앵커를 앞당겨도 array_context 정합·상응 합치 어느 쪽도 none/비정합 대비",
            "mean·median 동시 우위를 내지 못했다. 확정봉 앵커의 후행성만으로 PHASE4 관측을 설명할 수",
            "없으며, 형식화된 태그가 담아낸 신호가 성적 분리로 이어지지 않는다. 인프라(검출·저널·관측",
            "컬럼)는 보존하되 트레이딩 엣지 주장은 하지 않는다.",
        ]
    else:
        passed = []
        if h1["pass"]:
            passed.append("array_context_p1(정합)")
        if h2["pass"]:
            passed += [f"concordance_p1({w})" for w in h2["winners"]]
        L += [
            f"**통과 태그: {', '.join(passed)}.** 사전 등록 기준에 따라 해당 태그를 **필터로 사전 등록**하고",
            "forward 60일 단판 검증(G3 변형)을 제안한다(초안). **in-sample 재채점·필터 적용 백테스트는 하지 않음.**",
            "",
            "### forward 단판 검증 초안 (제안 — 실행 아님)",
            "- 등록 필터: 위 통과 태그 정합 조건을 캠페인 발행 시 라벨로만 부착(진입 게이트로 강제하지 않음).",
            "- 관측 기간: forward 60일. 지표: 통과 태그 정합군 net 기대값이 in-sample 대비 감쇠 50% 이내.",
            "- 판정: 사전 등록된 이 기준으로만 해석. 미달 시 태그 최종 기각.",
        ]

    L += [
        "",
        "## 미결 · 제안 (스코프 밖 — 기록만, 수행 안 함)\n",
        "- 추가 앵커(candidate 시점·구간 지배 상태 등) 비교는 **수행하지 않음**(위임: 복수 앵커 비교 금지).",
        "- H1/H2 기준 수치는 사전 등록값 그대로 — 아깝게 미달해도 변경 없음.",
        "- 통과 태그가 있어도 in-sample 필터 재채점은 금지(forward 제안까지만).",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return h1, h2, both_rejected, lead_mean


def _bool(x, y):
    if x is None or y is None:
        return "판단불가"
    return "예" if x > y else "아니오"


def main():
    frames, records, _ = build()
    h1, h2, both_rejected, lead_mean = write_report(records, frames)
    print(f"H1 pass={h1['pass']} (aligned n={h1['aligned']['n']})  H2 pass={h2['pass']} winners={h2['winners']}")
    print(f"anchor lead mean={lead_mean:.1f}봉  both_rejected={both_rejected}")
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
