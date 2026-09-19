"""화면 시각 KST 표기 — 헬퍼 정확성(+9h, DST 없음), 기록 계층 무변환, 표시 지점 일관성."""
import os
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.tz_label as TZ  # noqa: E402


# ------------------------------------------------------------ 헬퍼
@pytest.mark.parametrize("ts", ["2026-01-15 00:00", "2026-03-29 01:30", "2026-06-30 23:59", "2026-09-19 05:00",
                                "2026-10-25 01:00", "2026-12-31 15:00", "2024-02-29 12:00"])
def test_to_kst_is_exactly_plus_nine_hours_no_dst(ts):
    t = pd.Timestamp(ts)
    k = TZ.to_kst(t)
    assert k - t == pd.Timedelta(hours=9)
    assert k.tzinfo is None                                    # naive → naive
    # zoneinfo 로 교차 확인: Asia/Seoul 은 연중 +9h (DST 없음)
    ref = t.tz_localize("UTC").tz_convert(ZoneInfo("Asia/Seoul")).tz_localize(None)
    assert k == ref


def test_to_kst_handles_aware_and_nat():
    aware = pd.Timestamp("2026-09-19 05:00", tz="UTC")
    assert TZ.to_kst(aware) == pd.Timestamp("2026-09-19 14:00")
    assert TZ.to_kst(pd.NaT) is pd.NaT
    assert TZ.KST_LABEL == "(KST)" and TZ.KST_OFFSET == pd.Timedelta(hours=9)


def test_kst_text_shifts_embedded_timestamps_only():
    assert TZ.kst_text("교차 2026-09-18 08:00 · hist 423.9") == "교차 2026-09-18 17:00 · hist 423.9"
    assert TZ.kst_text("교차 2026-09-18 20:00 · MACD -343.7") == "교차 2026-09-19 05:00 · MACD -343.7"   # 날짜 넘어감
    assert TZ.kst_text("LL") == "LL" and TZ.kst_text(None) is None


# ------------------------------------------------------------ 기록·정의 계층 무변환
RECORD_AND_DEFINITION_DIRS = ("analysis", "indicators", "data", "config")


def test_recording_and_definition_layers_never_convert_timezone():
    """사이드카·저널·검출기·데이터 적재는 naive UTC 그대로 — 표시 헬퍼를 import 하지도, tz 변환을 하지도 않는다."""
    hits = []
    for d in RECORD_AND_DEFINITION_DIRS:
        for root, _dirs, files in os.walk(os.path.join(ROOT, d)):
            for f in files:
                if not f.endswith(".py"):
                    continue
                src = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                for banned in ("display.tz_label", "to_kst", "kst_text", "Asia/Seoul", "tz_convert(", "KST"):
                    if banned in src:
                        hits.append((os.path.relpath(os.path.join(root, f), ROOT), banned))
    assert hits == [], hits
    # 기록 경로 대표 파일이 존재하고 위 검사에 포함되었는지
    for rel in ("analysis/wave_align_gate_forward.py", "analysis/wave_live_forward_journal.py", "analysis/alarm_signals.py"):
        assert os.path.isfile(os.path.join(ROOT, rel))


# ------------------------------------------------------------ 표시 지점 일관성 (전부 KST, 같은 헬퍼)
def test_every_display_point_shows_same_kst_wall_clock():
    import charts.lw_builder as LW
    import display.alarm_panel as AP
    import display.ma60_turn_tracker as T
    import main as M
    ts = pd.Timestamp("2026-09-19 05:00")           # 데이터(UTC) → 화면 2026-09-19 14:00 (KST)
    kst = "2026-09-19 14:00"
    # 차트: PAYLOAD 시프트 값이 헬퍼와 같다(툴팁 문자열은 test_lw_time_format 에서 node 로 확인)
    assert LW._display_seconds(ts) == int(TZ.to_kst(ts).timestamp())
    # 알람 탭 마지막 봉
    idx = pd.date_range(ts - pd.Timedelta(hours=2), periods=3, freq="h")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    assert AP.build_bar_caption(df).startswith(f"마지막 봉 {kst} {TZ.KST_LABEL}")
    assert AP.HISTORY_TIME_HEADER == f"시각 {TZ.KST_LABEL}"
    # 알람 탭 이력 표(시각 + 비고 안 교차 시각) — 정의 계층 프레임은 UTC 그대로, 표시 사본만 KST
    raw = pd.DataFrame({"시각": [ts], "신호": ["MACD 골든크로스"], "레이어": ["MACD"], "구분": ["확정"],
                        "지표값": [1.0], "비고": ["교차 2026-09-19 04:00 · MACD -1.0"]})
    shown = AP.history_frame_kst(raw)
    assert shown.loc[0, "시각"] == pd.Timestamp(kst) and shown.loc[0, "비고"] == "교차 2026-09-19 13:00 · MACD -1.0"
    assert raw.loc[0, "시각"] == ts and raw.loc[0, "비고"].startswith("교차 2026-09-19 04:00")
    # 60MA 추적 섹션
    assert T._fmt_ts(ts) == kst and T.DISPLAY_HEADERS["전환 시각"] == f"전환 시각 {TZ.KST_LABEL}"
    # 사이드바
    cap = M.data_freshness_caption(ts.timestamp(), ts)
    assert cap == f"마지막 로드 2026-09-19 14:00:00 · 마지막 봉 09-19 14:00 {TZ.KST_LABEL}"
    # UTC 라벨은 어디에도 남지 않았다
    for mod in (LW, AP, T, M):
        assert "UTC_LABEL" not in open(mod.__file__, encoding="utf-8").read()
