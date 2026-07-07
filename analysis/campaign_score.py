"""캠페인 채점 + 저널 스키마 (v2, §7). 채점 단위 = 캠페인(hit 아님).

캠페인당 2 트레이드:
- T1: long = ENTRY-1(매수)→EXIT-1(매도) / short = ENTRY-1(청산 매도)→ENTRY-2(재매수)
- T2: ENTRY-2(재매수)→S7(청산)  [long/short 공통: 재매수 후 상승 청산]
합산 = (1+T1)(1+T2)−1, 체결당 수수료 fee_per_fill를 체결 수만큼 복리 차감.

현물 매도(short) 의미론은 김박사 결정: T1은 회피한 하락폭(sell high→buy back low),
ENTRY-2 가격이 T1 청산·T2 진입을 겸한다. EXIT-1은 무매매 웨이포인트라 체결에서 제외.

전 구간 관측 전용(observation grade)으로 시작 — 게이트(§8) 통과 전까지 추천 아님.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from analysis.campaign_state_machine import CampaignResult
from config.settings import V2_CAMPAIGN_PARAMS

OBSERVATION_GRADE = "관측"

# 저널 필수 컬럼(§7).
CAMPAIGN_JOURNAL_COLS = (
    "campaign_id", "symbol", "base_tf", "direction", "grade",
    "s0_layer", "s0_kind", "strength_flag", "strength_layer",
    "setup_ts", "entry1_ts", "entry1_price", "exit1_ts", "exit1_price",
    "entry2_ts", "entry2_price", "exit_final_ts", "exit_final_price",
    "predicted_region", "t1_return", "t2_return", "combined_gross", "combined_net",
    "num_fills", "fee_per_fill", "mae_t2", "entry2_after_low_break",
    "upper_alignment", "lower_wave_count_at_entry2", "suppressed_by_upper",
    "array_context", "context_aligned",   # 4차 위임 C — 관측 태그(확정봉 앵커, 게이트 아님)
    "concordance",                          # 4차 위임 E — 상응 합치(확정봉 앵커)
    # 5차 위임 B — 첫 바닥(천장) 피봇 앵커 재주석(확정봉 앵커 컬럼과 병존, 게이트 아님)
    "array_context_p1", "context_aligned_p1", "concordance_p1",
    # 6차 위임 C — 기법0 추세 레이어 관측 컬럼(게이트·필터 사용 금지, 표시·저널 전용)
    "trend_state_at_entry", "bottom_width",
    "status", "obs_grade",
)

# 상태(채점 관점).
ST_NO_ENTRY = "NO_ENTRY"      # 진입 없음(S1 정체 등)
ST_OPEN = "OPEN"             # 진입했으나 T1/T2 미완
ST_T1_ONLY = "T1_ONLY"       # T1 완료, T2 미완
ST_COMPLETE = "COMPLETE"     # T1+T2 완료(캠페인 종료)


@dataclass
class CampaignScore:
    symbol: str
    base_tf: str
    direction: str
    t1_return: Optional[float] = None
    t2_return: Optional[float] = None
    combined_gross: Optional[float] = None
    combined_net: Optional[float] = None
    num_fills: int = 0
    fee_per_fill: float = 0.0
    mae_t2: Optional[float] = None
    entry2_after_low_break: Optional[bool] = None
    status: str = ST_NO_ENTRY


def _t1_return(res: CampaignResult) -> Optional[float]:
    if res.direction == "long":
        if res.entry1 and res.exit1:
            return (res.exit1.price - res.entry1.price) / res.entry1.price
        return None
    # short: 청산(E1) → 재매수(E2). 하락폭을 수익으로.
    if res.entry1 and res.entry2:
        return (res.entry1.price - res.entry2.price) / res.entry1.price
    return None


def _t2_return(res: CampaignResult) -> Optional[float]:
    # 공통: 재매수(E2) → S7 청산. 상승 수익.
    if res.entry2 and res.exit_final:
        return (res.exit_final.price - res.entry2.price) / res.entry2.price
    return None


def _num_fills(res: CampaignResult) -> int:
    """체결 수. long: E1,X1,E2,XF(각 매수/매도). short: E1(매도),E2(매수),XF(매도) — X1 무매매 제외."""
    if res.direction == "long":
        return sum(1 for tp in (res.entry1, res.exit1, res.entry2, res.exit_final) if tp)
    return sum(1 for tp in (res.entry1, res.entry2, res.exit_final) if tp)


def _mae_t2(res: CampaignResult, full_df: pd.DataFrame) -> Optional[float]:
    """T2(재매수 후 보유) 최대 역행폭 = (구간 최저가 − E2)/E2. 종료 전이면 데이터 끝까지."""
    if not res.entry2:
        return None
    start = res.entry2.pos
    end = res.exit_final.pos if res.exit_final else len(full_df) - 1
    if end < start:
        return None
    lows = full_df["low"].iloc[start:end + 1]
    if lows.empty:
        return None
    return (float(lows.min()) - res.entry2.price) / res.entry2.price


def _entry2_after_low_break(res: CampaignResult, full_df: pd.DataFrame) -> Optional[bool]:
    """재진입 전 쌍바닥 저점(쌍봉 고점) 이탈 여부. 무효화-없음 리스크 계측(§5)."""
    if not res.entry2:
        return None
    seg = full_df.iloc[res.setup_pos:res.entry2.pos + 1]
    if seg.empty:
        return None
    if res.direction == "long":
        if res.setup_pattern_low is None:
            return None
        return bool(float(seg["low"].min()) < res.setup_pattern_low)
    if res.setup_pattern_high is None:
        return None
    return bool(float(seg["high"].max()) > res.setup_pattern_high)


def score_campaign(
    res: CampaignResult,
    full_df: pd.DataFrame,
    fee_per_fill: Optional[float] = None,
) -> CampaignScore:
    fee = V2_CAMPAIGN_PARAMS["fee_per_fill"] if fee_per_fill is None else fee_per_fill
    t1 = _t1_return(res)
    t2 = _t2_return(res)
    fills = _num_fills(res)

    combined_gross = combined_net = None
    if t1 is not None and t2 is not None:
        g = (1.0 + t1) * (1.0 + t2)
        combined_gross = g - 1.0
        combined_net = g * (1.0 - fee) ** fills - 1.0
    elif t1 is not None:
        combined_gross = t1
        combined_net = (1.0 + t1) * (1.0 - fee) ** fills - 1.0

    if res.entry1 is None:
        status = ST_NO_ENTRY
    elif t2 is not None and res.is_closed():
        status = ST_COMPLETE
    elif t1 is not None:
        status = ST_T1_ONLY
    else:
        status = ST_OPEN

    return CampaignScore(
        symbol=res.symbol, base_tf=res.base_tf, direction=res.direction,
        t1_return=t1, t2_return=t2,
        combined_gross=combined_gross, combined_net=combined_net,
        num_fills=fills, fee_per_fill=fee,
        mae_t2=_mae_t2(res, full_df),
        entry2_after_low_break=_entry2_after_low_break(res, full_df),
        status=status,
    )


def make_campaign_id(res: CampaignResult) -> str:
    return f"{res.symbol}_{res.base_tf}_{res.direction}_{res.setup_ts:%Y%m%d%H%M}_{res.setup_layer}"


def _tp(tp) -> tuple:
    return (None, None) if tp is None else (pd.Timestamp(tp.ts), tp.price)


def campaign_journal_row(
    res: CampaignResult,
    score: CampaignScore,
    *,
    upper_alignment: Optional[str] = None,
    lower_wave_count_at_entry2: Optional[str] = None,
    suppressed_by_upper: Optional[str] = None,
    array_context: Optional[str] = None,
    context_aligned: Optional[bool] = None,
    concordance: Optional[str] = None,
    array_context_p1: Optional[str] = None,
    context_aligned_p1: Optional[bool] = None,
    concordance_p1: Optional[str] = None,
    trend_state_at_entry: Optional[str] = None,
    bottom_width: Optional[int] = None,
) -> dict:
    """저널 1행. upper_alignment/lower_wave_count는 L3(commit9)·관측에서 주입(없으면 None)."""
    e1_ts, e1_px = _tp(res.entry1)
    x1_ts, x1_px = _tp(res.exit1)
    e2_ts, e2_px = _tp(res.entry2)
    xf_ts, xf_px = _tp(res.exit_final)
    return {
        "campaign_id": make_campaign_id(res),
        "symbol": res.symbol, "base_tf": res.base_tf, "direction": res.direction,
        "grade": res.predicted_grade, "s0_layer": res.setup_layer,
        "s0_kind": DIRECTION_KIND.get(res.direction),
        "strength_flag": res.strength_flag, "strength_layer": res.strength_layer,
        "setup_ts": pd.Timestamp(res.setup_ts),
        "entry1_ts": e1_ts, "entry1_price": e1_px,
        "exit1_ts": x1_ts, "exit1_price": x1_px,
        "entry2_ts": e2_ts, "entry2_price": e2_px,
        "exit_final_ts": xf_ts, "exit_final_price": xf_px,
        "predicted_region": res.predicted_region_label,
        "t1_return": score.t1_return, "t2_return": score.t2_return,
        "combined_gross": score.combined_gross, "combined_net": score.combined_net,
        "num_fills": score.num_fills, "fee_per_fill": score.fee_per_fill,
        "mae_t2": score.mae_t2, "entry2_after_low_break": score.entry2_after_low_break,
        "upper_alignment": upper_alignment,
        "lower_wave_count_at_entry2": lower_wave_count_at_entry2,
        "suppressed_by_upper": suppressed_by_upper,
        "array_context": array_context,
        "context_aligned": context_aligned,
        "concordance": concordance,
        "array_context_p1": array_context_p1,
        "context_aligned_p1": context_aligned_p1,
        "concordance_p1": concordance_p1,
        "trend_state_at_entry": trend_state_at_entry,
        "bottom_width": bottom_width,
        "status": score.status, "obs_grade": OBSERVATION_GRADE,
    }


DIRECTION_KIND = {"long": "HL", "short": "LH"}


def journal_to_dataframe(rows: List[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(CAMPAIGN_JOURNAL_COLS))
    return pd.DataFrame(rows)[list(CAMPAIGN_JOURNAL_COLS)]


def summarize_campaigns(scores: List[CampaignScore]) -> dict:
    """백테스트 요약 — 합산 기대값(수수료 차감 후) 등 G2 게이트 지표."""
    complete = [s for s in scores if s.status == ST_COMPLETE and s.combined_net is not None]
    n = len(complete)
    if n == 0:
        return {"n_complete": 0, "expectancy_net": None}
    nets = [s.combined_net for s in complete]
    wins = [x for x in nets if x > 0]
    return {
        "n_total": len(scores),
        "n_complete": n,
        "expectancy_net": sum(nets) / n,
        "win_rate": len(wins) / n,
        "mean_t1": _mean([s.t1_return for s in complete]),
        "mean_t2": _mean([s.t2_return for s in complete]),
        "mean_mae_t2": _mean([s.mae_t2 for s in complete if s.mae_t2 is not None]),
        "low_break_rate": _mean(
            [1.0 if s.entry2_after_low_break else 0.0 for s in complete
             if s.entry2_after_low_break is not None]
        ),
    }


def _mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
