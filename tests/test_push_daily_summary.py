"""일일 요약 알림(scripts/push_alarms) — 시각 판정(00:00 UTC 경계 · 늦은 기동 시 당일 1회 · 중복 방지) · 내용 형식 · run 통합. 네트워크 없음."""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import display.ma60_turn_tracker as MT  # noqa: E402
from notify import events as EV  # noqa: E402
from notify import history as H  # noqa: E402
from scripts import push_alarms as P  # noqa: E402
from test_ma60_down_tracker import _pipeline, _raw  # noqa: E402

FORBIDDEN = tuple(EV.FORBIDDEN_WORDS) + ("중요", "주목", "유망", "추천", "권고")


# ------------------------------------------------------------ 시각 판정
def test_due_first_cycle_after_00_utc_once_per_day_and_late_boot():
    hist = H.empty()
    assert P.daily_key(pd.Timestamp("2026-09-23 00:01")) == "2026-09-23"
    # 09:00 KST = 00:00 UTC 경계: 23:59 UTC 는 전날 키, 00:00 UTC 부터 새 날 키
    assert P.daily_key(pd.Timestamp("2026-09-22 23:59")) == "2026-09-22" and P.daily_key(pd.Timestamp("2026-09-23 00:00")) == "2026-09-23"
    # 전날 보냈으면 00:01 UTC(09:01 KST) 첫 순회에 due
    P.mark_daily_summary(hist, pd.Timestamp("2026-09-22 00:01"))
    assert hist["daily"] == {"last_date": "2026-09-22", "sent_at": "2026-09-22T00:01:00Z"}
    assert not P.daily_summary_due(hist, pd.Timestamp("2026-09-22 23:59"))          # 같은 날(UTC) 두 번 없음
    assert P.daily_summary_due(hist, pd.Timestamp("2026-09-23 00:01"))
    # 서버가 꺼져 있다 늦게 켜져도(예: 15:36 UTC = 00:36 KST 다음날 새벽) 그날 첫 순회에 1회
    assert P.daily_summary_due(hist, pd.Timestamp("2026-09-23 15:36"))
    P.mark_daily_summary(hist, pd.Timestamp("2026-09-23 15:36"))
    assert not P.daily_summary_due(hist, pd.Timestamp("2026-09-23 15:41")) and not P.daily_summary_due(hist, pd.Timestamp("2026-09-23 23:59"))
    assert P.daily_summary_due(hist, pd.Timestamp("2026-09-24 00:01"))
    # 이력 파일 왕복에 daily 가 보존된다
    assert H.empty()["daily"] == {}


def test_daily_field_survives_save_load(tmp_path):
    hist = H.empty()
    P.mark_daily_summary(hist, pd.Timestamp("2026-09-23 00:01"))
    p = str(tmp_path / "s.json")
    H.save(p, hist)
    assert H.load(p)["daily"] == {"last_date": "2026-09-23", "sent_at": "2026-09-23T00:01:00Z"}


# ------------------------------------------------------------ 내용 형식
def _turn(tf, ts, kind=EV.KIND_MA60_TURN, divergence=False):
    return EV.Event("BTCUSDT", tf, kind, pd.Timestamp(ts), 100, 100, {
        "confirm_ts": pd.Timestamp(ts) - pd.Timedelta(hours=4), "turn_ts": pd.Timestamp(ts), "bars": 1, "price": 1.0,
        "pattern_low": 1.0, "baseline": 1.0, "pattern_high": 1.0, "divergence": divergence})


def _snap(tf, ma="↑", waiting=()):
    return {"symbol": "BTCUSDT", "tf": tf, "ma60_dir": ma,
            "waiting": [{"elapsed": f"{b}/20", "bars": b, "divergence": d} for b, d in waiting]}


NOW = pd.Timestamp("2026-09-23 00:01")     # 09:01 KST


def test_headline_priority_turn_then_waiting_then_none():
    snaps = [_snap(tf) for tf in P.PUSH_TARGETS["intervals"]]
    # ① 지난 24h 전환 — 어제 21:00 KST = 09-22 12:00 UTC
    ev = _turn("4h", "2026-09-22 12:00", divergence=True)
    assert P.headline([ev], snaps, NOW) == "볼 TF: 4h — 60MA 상방 전환 (어제 21:00, 다이버전스 있음)"
    down = _turn("1d", "2026-09-22 04:00", kind=EV.KIND_MA60_DOWN)          # 어제 13:00 KST (24h 안)
    assert P.headline([ev, down], snaps, NOW) == ("볼 TF: 1d, 4h — 1d: 60MA 하방 전환 (어제 13:00, 하락 다이버전스 없음) · "
                                                  "4h: 60MA 상방 전환 (어제 21:00, 다이버전스 있음)")   # 긴 TF부터, 종류 병기
    # 24h 밖의 전환(경계: 09-22 00:01 UTC 이전)은 ①에 들지 않는다 → ② 로
    assert P.headline([_turn("1d", "2026-09-22 00:00")], [_snap("1h")], NOW) == "특이 사항 없음"
    old = _turn("2h", "2026-09-21 23:00")
    snaps2 = [_snap("4h", waiting=((7, True),)), _snap("1d", waiting=((2, False),)), _snap("1h")]
    assert P.headline([old], snaps2, NOW) == "볼 TF: 1d, 4h — 후보 대기 중 (1d 2/20 · 4h 7/20 ★)"
    assert P.headline([], [_snap("1d", waiting=((2, False),))], NOW) == "볼 TF: 1d — 후보 대기 중 (경과 2/20)"
    assert P.headline([], [_snap("4h", waiting=((7, True), (3, False)))], NOW) == "볼 TF: 4h — 후보 대기 중 (경과 7/20, 다이버전스 있음)"  # ★ 우선
    assert P.headline([], [_snap("4h", waiting=((9, False), (3, False)))], NOW) == "볼 TF: 4h — 후보 대기 중 (경과 3/20)"        # 경과 짧은 순
    # ③
    assert P.headline([], snaps, NOW) == "특이 사항 없음"
    # 시각 라벨: 오늘/어제/그 외
    assert P._when_label(pd.Timestamp("2026-09-22 16:00"), NOW) == "오늘 01:00"
    assert P._when_label(pd.Timestamp("2026-09-20 03:00"), NOW) == "09-20 12:00"
    assert P.tf_seconds("2d") == 2 * 86400 and P.tf_seconds("12h") == 43200 and P.tf_seconds("2h") < P.tf_seconds("4h")


def test_summary_body_format_and_no_evaluative_words():
    hist = H.empty()
    hist["sent"] = {
        "BTCUSDT|4h|stoch_db|2026-09-22T08:00:00Z": {"event_ts": "2026-09-22T08:00:00Z", "sent_at": "2026-09-22T12:01:00Z", "delivered": True},
        "BTCUSDT|1h|ma60_down|2026-09-22T20:00:00Z": {"event_ts": "2026-09-22T20:00:00Z", "sent_at": "2026-09-22T21:01:00Z", "delivered": True},
        "BTCUSDT|1h|ma60_turn|2026-09-10T20:00:00Z": {"event_ts": "2026-09-10T20:00:00Z", "sent_at": "2026-09-10T21:01:00Z", "delivered": True},  # 24h 밖
        "BTCUSDT|1h|structure_ll|2026-09-22T20:00:00Z": {"event_ts": "2026-09-22T20:00:00Z", "sent_at": None, "delivered": False},  # 기록만
    }
    snaps = [_snap("1h"), _snap("2h"), _snap("4h", waiting=((7, True),)), _snap("6h"), _snap("12h"), _snap("1d", waiting=((2, False),)),
             _snap("2d", ma="↓")]
    ev = _turn("4h", "2026-09-22 12:00", divergence=True)
    text = P.build_daily_summary([ev], snaps, hist, NOW, n_cells=7, failures=[])
    assert text.splitlines() == [
        "볼 TF: 4h — 60MA 상방 전환 (어제 21:00, 다이버전스 있음)",
        "지난 24h 발송: 후보 1 · 상방 0 · 하방 1",
        "대기 중: 4h(7/20, ★) · 1d(2/20)",
        "60MA: 1h↑ 2h↑ 4h↑ 6h↑ 12h↑ 1d↑ 2d↓",
        "스캐너 정상 · 마지막 순회 09:01 · 7셀 OK",
    ]
    assert P.daily_summary_title(NOW) == "[WEH] 일일 요약 09-23 (미검증)"
    for w in FORBIDDEN:
        assert w not in text and w not in P.daily_summary_title(NOW), w
    # 사건 없음 · 실패 셀
    none = P.build_daily_summary([], [_snap("1h")], H.empty(), NOW, n_cells=7, failures=["BTCUSDT 2d: x"])
    assert none.splitlines()[0] == "특이 사항 없음" and none.splitlines()[2] == "대기 중: 없음"
    assert none.splitlines()[-1] == "스캐너 오류 1셀 · 마지막 순회 09:01 · 6셀 OK"


# ------------------------------------------------------------ run 통합 — dry-run 샘플 · 발송 1회 · 실패 재시도
@pytest.fixture(scope="module")
def synth():
    return _pipeline(_raw(n=1600, seed=7))


class _Pusher:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def __call__(self, token, title, body):
        self.calls.append((token, title, body))
        return self.ok


def _kinds_seen(hist):
    for k in EV.KINDS:
        H.mark_kind(hist, k, now=pd.Timestamp("2020-01-01"))
    return hist


def test_cell_snapshot_reads_tracker_waiting_rows_and_ma60_direction(synth):
    snap = P.cell_snapshot(synth, "BTCUSDT", "1h")
    frame = MT.track_candidates(synth)
    waiting = frame[frame["상태"] == MT.STATUS_WAITING]
    assert snap["tf"] == "1h" and len(snap["waiting"]) == len(waiting)
    assert snap["ma60_dir"] in ("↑", "↓", "→")
    ma = synth["MA60"]
    assert snap["ma60_dir"] == ("↑" if ma.iloc[-1] > ma.iloc[-2] else "↓" if ma.iloc[-1] < ma.iloc[-2] else "→")
    for w, d in zip(snap["waiting"], waiting.to_dict("records")):
        assert w["elapsed"] == d[MT.ELAPSED_COL] and w["bars"] == int(d["_bars"])


def test_run_dry_run_prints_sample_and_real_run_sends_once_per_day_and_retries_on_failure(synth, tmp_path, caplog):
    state = str(tmp_path / "s.json")
    hist = _kinds_seen(H.empty())
    H.record(hist, "SEED|1h|ma60_turn|2026-01-01T00:00:00Z", "2026-01-01 00:00", delivered=True, now=pd.Timestamp("2026-01-01"))
    H.save(state, hist)
    now = pd.Timestamp(synth.index[-1]) + pd.Timedelta(hours=1)
    fetch = lambda sym, tf: synth  # noqa: E731
    # dry-run: 요약 샘플 1건 출력, 기록 없음
    with caplog.at_level("INFO", logger="push_alarms"):
        r = P.run(state_path=state, dry_run=True, token=None, symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
                  pusher=_Pusher(), now=now)
    assert r["daily_summary"] and not r["daily_summary_sent"] and "daily summary sample" in caplog.text
    assert H.load(state)["daily"] == {}
    lines = r["daily_summary"].splitlines()
    assert len(lines) == 5 and lines[1].startswith("지난 24h 발송: 후보 ") and lines[3].startswith("60MA: 1h") and "1셀 OK" in lines[4]
    # 실제 실행: 그날 첫 순회에 1회 발송·기록, 같은 날 재순회에는 없음
    pusher = _Pusher()
    r1 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
               pusher=pusher, now=now)
    titles = [t for _, t, _ in pusher.calls]
    assert r1["daily_summary_sent"] and titles.count(P.daily_summary_title(now)) == 1
    assert H.load(state)["daily"]["last_date"] == P.daily_key(now)
    body = [b for _, t, b in pusher.calls if t == P.daily_summary_title(now)][0]
    assert body == r1["daily_summary"] and len(body.splitlines()) == 5
    r2 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
               pusher=pusher, now=now + pd.Timedelta(minutes=5))
    assert not r2["daily_summary_sent"] and r2["daily_summary"] is None and titles.count(P.daily_summary_title(now)) == 1
    # 다음 날(UTC) 첫 순회: 발송 실패면 기록하지 않아 그날 다음 순회에 재시도
    nxt = now.normalize() + pd.Timedelta(days=1, minutes=1)
    bad = _Pusher(ok=False)
    r3 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
               pusher=bad, now=nxt)
    assert not r3["daily_summary_sent"] and H.load(state)["daily"]["last_date"] == P.daily_key(now)
    good = _Pusher()
    r4 = P.run(state_path=state, dry_run=False, token="tok", symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
               pusher=good, now=nxt + pd.Timedelta(minutes=5))
    assert r4["daily_summary_sent"] and H.load(state)["daily"]["last_date"] == P.daily_key(nxt)
    # 토큰 없으면 보내지 않고 기록도 없다(다음 순회 재시도)
    r5 = P.run(state_path=state, dry_run=False, token=None, symbols=("BTCUSDT",), intervals=("1h",), fetch_frame=fetch,
               pusher=good, now=nxt + pd.Timedelta(days=1))
    assert not r5["daily_summary_sent"] and H.load(state)["daily"]["last_date"] == P.daily_key(nxt)
