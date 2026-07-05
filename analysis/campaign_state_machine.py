"""기법 1 — 캠페인 상태 기계 (v2, §5). 현물 보유 전략.

모든 크로스는 MACD선-시그널선 기준 (스토캐 K/D 아님). 봉 마감 확정값으로만 전이(as-of).

상태(§5):
  S0 SETUP   : 기준 TF 이평선 쌍바닥/쌍봉 확정 (kind + 넥라인 돌파) — L2 승격 이벤트가 진입점
  S1 CONFIRM : MACD 크로스 대기 (long=GC / short=DC), S0 이후 발생분만
  S2 ENTRY-1 : 매수(long) / 청산(short) 시그널
  S3 WAVE-1  : 보유(long) / 대기(short) — 반대 크로스 발생 시 전이
  S4 EXIT-1  : 전량 매도(long) / 무매매 웨이포인트(short)
  S5 WAVE-2  : 조정 깊이 예측 — 조정 주도 스토캐 쌍봉/쌍바닥 급으로 MA 구간 결정
  S6 ENTRY-2 : (구간 도달 AND MACD 재GC) → 재매수. ★무효화 없음(무기한 대기)
  S7 WAVE-3  : 보유 — [대파동 스토캐] 또는 [MA10] 반대 확정 시 청산 → 종료

방향 대칭·현물 매도 의미론은 김박사 결정을 따른다:
- 강화 플래그 = 스토캐 삼중(MA 삼중 검출기 부재 대체). long=stoch_tb, short=stoch_tt.
- 매도 캠페인 = 청산 + 재매수 보류 해제. 재매수(S6)는 방향 무관 GC 대기(재매수=매수).
- short의 S5 구간 기하는 long의 기계적 미러 — G1 리플레이에서 검증 대상.

전이 규칙은 CAMPAIGN_FLOW(데이터 선언) + 방향 config(DIRECTION_CFG)로 선언한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.settings import STOCH_LAYERS, WAVE_LAYER_ROLES

# --- 상태 상수 ---
S0_SETUP = "S0_SETUP"
S1_CONFIRM = "S1_CONFIRM"
S2_ENTRY1 = "S2_ENTRY1"
S3_WAVE1 = "S3_WAVE1"
S4_EXIT1 = "S4_EXIT1"
S5_WAVE2 = "S5_WAVE2"
S6_ENTRY2 = "S6_ENTRY2"
S7_WAVE3 = "S7_WAVE3"
DONE = "DONE"

# 대기(휴지) 상태 — step()은 여기서 멈춘다. S2/S4/S6는 액션 후 즉시 다음 대기 상태로.
RESTING_STATES = (S1_CONFIRM, S3_WAVE1, S5_WAVE2, S7_WAVE3, DONE)

# 상태 문서화 테이블 (규칙=데이터). role: 표시용, trade: 방출 시그널.
CAMPAIGN_FLOW = [
    {"state": S0_SETUP, "role": "이평선 쌍바닥/쌍봉 확정", "trade": None},
    {"state": S1_CONFIRM, "role": "MACD 크로스 대기", "trade": None},
    {"state": S2_ENTRY1, "role": "1차 진입", "trade": "entry1"},
    {"state": S3_WAVE1, "role": "1파 보유/대기", "trade": None},
    {"state": S4_EXIT1, "role": "1차 청산/웨이포인트", "trade": "exit1"},
    {"state": S5_WAVE2, "role": "2파 조정 깊이 예측", "trade": None},
    {"state": S6_ENTRY2, "role": "재진입(무효화 없음)", "trade": "entry2"},
    {"state": S7_WAVE3, "role": "3파 보유 → 청산", "trade": "exit_final"},
]

# 스토캐 급(layer role) → (얕은 MA, 깊은 MA). 조정 구간 예측(§5 S5).
# 소파동→MA10~20(최소 MA10), 중파동→MA20~60, 대파동→MA60~120.
GRADE_REGION = {
    "small": (10, 20),
    "mid": (20, 60),
    "large": (60, 120),
}
# 스토캐 라벨(suffix) ↔ 급.
_SUFFIX_BY_GRADE = {g: WAVE_LAYER_ROLES[g] for g in ("small", "mid", "large")}
_GRADE_BY_SUFFIX = {v: k for k, v in _SUFFIX_BY_GRADE.items()}
_LARGE_SUFFIX = WAVE_LAYER_ROLES["large"]
ALL_SUFFIXES = [layer["label"] for layer in STOCH_LAYERS]

# 방향별 config. correction_pat = 2파 조정 주도 스토캐 패턴, final_pat = S7 청산 트리거 패턴.
DIRECTION_CFG = {
    "long": {
        "setup_pat": "db", "setup_kind": "HL",
        "confirm_cross": "gc",     # S1→S2
        "exit1_cross": "dc",       # S3→S4
        "reentry_cross": "gc",     # S5→S6 (재매수=매수 → GC)
        "correction_pat": "dt",    # 2파(하락) 주도 스토캐 쌍봉
        "final_stoch_pat": "dt",   # S7: 대파동 스토캐 쌍봉
        "final_ma_pat": "dt",      # S7: MA10 쌍봉
        "strength_pat": "tb",      # 강화: 스토캐 삼중바닥
        "region_side": "low",      # 구간 도달 = 저가가 얕은 MA 이하
    },
    "short": {
        "setup_pat": "dt", "setup_kind": "LH",
        "confirm_cross": "dc",
        "exit1_cross": "gc",
        "reentry_cross": "gc",     # 재매수 보류 해제 = 매수 → GC (김박사)
        "correction_pat": "db",
        "final_stoch_pat": "db",
        "final_ma_pat": "db",
        "strength_pat": "tt",      # 강화: 스토캐 삼중봉
        "region_side": "high",
    },
}


@dataclass
class TradePoint:
    state: str
    ts: pd.Timestamp
    pos: int
    price: float
    action: str          # BUY | SELL | WAYPOINT


@dataclass
class CampaignResult:
    symbol: str
    base_tf: str
    direction: str
    setup_ts: pd.Timestamp
    setup_pos: int
    setup_layer: str                 # 승격 구동 MA (예: "MA10")
    strength_flag: bool = False
    strength_layer: Optional[str] = None
    state: str = S0_SETUP            # 데이터 끝에서의 최종(또는 DONE) 상태
    entry1: Optional[TradePoint] = None
    exit1: Optional[TradePoint] = None
    entry2: Optional[TradePoint] = None
    exit_final: Optional[TradePoint] = None
    predicted_grade: Optional[str] = None
    predicted_region_ma: Optional[Tuple[int, int]] = None   # (얕은, 깊은) MA 기간
    predicted_region_label: str = "미정"
    setup_pattern_low: Optional[float] = None    # 쌍바닥 저점(저점 이탈 판정용, commit5)
    setup_pattern_high: Optional[float] = None   # 쌍봉 고점
    timeline: List[Tuple[str, pd.Timestamp]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def is_closed(self) -> bool:
        return self.state == DONE


# --- MACD 크로스 (봉 마감, 이전봉 대비) ---
def macd_cross_at(df: pd.DataFrame, pos: int) -> Optional[str]:
    """pos봉의 MACD선-시그널선 크로스: 'gc' | 'dc' | None. 이전봉 필요."""
    if pos < 1 or "macd" not in df.columns or "macd_signal" not in df.columns:
        return None
    m, s = df["macd"].iloc[pos], df["macd_signal"].iloc[pos]
    mp, sp = df["macd"].iloc[pos - 1], df["macd_signal"].iloc[pos - 1]
    if any(pd.isna(x) for x in (m, s, mp, sp)):
        return None
    if mp <= sp and m > s:
        return "gc"
    if mp >= sp and m < s:
        return "dc"
    return None


def _stoch_confirmed_grades(df: pd.DataFrame, pos: int, pat: str) -> List[str]:
    """pos봉에서 확정된 스토캐 pat(db/dt/tb/tt) 패턴의 급 리스트 (large/mid/small)."""
    grades = []
    for suffix in ALL_SUFFIXES:
        col = f"stoch_{pat}_{suffix}"
        if col in df.columns and not pd.isna(df[col].iloc[pos]):
            grades.append(_GRADE_BY_SUFFIX.get(suffix))
    return [g for g in grades if g]


def _ma_confirmed(df: pd.DataFrame, pos: int, period: int, pat: str) -> bool:
    col = f"ma{period}_{pat}"
    return col in df.columns and not pd.isna(df[col].iloc[pos])


def _region_reached(df: pd.DataFrame, pos: int, shallow_ma: int, side: str) -> bool:
    """구간 도달: long은 저가 ≤ 얕은 MA, short은 고가 ≥ 얕은 MA (미러)."""
    ma_col = f"MA{shallow_ma}"
    if ma_col not in df.columns:
        return False
    ma_val = df[ma_col].iloc[pos]
    if pd.isna(ma_val):
        return False
    if side == "low":
        return float(df["low"].iloc[pos]) <= float(ma_val)
    return float(df["high"].iloc[pos]) >= float(ma_val)


def prepare_base_frame(bare: pd.DataFrame):
    """검출기 파이프라인 + MACD (상태 기계 입력). 소비-only(재계산 없음)."""
    from display.asof import run_indicator_pipeline
    from indicators.oscillators import add_macd

    full = run_indicator_pipeline(bare)
    return add_macd(full)


def replay_campaign(
    full_df: pd.DataFrame,
    symbol: str,
    base_tf: str,
    direction: str,
    setup_pos: int,
    setup_layer: str,
    setup_first_pos: Optional[int] = None,
) -> CampaignResult:
    """setup_pos(S0 확정 봉)부터 데이터 끝까지 캠페인 상태를 전개한다.

    full_df: prepare_base_frame 결과(파이프라인+MACD). 봉 마감 확정값만 사용.
    """
    cfg = DIRECTION_CFG[direction]
    idx = full_df.index
    n = len(full_df)

    # 쌍바닥/쌍봉 저·고점(저점 이탈 판정용): setup_first_pos..setup_pos 구간.
    lo_hi_lo = setup_first_pos if setup_first_pos is not None else max(0, setup_pos - 20)
    seg = full_df.iloc[lo_hi_lo:setup_pos + 1]
    setup_low = float(seg["low"].min()) if not seg.empty else None
    setup_high = float(seg["high"].max()) if not seg.empty else None

    res = CampaignResult(
        symbol=symbol, base_tf=base_tf, direction=direction,
        setup_ts=pd.Timestamp(idx[setup_pos]), setup_pos=setup_pos,
        setup_layer=setup_layer, state=S0_SETUP,
        setup_pattern_low=setup_low, setup_pattern_high=setup_high,
    )
    res.timeline.append((S0_SETUP, res.setup_ts))

    # 강화 플래그: setup 봉에 스토캐 삼중(long=tb/short=tt) 동시 확정?
    strength_grades = _stoch_confirmed_grades(full_df, setup_pos, cfg["strength_pat"])
    if strength_grades:
        res.strength_flag = True
        res.strength_layer = _SUFFIX_BY_GRADE.get(strength_grades[0])
        res.notes.append(f"강화: 스토캐 삼중({res.strength_layer}) 대체 플래그")

    # S0 → S1 즉시.
    state = S1_CONFIRM
    res.timeline.append((S1_CONFIRM, res.setup_ts))

    reGC_seen = False       # S4 이후 재GC 관측 (S6 AND 조건)
    region_reached = False

    for pos in range(setup_pos + 1, n):
        ts = pd.Timestamp(idx[pos])
        cross = macd_cross_at(full_df, pos)
        close = float(full_df["close"].iloc[pos])

        if state == S1_CONFIRM:
            # S0 이후 발생분만 유효.
            if cross == cfg["confirm_cross"]:
                res.entry1 = TradePoint(
                    S2_ENTRY1, ts, pos, close,
                    "BUY" if direction == "long" else "SELL",
                )
                res.timeline.append((S2_ENTRY1, ts))
                state = S3_WAVE1
                res.timeline.append((S3_WAVE1, ts))

        elif state == S3_WAVE1:
            if cross == cfg["exit1_cross"]:
                res.exit1 = TradePoint(
                    S4_EXIT1, ts, pos, close,
                    "SELL" if direction == "long" else "WAYPOINT",
                )
                res.timeline.append((S4_EXIT1, ts))
                state = S5_WAVE2
                res.timeline.append((S5_WAVE2, ts))

        elif state == S5_WAVE2:
            # 1) 조정 주도 스토캐 패턴으로 급·구간 확정 (최초 1회, 최상위 급 우선).
            if res.predicted_grade is None:
                grades = _stoch_confirmed_grades(full_df, pos, cfg["correction_pat"])
                for g in ("large", "mid", "small"):
                    if g in grades:
                        res.predicted_grade = g
                        res.predicted_region_ma = GRADE_REGION[g]
                        sh, dp = GRADE_REGION[g]
                        res.predicted_region_label = f"MA{sh}~{dp}"
                        break
            # 2) 재GC(재매수 크로스) 관측 — 순서 무관.
            if cross == cfg["reentry_cross"]:
                reGC_seen = True
            # 3) 구간 도달 (급 확정된 경우에만 판정).
            if res.predicted_grade is not None:
                sh = res.predicted_region_ma[0]
                if _region_reached(full_df, pos, sh, cfg["region_side"]):
                    region_reached = True
            # 4) AND 충족 → S6 재진입. ★무효화 없음.
            if region_reached and reGC_seen:
                res.entry2 = TradePoint(S6_ENTRY2, ts, pos, close, "BUY")
                res.timeline.append((S6_ENTRY2, ts))
                state = S7_WAVE3
                res.timeline.append((S7_WAVE3, ts))

        elif state == S7_WAVE3:
            # 청산: 대파동 스토캐 반대 확정 OR MA10 반대 확정.
            large_stoch = _LARGE_SUFFIX in [
                _SUFFIX_BY_GRADE[g] for g in _stoch_confirmed_grades(full_df, pos, cfg["final_stoch_pat"])
            ]
            ma10 = _ma_confirmed(full_df, pos, 10, cfg["final_ma_pat"])
            if large_stoch or ma10:
                res.exit_final = TradePoint(
                    DONE, ts, pos, close,
                    "SELL" if direction == "long" else "SELL",
                )
                res.timeline.append((DONE, ts))
                state = DONE
                break

    res.state = state
    return res
