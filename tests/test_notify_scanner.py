"""알림 스캐너(notify/) — 체리픽 동일성 · 검출 import 소비 단언 · 닫힌 봉만 발화 · 중복 차단 · 최초 실행 제한 ·
메시지 형식 · Secrets 부재 안전 종료 · 발송 실패 미기록 · 회전 · dry-run · 워크플로 계약 · 금지 항목."""
import hashlib
import json
import os
import re
import subprocess
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import notify  # noqa: E402
import notify.events as EV  # noqa: E402
import notify.fetch as F  # noqa: E402
import notify.history as H  # noqa: E402
import notify.scanner as S  # noqa: E402
import notify.telegram as TG  # noqa: E402
import display.ma60_turn_tracker as MT  # noqa: E402
import display.trend_structure as TS  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402

CACHE_CSV = os.path.join(ROOT, "validation", "_ma60_turn_cache", "ohlcv_BTCUSDT_4h.csv")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "notify_scan.yml")


def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def _git_show(spec: str):
    try:
        return subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None


# ------------------------------------------------------------ 체리픽 동일성 · import 소비
def test_cherrypick_manifest_matches_files_and_source_commit():
    assert set(notify.CHERRYPICK) == {"display/tz_label.py", "display/ma60_turn_tracker.py",
                                      "display/trend_structure.py", "validation/wave_ma60_turn_probe.py"}
    for rel, sha in notify.CHERRYPICK.items():
        local = _norm(open(os.path.join(ROOT, rel), "rb").read())
        assert hashlib.sha256(local).hexdigest() == sha, f"{rel} 가 매니페스트와 다르다 (내용 무변경 원칙)"
        blob = _git_show(f"{notify.CHERRYPICK_SOURCE_COMMIT}:{rel}")
        if blob is None:
            pytest.skip("git 또는 원본 커밋을 읽을 수 없음 — 매니페스트 해시로만 확인")
        assert _norm(blob) == local, f"{rel} 가 원본 커밋 {notify.CHERRYPICK_SOURCE_COMMIT} 과 diff 있음"
    # 트래커 자체의 probe 매니페스트와도 일치(양 브랜치 같은 blob)
    assert MT.CHERRYPICK_PROBE["validation/wave_ma60_turn_probe.py"] == notify.CHERRYPICK["validation/wave_ma60_turn_probe.py"]


def test_detection_is_imported_not_reimplemented():
    assert EV.MT is MT and EV.TS is TS and TS.probe is probe and MT.probe is probe
    src = open(EV.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "MT.track_candidates(" in src and "TS.analyze(" in src
    for banned in ("stoch_pivot", "compute_series_pivots", "find_swing_lows", "find_swing_highs", "np.roll",
                   "shift(", "rolling(", "extract_signals(", "\"MA60\"]"):
        assert banned not in src, banned
    # 스캐너 패키지 어디에도 검출기·지표 계산 없음
    for fn in ("scanner.py", "fetch.py", "history.py", "telegram.py"):
        body = open(os.path.join(ROOT, "notify", fn), encoding="utf-8").read()
        for banned in ("stoch_pivot", "compute_series_pivots", "find_swing", "np.roll", "rolling("):
            assert banned not in body, (fn, banned)


def test_scanner_only_touches_vision_endpoint_and_not_data_binance():
    src = open(F.__file__, encoding="utf-8").read().split('"""', 2)[2]      # 본문(독스트링 제외)
    assert F.VISION_KLINES_URL == "https://data-api.binance.vision/api/v3/klines"
    assert "data.binance" not in src and "api.binance.com" not in src and "BINANCE_BASE_URL" not in src
    blob = _git_show("0be06d7:data/binance.py")   # 이 작업 직전 main 의 data/binance.py
    if blob is None:
        pytest.skip("git 없음")
    assert _norm(blob) == _norm(open(os.path.join(ROOT, "data", "binance.py"), "rb").read()), "data/binance.py 무접촉"


# ------------------------------------------------------------ 데이터 픽스처 (계측 캐시 — 네트워크 없음)
@pytest.fixture(scope="module")
def bars():
    if not os.path.isfile(CACHE_CSV):
        pytest.skip("계측 캐시 CSV 없음")
    df = pd.read_csv(CACHE_CSV, index_col=0, parse_dates=True).tail(1000)
    df.index.name = "open_time"
    return df


@pytest.fixture(scope="module")
def pipe(bars):
    return S.build_pipe(bars)


@pytest.fixture(scope="module")
def events(pipe):
    return EV.scan_frame(pipe, "BTCUSDT", "4h")


def _raw_from_bars(df: pd.DataFrame, step_ms: int = 4 * 3_600_000):
    rows = []
    for ts, r in df.iterrows():
        o = int(pd.Timestamp(ts).value // 1_000_000)
        rows.append([o, str(r["open"]), str(r["high"]), str(r["low"]), str(r["close"]), str(r["volume"]),
                     o + step_ms - 1, "0", 0, "0", "0", "0"])
    return rows


# ------------------------------------------------------------ 이벤트 = 검출 모듈 출력 그대로
def test_events_equal_tracker_turned_rows_and_structure_ll_rows(pipe, events):
    turned = MT.track_candidates(pipe, recent_bars=len(pipe))
    turned = turned[turned["상태"] == MT.STATUS_TURNED]
    got_turn = {e.ts for e in events if e.kind == EV.KIND_MA60_TURN}
    assert got_turn == set(pd.to_datetime(turned["전환 시각"])) and len(got_turn) >= 1
    res = TS.analyze(pipe)
    ll = [r for r in res["chain"] if r["kind"] == TS.KIND_LOW and r["cls"] == TS.CLS_LL]
    got_ll = {e.ts for e in events if e.kind == EV.KIND_STRUCTURE_LL}
    assert got_ll == {pd.Timestamp(r["ts"]) for r in ll} and len(got_ll) >= 1
    for e in events:
        assert e.last_pos == len(pipe) - 1 and 0 <= e.known_pos <= e.last_pos
        if e.kind == EV.KIND_STRUCTURE_LL:
            assert e.known_pos == int(pipe.index.get_loc(e.ts)) + TS.PIVOT   # 스윙 확정 후행
        else:
            assert e.known_pos == int(pipe.index.get_loc(e.ts))


def test_event_key_is_symbol_tf_kind_bar_timestamp(events):
    e = events[0]
    assert e.key == f"BTCUSDT|4h|{e.kind}|{e.ts:%Y-%m-%dT%H:%M:%S}Z"
    assert len({x.key for x in events}) == len(events)


# ------------------------------------------------------------ 닫힌 봉만
def test_closed_only_drops_in_progress_bar(bars):
    raw = _raw_from_bars(bars.tail(5))
    now_ms = raw[-1][F.CLOSE_TIME_COL]          # 마지막 봉이 아직 닫히지 않음(close_time == now)
    kept = F.closed_only(raw, now_ms)
    assert len(kept) == 4 and kept[-1][0] == raw[-2][0]
    assert len(F.closed_only(raw, raw[-1][F.CLOSE_TIME_COL] + 1)) == 5
    assert F.closed_only([], now_ms) == []


def test_turn_does_not_fire_while_turn_bar_is_in_progress(bars, events):
    """전환봉이 진행 중(닫히지 않음)인 시점에는 이벤트 없음 → 봉이 닫힌 뒤에만 발화."""
    turn = max((e for e in events if e.kind == EV.KIND_MA60_TURN), key=lambda e: e.ts)
    pos = int(bars.index.get_loc(turn.ts))
    raw = _raw_from_bars(bars.iloc[: pos + 1])           # 전환봉까지 포함한 원시 kline
    in_progress_now = raw[-1][F.CLOSE_TIME_COL]            # 전환봉 close_time 직전
    from data.processor import build_dataframe
    df_open = build_dataframe(F.closed_only(raw, in_progress_now))
    assert df_open.index[-1] < turn.ts
    assert all(e.ts != turn.ts for e in EV.scan_frame(S.build_pipe(df_open), "BTCUSDT", "4h"))
    df_closed = build_dataframe(F.closed_only(raw, in_progress_now + 1))
    assert df_closed.index[-1] == turn.ts
    fired = [e for e in EV.scan_frame(S.build_pipe(df_closed), "BTCUSDT", "4h") if e.ts == turn.ts]
    assert len(fired) == 1 and fired[0].bars_since_known == 0


def test_fetch_closed_bars_uses_vision_url_and_strips_last_open_bar(bars):
    raw = _raw_from_bars(bars.tail(300))
    calls = []

    class _R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return raw

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return _R()

    df = F.fetch_closed_bars("BTCUSDT", "4h", get=fake_get, now_ms=raw[-1][F.CLOSE_TIME_COL])
    assert calls[0][0] == F.VISION_KLINES_URL and calls[0][1]["symbol"] == "BTCUSDT"
    assert len(df) == 299 and list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index[-1] == bars.index[-2]


# ------------------------------------------------------------ 메시지 형식
def _turn_event(ts="2026-09-18 12:00", last_pos=100, known_pos=99):
    return EV.Event("BTCUSDT", "4h", EV.KIND_MA60_TURN, pd.Timestamp(ts), known_pos, last_pos, {
        "confirm_ts": pd.Timestamp("2026-09-18 08:00"), "turn_ts": pd.Timestamp(ts), "bars": 1,
        "price": 80725.6, "pattern_low": 74967.97, "baseline": 74593.13})


def _ll_event(ts="2026-09-19 00:00", last_pos=100, known_pos=99):
    return EV.Event("ETHUSDT", "1h", EV.KIND_STRUCTURE_LL, pd.Timestamp(ts), known_pos, last_pos, {
        "low_ts": pd.Timestamp(ts), "low": 4321.5, "prev_low": 4400.0, "pct": -1.784,
        "known_ts": pd.Timestamp("2026-09-19 03:00"), "base_low": 4100.25,
        "base_confirm_ts": pd.Timestamp("2026-09-15 20:00"), "state": TS.STATE_BROKEN})


def test_message_format_ma60_turn_matches_delegation_example():
    msg = EV.format_message(_turn_event())
    assert msg.splitlines() == [
        "[BTCUSDT 4h] 60MA 전환 발생 (미검증)",
        "쌍바닥 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)",      # UTC 08:00/12:00 → KST +9h
        "가격 80,726 · 패턴 저점 74,968 / 기준선 74,593",
    ]


def test_message_format_structure_ll_kst_and_labels():
    msg = EV.format_message(_ll_event())
    lines = msg.splitlines()
    assert lines[0] == "[ETHUSDT 1h] 구조 훼손 — 저점 LL 발생 (미검증)"
    assert lines[1] == "저점 09-19 09:00 4,322 < 직전 저점 4,400 (-1.78%) · 확정 09-19 12:00"
    assert lines[2] == "기준 저점 4,100 (쌍바닥 확정 09-16 05:00) · 현재 구조: 훼손 (LL 발생)"


def test_messages_carry_unverified_and_no_recommendation_words(events):
    for e in list(events) + [_turn_event(), _ll_event()]:
        msg = EV.format_message(e)
        assert "(미검증)" in msg.splitlines()[0]
        for w in EV.FORBIDDEN_WORDS:
            assert w not in msg, (w, msg)
        assert re.search(r"\d{2}-\d{2} \d{2}:\d{2}", msg)


# ------------------------------------------------------------ 계획(순수 함수): 최초 실행 제한 · 중복 · 회전 창
def test_plan_initial_run_sends_only_recent_two_bars():
    now = pd.Timestamp("2026-09-19 12:00")
    evs = [_turn_event("2026-09-19 08:00", last_pos=100, known_pos=100),     # 0봉 전 → 발송
           _turn_event("2026-09-19 04:00", last_pos=100, known_pos=99),      # 1봉 전 → 발송
           _turn_event("2026-09-19 00:00", last_pos=100, known_pos=98),      # 2봉 전 → 기록만
           _turn_event("2026-09-10 00:00", last_pos=100, known_pos=50)]      # 오래됨 → 기록만
    acts = {e.ts: a for e, a in S.plan(evs, H.empty(), now)}
    assert acts[pd.Timestamp("2026-09-19 08:00")] == S.ACT_SEND
    assert acts[pd.Timestamp("2026-09-19 04:00")] == S.ACT_SEND
    assert acts[pd.Timestamp("2026-09-19 00:00")] == S.ACT_RECORD_ONLY
    assert acts[pd.Timestamp("2026-09-10 00:00")] == S.ACT_RECORD_ONLY


def test_initial_mode_is_no_delivered_entry_not_just_empty_file():
    """Secrets 없이 돌며 기록만 쌓인 이력도 최초 실행 모드 — Secrets 투입 순간 밀린 이벤트가 쏟아지지 않는다."""
    now = pd.Timestamp("2026-09-19 12:00")
    hist = H.empty()
    H.record(hist, "X|1h|ma60_turn|2026-09-18T00:00:00Z", "2026-09-18 00:00", delivered=False, now=now)
    assert not H.is_empty(hist) and H.nothing_delivered(hist)
    evs = [_turn_event("2026-09-19 08:00", known_pos=100), _turn_event("2026-09-19 00:00", known_pos=98)]
    acts = {e.ts: a for e, a in S.plan(evs, hist, now)}
    assert acts[pd.Timestamp("2026-09-19 08:00")] == S.ACT_SEND and acts[pd.Timestamp("2026-09-19 00:00")] == S.ACT_RECORD_ONLY
    H.record(hist, "Y|1h|ma60_turn|2026-09-18T04:00:00Z", "2026-09-18 04:00", delivered=True, now=now)
    assert not H.nothing_delivered(hist)
    assert {a for _, a in S.plan(evs, hist, now)} == {S.ACT_SEND}


def test_plan_same_key_twice_in_one_run_sends_once():
    """두 쌍바닥 후보가 같은 봉에서 전환 → 키 동일 → 한 실행 안에서도 1건만 (Actions 첫 실행 로그에서 관찰된 사례)."""
    now = pd.Timestamp("2026-09-19 12:00")
    a = _turn_event("2026-09-19 08:00", known_pos=100)
    b = EV.Event(a.symbol, a.tf, a.kind, a.ts, a.known_pos, a.last_pos, {**a.fields, "bars": 7})
    assert a.key == b.key and a != b
    acts = [act for _, act in S.plan([a, b], H.empty(), now)]
    assert acts.count(S.ACT_SEND) == 1 and acts.count(S.ACT_DUP) == 1


def test_plan_non_initial_sends_everything_unseen_within_scan_window():
    now = pd.Timestamp("2026-09-19 12:00")
    hist = H.empty()
    H.record(hist, _turn_event("2026-09-19 04:00").key, "2026-09-19 04:00", delivered=True, now=now)
    evs = [_turn_event("2026-09-19 04:00", known_pos=99), _turn_event("2026-09-10 00:00", known_pos=50),
           _turn_event("2026-08-01 00:00", known_pos=1)]
    acts = {e.ts: a for e, a in S.plan(evs, hist, now)}
    assert acts[pd.Timestamp("2026-09-19 04:00")] == S.ACT_DUP
    assert acts[pd.Timestamp("2026-09-10 00:00")] == S.ACT_SEND        # 이력 있음 → 2봉 제한 없음
    assert acts[pd.Timestamp("2026-08-01 00:00")] == S.ACT_OLD         # 회전 창 밖 → 재발송 불가


def test_history_rotation_and_scan_window_consistency(tmp_path):
    assert H.SCAN_MAX_AGE_DAYS < H.RETENTION_DAYS == 30 and H.INITIAL_RECENT_BARS == 2
    now = pd.Timestamp("2026-09-20 00:00")
    hist = H.empty()
    H.record(hist, "A|1h|ma60_turn|2026-08-01T00:00:00Z", "2026-08-01 00:00", delivered=True, now=now)
    H.record(hist, "B|1h|ma60_turn|2026-09-01T00:00:00Z", "2026-09-01 00:00", delivered=False, now=now)
    assert H.rotate(hist, now) == 1 and list(hist["sent"]) == ["B|1h|ma60_turn|2026-09-01T00:00:00Z"]
    assert hist["sent"]["B|1h|ma60_turn|2026-09-01T00:00:00Z"] == {"event_ts": "2026-09-01T00:00:00Z",
                                                                  "sent_at": None, "delivered": False}
    p = tmp_path / "sent.json"
    H.save(str(p), hist)
    assert H.load(str(p)) == {"version": 1, "sent": hist["sent"]}
    assert not list(tmp_path.glob(".sent-*"))          # 임시 파일 정리
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        H.load(str(p))


# ------------------------------------------------------------ run(): 대역 fetch/발송으로 종단 간
class _Sender:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def __call__(self, token, chat, text):
        self.calls.append((token, chat, text))
        return (True, "ok") if self.ok else (False, "HTTP 500")


def _fetch_of(bars):
    return lambda sym, tf: bars


def _now_after(bars):
    return bars.index[-1] + pd.Timedelta(hours=4)


def test_run_dedups_across_runs_and_persists_history(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    env = {"TELEGRAM_TOKEN": "t0k", "TELEGRAM_CHAT_ID": "42"}
    hist = H.empty()                                       # 최초 실행 제한을 피하려고 무관 키 1개를 심는다
    H.record(hist, "X|1h|ma60_turn|2026-08-31T00:00:00Z", "2026-08-31 00:00", delivered=True, now=_now_after(bars))
    H.save(state, hist)
    now = _now_after(bars)
    in_window = [e for e in events if e.ts >= now - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)]
    assert in_window, "픽스처 안에 창 안 이벤트가 있어야 한다"
    s1 = _Sender()
    r1 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars),
               send=s1, env=env, now=now)
    assert r1["sent"] == len(in_window) == len(s1.calls) and r1["old"] == len(events) - len(in_window)
    saved = json.load(open(state, encoding="utf-8"))
    assert all(e.key in saved["sent"] and saved["sent"][e.key]["delivered"] for e in in_window)
    assert all("t0k" not in c[2] for c in s1.calls)
    s2 = _Sender()
    r2 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars),
               send=s2, env=env, now=now)
    assert r2["sent"] == 0 and r2["dup"] == len(in_window) and s2.calls == []


def test_run_initial_history_limits_to_recent_bars_and_records_rest(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    now = _now_after(bars)
    s = _Sender()
    r = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars),
              send=s, env={"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}, now=now)
    in_window = [e for e in events if e.ts >= now - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)]
    recent = [e for e in in_window if e.bars_since_known < H.INITIAL_RECENT_BARS]
    assert r["sent"] == len(recent) == len(s.calls) and r["record_only"] == len(in_window) - len(recent)
    saved = json.load(open(state, encoding="utf-8"))["sent"]
    assert len(saved) == len(in_window)
    assert all(saved[e.key]["delivered"] is (e in recent) for e in in_window)


def test_send_failure_is_not_recorded_and_retried_next_run(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    now = _now_after(bars)
    H.save(state, {"version": 1, "sent": {"X|1h|ma60_turn|2026-08-31T00:00:00Z":
                                          {"event_ts": "2026-08-31T00:00:00Z", "sent_at": "2026-08-31T00:00:00Z", "delivered": True}}})
    env = {"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
    bad = _Sender(ok=False)
    r = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=bad, env=env, now=now)
    assert r["send_failed"] == len(bad.calls) > 0 and r["sent"] == 0
    assert len(json.load(open(state, encoding="utf-8"))["sent"]) == 1      # 실패분 미기록
    good = _Sender()
    r = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=good, env=env, now=now)
    assert r["sent"] == len(bad.calls) == len(good.calls)                   # 다음 실행에서 재시도


def test_secrets_absent_logs_only_and_exits_zero(tmp_path, bars, monkeypatch):
    state = str(tmp_path / "sent.json")
    H.save(state, {"version": 1, "sent": {"X|1h|ma60_turn|2026-08-31T00:00:00Z":
                                          {"event_ts": "2026-08-31T00:00:00Z", "sent_at": "2026-08-31T00:00:00Z", "delivered": True}}})
    assert TG.credentials({}) is None and TG.credentials({"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": " "}) is None
    assert TG.credentials({"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}) == ("t", "c")
    for k in (TG.ENV_TOKEN, TG.ENV_CHAT_ID):
        monkeypatch.delenv(k, raising=False)

    def boom(*a, **k):
        raise AssertionError("발송이 호출되면 안 된다")

    monkeypatch.setattr(S.F, "fetch_closed_bars", _fetch_of(bars))
    monkeypatch.setattr(S.TG, "send_message", boom)
    monkeypatch.setattr(S, "utcnow", lambda: _now_after(bars))
    rc = S.main(["--state", state, "--symbols", "BTCUSDT", "--tfs", "4h"])
    assert rc == 0
    assert len(json.load(open(state, encoding="utf-8"))["sent"]) == 1      # 미발송분 미기록


def test_dry_run_sends_nothing_and_writes_nothing(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    s = _Sender()
    r = S.run(state_path=state, dry_run=True, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=s,
              env={"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}, now=_now_after(bars))
    assert s.calls == [] and not os.path.exists(state)
    assert r["would_send"] + r["record_only"] + r["old"] == len(events) and r["sent"] == 0


def test_cell_failure_does_not_stop_other_cells(tmp_path, bars):
    def fetch(sym, tf):
        if sym == "ETHUSDT":
            raise RuntimeError("boom")
        return bars

    r = S.run(state_path=str(tmp_path / "s.json"), dry_run=True, symbols=["ETHUSDT", "BTCUSDT"], tfs=["4h"],
              fetch=fetch, send=_Sender(), env={}, now=_now_after(bars))
    assert len(r["failures"]) == 1 and "ETHUSDT 4h" in r["failures"][0] and r["events"] > 0


def test_telegram_send_masks_token_and_never_raises():
    class _R:
        status_code = 500
        text = "boom with SECRET-TOKEN inside"

    ok, why = TG.send_message("SECRET-TOKEN", "c", "hi", post=lambda *a, **k: _R())
    assert ok is False and "SECRET-TOKEN" not in why

    def raising(*a, **k):
        raise ConnectionError("dns https://api.telegram.org/botSECRET-TOKEN/sendMessage")

    ok, why = TG.send_message("SECRET-TOKEN", "c", "hi", post=raising)
    assert ok is False and "SECRET-TOKEN" not in why
    sent = {}

    class _OK:
        status_code = 200

        def json(self):
            return {"ok": True}

    def post(url, json=None, timeout=None):
        sent.update(json)
        return _OK()

    assert TG.send_message("T", "C", "msg", post=post) == (True, "ok") and sent == {
        "chat_id": "C", "text": "msg", "disable_web_page_preview": True}


# ------------------------------------------------------------ 고정 대상 · 워크플로 계약 · 금지 항목
def test_fixed_scan_targets():
    assert S.SYMBOLS == ("BTCUSDT", "ETHUSDT", "BNBUSDT") and S.TFS == ("1h", "4h", "1d")


def test_workflow_contract():
    import yaml
    raw = open(WORKFLOW, encoding="utf-8").read()
    wf = yaml.safe_load(raw)
    text = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("#"))   # 주석 제외
    on = wf.get("on", wf.get(True))
    assert on["schedule"] == [{"cron": "7,22,37,52 * * * *"}] and "workflow_dispatch" in on   # 15분 주기, 정각 회피
    assert on["workflow_dispatch"]["inputs"]["dry_run"]["type"] == "boolean"
    assert wf["permissions"] == {"contents": "write"} and wf["concurrency"]["group"] == "notify-scan"
    assert "${{ secrets.TELEGRAM_TOKEN }}" in text and "${{ secrets.TELEGRAM_CHAT_ID }}" in text
    assert "python -m notify.scanner" in text and "--dry-run" in text
    assert "HEAD:main" not in text and "notify-state" in text          # 이력은 main 이 아니라 별도 브랜치
    assert re.search(r"git push[^\n]*\$STATE_BRANCH", text) and not re.search(r"git push[^\n]*main", text)
    assert "--force" not in text


def test_no_forbidden_indicators_or_symbols_in_notify_package():
    for fn in os.listdir(os.path.join(ROOT, "notify")):
        if not fn.endswith(".py"):
            continue
        body = open(os.path.join(ROOT, "notify", fn), encoding="utf-8").read()
        for banned in (r"RSI", r"MACD", r"[\"']5m[\"']"):
            assert not re.search(banned, body), (fn, banned)
        for w in EV.FORBIDDEN_WORDS:
            assert w not in body or fn == "events.py", (fn, w)       # events.py 는 금지 목록 정의만
    assert "5m" not in S.TFS and "15m" not in S.TFS
