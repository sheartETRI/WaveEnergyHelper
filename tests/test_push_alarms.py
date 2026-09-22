"""알림 Pushbullet 푸시 — notify/pushbullet + scripts/push_alarms (notify 스캐너 통합판) 단위·스모크 (네트워크 없음).

확인하는 계약:
  1. 토큰: 저장소 홈 token.txt 첫 줄, 없거나 비면 None. .gitignore 에 token.txt·이력 파일이 있다.
  2. push_note: /v2/pushes 에 Access-Token 헤더 + note JSON, 2xx 만 True, 예외·비 2xx 는 False(폴러가 죽지 않음).
  3. 닫힌 봉만: 마지막 봉이 진행 중이면 뺀다. 2d 는 1d 닫힌 봉을 config 규칙으로 합성(1d 두 봉 = 2d 한 봉), 창이 밀려도 짝 고정.
  4. 대상·종류·주기: BTCUSDT × 7 TF 고정(config/settings.py 무접촉), 종류 = notify.events.KINDS, LL 발송 제외, systemd 300/60.
  5. run: 폭탄 방지 2단(전역 2봉·종류별 첫 스캔 0건) · 중복 · dry-run 무기록 · 실패 미기록 · ledger 상승/하방 · 예전 이력 이관.
  6. 예전 경로(--legacy-signals, 기본 꺼짐): 3층 확정·RSI·MACD 묶음 푸시 — 기존 계약 그대로.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from analysis.alarm_signals import SEV_CONFIRMED, scan_alarm_signals  # noqa: E402
from data.processor import resample_timeframe  # noqa: E402
from display.alarm_panel import format_signal_line  # noqa: E402
from notify import events as EV  # noqa: E402
from notify import history as H  # noqa: E402
from notify import ledger as LG  # noqa: E402
from notify import plan as PL  # noqa: E402
from notify import pushbullet as PB  # noqa: E402
from scripts import push_alarms as P  # noqa: E402
from test_ma60_down_tracker import _pipeline, _raw  # noqa: E402
from test_slim_app_smoke import _pipeline_frame  # noqa: E402


@pytest.fixture(scope="module")
def frame():
    return _pipeline_frame()


@pytest.fixture(scope="module")
def synth():
    """합성 1h 프레임(지표 포함, 마지막 봉까지 닫힘으로 간주) — 상승/하방 전환·쌍바닥 후보 이벤트가 있다."""
    return _pipeline(_raw(n=1600, seed=7))


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


# ------------------------------------------------------------ 1. 토큰 · gitignore
def test_read_token_first_nonempty_line_or_none(tmp_path):
    p = tmp_path / "token.txt"
    p.write_text("\n# comment\n  o.abc123  \nsecond\n", encoding="utf-8")
    assert PB.read_token(str(p)) == "o.abc123"
    (tmp_path / "empty.txt").write_text("\n\n", encoding="utf-8")
    assert PB.read_token(str(tmp_path / "empty.txt")) is None
    assert PB.read_token(str(tmp_path / "missing.txt")) is None
    assert PB.DEFAULT_TOKEN_PATH == os.path.join(ROOT, "token.txt")


def test_gitignore_excludes_token_and_state():
    with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh]
    assert "token.txt" in lines and "pushbullet_state.json" in lines and "pushbullet_state.legacy.json" in lines


# ------------------------------------------------------------ 2. push_note
def test_push_note_posts_note_with_token_header():
    calls = []

    def post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json, timeout))
        return _Resp(200)

    assert PB.push_note("tok", "제목", "본문", post=post) is True
    url, headers, payload, timeout = calls[0]
    assert url == "https://api.pushbullet.com/v2/pushes"
    assert headers["Access-Token"] == "tok"
    assert payload == {"type": "note", "title": "제목", "body": "본문"}
    assert timeout == PB.TIMEOUT_SEC


def test_push_note_failures_return_false_without_raising():
    assert PB.push_note("tok", "t", "b", post=lambda *a, **k: _Resp(401, "unauthorized")) is False

    def boom(*a, **k):
        raise ConnectionError("down")

    assert PB.push_note("tok", "t", "b", post=boom) is False
    assert PB.push_note("", "t", "b", post=lambda *a, **k: _Resp(200)) is False   # 토큰 없음
    long_calls = []
    PB.push_note("tok", "t", "x" * (PB.BODY_MAX_CHARS + 100),
                 post=lambda u, headers, json, timeout: long_calls.append(json) or _Resp(200))
    assert len(long_calls[0]["body"]) <= PB.BODY_MAX_CHARS


# ------------------------------------------------------------ 3. 닫힌 봉 · 2d 리샘플 정합
def test_closed_frame_drops_open_last_bar(frame):
    last = pd.Timestamp(frame.index[-1])
    assert P.interval_delta("1h") == pd.Timedelta(hours=1) and P.interval_delta("1d") == pd.Timedelta(days=1)
    assert P.interval_delta("2h") == pd.Timedelta(hours=2) and P.interval_delta("12h") == pd.Timedelta(hours=12)
    assert P.interval_delta("6h") == pd.Timedelta(hours=6)
    open_now = last + pd.Timedelta(minutes=59)
    assert len(P.closed_frame(frame, "1h", open_now)) == len(frame) - 1
    closed_now = last + pd.Timedelta(hours=1)
    assert len(P.closed_frame(frame, "1h", closed_now)) == len(frame)
    assert P.closed_frame(None, "1h", closed_now) is None
    with pytest.raises(ValueError):
        P.interval_delta("2d")   # 커스텀 TF 는 베이스(1d)에서 닫힘 판정 → resample_closed


def _daily(n=11, start="2026-01-01"):
    idx = pd.date_range(start, periods=n, freq="D")
    v = np.arange(n, dtype=float)
    return pd.DataFrame({"open": v, "high": v + 10, "low": v - 10, "close": v + 0.5, "volume": 1.0}, index=idx)


def test_2d_resample_two_daily_bars_make_one_bar_and_pairs_are_stable_when_window_slides():
    assert P.resample_factor("2d") == 2
    with pytest.raises(ValueError):
        P.resample_factor("3h")
    with pytest.raises(ValueError):
        P.resample_factor("1h")
    base = _daily(11)                                     # 2026-01-01 = epoch 일수 20454(짝수) … 2026-01-11
    r = P.resample_closed(base, "2d")
    # 정렬: 첫 봉이 짝수 일수라 그대로. config 규칙(right/right/origin=start): (t0, t0+2D] → 01-02·01-03 → 라벨 01-03
    assert list(r.index.strftime("%m-%d")) == ["01-03", "01-05", "01-07", "01-09", "01-11"]
    for label, row in r.iterrows():                       # 1d 두 봉 합성 = 2d 한 봉 (open 첫·high 최대·low 최소·close 마지막·volume 합)
        pair = base.loc[label - pd.Timedelta(days=1): label]
        assert len(pair) == 2
        assert row["open"] == pair["open"].iloc[0] and row["close"] == pair["close"].iloc[-1]
        assert row["high"] == pair["high"].max() and row["low"] == pair["low"].min() and row["volume"] == 2.0
    # 라벨·값은 config 의 resample_timeframe 결과(정렬된 입력)와 동일 — 규칙 재정의 없음
    ref = resample_timeframe(P.align_base_frame(base, "2d"), "2d")
    pd.testing.assert_frame_equal(r, ref.loc[r.index])
    # 창이 하루 밀려도(첫 봉 01-02, 홀수 일수) 앞 봉 하나를 버려 같은 짝·같은 라벨
    slid = P.resample_closed(base.iloc[1:], "2d")
    assert list(slid.index) == list(r.index)[1:] or list(slid.index) == list(r.index)
    pd.testing.assert_frame_equal(slid, r.loc[slid.index])
    # 마지막 2d 봉에 1d 봉이 하나만 있으면(진행 중) 뺀다: 01-01..01-10 → 01-10 짝 미완
    part = P.resample_closed(base.iloc[:10], "2d")
    assert list(part.index.strftime("%m-%d")) == ["01-03", "01-05", "01-07", "01-09"]
    assert P.align_base_frame(base.iloc[1:], "2d").index[0] == pd.Timestamp("2026-01-03")
    assert P.resample_closed(base.iloc[:0], "2d").empty


def _klines(df: pd.DataFrame, step_ms: int):
    rows = []
    for ts, r in df.iterrows():
        o = int(pd.Timestamp(ts).value // 1_000_000)
        rows.append([o, str(r["open"]), str(r["high"]), str(r["low"]), str(r["close"]), str(r["volume"]),
                     o + step_ms - 1, "0", 0, "0", "0", "0"])
    return rows


def test_load_closed_frame_uses_base_interval_and_drops_open_bars():
    daily = _daily(400, start="2025-01-01")
    calls = []

    def fetch(symbol, interval, limit):
        calls.append((symbol, interval, limit))
        return _klines(daily, 86_400_000)

    now = pd.Timestamp(daily.index[-1]) + pd.Timedelta(hours=3)          # 마지막 1d 봉 진행 중
    out = P.load_closed_frame("BTCUSDT", "2d", now=now, fetch=fetch)
    assert calls[-1][1] == "1d"                                           # 2d 는 1d 를 받아 합성
    assert out.index[-1] < daily.index[-1] and "MA60" in out.columns and any(c.startswith("stoch_k_") for c in out.columns)
    ref = P.resample_closed(daily.iloc[:-1], "2d")
    assert list(out.index) == list(ref.index)
    out1 = P.load_closed_frame("BTCUSDT", "1d", now=now, fetch=fetch)
    assert calls[-1][1] == "1d" and out1.index[-1] == daily.index[-2]     # 진행 중 봉 제외
    assert P.load_closed_frame("BTCUSDT", "1d", now=now, fetch=lambda *a: []) is None


# ------------------------------------------------------------ 4. 대상 · 종류 · 주기
def test_targets_kinds_and_schedule_are_fixed_without_touching_settings():
    assert P.PUSH_TARGETS == {"symbols": ("BTCUSDT",), "intervals": ("1h", "2h", "4h", "6h", "12h", "1d", "2d")}
    assert P.LEDGER_INTERVALS == P.PUSH_TARGETS["intervals"]
    from config.settings import PUSH_WATCHLIST
    assert PUSH_WATCHLIST == {"symbols": ["BTCUSDT"], "intervals": ["1h", "2h", "4h", "6h", "1d"]}   # INTEGRITY 파일 무접촉
    assert EV.KINDS == ("ma60_turn", "ma60_down", "structure_ll", "stoch_db")
    assert PL.SEND_DISABLED_KINDS == frozenset({EV.KIND_STRUCTURE_LL})
    src = open(P.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "scan_alarm_signals(" in src.split("# ================================================================ 예전 경로")[1]
    assert "scan_alarm_signals(" not in src.split("# ================================================================ 예전 경로")[0]
    with open(os.path.join(ROOT, "deploy", "push_alarms.service"), encoding="utf-8") as fh:
        unit = fh.read()
    assert "scripts/push_alarms.py --loop 300 --offset 60" in unit and "--legacy-signals" not in unit and "Restart=always" in unit
    args = P.parse_args([])
    assert args.loop is None and not args.legacy_signals and args.export_ledger is None and args.offset == 60
    assert P.parse_args(["--legacy-signals", "--export-ledger", "x.csv"]).legacy_signals
    title, body = P.split_title("[BTCUSDT 4h] 60MA 전환 발생 (미검증)\n둘째 줄\n셋째 줄")
    assert title == "[WEH] [BTCUSDT 4h] 60MA 전환 발생 (미검증)" and body == "둘째 줄\n셋째 줄"


def test_loop_grid_wakes_at_offset_after_the_hour():
    hour = 1_800_000 * 2
    assert P.seconds_until_next_slot(hour, 300, 60) == 60
    assert P.seconds_until_next_slot(hour + 60, 300, 60) == 300
    assert P.seconds_until_next_slot(hour + 359, 300, 60) == 1
    assert P.seconds_until_next_slot(hour + 3599, 300, 60) == 61
    assert P.seconds_until_next_slot(hour, 3, 0) >= 1


# ------------------------------------------------------------ 5. run — 폭탄 방지 2단 · 중복 · dry-run · 실패 · ledger · 이관
class _Pusher:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def __call__(self, token, title, body):
        self.calls.append((token, title, body))
        return self.ok


def _fetch_of(pipe):
    return lambda sym, tf: pipe


def _now_after(pipe):
    return pd.Timestamp(pipe.index[-1]) + pd.Timedelta(hours=1)


def _kinds_seen(hist):
    for k in EV.KINDS:
        H.mark_kind(hist, k, now=pd.Timestamp("2020-01-01"))
    return hist


def test_run_first_deploy_sends_nothing_records_all_then_only_new_events(synth, tmp_path):
    state = str(tmp_path / "pushbullet_state.json")
    now = _now_after(synth)
    events = EV.scan_frame(synth, "BTCUSDT", "1h")
    in_window = {e.key for e in events if e.ts >= now - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)}
    assert in_window and {e.kind for e in events} >= {EV.KIND_MA60_TURN, EV.KIND_MA60_DOWN, EV.KIND_STOCH_DB}
    pusher = _Pusher()
    r1 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
               fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    # 1회차: 모든 종류가 '첫 스캔' → 발송 0, 창 안 이벤트 전량 기록, kinds 기록
    assert r1["sent"] == 0 and pusher.calls == [] and r1["new_kinds"] == list(EV.KINDS)
    assert r1["new_kind_record_only"] + r1["disabled_record_only"] == len(in_window) and r1["old"] == len(events) - len(in_window)
    saved = H.load(state)
    assert set(saved["sent"]) == in_window and all(not v["delivered"] for v in saved["sent"].values())
    assert set(saved["kinds"]) == set(EV.KINDS) and saved["ledger"]["since"] is not None
    # 2회차(같은 데이터): 전부 dup, 발송 0
    r2 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
               fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    assert r2["sent"] == 0 and r2["dup"] == len(in_window) and r2["new_kinds"] == []
    # 3회차: 이력에서 최신 상승/하방 전환 키 하나씩 지우면(새 이벤트 흉내) 그 둘만 발송 — 전역 최초 실행 규칙(2봉)은 kinds 와 별개라
    # 발송 성공 이력이 없으면 최근 2봉만 보내므로, 먼저 발송 성공 1건을 심어 둔다
    hist = H.load(state)
    newest = {}
    for e in events:
        if e.key in hist["sent"] and e.kind in (EV.KIND_MA60_TURN, EV.KIND_MA60_DOWN):
            newest[e.kind] = max(newest.get(e.kind, e), e, key=lambda x: x.ts)
    for e in newest.values():
        del hist["sent"][e.key]
    H.record(hist, "SEED|1h|ma60_turn|2026-01-01T00:00:00Z", now - pd.Timedelta(days=1), delivered=True, now=now)
    H.save(state, hist)
    r3 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
               fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    assert r3["sent"] == len(newest) == len(pusher.calls)
    titles = [t for _, t, _ in pusher.calls]
    assert all(t.startswith("[WEH] [BTCUSDT 1h] ") and "(미검증)" in t for t in titles)
    assert not any("구조 훼손" in t for t in titles)                          # LL 은 발송 제외
    for _, t, b in pusher.calls:
        for w in EV.FORBIDDEN_WORDS:
            assert w not in t + b
    assert all(H.load(state)["sent"][e.key]["delivered"] for e in newest.values())


def test_run_global_initial_mode_limits_to_recent_two_bars(synth, tmp_path):
    state = str(tmp_path / "s.json")
    H.save(state, _kinds_seen(H.empty()))                                     # 종류별 규칙은 미리 충족 → 전역 규칙만
    now = _now_after(synth)
    pusher = _Pusher()
    r = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
              fetch_frame=_fetch_of(synth), pusher=pusher, now=now, disabled_kinds=())
    events = EV.scan_frame(synth, "BTCUSDT", "1h")
    in_window = [e for e in events if e.ts >= now - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)]
    recent = [e for e in in_window if e.bars_since_known < H.INITIAL_RECENT_BARS]
    assert r["sent"] == len(recent) == len(pusher.calls) and r["record_only"] == len(in_window) - len(recent)
    saved = H.load(state)["sent"]
    assert len(saved) == len(in_window) and all(saved[e.key]["delivered"] is (e in recent) for e in in_window)


def test_run_disabled_kind_recorded_not_sent_and_dry_run_writes_nothing(synth, tmp_path):
    state = str(tmp_path / "s.json")
    hist = _kinds_seen(H.empty())
    H.record(hist, "SEED|1h|ma60_turn|2026-01-01T00:00:00Z", "2026-01-01 00:00", delivered=True, now=_now_after(synth))
    H.save(state, hist)
    now = _now_after(synth)
    events = EV.scan_frame(synth, "BTCUSDT", "1h")
    ll = [e for e in events if e.kind == EV.KIND_STRUCTURE_LL and e.ts >= now - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)]
    pusher = _Pusher()
    r = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
              fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    assert r["disabled_kinds"] == [EV.KIND_STRUCTURE_LL] and r["disabled_record_only"] == len({e.key for e in ll})
    assert not any("구조 훼손" in t for _, t, _ in pusher.calls) and r["sent"] > 0
    assert all(H.load(state)["sent"][e.key]["delivered"] is False for e in ll)
    state2 = str(tmp_path / "s2.json")
    r_dry = P.run(state_path=state2, dry_run=True, token=None, symbols=("BTCUSDT",), intervals=("1h",),
                  fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    assert not os.path.exists(state2) and r_dry["sent"] == 0 and r_dry["would_send"] == 0     # 첫 스캔 → 기록 대상만
    r_tok = P.run(state_path=state, dry_run=False, token=None, symbols=("BTCUSDT",), intervals=("1h",),
                  fetch_frame=_fetch_of(synth), pusher=pusher, now=now)
    assert r_tok["sent"] == 0 and r_tok["not_sent_no_token"] == 0 and r_tok["dup"] > 0       # 이미 기록/발송된 것은 dup


def test_run_send_failure_not_recorded_and_retried(synth, tmp_path):
    state = str(tmp_path / "s.json")
    hist = _kinds_seen(H.empty())
    H.record(hist, "SEED|1h|ma60_turn|2026-01-01T00:00:00Z", "2026-01-01 00:00", delivered=True, now=_now_after(synth))
    H.save(state, hist)
    now = _now_after(synth)
    bad = _Pusher(ok=False)
    r = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
              fetch_frame=_fetch_of(synth), pusher=bad, now=now, disabled_kinds=())
    assert r["send_failed"] == len(bad.calls) > 0 and r["sent"] == 0
    assert all(k == "SEED|1h|ma60_turn|2026-01-01T00:00:00Z" for k in H.load(state)["sent"])   # 실패분 미기록
    good = _Pusher()
    r = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
              fetch_frame=_fetch_of(synth), pusher=good, now=now, disabled_kinds=())
    assert r["sent"] == len(bad.calls) == len(good.calls)


def test_run_records_ledger_both_directions_after_since_and_export_csv(synth, tmp_path):
    state = str(tmp_path / "s.json")
    hist = _kinds_seen(H.empty())
    H.ledger_init(hist, now=pd.Timestamp("2020-01-01"))                     # since 를 과거로 → 종료 후보가 기록된다
    H.save(state, hist)
    now = _now_after(synth)
    r = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
              fetch_frame=_fetch_of(synth), pusher=_Pusher(), now=now)
    fin = LG.finished_rows(synth, "BTCUSDT", "1h") + LG.finished_rows_down(synth, "BTCUSDT", "1h")
    rows = H.load(state)["ledger"]["rows"]
    assert r["ledger_added"] == len(rows) == len(fin) and {LG.direction_of(x) for x in rows} == {"up", "down"}
    r2 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",),
               fetch_frame=_fetch_of(synth), pusher=_Pusher(), now=now)
    assert r2["ledger_added"] == 0                                            # 재실행 중복 없음
    out = str(tmp_path / "ledger.csv")
    assert P.export_ledger(state, out) == len(rows)
    lines = open(out, encoding="utf-8").read().splitlines()
    assert lines[0] == ",".join(LG.FIELDS) and len(lines) == len(rows) + 1
    # ledger 만 있는 셀 지정도 가능(대상 밖 TF 는 이벤트만)
    r3 = P.run(state_path=state, dry_run=True, token=None, symbols=("BTCUSDT",), intervals=("1h",), ledger_intervals=(),
               fetch_frame=_fetch_of(synth), pusher=_Pusher(), now=now)
    assert r3["ledger_added"] == 0


def test_run_cell_failure_is_isolated(synth, tmp_path):
    def fetch(sym, tf):
        if tf == "2d":
            raise RuntimeError("fetch down")
        return synth

    r = P.run(state_path=str(tmp_path / "s.json"), dry_run=True, token=None, symbols=("BTCUSDT",), intervals=("2d", "1h"),
              fetch_frame=fetch, pusher=_Pusher(), now=_now_after(synth))
    assert r["failures"] == ["BTCUSDT 2d: fetch down"] and r["events"] > 0


def test_legacy_state_file_is_moved_aside_and_new_history_starts_empty(tmp_path):
    state = tmp_path / "pushbullet_state.json"
    legacy = {"version": 1, "sent": {"BTCUSDT|1h|2026-09-01T00:00:00|stoch_db|대(20,10,10)": "2026-09-01T01:00:00+00:00"},
              "last_bar": {"BTCUSDT|1h": "2026-09-01T00:00:00"}}
    state.write_text(json.dumps(legacy), encoding="utf-8")
    assert P.is_legacy_state(legacy) and not P.is_legacy_state(H.empty())
    hist = P.load_history(str(state))
    assert hist == H.empty() and not state.exists()
    moved = tmp_path / "pushbullet_state.legacy.json"
    assert json.loads(moved.read_text(encoding="utf-8")) == legacy
    assert P.legacy_state_path(str(state)) == str(moved)
    # 예전 경로는 옮겨진 파일을 그대로 쓴다
    st = P.PushState(str(moved))
    assert st.was_sent(next(iter(legacy["sent"]))) and st.get_last_bar("BTCUSDT", "1h") == pd.Timestamp("2026-09-01")
    # 새 형식 파일은 그대로 읽힌다
    H.save(str(state), H.empty())
    assert P.load_history(str(state)) == H.empty() and state.exists()


# ------------------------------------------------------------ 6. 예전 경로 (--legacy-signals, 기본 꺼짐) — 기존 계약 그대로
def test_legacy_select_signals_lookback_then_catch_up(frame):
    signals = scan_alarm_signals(frame, include_candidates=True)
    assert signals and any(s.severity != SEV_CONFIRMED for s in signals)
    picked = P.select_signals(frame, signals, None, lookback_bars=50, include_candidates=False)
    cutoff = pd.Timestamp(frame.index[-50])
    assert picked and all(s.timestamp >= cutoff and s.severity == SEV_CONFIRMED for s in picked)
    last_bar = pd.Timestamp(frame.index[-10])
    after = P.select_signals(frame, signals, last_bar, lookback_bars=50, include_candidates=False)
    assert all(s.timestamp > last_bar for s in after)


def test_legacy_build_pushes_groups_by_bar_and_uses_panel_line_format(frame):
    signals = [s for s in scan_alarm_signals(frame, include_candidates=False)][-40:]
    pushes = P.build_pushes("BTCUSDT", "1h", frame, signals)
    assert pushes and [p["bar"] for p in pushes] == sorted(p["bar"] for p in pushes)
    bars = {}
    for s in signals:
        bars.setdefault(pd.Timestamp(s.timestamp), []).append(s)
    for push in pushes:
        group = bars[push["bar"]]
        assert push["title"].startswith("[WEH] BTCUSDT 1h · ") and "(KST)" in push["title"]
        body_lines = push["body"].split("\n")
        assert body_lines[:len(group)] == [format_signal_line(s) for s in group]
        assert len(push["keys"]) == len(group) and all(k.startswith("BTCUSDT|1h|") for k in push["keys"])


def _run_legacy(frame, state, pusher, **kw):
    now = pd.Timestamp(frame.index[-1]) + pd.Timedelta(minutes=30)
    return P.run_once([("SYN", "1h")], state, "tok", loader=lambda s, i: frame, pusher=pusher, now=now, **kw)


def test_legacy_run_once_dedupes_and_dry_run_and_failure(frame, tmp_path):
    sent = []
    pusher = lambda token, title, body: sent.append((token, title, body)) or True  # noqa: E731
    path = str(tmp_path / "state.legacy.json")
    first = _run_legacy(frame, P.PushState(path), pusher, lookback_bars=100)
    assert first["pushed"] > 0 and first["failed"] == 0 and len(sent) == first["pushed"]
    saved = json.load(open(path, encoding="utf-8"))
    assert saved["version"] == P.STATE_VERSION and saved["last_bar"]["SYN|1h"] == pd.Timestamp(frame.index[-2]).isoformat()
    second = _run_legacy(frame, P.PushState(path), pusher, lookback_bars=100)
    assert second["pushed"] == 0 and len(sent) == first["pushed"]
    dry = _run_legacy(frame, P.PushState(str(tmp_path / "d.json")), lambda *a: sent.append(a) or True, lookback_bars=100, dry_run=True)
    assert dry["pushed"] > 0 and not os.path.exists(str(tmp_path / "d.json"))
    fail = _run_legacy(frame, P.PushState(str(tmp_path / "f.json")), lambda *a: False, lookback_bars=100)
    assert fail["failed"] > 0 and json.load(open(str(tmp_path / "f.json"), encoding="utf-8"))["sent"] == {}
