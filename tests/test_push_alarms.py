"""알람 Pushbullet 푸시 — notify/pushbullet + scripts/push_alarms 단위·스모크 (네트워크 없음).

확인하는 계약:
  1. 토큰: 저장소 홈 token.txt 첫 줄, 없거나 비면 None. .gitignore 에 token.txt·이력 파일이 있다.
  2. push_note: /v2/pushes 에 Access-Token 헤더 + note JSON, 2xx 만 True, 예외·비 2xx 는 False(폴러가 죽지 않음).
  3. 닫힌 봉만: 마지막 봉이 진행 중이면 뺀다.
  4. 선별: 이력 없으면 최근 lookback 봉, 이력 있으면 마지막 처리 봉 이후(따라잡기), 기본 확정만.
  5. 묶음·형식: 같은 봉 신호는 푸시 1건, 줄 형식은 알람 탭 format_signal_line 그대로, 제목에 KST.
  6. 중복 방지: 같은 데이터로 두 번 돌려도 두 번째는 전송 0. dry-run 은 전송·이력 기록 없음. 전송 실패는 이력에 안 남음.
"""
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from analysis.alarm_signals import SEV_CONFIRMED, scan_alarm_signals  # noqa: E402
from display.alarm_panel import format_signal_line  # noqa: E402
from notify import pushbullet as PB  # noqa: E402
from scripts import push_alarms as P  # noqa: E402
from test_slim_app_smoke import _pipeline_frame  # noqa: E402


@pytest.fixture(scope="module")
def frame():
    return _pipeline_frame()


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
    assert "token.txt" in lines and "pushbullet_state.json" in lines


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


# ------------------------------------------------------------ 3. 닫힌 봉
def test_closed_frame_drops_open_last_bar(frame):
    last = pd.Timestamp(frame.index[-1])
    assert P.interval_delta("1h") == pd.Timedelta(hours=1) and P.interval_delta("1d") == pd.Timedelta(days=1)
    assert P.interval_delta("6h") == pd.Timedelta(hours=6)
    open_now = last + pd.Timedelta(minutes=59)
    assert len(P.closed_frame(frame, "1h", open_now)) == len(frame) - 1
    closed_now = last + pd.Timedelta(hours=1)
    assert len(P.closed_frame(frame, "1h", closed_now)) == len(frame)
    assert P.closed_frame(None, "1h", closed_now) is None
    with pytest.raises(ValueError):
        P.interval_delta("2d")   # 커스텀 TF 미지원(닫힌 봉 판정 불가)


# ------------------------------------------------------------ 4. 선별
def test_select_signals_lookback_then_catch_up(frame):
    signals = scan_alarm_signals(frame, include_candidates=True)
    assert signals and any(s.severity != SEV_CONFIRMED for s in signals)
    # 이력 없음 → 최근 lookback 봉, 확정만
    picked = P.select_signals(frame, signals, None, lookback_bars=50, include_candidates=False)
    cutoff = pd.Timestamp(frame.index[-50])
    assert picked and all(s.timestamp >= cutoff and s.severity == SEV_CONFIRMED for s in picked)
    # 후보 포함
    with_c = P.select_signals(frame, signals, None, lookback_bars=50, include_candidates=True)
    assert len(with_c) >= len(picked)
    # 이력 있음 → 마지막 처리 봉 "이후" 만 (같은 봉은 제외)
    last_bar = pd.Timestamp(frame.index[-10])
    after = P.select_signals(frame, signals, last_bar, lookback_bars=50, include_candidates=False)
    assert all(s.timestamp > last_bar for s in after)


# ------------------------------------------------------------ 5. 묶음 · 형식
def test_build_pushes_groups_by_bar_and_uses_panel_line_format(frame):
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
        assert body_lines[-1].startswith("종가 ")
        assert len(push["keys"]) == len(group) and len(set(push["keys"])) == len(group)
        assert all(k.startswith("BTCUSDT|1h|") for k in push["keys"])


# ------------------------------------------------------------ 6. run_once · 중복 방지 · dry-run · 실패
def _run(frame, state, pusher, **kw):
    now = pd.Timestamp(frame.index[-1]) + pd.Timedelta(minutes=30)     # 마지막 봉 진행 중
    return P.run_once([("SYN", "1h")], state, "tok", loader=lambda s, i: frame, pusher=pusher, now=now, **kw)


def test_run_once_dedupes_across_runs_and_persists_state(frame, tmp_path):
    sent = []
    pusher = lambda token, title, body: sent.append((token, title, body)) or True  # noqa: E731
    path = str(tmp_path / "state.json")
    first = _run(frame, P.PushState(path), pusher, lookback_bars=100)
    assert first["pushed"] > 0 and first["failed"] == 0 and len(sent) == first["pushed"]
    assert all(t == "tok" for t, _, _ in sent)
    saved = json.load(open(path, encoding="utf-8"))
    assert saved["version"] == P.STATE_VERSION and saved["last_bar"]["SYN|1h"] == pd.Timestamp(frame.index[-2]).isoformat()
    assert len(saved["sent"]) >= first["pushed"]
    # 같은 데이터 재실행 → 전송 0
    second = _run(frame, P.PushState(path), pusher, lookback_bars=100)
    assert second["pushed"] == 0 and len(sent) == first["pushed"]
    # 이력의 마지막 봉만 20봉 전으로 되돌리면(폴러 휴지) 그 뒤 봉의 신호만 따라잡는다 — sent 키는 그대로라 중복 생략
    state = P.PushState(path)
    state.set_last_bar("SYN", "1h", frame.index[-22])
    third = _run(frame, state, pusher, lookback_bars=100)
    assert third["pushed"] == 0 and third["skipped"] > 0
    state = P.PushState(path)
    state.sent = {}
    state.set_last_bar("SYN", "1h", frame.index[-22])
    fourth = _run(frame, state, pusher, lookback_bars=100)
    closed = frame.iloc[:-1]
    expected_bars = {s.timestamp for s in scan_alarm_signals(closed, include_candidates=False)
                     if s.timestamp > pd.Timestamp(frame.index[-22])}
    assert 0 < fourth["pushed"] == len(expected_bars) < first["pushed"]


def test_run_once_dry_run_sends_nothing_and_keeps_no_state(frame, tmp_path):
    sent = []
    path = str(tmp_path / "state.json")
    stats = _run(frame, P.PushState(path), lambda *a: sent.append(a) or True, lookback_bars=100, dry_run=True)
    assert stats["pushed"] > 0 and sent == [] and not os.path.exists(path)


def test_run_once_failed_push_is_not_marked_sent(frame, tmp_path):
    path = str(tmp_path / "state.json")
    stats = _run(frame, P.PushState(path), lambda *a: False, lookback_bars=100)
    assert stats["failed"] > 0 and stats["pushed"] == 0
    saved = json.load(open(path, encoding="utf-8"))
    assert saved["sent"] == {}                       # 실패한 신호는 다음 순회에 다시 시도된다
    retry = _run(frame, P.PushState(path), lambda *a: True, lookback_bars=100)
    assert retry["pushed"] == 0                       # 단, last_bar 는 갱신됐으므로 같은 봉은 다시 보지 않는다


def test_run_once_loader_error_is_isolated(frame, tmp_path):
    def loader(symbol, interval):
        if symbol == "BAD":
            raise RuntimeError("fetch down")
        return frame

    sent = []
    now = pd.Timestamp(frame.index[-1]) + pd.Timedelta(minutes=30)
    stats = P.run_once([("BAD", "1h"), ("SYN", "1h")], P.PushState(str(tmp_path / "s.json")), "tok",
                       loader=loader, pusher=lambda *a: sent.append(a) or True, now=now, lookback_bars=100)
    assert stats["errors"] and stats["errors"][0].startswith("BAD 1h") and stats["pushed"] == len(sent) > 0


def test_cli_parse_defaults_from_config():
    from config.settings import PUSH_PARAMS, PUSH_WATCHLIST
    args = P.parse_args([])
    assert args.loop is None and not args.test and not args.dry_run
    assert args.token == os.path.join(ROOT, PUSH_PARAMS["token_file"]) and args.state == os.path.join(ROOT, PUSH_PARAMS["state_file"])
    assert PUSH_WATCHLIST["symbols"] == ["BTCUSDT"] and PUSH_WATCHLIST["intervals"] == ["1h", "2h", "4h", "6h", "1d"]
    args = P.parse_args(["--loop", "60", "--symbols", "ETHUSDT", "--intervals", "4h", "--include-candidates", "--dry-run"])
    assert args.loop == 60 and args.symbols == ["ETHUSDT"] and args.intervals == ["4h"] and args.include_candidates and args.dry_run
