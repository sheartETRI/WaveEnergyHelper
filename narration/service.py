"""해설 생성 오케스트레이션."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import (
    NARRATION_CONFIG,
    NARRATION_DISCLAIMER,
    NARRATION_RATE_LIMIT_CAPTION,
)
from display.transition_radar import TransitionRadarContent
from narration.cache import cache_key, get_cached, set_cached
from narration.client import (
    NarrationClientError,
    NarrationRateLimitError,
    call_openai_compatible_chat,
)
from narration.fallback import build_fallback_summary
from narration.input_builder import build_narration_context, build_prompt_messages
from narration.validator import validate_narration_text


@dataclass
class NarrationResult:
    body: str
    source: str  # "llm" | "fallback"
    extra_caption: Optional[str] = None


def _resolve_api_key(config: dict) -> Optional[str]:
    env_name = config.get("api_key_env", "GEMINI_API_KEY")
    key = os.environ.get(env_name)
    if key and key.strip():
        return key.strip()
    return None


def generate_narration(
    report,
    alignment: str,
    radar: Optional[TransitionRadarContent],
    last_bar_ts,
    *,
    config: Optional[dict] = None,
) -> NarrationResult:
    """LLM 해설 또는 폴백. 예외는 밖으로 전파하지 않음."""
    cfg = dict(config or NARRATION_CONFIG)
    context = build_narration_context(report, alignment, radar)
    key_str = cache_key(report.symbol, report.interval, last_bar_ts)
    cached = get_cached(key_str)
    if cached is not None:
        return cached

    fallback_body = build_fallback_summary(context)

    if not cfg.get("enabled", True):
        result = NarrationResult(fallback_body, "fallback")
        set_cached(key_str, result)
        return result

    api_key = _resolve_api_key(cfg)
    if not api_key:
        result = NarrationResult(fallback_body, "fallback")
        set_cached(key_str, result)
        return result

    messages = build_prompt_messages(context)
    try:
        raw = call_openai_compatible_chat(
            base_url=cfg["base_url"],
            model=cfg["model"],
            messages=messages,
            api_key=api_key,
            temperature=float(cfg.get("temperature", 0.0)),
            max_tokens=int(cfg.get("max_tokens", 2000)),
            timeout_sec=float(cfg.get("timeout_sec", 20)),
        )
        ok, _reason = validate_narration_text(raw)
        if ok:
            result = NarrationResult(raw, "llm")
        else:
            result = NarrationResult(fallback_body, "fallback")
    except NarrationRateLimitError:
        result = NarrationResult(
            fallback_body,
            "fallback",
            extra_caption=NARRATION_RATE_LIMIT_CAPTION,
        )
    except (NarrationClientError, requests.RequestException):
        result = NarrationResult(fallback_body, "fallback")

    set_cached(key_str, result)
    return result
