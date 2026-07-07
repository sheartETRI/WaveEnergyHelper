"""캠페인 백테스트 오케스트레이터 (v2, §7·§8).

scan(L1) → promote(L2) → replay(상태기계) → score → journal 을 (symbol, tf)별로 엮는다.
- G1: 개별 캠페인 리플레이 트레이스(format_campaign_trace)로 수동 차트 판독 대조(김박사 승인).
- G2: run_matrix로 4심볼×{1h,4h,1d} 전수 채점 → summarize.

캠페인 중첩 방지: 기준 setup은 MA10 쌍바닥/쌍봉(대파동, §5 S0)만 채택하고, 진행 중 캠페인의
[setup..청산] 구간 안에서 시작되는 새 setup은 건너뛴다(순차 캠페인). 단일 TF 백테스트라
상위 TF 억제(suppressed_by_upper)는 None (forward/live 소관).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from analysis.campaign_promotion import PROMOTED, resolve_promotions
from analysis.campaign_score import (
    CampaignScore,
    campaign_journal_row,
    journal_to_dataframe,
    score_campaign,
    summarize_campaigns,
)
from analysis.array_context import tag_s0
from analysis.concordance import concordance_at
from analysis.campaign_state_machine import CampaignResult, prepare_base_frame, replay_campaign
from analysis.pattern_scanner import ma_first_pivot_pos, scan_dataframe
from analysis.trend_layer import bottom_width, trend_state_at

# 기준 setup 채택 MA(대파동). MA5/MA20는 강화·문맥이라 별도 캠페인으로 세지 않는다.
DEFAULT_PROMOTER_PERIODS = [10]


@dataclass
class SymbolTFResult:
    symbol: str
    base_tf: str
    campaigns: List[Tuple[CampaignResult, CampaignScore]] = field(default_factory=list)
    journal_rows: List[dict] = field(default_factory=list)

    @property
    def scores(self) -> List[CampaignScore]:
        return [s for _, s in self.campaigns]


def run_symbol_tf(
    symbol: str,
    base_tf: str,
    full_df: Optional[pd.DataFrame] = None,
    *,
    frame_provider: Optional[Callable[[str, str], Optional[pd.DataFrame]]] = None,
    promoter_periods: Optional[List[int]] = None,
    fee_per_fill: Optional[float] = None,
) -> SymbolTFResult:
    """한 (symbol, base_tf)의 순차 캠페인 전수 채점.

    full_df(파이프라인+MACD) 주입 시 그대로 사용(테스트). 아니면 frame_provider 또는
    prepare_base_frame(fetch)로 로딩.
    """
    if full_df is None:
        if frame_provider is not None:
            full_df = frame_provider(symbol, base_tf)
        else:
            from display.asof import fetch_ohlcv_bare
            bare = fetch_ohlcv_bare(symbol, base_tf)
            full_df = prepare_base_frame(bare) if bare is not None else None

    out = SymbolTFResult(symbol=symbol, base_tf=base_tf)
    if full_df is None or full_df.empty:
        return out

    periods = promoter_periods if promoter_periods is not None else DEFAULT_PROMOTER_PERIODS
    events = scan_dataframe(full_df, symbol, base_tf, ma_periods=periods, stoch_suffixes=[])
    promos = [p for p in resolve_promotions(events) if p.status == PROMOTED]
    promos.sort(key=lambda p: p.driver.confirmed_pos)

    last_close_pos = -1
    for p in promos:
        setup_pos = p.driver.confirmed_pos
        if setup_pos <= last_close_pos:
            continue  # 진행 중 캠페인과 중첩 → 건너뜀
        res = replay_campaign(
            full_df, symbol, base_tf, p.direction, setup_pos,
            p.driver.ma_or_layer, setup_pos,
        )
        score = score_campaign(res, full_df, fee_per_fill=fee_per_fill)
        # array_context 관측 태그(§C) + 상응 합치(§E) — 확정봉 앵커. 게이트 아님, 저널 컬럼만.
        arr_label, arr_aligned = tag_s0(full_df, res.setup_pos, res.direction)
        concord = concordance_at(full_df, p.driver.ma_or_layer, res.direction, res.setup_pos)
        # 5차 위임 B — 첫 바닥(천장) 피봇 앵커 재주석(병존). 앵커=first_pos, 없으면 setup_pos 폴백.
        period = int(str(p.driver.ma_or_layer).replace("MA", "")) if str(p.driver.ma_or_layer).startswith("MA") else 10
        pat = "db" if res.direction == "long" else "dt"
        anchor_p1 = ma_first_pivot_pos(full_df, period, pat, res.setup_pos)
        anchor_p1 = res.setup_pos if anchor_p1 is None else anchor_p1
        arr_label_p1, arr_aligned_p1 = tag_s0(full_df, anchor_p1, res.direction)
        concord_p1 = concordance_at(full_df, p.driver.ma_or_layer, res.direction, anchor_p1)
        # 6차 위임 C — 추세 상태·바닥 폭 관측 컬럼(게이트 아님). S0 봉 기준.
        t_state = trend_state_at(full_df, res.setup_pos)
        b_width = bottom_width(full_df, period, pat, res.setup_pos)
        row = campaign_journal_row(
            res, score, suppressed_by_upper=None,
            array_context=arr_label, context_aligned=arr_aligned,
            concordance=concord,
            array_context_p1=arr_label_p1, context_aligned_p1=arr_aligned_p1,
            concordance_p1=concord_p1,
            trend_state_at_entry=t_state, bottom_width=b_width,
        )
        out.campaigns.append((res, score))
        out.journal_rows.append(row)
        last_close_pos = res.exit_final.pos if res.exit_final else len(full_df) - 1

    return out


def run_matrix(
    symbols: List[str],
    tfs: List[str],
    *,
    frame_provider: Optional[Callable[[str, str], Optional[pd.DataFrame]]] = None,
    fee_per_fill: Optional[float] = None,
) -> Dict[str, object]:
    """G2 매트릭스 전수 채점 + 요약."""
    all_scores: List[CampaignScore] = []
    all_rows: List[dict] = []
    per_cell: Dict[str, dict] = {}
    for sym in symbols:
        for tf in tfs:
            r = run_symbol_tf(sym, tf, frame_provider=frame_provider, fee_per_fill=fee_per_fill)
            all_scores.extend(r.scores)
            all_rows.extend(r.journal_rows)
            per_cell[f"{sym}/{tf}"] = summarize_campaigns(r.scores)
    return {
        "overall": summarize_campaigns(all_scores),
        "per_cell": per_cell,
        "journal": journal_to_dataframe(all_rows),
        "scores": all_scores,
    }


def format_campaign_trace(res: CampaignResult, score: CampaignScore) -> str:
    """G1 인간 검토용 캠페인 리플레이 트레이스(수동 차트 판독 대조)."""
    lines = [
        f"[{res.symbol} · 기준 {res.base_tf} · {res.direction} · {score.status}]",
        f"  S0 SETUP  {res.setup_ts:%Y-%m-%d %H:%M}  {res.setup_layer}"
        f"{'  +강화(' + str(res.strength_layer) + ')' if res.strength_flag else ''}",
    ]

    def leg(tag, tp):
        if tp is None:
            return f"  {tag:<10} —"
        return f"  {tag:<10} {tp.ts:%Y-%m-%d %H:%M}  {tp.price:.4g}  {tp.action}"

    lines.append(leg("ENTRY-1", res.entry1))
    lines.append(leg("EXIT-1", res.exit1))
    lines.append(f"  2파 예측   {res.predicted_region_label} (급 {res.predicted_grade})")
    lines.append(leg("ENTRY-2", res.entry2))
    lines.append(leg("EXIT-FIN", res.exit_final))
    if score.t1_return is not None:
        lines.append(f"  T1={score.t1_return:+.2%}"
                     + (f"  T2={score.t2_return:+.2%}" if score.t2_return is not None else "")
                     + (f"  합산(net)={score.combined_net:+.2%}" if score.combined_net is not None else ""))
    if score.mae_t2 is not None:
        lines.append(f"  MAE(T2)={score.mae_t2:+.2%}  저점이탈후재진입={score.entry2_after_low_break}")
    return "\n".join(lines)
