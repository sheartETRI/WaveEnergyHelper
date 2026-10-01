"""OHLCV 로컬 저장소 — 바이낸스 raw kline 행을 TF 별 CSV 로 보관하고 꼬리만 갱신한다.

앱(`data/binance.fetch_klines`)과 스캔 스크립트(`scripts/sweep_scan_report.py`)가 같은 파일을
공유한다. 판정·지표·알람 로직과 무관한 데이터 계층 — 호출자에게 돌아가는 것은 바이낸스
`/api/v3/klines` 응답과 같은 모양의 행 리스트(12칸, open_time 오름차순)뿐이다.

  · 파일    <base_dir>/ohlcv_<SYMBOL>_<interval>.csv  (1M 은 1mo — 대소문자 무시 파일시스템에서 1m 과 충돌 방지)
  · 꼬리    마지막 저장 봉의 open_time 부터 재요청 → 그 봉(미완성일 수 있음)은 덮어쓰고 뒤를 붙인다.
            마감된 봉은 거래소에서 바뀌지 않으므로 이것으로 충분하다.
  · 백필    저장 봉 수 < min_bars 면 첫 봉 앞을 endTime 커서로 페이지 단위 보충 (상장 시작에 닿으면 중단).
            닿은 첫 봉은 프로세스 동안 기억해, 역사가 min_bars 보다 짧은 TF(월봉 등)가 갱신마다
            빈 백필 요청을 반복하지 않는다.
  · 연속성  이번 호출로 새로 들어온 봉 주변에서 인접 open_time 간격 > interval 이면 그 구간만 재요청.
            재요청 후에도 남는 틈(거래소 다운타임)은 result.gaps 로 보고만 하고 다시 두드리지 않는다.
  · 쓰기    임시파일 → os.replace (원자적). 앱·스크립트가 동시에 써도 파일이 깨지지 않는다 (마지막 쓰기 승).
  · 실패    원격 수신 실패 시 저장본이 있으면 그대로 돌려주고 stale=True (앱은 "N분 전 데이터" 캡션),
            저장본이 없으면 예외를 그대로 올린다 (종전 오류 경로 유지).

전송 계층은 fetch_page 주입으로 분리한다 — streamlit·requests 에 의존하지 않는 순수 모듈.
  fetch_page(symbol, interval, limit, start_time=None, end_time=None) -> list[row]
  (startTime/endTime 는 바이낸스 규약 그대로 open_time 기준 ms, 오름차순 반환)
"""
from __future__ import annotations

import csv
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

COLUMNS = (
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
)
_INT_COLS = (0, 6, 8)                  # 바이낸스 응답에서 정수인 칸 — 나머지는 문자열 그대로
DEFAULT_PAGE_LIMIT = 1000
DEFAULT_MAX_GAP_REQUESTS = 5           # 한 번의 refresh 에서 틈 메우기에 쓰는 요청 상한
_MAX_PAGES = 400                       # 꼬리·백필 루프 안전 상한 (400k 봉)
_REPLACE_RETRIES = 5                   # Windows: 다른 프로세스가 읽는 중이면 replace 가 잠깐 실패

_UNIT_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_HEAD_REACHED: dict[str, int] = {}     # 저장 경로 → 상장 시작에 닿았을 때의 첫 봉 open_time (프로세스 동안)

FetchPage = Callable[..., list]


def default_base_dir() -> str:
    """기본 저장 위치 — 이 모듈 옆 data/cache/ (logs/ 처럼 git 추적 제외)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def interval_ms(interval: str) -> Optional[int]:
    """인터벌 문자열 → 봉 간격 ms. 달력 단위(1M)는 가변이라 None."""
    if interval == "1M" or not interval:
        return None
    unit = interval[-1]
    if unit not in _UNIT_MS:
        return None
    try:
        return int(interval[:-1]) * _UNIT_MS[unit]
    except ValueError:
        return None


def interval_slug(interval: str) -> str:
    return "1mo" if interval == "1M" else interval


def store_path(symbol: str, interval: str, base_dir: Optional[str] = None) -> str:
    return os.path.join(base_dir or default_base_dir(),
                        f"ohlcv_{symbol.upper()}_{interval_slug(interval)}.csv")


def _lock_for(path: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(os.path.abspath(path), threading.Lock())


# ── 파일 입출력 ────────────────────────────────────────────────────────────
def _coerce(row: list) -> list:
    out = list(row[:len(COLUMNS)])
    if len(out) < len(COLUMNS):
        out += ["0"] * (len(COLUMNS) - len(out))
    for i in _INT_COLS:
        out[i] = int(float(out[i]))
    for i in range(len(COLUMNS)):
        if i not in _INT_COLS:
            out[i] = str(out[i])
    return out


def load_rows(path: str) -> list:
    """CSV → raw 행 리스트 (open_time 오름차순, 중복 제거). 파일이 없거나 깨졌으면 빈 리스트."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None or tuple(header) != COLUMNS:
                logger.warning("ohlcv store %s: 헤더 불일치 → 무시하고 새로 받음", path)
                return []
            rows = [_coerce(r) for r in reader if r]
    except (OSError, ValueError) as exc:
        logger.warning("ohlcv store %s 읽기 실패 (%s) → 무시하고 새로 받음", path, exc)
        return []
    return _dedupe_sorted(rows)


def save_rows(path: str, rows: list) -> None:
    """원자적 쓰기 — 같은 디렉터리의 임시파일에 쓰고 os.replace."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ohlcv_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
        last_exc: Optional[BaseException] = None
        for attempt in range(_REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError as exc:          # Windows: 상대가 읽는 중
                last_exc = exc
                time.sleep(0.05 * (attempt + 1))
        raise last_exc  # type: ignore[misc]
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _dedupe_sorted(rows: list) -> list:
    by_open: dict[int, list] = {}
    for r in rows:
        by_open[int(r[0])] = r
    return [by_open[k] for k in sorted(by_open)]


def merge_rows(old: list, new: list) -> list:
    """open_time 기준 병합 — 같은 봉은 new 가 이긴다 (미완성 봉 덮어쓰기)."""
    return _dedupe_sorted(list(old) + [_coerce(r) for r in new])


def find_gaps(rows: list, step: Optional[int]) -> list:
    """인접 open_time 간격 > step 인 구간 [(빠진 첫 open_time, 빠진 마지막 open_time), …]."""
    if step is None or len(rows) < 2:
        return []
    gaps = []
    for a, b in zip(rows, rows[1:]):
        if b[0] - a[0] > step:
            gaps.append((a[0] + step, b[0] - step))
    return gaps


# ── 갱신 ──────────────────────────────────────────────────────────────────
@dataclass
class RefreshResult:
    rows: list                              # 저장소 전체 (open_time 오름차순)
    path: str
    fetched: bool = True                    # 이번 호출에서 원격 수신 성공
    stale: bool = False                     # 수신 실패 → 저장본 그대로
    error: Optional[str] = None
    added: int = 0                          # 새로 들어온 봉 수 (덮어쓴 마지막 봉 제외)
    requests: int = 0                       # 이번 호출의 원격 요청 수
    gaps: list = field(default_factory=list)  # 재요청 후에도 남은 틈
    last_success_ms: Optional[int] = None   # 마지막 성공 저장 시각 (파일 mtime)

    @property
    def last_open_time(self) -> Optional[int]:
        return self.rows[-1][0] if self.rows else None

    def stale_minutes(self, now_ms: Optional[int] = None) -> Optional[float]:
        if self.last_success_ms is None:
            return None
        now = int(time.time() * 1000) if now_ms is None else now_ms
        return max(0.0, (now - self.last_success_ms) / 60_000.0)


def _mtime_ms(path: str) -> Optional[int]:
    try:
        return int(os.path.getmtime(path) * 1000)
    except OSError:
        return None


def refresh(
    symbol: str,
    interval: str,
    fetch_page: FetchPage,
    min_bars: int,
    *,
    base_dir: Optional[str] = None,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    max_gap_requests: int = DEFAULT_MAX_GAP_REQUESTS,
) -> RefreshResult:
    """저장소 읽기 → 꼬리 갱신 → 부족분 백필 → 새 봉 주변 틈 메우기 → 저장. 전체 행을 돌려준다.

    호출자는 필요한 만큼 `rows[-limit:]` 로 잘라 쓴다. 원격 실패 시 저장본이 있으면 stale 결과,
    없으면 예외를 그대로 올린다.
    """
    path = store_path(symbol, interval, base_dir)
    step = interval_ms(interval)
    with _lock_for(path):
        loaded = load_rows(path)
        before = {r[0] for r in loaded}
        result = RefreshResult(rows=loaded, path=path, fetched=False, last_success_ms=_mtime_ms(path))
        session = _Session(symbol, interval, fetch_page, page_limit, result)
        try:
            session.refresh_tail()
            session.backfill(min_bars)
            session.fill_new_gaps(before, step, max_gap_requests)
        except Exception as exc:  # noqa: BLE001 — 전송 계층의 어떤 실패든 저장본으로 버틴다
            if not result.rows:
                raise
            result.error = f"{type(exc).__name__}: {exc}"
            logger.warning("ohlcv store %s %s: 수신 실패 (%s) → 저장본 %d봉 사용 (최신 구간 수신 %s)",
                           symbol, interval, result.error, len(result.rows),
                           "성공" if result.fetched else "실패")
        # 꼬리(최신 구간)가 맨 먼저 오므로, 꼬리 수신이 실패하면 아무것도 병합되지 않은 상태다
        # → 저장하지 않고 파일 mtime(= 마지막 성공 시각)이 그대로 남아 "N분 전" 캡션이 정직하다.
        rows = result.rows
        result.stale = not result.fetched
        result.added = sum(1 for r in rows if r[0] not in before)
        result.gaps = find_gaps(rows, step)
        if rows is not loaded:                      # 무엇이든 병합됐으면 진행분 저장 (부분 백필 포함)
            try:
                save_rows(path, rows)
                result.last_success_ms = _mtime_ms(path)
            except OSError as exc:                  # 쓰기 불가(권한·디스크) — 받은 행은 그대로 돌려준다
                logger.warning("ohlcv store %s 저장 실패 (%s) → 이번 수신분은 저장 없이 반환", path, exc)
        return result


class _Session:
    """한 번의 refresh 동안의 상태 — 페이지마다 result.rows 를 제자리 갱신해 중간 실패에도 진행분이 남는다."""

    def __init__(self, symbol, interval, fetch_page, page_limit, result: RefreshResult):
        self.symbol, self.interval, self.fetch_page = symbol, interval, fetch_page
        self.page_limit, self.result = page_limit, result

    def page(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        self.result.requests += 1
        page = self.fetch_page(self.symbol, self.interval, self.page_limit,
                               start_time=start_time, end_time=end_time)
        page = [_coerce(r) for r in (page or [])]
        if page:
            self.result.rows = merge_rows(self.result.rows, page)
        return page

    def refresh_tail(self) -> None:
        rows = self.result.rows
        if not rows:
            return
        start = rows[-1][0]                       # 마지막 봉 포함 재요청 → 덮어쓰기
        for _ in range(_MAX_PAGES):
            page = self.page(start_time=start)
            self.result.fetched = True            # 최신 구간 수신 성공 (빈 응답도 "지금 상태" 다)
            if len(page) < self.page_limit:
                break
            start = page[-1][0] + 1

    def backfill(self, min_bars: int) -> None:
        for _ in range(_MAX_PAGES):
            rows = self.result.rows
            if len(rows) >= min_bars:
                break
            if rows and _HEAD_REACHED.get(self.result.path) == rows[0][0]:
                break                             # 이 프로세스에서 이미 상장 시작까지 받았다
            end = rows[0][0] - 1 if rows else None
            page = self.page(end_time=end)
            if end is None:
                self.result.fetched = True        # 빈 저장소의 첫 페이지 = 최신 구간
            if len(page) < self.page_limit:       # 상장 시작(또는 그 이전) 에 닿음
                if self.result.rows:
                    _HEAD_REACHED[self.result.path] = self.result.rows[0][0]
                break

    def fill_new_gaps(self, before: set, step: Optional[int], max_gap_requests: int) -> None:
        """이번 호출로 새로 들어온 봉이 경계에 있는 틈만 메운다 — 오래된 틈(거래소 다운타임)은 재시도하지 않는다."""
        if step is None:
            return
        budget = max_gap_requests
        for gap_start, gap_end in find_gaps(self.result.rows, step):
            if budget <= 0:
                break
            touches_new = (gap_start - step) not in before or (gap_end + step) not in before
            if not touches_new:
                continue
            cursor = gap_start
            while cursor <= gap_end and budget > 0:
                budget -= 1
                page = self.page(start_time=cursor, end_time=gap_end)
                if not page:
                    break
                cursor = page[-1][0] + step


def tail(rows: list, limit: int) -> list:
    """호출자용 — 마지막 limit 봉 (limit ≤ 0 이면 전체)."""
    return list(rows[-limit:]) if limit and limit > 0 else list(rows)
