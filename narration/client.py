"""OpenAI 호환 chat/completions HTTP 클라이언트 (Gemini·SGLang 등 공통)."""
from __future__ import annotations

import json
from typing import Any, List, Optional

import requests


class NarrationRateLimitError(Exception):
    """429 또는 RESOURCE_EXHAUSTED — 재시도 없이 폴백."""


class NarrationClientError(Exception):
    """기타 API 오류."""


def _is_rate_limit(status_code: int, body: Any) -> bool:
    if status_code == 429:
        return True
    if not isinstance(body, dict):
        return False
    err = body.get("error")
    parts = [str(body.get("message", "")), str(body.get("code", ""))]
    if isinstance(err, dict):
        parts.extend([str(err.get("message", "")), str(err.get("code", ""))])
    elif err is not None:
        parts.append(str(err))
    blob = " ".join(parts).upper()
    return "RESOURCE_EXHAUSTED" in blob or "RATE LIMIT" in blob


def call_openai_compatible_chat(
    *,
    base_url: str,
    model: str,
    messages: List[dict],
    api_key: str,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    timeout_sec: float = 20,
) -> str:
    """POST {base_url}/chat/completions — OpenAI 응답 형식 choices[0].message.content."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
    try:
        body = resp.json()
    except (ValueError, json.JSONDecodeError):
        body = {"raw": resp.text}

    if _is_rate_limit(resp.status_code, body):
        raise NarrationRateLimitError(f"rate limit status={resp.status_code}")

    if resp.status_code >= 400:
        raise NarrationClientError(f"HTTP {resp.status_code}: {body}")

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise NarrationClientError(f"unexpected response shape: {body}") from exc
