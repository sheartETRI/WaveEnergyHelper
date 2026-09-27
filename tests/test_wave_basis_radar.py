"""기준 TF 레이더 테스트 — 요약·우선순위 계약 (SPEC §10). 트래커는 이음새로 주입."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import display.ma60_down_tracker as down
import display.ma60_turn_tracker as up
from display.wave_basis_radar import (
    basis_table,
    build_basis_rows,
    pick_basis_focus,
)

# 트래커 출력 모사 — 상태 문자열은 실제 상수를 단일 출처로 쓴다.
WAITING_UP = pd.DataFrame([{"상태": up.STATUS_WAITING, "경과/소요": "4/20", "다이버전스": "있음"}])
TURNED_UP = pd.DataFrame([{"상태": up.STATUS_TURNED, "경과/소요": "7", "다이버전스": "없음"}])
WAITING_DOWN = pd.DataFrame([{"상태": down.STATUS_WAITING, "경과/소요": "2/20", "다이버전스": "있음"}])
EMPTY = pd.DataFrame(columns=["상태", "경과/소요", "다이버전스"])

DUMMY = pd.DataFrame({"close": [1.0, 2.0]})  # 트래커 주입 시 내용 무관 — 비어 있지만 않으면 됨


def _tracker(mapping):
    """interval 무관 — df 객체 id 로 구분할 수 없으니 호출 순서 대신 고정 프레임 반환용."""
    def fn(_df):
        return mapping
    return fn


def test_waiting_up_scores_and_focus():
    rows = build_basis_rows(
        {"1w": DUMMY, "1d": DUMMY},
        track_up=lambda df: WAITING_UP if df is DUMMY else EMPTY,
        track_down=_tracker(EMPTY),
    )
    assert rows[0].interval == "1w"            # 동률(둘 다 대기) -> 상위 TF 먼저
    assert rows[0].score == 2
    assert rows[0].up_text.startswith("대기 1")
    assert "4/20봉" in rows[0].up_text and "다이버전스 있음" in rows[0].up_text
    focus = pick_basis_focus(rows)
    assert focus.interval == "1w" and "상방" in focus.detail


def test_down_waiting_direction_in_detail():
    rows = build_basis_rows(
        {"6h": DUMMY},
        track_up=_tracker(EMPTY),
        track_down=_tracker(WAITING_DOWN),
    )
    assert rows[0].score == 2
    assert "하방" in rows[0].detail


def test_turned_scores_one():
    rows = build_basis_rows(
        {"3d": DUMMY},
        track_up=_tracker(TURNED_UP),
        track_down=_tracker(EMPTY),
    )
    assert rows[0].score == 1
    assert rows[0].up_text.startswith("전환 발생 1")


def test_no_data_and_quiet():
    rows = build_basis_rows(
        {"1d": None, "6h": DUMMY},
        track_up=_tracker(EMPTY),
        track_down=_tracker(EMPTY),
    )
    by_tf = {r.interval: r for r in rows}
    assert by_tf["1d"].up_text == "데이터 없음"
    assert by_tf["6h"].score == 0 and by_tf["6h"].up_text == "―"
    assert pick_basis_focus(rows) is None


def test_basis_table_shape():
    rows = build_basis_rows(
        {"1w": DUMMY},
        track_up=_tracker(WAITING_UP),
        track_down=_tracker(EMPTY),
    )
    table = basis_table(rows)
    assert list(table.columns) == ["TF", "쌍바닥→상방", "쌍봉→하방"]
    assert len(table) == 1
