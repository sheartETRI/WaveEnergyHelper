# analysis/engine.py
import pandas as pd
from config.settings import CORE_MA_PERIODS

def get_ma_alignment(df: pd.DataFrame) -> str:
    """Determines if MAs are in Bullish, Bearish, or Mixed alignment.

    판정은 책의 6개 코어 이평(CORE_MA_PERIODS)만 사용한다. 40·80은 표시 전용이라
    배열 판정에 포함하지 않는다.
    """
    if df is None or df.empty:
        return "No data for alignment check"

    last = df.iloc[-1]
    ma_vals = []
    for p in CORE_MA_PERIODS:
        ma_col = f'MA{p}'
        if ma_col in last.index and not pd.isna(last[ma_col]):
            ma_vals.append(last[ma_col])
        else:
            return "Incomplete MA data for alignment check"

    # TODO: 파동에너지 철학 반영 (60MA 추세선 기준 분석 등)
    # 1. 기준 프레임 확인
    # 2. 상위 프레임 방향 검증
    # 3. 하위 프레임 진입 타이밍
    
    if all(ma_vals[i] > ma_vals[i + 1] for i in range(len(ma_vals) - 1)):
        return "Bullish Alignment (정배열) 🚀"
    if all(ma_vals[i] < ma_vals[i + 1] for i in range(len(ma_vals) - 1)):
        return "Bearish Alignment (역배열) 📉"
    
    # TODO: 대파동 쌍바닥/쌍봉 구조 판정 로직 추가 예정
    return "Mixed / Consolidation (혼조세) ⚖️"

def analyze_wave_energy(df: pd.DataFrame, symbol: str, interval: str):
    """파동에너지 분석은 analysis.wave_energy 모듈로 위임한다.

    - 일봉 60MA 추세 분석
    - 상위 프레임(MTF) 검증
    - 스토캐스틱 쌍바닥/쌍봉 파동 판정
    """
    from analysis.wave_energy import analyze_wave_energy as _analyze_wave_energy

    return _analyze_wave_energy(df, symbol, interval)
