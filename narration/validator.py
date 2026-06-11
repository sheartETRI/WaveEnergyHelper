"""LLM 해설 출력 검증."""
from __future__ import annotations

from typing import Optional, Tuple

_FORBIDDEN = ("임박", "확률", "가능성 높음", "가능성이 높", "곧 ", "틀림없")


def validate_narration_text(text: Optional[str]) -> Tuple[bool, str]:
    """(통과 여부, 사유)."""
    if not text or not str(text).strip():
        return False, "empty"
    t = str(text).strip()
    if len(t) < 20:
        return False, "too_short"
    if len(t) > 2000:
        return False, "too_long"
    for word in _FORBIDDEN:
        if word in t:
            return False, f"forbidden:{word}"
    return True, "ok"
