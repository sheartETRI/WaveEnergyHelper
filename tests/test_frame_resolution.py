"""프레임 계층 해석(resolve_upper_frame / resolve_lower_frame) 회귀 테스트.

확정 규칙: 명시 맵 → ×4(존재 시) → ×6(존재 시) → None.
실행: `python -m pytest tests/test_frame_resolution.py` 또는 `python tests/test_frame_resolution.py`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.wave_energy import resolve_lower_frame, resolve_upper_frame

# 상위 프레임 회귀 테이블 (검토자 확정)
UPPER_CASES = {
    "5m": "30m",
    "15m": "1h",
    "30m": "2h",
    "1h": "4h",
    "2h": "8h",
    "3h": "12h",
    "4h": "1d",
    "6h": "1d",
    "8h": "2d",
    "12h": "2d",
    "1d": "4d",
    "4d": "2w",
    "2w": "1M",
    # None
    "1m": None,
    "3m": None,
    "2d": None,
    "3d": None,
    "1w": None,
    "1M": None,
}

LOWER_CASES = {
    "2h": "30m",
    "30m": "5m",
    "12h": "3h",
    "2d": "12h",
    "1h": "15m",
    "4h": "1h",
    "1d": "4h",
    "4d": "1d",
    "1M": "2w",
}


def test_resolve_upper_frame_regression():
    for interval, expected in UPPER_CASES.items():
        assert resolve_upper_frame(interval) == expected, (
            f"resolve_upper_frame({interval!r}) -> {resolve_upper_frame(interval)!r}, expected {expected!r}"
        )


def test_resolve_lower_frame_regression():
    for interval, expected in LOWER_CASES.items():
        assert resolve_lower_frame(interval) == expected, (
            f"resolve_lower_frame({interval!r}) -> {resolve_lower_frame(interval)!r}, expected {expected!r}"
        )


def test_core_asserts():
    assert resolve_upper_frame("30m") == "2h"
    assert resolve_upper_frame("5m") == "30m"
    assert resolve_upper_frame("1d") == "4d"
    assert resolve_lower_frame("2h") == "30m"
    assert resolve_lower_frame("30m") == "5m"
    assert resolve_lower_frame("12h") == "3h"
    assert resolve_lower_frame("2d") == "12h"
    assert resolve_lower_frame("1d") == "4h"


if __name__ == "__main__":
    test_resolve_upper_frame_regression()
    test_resolve_lower_frame_regression()
    test_core_asserts()
    print("ALL FRAME RESOLUTION TESTS PASSED")
