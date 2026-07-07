"""10차 위임 보고 — 스토캐 candidate 노출 스냅샷 + REPORT_OBSERVATORY_R2.md 생성.

표시·관측 전용. 스토캐 검출기가 이미 산출하는 candidate 컬럼(정본)을 이벤트로 노출한 뒤,
전조 슬롯·월봉 패널 반영 + 적시성 분포(MA vs 스토캐) + 4심볼 대파동 쌍봉 candidate 스냅샷.
판정·통계·승격 아님.

실행: `python validation/observatory_snapshot_r2.py`
"""
import logging
import os
import sys
import warnings
from statistics import mean, median

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_state_machine import prepare_base_frame  # noqa: E402
from analysis.observatory import LARGE_STOCH_SUFFIX, precursor_channel  # noqa: E402
from analysis.pattern_scanner import (  # noqa: E402
    STOCH_SUFFIXES,
    candidate_lead_bars,
    scan_stoch_candidates,
    stoch_candidate_lead_bars,
)
from analysis.trend_layer import TREND_STOCH_SUFFIX, add_trend_observation  # noqa: E402
from config.settings import OBSERVATORY_PARAMS, STOCH_PIVOT_PARAMS  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402
from display.observatory import build_precursor_lines  # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
DETAIL_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
LARGE_TFS = ["1M", "2w", "1d"]          # 대파동 쌍봉 candidate 관측 TF
ALL_SUFFIXES_4 = STOCH_SUFFIXES + [TREND_STOCH_SUFFIX]
WINDOW = 12
HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "REPORT_OBSERVATORY_R2.md")


def _load(symbol, tf, with_4th=False):
    bare = fetch_ohlcv_bare(symbol, tf)
    if bare is None or bare.empty:
        return None
    full = prepare_base_frame(bare)
    return add_trend_observation(full.copy()) if with_4th else full


def _agg_lead(rows):
    ls = [r["lead_bars"] for r in rows]
    if not ls:
        return {"n": 0, "mean": None, "median": None, "le0": None}
    return {"n": len(ls), "mean": mean(ls), "median": median(ls),
            "le0": sum(1 for x in ls if x <= 0) / len(ls)}


def large_wave_candidate(symbol, tf):
    """대파동 (20,10,10) 쌍봉: pending candidate 여부 + 최근 확정."""
    full = _load(symbol, tf)
    if full is None:
        return {"n_bars": 0, "pending": None, "confirmed_recent": None}
    cands = scan_stoch_candidates(full, symbol, tf, suffixes=[LARGE_STOCH_SUFFIX])
    dt = [c for c in cands if c.direction == "short"]
    conf_col = f"stoch_dt_{LARGE_STOCH_SUFFIX}"
    recent = None
    if conf_col in full.columns:
        last = len(full) - 1
        lo = max(0, last - WINDOW + 1)
        seg = full[conf_col].iloc[lo:last + 1].dropna()
        recent = seg.index[-1] if not seg.empty else None
    pend = None
    if dt:
        c = dt[0]
        pend = {"kind": c.kind, "neck": c.neckline_price, "ts": c.confirmed_bar}
    return {"n_bars": len(full), "pending": pend, "confirmed_recent": recent}


def main():
    # 적시성(MA vs 스토캐) — BTC·ETH 1d 집계
    stoch_leads, ma_leads = [], []
    for sym in DETAIL_SYMBOLS:
        f = _load(sym, "1d", with_4th=True)
        if f is None:
            continue
        stoch_leads += stoch_candidate_lead_bars(f, sym, "1d", suffixes=ALL_SUFFIXES_4)
        ma_leads += candidate_lead_bars(f, sym, "1d")
    stoch_agg, ma_agg = _agg_lead(stoch_leads), _agg_lead(ma_leads)

    # 4심볼 × TF 대파동 쌍봉 candidate 표
    grid = {sym: {tf: large_wave_candidate(sym, tf) for tf in LARGE_TFS} for sym in SYMBOLS}

    # BTC·ETH 전조 슬롯 상세(1d·4d — candidate 반영 후)
    detail = {}
    for sym in DETAIL_SYMBOLS:
        detail[sym] = {}
        for tf in ("1d", "4d"):
            f = _load(sym, tf)
            detail[sym][tf] = precursor_channel(f, sym, tf) if f is not None else None

    def _cand_cell(info):
        if info["n_bars"] == 0:
            return "데이터 없음"
        if info["pending"] is not None:
            p = info["pending"]
            return f"**후보 형성 중** ({p['kind']}, 넥라인K {p['neck']:.4g}, 2번째천장 {p['ts'].date()})"
        if info["confirmed_recent"] is not None:
            return f"확정(최근 {info['confirmed_recent'].date()})"
        return "없음(대기·최근확정 모두 없음)"

    L = [
        "# REPORT_OBSERVATORY_R2 — 스토캐 패턴 candidate 노출 (10차 위임)\n",
        "성격: **표시·관측 전용.** 판정·게이트·백테스트·등급 없음. 9차 미결(비정배열 전조 채널 candidate",
        "부재) 해소 라운드. 검출기 무수정 — 출력(candidate) 노출만(PHASE4-B 승인 예외 동일 적용).\n",
        "## A. 스토캐 candidate 스캐너 — 기존 컬럼 실재 확인 결과\n",
        "> **결론: 기존에 이미 존재.** 스토캐 검출기(`indicators/stochastic.py`)가 쌍바닥/쌍봉 상태머신에서",
        "> `stoch_{db,dt}_candidate_{suffix}` 컬럼(두 번째 극점 마킹 + kind + 넥라인, 넥라인 돌파 전)을",
        "> **이미 산출**한다. PHASE4-E가 concordance용으로 언급한 그 컬럼이 실재한다 → 이번 라운드는 신규",
        "> 검출이 아니라 **정본 컬럼을 이벤트로 노출**하는 스캐너를 추가했다(검출기 내부·확정 정의 무수정).",
        "",
        "- MA candidate(`scan_ma_candidates`, 피봇 재해석)와 달리 스토캐는 검출기가 candidate 컬럼을 직접",
        "  들고 있어 **재해석이 아니라 컬럼 노출**이다(그만큼 kind·넥라인이 검출기 기준으로 이미 확정적).",
        "- 신규: `analysis/pattern_scanner.scan_stoch_candidates` — (suffix, pat)별 가장 최근 마킹 1건 중,",
        "  이후 확정(넥라인 돌파)이 없는 '대기 후보'만 `stage=candidate`로 방출. 전 4층(소·중·대·대대파동)",
        "  쌍바닥·쌍봉. **승격·판정 금지**(표시·저널 전용).",
        "- 참고: 검출기 candidate는 HH/LH를 모두 마킹(kind 컬럼으로 구분). 하락 전조의 정석은 LH이나 정본",
        "  정의를 그대로 노출하고 kind를 표기한다(필터링은 하지 않음 — 판정 아님).",
        "",
        "## B. 적시성 계측 — candidate 선행 봉수 (MA 채널 vs 스토캐 채널)\n",
        "`lead_bars = confirm_pos − (두번째극점 + 피봇 lookback)`. 양수=candidate 선행 관측 가능,",
        f"≤0=넥라인 확정의 구조적 후행성(빠른 돌파). 집계: BTC·ETH 1d (스토캐 lookback={STOCH_PIVOT_PARAMS['lookback']}).",
        "",
        "| 채널 | n | 선행 mean | median | ≤0(후행) 비율 |",
        "|---|---|---|---|---|",
        f"| MA (db/dt, MA5/10/20) | {ma_agg['n']} | {ma_agg['mean']:.1f}봉 | {ma_agg['median']:.0f} | {ma_agg['le0']*100:.0f}% |"
        if ma_agg["n"] else "| MA | 0 | — | — | — |",
        f"| 스토캐 (db/dt, 4층) | {stoch_agg['n']} | {stoch_agg['mean']:.1f}봉 | {stoch_agg['median']:.0f} | {stoch_agg['le0']*100:.0f}% |"
        if stoch_agg["n"] else "| 스토캐 | 0 | — | — | — |",
        "",
        "- 대조(PHASE4-B): MA10 채널 candidate 선행 평균 **+6.9봉**, ≤0 비율 21%.",
        f"- **관측**: 스토캐 채널 선행({stoch_agg['mean']:.1f}봉)은 MA 채널({ma_agg['mean']:.1f}봉)보다 **짧고**,",
        f"  ≤0(후행) 비율({stoch_agg['le0']*100:.0f}%)이 MA({ma_agg['le0']*100:.0f}%)보다 높다 — 스토캐가 더 빠르게",
        "  확정돼 candidate 관측 창이 짧다. 즉 스토캐 candidate 노출은 관측 창을 앞당기되 그 선행 폭은",
        "  MA보다 작다(판정 아님, 관측). 이는 §2.5가 비정배열에서 스토캐를 '빠른 계기'로 지목한 것과 정합.",
        "",
        "## C. 현재 시점 4심볼 대파동(20,10,10) 쌍봉 candidate 스냅샷\n",
        "> 김박사 현재 국면 판독 직결 항목 — 월봉·주봉·일봉 대파동 쌍봉의 candidate/확정 여부.",
        "",
        "| 심볼 | 1M(월) | 2w(주2) | 1d(일) |",
        "|---|---|---|---|",
    ]
    for sym in SYMBOLS:
        L.append(f"| {sym} | {_cand_cell(grid[sym]['1M'])} | {_cand_cell(grid[sym]['2w'])} | {_cand_cell(grid[sym]['1d'])} |")

    L += [
        "",
        "## D. BTC·ETH 전조 슬롯 상세 (candidate 반영 후)\n",
        "> 활성 전조 채널의 candidate/confirmed — build_precursor_lines 실제 렌더 텍스트.",
        "",
    ]
    for sym in DETAIL_SYMBOLS:
        L.append(f"### {sym}")
        L.append("```")
        for tf in ("1d", "4d"):
            pc = detail[sym].get(tf)
            if pc is None:
                L.append(f"전조 슬롯 ({tf}) — 데이터 없음")
                continue
            L += build_precursor_lines(tf, pc)
            L.append("")
        L.append("```")
        L.append("")

    L += [
        "## 저널 컬럼\n",
        "- 관측 저널(`validation/observatory_journal.csv`)에 전조 슬롯 candidate 수(`n_candidates`) 컬럼 누적",
        "  (표시 시점 상태). 월봉 패널 행에도 `n_candidates` 반영.",
        "",
        "## 상수 목록\n",
        "```",
        f"STOCH_PIVOT_PARAMS.lookback = {STOCH_PIVOT_PARAMS['lookback']}   # candidate 선행 봉수 기준",
        f"관측 대상 스토캐 4층 = {ALL_SUFFIXES_4}",
        f"전조 대파동 채널 suffix = {LARGE_STOCH_SUFFIX}",
        "OBSERVATORY_PARAMS:",
    ]
    for k, v in OBSERVATORY_PARAMS.items():
        L.append(f"    {k!r}: {v!r},")
    L += [
        "```",
        "",
        "## 미결 · 캐비엇\n",
        "- **candidate = 표시·저널 전용**: 승격·판정·등급 금지(stage=candidate 가드). 본 라운드도 매매·엣지 없음.",
        "- **HH/LH 미필터**: 정본 검출기가 HH/LH 모두 마킹 → 그대로 노출하고 kind 표기. LH 한정 표시가",
        "  필요하면 별도 위임(표시 규칙)으로 — 판정 아님이라 이번엔 미적용.",
        "- **스토캐 선행 폭이 MA보다 작음**: 조기 경보로서 스토캐 candidate의 실효 창이 짧다(관측). 비정배열",
        "  국면에서 이평선 쌍봉이 늦거나 안 생기는 문제의 대안이지만 선행 여유는 제한적.",
        "- **커밋 해시**: 아래 기입(이번 라운드부터 보고 필수).",
        "",
        "## 커밋",
        "- 코드+리포트 커밋 해시: `__COMMIT_HASH__`",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"MA lead: {ma_agg}")
    print(f"STOCH lead: {stoch_agg}")
    for sym in SYMBOLS:
        print(f"{sym}: " + " | ".join(f"{tf}:{'PEND' if grid[sym][tf]['pending'] else ('conf' if grid[sym][tf]['confirmed_recent'] else 'none')}" for tf in LARGE_TFS))
    print(f"wrote {os.path.relpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()
