"""v2 PHASE2 — G1 검토 패키지(A) + G2' 강건성 판정(C). 엔진 무수정.

2차 위임 A~C 수행 스크립트. B(G1 피드백 반영)는 김박사 FAIL 판정이 있을 때만 조건부이며,
본 스크립트는 검토 전이라 스킵한다(리포트에 명시). C는 파라미터 조정 없이 기존 캠페인을
분할 채점만 한다.

산출물:
- validation/G1_REVIEW_PACKAGE.md   (A: 12 케이스, 김박사 기입란)
- validation/REPORT_V2_PHASE2.md    (C-1/C-2 게이트 판정, C-3 관측 통계)

실행: `python validation/wave_v2_phase2.py`
"""
import logging
import os
import sys
import warnings
from collections import defaultdict
from statistics import median, mean

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from analysis.campaign_promotion import PROMOTED, SUPPRESSED_BY_UPPER, resolve_promotions  # noqa: E402
from analysis.campaign_score import ST_COMPLETE, make_campaign_id, score_campaign  # noqa: E402
from analysis.campaign_state_machine import (  # noqa: E402
    ALL_SUFFIXES,
    macd_cross_at,
    prepare_base_frame,
    replay_campaign,
)
from analysis.pattern_scanner import scan_dataframe  # noqa: E402
from analysis.tf_ladder import upper  # noqa: E402
from config.settings import WAVE_LAYER_ROLES  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
TFS = ["1h", "4h", "1d"]
LIMITS = {"1h": 3000, "4h": 3000, "1d": 1500}
_LARGE = WAVE_LAYER_ROLES["large"]

HERE = os.path.dirname(os.path.abspath(__file__))
G1_PATH = os.path.join(HERE, "G1_REVIEW_PACKAGE.md")
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE2.md")

# C 게이트 (사전 확정 — 결과 확인 후 변경 금지)
C1_LATE_MIN_EXP = 0.005
C1_LATE_MIN_N = 40
C2_MIN_MEDIAN = 0.0
C2_MIN_MEAN = 0.005
C2_MIN_N = 30


def _pct(x):
    return "—" if x is None else f"{x * 100:+.2f}%"


# ---------------------------------------------------------------- build
def build():
    frames = {}
    records = []          # 캠페인 레코드(전 상태)
    events_by_symbol = defaultdict(list)   # C-3(2) 억제 판정용 승격가능 이벤트

    for sym in SYMBOLS:
        for tf in TFS:
            lim = LIMITS[tf]
            bare = fetch_ohlcv_bare(sym, tf, lim, paginated=lim > 1000)
            if bare is None:
                continue
            full = prepare_base_frame(bare)
            frames[(sym, tf)] = full
            events = scan_dataframe(full, sym, tf, ma_periods=[10], stoch_suffixes=[])
            promos = [p for p in resolve_promotions(events) if p.status == PROMOTED]
            promos.sort(key=lambda p: p.driver.confirmed_pos)
            events_by_symbol[sym].extend(events)

            last_close = -1
            for p in promos:
                sp = p.driver.confirmed_pos
                if sp <= last_close:
                    continue
                res = replay_campaign(full, sym, tf, p.direction, sp, p.driver.ma_or_layer, sp)
                score = score_campaign(res, full)
                last_close = res.exit_final.pos if res.exit_final else len(full) - 1
                records.append({
                    "symbol": sym, "tf": tf, "res": res, "score": score,
                    "driver": p.driver, "cid": make_campaign_id(res),
                    "setup_ts": res.setup_ts, "net": score.combined_net,
                    "t2": score.t2_return, "status": score.status,
                    "low_break": score.entry2_after_low_break,
                    "direction": res.direction,
                })
    return frames, records, events_by_symbol


# ---------------------------------------------------------------- A: G1 detail
def _correction_bar(full, res):
    if res.exit1 is None:
        return None, None
    pat = "dt" if res.direction == "long" else "db"
    end = res.entry2.pos if res.entry2 else len(full) - 1
    for pos in range(res.exit1.pos + 1, end + 1):
        for sfx in ALL_SUFFIXES:
            col = f"stoch_{pat}_{sfx}"
            if col in full.columns and not pd.isna(full[col].iloc[pos]):
                return full.index[pos], sfx
    return None, None


def _regc_bar(full, res):
    if res.entry2 is None or res.exit1 is None:
        return None
    last = None
    for pos in range(res.exit1.pos + 1, res.entry2.pos + 1):
        if macd_cross_at(full, pos) == "gc":
            last = full.index[pos]
    return last


def _s7_trigger(full, res):
    if res.exit_final is None:
        return "미종료"
    pos = res.exit_final.pos
    lp = "dt" if res.direction == "long" else "db"
    if f"stoch_{lp}_{_LARGE}" in full.columns and not pd.isna(full[f"stoch_{lp}_{_LARGE}"].iloc[pos]):
        return "대파동 스토캐 " + ("쌍봉" if res.direction == "long" else "쌍바닥")
    if f"ma10_{lp}" in full.columns and not pd.isna(full[f"ma10_{lp}"].iloc[pos]):
        return "MA10 " + ("쌍봉" if res.direction == "long" else "쌍바닥")
    return "트리거 미상"


def _case_block(rec, frames, idx):
    res, score, drv = rec["res"], rec["score"], rec["driver"]
    full = frames[(rec["symbol"], rec["tf"])]
    up = "상향" if res.direction == "long" else "하향"
    pat = "쌍바닥" if res.direction == "long" else "쌍봉"
    corr_ts, corr_sfx = _correction_bar(full, res)
    regc = _regc_bar(full, res)
    period = f"{res.setup_ts:%Y-%m-%d} ~ {(res.exit_final.ts if res.exit_final else full.index[-1]):%Y-%m-%d}"

    L = [f"### 케이스 {idx}: {rec['symbol']} · {rec['tf']} · {res.direction} · {score.status}",
         f"- 기간: {period}  ·  발단 MA: {res.setup_layer}"
         + (f"  ·  강화(스토캐 삼중 {res.strength_layer})" if res.strength_flag else ""),
         "",
         "**S0~S7 전이 타임라인**", ""]

    def line(tag, tp, extra=""):
        if tp is None:
            return f"- {tag}: —"
        return f"- {tag}: {tp.ts:%Y-%m-%d %H:%M}  가격 {tp.price:.6g}  {extra}"

    nl = "—" if drv.neckline_price is None else f"{drv.neckline_price:.6g}"
    L.append(f"- **S0 SETUP**: {res.setup_ts:%Y-%m-%d %H:%M}  {res.setup_layer} {pat}({'HL' if res.direction=='long' else 'LH'})  넥라인 {nl} {up} 돌파")
    L.append(line("**S1→S2 ENTRY-1**", res.entry1, f"[MACD {'GC' if res.direction=='long' else 'DC'}]"))
    L.append(line("**S3→S4 EXIT-1**", res.exit1, f"[MACD {'DC' if res.direction=='long' else 'GC'}]" if res.direction == "long" else "[MACD GC · 무매매 웨이포인트]"))
    corr = f"{corr_ts:%Y-%m-%d %H:%M} ({corr_sfx})" if corr_ts is not None else "미확정"
    L.append(f"- **S5 WAVE-2**: 조정 주도 스토캐 확정 {corr} → 예측 구간 {res.predicted_region_label} (급 {res.predicted_grade})")
    regc_s = f"{regc:%Y-%m-%d %H:%M}" if regc is not None else "—"
    L.append(line("**S6 ENTRY-2**", res.entry2, f"[구간 도달 AND 재GC({regc_s}) 동시 충족]"))
    L.append(line("**S7 청산**", res.exit_final, f"[{_s7_trigger(full, res)}]"))
    L.append("")
    L.append(f"**손익**: T1 {_pct(score.t1_return)} · T2 {_pct(score.t2_return)} · 합산(net) {_pct(score.combined_net)}  ·  "
             f"MAE(T2) {_pct(score.mae_t2)} · 저점이탈후재진입 {score.entry2_after_low_break}")
    L.append("")
    L.append("**김박사 대조 체크포인트**")
    L.append(f"- [ ] {res.setup_ts:%Y-%m-%d %H:%M} 봉에서 {res.setup_layer} {pat} 넥라인 {nl} {up} 돌파 확인")
    if res.entry1:
        L.append(f"- [ ] {res.entry1.ts:%Y-%m-%d %H:%M} 봉에서 MACD {'골든' if res.direction=='long' else '데드'}크로스 확인")
    if corr_ts is not None:
        L.append(f"- [ ] {corr_ts:%Y-%m-%d %H:%M} 봉에서 스토캐 {corr_sfx} {'쌍봉' if res.direction=='long' else '쌍바닥'}(조정 주도) 확인 → 예측 {res.predicted_region_label}")
    if res.entry2:
        L.append(f"- [ ] {res.entry2.ts:%Y-%m-%d %H:%M} 봉에서 예측 구간 도달 + MACD 재GC 동시 충족 확인")
    if res.exit_final:
        L.append(f"- [ ] {res.exit_final.ts:%Y-%m-%d %H:%M} 봉에서 청산 트리거({_s7_trigger(full, res)}) 확인")
    L.append("")
    L.append("**검토란**: PASS / FAIL / 비고 → `____________________________`")
    L.append("\n---\n")
    return "\n".join(L)


def select_cases(records):
    """12 케이스 선정 (위임 A 기준). 결정론적."""
    comp = [r for r in records if r["status"] == ST_COMPLETE]
    chosen, ids = [], set()

    def take(pred, k, order=None, reverse=False):
        pool = [r for r in comp if r["cid"] not in ids and pred(r)]
        if order:
            pool = sorted(pool, key=order, reverse=reverse)
        for r in pool[:k]:
            chosen.append(r); ids.add(r["cid"])

    # 1) ETHUSDT 4h (ETHKRW 대체)
    take(lambda r: r["symbol"] == "ETHUSDT" and r["tf"] == "4h", 1, order=lambda r: r["setup_ts"])
    # 2) 저점이탈 재진입 4건
    take(lambda r: r["low_break"] is True, 4, order=lambda r: r["setup_ts"])
    # 3) 1h 손실 2건
    take(lambda r: r["tf"] == "1h" and (r["net"] or 0) < 0, 2, order=lambda r: r["net"])
    # 4) 1d 대형 승리 2건 (BNB/SOL)
    take(lambda r: r["tf"] == "1d" and r["symbol"] in ("BNBUSDT", "SOLUSDT") and (r["net"] or 0) > 0,
         2, order=lambda r: r["net"], reverse=True)
    # 5) 매도 캠페인 1건
    take(lambda r: r["direction"] == "short", 1, order=lambda r: r["setup_ts"])
    # 6) 나머지 무작위(결정론적 균등 간격)
    remain = [r for r in comp if r["cid"] not in ids]
    remain = sorted(remain, key=lambda r: r["cid"])
    step = max(1, len(remain) // max(1, (12 - len(chosen))))
    for r in remain[::step]:
        if len(chosen) >= 12:
            break
        chosen.append(r); ids.add(r["cid"])
    return chosen[:12]


def write_g1_package(records, frames):
    cases = select_cases(records)
    L = ["# G1_REVIEW_PACKAGE — 엔진 정합 검토 (김박사 기입용)\n",
         "선행: REPORT_V2_PHASE1 (G2 예비 통과). 아래 12 케이스의 전이 타임라인을 차트와 대조해",
         "각 케이스 **검토란**에 PASS/FAIL/비고를 기입해 주세요. FAIL이 있으면 PHASE2-B(전이 규칙",
         "데이터 테이블 수정 → G2 재실행)를 수행합니다.\n",
         "- 데이터: 바이낸스 KRW 미지원 → **ETHKRW 4h는 ETHUSDT 4h로 대체**(케이스 1, 명시).",
         "- 모든 전이는 봉 마감 확정값 기준(as-of). 재GC 시각은 EXIT-1 이후 마지막 골든크로스 봉.",
         f"- 케이스 수: {len(cases)}  ·  선정 기준: ETH4h·저점이탈4·1h손실2·1d대승2·매도1·무작위2\n",
         "---\n"]
    for i, rec in enumerate(cases, 1):
        L.append(_case_block(rec, frames, i))
    with open(G1_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return len(cases)


# ---------------------------------------------------------------- C
def _agg(nets):
    nets = [x for x in nets if x is not None]
    if not nets:
        return {"n": 0, "mean": None, "median": None, "win": None}
    return {"n": len(nets), "mean": mean(nets), "median": median(nets),
            "win": sum(1 for x in nets if x > 0) / len(nets)}


def c1_temporal(records):
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    by_cell = defaultdict(list)
    for r in comp:
        by_cell[(r["symbol"], r["tf"])].append(r)
    early, late = [], []
    for rs in by_cell.values():
        rs = sorted(rs, key=lambda x: x["setup_ts"])
        mid = len(rs) // 2
        early += rs[:mid]; late += rs[mid:]
    ov = {"early": _agg([r["net"] for r in early]), "late": _agg([r["net"] for r in late])}
    per_tf = {}
    for tf in TFS:
        e = [r["net"] for r in early if r["tf"] == tf]
        l = [r["net"] for r in late if r["tf"] == tf]
        per_tf[tf] = {"early": _agg(e), "late": _agg(l)}
    passed = (ov["late"]["mean"] is not None and ov["late"]["mean"] >= C1_LATE_MIN_EXP
              and ov["late"]["n"] >= C1_LATE_MIN_N)
    return ov, per_tf, passed


def c2_per_tf(records):
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    out = {}
    for tf in TFS:
        a = _agg([r["net"] for r in comp if r["tf"] == tf])
        passed = (a["n"] >= C2_MIN_N and a["median"] is not None
                  and a["median"] >= C2_MIN_MEDIAN and a["mean"] >= C2_MIN_MEAN)
        out[tf] = {"agg": a, "pass": passed}
    return out


def c3_stats(records, frames, events_by_symbol):
    comp = [r for r in records if r["status"] == ST_COMPLETE]
    # (1) 저점이탈 vs 비이탈 T2
    lb = [r["t2"] for r in comp if r["low_break"] is True and r["t2"] is not None]
    nlb = [r["t2"] for r in comp if r["low_break"] is False and r["t2"] is not None]
    stat1 = {"low_break": _agg(lb), "non_low_break": _agg(nlb)}

    # (2) suppressed_by_upper 가상 성적 (심볼별 cross-TF resolve)
    supp_nets, supp_n = [], 0
    for sym, evs in events_by_symbol.items():
        for s in resolve_promotions(evs):
            if s.status != SUPPRESSED_BY_UPPER:
                continue
            supp_n += 1
            full = frames.get((sym, s.base_tf))
            if full is None:
                continue
            res = replay_campaign(full, sym, s.base_tf, s.direction,
                                  s.driver.confirmed_pos, s.driver.ma_or_layer, s.driver.confirmed_pos)
            sc = score_campaign(res, full)
            if sc.combined_net is not None:
                supp_nets.append(sc.combined_net)
    stat2 = {"n_suppressed": supp_n, "virtual": _agg(supp_nets)}

    # (3) upper_alignment 일치/불일치 (setup 시점 상위 TF MA120 vs MA240)
    aligned, misaligned = [], []
    for r in comp:
        up = upper(r["tf"])
        uf = frames.get((r["symbol"], up)) if up else None
        if uf is None:
            continue
        cut = uf.loc[uf.index <= r["setup_ts"]]
        if cut.empty:
            continue
        last = cut.iloc[-1]
        m120, m240 = last.get("MA120"), last.get("MA240")
        if m120 is None or m240 is None or pd.isna(m120) or pd.isna(m240):
            continue
        regime_up = m120 > m240
        is_aligned = (r["direction"] == "long" and regime_up) or (r["direction"] == "short" and not regime_up)
        (aligned if is_aligned else misaligned).append(r["net"])
    stat3 = {"aligned": _agg(aligned), "misaligned": _agg(misaligned)}
    return stat1, stat2, stat3


def _row(name, a):
    return f"| {name} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | {a['win']*100:.0f}% |" \
        if a["mean"] is not None else f"| {name} | {a['n']} | — | — | — |"


def write_report(records, frames, events_by_symbol, n_cases):
    ov, per_tf, c1_pass = c1_temporal(records)
    c2 = c2_per_tf(records)
    s1, s2, s3 = c3_stats(records, frames, events_by_symbol)

    L = ["# REPORT_V2_PHASE2 — G1 준비 + G2' 강건성 판정\n",
         "선행: REPORT_V2_PHASE1 (G2 예비: n=223, net +1.45%). 엔진 무수정.\n",
         "## A. G1 검토 패키지",
         f"- `validation/G1_REVIEW_PACKAGE.md` 생성 ({n_cases} 케이스, 김박사 기입 대기).",
         "- ETHKRW 4h → ETHUSDT 4h 대체(바이낸스 KRW 미지원).\n",
         "## B. G1 피드백 반영 — **미수행(스킵)**",
         "- 김박사 FAIL 판정이 아직 없음(검토란 미기입). 조건부 파트라 스킵.",
         "- **중요**: PHASE1/PHASE2 수치는 G1 실제 PASS 서명 전까지 여전히 PRELIMINARY다.",
         "  'FAIL 부재'는 '검토 미실시' 때문이며 자동 확정 승격 근거가 아니다(정직성).\n",
         "## C-1. Temporal split (전반/후반 50:50, 셀별 캠페인 시작시각 기준)\n",
         f"- 게이트(사전 확정): 후반 net 기대값(mean) ≥ +0.50% **AND** 후반 n ≥ 40",
         "",
         "| 구간 | n | 기대값(mean) | median | 승률 |",
         "|------|---|------|--------|------|",
         _row("전반", ov["early"]),
         _row("후반", ov["late"]),
         "",
         f"- **판정: {'통과(PASS)' if c1_pass else '미달(FAIL)'}** "
         f"(후반 mean {_pct(ov['late']['mean'])}, n {ov['late']['n']})",
         f"- v1 감쇠 패턴(전반 6.85→후반 1.42) 대조: 전반 {_pct(ov['early']['mean'])} → 후반 {_pct(ov['late']['mean'])}",
         "",
         "TF별 전반/후반:",
         "",
         "| TF | 전반 n | 전반 mean | 후반 n | 후반 mean |",
         "|----|-----|------|-----|------|"]
    for tf in TFS:
        e, l = per_tf[tf]["early"], per_tf[tf]["late"]
        L.append(f"| {tf} | {e['n']} | {_pct(e['mean'])} | {l['n']} | {_pct(l['mean'])} |")

    L += ["", "## C-2. TF별 분리 판정\n",
          "- 게이트(TF별): net median ≥ 0% **AND** net mean ≥ +0.50% **AND** n ≥ 30",
          "",
          "| TF | n | mean | median | 승률 | 판정 | G3 대상 |",
          "|----|---|------|--------|------|------|--------|"]
    for tf in TFS:
        a = c2[tf]["agg"]
        ok = c2[tf]["pass"]
        g3 = "예 (forward 관측)" if ok else "아니오 (검증 미달 라벨)"
        L.append(f"| {tf} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | "
                 f"{a['win']*100:.0f}% | {'통과' if ok else '미달'} | {g3} |")
    passed_tfs = [tf for tf in TFS if c2[tf]["pass"]]
    L.append("")
    L.append(f"- G3 forward 관측 대상 TF: **{', '.join(passed_tfs) if passed_tfs else '없음'}**. "
             f"미달 TF는 시그널 카드에서 '검증 미달' 라벨(발행은 하되 등급 구분).")
    # 정직 캐비엇: C-2 통과라도 C-1 후반이 음(-)이면 그 통과는 전반 편중일 수 있다(기록만).
    frag = [tf for tf in passed_tfs
            if per_tf[tf]["late"]["mean"] is not None and per_tf[tf]["late"]["mean"] < C2_MIN_MEAN]
    if frag:
        L.append(f"- ⚠ 캐비엇: {', '.join(frag)}는 C-2 통과지만 C-1 후반 mean이 게이트 미만 "
                 f"({', '.join(tf + ' ' + _pct(per_tf[tf]['late']['mean']) for tf in frag)}) "
                 f"— 통과가 전반 편중일 수 있음. G3에서 최우선 관찰.")

    L += ["", "## C-3. 부가 관측 통계 (판정 아님, 기록만)\n",
          "### (1) 저점이탈 재진입군 vs 비이탈군 — T2 성적",
          "",
          "| 군 | n | T2 mean | T2 median | 승률 |",
          "|----|---|------|--------|------|",
          _row("저점이탈(low_break)", s1["low_break"]),
          _row("비이탈", s1["non_low_break"]),
          "",
          f"### (2) suppressed_by_upper 가상 성적 (cross-TF 억제, 심볼별 재해석)",
          f"- 억제 이벤트 수: {s2['n_suppressed']}  ·  가상 캠페인 채점:",
          "",
          "| | n | mean | median | 승률 |",
          "|--|---|------|--------|------|",
          _row("억제된(가상)", s2["virtual"]),
          "",
          "### (3) upper_alignment 일치/불일치 (setup 시점 상위 TF MA120 vs 240)",
          "",
          "| 군 | n | net mean | net median | 승률 |",
          "|----|---|------|--------|------|",
          _row("정합(aligned)", s3["aligned"]),
          _row("불일치", s3["misaligned"]),
          "",
          "> C-3은 향후 필터 승격의 관측 데이터일 뿐 이번 판정에 반영하지 않는다(스코프 규율).",
          ""]

    # 결론
    g3_ready = c1_pass and len(passed_tfs) > 0
    L += ["## 결론 — G3(forward 60일) 개시 조건\n",
          f"- C-1 temporal: {'통과' if c1_pass else '미달'}  ·  C-2 통과 TF: {', '.join(passed_tfs) or '없음'}",
          f"- **G3 개시 조건**: {'충족 (단 G1 서명 전이라 PRELIMINARY)' if g3_ready else '미충족'}. "
          "실제 개시는 G1 PASS 서명 후.",
          "",
          "## 미결 · 제안 (스코프 밖 — 수행하지 않고 기록만)",
          "- 저점이탈군의 T2가 비이탈군 대비 유의미하게 낮다면 '저점 이탈 시 보류' 필터 후보(C-3-1 근거). 도입 금지, 제안만.",
          "- upper_alignment 정합군 우세 시 상위 정합 게이트 승격 후보(C-3-3). 관측 지속.",
          "- 1h 미달 확정 시 1h 캠페인 개선(필터/튜닝) 시도 금지 — 미달 판정 자체가 산출물.",
          "- PRELIMINARY 해제는 G1 실제 PASS 서명을 조건으로 한다.",
          ""]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return c1_pass, passed_tfs, g3_ready


def main():
    frames, records, events_by_symbol = build()
    n_cases = write_g1_package(records, frames)
    c1_pass, passed_tfs, g3_ready = write_report(records, frames, events_by_symbol, n_cases)
    print(f"records={len(records)} G1_cases={n_cases}")
    print(f"C-1 temporal PASS={c1_pass}  C-2 통과 TF={passed_tfs}  G3_ready(엔진기준)={g3_ready}")
    print(f"wrote {os.path.relpath(G1_PATH)} , {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
