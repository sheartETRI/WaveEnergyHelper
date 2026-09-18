"""LW 게이트 라벨·구조 기준선 공급 (display/lw_gate_context) — 체리픽 동일성 · 실공급 경로 · 폴백.

- 체리픽한 정의 파일 5개가 원본(origin/main 74fa4ad) 과 diff 없음 (매니페스트 sha256 + git blob 대조)
- gate_label: 개방/폐쇄/불명/미적용 TF 문구 (main 문구 승계), current_gate_status 위임(닫힌 봉 asof)
- struct_reference: 확정 swing 저점 → ×(1−BUFFER) 기준선, 미검출·퇴화·짧은 프레임 → None
"""
import hashlib
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import display.lw_gate_context as LGC  # noqa: E402
from analysis.wave_mm_struct_stop import BUFFER, REASON_DEGENERATE, REASON_NO_LOW, REASON_OK  # noqa: E402
from analysis.wave_structure_confirmation import PIVOT  # noqa: E402


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


# ------------------------------------------------------------ 체리픽 동일성
def test_cherrypicked_definition_files_match_manifest_and_origin():
    assert set(LGC.CHERRYPICK_FILES) == {
        "analysis/wave_htf_gate.py", "analysis/wave_htf_gate_v2.py", "analysis/wave_align_gate_forward.py",
        "analysis/wave_mm_struct_stop.py", "analysis/wave_mm_simulator.py",
    }
    for rel, sha in LGC.CHERRYPICK_FILES.items():
        with open(os.path.join(ROOT, rel), "rb") as fh:
            local = _norm(fh.read())
        assert hashlib.sha256(local).hexdigest() == sha, f"{rel} 가 매니페스트와 다르다 (수정 금지 파일)"
        try:
            blob = subprocess.run(
                ["git", "show", f"{LGC.CHERRYPICK_SOURCE_COMMIT}:{rel}"],
                cwd=ROOT, capture_output=True, check=True, timeout=30,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            pytest.skip("git 또는 원본 커밋을 읽을 수 없음 — 매니페스트 해시로만 확인")
        assert _norm(blob) == local, f"{rel} 가 원본 커밋 {LGC.CHERRYPICK_SOURCE_COMMIT} 과 diff 있음"


def test_glue_only_imports_definitions_and_touches_no_sidecar():
    src = open(LGC.__file__, encoding="utf-8").read()
    body = src.split('"""', 2)[2]        # 모듈 docstring(설명문) 제외 — 코드만 검사
    assert "from analysis.wave_align_gate_forward import PROMOTED_LTF_TO_HTF, current_gate_status" in body
    assert "from analysis.wave_mm_struct_stop import REASON_OK, struct_stops" in body
    for banned in ("sidecar_path", "read_csv", "validation", "mm_shadow", "load_shadow", "_htf_gate_v2_cache"):
        assert banned not in body, banned
    # 정의 재구현 없음: MA 기울기·swing 검출 코드가 글루에 없다
    assert "find_swing_lows" not in body and "shift(" not in body and "MA60" not in body


# ------------------------------------------------------------ gate_label
def test_gate_label_texts_follow_main_rules():
    assert LGC.gate_label("BTCUSDT", "15m") == "[게이트 미적용 TF]"
    assert LGC.gate_label("BTCUSDT", "4h") == "[게이트 미적용 TF]"          # 승격 쌍의 LTF 만 정의됨
    assert LGC.promoted_htf("1h") == "4h" and LGC.promoted_htf("6h") == "1d"
    assert LGC.gate_label("BTCUSDT", "1h", row={"gate_align": None}) == "[4h 게이트 상태 불명]"
    assert LGC.gate_label("BTCUSDT", "1h", row={"gate_align": True, "open_bars": 12}) == "[4h 게이트 개방 12봉]"
    assert LGC.gate_label("ETHUSDT", "6h", row={"gate_align": False, "open_rate_recent": 0.35}) \
        == "[1d 게이트 폐쇄 · 최근 120봉 개방률 35%]"
    assert LGC.gate_label("ETHUSDT", "6h", row={"gate_align": False}) == "[1d 게이트 폐쇄]"
    for text in (LGC.gate_label("BTCUSDT", "1h", row={"gate_align": True, "open_bars": 1}),):
        assert "매수" not in text and "매도" not in text and "권고" not in text


def test_gate_row_delegates_to_current_gate_status_for_one_cell(monkeypatch):
    calls = []

    def fake(symbols=(), htfs=()):
        calls.append((tuple(symbols), tuple(htfs)))
        return [{"symbol": "BTCUSDT", "htf": "4h", "gate_align": True, "open_bars": 7,
                 "open_rate_recent": 0.5, "htf_close_time": pd.Timestamp("2026-09-17 11:59:59.999")}]

    monkeypatch.setattr(LGC, "current_gate_status", fake)
    row = LGC._fetch_gate_row("BTCUSDT", "4h")
    assert calls == [(("BTCUSDT",), ("4h",))]           # 심볼×HTF 한 셀만
    assert row["gate_align"] is True and row["open_bars"] == 7
    assert LGC.gate_label("BTCUSDT", "1h", row=row) == "[4h 게이트 개방 7봉]"


def test_gate_row_failure_is_unknown_not_fabricated(monkeypatch):
    def boom(symbols=(), htfs=()):
        raise RuntimeError("network down")

    monkeypatch.setattr(LGC, "current_gate_status", boom)
    row = LGC._fetch_gate_row("BTCUSDT", "4h")
    assert row == {"symbol": "BTCUSDT", "htf": "4h", "gate_align": None}
    assert LGC.gate_label("BTCUSDT", "1h", row=row) == "[4h 게이트 상태 불명]"


def test_current_gate_status_uses_last_closed_bar():
    """체리픽한 current_gate_status 의 닫힌 봉 asof — 마지막 봉(진행 중) 이 아니라 직전 봉을 쓴다."""
    import analysis.wave_align_gate_forward as AGF

    n = 30
    idx = pd.date_range("2026-01-01", periods=n, freq="4h")
    rising = pd.DataFrame({f"MA{p}": np.arange(n, dtype=float) + p for p in (60, 120, 240)}, index=idx)
    rising.loc[idx[-1], "MA60"] = 0.0     # 마지막(진행 중) 봉만 게이트를 닫는 값
    original = AGF.load_htf_pipe
    AGF.load_htf_pipe = lambda sym, htf: rising
    try:
        rows = AGF.current_gate_status(symbols=("BTCUSDT",), htfs=("4h",))
    finally:
        AGF.load_htf_pipe = original
    assert rows[0]["gate_align"] is True            # 직전 닫힌 봉 기준 개방
    assert rows[0]["htf_open_time"] == idx[-2]
    assert rows[0]["open_bars"] == n - 2            # 첫 봉은 prev 없음 → False, 이후 연속 True (마지막 봉 제외)


# ------------------------------------------------------------ struct_reference
def _bars_with_swing_low(n=80, low_at=40, low_val=90.0, tail_level=100.0):
    """low_at 에서 뚜렷한 swing 저점, 이후 tail_level 근처에서 횡보 — PIVOT 뒤에 확정된다."""
    idx = pd.date_range("2026-01-01", periods=n, freq="h")
    close = np.full(n, tail_level)
    close[:low_at] = np.linspace(110, low_val + 2, low_at)
    close[low_at] = low_val + 0.5
    close[low_at + 1:] = np.linspace(low_val + 2, tail_level, n - low_at - 1)
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 0.5, "close": close}, index=idx)
    df.loc[idx[low_at], "low"] = low_val
    return df


def test_struct_reference_returns_confirmed_low_and_buffered_line():
    df = _bars_with_swing_low()
    ref = LGC.struct_reference(df, "BTCUSDT", "1h")
    assert ref is not None
    assert ref["reference_low"] == pytest.approx(90.0)
    assert ref["line_price"] == pytest.approx(90.0 * (1.0 - BUFFER))     # ×0.995
    assert BUFFER == 0.005
    assert pd.Timestamp(ref["reference_ts"]) == df.index[-2]              # 앵커 = 마지막 닫힌 봉


def test_struct_reference_fallbacks_to_none():
    # 짧은 프레임
    assert LGC.struct_reference(_bars_with_swing_low().iloc[:2], "BTCUSDT", "1h") is None
    assert LGC.struct_reference(None, "BTCUSDT", "1h") is None
    # 저점 미확정: 마지막 봉들이 계속 신저가 → 확정 swing 저점 없음 (PIVOT 이후 반등 없음)
    n = 40
    idx = pd.date_range("2026-01-01", periods=n, freq="h")
    down = np.linspace(120, 80, n)
    df = pd.DataFrame({"open": down, "high": down + 1, "low": down - 1, "close": down}, index=idx)
    assert LGC.struct_reference(df, "BTCUSDT", "1h") is None
    # 퇴화: 확정 저점은 있으나 진입가(마지막 봉 시가)가 기준선 아래 → DEGENERATE → None
    df2 = _bars_with_swing_low()
    df2.loc[df2.index[-1], ["open", "high", "low", "close"]] = [80.0, 81.0, 79.0, 80.0]
    assert LGC.struct_reference(df2, "BTCUSDT", "1h") is None
    assert {REASON_OK, REASON_NO_LOW, REASON_DEGENERATE} == {"STRUCT", "NO_REFERENCE_LOW", "DEGENERATE_ABOVE_ENTRY"}
    assert PIVOT == 3


def test_struct_reference_swallows_definition_errors(monkeypatch):
    monkeypatch.setattr(LGC, "struct_stops", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert LGC.struct_reference(_bars_with_swing_low(), "BTCUSDT", "1h") is None
