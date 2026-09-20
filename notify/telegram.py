"""텔레그램 Bot API 전달. 토큰·chat_id 는 환경변수(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = GitHub Secrets)로만 받는다.

토큰은 로그·예외 메시지에 절대 싣지 않는다(URL 에 토큰이 들어가므로 예외 문자열도 마스킹).
"""
from __future__ import annotations

import os
from typing import Callable, Optional, Tuple

import requests

ENV_TOKEN = "TELEGRAM_TOKEN"
ENV_CHAT_ID = "TELEGRAM_CHAT_ID"
TIMEOUT_SEC = 15
API_FMT = "https://api.telegram.org/bot{token}/sendMessage"


def credentials(env: Optional[dict] = None) -> Optional[Tuple[str, str]]:
    """둘 다 비어 있지 않을 때만 (token, chat_id). 아니면 None → 호출부가 '발송 없이 로그만'."""
    e = os.environ if env is None else env
    token, chat = (e.get(ENV_TOKEN) or "").strip(), (e.get(ENV_CHAT_ID) or "").strip()
    return (token, chat) if token and chat else None


def _mask(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def send_message(token: str, chat_id: str, text: str, post: Callable = requests.post) -> Tuple[bool, str]:
    """(성공 여부, 짧은 사유). 예외를 던지지 않는다 — 실패는 호출부가 '이력 미기록' 으로 처리."""
    try:
        r = post(API_FMT.format(token=token), json={"chat_id": chat_id, "text": text,
                                                     "disable_web_page_preview": True}, timeout=TIMEOUT_SEC)
        if r.status_code != 200:
            return False, _mask(f"HTTP {r.status_code} {r.text[:120]}", token)
        body = r.json()
        if not (isinstance(body, dict) and body.get("ok")):
            return False, _mask(f"telegram not ok: {str(body)[:120]}", token)
        return True, "ok"
    except Exception as exc:   # noqa: BLE001 — 네트워크·파싱 오류 전부 '실패' 로
        return False, _mask(f"{type(exc).__name__}: {str(exc)[:120]}", token)
