"""G2 백테스트 실행기 (§8 G2) — 4심볼 × {1h,4h,1d} 캠페인 전수 채점 → REPORT_V2_CAMPAIGN.md.

게이트(사전 확정, 변경 금지):
  합산 기대값(수수료 차감 후) ≥ +0.5%/캠페인 AND 캠페인 n ≥ 100 → 통과.
  미달 시 "기준 TF 승격 + 캠페인 구조" 가설 기각, 트레이딩 용도 종료(인프라 보존).

실행: `python validation/wave_v2_campaign_backtest.py`
관측 전용 — 채점은 in-sample 단일 패스(walk-forward 아님). 해석 시 캐비엇 참조.
"""
import logging
import os
import sys
import warnings
from statistics import median

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_backtest import run_matrix  # noqa: E402
from analysis.campaign_score import ST_COMPLETE  # noqa: E402
from analysis.campaign_state_machine import prepare_base_frame  # noqa: E402
from config.settings import V2_CAMPAIGN_PARAMS  # noqa: E402
from display.asof import fetch_ohlcv_bare  # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
TFS = ["1h", "4h", "1d"]
LIMITS = {"1h": 3000, "4h": 3000, "1d": 1500}

GATE_EXPECTANCY = 0.005
GATE_N = 100

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "REPORT_V2_CAMPAIGN.md")
JOURNAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wave_v2_campaign_journal.csv")


def _provider(sym, tf):
    lim = LIMITS[tf]
    bare = fetch_ohlcv_bare(sym, tf, lim, paginated=lim > 1000)
    return prepare_base_frame(bare) if bare is not None else None


def _pct(x):
    return "—" if x is None else f"{x * 100:+.2f}%"


def _agg(scores):
    comp = [s for s in scores if s.status == ST_COMPLETE and s.combined_net is not None]
    if not comp:
        return None
    nets = [s.combined_net for s in comp]
    return {
        "n": len(comp),
        "mean": sum(nets) / len(nets),
        "median": median(nets),
        "win": sum(1 for x in nets if x > 0) / len(nets),
    }


def main():
    out = run_matrix(SYMBOLS, TFS, frame_provider=_provider)
    ov = out["overall"]
    scores = out["scores"]
    journal = out["journal"]
    journal.to_csv(JOURNAL_PATH, index=False)

    n = ov["n_complete"]
    exp = ov["expectancy_net"] or 0.0
    passed = exp >= GATE_EXPECTANCY and n >= GATE_N

    # TF별 집계
    by_tf = {tf: _agg([s for s in scores if s.base_tf == tf]) for tf in TFS}

    L = []
    L.append("# REPORT_V2_CAMPAIGN — G2 백테스트 (기법1 캠페인)\n")
    L.append(f"- 대상: {', '.join(SYMBOLS)} × {{{', '.join(TFS)}}}")
    L.append(f"- 데이터 한도(봉): {LIMITS} · 수수료/체결: {V2_CAMPAIGN_PARAMS['fee_per_fill']*100:.2f}%")
    L.append("- 채점 단위: 캠페인(T1: ENTRY-1→EXIT-1, T2: ENTRY-2→S7). 합산=(1+T1)(1+T2)-1 − 수수료.")
    L.append("- 관측 전용 · in-sample 단일 패스(walk-forward 아님).\n")

    L.append("## 게이트 판정 (§8 G2, 사전 확정)\n")
    L.append(f"- 기준: 합산 기대값(net) ≥ +0.50%/캠페인 **AND** n ≥ 100")
    L.append(f"- 결과: n_complete = **{n}**, 기대값(net) = **{_pct(exp)}**")
    L.append(f"- **판정: {'통과 (PASS)' if passed else '미달 (FAIL)'}**\n")
    if passed:
        L.append("> 통과 → 15m·4d·2w 확대 및 forward 관측 지속(§8), 시그널 카드 UI 진행(commit 8).\n")
    else:
        L.append("> 미달 → '기준 TF 승격 + 캠페인 구조' 가설 기각, 트레이딩 용도 종료(인프라 보존).\n")

    L.append("## 전체 요약\n")
    L.append(f"- 승률: {ov['win_rate']*100:.1f}%  · 평균 T1: {_pct(ov['mean_t1'])} · 평균 T2: {_pct(ov['mean_t2'])}")
    L.append(f"- 평균 MAE(T2): {_pct(ov['mean_mae_t2'])} · 저점이탈 후 재진입 비율: {ov['low_break_rate']*100:.1f}%\n")

    L.append("## TF별 집계 (mean vs median — 이상치 민감도)\n")
    L.append("| TF | n | 기대값(mean) | 기대값(median) | 승률 |")
    L.append("|----|---|-----|------|------|")
    for tf in TFS:
        a = by_tf[tf]
        if a:
            L.append(f"| {tf} | {a['n']} | {_pct(a['mean'])} | {_pct(a['median'])} | {a['win']*100:.0f}% |")
    L.append("")

    L.append("## 셀별 (symbol/tf)\n")
    L.append("| 셀 | n | 기대값(net) | 승률 |")
    L.append("|----|---|-----|------|")
    for cell, s in out["per_cell"].items():
        e = s.get("expectancy_net")
        w = s.get("win_rate")
        L.append(f"| {cell} | {s.get('n_complete')} | {_pct(e)} | {w*100:.0f}% |" if w is not None
                 else f"| {cell} | {s.get('n_complete')} | — | — |")
    L.append("")

    L.append("## 정직한 캐비엇 (근거 없는 자신감 표시 금지, §6·§7)\n")
    L.append("- **In-sample 단일 패스**: walk-forward/OOS 아님. 과최적화 위험 미검증.")
    L.append("- **엣지 집중**: 1h 셀 다수 음(-), 4h·1d 양(+). 1d는 n이 작고 소수 대형 승리가 mean을 견인 "
             "(mean≫median일 때 이상치 의존). TF별 median 열로 확인.")
    L.append("- **저점이탈 후 재진입 비율 높음**: S6 '무효화 없음'의 실측 리스크. "
             "향후 '저점 이탈 시 보류' 필터 승격 근거 데이터로 저널에 MAE·entry2_after_low_break 축적.")
    L.append("- 게이트는 사전 확정 임계값(집계 기대값·n)만 판정한다. 위 캐비엇은 G3 forward(§8) 대상.\n")

    L.append(f"저널 CSV: `{os.path.relpath(JOURNAL_PATH)}` ({len(journal)}행)")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"n_complete={n} expectancy_net={exp*100:+.2f}% PASS={passed}")
    print(f"wrote {os.path.relpath(REPORT_PATH)} and {os.path.relpath(JOURNAL_PATH)}")


if __name__ == "__main__":
    main()
