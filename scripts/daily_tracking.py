"""추적 주기 실행 — 일 1회, 무판정.

전방 추적(F2-b)과 MM 섀도가 데이터를 계속 쌓게만 한다. 세 단계 모두 멱등이므로
재실행이 안전하다.

  1. watchlist_scan   — 전방 이벤트 생성 경로 (워치리스트 스캔 + forward journal)
  2. f2b_annotate     — F2-b 게이트 사이드카 기록
  3. mm_shadow_record — MM 섀도 3변형 기록

규율:
- **판정·임계값·알림·이메일·자동 매매 일체 없다.** 출력은 로그뿐이다.
- **성과 지표(G·수익률·승률·기대값 등)는 로그에도 쓰지 않는다.** 기록하는 것은
  행 수·기간·소요 시간뿐이다. 상시 기록은 열람 동결(2027-03)의 우회다.
- 한 단계가 실패해도 다음 단계는 진행한다. 실패는 로그에만 남긴다.
- 하위 명령의 표준출력은 로그에 옮기지 않는다 — 그쪽 출력에 무엇이 섞이든
  이 로그에는 새지 않게 한다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LOG_PATH = os.path.join(LOG_DIR, "daily_tracking.log")
LOG_RETENTION_DAYS = 90

STEP_TIMEOUT_SEC = 3600
TS_FMT = "%Y-%m-%d %H:%M:%S"

JOURNAL_CSV = os.path.join(ROOT, "validation", "wave_live_forward_journal.csv")
GATE_SIDECAR = os.path.join(ROOT, "validation", "wave_align_gate_forward.csv")
SHADOW_SIDECAR = os.path.join(ROOT, "validation", "wave_mm_shadow.csv")


# ------------------------------------------------------------------ 로그
def _now() -> datetime:
    return datetime.now()


def rotate_log(path: str = LOG_PATH, days: int = LOG_RETENTION_DAYS,
               now: Optional[datetime] = None) -> int:
    """최근 `days` 일 줄만 남긴다. 반환값은 버린 줄 수."""
    if not os.path.isfile(path):
        return 0
    now = now or _now()
    cutoff = now - timedelta(days=days)
    kept, dropped = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            stamp = line[:19]
            try:
                ts = datetime.strptime(stamp, TS_FMT)
            except ValueError:
                kept.append(line)          # 형식을 모르는 줄은 보존한다
                continue
            if ts >= cutoff:
                kept.append(line)
            else:
                dropped += 1
    if dropped:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept)
    return dropped


def log(msg: str, path: str = LOG_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = f"{_now().strftime(TS_FMT)} | {msg}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


# ------------------------------------------------------------------ 행 수
def count_rows(path: str) -> Optional[int]:
    """CSV 데이터 행 수 (헤더 제외). 없으면 None."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            n = sum(1 for _ in f)
        return max(n - 1, 0)
    except OSError:
        return None


def _delta_text(before: Optional[int], after: Optional[int]) -> str:
    b = "—" if before is None else str(before)
    a = "—" if after is None else str(after)
    if before is None or after is None:
        return f"{b}->{a}"
    return f"{b}->{a} (+{after - before})"


# ------------------------------------------------------------------ 실행
def run_command(args: list[str], timeout: int = STEP_TIMEOUT_SEC) -> tuple[int, str]:
    """하위 명령 실행. 표준출력은 버리고 종료코드와 오류 꼬리만 돌려준다."""
    proc = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )
    tail = ""
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        tail = err[-1][:200] if err else ""
    return proc.returncode, tail


def _py(script: str, *args: str) -> list[str]:
    return [sys.executable, os.path.join(ROOT, script), *args]


def step_watchlist_scan() -> str:
    """전방 이벤트 생성 경로 — 워치리스트 스캔 후 forward journal 재생성."""
    before = count_rows(JOURNAL_CSV)
    for script in ("validation/wave_live_watchlist_sweep.py",
                   "validation/wave_live_forward_journal_sweep.py"):
        code, tail = run_command(_py(script))
        if code != 0:
            raise RuntimeError(f"{script} rc={code} {tail}")
    return f"journal_rows={_delta_text(before, count_rows(JOURNAL_CSV))}"


def step_f2b_annotate() -> str:
    before = count_rows(GATE_SIDECAR)
    code, tail = run_command(_py("validation/wave_align_gate_forward_sweep.py", "--annotate"))
    if code != 0:
        raise RuntimeError(f"annotate rc={code} {tail}")
    return f"gate_sidecar_rows={_delta_text(before, count_rows(GATE_SIDECAR))}"


def step_mm_shadow_record() -> str:
    before = count_rows(SHADOW_SIDECAR)
    code, tail = run_command(_py("validation/wave_mm_shadow_sweep.py", "--record"))
    if code != 0:
        raise RuntimeError(f"record rc={code} {tail}")
    return f"shadow_rows={_delta_text(before, count_rows(SHADOW_SIDECAR))}"


STEPS: tuple[tuple[str, Callable[[], str]], ...] = (
    ("watchlist_scan", step_watchlist_scan),
    ("f2b_annotate", step_f2b_annotate),
    ("mm_shadow_record", step_mm_shadow_record),
)


def run_steps(steps=STEPS, log_fn: Callable[[str], None] = log) -> dict:
    """각 단계를 순서대로 실행한다. 실패해도 다음 단계로 넘어간다."""
    results: dict = {}
    for name, fn in steps:
        started = time.monotonic()
        try:
            detail = fn() or ""
            elapsed = time.monotonic() - started
            log_fn(f"step={name} | status=ok | elapsed={elapsed:.1f}s | {detail}".rstrip(" |"))
            results[name] = "ok"
        except Exception as exc:  # noqa: BLE001 — 한 단계 실패가 나머지를 막지 않는다
            elapsed = time.monotonic() - started
            log_fn(f"step={name} | status=failed | elapsed={elapsed:.1f}s | "
                   f"reason={str(exc)[:200]}")
            results[name] = "failed"
    return results


def main() -> int:
    dropped = rotate_log()
    log(f"run=start | retention_days={LOG_RETENTION_DAYS} | rotated_lines={dropped}")
    started = time.monotonic()
    results = run_steps()
    ok = sum(1 for v in results.values() if v == "ok")
    log(f"run=end | steps_ok={ok}/{len(results)} | elapsed={time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
