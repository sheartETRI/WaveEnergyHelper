"""봉 단위 해설 캐시."""
from __future__ import annotations

from typing import Any, Optional

# 동일 symbol·interval·마지막 봉 타임스탬프면 LLM 재호출하지 않는다.
# 무료 티어 호출량 1차 방어선 — 세션당 1회 제한 옵션은 두지 않음 (캐시로 충분).
_CACHE: dict[str, Any] = {}


def cache_key(symbol: str, interval: str, bar_ts) -> str:
    return f"{symbol}|{interval}|{bar_ts}"


def get_cached(key: str) -> Optional[Any]:
    return _CACHE.get(key)


def set_cached(key: str, value: Any) -> None:
    _CACHE[key] = value


def clear_narration_cache() -> None:
    """테스트용."""
    _CACHE.clear()
