"""notify 스캐너(main) → signal-alarm 이식 — events · history · ledger · plan (네트워크·Streamlit 런타임 없음).

main 의 tests/test_notify_scanner.py 중 전송 수단(텔레그램·vision fetch·워크플로)과 무관한 계약을 합성 프레임으로 옮겼다:
  1. 이벤트 = 검출 모듈 출력 그대로(재구현 없음) — 상승/하방 전환·쌍바닥 후보·구조 LL, known_pos 규칙.
  2. 메시지 형식(4종 고정 문구, "(미검증)", 권고 어휘 부재).
  3. plan: 전역 최초 실행(최근 2봉) · 종류별 첫 스캔 0건 · 발송 제외 종류(LL) · 중복 · 회전 창.
  4. history: 회전·kinds·왕복. ledger: 상승/하방 행(direction), 키 충돌 없음, since 이후만, CSV.
"""
import os
import re
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import display.divergence_flag as DV  # noqa: E402
import display.ma60_down_tracker as MD  # noqa: E402
import display.ma60_turn_tracker as MT  # noqa: E402
import display.trend_structure as TS  # noqa: E402
import validation.wave_ma60_turn_probe as probe  # noqa: E402
from notify import events as EV  # noqa: E402
from notify import history as H  # noqa: E402
from notify import ledger as LG  # noqa: E402
from notify import plan as PL  # noqa: E402
from test_ma60_down_tracker import _pipeline, _raw  # noqa: E402


# ------------------------------------------------------------ 픽스처 (합성, 1h)
@pytest.fixture(scope="module")
def pipe():
    return _pipeline(_raw(n=1600, seed=7))


@pytest.fixture(scope="module")
def events(pipe):
    return EV.scan_frame(pipe, "BTCUSDT", "1h")


# ------------------------------------------------------------ 1. 검출 import 소비 · 이벤트 = 모듈 출력
def test_port_is_verbatim_import_consumption_no_reimplementation():
    assert EV.MT is MT and EV.MD is MD and EV.TS is TS and EV.DV is DV and LG.MT is MT and LG.MD is MD and LG.DV is DV
    assert MD.up is MT and MT.probe is probe and MD.probe is probe
    src = open(EV.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "MT.track_candidates(" in src and "MD.track_candidates(" in src and "TS.analyze(" in src
    for banned in ("stoch_pivot", "compute_series_pivots", "find_swing_lows", "find_swing_highs", "np.roll",
                   "shift(", "rolling(", "extract_signals(", "\"MA60\"]", "stoch_db_kind", "pipe[\"low\"]"):
        assert banned not in src, banned
    for mod in (H, LG, PL):
        body = open(mod.__file__, encoding="utf-8").read()
        for banned in ("stoch_pivot", "compute_series_pivots", "find_swing", "np.roll", "rolling("):
            assert banned not in body, (mod.__name__, banned)
    assert EV.KINDS == ("ma60_turn", "ma60_down", "structure_ll", "stoch_db")


def test_events_equal_tracker_rows(pipe, events):
    turned = MT.track_candidates(pipe, recent_bars=len(pipe))
    turned = turned[turned[MT.LIFECYCLE_COL] == MT.STATUS_TURNED]      # 원 생애주기 — '이미 상방'(표 상태 해당 없음) 후보의 창 안 새 전환도 종전대로 발화
    got_turn = {e.ts for e in events if e.kind == EV.KIND_MA60_TURN}
    assert got_turn == set(pd.to_datetime(turned["전환 시각"])) and len(got_turn) >= 1
    down = MD.track_candidates(pipe, recent_bars=len(pipe))
    down = down[down[MD.LIFECYCLE_COL] == MD.STATUS_TURNED]
    got_down = {e.ts: e for e in events if e.kind == EV.KIND_MA60_DOWN}
    assert set(got_down) == set(pd.to_datetime(down["전환 시각"])) and len(got_down) >= 1
    for d in down.to_dict("records"):
        assert got_down[pd.Timestamp(d["전환 시각"])].fields["divergence"] == (d[MD.DOWN_DIVERGENCE_COL] == DV.YES)
    assert not (got_turn & set(got_down))                                   # 상승·하방 전환봉은 배타
    frame = MT.track_candidates(pipe, recent_bars=len(pipe))
    got_db = {e.ts for e in events if e.kind == EV.KIND_STOCH_DB}
    assert got_db == set(pd.to_datetime(frame["확정 시각"])) and len(got_db) >= 5
    for e in events:
        assert e.last_pos == len(pipe) - 1 and 0 <= e.known_pos <= e.last_pos
        if e.kind == EV.KIND_STRUCTURE_LL:
            assert e.known_pos == int(pipe.index.get_loc(e.ts)) + TS.PIVOT
        elif e.kind == EV.KIND_STOCH_DB:
            c = int(pipe.index.get_loc(e.ts))
            assert c <= e.known_pos <= c + probe.STOCH_LAG
        else:
            assert e.known_pos == int(pipe.index.get_loc(e.ts))


# ------------------------------------------------------------ 2. 메시지 형식 (main 문구 그대로)
def _turn_event(ts="2026-09-18 12:00", last_pos=100, known_pos=99, **over):
    f = {"confirm_ts": pd.Timestamp("2026-09-18 08:00"), "turn_ts": pd.Timestamp(ts), "bars": 1,
         "price": 80725.6, "pattern_low": 74967.97, "baseline": 74593.13}
    f.update(over)
    return EV.Event("BTCUSDT", "4h", EV.KIND_MA60_TURN, pd.Timestamp(ts), known_pos, last_pos, f)


def _down_event(ts="2026-09-18 12:00", last_pos=100, known_pos=99, divergence=True):
    return EV.Event("BTCUSDT", "4h", EV.KIND_MA60_DOWN, pd.Timestamp(ts), known_pos, last_pos, {
        "confirm_ts": pd.Timestamp("2026-09-18 08:00"), "turn_ts": pd.Timestamp(ts), "bars": 1,
        "price": 80725.6, "pattern_high": 84967.97, "divergence": divergence})


def _ll_event(ts="2026-09-19 00:00", last_pos=100, known_pos=99):
    return EV.Event("ETHUSDT", "1h", EV.KIND_STRUCTURE_LL, pd.Timestamp(ts), known_pos, last_pos, {
        "low_ts": pd.Timestamp(ts), "low": 4321.5, "prev_low": 4400.0, "pct": -1.784,
        "known_ts": pd.Timestamp("2026-09-19 03:00"), "base_low": 4100.25,
        "base_confirm_ts": pd.Timestamp("2026-09-15 20:00"), "state": TS.STATE_BROKEN})


def _db_event(ts="2026-09-21 04:00", last_pos=100, known_pos=100, **over):
    f = {"confirm_ts": pd.Timestamp(ts), "status": MT.STATUS_WAITING, "ma_now": "하방", "already_up": False,
         "divergence": False, "pattern_low": 74967.97, "baseline": 74593.13, "turn_ts": None, "bars": None, "obs_bars": 20}
    f.update(over)
    return EV.Event("BTCUSDT", "4h", EV.KIND_STOCH_DB, pd.Timestamp(ts), known_pos, last_pos, f)


def test_message_formats_match_main_scanner_wording():
    assert EV.format_message(_turn_event()).splitlines() == [
        "[BTCUSDT 4h] 60MA 상방 전환 발생 (미검증)",
        "쌍바닥 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)",
        "가격 80,726 · 패턴 저점 74,968 / 기준선 74,593",
        "다이버전스 없음",
    ]
    assert EV.format_message(_turn_event(divergence=True)).splitlines()[-1] == "다이버전스 있음"
    assert EV.format_message(_db_event()).splitlines() == [
        "[BTCUSDT 4h] 대파동 쌍바닥 후보 (미검증)",
        "확정 09-21 13:00 · 60MA 현재 하방 (전환 대기, 창 20봉)",
        "패턴 저점 74,968 / 기준선 74,593",
        "참고: 과거 계측상 후보의 약 60%는 60MA 전환 없이 소멸",
    ]
    assert EV.format_message(_db_event(divergence=True)).splitlines()[1] == "★ 상승 다이버전스"
    assert EV.format_message(_down_event()).splitlines() == [
        "[BTCUSDT 4h] 60MA 하방 전환 발생 (미검증)",
        "쌍봉 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)",
        "가격 80,726 · 패턴 고점 84,968 · 하락 다이버전스 있음",
        "참고: 현물 보유 시 관측용",
    ]
    assert EV.format_message(_down_event(divergence=False)).splitlines()[2].endswith("하락 다이버전스 없음")
    lines = EV.format_message(_ll_event()).splitlines()
    assert lines[0] == "[ETHUSDT 1h] 구조 훼손 — 저점 LL 발생 (미검증)"
    assert lines[1] == "저점 09-19 09:00 4,322 < 직전 저점 4,400 (-1.78%) · 확정 09-19 12:00"
    assert _down_event().key == "BTCUSDT|4h|ma60_down|2026-09-18T12:00:00Z" and _down_event().key != _turn_event().key


def test_messages_carry_unverified_and_no_recommendation_words(events):
    for e in list(events) + [_turn_event(), _down_event(), _ll_event(), _db_event(), _db_event(divergence=True)]:
        msg = EV.format_message(e)
        assert "(미검증)" in msg.splitlines()[0]
        for w in EV.FORBIDDEN_WORDS:
            assert w not in msg, (w, msg)
        assert re.search(r"\d{2}-\d{2} \d{2}:\d{2}", msg)


# ------------------------------------------------------------ 3. plan — 폭탄 방지 2단 · 발송 제외 · 중복 · 회전 창
def _kinds_seen(hist: dict, now="2026-09-01 00:00") -> dict:
    for k in EV.KINDS:
        H.mark_kind(hist, k, now=pd.Timestamp(now))
    return hist


def test_plan_global_initial_run_sends_only_recent_two_bars():
    now = pd.Timestamp("2026-09-19 12:00")
    evs = [_turn_event("2026-09-19 08:00", last_pos=100, known_pos=100),
           _turn_event("2026-09-19 04:00", last_pos=100, known_pos=99),
           _turn_event("2026-09-19 00:00", last_pos=100, known_pos=98),
           _turn_event("2026-09-10 00:00", last_pos=100, known_pos=50)]
    acts = {e.ts: a for e, a in PL.plan(evs, _kinds_seen(H.empty()), now)}
    assert acts[pd.Timestamp("2026-09-19 08:00")] == PL.ACT_SEND and acts[pd.Timestamp("2026-09-19 04:00")] == PL.ACT_SEND
    assert acts[pd.Timestamp("2026-09-19 00:00")] == PL.ACT_RECORD_ONLY and acts[pd.Timestamp("2026-09-10 00:00")] == PL.ACT_RECORD_ONLY
    # 기록만 쌓인 이력(발송 성공 0건)도 최초 실행 모드 — 토큰 투입 순간 밀린 이벤트가 쏟아지지 않는다
    hist = H.empty()
    H.record(hist, "X|1h|ma60_turn|2026-09-18T00:00:00Z", "2026-09-18 00:00", delivered=False, now=now)
    assert not H.is_empty(hist) and H.nothing_delivered(hist)


def test_plan_new_kind_first_scan_sends_nothing_then_only_new():
    now = pd.Timestamp("2026-09-19 12:00")
    hist = H.empty()
    H.record(hist, "Y|1h|ma60_turn|2026-09-18T04:00:00Z", "2026-09-18 04:00", delivered=True, now=now)
    assert not H.nothing_delivered(hist)                                    # 전역 최초 실행 모드 아님
    assert H.kind_seen(hist, EV.KIND_MA60_TURN) and not H.kind_seen(hist, EV.KIND_MA60_DOWN)   # sent 키의 kind 조각으로 인정
    evs = [_down_event("2026-09-19 08:00", known_pos=100), _down_event("2026-09-19 00:00", known_pos=98),
           _turn_event("2026-09-19 08:00", known_pos=100)]
    acts = {(e.kind, e.ts): a for e, a in PL.plan(evs, hist, now)}
    assert all(a == PL.ACT_NEW_KIND for (k, _), a in acts.items() if k == EV.KIND_MA60_DOWN)
    assert acts[(EV.KIND_MA60_TURN, pd.Timestamp("2026-09-19 08:00"))] == PL.ACT_SEND
    for e, a in PL.plan(evs, hist, now):                                     # 실행 끝: 기록 + kinds
        if a == PL.ACT_NEW_KIND:
            H.record(hist, e.key, e.ts, delivered=False, now=now)
    H.mark_kind(hist, EV.KIND_MA60_DOWN, now=now)
    evs2 = evs + [_down_event("2026-09-19 12:00", known_pos=101, last_pos=101)]
    acts2 = {(e.kind, e.ts): a for e, a in PL.plan(evs2, hist, now + pd.Timedelta(hours=4))}
    assert acts2[(EV.KIND_MA60_DOWN, pd.Timestamp("2026-09-19 12:00"))] == PL.ACT_SEND
    assert acts2[(EV.KIND_MA60_DOWN, pd.Timestamp("2026-09-19 08:00"))] == PL.ACT_DUP


def test_plan_disabled_kind_records_only_and_is_revivable():
    assert PL.SEND_DISABLED_KINDS == frozenset({EV.KIND_STRUCTURE_LL}) and EV.KIND_STRUCTURE_LL in EV.KINDS
    now = pd.Timestamp("2026-09-19 12:00")
    hist = _kinds_seen(H.empty())
    H.record(hist, "X|1h|ma60_turn|2026-09-01T00:00:00Z", "2026-09-01 00:00", delivered=True, now=now)
    ll, turn = _ll_event(ts="2026-09-19 00:00", known_pos=99), _turn_event(ts="2026-09-19 08:00")
    acts = {e.kind: a for e, a in PL.plan([ll, turn], hist, now)}
    assert acts[EV.KIND_STRUCTURE_LL] == PL.ACT_DISABLED and acts[EV.KIND_MA60_TURN] == PL.ACT_SEND
    assert {a for _, a in PL.plan([ll], hist, now, disabled_kinds=())} == {PL.ACT_SEND}     # 되살림 경로
    hist["sent"][ll.key] = {"event_ts": "2026-09-19T00:00:00Z", "sent_at": None, "delivered": False}
    assert PL.plan([ll], hist, now)[0][1] == PL.ACT_DUP                                      # dup 이 먼저


def test_plan_dup_same_key_once_and_scan_window():
    now = pd.Timestamp("2026-09-19 12:00")
    hist = _kinds_seen(H.empty())
    H.record(hist, "X|1h|ma60_turn|2026-09-01T00:00:00Z", "2026-09-01 00:00", delivered=True, now=now)
    a, b = _turn_event("2026-09-19 08:00"), _turn_event("2026-09-19 08:00", known_pos=98)
    acts = [act for _, act in PL.plan([a, b], hist, now)]
    assert acts.count(PL.ACT_SEND) == 1 and acts.count(PL.ACT_DUP) == 1
    H.record(hist, a.key, a.ts, delivered=True, now=now)
    evs = [_turn_event("2026-09-19 08:00"), _turn_event("2026-09-10 00:00", known_pos=50), _turn_event("2026-08-01 00:00", known_pos=1)]
    acts = {e.ts: act for e, act in PL.plan(evs, hist, now)}
    assert acts[pd.Timestamp("2026-09-19 08:00")] == PL.ACT_DUP
    assert acts[pd.Timestamp("2026-09-10 00:00")] == PL.ACT_SEND            # 이력 있음 → 2봉 제한 없음
    assert acts[pd.Timestamp("2026-08-01 00:00")] == PL.ACT_OLD             # 회전 창 밖


# ------------------------------------------------------------ 4. history · ledger
def test_history_rotation_kinds_and_roundtrip(tmp_path):
    assert H.SCAN_MAX_AGE_DAYS < H.RETENTION_DAYS == 30 and H.INITIAL_RECENT_BARS == 2
    now = pd.Timestamp("2026-09-20 00:00")
    hist = H.empty()
    H.record(hist, "A|1h|ma60_turn|2026-08-01T00:00:00Z", "2026-08-01 00:00", delivered=True, now=now)
    H.record(hist, "B|1h|ma60_turn|2026-09-01T00:00:00Z", "2026-09-01 00:00", delivered=False, now=now)
    assert H.rotate(hist, now) == 1 and list(hist["sent"]) == ["B|1h|ma60_turn|2026-09-01T00:00:00Z"]
    p = tmp_path / "state.json"
    H.mark_kind(hist, "ma60_down", now=now)
    H.save(str(p), hist)
    loaded = H.load(str(p))
    assert loaded["sent"] == hist["sent"] and loaded["kinds"] == {"ma60_down": "2026-09-20T00:00:00Z"}
    assert loaded["ledger"] == {"since": None, "rows": []}
    assert H.rotate(hist, now + pd.Timedelta(days=400)) == 1 and hist["kinds"] == {"ma60_down": "2026-09-20T00:00:00Z"}


def test_ledger_rows_up_and_down_with_direction_and_no_key_collision(pipe):
    up_rows = LG.finished_rows(pipe, "BTCUSDT", "1h")
    dn_rows = LG.finished_rows_down(pipe, "BTCUSDT", "1h")
    assert len(up_rows) >= 3 and len(dn_rows) >= 3
    assert all("direction" not in r for r in up_rows) and all(r["direction"] == "down" for r in dn_rows)
    assert set(up_rows[0]) == set(LG.FIELDS) - {"recorded_at", "direction", "pattern_high", "already_down"}
    assert set(dn_rows[0]) == set(LG.FIELDS) - {"recorded_at", "pattern_low", "already_up"}
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))
    frame = MT.track_candidates(pipe, recent_bars=len(pipe))
    by_ts = {pd.Timestamp(d["확정 시각"]).strftime("%Y-%m-%dT%H:%M:%SZ"): d for d in frame.to_dict("records")}
    for r in up_rows:
        assert r["divergence"] == flags[int(by_ts[r["confirm_ts"]]["_confirm_pos"])]
    # '이미 상방' 후보도 원 생애주기(LIFECYCLE_COL)로 그대로 기록 — 표 상태 '해당 없음' 과 무관, already_up 필드로 구분(기록 불변)
    done = frame[frame[MT.LIFECYCLE_COL].isin([MT.STATUS_TURNED, MT.STATUS_EXPIRED])]
    assert len(up_rows) == len(done) >= 1
    already_ts = {pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ") for t in done.loc[done["상태"] == MT.STATUS_ALREADY_UP, "확정 시각"]}
    assert {r["confirm_ts"] for r in up_rows if r["already_up"]} == already_ts
    down = MD.track_candidates(pipe, recent_bars=len(pipe))
    by_dn = {pd.Timestamp(d["확정 시각"]).strftime("%Y-%m-%dT%H:%M:%SZ"): d for d in down.to_dict("records")}
    for r in dn_rows:
        assert r["divergence"] == (by_dn[r["confirm_ts"]][MD.DOWN_DIVERGENCE_COL] == DV.YES)
        assert r["pattern_high"] == float(by_dn[r["confirm_ts"]][MD.HIGH_COL])
    up = {"symbol": "X", "tf": "1h", "confirm_ts": "2026-09-22T00:00:00Z", "result": "expired", "divergence": False}
    dn = {**up, "direction": "down", "pattern_high": 1.0, "already_down": False}
    assert LG.key_of(up) == "X|1h|2026-09-22T00:00:00Z" and LG.key_of(dn) == "X|1h|2026-09-22T00:00:00Z|down"
    hist = H.empty()
    assert H.ledger_append(hist, [up]) == 0                                      # since 없으면 기록 없음
    H.ledger_init(hist, now=pd.Timestamp("2026-09-22 00:00"))
    old = {**up, "confirm_ts": "2026-09-21T23:00:00Z"}                             # since 이전 → 제외(과거 소급 금지)
    assert H.ledger_append(hist, [up, dn, old], now=pd.Timestamp("2026-09-23 00:00")) == 2
    assert H.ledger_append(hist, [up, dn], now=pd.Timestamp("2026-09-23 00:00")) == 0
    csv_lines = LG.to_csv(hist["ledger"]["rows"]).splitlines()
    assert csv_lines[0] == ",".join(LG.FIELDS)
    assert [ln.split(",")[LG.FIELDS.index("direction")] for ln in csv_lines[1:]] == ["up", "down"]
    assert sum(v for d in LG.summary(up_rows + dn_rows).values() for v in d.values()) == len(up_rows)
    assert sum(v for d in LG.summary(up_rows + dn_rows, direction="down").values() for v in d.values()) == len(dn_rows)
