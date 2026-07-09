"""Wilder RSI(14) — 연구용 순수 지표 (12차 위임 A, 신규 지표).

김박사 확정: 과매도 = Wilder RSI(14) ≤ 30. 기존 indicators/oscillators.add_rsi는 앱 표시용으로
2봉 SMA 평활(rsi)과 원시(rsi_raw)를 함께 산출한다. 본 모듈은 그 rsi_raw와 수학적으로 동일한
'순수 Wilder RSI(14)'만 독립 제공한다(streamlit·피벗·패턴 없음, 테스트 가능, 기간 상수 노출).

Wilder 평활 = RMA(alpha=1/period). 유효 구간에서 add_rsi의 rsi_raw와 동일하다. 단, 워밍업
구간은 rsi_raw가 100으로 채우는(fillna) 반면 본 모듈은 NaN을 유지한다 — 워밍업 경계에서
인위적 100→저값 낙차가 '과매도 하향 교차'로 오검출되는 것을 막기 위함(연구 정확성).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 기간 상수(노출) — 김박사 동결값.
WILDER_RSI_PERIOD = 14
OVERSOLD_THRESHOLD = 30.0


def wilder_rsi(close: pd.Series, period: int = WILDER_RSI_PERIOD) -> pd.Series:
    """Wilder RSI. close: 종가 Series. 반환: 동일 인덱스 RSI Series(0~100).

    워밍업(첫 period봉)은 NaN. 전(全)상승 구간(avg_loss=0, avg_gain>0)은 RSI=100.
    평탄(avg_gain=avg_loss=0) 극단은 NaN(정의 불가, 실전 일봉에서 사실상 없음).
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)     # 0-손실 → NaN (inf 회피)
    rsi = 100 - (100 / (1 + rs))
    # 전상승(손실 0, 이익>0) → RSI 100. 워밍업/평탄 NaN은 그대로 둔다.
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return rsi


def oversold_downcross(rsi: pd.Series, threshold: float = OVERSOLD_THRESHOLD) -> pd.Series:
    """RSI가 threshold를 상→하 교차한 봉(True). 연속 과매도 중복 방지 — 진입 봉만.

    조건: 직전 봉 RSI > threshold 이고 현재 봉 RSI ≤ threshold. 첫 봉(직전값 NaN)은 False.
    """
    prev = rsi.shift(1)
    return (prev > threshold) & (rsi <= threshold)
