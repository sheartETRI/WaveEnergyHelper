"""v2 PHASE3 (G1-a) — S0 검출 리뷰 시트(A) + 라이브 스캔 스냅샷(B). 검출기·규칙 무수정.

3차 위임 A·B만 수행. 김박사 O/X 기입 전이라 어떤 교정도 하지 않는다.
산출물:
- validation/g1a_charts/*.png            (이벤트별 차트)
- validation/G1A_REVIEW_SHEET.md         (A: ~40 과거 S0, 성적 컬럼 없음)
- validation/G1A_LIVE_SNAPSHOT.md        (B: 10-TF 라이브 확정 쌍바닥/쌍봉)
- validation/REPORT_V2_PHASE3.md         (표본 구성·이미지 방법·TF 분포·미결)

실행: `python validation/wave_v2_phase3.py`
"""
import logging
import os
import sys
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from analysis.campaign_promotion import PROMOTED, SUPPRESSED_BY_UPPER, resolve_promotions  # noqa: E402
from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.campaign_state_machine import prepare_base_frame  # noqa: E402
from analysis.pattern_scanner import scan_dataframe  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402
from validation.g1a_render import ensure_dir, render_ma_event  # noqa: E402
from validation.wave_v2_phase2 import build  # noqa: E402 (엔진 무수정 재사용)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
# B: 확정 스캔 풀 10개 = 동결 스펙 §1 (tf_ladder.TF_POOL). 4차 위임 A에서 12h→8h 교정.
# ⚠ 이 스크립트로 생성된 기존 REPORT_V2_PHASE3.md / G1A_LIVE_SNAPSHOT.md 는 잘못된 12h 풀
#   상태에서 산출됐다(재실행 금지 — PHASE1~3 리포트 무수정). 캐비엇은 REPORT_V2_PHASE4.md.
from analysis.tf_ladder import TF_POOL  # noqa: E402

POOL_10 = list(TF_POOL)   # ["15m","30m","1h","2h","4h","6h","8h","1d","4d","2w"]
POOL_LIMITS = {"15m": 1000, "30m": 1000, "1h": 1000, "2h": 1000, "4h": 1000,
               "6h": 1000, "8h": 1000, "1d": 800, "4d": 1000, "2w": 1000}
RECENT_BARS = 30   # 라이브에서 '활성 기준 TF 후보' = 최근 30봉 내 확정

HERE = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(HERE, "g1a_charts")
SHEET_PATH = os.path.join(HERE, "G1A_REVIEW_SHEET.md")
LIVE_PATH = os.path.join(HERE, "G1A_LIVE_SNAPSHOT.md")
REPORT_PATH = os.path.join(HERE, "REPORT_V2_PHASE3.md")

N_PROMOTED = 34
N_SUPPRESSED = 6


def _period_pat(drv):
    period = int(drv.ma_or_layer.replace("MA", ""))
    pat = "db" if drv.direction == "long" else "dt"
    return period, pat


# ---------------------------------------------------------------- A sampling
def _allocate(sizes, total):
    tot = sum(sizes.values()) or 1
    alloc = {k: max(1, round(total * v / tot)) for k, v in sizes.items()}
    # total에 맞춰 조정
    while sum(alloc.values()) > total:
        k = max(alloc, key=lambda x: alloc[x])
        if alloc[k] > 1:
            alloc[k] -= 1
        else:
            break
    while sum(alloc.values()) < total:
        k = max(sizes, key=lambda x: sizes[x])
        alloc[k] += 1
    return alloc


def _even_pick(items, k):
    if k <= 0 or not items:
        return []
    if k >= len(items):
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def sample_promoted(records):
    """층화 추출: (symbol,tf) 비례 + 각 셀 net 오름차순 균등(성적 나쁨~좋음·저점이탈 자연 포함)."""
    comp = [r for r in records if r["status"] == ST_COMPLETE and r["net"] is not None]
    groups = defaultdict(list)
    for r in comp:
        groups[(r["symbol"], r["tf"])].append(r)
    sizes = {k: len(v) for k, v in groups.items()}
    alloc = _allocate(sizes, N_PROMOTED)
    picked = []
    for key, rs in groups.items():
        rs = sorted(rs, key=lambda x: x["net"])   # 나쁨→좋음
        picked += _even_pick(rs, alloc.get(key, 0))
    return picked


def sample_suppressed(events_by_symbol, frames):
    """suppressed_by_upper 이벤트 표본 (심볼 분산)."""
    out = []
    per_sym = defaultdict(list)
    for sym, evs in events_by_symbol.items():
        for s in resolve_promotions(evs):
            if s.status == SUPPRESSED_BY_UPPER:
                per_sym[sym].append(s)
    # 심볼별 라운드로빈
    idx = 0
    while len(out) < N_SUPPRESSED and any(per_sym.values()):
        for sym in SYMBOLS:
            lst = per_sym.get(sym) or []
            if idx < len(lst):
                out.append(lst[idx])
                if len(out) >= N_SUPPRESSED:
                    break
        idx += 1
        if idx > 50:
            break
    return out


def write_review_sheet(records, events_by_symbol, frames):
    ensure_dir(CHART_DIR)
    promoted = sample_promoted(records)
    suppressed = sample_suppressed(events_by_symbol, frames)

    rows = []
    seq = 0
    tf_dist = defaultdict(int)

    def emit(drv, full_df, kind_type, supp_by=None):
        nonlocal seq
        seq += 1
        period, pat = _period_pat(drv)
        pat_ko = "쌍바닥" if pat == "db" else "쌍봉"
        fname = f"{seq:02d}_{drv.symbol}_{drv.tf}_{pat}_{drv.kind}.png"
        ok = render_ma_event(full_df, drv.symbol, drv.tf, period, pat,
                             drv.confirmed_pos, drv.kind, drv.neckline_price,
                             os.path.join(CHART_DIR, fname))
        tf_dist[drv.tf] += 1
        nl = "—" if drv.neckline_price is None else f"{drv.neckline_price:.6g}"
        ts = f"{drv.confirmed_bar:%Y-%m-%d %H:%M}"
        typ = "승격" if supp_by is None else f"억제(상위 {supp_by})"
        img = f"![{seq}](g1a_charts/{fname})" if ok else "(렌더 실패)"
        rows.append(
            f"| {seq} | {img} | {drv.symbol}·{drv.tf} | {pat_ko}({drv.kind}) | {nl} | {ts} | {typ} | ☐ O ☐ X | ☐ O ☐ X |  |"
        )

    for r in promoted:
        emit(r["driver"], frames[(r["symbol"], r["tf"])], "promoted")
    for s in suppressed:
        emit(s.driver, frames[(s.symbol, s.base_tf)], "suppressed", supp_by=s.suppressed_by)

    L = ["# G1A_REVIEW_SHEET — S0 검출 리뷰 (김박사 O/X 기입용)\n",
         "**질문은 단 둘**: (1) 이 패턴이 쌍바닥/쌍봉으로 인정되는가? (2) 이 TF를 기준 TF로 동의하는가?",
         "진입·청산·전이 판단은 이번 범위가 아닙니다. **손익/성적은 의도적으로 표시하지 않았습니다**",
         "(결과를 알면 패턴 판정이 오염되므로).\n",
         f"- 표본: 승격 {len(promoted)} + 억제 {len(suppressed)} = {len(rows)}건 · 전 이벤트 급=대파동(MA10, §5)",
         "- 층화: (심볼×TF) 비례 + 셀별 성적 오름차순 균등추출(성적 비표시). 억제=상위 TF 동시확정.",
         "- 차트: 확정 봉 전 120봉/후 30봉 · MA10 강조 + MA5/20/60 맥락 · ▲/▼ 바닥·천장 피봇 ·",
         "  파란 점선=넥라인 · 보라 세로선=확정 봉.\n",
         "| # | 차트 | 심볼·TF | 패턴(kind) | 넥라인 | 확정시각 | 유형 | 쌍바닥/봉 인정 | 기준TF 동의 | 비고 |",
         "|---|------|---------|-----------|--------|----------|------|------|------|------|"]
    L += rows
    with open(SHEET_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return len(rows), dict(tf_dist)


# ---------------------------------------------------------------- B live
def live_snapshot():
    ensure_dir(CHART_DIR)
    seq = 1000
    rows = []
    dist_hist = defaultdict(lambda: defaultdict(int))   # symbol -> tf -> 확정 총수(이력)
    active = []   # (symbol, tf, drv, bars_ago)

    for sym in SYMBOLS:
        for tf in POOL_10:
            lim = POOL_LIMITS[tf]
            bare = fetch_ohlcv_bare(sym, tf, lim, paginated=lim > 1000)
            if bare is None or bare.empty:
                continue
            full = prepare_base_frame(bare)
            events = scan_dataframe(full, sym, tf, ma_periods=[10], stoch_suffixes=[])
            ma_conf = [e for e in events if e.source == "ma" and e.clean == "clean"]
            dist_hist[sym][tf] = len(ma_conf)
            if not ma_conf:
                continue
            last_pos = len(full) - 1
            recent = [e for e in ma_conf if last_pos - e.confirmed_pos <= RECENT_BARS]
            # 최근 것 우선, 셀당 최신 1건만 차트(스냅샷 간결)
            recent.sort(key=lambda e: e.confirmed_pos, reverse=True)
            if recent:
                active.append((sym, tf, recent[0], last_pos - recent[0].confirmed_pos, full))

    L = ["# G1A_LIVE_SNAPSHOT — 현재 라이브 스캔 (지금 어느 TF를 봐야 하는가)\n",
         "지금 시점 4심볼 × 10 TF 풀 스캔. **확정(clean) 이평선 쌍바닥/쌍봉 = 현재 기준 TF 후보**.",
         "최근 30봉 내 확정만 '활성'으로 차트화(셀당 최신 1건). 급=대파동(MA10).\n",
         "> candidate(넥라인 미돌파) 상태는 검출기가 MA용 candidate 컬럼을 노출하지 않아 이번엔",
         "> 표기 불가(미결). 스토캐 candidate는 별도 존재하나 기준 TF 승격 대상이 아니라 제외.\n"]

    if not active:
        L.append("**현재 활성(최근 30봉 내) 확정 기준 TF 후보 없음.**")
    else:
        L.append("| 심볼 | TF | 패턴(kind) | 넥라인 | 확정시각 | N봉 전 | 차트 |")
        L.append("|------|----|-----------|--------|----------|--------|------|")
        for sym, tf, drv, ago, full in sorted(active, key=lambda x: (x[0], POOL_10.index(x[1]))):
            seq += 1
            period, pat = _period_pat(drv)
            pat_ko = "쌍바닥" if pat == "db" else "쌍봉"
            fname = f"live_{seq}_{sym}_{tf}_{pat}_{drv.kind}.png"
            ok = render_ma_event(full, sym, tf, period, pat, drv.confirmed_pos,
                                 drv.kind, drv.neckline_price, os.path.join(CHART_DIR, fname))
            nl = "—" if drv.neckline_price is None else f"{drv.neckline_price:.6g}"
            img = f"![]({'g1a_charts/' + fname})" if ok else "(실패)"
            L.append(f"| {sym} | {tf} | {pat_ko}({drv.kind}) | {nl} | "
                     f"{drv.confirmed_bar:%Y-%m-%d %H:%M} | {ago} | {img} |")

    with open(LIVE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return len(active), dist_hist


# ---------------------------------------------------------------- report
def write_report(n_sheet, tf_dist_a, n_active, dist_hist):
    L = ["# REPORT_V2_PHASE3 — G1-a 패턴·기준 TF 검출 리뷰 준비\n",
         "선행: PHASE2(C-1 미달). 이번은 G1 단계분해의 첫 단계 G1-a(검출·승격만, 전이/채점 제외).",
         "검출기·전이 규칙·파라미터 무수정. 김박사 O/X 기입 대기.\n",
         "## A. S0 검출 리뷰 시트",
         f"- `validation/G1A_REVIEW_SHEET.md` 생성 — {n_sheet}건(승격 {N_PROMOTED}+억제 {N_SUPPRESSED} 목표).",
         "- 층화: (심볼×TF) 비례 배분 + 셀별 net 오름차순 균등추출. **시트에 성적 미표시**(판정 오염 방지).",
         "- 이미지: mplfinance(charles 스타일·config MA색) 재사용, Malgun Gothic 한글 라벨.",
         "  전 120봉/후 30봉, 바닥·천장 피봇 마커, 넥라인 수평선, 확정 봉 세로선, S0 주석.",
         "",
         "표본 TF 분포 (A 시트):",
         "",
         "| TF | 건수 |", "|----|------|"]
    for tf in sorted(tf_dist_a, key=lambda t: tf_dist_a[t], reverse=True):
        L.append(f"| {tf} | {tf_dist_a[tf]} |")

    L += ["", "## B. 라이브 스캔 스냅샷 (10-TF 풀)",
          f"- `validation/G1A_LIVE_SNAPSHOT.md` 생성 — 활성(최근 30봉 내) 확정 기준 TF 후보 {n_active}건.",
          f"- 스캔 풀: {', '.join(POOL_10)} (사다리 6 + 중간 네이티브 4).",
          "",
          "### 10-TF 확대의 실효성 — 심볼×TF별 확정(clean) 이벤트 수(이력 전체)",
          "",
          "| 심볼 | " + " | ".join(POOL_10) + " | 합 |",
          "|------|" + "----|" * (len(POOL_10) + 1)]
    pool_tot = defaultdict(int)
    for sym in SYMBOLS:
        cells = [str(dist_hist[sym].get(tf, 0)) for tf in POOL_10]
        for tf in POOL_10:
            pool_tot[tf] += dist_hist[sym].get(tf, 0)
        L.append(f"| {sym} | " + " | ".join(cells) + f" | {sum(dist_hist[sym].get(tf,0) for tf in POOL_10)} |")
    L.append("| **합** | " + " | ".join(str(pool_tot[tf]) for tf in POOL_10) +
             f" | {sum(pool_tot.values())} |")

    L += ["",
          "- 위 분포는 스캔 풀을 {1h,4h,1d}(백테스트) → 10개로 확대할 실효성 근거 데이터다.",
          "  중간·상위 TF에서 유의미한 확정이 잡히면 확대 가치가 있고, 희소하면 사다리 축소를 검토.",
          "",
          "## 미결 · 제안 (스코프 밖 — 수행하지 않고 기록만)",
          "- **10-TF 풀 구성은 잠정**: 원본 스펙 사다리는 6개(15m·1h·4h·1d·4d·2w). '10개'의 정확한",
          "  구성은 김박사 확정 대상(현재 30m·2h·6h·12h 추가로 10 구성).",
          "- **MA candidate(넥라인 미돌파) 노출 부재**: 검출기가 MA용 candidate 컬럼을 내보내지 않아",
          "  라이브 candidate 표기 불가. 노출하려면 검출기 변경 필요(스코프 밖, 제안만).",
          "- 4d/2w는 데이터 충분성상 CORE_MA 부분집합만 동작할 수 있음(assess_tf_data). 패턴은 MA10",
          "  기반이라 대개 계산 가능하나, 상위 MA 문맥선은 결측일 수 있음.",
          "",
          "## 이후 절차 (이번 위임 아님)",
          "- 김박사 O/X 기입 → X 비율·유형 분석 → 유의하면 검출 정의 교정(G1-a 재실행), 낮으면 G1-b(전이 검토).",
          "- G2' 숫자 재해석은 G1-a/b 완료 후.",
          ""]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    frames, records, events_by_symbol = build()
    n_sheet, tf_dist_a = write_review_sheet(records, events_by_symbol, frames)
    n_active, dist_hist = live_snapshot()
    write_report(n_sheet, tf_dist_a, n_active, dist_hist)
    print(f"A sheet rows={n_sheet}  B active={n_active}")
    print(f"wrote {os.path.relpath(SHEET_PATH)}, {os.path.relpath(LIVE_PATH)}, {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
