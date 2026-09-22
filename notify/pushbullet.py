"""Pushbullet 전송 — 토큰 파일 읽기 + note 푸시. 검출 로직 무접촉, 네트워크는 이 파일에만.

토큰: 저장소 홈의 ``token.txt`` 한 줄(Access Token). ``.gitignore`` 에 등록돼 커밋되지 않는다.
API: POST https://api.pushbullet.com/v2/pushes  {"type": "note", "title": ..., "body": ...}
     헤더 Access-Token. 성공 200. 실패는 예외 대신 False 로 돌려주고 사유를 로그에 남긴다(폴러가 죽지 않게).
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

PUSHBULLET_PUSHES_URL = "https://api.pushbullet.com/v2/pushes"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TOKEN_PATH = os.path.join(REPO_ROOT, "token.txt")
TIMEOUT_SEC = 10
BODY_MAX_CHARS = 4000     # Pushbullet note body 상한 근처에서 자른다(제목·줄 단위 유지)


def read_token(path: str = DEFAULT_TOKEN_PATH) -> Optional[str]:
    """token.txt 의 첫 비어 있지 않은 줄. 파일이 없거나 비어 있으면 None (예외 없음)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                token = line.strip()
                if token and not token.startswith("#"):
                    return token
    except OSError:
        return None
    return None


def push_note(
    token: str,
    title: str,
    body: str,
    post: Callable = requests.post,
    timeout: float = TIMEOUT_SEC,
) -> bool:
    """note 한 건 전송. 성공(2xx)이면 True. ``post`` 는 테스트 주입용(requests.post 시그니처)."""
    if not token:
        logger.error("pushbullet: 토큰 없음 — 전송 생략")
        return False
    if len(body) > BODY_MAX_CHARS:
        body = body[:BODY_MAX_CHARS - 1] + "…"
    try:
        resp = post(
            PUSHBULLET_PUSHES_URL,
            headers={"Access-Token": token, "Content-Type": "application/json"},
            json={"type": "note", "title": title, "body": body},
            timeout=timeout,
        )
    except Exception as exc:                       # 네트워크·타임아웃 — 폴러는 계속 돈다
        logger.error("pushbullet: 요청 실패 %s", exc)
        return False
    status = getattr(resp, "status_code", None)
    if status is None or not 200 <= int(status) < 300:
        text = getattr(resp, "text", "")
        logger.error("pushbullet: HTTP %s %s", status, str(text)[:200])
        return False
    return True
