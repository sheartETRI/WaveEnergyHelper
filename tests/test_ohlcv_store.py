"""OHLCV 저장소 테스트 — 꼬리 갱신·백필·틈·실패 시 저장본 계약. 전송은 가짜 거래소로 주입."""
import os
import subprocess
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
    assert res.requests == 1 and ex.calls[-1] == (1000, first.rows[-2][0], None)   # 끝에서 두 번째(확정) 봉부터 — 겹쳐 대조
    assert res.rebuilt is None
    assert res.added == 5 and len(res.rows) == len(first.rows) + 5
    overwritten = next(r for r in res.rows if r[0] == old_last)
    assert overwritten[4] == "100.7"                                      # 미완성 봉 덮어쓰기
    assert _contiguous(res.rows) and store.load_rows(res.path) == res.rows


def test_tail_paginates_when_many_new_bars(tmp_path):
    ex = FakeExchange(1000)
    _refresh(ex, tmp_path, min_bars=1000)
    ex.advance(2500)
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.requests == 3 and res.added == 2500 and _contiguous(res.rows)   # 1000, 1000, 502 (겹친 확정 봉 포함)


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


# ── 오염 복구 (2026-10-02 사고 모양 — 가짜 응답이 실제 저장소에 섞인 파일) ──────────────
WEEK = 7 * 86_400_000
MONDAY = 1_600_041_600_000          # 2020-09-14 00:00 UTC (월) — 바이낸스 주봉 시작. epoch 정렬 주봉은 목요일 시작


class BtcLikeExchange(FakeExchange):
    """가격대가 실제 BTC 수준인 거래소 — 100 대에서 시작하는 가짜와 이어 붙으면 이음매가 3배 넘게 벌어진다."""

    def _row(self, t, version=0):
        return [t, "60000.0", "60100.0", "59900.0", f"60000.{version}", "10.0", t + self.step - 1,
                "1000.0", 5, "5.0", "500.0", "0"]


def _fake_rows(open_times, step):
    """사고의 가짜 응답 모양 — 100.2285 에서 매끈하게 오르는 소수 4자리 수열, 거래량 "1.0", 체결 0."""
    rows = []
    for i, t in enumerate(open_times):
        c = 100.2285 + 0.0285 * i
        rows.append([t, f"{c - 0.0285:.4f}", f"{c + 0.01:.4f}", f"{c - 0.04:.4f}", f"{c:.4f}", "1.0",
                     t + step - 1, "0", 0, "0", "0", "0"])
    return rows


def _exchange_copy(rows, ex):
    """rows 가 전부 거래소 봉 그대로(가짜 없음)이고, 빈틈 없이 거래소 최신 봉까지 이어지는지."""
    return (bool(rows) and rows[-1][0] == max(ex.bars) and _contiguous(rows, ex.step)
            and all(r[0] in ex.bars and r == store._coerce(ex.bars[r[0]]) for r in rows))


def test_aligned_fake_over_tail_is_rebuilt_in_one_refresh(tmp_path):
    """(i) 정렬된 가짜가 꼬리를 덮은 파일 — 겹친 확정 봉의 OHLC 가 거래소와 달라 (b) 로 한 번에 재구축."""
    ex = BtcLikeExchange(3000)
    first = _refresh(ex, tmp_path, min_bars=2000)
    res = _refresh(ex, tmp_path, min_bars=2000)                       # 정상 파일 — 처음 읽어도 꼬리 1회 그대로
    assert res.requests == 1 and res.rebuilt is None and not os.path.exists(res.path + ".corrupt")
    fake = _fake_rows([r[0] for r in first.rows[-1000:]], STEP)
    store.save_rows(first.path, store.merge_rows(first.rows, fake))  # 끝 1000봉을 가짜로 덮음
    res = _refresh(ex, tmp_path, min_bars=2000)
    assert res.rebuilt and "OHLC 불일치" in res.rebuilt, res.rebuilt
    assert res.requests == 1 + 2                                      # 꼬리 대조 1 + 빈 상태에서 2000봉 (1000 × 2)
    assert len(res.rows) == 2000 and _exchange_copy(res.rows, ex) and store.load_rows(res.path) == res.rows
    assert store.load_rows(res.path + ".corrupt")[-1][4] == fake[-1][4]          # 오염본은 .corrupt 로 보관
    nxt = _refresh(ex, tmp_path, min_bars=2000)
    assert nxt.requests == 1 and nxt.rebuilt is None                  # 다음 갱신은 다시 꼬리 1회


def test_thursday_fake_interleaved_in_weekly_file_is_rebuilt(tmp_path):
    """(ii) 목요일 시작 가짜 1000봉이 월요일 시작 실제 주봉 사이에 끼어든 1w 파일 — 인접 간격 < 1주 (c) 로 재구축."""
    ex = BtcLikeExchange(300, step=WEEK, t0=MONDAY)                   # 역사 300주 < 1000 → 상장 시작까지 한 페이지
    first = store.refresh("BTCUSDT", "1w", ex.fetch_page, 1000, base_dir=str(tmp_path))
    last_thursday = max(ex.bars) - max(ex.bars) % WEEK
    assert (last_thursday - MONDAY) % WEEK == 3 * 86_400_000          # 목요일 — 실제 주봉 사이
    fake = _fake_rows([last_thursday - (999 - i) * WEEK for i in range(1000)], WEEK)
    store.save_rows(first.path, store.merge_rows(first.rows, fake))
    res = store.refresh("BTCUSDT", "1w", ex.fetch_page, 1000, base_dir=str(tmp_path))
    assert res.rebuilt and "인접 봉 간격" in res.rebuilt, res.rebuilt
    assert res.requests == 1 and len(res.rows) == 300 and _exchange_copy(res.rows, ex)
    assert store._HEAD_REACHED[res.path] == MONDAY and os.path.exists(res.path + ".corrupt")


@pytest.mark.parametrize("interval,step,t0,reason_part", [
    ("1h", STEP, T0, "OHLC 불일치"),                  # 정렬이 같은 가짜 — 겹친 확정 봉 값이 다름 (b)
    ("1w", WEEK, MONDAY, "요청 startTime"),           # 목요일 시작 가짜 — 응답 첫 봉이 요청 시각과 다름 (a)
])
def test_fake_only_file_is_rebuilt(tmp_path, interval, step, t0, reason_part):
    """(iii) 가짜만 찬 파일 — 이음매가 없어 (d) 는 조용하지만 꼬리 대조가 잡아 한 번에 재구축."""
    ex = BtcLikeExchange(1500, step=step, t0=t0)
    last = max(ex.bars)
    last_fake = last if interval == "1h" else last - last % WEEK     # 1w: epoch 정렬 = 목요일
    path = store.store_path("BTCUSDT", interval, str(tmp_path))
    store.save_rows(path, _fake_rows([last_fake - (999 - i) * step for i in range(1000)], step))
    res = store.refresh("BTCUSDT", interval, ex.fetch_page, 1000, base_dir=str(tmp_path))
    assert res.rebuilt and reason_part in res.rebuilt, res.rebuilt
    assert res.requests == 2 and len(res.rows) == 1000 and _exchange_copy(res.rows, ex)
    assert store.load_rows(path) == res.rows and os.path.exists(path + ".corrupt")


def test_fake_block_followed_by_real_bars_is_rebuilt_on_first_read(tmp_path):
    """(iv) 가짜 블록 뒤에 실제 봉이 이미 붙은 파일 — 꼬리는 실제라 대조를 통과하므로, 새 프로세스에서 파일을
    처음 읽을 때 이음매 (d) 로 재구축한다."""
    ex = BtcLikeExchange(3000)
    first = _refresh(ex, tmp_path, min_bars=2000)
    _refresh(ex, tmp_path, min_bars=2000)                             # 이 프로세스는 이미 한 번 읽었다
    block = [r[0] for r in first.rows[-1200:-200]]                    # 가짜 1000봉 뒤에 실제 200봉
    store.save_rows(first.path, store.merge_rows(first.rows, _fake_rows(block, STEP)))
    same = _refresh(ex, tmp_path, min_bars=2000)
    assert same.rebuilt is None and same.requests == 1                # 같은 프로세스 — (d) 는 처음 읽을 때만
    store._SCANNED.clear()                                            # 새 프로세스
    store._HEAD_REACHED.clear()
    res = _refresh(ex, tmp_path, min_bars=2000)
    assert res.rebuilt and "직전 종가" in res.rebuilt, res.rebuilt
    assert res.requests == 2 and len(res.rows) == 2000 and _exchange_copy(res.rows, ex)
    assert store.load_rows(res.path) == res.rows and os.path.exists(res.path + ".corrupt")


def test_rebuild_forgets_listing_start_memory(tmp_path):
    """재구축하면 그 경로의 '상장 첫 봉 도달' 기억을 지운다 — 남아 있으면 다음 갱신의 백필을 건너뛴다."""
    ex = BtcLikeExchange(3000)
    first = _refresh(ex, tmp_path, min_bars=1000)
    store._HEAD_REACHED[first.path] = first.rows[0][0]                # 오염 시절에 생긴 기억이라고 하자
    store.save_rows(first.path, store.merge_rows(first.rows, _fake_rows([r[0] for r in first.rows[-10:]], STEP)))
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.rebuilt and res.rows[0][0] == first.rows[0][0] and first.path not in store._HEAD_REACHED
    deeper = _refresh(ex, tmp_path, min_bars=2000)
    assert deeper.requests == 2 and len(deeper.rows) == 2000          # 꼬리 + 백필 1페이지


def test_rebuilt_rows_are_not_rechecked_in_the_same_call(tmp_path):
    """다시 받은 행은 같은 호출에서 재검사하지 않는다 — 거래소 역사 자체에 큰 가격대 변화가 있어도 재구축은 한 번."""
    ex = BtcLikeExchange(1500)
    for t in sorted(ex.bars)[:900]:                                   # 거래소 역사 자체의 가격대 변화 (60배)
        ex.bars[t] = [t, "1000.0", "1001.0", "999.0", "1000.0"] + ex.bars[t][5:]
    path = store.store_path("BTCUSDT", "1h", str(tmp_path))
    store.save_rows(path, [ex.bars[T0 + 1400 * STEP], [T0 + 1400 * STEP + STEP // 2] + ex.bars[T0][1:]])  # 끼어든 행
    res = _refresh(ex, tmp_path, min_bars=1000)
    assert res.rebuilt and "인접 봉 간격" in res.rebuilt and res.requests == 1 and _exchange_copy(res.rows, ex)
    nxt = _refresh(ex, tmp_path, min_bars=1000)
    assert nxt.rebuilt is None and nxt.requests == 1


def test_monthly_interleave_threshold_is_28_days():
    day = 86_400_000
    row = ["1"] * 5 + ["1", 0, "1", 1, "1", "1", "0"]
    assert store._interleaved([[0] + row[1:], [28 * day] + row[1:]], "1M") is None
    assert store._interleaved([[0] + row[1:], [27 * day] + row[1:]], "1M")


# ── 경로·격리 (2026-10-02 오염 사고 재발 방지) ─────────────────────────────────
def test_store_dir_env_takes_priority_over_settings(monkeypatch, tmp_path):
    from config import settings

    env_dir, settings_dir = str(tmp_path / "env_dir"), str(tmp_path / "settings_dir")
    monkeypatch.setenv(store.STORE_DIR_ENV, env_dir)
    monkeypatch.setitem(settings.OHLCV_STORE_PARAMS, "dir", settings_dir)
    assert store.resolve_store_dir() == os.path.normpath(env_dir)
    assert os.path.dirname(store.store_path("BTCUSDT", "1h")) == os.path.normpath(env_dir)
    monkeypatch.delenv(store.STORE_DIR_ENV)
    assert store.resolve_store_dir() == os.path.normpath(settings_dir)
    monkeypatch.setitem(settings.OHLCV_STORE_PARAMS, "dir", "data/cache")          # 운영 기본값 — 저장소 루트 기준
    assert store.resolve_store_dir() == os.path.normpath(store.REAL_STORE_DIR)     # 경로 해석만 (쓰지 않음)


def test_store_dir_env_reaches_subprocesses():
    """conftest 가 지정한 저장 경로·pytest 표지는 자식 프로세스까지 간다 — 자식의 쓰기도 임시 폴더·트립와이어 아래."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import os, sys; sys.path.insert(0, sys.argv[1]); from data import ohlcv_store as s; "
            "print(s.resolve_store_dir()); print(bool(os.environ.get('PYTEST_CURRENT_TEST')))")
    out = subprocess.run([sys.executable, "-c", code, root], capture_output=True, text=True, timeout=120, check=True)
    resolved, under_pytest = out.stdout.splitlines()[-2:]
    assert resolved == os.path.normpath(os.environ[store.STORE_DIR_ENV]) and under_pytest == "True"
    assert os.path.normcase(resolved) != os.path.normcase(os.path.normpath(store.REAL_STORE_DIR))


def test_tripwire_refuses_real_store_during_pytest():
    real, name = store.REAL_STORE_DIR, "ohlcv_TRIPWIRE_1h.csv"
    variants = [os.path.join(real, name), real.replace(os.sep, "/") + "/" + name,
                os.path.join(real, "sub", name)]                                   # 안쪽 폴더도
    if os.name == "nt":                                                            # 대소문자 무시 파일시스템
        variants += [os.path.join(real.upper(), name), os.path.join(real.lower(), name)]
    listing = sorted(os.listdir(real)) if os.path.isdir(real) else None
    try:
        for path in variants:
            with pytest.raises(RuntimeError, match="실제 OHLCV 저장소"):
                store.save_rows(path, [])
        assert (sorted(os.listdir(real)) if os.path.isdir(real) else None) == listing   # 쓰기 전에 막힘 — 임시파일도 없음
    finally:                                                                         # 트립와이어가 고장 났을 때만 남는 흔적
        for leftover in (os.path.join(real, name), os.path.join(real, "sub", name)):
            if os.path.exists(leftover):
                os.remove(leftover)
        if os.path.isdir(os.path.join(real, "sub")) and not os.listdir(os.path.join(real, "sub")):
            os.rmdir(os.path.join(real, "sub"))


def test_tripwire_is_quiet_for_temp_dirs_and_outside_pytest(monkeypatch, tmp_path):
    path = str(tmp_path / "ohlcv_BTCUSDT_1h.csv")
    store.save_rows(path, [[1, "1", "1", "1", "1", "1", 2, "1", 1, "1", "1", "0"]])  # 임시 폴더 — pytest 중에도 쓴다
    assert len(store.load_rows(path)) == 1
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    store._refuse_real_store(os.path.join(store.REAL_STORE_DIR, "ohlcv_BTCUSDT_1h.csv"))   # pytest 밖 — 검사 안 함 (쓰지는 않음)
