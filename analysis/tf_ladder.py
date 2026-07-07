"""TF 사다리 (v2) — 상시 스캔 대상 타임프레임 체계 + 데이터 충분성 점검.

v2 개편의 기반 레이어. v1의 "사용자가 TF 선택" 대신 전 TF를 사다리로 상시 스캔한다.
이 모듈은 config만 의존한다(순환 임포트 방지). 검출기·리샘플러는 상위 레이어가 소비.

확정 규칙:
- TF_LADDER는 하위→상위 순서. upper/lower는 사다리 인덱스 ±1.
- 4d/2w는 data.processor.resample_timeframe이 1d에서 리샘플(기존 CUSTOM_INTERVAL_BASE).
- 데이터 충분성: CORE_MA_PERIODS 중 실제로 검출 가능한 부분집합만 사용, 나머지는 UI에 명시.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from config.settings import CORE_MA_PERIODS, CUSTOM_INTERVAL_BASE

# 확정 풀 (동결 스펙 §1). 하위→상위(분 단위 크기 오름차순). 12h 없음 — 아래 주석 참조.
# 스펙 원문: TF_POOL = ["15m","30m","1h","2h","4h","6h","8h","1d","4d","2w"]
# PHASE1/2 백테스트는 이 풀을 쓰지 않고 {1h,4h,1d} 단일 TF 리플레이만 수행했고(풀 무관),
# PHASE3 라이브 스냅샷은 12h를 포함한 잘못된 10-풀(8h 부재)로 산출됐다 → PHASE4에서 교정.
# 9차 위임 B: "1M"(월봉) 추가 — 관측 전용. 인접 비율상 2w와 ×2.14(<3.5)라 상·하위 없는 고립 TF.
#   히스토리 ~107개월 한계 → CORE_MA 부분집합(MA60까지) 운용, 통계·승격 대상 아님(UI 명시).
TF_POOL: List[str] = ["15m", "30m", "1h", "2h", "4h", "6h", "8h", "1d", "4d", "2w", "1M"]

# ★ 12h 제외 근거: 12h(720분)는 인접 비율 규칙(×3.5~×6)상 상·하위가 모두 없는 고립 TF다.
#   upper 후보: 720×[3.5,6] = [2520,4320]분 → 풀에 해당 TF 없음(1d=1440은 ×2, 4d=5760은 ×8).
#   lower 후보: 720÷[3.5,6] = [120,206]분 → 2h(120)는 ×6 경계지만 스펙 확정 풀은 8h를 채택.
#   따라서 12h는 사다리에 편입되지 않으며 풀에서 제외한다(스펙 §1 정합).

# TF 분(minute) 크기 — 비율 기반 인접 계산용(스펙 §1). 리샘플/네이티브 무관 논리 크기.
TF_MINUTES: dict = {
    "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240,
    "6h": 360, "8h": 480, "12h": 720, "1d": 1440, "4d": 5760, "2w": 20160,
    "1M": 43200,   # 월봉 논리 크기(30일 명목). 2w(20160)와 ×2.14 → 인접 없음(고립 TF).
}

# 인접 비율 규칙(스펙 §1, 예외 없음): upper=×3.5~×6(×4 최근접 우선), lower=÷3.5~÷6(÷4 우선).
# 상·하위는 각각 독립 계산 — 대칭 보장 안 함(예: upper(4h)=1d(×6)이나 lower(1d)=6h(÷4)).
_RATIO_LOW = 3.5
_RATIO_HIGH = 6.0
_RATIO_PREFER = 4.0

# 하위 호환: 기존 소비자(campaign_promotion.ladder_index, v2_campaign_view 순회)는 크기순
# 인덱스만 필요로 하므로 TF_LADDER를 풀의 별칭으로 유지한다. '고정 사다리'가 아니라 크기순 풀이다.
TF_LADDER: List[str] = TF_POOL

# 커스텀 TF 1봉이 베이스(1d) 몇 봉인지. 리샘플 기반 fetch 예산 산정용.
# 4d = 4×1d, 2w = 14×1d (2주 = 14일). 네이티브 TF(30m/2h/6h/8h 등)는 베이스와 동일하므로 1.
CUSTOM_TF_BASE_MULTIPLIER = {"4d": 4, "2w": 14, "2d": 2, "3h": 3}

# CORE_MA period p가 "검출 가능"하려면 워밍업(p봉) 이후에도 패턴을 볼 만큼의
# 유효 MA 점이 있어야 한다. MA 시계열 쌍바닥 검출은 피봇 2개(각 lookback=3 좌우)+
# 넥라인 돌파가 필요하므로 최소 여유분을 둔다.
# 잠정값 — §10 미결(2w/4d MA240 부족 시 CORE_MA 부분집합 범위)로 김박사 확정 대상.
MIN_MA_DETECT_BARS = 20


def ladder_index(tf: str) -> Optional[int]:
    """사다리 내 인덱스. 사다리 밖 TF는 None."""
    try:
        return TF_LADDER.index(tf)
    except ValueError:
        return None


def in_ladder(tf: str) -> bool:
    return tf in TF_LADDER


def _adjacent(tf: str, going_up: bool) -> Optional[str]:
    """비율 기반 인접(스펙 §1). going_up=True면 상위(×3.5~×6), False면 하위(÷3.5~÷6).

    후보 비율이 [3.5, 6] 범위에 드는 TF 중 ×4(÷4)에 최근접. 동률이면 비율이 작은 쪽.
    범위 안 후보가 없으면 None(대체 TF를 임의로 끌어오지 않는다).
    """
    base = TF_MINUTES.get(tf)
    if base is None or tf not in TF_POOL:
        return None
    within = []
    for c in TF_POOL:
        cm = TF_MINUTES[c]
        if going_up and cm > base:
            r = cm / base
        elif not going_up and cm < base:
            r = base / cm
        else:
            continue
        if _RATIO_LOW <= r <= _RATIO_HIGH:
            within.append((c, r))
    if not within:
        return None
    within.sort(key=lambda cr: (abs(cr[1] - _RATIO_PREFER), cr[1]))
    return within[0][0]


def upper(tf: str) -> Optional[str]:
    """상위 1단계 TF (비율 ×3.5~×6, ×4 최근접). 상위 없으면 None. 스펙 §1."""
    return _adjacent(tf, going_up=True)


def lower(tf: str) -> Optional[str]:
    """하위 1단계 TF (비율 ÷3.5~÷6, ÷4 최근접). 하위 없으면 None. 스펙 §1."""
    return _adjacent(tf, going_up=False)


def base_fetch_interval(tf: str) -> str:
    """리샘플 TF면 베이스 인터벌, 아니면 그대로 (data.processor.get_fetch_interval 미러)."""
    return CUSTOM_INTERVAL_BASE.get(tf, tf)


def recommended_base_limit(tf: str, target_bars: int) -> int:
    """target_bars개의 tf봉을 확보하려면 베이스 인터벌을 몇 봉 fetch해야 하는지.

    리샘플 손실(경계 부분봉)을 감안해 여유 배수를 더한다. 네이티브 TF는 target 그대로.
    """
    mult = CUSTOM_TF_BASE_MULTIPLIER.get(tf, 1)
    if mult == 1:
        return int(target_bars)
    # 부분봉 경계에서 최대 1봉 손실 + 안전 여유.
    return int(target_bars * mult) + mult


@dataclass
class TFDataSufficiency:
    """한 TF의 데이터 충분성 판정 결과 (관측·표시용)."""

    tf: str
    available_bars: int
    usable_ma_periods: List[int] = field(default_factory=list)
    missing_ma_periods: List[int] = field(default_factory=list)
    ma240_ok: bool = False
    note: str = ""


def usable_core_ma_periods(
    available_bars: int,
    periods: Optional[List[int]] = None,
    min_detect_bars: int = MIN_MA_DETECT_BARS,
) -> List[int]:
    """available_bars로 패턴 검출까지 가능한 CORE_MA period 부분집합.

    period p는 워밍업 p봉 + 검출 여유 min_detect_bars봉이 확보돼야 usable.
    즉 available_bars >= p + min_detect_bars.
    """
    src = periods if periods is not None else CORE_MA_PERIODS
    return [p for p in src if available_bars >= p + min_detect_bars]


def assess_tf_data(
    available_bars: int,
    tf: str,
    periods: Optional[List[int]] = None,
    min_detect_bars: int = MIN_MA_DETECT_BARS,
) -> TFDataSufficiency:
    """available_bars 기준 충분성 판정. periods 미지정 시 CORE_MA_PERIODS."""
    src = list(periods if periods is not None else CORE_MA_PERIODS)
    usable = usable_core_ma_periods(available_bars, src, min_detect_bars)
    missing = [p for p in src if p not in usable]
    ma240_ok = 240 in usable

    if not usable:
        note = f"{tf}: 데이터 부족({available_bars}봉) — CORE_MA 전 구간 검출 불가"
    elif missing:
        note = (
            f"{tf}: {available_bars}봉 — MA{max(usable)}까지만 검출 가능 "
            f"(MA{'/'.join(str(p) for p in missing)} 부족, 부분집합 동작)"
        )
    else:
        note = f"{tf}: {available_bars}봉 — CORE_MA 전 구간 검출 가능"

    return TFDataSufficiency(
        tf=tf,
        available_bars=available_bars,
        usable_ma_periods=usable,
        missing_ma_periods=missing,
        ma240_ok=ma240_ok,
        note=note,
    )


def assess_tf_from_df(df, tf: str, **kwargs) -> TFDataSufficiency:
    """리샘플·지표 적용 전/후 DataFrame의 행 수로 충분성 판정."""
    n = 0 if df is None else int(len(df))
    return assess_tf_data(n, tf, **kwargs)
