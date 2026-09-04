"""렌더 호출-시그니처 정합 회귀 테스트 (display 전용).

(a) display 계층에서 호출하는 렌더 함수의 kwargs·위치인자·필수인자가 실제
    시그니처와 맞는지 전수 확인 — struct_reference 류 시그니처 불일치 재발 방지.
(b) 페이지 렌더 경로 스모크 — 승격 TF(6h)와 비승격 TF(1d/4h)에서 예외 없이 완주.
"""
import ast
import importlib
import inspect
import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 시그니처를 대조할 대상 모듈 접두사 (서드파티는 제외)
OWN_PREFIXES = ("display", "charts", "analysis", "narration", "indicators")


def _scan_targets() -> list[str]:
    targets = ["main.py", "charts/plotly_builder.py"]
    targets += [
        f"display/{f}" for f in sorted(os.listdir(os.path.join(ROOT, "display")))
        if f.endswith(".py") and f != "__init__.py"
    ]
    return targets


def _imported_symbols(tree: ast.Module) -> dict:
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                out[alias.asname or alias.name] = (node.module, alias.name)
    return out


def _check_file(rel: str) -> tuple[int, list[str]]:
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    tree = ast.parse(src)
    syms = _imported_symbols(tree)
    problems: list[str] = []
    checked = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in syms:
            continue
        mod_name, orig = syms[name]
        if not mod_name.startswith(OWN_PREFIXES):
            continue
        try:
            fn = getattr(importlib.import_module(mod_name), orig)
            sig = inspect.signature(fn)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{rel}:{node.lineno} {name}() 해석 실패: {exc}")
            continue
        if not callable(fn):
            continue

        checked += 1
        params = sig.parameters
        has_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
        has_varargs = any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params.values())
        positional = [p for p in params.values()
                      if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                    inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        supplied = {kw.arg for kw in node.keywords if kw.arg}

        for kw in node.keywords:
            if kw.arg and kw.arg not in params and not has_kwargs:
                problems.append(f"{rel}:{node.lineno} {name}() 알 수 없는 kwarg: {kw.arg}")
        if not has_varargs and len(node.args) > len(positional):
            problems.append(
                f"{rel}:{node.lineno} {name}() 위치인자 초과: "
                f"{len(node.args)} > {len(positional)}")
        for i, p in enumerate(positional):
            if p.default is not inspect.Parameter.empty:
                continue
            if i < len(node.args) or p.name in supplied:
                continue
            problems.append(f"{rel}:{node.lineno} {name}() 필수 인자 누락: {p.name}")
    return checked, problems


# ------------------------------------------------------------------ (a)
def test_all_render_calls_match_their_signatures():
    """호출-시그니처 전수 정합. 새 파라미터를 호출부에만/정의에만 넣는 실수를 잡는다."""
    total, problems = 0, []
    for rel in _scan_targets():
        c, p = _check_file(rel)
        total += c
        problems.extend(p)
    assert total > 50, f"스캔 대상이 너무 적다 ({total}) — 스캐너가 망가졌을 수 있다"
    assert not problems, "호출-시그니처 불일치:\n" + "\n".join(problems)


def test_render_chart_exposes_struct_reference():
    """이번 버그의 대상 파라미터가 시그니처에 실제로 있고 기본값이 None 이다."""
    from charts.plotly_builder import render_chart

    p = inspect.signature(render_chart).parameters
    assert "struct_reference" in p
    assert p["struct_reference"].default is None


def test_scanner_detects_an_injected_mismatch():
    """스캐너 역확인 — 없는 kwarg 를 넣은 소스를 실제로 잡아내는지."""
    src = (
        "from charts.plotly_builder import render_chart\n"
        "render_chart(df, 'BTCUSDT', '6h', no_such_param=1)\n"
    )
    tree = ast.parse(src)
    syms = _imported_symbols(tree)
    assert "render_chart" in syms
    from charts.plotly_builder import render_chart

    params = inspect.signature(render_chart).parameters
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
    unknown = [kw.arg for kw in call.keywords if kw.arg not in params]
    assert unknown == ["no_such_param"]


# ------------------------------------------------------------------ (b)
def _frame(freq: str, n: int = 300) -> pd.DataFrame:
    from indicators.moving_averages import add_moving_averages

    idx = pd.date_range("2026-01-01", periods=n, freq=freq)
    c = 100 + np.cumsum(np.random.default_rng(0).normal(0, 1, n))
    df = pd.DataFrame(
        {"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx,
    )
    df.index.name = "open_time"
    return add_moving_averages(df)


def _mock_st() -> MagicMock:
    """streamlit 대역. columns/tabs 는 언패킹되므로 실제 길이의 리스트를 돌려준다."""
    st = MagicMock()

    def _n(spec):
        return spec if isinstance(spec, int) else len(spec)

    st.columns.side_effect = lambda spec, **kw: [MagicMock() for _ in range(_n(spec))]
    st.tabs.side_effect = lambda labels, **kw: [MagicMock() for _ in labels]
    return st


_GATE_ROWS = [
    {"symbol": s, "htf": h, "gate_align": h == "4h", "open_bars": 3 if h == "4h" else 0,
     "open_rate_recent": 0.7 if h == "4h" else 0.0,
     "htf_open_time": pd.Timestamp("2026-09-03")}
    for s in ("BTCUSDT", "ETHUSDT", "BNBUSDT") for h in ("1d", "4h")
]


@pytest.mark.parametrize("interval,freq", [("6h", "6h"), ("1h", "1h"),
                                           ("1d", "1D"), ("4h", "4h")])
def test_page_render_path_smoke(interval, freq):
    """승격 TF(1h·6h)와 비승격 TF(1d·4h) 모두에서 렌더 경로가 예외 없이 완주한다."""
    import display.wave_gate_context as CTX
    import display.wave_gate_panel_ui as PANEL
    from charts.plotly_builder import render_chart

    df = _frame(freq)
    ref = ({"reference_low": float(df["low"].min()),
            "line_price": float(df["low"].min()) * 0.995}
           if CTX.promoted_htf_available(interval) else None)

    with patch.object(CTX, "gate_rows", lambda: _GATE_ROWS), \
         patch.object(PANEL, "gate_rows", lambda: _GATE_ROWS), \
         patch("display.wave_gate_panel_ui.st", _mock_st()), \
         patch("charts.plotly_builder.st", _mock_st()):
        PANEL.render_gate_panel()
        PANEL.render_tracking_status()
        PANEL.render_data_freshness("BTCUSDT", interval, df)
        label = CTX.gate_label("BTCUSDT", interval, _GATE_ROWS)
        assert label.startswith("[") and label.endswith("]")
        render_chart(df, "BTCUSDT", interval, struct_reference=ref)


def test_wave_summary_render_path_smoke():
    """파동 요약도 게이트 컨텍스트를 받아 예외 없이 렌더된다."""
    import main
    from analysis.wave_energy import TrendState, WaveEnergyReport, WaveState

    report = WaveEnergyReport(
        symbol="BTCUSDT", interval="6h",
        trend=TrendState(direction="상승", slope_pct=1.2, valid=True),
        base_large=WaveState(direction="상승", zone="중립", valid=True),
        base_small=WaveState(direction="상승", zone="중립", valid=True),
        upper_interval="1d",
        upper_small=WaveState(direction="상승", zone="중립", valid=True),
        mtf_agreement="일치", verdict="관망", notes=[], dynamics=None,
    )
    with patch("main.st", _mock_st()):
        main.render_wave_summary(report, "정배열", "[1d 게이트 폐쇄]")


def test_chart_renders_without_struct_reference():
    """기준선이 없는 경로(None)도 그대로 완주한다."""
    from charts.plotly_builder import render_chart

    df = _frame("1D")
    with patch("charts.plotly_builder.st", _mock_st()):
        render_chart(df, "BTCUSDT", "1d")
        render_chart(df, "BTCUSDT", "1d", struct_reference=None)
