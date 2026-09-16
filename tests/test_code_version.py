"""코드 버전 위젯 — 기동 HEAD · 기동 시각 · 저장소 루트 경로 (순수 빌더, streamlit 무관)."""
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display import code_version as cv_mod
from display.code_version import (
    CODE_VERSION,
    HEAD_UNAVAILABLE,
    REPO_ROOT,
    CodeVersion,
    build_version_lines,
    capture_code_version,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_repo_root_path_line_present():
    """경로 줄이 있고, 실행 중인 저장소 루트의 절대경로(이 tests/ 의 상위)와 일치한다."""
    lines = build_version_lines(CODE_VERSION)
    assert len(lines) == 3
    path_line = lines[2]
    assert path_line.startswith("경로 ")
    shown = path_line[len("경로 "):]
    assert os.path.isabs(shown) and os.path.isdir(shown)
    assert os.path.normcase(shown) == os.path.normcase(os.path.abspath(ROOT))
    assert os.path.normcase(REPO_ROOT) == os.path.normcase(ROOT)
    assert os.path.isfile(os.path.join(shown, "main.py"))


def test_head_and_started_at_lines():
    """기동 HEAD 는 짧은 해시(이 저장소에서 git 이 되면) 또는 강등 라벨. 기동 시각은 캡처값 그대로."""
    fixed = datetime(2026, 9, 17, 12, 34, 56)
    cv = capture_code_version(now=fixed)
    lines = build_version_lines(cv)
    assert lines[1] == "기동 시각 2026-09-17 12:34:56"
    head = lines[0][len("기동 HEAD "):]
    assert re.fullmatch(r"[0-9a-f]{7,40}", head) or head == HEAD_UNAVAILABLE
    # 모듈 캡처본은 프로세스당 1회 — 두 번 불러도 같은 객체.
    assert cv_mod.CODE_VERSION is CODE_VERSION


def test_git_failure_degrades_only_head(monkeypatch):
    """git 조회 실패(예외·비정상 종료) 시 HEAD 만 '조회 불가', 시각·경로는 정상."""
    def boom(*args, **kwargs):
        raise FileNotFoundError("git not found")
    monkeypatch.setattr(subprocess, "run", boom)
    cv = capture_code_version(now=datetime(2026, 1, 1))
    lines = build_version_lines(cv)
    assert cv.head is None and lines[0] == f"기동 HEAD {HEAD_UNAVAILABLE}"
    assert lines[1] == "기동 시각 2026-01-01 00:00:00"
    assert lines[2] == f"경로 {os.path.abspath(ROOT)}"

    class Failed:
        returncode = 128
        stdout = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())
    assert capture_code_version().head is None

    # 저장소가 아닌 경로에서도 경로 줄은 그 경로로 나온다.
    monkeypatch.undo()
    cv = capture_code_version(root=os.path.dirname(ROOT) if os.path.dirname(ROOT) else ROOT)
    assert build_version_lines(cv)[2].startswith("경로 ")


def test_main_wires_widget():
    """main.py 사이드바가 위젯을 호출한다."""
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as fh:
        body = fh.read()
    assert "render_code_version()" in body
    assert build_version_lines(CodeVersion(head="abc1234", started_at=datetime(2026, 1, 1), root=ROOT))[0] == "기동 HEAD abc1234"
