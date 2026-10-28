"""화면과 외부 알림에서 공유하는 적재·문구의 동작과 UI 의존 분리를 검증한다."""
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from data import frames
from notify import legacy_signals


def _klines(n=480):
    first = pd.Timestamp("2024-01-01").value // 1_000_000
    step = 3_600_000
    rows = []
    for i in range(n):
        price = 100 + i * 0.02 + np.sin(i / 7)
        timestamp = first + i * step
        rows.append([timestamp, str(price), str(price + 1), str(price - 1), str(price),
                     "1", timestamp + step - 1, "0", 1, "0", "0", "0"])
    return rows


def test_optional_macd_keeps_same_price_and_other_indicators(monkeypatch):
    monkeypatch.setattr(frames, "fetch_klines", lambda *args: _klines())
    full = frames.load_frame("SYN", "1h")
    minimal = frames.load_frame("SYN", "1h", with_macd=False)
    assert len(full) == len(minimal) == 480
    assert "macd" in full and not any(c.startswith("macd") for c in minimal.columns)
    assert {"MA60", "rsi"}.issubset(minimal.columns)
    pd.testing.assert_frame_equal(full[list(minimal.columns)], minimal)


def test_custom_interval_fetches_base_and_preserves_ohlcv_aggregation(monkeypatch):
    raw = _klines()
    calls = []
    monkeypatch.setattr(frames, "fetch_klines", lambda *args: calls.append(args) or raw)
    out = frames.load_frame("SYN", "3h")
    assert calls[0][:2] == ("SYN", "1h")
    assert len(out) == 160
    assert (out.index.to_series().diff().dropna() == pd.Timedelta(hours=3)).all()
    assert out["volume"].sum() == 480
    assert out["close"].iloc[-1] == pytest.approx(float(raw[-1][4]))


@pytest.mark.parametrize("raw", [None, []])
def test_empty_source_does_not_produce_indicators(monkeypatch, raw):
    monkeypatch.setattr(frames, "fetch_klines", lambda *args: raw)
    assert frames.load_frame("SYN", "1h") is None


def test_legacy_loader_uses_shared_frame_and_rejects_stale_data(monkeypatch):
    frame = pd.DataFrame({"close": [100.0]})
    calls = []
    monkeypatch.setattr(legacy_signals, "clear_klines_cache", lambda: calls.append("clear"))
    monkeypatch.setattr(frames, "load_frame", lambda symbol, interval, with_macd: calls.append(
        (symbol, interval, with_macd)) or frame)
    monkeypatch.setattr(legacy_signals, "served_from_stale_store", lambda *args: False)
    assert legacy_signals.default_loader("SYN", "1h") is frame
    assert calls == ["clear", ("SYN", "1h", True)]
    monkeypatch.setattr(legacy_signals, "served_from_stale_store", lambda *args: True)
    assert legacy_signals.default_loader("SYN", "1h") is None


def test_legacy_path_runs_without_loading_ui_modules():
    code = '''
import sys
from data import frames
from notify import legacy_signals
frames.load_frame = lambda *a, **k: None
legacy_signals.clear_klines_cache = lambda: None
legacy_signals.served_from_stale_store = lambda *a: False
assert legacy_signals.default_loader("SYN", "1h") is None
assert "main" not in sys.modules
assert not any(name.startswith("display.") for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_existing_frame_and_text_imports_are_same_shared_functions():
    import main
    from display import alarm_panel
    from utils import alarm_text
    assert main.load_frame is frames.load_frame
    assert alarm_panel.format_signal_line is alarm_text.format_signal_line
    assert alarm_panel.signal_icon is alarm_text.signal_icon
