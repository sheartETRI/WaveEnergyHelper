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

# 하위 → 상위. v2 스캐너가 순회하는 표준 사다리.
TF_LADDER: List[str] = ["15m", "1h", "4h", "1d", "4d", "2w"]

# 커스텀 TF 1봉이 베이스(1d) 몇 봉인지. 리샘플 기반 fetch 예산 산정용.
# 4d = 4×1d, 2w = 14×1d (2주 = 14일). 네이티브 TF는 베이스와 동일하므로 1.
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


def upper(tf: str) -> Optional[str]:
    """상위 1단계 TF. 사다리 최상단(2w)이거나 사다리 밖이면 None."""
    idx = ladder_index(tf)
    if idx is None or idx + 1 >= len(TF_LADDER):
        return None
    return TF_LADDER[idx + 1]


def lower(tf: str) -> Optional[str]:
    """하위 1단계 TF. 사다리 최하단(15m)이거나 사다리 밖이면 None."""
    idx = ladder_index(tf)
    if idx is None or idx - 1 < 0:
        return None
    return TF_LADDER[idx - 1]


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
