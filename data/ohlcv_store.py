"""OHLCV 로컬 저장소 — 바이낸스 raw kline 행을 TF 별 CSV 로 보관하고 꼬리만 갱신한다.

앱(`data/binance.fetch_klines`)과 스캔 스크립트(`scripts/sweep_scan_report.py`)가 같은 파일을
공유한다. 판정·지표·알람 로직과 무관한 데이터 계층 — 호출자에게 돌아가는 것은 바이낸스
`/api/v3/klines` 응답과 같은 모양의 행 리스트(12칸, open_time 오름차순)뿐이다.

  · 파일    <base_dir>/ohlcv_<SYMBOL>_<interval>.csv  (1M 은 1mo — 대소문자 무시 파일시스템에서 1m 과 충돌 방지)
  · 경로    resolve_store_dir() 한 곳 — 환경변수 WEH_OHLCV_STORE_DIR 최우선, 없으면 settings 의 dir(저장소 루트 기준).
            앱·스캔 스크립트·푸시 폴러(data/binance 경유)가 모두 이것을 쓴다. 테스트·가짜 응답 검증은 반드시
            임시 폴더로 — pytest 실행 중 실제 data/cache 에 쓰려 하면 RuntimeError (트립와이어).
  · 꼬리    끝에서 두 번째 저장 봉의 open_time 부터 재요청 → 확정 봉 하나와 항상 겹쳐 저장본을 거래소와 대조하고
            (요청 수 불변), 마지막 봉(미완성일 수 있음)은 덮어쓰고 뒤를 붙인다. 마감된 봉은 거래소에서 바뀌지 않는다.
  · 오염    하나라도 해당하면 경고 + <name>.corrupt 로 보관(덮어씀) + 빈 상태에서 min_bars 를 새로 받는다 (그 경로의
            '상장 첫 봉 도달' 기억도 초기화, 새로 받은 행은 같은 호출에서 재검사하지 않음) — 무엇이 새든 다음 갱신에서 복구.
              (a) 꼬리 응답 첫 행 open_time ≠ 요청 startTime            매 갱신
              (b) 겹친 확정 봉의 OHLC ≠ 저장본 (float 비교)             매 갱신
              (c) 인접 open_time 간격 < interval (1M 은 28일 미만)      매 갱신, 파일 전체 — 끼어든 행
              (d) 시가가 직전 종가의 3배 이상·1/3 이하                  프로세스에서 파일을 처음 읽을 때 1회 — 이음매
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

from config.settings import OHLCV_STORE_PARAMS

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
_SCANNED: set[str] = set()             # 이 프로세스에서 한 번 읽은 저장 경로 — 이음매 검사(d)는 처음 읽을 때 1회
_SEAM_RATIO = 3.0                      # 오염 (d): 시가 / 직전 종가 ≥ 3 또는 ≤ 1/3
_MIN_MONTH_MS = 28 * 86_400_000        # 오염 (c): 월봉 인접 간격 하한

STORE_DIR_ENV = "WEH_OHLCV_STORE_DIR"  # 저장 경로 재지정 — 테스트·가짜 응답 검증 실행은 반드시 임시 폴더로
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_STORE_DIR = os.path.join(_ROOT, "data", "cache")   # 운영 저장소 — pytest 중 쓰기 금지 (트립와이어)

FetchPage = Callable[..., list]


def resolve_store_dir() -> str:
    """저장 경로 — 환경변수 WEH_OHLCV_STORE_DIR 최우선, 없으면 settings.OHLCV_STORE_PARAMS["dir"](저장소 루트 기준).

    앱(data/binance)·스캔 스크립트·푸시 폴러(data/binance 경유)가 모두 이 함수로 경로를 정한다. 호출 시점에
    읽는다 — tests/conftest 가 환경변수를 임시 폴더로 바꾸면 서브프로세스까지 따라간다.
    """
    override = os.environ.get(STORE_DIR_ENV, "").strip()
    if override:
        return os.path.normpath(os.path.abspath(override))
    return os.path.normpath(os.path.join(_ROOT, OHLCV_STORE_PARAMS["dir"]))


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
    return os.path.join(base_dir or resolve_store_dir(),
                        f"ohlcv_{symbol.upper()}_{interval_slug(interval)}.csv")


class RealStoreWriteError(RuntimeError):
    """pytest 실행 중 실제 저장소(<repo>/data/cache)에 쓰려 함 — 호출자가 '수신 실패'로 삼키지 않는다."""


def _norm_dir(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _refuse_real_store(path: str) -> None:
    """트립와이어 — PYTEST_CURRENT_TEST 가 있는데 path 가 실제 <repo>/data/cache 안이면 RealStoreWriteError.

    2026-10-02 가짜 바이낸스 응답 실행이 운영 저장소를 덮은 사고의 재발 방지. Windows 대소문자·구분자는
    정규화해 비교한다. pytest 밖(앱·스크립트·폴러)에서는 아무것도 하지 않는다.
    """
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    target, real = _norm_dir(os.path.dirname(os.path.abspath(path))), _norm_dir(REAL_STORE_DIR)
    if target == real or target.startswith(real.rstrip(os.sep) + os.sep):
        raise RealStoreWriteError(
            f"테스트 중 실제 OHLCV 저장소에 쓰기 시도: {path} — {STORE_DIR_ENV} 를 임시 폴더로 지정할 것")


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
    """원자적 쓰기 — 같은 디렉터리의 임시파일에 쓰고 os.replace. pytest 중 실제 저장소면 쓰기 전에 RuntimeError."""
    _refuse_real_store(path)
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
    rebuilt: Optional[str] = None           # 오염으로 버리고 새로 받았으면 그 사유

    @property
    def last_open_time(self) -> Optional[int]:
        return self.rows[-1][0] if self.rows else None

    def stale_minutes(self, now_ms: Optional[int] = None) -> Optional[float]:
        if self.last_success_ms is None:
            return None
        now = int(time.time() * 1000) if now_ms is None else now_ms
        return max(0.0, (now - self.last_success_ms) / 60_000.0)


# ── 오염 검사 ─────────────────────────────────────────────────────────────
def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")                     # 해석 불가 — 비교하면 항상 '다름'


def _interleaved(rows: list, interval: str) -> Optional[str]:
    """(c) 인접 open_time 간격 < interval — 정렬이 다른 수열이 끼어든 행 (1M 은 28일 미만)."""
    step = _MIN_MONTH_MS if interval == "1M" else interval_ms(interval)
    if step is None:
        return None
    for a, b in zip(rows, rows[1:]):
        if b[0] - a[0] < step:
            return f"인접 봉 간격 {b[0] - a[0]}ms < {interval} ({a[0]} → {b[0]})"
    return None


def _price_seam(rows: list) -> Optional[str]:
    """(d) 시가가 직전 종가의 3배 이상 또는 1/3 이하 — 가격대가 다른 수열이 이어 붙은 이음매."""
    for a, b in zip(rows, rows[1:]):
        prev_close, open_ = _num(a[4]), _num(b[1])
        if not (prev_close > 0 and open_ > 0):
            continue
        ratio = open_ / prev_close
        if ratio >= _SEAM_RATIO or ratio <= 1.0 / _SEAM_RATIO:
            return f"봉 {b[0]} 시가 {b[1]} = 직전 종가 {a[4]} 의 {ratio:.3g}배"
    return None


def _tail_mismatch(rows: list, start: int, page: list) -> Optional[str]:
    """꼬리 첫 응답 대조 — (a) 첫 행 open_time ≠ 요청 startTime, (b) 겹친 확정 봉의 OHLC ≠ 저장본.

    빈 응답은 판단하지 않는다. 저장 봉이 하나뿐이면 겹친 봉이 미완성일 수 있어 (b) 는 생략.
    """
    if not page:
        return None
    if page[0][0] != start:
        return f"꼬리 응답 첫 봉 {page[0][0]} ≠ 요청 startTime {start}"
    if len(rows) >= 2:
        stored, got = rows[-2], page[0]
        if any(_num(stored[i]) != _num(got[i]) for i in (1, 2, 3, 4)):
            return f"겹친 확정 봉 {start} OHLC 불일치 (저장 {stored[1:5]} · 응답 {got[1:5]})"
    return None


def _archive_corrupt(path: str) -> None:
    """오염 파일을 <name>.corrupt 로 보관 (이전 보관본은 덮어씀). 옮기지 못하면 경고만 — 다음 저장이 덮어쓴다."""
    _refuse_real_store(path)
    if not os.path.exists(path):
        return
    try:
        os.replace(path, path + ".corrupt")
    except OSError as exc:
        logger.warning("ohlcv store %s: .corrupt 보관 실패 (%s) → 다음 저장이 덮어씀", path, exc)


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
    """저장소 읽기 → 오염 검사 → 꼬리 갱신(겹친 확정 봉 대조) → 부족분 백필 → 새 봉 주변 틈 메우기 → 저장.
    전체 행을 돌려준다. 오염이면 파일을 .corrupt 로 보관하고 같은 호출에서 빈 상태부터 다시 받는다.

    호출자는 필요한 만큼 `rows[-limit:]` 로 잘라 쓴다. 원격 실패 시 저장본이 있으면 stale 결과,
    없으면 예외를 그대로 올린다.
    """
    path = store_path(symbol, interval, base_dir)
    step = interval_ms(interval)
    with _lock_for(path):
        loaded = load_rows(path)
        before = {r[0] for r in loaded}
        result = RefreshResult(rows=loaded, path=path, fetched=False, last_success_ms=_mtime_ms(path))
        session = _Session(symbol, interval, fetch_page, page_limit, result, before)
        session.check_stored()                      # (c)(d) — 오염이면 비우고 아래 백필이 새로 받는다
        try:
            session.refresh_tail()                  # (a)(b) — 겹친 확정 봉 대조
            session.backfill(min_bars)
            session.fill_new_gaps(before, step, max_gap_requests)
        except RealStoreWriteError:
            raise                                   # 테스트 격리 위반(트립와이어)은 저장본으로 버티지 않는다
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

    def __init__(self, symbol, interval, fetch_page, page_limit, result: RefreshResult, before: set):
        self.symbol, self.interval, self.fetch_page = symbol, interval, fetch_page
        self.page_limit, self.result = page_limit, result
        self.before = before                      # 갱신 전 저장 봉 open_time — 오염으로 버리면 비운다

    def fetch(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        self.result.requests += 1
        page = self.fetch_page(self.symbol, self.interval, self.page_limit,
                               start_time=start_time, end_time=end_time)
        return [_coerce(r) for r in (page or [])]

    def merge(self, page: list) -> None:
        if page:
            self.result.rows = merge_rows(self.result.rows, page)

    def page(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> list:
        page = self.fetch(start_time=start_time, end_time=end_time)
        self.merge(page)
        return page

    def check_stored(self) -> None:
        """저장본 검사 — (c) 끼어든 행은 매번 파일 전체, (d) 이음매는 이 프로세스에서 파일을 처음 읽을 때 1회."""
        rows, path = self.result.rows, self.result.path
        if not rows:
            return
        first_read = path not in _SCANNED
        _SCANNED.add(path)
        reason = _interleaved(rows, self.interval) or (_price_seam(rows) if first_read else None)
        if reason:
            self.discard(reason)

    def discard(self, reason: str) -> None:
        """오염 — 경고, 파일을 <name>.corrupt 로 보관, 빈 상태로. 이어지는 백필이 min_bars 를 새로 받고,
        새로 받은 행은 같은 호출에서 재검사하지 않는다 (무한 재구축 방지)."""
        path = self.result.path
        logger.warning("ohlcv store %s %s: 오염 감지 (%s) → %s.corrupt 로 보관하고 새로 받음",
                       self.symbol, self.interval, reason, os.path.basename(path))
        _archive_corrupt(path)
        _HEAD_REACHED.pop(path, None)
        self.before.clear()
        self.result.rows = []
        self.result.rebuilt = reason
        self.result.last_success_ms = None

    def refresh_tail(self) -> None:
        rows = self.result.rows
        if not rows:
            return
        # 끝에서 두 번째 저장 봉부터 — 확정 봉 하나와 겹쳐 대조하고, 마지막 봉(미완성일 수 있음)은 덮어쓴다.
        start = rows[-2][0] if len(rows) >= 2 else rows[-1][0]
        page = self.fetch(start_time=start)
        self.result.fetched = True                # 최신 구간 수신 성공 (빈 응답도 "지금 상태" 다)
        reason = _tail_mismatch(rows, start, page)
        if reason:
            self.discard(reason)                  # 백필이 빈 상태에서 min_bars 를 새로 받는다
            return
        self.merge(page)
        for _ in range(_MAX_PAGES - 1):
            if len(page) < self.page_limit:
                break
            page = self.page(start_time=page[-1][0] + 1)

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
