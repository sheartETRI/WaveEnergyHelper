"""OHLCV 저장소 테스트 — 꼬리 갱신·백필·틈·실패 시 저장본 계약. 전송은 가짜 거래소로 주입."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import ohlcv_store as store

STEP = 3_600_000            # 1h
T0 = 1_600_000_000_000


class FakeExchange:
    """바이낸스 /klines 규약 흉내: startTime 은 그 이후 첫 limit 봉, endTime 만 있으면 그 이전 최신 limit 봉."""

    def __init__(self, n_bars, step=STEP, t0=T0, holes=()):
        self.step, self.t0 = step, t0
        self.bars = {}
        for i in range(n_bars):
            t = t0 + i * step
            if t not in holes:
                self.bars[t] = self._row(t)
        self.calls = []
        self.fail = False
        self.fail_at_call = None      # n 번째 호출(1-based)에서 예외
        self.drop_once = set()        # 첫 응답에서만 빠뜨릴 open_time (플래키 응답 모사)

    def _row(self, t, version=0):
        return [t, "100.0", "101.0", "99.0", f"100.{version}", "10.0", t + self.step - 1,
                "1000.0", 5, "5.0", "500.0", "0"]

    def advance(self, n, mutate_last=True):
        last = max(self.bars)
        if mutate_last:
            self.bars[last] = self._row(last, version=7)      # 미완성 봉의 종가가 바뀜
        for i in range(1, n + 1):
            t = last + i * self.step
            self.bars[t] = self._row(t)

    def fetch_page(self, symbol, interval, limit, start_time=None, end_time=None):
        self.calls.append((limit, start_time, end_time))
        if self.fail or (self.fail_at_call is not None and len(self.calls) == self.fail_at_call):
            raise ConnectionError("boom")
        keys = sorted(k for k in self.bars
                      if (start_time is None or k >= start_time) and (end_time is None or k <= end_time))
        keys = keys[:limit] if start_time is not None else keys[-limit:]
        if self.drop_once:
            keys = [k for k in keys if k not in self.drop_once]
            self.drop_once = set()
        return [list(self.bars[k]) for k in keys]


def _refresh(ex, tmp_path, min_bars, **kw):
    return store.refresh("BTCUSDT", "1h", ex.fetch_page, min_bars, base_dir=str(tmp_path), **kw)


def _contiguous(rows, step=STEP):
    return all(b[0] - a[0] == step for a, b in zip(rows, rows[1:]))


# ── 백필·꼬리 ──────────────────────────────────────────────────────────────
def test_empty_store_backfills_to_min_bars(tmp_path):
    ex = FakeExchange(3500)
    res = _refresh(ex, tmp_path, min_bars=2500)
    assert res.requests == 3 and len(res.rows) == 3000        # 최신 1000 + 이전 1000 + 이전 1000
    assert ex.calls[0] == (1000, None, None)                      # 최신 1000
    assert ex.calls[1] == (1000, None, T0 + 2500 * STEP - 1)      # 그 앞 페이지: endTime = 첫 봉 - 1
    assert ex.calls[2] == (1000, None, T0 + 1500 * STEP - 1)
    assert _contiguous(res.rows) and res.rows[-1][0] == max(ex.bars)
    assert res.fetched and not res.stale and res.added == 3000 and res.gaps == []
    assert os.path.exists(res.path) and store.load_rows(res.path) == res.rows


def test_tail_refresh_overwrites_open_bar_and_appends(tmp_path):
    ex = FakeExchange(1200)
    first = _refresh(ex, tmp_path, min_bars=1000)
    old_last = first.rows[-1][0]
    ex.advance(5)
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.requests == 1 and ex.calls[-1] == (1000, old_last, None)   # 마지막 봉 포함 재요청
    assert res.added == 5 and len(res.rows) == len(first.rows) + 5
    overwritten = next(r for r in res.rows if r[0] == old_last)
    assert overwritten[4] == "100.7"                                      # 미완성 봉 덮어쓰기
    assert _contiguous(res.rows) and store.load_rows(res.path) == res.rows


def test_tail_paginates_when_many_new_bars(tmp_path):
    ex = FakeExchange(1000)
    _refresh(ex, tmp_path, min_bars=1000)
    ex.advance(2500)
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.requests == 3 and res.added == 2500 and _contiguous(res.rows)   # 1000, 1000, 501


def test_no_backfill_when_store_already_deep(tmp_path):
    ex = FakeExchange(5000)
    _refresh(ex, tmp_path, min_bars=4000)
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.requests == 1 and len(res.rows) == 4000               # 꼬리만 — 4000봉은 그대로 유지


def test_backfill_stops_at_listing_start(tmp_path):
    ex = FakeExchange(1500)
    res = _refresh(ex, tmp_path, min_bars=10_000)
    assert len(res.rows) == 1500 and res.requests == 2               # 두 번째 페이지 500 < 1000 → 중단


def test_listing_start_is_probed_once_per_process(tmp_path):
    month = 30 * 86_400_000
    ex = FakeExchange(110, step=month)                                # 월봉 240 요청 · 역사 110봉
    store.refresh("BTCUSDT", "1M", ex.fetch_page, 240, base_dir=str(tmp_path))
    ex.advance(1)
    res = store.refresh("BTCUSDT", "1M", ex.fetch_page, 240, base_dir=str(tmp_path))
    assert res.requests == 1 and len(res.rows) == 111                 # 꼬리만 — 상장 시작은 이미 닿았다
    store._HEAD_REACHED.clear()                                       # 새 프로세스: 한 번은 다시 확인
    res = store.refresh("BTCUSDT", "1M", ex.fetch_page, 240, base_dir=str(tmp_path))
    assert res.requests == 2 and ex.calls[-1][2] == T0 - 1


# ── 실패 ─────────────────────────────────────────────────────────────────────
def test_failure_with_store_returns_stale_copy(tmp_path):
    ex = FakeExchange(1200)
    first = _refresh(ex, tmp_path, min_bars=1000)
    mtime = os.path.getmtime(first.path)
    ex.fail = True
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.stale and not res.fetched and "ConnectionError" in res.error
    assert res.rows == first.rows and res.added == 0
    assert os.path.getmtime(res.path) == mtime                        # 저장 안 함 → 마지막 성공 시각 유지
    assert res.last_success_ms == int(mtime * 1000)


def test_failure_without_store_raises(tmp_path):
    ex = FakeExchange(1200)
    ex.fail = True
    with pytest.raises(ConnectionError):
        _refresh(ex, tmp_path, min_bars=1000)
    assert not os.path.exists(store.store_path("BTCUSDT", "1h", str(tmp_path)))


def test_partial_backfill_progress_is_saved(tmp_path):
    ex = FakeExchange(3500)
    ex.fail_at_call = 2                                               # 최신 페이지는 성공, 그 다음 실패
    res = _refresh(ex, tmp_path, min_bars=2500)
    assert len(res.rows) == 1000 and res.error and res.fetched and not res.stale
    assert store.load_rows(res.path) == res.rows
    ex.fail_at_call = None
    res2 = _refresh(ex, tmp_path, min_bars=2500)                      # 이어서 백필
    assert len(res2.rows) == 3000 and res2.error is None and _contiguous(res2.rows)


# ── 틈 ───────────────────────────────────────────────────────────────────────
def test_old_gap_is_reported_but_not_retried(tmp_path):
    ex = FakeExchange(1200)
    first = _refresh(ex, tmp_path, min_bars=1000)
    rows = [r for r in first.rows if not (first.rows[300][0] <= r[0] <= first.rows[309][0])]
    store.save_rows(first.path, rows)                                 # 저장본에 오래된 틈을 만든다
    res = _refresh(ex, tmp_path, min_bars=900)                        # 990 ≥ 900 → 백필 없음
    assert res.requests == 1                                          # 꼬리만 — 옛 틈은 건드리지 않음
    assert res.gaps == [(first.rows[300][0], first.rows[309][0])]


def test_new_gap_from_flaky_page_is_filled(tmp_path):
    ex = FakeExchange(1000)
    _refresh(ex, tmp_path, min_bars=1000)
    ex.advance(50)
    last = max(ex.bars)
    ex.drop_once = {last - 20 * STEP, last - 19 * STEP}              # 꼬리 응답에서만 두 봉 누락
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.gaps == [] and _contiguous(res.rows)
    assert res.requests == 2                                          # 꼬리 + 틈 1구간
    assert ex.calls[-1] == (1000, last - 20 * STEP, last - 19 * STEP)


def test_permanent_gap_requests_are_bounded(tmp_path):
    holes = {T0 + i * STEP for i in (1100, 1150, 1200, 1250)}         # 거래소 자체에 없는 봉 4개
    ex = FakeExchange(1300, holes=holes)
    _refresh(ex, tmp_path, min_bars=1000)                             # 1300 중 최신 1000 (틈 4개 포함)
    res = _refresh(ex, tmp_path, min_bars=1000, max_gap_requests=2)
    assert res.requests == 1                                          # 저장된 틈은 옛 틈 → 재시도 없음
    assert len(res.gaps) == 4
    ex2 = FakeExchange(1300, holes=holes)
    res2 = store.refresh("ETHUSDT", "1h", ex2.fetch_page, 1000, base_dir=str(tmp_path), max_gap_requests=2)
    assert res2.requests == 1 + 2 and len(res2.gaps) == 4             # 첫 적재: 새 틈이지만 예산 2로 제한


# ── 형식·경로 ─────────────────────────────────────────────────────────────────
def test_row_types_match_binance_shape(tmp_path):
    ex = FakeExchange(1010)
    res = _refresh(ex, tmp_path, min_bars=1000)
    row = store.load_rows(res.path)[0]
    assert len(row) == 12
    assert isinstance(row[0], int) and isinstance(row[6], int) and isinstance(row[8], int)
    assert all(isinstance(row[i], str) for i in (1, 2, 3, 4, 5, 7, 9, 10, 11))
    assert row[4] == "100.0"                                          # 문자열 가격 그대로 (float 변환 없음)


def test_monthly_interval_has_no_step_and_distinct_path():
    assert store.interval_ms("1M") is None and store.interval_ms("1m") == 60_000
    assert store.interval_ms("3d") == 3 * 86_400_000 and store.interval_ms("1w") == 7 * 86_400_000
    p_month = store.store_path("BTCUSDT", "1M", "/x")
    p_minute = store.store_path("BTCUSDT", "1m", "/x")
    assert p_month.endswith("ohlcv_BTCUSDT_1mo.csv") and p_minute.endswith("ohlcv_BTCUSDT_1m.csv")
    assert p_month.lower() != p_minute.lower()


def test_monthly_rows_skip_gap_check(tmp_path):
    ex = FakeExchange(30, step=30 * 86_400_000)                         # 간격 불규칙해도 틈으로 안 봄
    res = store.refresh("BTCUSDT", "1M", ex.fetch_page, 12, base_dir=str(tmp_path))
    assert res.gaps == [] and len(res.rows) == 30


def test_corrupt_file_is_replaced(tmp_path):
    path = store.store_path("BTCUSDT", "1h", str(tmp_path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("garbage,,,\n1,2\n")
    assert store.load_rows(path) == []
    ex = FakeExchange(1200)
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert len(res.rows) == 1000 and store.load_rows(path) == res.rows


def test_save_is_atomic_and_leaves_no_temp(tmp_path):
    ex = FakeExchange(1200)
    res = _refresh(ex, tmp_path, min_bars=1000)
    leftovers = [n for n in os.listdir(os.path.dirname(res.path)) if n.endswith(".tmp")]
    assert leftovers == []


def test_tail_helper():
    rows = [[i] for i in range(10)]
    assert store.tail(rows, 3) == [[7], [8], [9]]
    assert store.tail(rows, 0) == rows and store.tail(rows, 100) == rows


def test_merge_prefers_new_and_sorts():
    old = [[2, "a"], [1, "a"]]
    new = [[2, "b"], [3, "b"]]
    merged = store.merge_rows(old, new)
    assert [r[0] for r in merged] == [1, 2, 3] and merged[1][1] == "b"
