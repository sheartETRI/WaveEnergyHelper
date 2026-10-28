"""고정 원본과 추출한 계산을 같은 입력·절단 시점에서 비교한다."""
import importlib
import logging
import warnings

import numpy as np
import pytest

from tracking import signals, ma60_turn
from test_ma60_down_tracker import _pipeline, _raw


@pytest.mark.parametrize("seed", [7, 11, 23])
def test_signal_extraction_matches_frozen_probe(seed):
    before_disable, before_filters = logging.root.manager.disable, warnings.filters[:]
    try:
        original = importlib.import_module("validation.wave_ma60_turn_probe")
    finally:
        logging.disable(before_disable)
        warnings.filters[:] = before_filters
    assert (signals.OBS_BARS, signals.BUFFER, signals.STOCH_LAG, signals.MA_LAG, signals.LARGE) == (
        original.OBS_BARS, original.BUFFER, original.STOCH_LAG, original.MA_LAG, original.LARGE)
    pipe = ma60_turn.tracker_pipe(_pipeline(_raw(n=1600, seed=seed)))
    for n in (400, 999, 1600):
        expected, actual = original.extract_signals(pipe.iloc[:n]), signals.extract_signals(pipe.iloc[:n])
        assert actual.keys() == expected.keys()
        for key in actual:
            if isinstance(actual[key], np.ndarray):
                np.testing.assert_array_equal(actual[key], expected[key])
            else:
                assert actual[key] == expected[key]


def test_shared_import_does_not_run_validation_or_change_logging():
    import subprocess
    import sys
    code = '''
import logging, warnings, sys
from tracking import ma60_turn, ma60_down, divergence, structure
assert "validation.wave_ma60_turn_probe" not in sys.modules
before = logging.root.manager.disable, list(warnings.filters)
import importlib
for mod in (ma60_turn, ma60_down, divergence, structure):
    importlib.reload(mod)
assert before == (logging.root.manager.disable, list(warnings.filters))
from notify import events, ledger
assert not any(name.startswith("display.") for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
