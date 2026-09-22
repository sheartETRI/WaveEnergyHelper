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
import display.divergence_flag as DV  # noqa: E402
import display.ma60_down_tracker as MD  # noqa: E402
import notify.ledger as LG  # noqa: E402
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
                                      "display/trend_structure.py", "validation/wave_ma60_turn_probe.py",
                                      "display/ma60_down_tracker.py", "display/divergence_flag.py"}
    missing = []
    src_of = {"display/ma60_down_tracker.py": notify.CHERRYPICK_SOURCE_COMMIT_DOWN,
              "display/divergence_flag.py": notify.CHERRYPICK_SOURCE_COMMIT_DIV}
    for rel, sha in notify.CHERRYPICK.items():
        local = _norm(open(os.path.join(ROOT, rel), "rb").read())
        assert hashlib.sha256(local).hexdigest() == sha, f"{rel} 가 매니페스트와 다르다 (내용 무변경 원칙)"
        src = src_of.get(rel, notify.CHERRYPICK_SOURCE_COMMIT)
        blob = _git_show(f"{src}:{rel}")
        if blob is None:
            missing.append(rel)
            continue
        assert _norm(blob) == local, f"{rel} 가 원본 커밋 {src} 과 diff 있음"
    if missing:
        pytest.skip(f"git 또는 원본 커밋을 읽을 수 없음 — 매니페스트 해시로만 확인: {missing}")
    # 트래커 자체의 probe 매니페스트와도 일치(양 브랜치 같은 blob)
    assert MT.CHERRYPICK_PROBE["validation/wave_ma60_turn_probe.py"] == notify.CHERRYPICK["validation/wave_ma60_turn_probe.py"]


def test_detection_is_imported_not_reimplemented():
    assert EV.MT is MT and EV.MD is MD and EV.TS is TS and TS.probe is probe and MT.probe is probe and MD.probe is probe
    assert EV.DV is DV and LG.DV is DV and LG.MT is MT and DV.probe is probe
    assert MD.up is MT                                      # 하방 추적은 상승 쪽 모듈(창·경과 규칙)을 import 소비
    src = open(EV.__file__, encoding="utf-8").read().split('"""', 2)[2]
    assert "MT.track_candidates(" in src and "MD.track_candidates(" in src and "TS.analyze(" in src
    for banned in ("stoch_pivot", "compute_series_pivots", "find_swing_lows", "find_swing_highs", "np.roll",
                   "shift(", "rolling(", "extract_signals(", "\"MA60\"]", "stoch_db_kind", "pipe[\"low\"]"):
        assert banned not in src, banned
    # 스캐너 패키지 어디에도 검출기·지표 계산 없음
    for fn in ("scanner.py", "fetch.py", "history.py", "telegram.py", "ledger.py"):
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
        elif e.kind == EV.KIND_STOCH_DB:
            c = int(pipe.index.get_loc(e.ts))
            assert c <= e.known_pos <= c + probe.STOCH_LAG                    # 가용 시점(피봇 확정 지연)
        else:
            assert e.known_pos == int(pipe.index.get_loc(e.ts))


def test_down_events_equal_down_tracker_turned_rows(pipe, events):
    turned = MD.track_candidates(pipe, recent_bars=len(pipe))
    turned = turned[turned["상태"] == MD.STATUS_TURNED]
    got = {e.ts for e in events if e.kind == EV.KIND_MA60_DOWN}
    assert got == set(pd.to_datetime(turned["전환 시각"])) and len(got) >= 1
    for e in events:
        if e.kind == EV.KIND_MA60_DOWN:
            assert e.known_pos == int(pipe.index.get_loc(e.ts)) and e.last_pos == len(pipe) - 1
            assert e.fields["pattern_high"] > 0 and e.fields["bars"] >= 0
    # 하락 다이버전스 = 하방 모듈의 거울상 정의 라벨(행 그대로) — 이벤트가 재계산하지 않는다
    by_ts = {pd.Timestamp(d["전환 시각"]): d for d in turned.to_dict("records")}
    for e in events:
        if e.kind == EV.KIND_MA60_DOWN:
            assert e.fields["divergence"] == (by_ts[e.ts][MD.DOWN_DIVERGENCE_COL] == DV.YES)
    assert {e.fields["divergence"] for e in events if e.kind == EV.KIND_MA60_DOWN} <= {True, False}
    # 하방 전환봉과 상승 전환봉은 같은 봉일 수 없다(전환 정의가 서로 배타적)
    up_ts = {e.ts for e in events if e.kind == EV.KIND_MA60_TURN}
    assert not (got & up_ts)


def test_stoch_db_events_equal_all_tracker_rows_with_single_definition_divergence(pipe, events):
    frame = MT.track_candidates(pipe, recent_bars=len(pipe))
    got = {e.ts: e for e in events if e.kind == EV.KIND_STOCH_DB}
    assert set(got) == set(pd.to_datetime(frame["확정 시각"])) and len(got) >= 10
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))
    for d in frame.to_dict("records"):
        e = got[pd.Timestamp(d["확정 시각"])]
        assert e.fields["divergence"] == flags[int(d["_confirm_pos"])] and e.fields["status"] == d["상태"]
        assert e.fields["already_up"] == (d["확정 시 60MA"] == MT.ALREADY_UP_MARK)
        assert e.fields["pattern_low"] == float(d["패턴 저점"]) and e.key.split("|")[2] == "stoch_db"
    assert any(e.fields["divergence"] for e in got.values()) and not all(e.fields["divergence"] for e in got.values())
    # 60MA 전환 이벤트도 같은 정의의 플래그를 싣는다(후보 확정봉 기준)
    for e in events:
        if e.kind == EV.KIND_MA60_TURN:
            c = int(pipe.index.get_loc(e.fields["confirm_ts"]))
            assert e.fields["divergence"] == flags[c]


def test_event_key_is_symbol_tf_kind_bar_timestamp(events):
    e = events[0]
    assert e.key == f"BTCUSDT|4h|{e.kind}|{e.ts:%Y-%m-%dT%H:%M:%S}Z"
    # 키는 (심볼, TF, 종류, 이벤트 봉). 같은 봉에서 전환한 두 후보(확정 시각이 다른 두 쌍봉/쌍바닥)는 키가 같다 —
    # 이벤트 목록에는 둘 다 있지만 plan() 이 같은 실행 안에서 1건으로 접는다(test_plan_same_key_twice_in_one_run_sends_once).
    assert len({(x.key, x.fields.get("confirm_ts")) for x in events}) == len(events)
    for k in {x.key for x in events}:
        same = [x for x in events if x.key == k]
        assert len({x.fields.get("confirm_ts") for x in same}) == len(same) and len({x.ts for x in same}) == 1
    planned = S.plan(events, {"sent": {}}, now=min(e.ts for e in events) + pd.Timedelta(days=1))   # 회전 창 밖(skip_old) 없이
    assert len([1 for _, act in planned if act == S.ACT_DUP]) == len(events) - len({x.key for x in events})


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


def test_message_format_ma60_turn_matches_delegation_example_plus_divergence_line():
    msg = EV.format_message(_turn_event())
    assert msg.splitlines() == [
        "[BTCUSDT 4h] 60MA 전환 발생 (미검증)",
        "쌍바닥 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)",      # UTC 08:00/12:00 → KST +9h
        "가격 80,726 · 패턴 저점 74,968 / 기준선 74,593",
        "다이버전스 없음",                                            # 기존 3줄 유지 + 끝 1줄
    ]
    e = _turn_event()
    e2 = EV.Event(e.symbol, e.tf, e.kind, e.ts, e.known_pos, e.last_pos, {**e.fields, "divergence": True})
    assert EV.format_message(e2).splitlines()[-1] == "다이버전스 있음"


def test_message_format_stoch_db_candidate_matches_delegation_example():
    assert EV.format_message(_db_event()).splitlines() == [
        "[BTCUSDT 4h] 대파동 쌍바닥 후보 (미검증)",
        "확정 09-21 13:00 · 60MA 현재 하방 (전환 대기, 창 20봉)",
        "패턴 저점 74,968 / 기준선 74,593",
        "참고: 과거 계측상 후보의 약 60%는 60MA 전환 없이 소멸",
    ]
    assert EV.format_message(_db_event(divergence=True)).splitlines()[1] == "★ 상승 다이버전스"    # 해당 시에만 2행
    assert "★" not in EV.format_message(_db_event())
    assert EV.format_message(_db_event(already_up=True, ma_now="상방")).splitlines()[1] == "확정 09-21 13:00 · 60MA 이미 상방"
    turned = _db_event(status=MT.STATUS_TURNED, turn_ts=pd.Timestamp("2026-09-21 16:00"), bars=3, ma_now="상방")
    assert EV.format_message(turned).splitlines()[1] == "확정 09-21 13:00 · 60MA 전환 발생 09-22 01:00 (소요 3봉)"
    assert EV.format_message(_db_event(status=MT.STATUS_EXPIRED)).splitlines()[1] == "확정 09-21 13:00 · 소멸 (창 20봉 안 60MA 전환 없음)"
    assert _db_event().key == "BTCUSDT|4h|stoch_db|2026-09-21T04:00:00Z"


def test_message_format_ma60_down_is_mirror_and_states_observation_only():
    msg = EV.format_message(_down_event())
    assert msg.splitlines() == [
        "[BTCUSDT 4h] 60MA 하방 전환 발생 (미검증)",
        "쌍봉 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)",
        "가격 80,726 · 패턴 고점 84,968 · 하락 다이버전스 있음",
        "참고: 현물 보유 시 관측용",
    ]
    assert EV.format_message(_down_event(divergence=False)).splitlines()[2] == "가격 80,726 · 패턴 고점 84,968 · 하락 다이버전스 없음"
    assert "40.7" not in msg and "41.3" not in msg and "기준선" not in msg      # 상승 쪽 수치·롱 손절 참조값 미사용
    assert _down_event().key == "BTCUSDT|4h|ma60_down|2026-09-18T12:00:00Z"
    assert _down_event().key != _turn_event().key                                 # 같은 봉이라도 종류가 달라 키가 다르다


def test_message_format_structure_ll_kst_and_labels():
    msg = EV.format_message(_ll_event())
    lines = msg.splitlines()
    assert lines[0] == "[ETHUSDT 1h] 구조 훼손 — 저점 LL 발생 (미검증)"
    assert lines[1] == "저점 09-19 09:00 4,322 < 직전 저점 4,400 (-1.78%) · 확정 09-19 12:00"
    assert lines[2] == "기준 저점 4,100 (쌍바닥 확정 09-16 05:00) · 현재 구조: 훼손 (LL 발생)"


def test_messages_carry_unverified_and_no_recommendation_words(events):
    for e in list(events) + [_turn_event(), _down_event(), _ll_event(), _db_event(), _db_event(divergence=True)]:
        msg = EV.format_message(e)
        assert "(미검증)" in msg.splitlines()[0]
        for w in EV.FORBIDDEN_WORDS:
            assert w not in msg, (w, msg)
        assert re.search(r"\d{2}-\d{2} \d{2}:\d{2}", msg)


# ------------------------------------------------------------ 계획(순수 함수): 최초 실행 제한 · 중복 · 회전 창
def _kinds_seen(hist: dict, now="2026-09-01 00:00") -> dict:
    """모든 종류를 이미 스캔한 것으로 표시 — 전역 최초 실행 규칙만 따로 검사할 때 쓴다."""
    for k in EV.KINDS:
        H.mark_kind(hist, k, now=pd.Timestamp(now))
    return hist


def test_plan_initial_run_sends_only_recent_two_bars():
    now = pd.Timestamp("2026-09-19 12:00")
    evs = [_turn_event("2026-09-19 08:00", last_pos=100, known_pos=100),     # 0봉 전 → 발송
           _turn_event("2026-09-19 04:00", last_pos=100, known_pos=99),      # 1봉 전 → 발송
           _turn_event("2026-09-19 00:00", last_pos=100, known_pos=98),      # 2봉 전 → 기록만
           _turn_event("2026-09-10 00:00", last_pos=100, known_pos=50)]      # 오래됨 → 기록만
    acts = {e.ts: a for e, a in S.plan(evs, _kinds_seen(H.empty()), now)}
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


def test_new_kind_first_run_sends_nothing_even_with_existing_kind_history():
    """신규 알림 종류 도입 폭탄 방지(종류별, 전역 규칙과 별개): 기존 종류(ma60_turn) 발송 이력이 있는 상태에서 신규 종류
    (ma60_down)를 처음 스캔하는 실행은 그 종류를 **0건 발송·전량 기록**하고, 그다음 실행부터 새 이벤트만 발송한다."""
    now = pd.Timestamp("2026-09-19 12:00")
    hist = H.empty()
    H.record(hist, "Y|1h|ma60_turn|2026-09-18T04:00:00Z", "2026-09-18 04:00", delivered=True, now=now)
    H.record(hist, "Y|1h|structure_ll|2026-09-18T04:00:00Z", "2026-09-18 04:00", delivered=True, now=now)
    assert not H.nothing_delivered(hist)                                     # 전역 최초 실행 모드 아님
    assert H.kind_seen(hist, EV.KIND_MA60_TURN) and H.kind_seen(hist, EV.KIND_STRUCTURE_LL)   # 기존 형식 이력으로 인정
    assert not H.kind_seen(hist, EV.KIND_MA60_DOWN)
    evs = [_down_event("2026-09-19 08:00", known_pos=100),                   # 0봉 전이라도 발송 안 함
           _down_event("2026-09-19 04:00", known_pos=99),
           _down_event("2026-09-10 00:00", known_pos=50),
           _turn_event("2026-09-10 00:00", known_pos=50)]
    acts = {(e.kind, e.ts): a for e, a in S.plan(evs, hist, now)}
    assert all(acts[(EV.KIND_MA60_DOWN, e.ts)] == S.ACT_NEW_KIND for e in evs if e.kind == EV.KIND_MA60_DOWN)
    assert acts[(EV.KIND_MA60_TURN, pd.Timestamp("2026-09-10 00:00"))] == S.ACT_SEND       # 기존 종류는 영향 없음
    assert S.ACT_SEND not in [a for (k, _), a in acts.items() if k == EV.KIND_MA60_DOWN]
    # 다음 실행: 종류를 본 것으로 표시하면 이력에 없는 새 이벤트만 발송, 기록된 것은 중복
    for e in evs:
        if e.kind == EV.KIND_MA60_DOWN:
            H.record(hist, e.key, e.ts, delivered=False, now=now)
    assert H.mark_kind(hist, EV.KIND_MA60_DOWN, now=now) and not H.mark_kind(hist, EV.KIND_MA60_DOWN, now=now)
    later = pd.Timestamp("2026-09-19 16:00")
    nxt = [_down_event("2026-09-19 12:00", known_pos=101, last_pos=101)] + evs[:1]
    acts2 = {(e.kind, e.ts): a for e, a in S.plan(nxt, hist, later)}
    assert acts2[(EV.KIND_MA60_DOWN, pd.Timestamp("2026-09-19 12:00"))] == S.ACT_SEND
    assert acts2[(EV.KIND_MA60_DOWN, pd.Timestamp("2026-09-19 08:00"))] == S.ACT_DUP
    # 이력 파일 왕복: kinds 필드 보존, 없던 파일(기존 형식)은 {} 로 읽힘
    assert H.key_kind("BTCUSDT|4h|ma60_down|2026-09-18T12:00:00Z") == "ma60_down"


def test_new_kind_first_run_end_to_end_records_then_sends_only_new(tmp_path, bars, events):
    """실데이터 픽스처: 기존 종류 이력만 있는 상태에서 1회차(하방 종류 첫 스캔) 발송 0건·전량 기록·kinds 기록,
    2회차(새 하방 전환봉 추가)에는 그 새 이벤트 1건만 발송."""
    state = str(tmp_path / "sent.json")
    env = {"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
    downs = sorted((e for e in events if e.kind == EV.KIND_MA60_DOWN), key=lambda e: e.ts)
    assert len(downs) >= 2
    last = downs[-1]
    cut = int(bars.index.get_loc(last.ts))                   # 1회차 = 마지막 하방 전환봉 직전까지
    bars1 = bars.iloc[:cut]
    seeded = {k: v for k, v in _seeded_sent().items() if H.key_kind(k) != EV.KIND_MA60_DOWN}   # 기존 종류 이력만
    H.save(state, {"version": 1, "sent": seeded})            # 기존 형식(kinds 없음)
    s1 = _Sender()
    now1 = bars1.index[-1] + pd.Timedelta(hours=4)
    r1 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars1), send=s1, env=env, now=now1)
    assert not any("하방 전환 발생" in c[2] for c in s1.calls)                 # 하방 종류 발송 0건
    ev1 = EV.scan_frame(S.build_pipe(bars1), "BTCUSDT", "4h")
    d1 = [e for e in ev1 if e.kind == EV.KIND_MA60_DOWN and e.ts >= now1 - pd.Timedelta(days=H.SCAN_MAX_AGE_DAYS)]
    assert r1["new_kind_record_only"] == len(d1) and r1["new_kinds"] == [EV.KIND_MA60_DOWN]
    saved = json.load(open(state, encoding="utf-8"))
    assert saved["kinds"].keys() == {EV.KIND_MA60_DOWN} and all(not saved["sent"][e.key]["delivered"] for e in d1)
    s2 = _Sender()
    now2 = _now_after(bars)
    r2 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=s2, env=env, now=now2)
    sent_down = [c for c in s2.calls if "하방 전환 발생" in c[2]]
    assert len(sent_down) == 1 and f"{last.ts + pd.Timedelta(hours=9):%m-%d %H:%M}" in sent_down[0][2]
    assert r2["new_kinds"] == [] and r2["new_kind_record_only"] == 0
    assert json.load(open(state, encoding="utf-8"))["sent"][last.key]["delivered"] is True


def test_plan_same_key_twice_in_one_run_sends_once():
    """두 쌍바닥 후보가 같은 봉에서 전환 → 키 동일 → 한 실행 안에서도 1건만 (Actions 첫 실행 로그에서 관찰된 사례)."""
    now = pd.Timestamp("2026-09-19 12:00")
    a = _turn_event("2026-09-19 08:00", known_pos=100)
    b = EV.Event(a.symbol, a.tf, a.kind, a.ts, a.known_pos, a.last_pos, {**a.fields, "bars": 7})
    assert a.key == b.key and a != b
    acts = [act for _, act in S.plan([a, b], _kinds_seen(H.empty()), now)]
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
    assert H.load(str(p)) == {"version": 1, "sent": hist["sent"], "kinds": {}, "ledger": {"since": None, "rows": []}}
    H.mark_kind(hist, "ma60_down", now=now)
    H.save(str(p), hist)
    assert H.load(str(p))["kinds"] == {"ma60_down": "2026-09-20T00:00:00Z"} and H.rotate(hist, now + pd.Timedelta(days=400)) == 1
    assert hist["kinds"] == {"ma60_down": "2026-09-20T00:00:00Z"}         # 회전은 kinds 를 건드리지 않는다
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


def _seeded_sent() -> dict:
    """종류별 무관 키 1개씩 발송 성공 기록 — 종류별 최초 실행 제한을 피하기 위한 씨앗(테스트 전용)."""
    return {f"X|1h|{k}|2026-08-31T00:00:00Z": {"event_ts": "2026-08-31T00:00:00Z", "sent_at": "2026-08-31T00:00:00Z",
                                              "delivered": True} for k in EV.KINDS}


def test_run_dedups_across_runs_and_persists_history(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    env = {"TELEGRAM_TOKEN": "t0k", "TELEGRAM_CHAT_ID": "42"}
    H.save(state, {"version": 1, "sent": _seeded_sent()})   # 최초 실행 제한을 피하려고 종류별 무관 키를 심는다
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
    """전역 최초 실행 규칙(발송 성공 0건 → 최근 2봉만). 종류별 첫 스캔 규칙은 kinds 를 미리 채워 분리한다."""
    state = str(tmp_path / "sent.json")
    now = _now_after(bars)
    H.save(state, _kinds_seen(H.empty()))
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
    H.save(state, {"version": 1, "sent": _seeded_sent()})
    env = {"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}
    bad = _Sender(ok=False)
    r = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=bad, env=env, now=now)
    assert r["send_failed"] == len(bad.calls) > 0 and r["sent"] == 0
    assert len(json.load(open(state, encoding="utf-8"))["sent"]) == len(EV.KINDS)      # 실패분 미기록
    good = _Sender()
    r = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=good, env=env, now=now)
    assert r["sent"] == len(bad.calls) == len(good.calls)                   # 다음 실행에서 재시도


def test_secrets_absent_logs_only_and_exits_zero(tmp_path, bars, monkeypatch):
    state = str(tmp_path / "sent.json")
    H.save(state, {"version": 1, "sent": _seeded_sent()})
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
    assert len(json.load(open(state, encoding="utf-8"))["sent"]) == len(EV.KINDS)      # 미발송분 미기록


def test_dry_run_sends_nothing_and_writes_nothing(tmp_path, bars, events):
    state = str(tmp_path / "sent.json")
    s = _Sender()
    r = S.run(state_path=state, dry_run=True, symbols=["BTCUSDT"], tfs=["4h"], fetch=_fetch_of(bars), send=s,
              env={"TELEGRAM_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}, now=_now_after(bars))
    assert s.calls == [] and not os.path.exists(state)                     # dry-run 은 kinds 도 기록하지 않는다
    assert r["would_send"] + r["record_only"] + r["new_kind_record_only"] + r["old"] == len(events) and r["sent"] == 0
    assert r["would_send"] == 0 and set(r["new_kinds"]) == set(EV.KINDS)     # 빈 이력 = 모든 종류의 첫 스캔


def test_cell_failure_does_not_stop_other_cells(tmp_path, bars):
    def fetch(sym, tf):
        if sym == "ETHUSDT":
            raise RuntimeError("boom")
        return bars

    r = S.run(state_path=str(tmp_path / "s.json"), dry_run=True, symbols=["ETHUSDT", "BTCUSDT"], tfs=["4h"],
              fetch=fetch, send=_Sender(), env={}, now=_now_after(bars))
    assert len(r["failures"]) == 4 and {f.split(":")[0] for f in r["failures"]} == {f"ETHUSDT {t}" for t in LG.LEDGER_TFS}
    assert r["events"] > 0                                    # BTCUSDT 셀은 정상 처리(알림 4h + ledger 1h/4h/6h/1d)


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
    assert S.LEDGER_TFS == ("1h", "4h", "6h", "1d") and "6h" not in S.TFS      # 6h 는 ledger 전용
    assert EV.KINDS == ("ma60_turn", "ma60_down", "structure_ll", "stoch_db")   # 알림 종류 4개(쌍바닥 후보 추가)


# ------------------------------------------------------------ 전방 ledger (알림과 별개)
def test_ledger_rows_are_finished_candidates_with_single_definition_divergence(pipe):
    rows = LG.finished_rows(pipe, "BTCUSDT", "4h")
    frame = MT.track_candidates(pipe, recent_bars=len(pipe))
    fin = frame[frame["상태"].isin([MT.STATUS_TURNED, MT.STATUS_EXPIRED])]
    assert len(rows) == len(fin) >= 10 and {r["result"] for r in rows} == {"turned", "expired"}
    flags = DV.divergence_flags(MT.tracker_pipe(pipe))
    by = {r["confirm_ts"]: r for r in rows}
    for d in fin.to_dict("records"):
        r = by[pd.Timestamp(d["확정 시각"]).strftime("%Y-%m-%dT%H:%M:%SZ")]
        assert r["divergence"] == flags[int(d["_confirm_pos"])]
        if d["상태"] == MT.STATUS_TURNED:
            assert r["result"] == "turned" and r["bars_to_turn"] == int(d["_bars"]) and r["turn_price"] == float(d["전환 시 가격"])
        else:
            assert r["result"] == "expired" and r["bars_to_turn"] is None and r["turn_ts"] is None
    assert set(rows[0]) == set(LG.FIELDS) - {"recorded_at", "direction", "pattern_high", "already_down"}   # 상승 행 형식 불변
    csv_text = LG.to_csv([{**r, "recorded_at": "2026-09-22T00:00:00Z"} for r in rows])
    assert csv_text.splitlines()[0] == ",".join(LG.FIELDS) and len(csv_text.splitlines()) == len(rows) + 1
    s = LG.summary(rows)
    assert s["divergence"]["turned"] + s["divergence"]["expired"] + s["no_divergence"]["turned"] + s["no_divergence"]["expired"] == len(rows)


def test_ledger_down_rows_have_direction_and_mirror_fields_and_do_not_collide_with_up_rows(pipe):
    """하방 후보 생애주기도 같은 ledger 에 direction="down" 행으로. 상승 행 형식(키 집합)은 종전 그대로."""
    up_rows = LG.finished_rows(pipe, "BTCUSDT", "4h")
    dn_rows = LG.finished_rows_down(pipe, "BTCUSDT", "4h")
    frame = MD.track_candidates(pipe, recent_bars=len(pipe))
    fin = frame[frame["상태"].isin([MD.STATUS_TURNED, MD.STATUS_EXPIRED])]
    assert len(dn_rows) == len(fin) >= 3 and {r["result"] for r in dn_rows} <= {"turned", "expired"}
    assert all("direction" not in r and "pattern_high" not in r for r in up_rows)              # 상승 행 형식 불변
    assert set(up_rows[0]) == set(LG.FIELDS) - {"recorded_at", "direction", "pattern_high", "already_down"}
    assert set(dn_rows[0]) == set(LG.FIELDS) - {"recorded_at", "pattern_low", "already_up"}
    by = {r["confirm_ts"]: r for r in dn_rows}
    for d in fin.to_dict("records"):
        r = by[pd.Timestamp(d["확정 시각"]).strftime("%Y-%m-%dT%H:%M:%SZ")]
        assert r["direction"] == "down" and r["pattern_high"] == float(d[MD.HIGH_COL])
        assert r["divergence"] == (d[MD.DOWN_DIVERGENCE_COL] == DV.YES)
        assert r["already_down"] == (d["확정 시 60MA"] == MD.ALREADY_DOWN_MARK)
        if d["상태"] == MD.STATUS_TURNED:
            assert r["result"] == "turned" and r["bars_to_turn"] == int(d["_bars"]) and r["turn_price"] == float(d["전환 시 가격"])
        else:
            assert r["result"] == "expired" and r["bars_to_turn"] is None and r["turn_ts"] is None
    # 키: 상승 행은 종전 형식 그대로, 하방 행은 '|down' — 같은 확정봉이라도 충돌하지 않는다
    up = {"symbol": "X", "tf": "1h", "confirm_ts": "2026-09-22T00:00:00Z", "result": "expired", "divergence": False}
    dn = {**up, "direction": "down", "pattern_high": 1.0, "already_down": False}
    assert LG.key_of(up) == "X|1h|2026-09-22T00:00:00Z" and LG.key_of(dn) == "X|1h|2026-09-22T00:00:00Z|down"
    hist = H.empty(); H.ledger_init(hist, now=pd.Timestamp("2026-09-22 00:00"))
    assert H.ledger_append(hist, [up, dn], now=pd.Timestamp("2026-09-23 00:00")) == 2
    assert H.ledger_append(hist, [up, dn], now=pd.Timestamp("2026-09-23 00:00")) == 0
    assert H.ledger_keys(hist) == {LG.key_of(up), LG.key_of(dn)}
    # CSV: 헤더에 direction·pattern_high·already_down, 상승 행은 direction "up" 으로만 채움(저장 형식은 그대로)
    csv_lines = LG.to_csv([{**r, "recorded_at": "2026-09-22T00:00:00Z"} for r in up_rows[:1] + dn_rows[:1]]).splitlines()
    assert csv_lines[0] == ",".join(LG.FIELDS) and csv_lines[1].split(",")[LG.FIELDS.index("direction")] == "up"
    assert csv_lines[2].split(",")[LG.FIELDS.index("direction")] == "down"
    # 요약은 방향별로 분리 — 기본 호출은 상승 행만(기존 호출 불변)
    s_up, s_dn = LG.summary(up_rows + dn_rows), LG.summary(up_rows + dn_rows, direction="down")
    assert sum(v for d in s_up.values() for v in d.values()) == len(up_rows)
    assert sum(v for d in s_dn.values() for v in d.values()) == len(dn_rows)


def test_ledger_no_backfill_only_after_since_and_dedup():
    now = pd.Timestamp("2026-09-22 00:00")
    hist = H.empty()
    assert H.ledger_append(hist, [{"symbol": "X", "tf": "1h", "confirm_ts": "2026-09-21T00:00:00Z", "result": "expired"}]) == 0
    assert H.ledger_init(hist, now=now) and not H.ledger_init(hist, now=now) and hist["ledger"]["since"] == "2026-09-22T00:00:00Z"
    rows = [{"symbol": "X", "tf": "1h", "confirm_ts": "2026-09-21T23:00:00Z", "result": "expired", "divergence": False},   # since 이전 → 제외
            {"symbol": "X", "tf": "1h", "confirm_ts": "2026-09-22T00:00:00Z", "result": "turned", "divergence": True},     # since 봉 → 포함
            {"symbol": "X", "tf": "6h", "confirm_ts": "2026-09-23T06:00:00Z", "result": "expired", "divergence": False}]
    assert H.ledger_append(hist, rows, now=now + pd.Timedelta(days=2)) == 2
    assert H.ledger_append(hist, rows, now=now + pd.Timedelta(days=3)) == 0                 # 중복 없음
    assert [r["confirm_ts"] for r in hist["ledger"]["rows"]] == ["2026-09-22T00:00:00Z", "2026-09-23T06:00:00Z"]
    assert all(r["recorded_at"] == "2026-09-24T00:00:00Z" for r in hist["ledger"]["rows"])
    assert H.rotate(hist, now + pd.Timedelta(days=400)) == 0 and len(hist["ledger"]["rows"]) == 2   # 회전 무관
    assert LG.since_of(hist) == now and LG.since_of(H.empty()) is None


def test_run_records_ledger_including_6h_and_never_backfills(tmp_path, bars, events):
    """실데이터: 첫 실행은 since 만 기록(0행, 과거 소급 없음). 그 뒤 새로 확정·종료된 후보만 추가. 6h 셀도 fetch·기록."""
    state = str(tmp_path / "sent.json")
    fetched = []

    def fetch(sym, tf):
        fetched.append((sym, tf))
        return bars

    H.save(state, _kinds_seen(H.empty()))
    now1 = _now_after(bars)
    r1 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], ledger_tfs=["4h", "6h"],
               fetch=fetch, send=_Sender(), env={}, now=now1)
    assert ("BTCUSDT", "6h") in fetched and ("BTCUSDT", "4h") in fetched
    saved = H.load(state)
    assert r1["ledger_added"] == 0 and saved["ledger"]["since"] == now1.strftime("%Y-%m-%dT%H:%M:%SZ") and saved["ledger"]["rows"] == []
    # since 를 과거로 되돌린 상태를 흉내내면(배포 이후 확정된 후보가 존재) 종료 후보가 기록된다 — 6h 도 4h 프레임을 받으므로 같은 행이 tf=6h 로
    hist = H.load(state)
    hist["ledger"]["since"] = "2026-01-01T00:00:00Z"
    H.save(state, hist)
    r2 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], ledger_tfs=["4h", "6h"],
               fetch=fetch, send=_Sender(), env={}, now=now1)
    rows = H.load(state)["ledger"]["rows"]
    fin = LG.finished_rows(S.build_pipe(bars), "BTCUSDT", "4h") + LG.finished_rows_down(S.build_pipe(bars), "BTCUSDT", "4h")
    assert r2["ledger_added"] == len(rows) == 2 * len(fin) and {r["tf"] for r in rows} == {"4h", "6h"}
    assert {LG.direction_of(r) for r in rows} == {"up", "down"}                             # 하방 생애주기도 기록
    r3 = S.run(state_path=state, dry_run=False, symbols=["BTCUSDT"], tfs=["4h"], ledger_tfs=["4h", "6h"],
               fetch=fetch, send=_Sender(), env={}, now=now1)
    assert r3["ledger_added"] == 0 and len(H.load(state)["ledger"]["rows"]) == len(rows)    # 재실행 중복 없음
    # dry-run 은 since 도 ledger 도 쓰지 않는다
    state2 = str(tmp_path / "s2.json")
    S.run(state_path=state2, dry_run=True, symbols=["BTCUSDT"], tfs=["4h"], fetch=fetch, send=_Sender(), env={}, now=now1)
    assert not os.path.exists(state2)
    # CSV 내보내기 CLI
    out = str(tmp_path / "ledger.csv")
    assert S.main(["--state", state, "--export-ledger", out]) == 0
    assert open(out, encoding="utf-8").read().splitlines()[0] == ",".join(LG.FIELDS)


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
