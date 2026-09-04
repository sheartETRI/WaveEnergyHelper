"""UI 마감 테스트 — display 계층 전용.

강제 항목:
- 항목 2: 파동 문구 렌더 함수가 게이트 컨텍스트 인자 없이 호출되면 실패한다
  (단독 표시 경로가 남지 않음).
- 항목 5: 성과 지표(G·Δ·수익률·승률)가 UI 경로로 노출되지 않는다.
"""
import inspect
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import display.wave_gate_context as CTX
import display.wave_gate_panel_ui as PANEL
from analysis.wave_align_gate_forward import PROMOTED_LTF_TO_HTF, REVIEW_DUE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------- 항목 2 강제: 게이트 병기 없이 렌더 불가
def test_wave_summary_requires_gate_context():
    import main

    sig = inspect.signature(main.render_wave_summary)
    assert "gate_context" in sig.parameters
    p = sig.parameters["gate_context"]
    assert p.default is inspect.Parameter.empty, "게이트 컨텍스트는 기본값이 없어야 한다"

    with pytest.raises(TypeError):
        main.render_wave_summary(object(), "정배열")   # 인자 누락 → 실패


def test_wave_narration_requires_gate_context():
    import main

    for fn in (main.render_wave_narration, main.render_wave_narration_if_enabled):
        params = inspect.signature(fn).parameters
        assert "gate_context" in params, fn.__name__
        assert params["gate_context"].default is inspect.Parameter.empty, fn.__name__

    with pytest.raises(TypeError):
        main.render_wave_narration(object(), "정배열", None, None)


def test_verdict_line_embeds_the_gate_label():
    """문구 렌더가 게이트 라벨을 실제로 같이 출력하는지 (소스 수준 확인)."""
    src = inspect.getsource(__import__("main").render_wave_summary)
    assert "{report.verdict}" in src and "{gate_context}" in src


def test_gate_label_shapes():
    rows = [
        {"symbol": "BTCUSDT", "htf": "1d", "gate_align": False,
         "open_bars": 0, "open_rate_recent": 0.0},
        {"symbol": "ETHUSDT", "htf": "4h", "gate_align": True,
         "open_bars": 7, "open_rate_recent": 0.71},
    ]
    closed = CTX.gate_label("BTCUSDT", "6h", rows)      # 6h → 1d
    assert closed.startswith("[1d 게이트 폐쇄")
    opened = CTX.gate_label("ETHUSDT", "1h", rows)      # 1h → 4h
    assert opened == "[4h 게이트 개방 7봉]"
    assert CTX.gate_label("BTCUSDT", "1d", rows) == "[게이트 미적용 TF]"
    assert CTX.gate_label("SOLUSDT", "1h", rows) == "[4h 게이트 상태 불명]"


def test_gate_label_never_uses_directive_language():
    rows = [{"symbol": "BTCUSDT", "htf": "1d", "gate_align": True,
             "open_bars": 3, "open_rate_recent": 0.5}]
    for tf in ("1h", "6h", "1d", "4h"):
        label = CTX.gate_label("BTCUSDT", tf, rows)
        for banned in ("매수", "매도", "권고", "진입 시점", "목표가"):
            assert banned not in label


# ------------------------------------------- 항목 5 강제: 성과 지표 미노출
PERF_TOKENS = ("growth", "net_mean", "win_rate", "expectancy", "profit_factor",
               "delta_sharpe", "variant_summary", "sharpe")

DISPLAY_FILES = (
    "display/wave_gate_context.py",
    "display/wave_gate_panel_ui.py",
    "display/wave_live_watchlist_ui.py",
)


def test_display_layer_never_imports_performance_reporters():
    """--peek 류 성과 출력이 UI 경로로 새지 않음을 소스에서 강제."""
    for rel in DISPLAY_FILES:
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for token in PERF_TOKENS:
            assert token not in src, f"{rel} 에 성과 지표 경로({token})가 있다"
        assert "wave_mm_shadow_sweep" not in src, rel


def test_tracking_counts_returns_no_performance_fields():
    t = CTX.tracking_counts()
    keys = set(t)
    for banned in ("growth", "delta", "net_mean_pct", "win_rate", "stop_rate",
                   "expectancy", "sharpe"):
        assert banned not in keys, banned
    assert t["review_due"] == REVIEW_DUE
    assert "shadow_by_variant" in t and "gate_rows" in t


def test_tracking_panel_source_has_no_performance_metric():
    src = inspect.getsource(PANEL.render_tracking_status)
    for banned in PERF_TOKENS:
        assert banned not in src
    assert "행" in src and "열람일" in src


# ------------------------------------------------------------ 항목 6 신선도
def test_freshness_flags_lag_beyond_two_bars():
    now = pd.Timestamp("2026-09-04 12:00")
    fresh = CTX.freshness("1h", pd.Timestamp("2026-09-04 11:30"), now)
    assert fresh["warn"] is False
    stale = CTX.freshness("1h", pd.Timestamp("2026-09-04 08:00"), now)
    assert stale["warn"] is True
    assert stale["lag_bars"] == pytest.approx(4.0)


def test_freshness_missing_bar_is_warned():
    f = CTX.freshness("1h", None)
    assert f["warn"] is True
    assert f["last_bar"] is None
    assert CTX.format_lag(None) == "—"


def test_format_lag_shapes():
    assert CTX.format_lag(pd.Timedelta(minutes=30)) == "30분"
    assert CTX.format_lag(pd.Timedelta(hours=5, minutes=2)) == "5시간 2분"
    assert CTX.format_lag(pd.Timedelta(days=2, hours=3)) == "2일 3시간"


# ------------------------------------------------------------ 항목 3 뱃지·주석
def test_profile_note_is_fixed_and_has_no_expectancy_number():
    note = CTX.GATE_PROFILE_NOTE
    assert "에피소드 과반" in note and "in-sample" in note
    for banned in ("0.70", "0.6982", "%", "기대값"):
        assert banned not in note


def test_watchlist_badge_labels_are_state_descriptive():
    from display.wave_live_watchlist_ui import _gate_badge

    rows = [{"symbol": "BTCUSDT", "htf": "4h", "gate_align": True},
            {"symbol": "ETHUSDT", "htf": "1d", "gate_align": False}]
    assert "게이트 통과" in _gate_badge("BTCUSDT", "1h", rows)
    assert "게이트 비통과" in _gate_badge("ETHUSDT", "6h", rows)
    assert "미적용" in _gate_badge("BTCUSDT", "1d", rows)
    for tf in ("1h", "6h", "1d"):
        badge = _gate_badge("BTCUSDT", tf, rows)
        assert "매수" not in badge and "권고" not in badge


# ------------------------------------------------------------ 항목 4 기준선
def test_struct_line_label_is_not_directive():
    assert CTX.STRUCT_LINE_LABEL == "패턴 저점 기준선 (검증 중)"
    assert "손절" not in CTX.STRUCT_LINE_LABEL
    assert CTX.STRUCT_LINE_MISSING == "기준선 없음"


def test_chart_accepts_struct_reference_and_skips_when_none():
    from charts.plotly_builder import _add_struct_reference_lines, render_chart

    assert "struct_reference" in inspect.signature(render_chart).parameters

    class _Fig:
        def __init__(self):
            self.lines = []

        def add_hline(self, **kw):
            self.lines.append(kw)

    fig = _Fig()
    _add_struct_reference_lines(fig, {"reference_low": None, "line_price": None})
    assert fig.lines == []

    _add_struct_reference_lines(fig, {"reference_low": 100.0, "line_price": 99.5})
    assert len(fig.lines) == 2
    texts = [l["annotation_text"] for l in fig.lines]
    assert CTX.STRUCT_LINE_LABEL in texts
    assert all("손절 권고" not in t for t in texts)


def test_promoted_htf_gating_for_reference_line():
    assert CTX.promoted_htf_available("1h") is True
    assert CTX.promoted_htf_available("6h") is True
    assert CTX.promoted_htf_available("1d") is False
    assert CTX.promoted_htf("1h") == PROMOTED_LTF_TO_HTF["1h"]


# ------------------------------------------------------------ 항목 1 패널 위치
def test_gate_panel_is_rendered_at_main_top_not_behind_a_toggle():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    body = src.split("def main():", 1)[1]
    call_pos = body.index("render_gate_panel()")
    sidebar_pos = body.index("# --- Sidebar ---")
    assert call_pos < sidebar_pos, "게이트 패널은 사이드바보다 먼저 렌더돼야 한다"
    # 토글 뒤에 숨지 않는다
    assert "if show_" not in body[max(0, call_pos - 200):call_pos]


def test_no_order_or_trading_hooks_in_display_layer():
    for rel in DISPLAY_FILES + ("main.py", "charts/plotly_builder.py"):
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for banned in ("place_order", "create_order", "submit_order", "api_secret"):
            assert banned not in src, f"{rel}: {banned}"
