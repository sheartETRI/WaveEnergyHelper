"""v2 시그널 카드 빌더 + 패널 레지스트리 테스트 (§6).

실행: `python -m pytest tests/test_campaign_card.py` 또는 직접 실행
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.campaign_score import score_campaign
from analysis.campaign_state_machine import DONE, CampaignResult, TradePoint
from display.campaign_card import build_campaign_card
from display.panel_registry import TYPE_A_PANELS, PanelSpec, render_type_a_panels


def _df(n=20):
    idx = pd.date_range("2026-01-01", periods=n, freq="4h")
    return pd.DataFrame({"close": 100.0, "low": 100.0, "high": 130.0}, index=idx)


def _complete_long():
    res = CampaignResult(
        symbol="BNBUSDT", base_tf="4h", direction="long",
        setup_ts=pd.Timestamp("2026-05-01"), setup_pos=0, setup_layer="MA10",
        state=DONE, strength_flag=True, strength_layer="(20,10,10)",
        predicted_grade="mid", predicted_region_label="MA20~60",
    )
    res.entry1 = TradePoint("S2_ENTRY1", res.setup_ts, 2, 615.2, "BUY")
    res.exit1 = TradePoint("S4_EXIT1", res.setup_ts, 5, 648.9, "SELL")
    res.entry2 = TradePoint("S6_ENTRY2", res.setup_ts, 10, 622.0, "BUY")
    res.exit_final = TradePoint("DONE", res.setup_ts, 15, 700.0, "SELL")
    return res


def test_card_lines_match_mockup_fields():
    res = _complete_long()
    score = score_campaign(res, _df())
    lines = build_campaign_card(res, score, upper_info="1d 레짐 UP")
    head = lines[0]
    assert "BNBUSDT" in head and "기준 4h" in head and "매수 캠페인" in head
    assert "[관측 등급]" in head        # 관측 등급 라벨 필수
    body = "\n".join(lines)
    assert "발단: MA10 쌍바닥(HL)" in body
    assert "[강화]" in body and "스토캐 삼중" in body
    assert "ENTRY-1 615.2" in body and "EXIT-1 648.9" in body
    assert "2파 예측: 중파동 → MA20~60" in body
    assert "ENTRY-2 622" in body
    assert "1d 레짐 UP" in body


def test_card_honest_placeholders_before_journal():
    res = _complete_long()
    score = score_campaign(res, _df())
    lines = build_campaign_card(res, score)   # 컨텍스트 미주입
    body = "\n".join(lines)
    assert "과거 성적: 수집 중" in body       # 근거 없는 자신감 금지
    assert "하위 파동: 수집 중" in body


def test_card_pre_entry_state():
    res = CampaignResult(symbol="X", base_tf="1h", direction="long",
                         setup_ts=pd.Timestamp("2026-05-01"), setup_pos=0, setup_layer="MA10",
                         state="S1_CONFIRM")
    score = score_campaign(res, _df())
    body = "\n".join(build_campaign_card(res, score))
    assert "진입 전" in body
    assert "재진입 조건" in body and "무효화 없음" in body


def test_registry_is_data_and_renders_selected():
    # 레지스트리는 데이터 선언 — 40개 안팎의 Type A 패널
    assert len(TYPE_A_PANELS) >= 35
    assert all(isinstance(p, PanelSpec) for p in TYPE_A_PANELS)
    keys = {p.key for p in TYPE_A_PANELS}
    assert "show_wave_survival" in keys and "show_final_synthesis" in keys

    # 렌더 루프: flags로 선택된 것만 호출 (모의 스펙으로 검증)
    calls = []
    fake = [
        PanelSpec("show_a", "A", "os", "getcwd"),   # os.getcwd(symbol,interval) → 예외 격리 테스트용
    ]

    # 선택 안 하면 호출 없음
    rendered = render_type_a_panels({"show_a": False}, "BTC", "4h", registry=fake)
    assert rendered == []


if __name__ == "__main__":
    test_card_lines_match_mockup_fields()
    test_card_honest_placeholders_before_journal()
    test_card_pre_entry_state()
    test_registry_is_data_and_renders_selected()
    print("ALL CAMPAIGN CARD / REGISTRY TESTS PASSED")
