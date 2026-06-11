"""AI 해설 테스트.

실행: python -m pytest tests/test_narration.py
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NARRATION_CONFIG, NARRATION_RATE_LIMIT_CAPTION
from display.transition_radar import TransitionRadarContent
from narration.cache import clear_narration_cache
from narration.client import NarrationRateLimitError, call_openai_compatible_chat
from narration.fallback import build_fallback_summary
from narration.input_builder import build_narration_context, build_prompt_messages
from narration.service import generate_narration
from narration.validator import validate_narration_text
from tests.test_transition_rules import _scenario_F6_4a, _struct_df
from analysis.dynamics_rules import evaluate_dynamics
from analysis.wave_energy import WaveEnergyReport, TrendState, WaveState


def _minimal_report():
    trend = TrendState(direction="상승", slope_pct=1.2, valid=True)
    wave = WaveState(direction="상승", zone="중립", valid=True)
    df = _struct_df("U1")
    _scenario_F6_4a(df)
    dyn = evaluate_dynamics(df)
    return WaveEnergyReport(
        symbol="BTCUSDT",
        interval="1d",
        trend=trend,
        base_large=wave,
        base_small=wave,
        upper_interval="4d",
        upper_small=wave,
        mtf_agreement="일치",
        verdict="관망",
        notes=[],
        dynamics=dyn,
    )


def _sample_context():
    radar = TransitionRadarContent(
        environment_line="변곡 환경: 이격도 P55 · 중간",
        forming_items=[],
        recent_caption="최근 변곡: [F6-4a] 하방 · 완성 01-23 (7봉 전)",
    )
    return build_narration_context(_minimal_report(), "정배열", radar)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_narration_cache()
    yield
    clear_narration_cache()


def test_build_narration_context_facts():
    ctx = _sample_context()
    assert ctx["symbol"] == "BTCUSDT"
    assert ctx["verdict"] == "관망"
    assert ctx["radar"]["environment"].startswith("변곡 환경")


def test_build_prompt_messages_korean_system():
    msgs = build_prompt_messages(_sample_context())
    assert msgs[0]["role"] == "system"
    assert "한국어" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"


def test_validate_rejects_prediction_words():
    text = (
        "일봉 추세는 상승이며 MA는 정배열입니다. "
        "대파동과 소파동은 중립 구간에 있으며 전환 임박합니다."
    )
    ok, reason = validate_narration_text(text)
    assert not ok
    assert reason.startswith("forbidden")


def test_validate_accepts_factual_text():
    text = "일봉 60MA는 상승 추세이며 대파동과 소파동 모두 중립 구간에 있습니다."
    ok, _ = validate_narration_text(text)
    assert ok


def test_fallback_summary_no_exception():
    body = build_fallback_summary(_sample_context())
    assert "관망" in body
    assert "변곡 형성 중인 패턴 없음" in body


def test_narration_config_max_tokens_is_2000():
    """gemini-2.5-flash reasoning 예산 — 기본 max_tokens는 2000."""
    assert NARRATION_CONFIG["max_tokens"] == 2000


@patch("narration.service.call_openai_compatible_chat")
@patch("narration.service._resolve_api_key", return_value="test-key")
def test_truncated_empty_llm_response_uses_fallback(mock_key, mock_call):
    """짧은 예산으로 잘린/빈 LLM 응답 → 검증 실패 → 폴백 (조용한 기능 무력화 방지 회귀)."""
    mock_call.return_value = ""
    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    fallback_preview = build_fallback_summary(
        build_narration_context(report, "정배열", radar),
    )
    result = generate_narration(report, "정배열", radar, "2024-01-30")
    assert result.source == "fallback"
    assert result.body == fallback_preview


def test_opt_in_off_skips_generate_narration():
    """기본(off): generate_narration·캐시·폴백 경로 미진입."""
    from main import render_wave_narration_if_enabled

    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    df = _struct_df("U1")
    with patch("main.generate_narration") as mock_gen, patch(
        "main.st",
    ) as mock_st:
        render_wave_narration_if_enabled(False, report, "정배열", df, radar)
        mock_gen.assert_not_called()
        mock_st.markdown.assert_not_called()


@patch("main.generate_narration")
def test_opt_in_on_calls_generate_narration(mock_gen):
    """체크 on → generate_narration 호출."""
    from main import render_wave_narration_if_enabled

    mock_gen.return_value = MagicMock(body="해설 본문", extra_caption=None, source="llm")
    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    df = _struct_df("U1")
    with patch("main.st") as mock_st:
        render_wave_narration_if_enabled(True, report, "정배열", df, radar)
        mock_gen.assert_called_once()
        assert mock_st.markdown.call_count >= 2


def test_master_enabled_false_hides_checkbox_path():
    """enabled=False → UI·옵트인 모두 불가."""
    cfg = {"enabled": False}
    from main import is_narration_ui_available, should_show_narration

    assert not is_narration_ui_available(cfg)
    assert not should_show_narration(True, cfg)
    assert not should_show_narration(False, cfg)


def test_session_recheck_uses_cache_without_second_llm_call():
    """세션 내 재체크 — 동일 봉이면 캐시 hit, LLM 재호출 없음."""
    with patch("narration.service.call_openai_compatible_chat") as mock_call, patch(
        "narration.service._resolve_api_key",
        return_value="test-key",
    ):
        mock_call.return_value = (
            "일봉 추세는 상승이며 MA는 정배열입니다. "
            "대파동·소파동 모두 중립 구간에 있고 변곡 형성 중 패턴은 없습니다."
        )
        report = _minimal_report()
        radar = TransitionRadarContent(None, [], None)
        bar_ts = "2024-01-30"
        r1 = generate_narration(report, "정배열", radar, bar_ts)
        r2 = generate_narration(report, "정배열", radar, bar_ts)
        assert r1.source == "llm"
        assert r2.body == r1.body
        mock_call.assert_called_once()


@patch("narration.service._resolve_api_key", return_value=None)
def test_missing_api_key_uses_fallback(mock_key):
    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    result = generate_narration(report, "정배열", radar, "2024-01-30")
    assert result.source == "fallback"
    assert result.body
    assert result.extra_caption is None


@patch("narration.service.call_openai_compatible_chat")
@patch("narration.service._resolve_api_key", return_value="test-key")
def test_429_uses_fallback_with_rate_limit_caption(mock_key, mock_call):
    mock_call.side_effect = NarrationRateLimitError("429")
    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    result = generate_narration(report, "정배열", radar, "2024-01-30")
    assert result.source == "fallback"
    assert result.extra_caption == NARRATION_RATE_LIMIT_CAPTION
    mock_call.assert_called_once()


@patch("narration.service.call_openai_compatible_chat")
@patch("narration.service._resolve_api_key", return_value="test-key")
def test_llm_success(mock_key, mock_call):
    mock_call.return_value = (
        "일봉 추세는 상승이며 MA는 정배열입니다. "
        "대파동·소파동 모두 중립 구간에 있고 변곡 형성 중 패턴은 없습니다."
    )
    report = _minimal_report()
    radar = TransitionRadarContent(None, [], None)
    result = generate_narration(report, "정배열", radar, "2024-01-30")
    assert result.source == "llm"
    assert "상승" in result.body


@patch("requests.post")
def test_client_openai_compatible_response_shape(mock_post):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": "테스트 해설입니다."}}],
    }
    mock_post.return_value = resp
    text = call_openai_compatible_chat(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "hi"}],
        api_key="k",
    )
    assert text == "테스트 해설입니다."
    url = mock_post.call_args[0][0]
    assert url.endswith("/chat/completions")


@patch("requests.post")
def test_client_429_raises_rate_limit(mock_post):
    resp = MagicMock()
    resp.status_code = 429
    resp.json.return_value = {"error": {"message": "RESOURCE_EXHAUSTED"}}
    mock_post.return_value = resp
    with pytest.raises(NarrationRateLimitError):
        call_openai_compatible_chat(
            base_url="https://example.com/v1/",
            model="m",
            messages=[{"role": "user", "content": "x"}],
            api_key="k",
        )
