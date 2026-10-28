"""지표 프레임의 숫자형 정규화."""
import pandas as pd
from config.settings import MA_PERIODS

def _coerce_ma_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """pd.NA → NaN (짧은 상위 프레임 등 MA 워밍업 부족 시 ma_patterns 호환)."""
    out = df.copy()
    for w in MA_PERIODS:
        col = f"MA{w}"
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
