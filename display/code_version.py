"""코드 버전 위젯 — 지금 떠 있는 앱이 어느 코드인지 한눈에.

세 줄: 기동 HEAD(짧은 해시) · 기동 시각 · 실행 중인 저장소 루트 절대경로.
값은 프로세스 기동 시점에 한 번 캡처한다(모듈 import 시 CODE_VERSION) — Streamlit 재실행마다
git 을 부르지 않고, 앱이 뜬 뒤 체크아웃이 바뀌어도 "떠 있는 코드"가 무엇인지 그대로 보여준다.
git 조회가 실패하면(git 없음·저장소 아님·타임아웃) HEAD 줄만 "조회 불가" 로 강등하고 나머지는
정상 표시한다. 저장소 루트는 git 이 아니라 이 파일의 위치에서 구하므로 강등과 무관하게 항상 나온다.

build_* 는 순수 함수(테스트 가능), render_* 는 streamlit 래퍼.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

HEAD_UNAVAILABLE = "조회 불가"

# 실행 중인 저장소 루트 = 이 파일(display/code_version.py)의 두 단계 위. git 무관.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class CodeVersion:
    head: Optional[str]      # 짧은 해시. git 조회 실패 시 None(표시는 HEAD_UNAVAILABLE)
    started_at: datetime     # 기동 시각(로컬)
    root: str                # 저장소 루트 절대경로


def _git_short_head(root: str) -> Optional[str]:
    """`git rev-parse --short HEAD`. 어떤 실패든 None(강등)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=3, check=False,
        )
    except Exception:  # noqa: BLE001 — git 없음/타임아웃/권한 등 전부 강등
        return None
    head = out.stdout.strip()
    return head if out.returncode == 0 and head else None


def capture_code_version(root: str = REPO_ROOT, now: Optional[datetime] = None) -> CodeVersion:
    """기동 시점 캡처. now 는 테스트용 주입."""
    return CodeVersion(
        head=_git_short_head(root),
        started_at=now or datetime.now(),
        root=os.path.abspath(root),
    )


def build_version_lines(cv: CodeVersion) -> List[str]:
    """표시 줄 3개 — 기동 HEAD / 기동 시각 / 경로."""
    return [
        f"기동 HEAD {cv.head or HEAD_UNAVAILABLE}",
        f"기동 시각 {cv.started_at:%Y-%m-%d %H:%M:%S}",
        f"경로 {cv.root}",
    ]


# 프로세스당 1회 캡처.
CODE_VERSION = capture_code_version()


def render_code_version(cv: CodeVersion = CODE_VERSION) -> None:
    """사이드바 맨 아래 캡션 3줄."""
    import streamlit as st

    st.sidebar.divider()
    st.sidebar.caption("  \n".join(build_version_lines(cv)))
