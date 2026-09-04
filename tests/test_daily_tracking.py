"""추적 주기 실행 테스트 — 로그 전용 규율의 검증.

- 스크립트 소스에 성과 지표 문자열 부재 (UI 항목 5 테스트와 같은 방식)
- 한 단계가 실패해도 후속 단계가 진행됨 (모킹)
- 멱등 재실행 시 사이드카 증가 0행
"""
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import daily_tracking as DT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# UI 항목 5 와 동일한 금지 토큰 + 로그 전용 규율에서 추가로 막는 것
PERF_TOKENS = (
    "growth", "net_ret", "net_mean", "win_rate", "expectancy", "profit_factor",
    "sharpe", "log_growth", "variant_summary", "수익률", "승률", "기대값",
)
SIDE_EFFECT_TOKENS = (
    "smtplib", "sendmail", "requests.post", "webhook", "notify",
    "place_order", "create_order", "submit_order",
)


# ------------------------------------------------------ 성과 지표·부작용 부재
def test_script_source_has_no_performance_metric():
    src = open(os.path.join(ROOT, "scripts", "daily_tracking.py"), encoding="utf-8").read()
    body = src.split('"""', 2)[2]        # 모듈 docstring(금지어를 설명하는 곳) 제외
    for token in PERF_TOKENS:
        assert token not in body, f"성과 지표 문자열이 있다: {token}"


def test_script_has_no_alert_or_order_hooks():
    src = open(os.path.join(ROOT, "scripts", "daily_tracking.py"), encoding="utf-8").read()
    for token in SIDE_EFFECT_TOKENS:
        assert token not in src, token


def test_subprocess_stdout_is_not_written_to_the_log():
    """하위 명령 표준출력이 로그로 새지 않는지 — 종료코드와 오류 꼬리만 남긴다."""
    import inspect

    src = inspect.getsource(DT.run_command)
    assert "proc.stdout" not in src
    assert "returncode" in src and "stderr" in src


def test_log_lines_carry_only_counts_and_timing(tmp_path):
    path = str(tmp_path / "t.log")
    written = []
    DT.run_steps(
        steps=(("a", lambda: "journal_rows=10->12 (+2)"),),
        log_fn=written.append,
    )
    line = written[0]
    assert "status=ok" in line and "elapsed=" in line and "journal_rows=" in line
    for token in PERF_TOKENS:
        assert token not in line


# ------------------------------------------------ 단계 실패 시 후속 진행 (모킹)
def test_failing_step_does_not_block_later_steps():
    calls = []

    def ok_a():
        calls.append("a")
        return "rows=1->1 (+0)"

    def boom():
        calls.append("b")
        raise RuntimeError("annotate rc=1 boom")

    def ok_c():
        calls.append("c")
        return "rows=2->3 (+1)"

    written = []
    results = DT.run_steps(
        steps=(("a", ok_a), ("b", boom), ("c", ok_c)), log_fn=written.append,
    )
    assert calls == ["a", "b", "c"], "실패 단계 뒤에도 다음 단계가 실행돼야 한다"
    assert results == {"a": "ok", "b": "failed", "c": "ok"}
    assert any("status=failed" in w and "step=b" in w for w in written)
    assert any("step=c" in w and "status=ok" in w for w in written)


def test_failure_reason_is_truncated_and_logged():
    written = []

    def boom():
        raise RuntimeError("x" * 500)

    DT.run_steps(steps=(("b", boom),), log_fn=written.append)
    assert "reason=" in written[0]
    reason = written[0].split("reason=", 1)[1]
    assert len(reason) <= 200


def test_all_steps_failing_still_returns_a_result_per_step():
    def boom():
        raise OSError("nope")

    res = DT.run_steps(steps=(("a", boom), ("b", boom)), log_fn=lambda _m: None)
    assert res == {"a": "failed", "b": "failed"}


# ------------------------------------------------------------ 로그 회전 90일
def test_rotate_keeps_only_recent_days(tmp_path):
    path = str(tmp_path / "r.log")
    now = datetime(2026, 9, 4, 12, 0, 0)
    old = (now - timedelta(days=120)).strftime(DT.TS_FMT)
    recent = (now - timedelta(days=3)).strftime(DT.TS_FMT)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{old} | step=a | status=ok\n")
        f.write(f"{recent} | step=b | status=ok\n")

    dropped = DT.rotate_log(path, days=DT.LOG_RETENTION_DAYS, now=now)
    assert dropped == 1
    kept = open(path, encoding="utf-8").read()
    assert recent in kept and old not in kept


def test_rotate_preserves_unparsable_lines(tmp_path):
    path = str(tmp_path / "r.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write("형식을 모르는 줄\n")
    assert DT.rotate_log(path, days=90) == 0
    assert "형식을 모르는 줄" in open(path, encoding="utf-8").read()


def test_rotate_on_missing_file_is_noop(tmp_path):
    assert DT.rotate_log(str(tmp_path / "none.log")) == 0


def test_retention_is_ninety_days():
    assert DT.LOG_RETENTION_DAYS == 90


# ------------------------------------------------------------ 멱등 재실행
def test_row_counting_and_delta_text(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    assert DT.count_rows(str(p)) == 2
    assert DT.count_rows(str(tmp_path / "missing.csv")) is None
    assert DT._delta_text(2, 2) == "2->2 (+0)"
    assert DT._delta_text(2, 5) == "2->5 (+3)"
    assert DT._delta_text(None, 3) == "—->3"


def test_shadow_sidecar_is_idempotent_on_rerun():
    """섀도 사이드카는 같은 행을 다시 넣어도 증가 0행이다 (append-only)."""
    from analysis.mm_shadow import append_shadow, load_shadow

    if not os.path.isfile(DT.SHADOW_SIDECAR):
        pytest.skip("섀도 사이드카 없음")
    existing = load_shadow()
    if existing.empty:
        pytest.skip("섀도 기록 없음")

    before = DT.count_rows(DT.SHADOW_SIDECAR)
    res = append_shadow(existing)
    after = DT.count_rows(DT.SHADOW_SIDECAR)
    assert res["appended"] == 0
    assert after == before
    assert DT._delta_text(before, after).endswith("(+0)")


def test_steps_are_in_the_specified_order():
    assert [name for name, _ in DT.STEPS] == [
        "watchlist_scan", "f2b_annotate", "mm_shadow_record",
    ]
