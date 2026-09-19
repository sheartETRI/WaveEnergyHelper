"""LW 차트 시간 표기(한국식 순서, KST 표시) — 포맷 함수 단위 테스트(node 로 실제 JS 실행) + 배선 + 표시 시프트."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import charts.lw_builder as LW  # noqa: E402

NODE = shutil.which("node")


def _run_js(script: str) -> list:
    if not NODE:
        pytest.skip("node 없음 — JS 포맷 함수 실행 불가")
    out = subprocess.run([NODE, "-e", LW.TIME_FORMAT_JS + "\n" + script],
                         capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


def _utc(y, mo, d, h=0, mi=0, s=0) -> int:
    return int(pd.Timestamp(year=y, month=mo, day=d, hour=h, minute=mi, second=s).timestamp())


# ------------------------------------------------------------ 툴팁(크로스헤어 시간 라벨)
def test_tooltip_hourly_and_minute_have_clock_daily_omits_it():
    t = _utc(2026, 5, 12, 0, 0)
    t2 = _utc(2026, 5, 12, 13, 5, 7)
    r = _run_js(f"var TOOLTIP_CLOCK = true; console.log(JSON.stringify([lwTooltipTime({t}), lwTooltipTime({t2})]));")
    assert r == ["2026-05-12 00:00", "2026-05-12 13:05"]          # 시간봉·분봉: 초 생략
    r = _run_js(f"var TOOLTIP_CLOCK = false; console.log(JSON.stringify([lwTooltipTime({t}), "
                "lwTooltipTime({year: 2026, month: 5, day: 12})]));")
    assert r == ["2026-05-12", "2026-05-12"]                      # 일봉 이상: 시:분 생략, BusinessDay 객체도 처리


@pytest.mark.parametrize("interval,clock", [("1m", True), ("15m", True), ("1h", True), ("4h", True), ("12h", True),
                                            ("1d", False), ("3d", False), ("1w", False), ("2w", False), ("1M", False)])
def test_tooltip_clock_rule_by_interval(interval, clock):
    assert LW.tooltip_shows_clock(interval) is clock


# ------------------------------------------------------------ 시간축 눈금(LW 밀도 단계 유지, 순서만 한국식)
def test_tick_marks_follow_lw_types_in_korean_order():
    t = _utc(2026, 5, 12, 13, 5, 7)
    r = _run_js(f"var TOOLTIP_CLOCK = true; console.log(JSON.stringify([0,1,2,3,4].map(function(k){{return lwTickMark({t}, k);}})));")
    assert r == ["2026", "2026-05", "05-12", "13:05", "13:05:07"]
    t0 = _utc(2026, 1, 1, 0, 0)
    r = _run_js(f"var TOOLTIP_CLOCK = true; console.log(JSON.stringify([lwTickMark({t0}, 0), lwTickMark({t0}, 1), lwTickMark({t0}, 2), lwTickMark({t0}, 3)]));")
    assert r == ["2026", "2026-01", "01-01", "00:00"]             # 0 패딩


# ------------------------------------------------------------ 시간대 불변 · 배선
def test_chart_tooltip_shows_kst_via_payload_shift():
    """naive 인덱스 = UTC(바이낸스 open_time). 차트는 PAYLOAD 시프트로 KST 벽시계를 찍는다(헬퍼 to_kst 와 동일값)."""
    from display.tz_label import to_kst
    ts = pd.Timestamp("2026-09-19 05:00")
    assert LW._unix_seconds(ts) == int(ts.timestamp())            # 데이터 규약(UTC) 자체는 불변
    assert LW._display_seconds(ts) == int(to_kst(ts).timestamp())  # 시프트 = 헬퍼 1곳
    r = _run_js(f"var TOOLTIP_CLOCK = true; console.log(JSON.stringify([lwTooltipTime({LW._display_seconds(ts)})]));")
    assert r == ["2026-09-19 14:00"]                              # 차트 툴팁 = KST


def _ohlc(n=30):
    idx = pd.date_range("2026-09-01", periods=n, freq="h")
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx)


def test_html_wires_formatters_and_interval_flag():
    html = LW.build_lw_html(_ohlc(), "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    assert "var TOOLTIP_CLOCK = true;" in html and 'var INTERVAL = "1h";' in html
    assert "function lwTooltipTime" in html and "function lwTickMark" in html
    assert "timeFormatter: lwTooltipTime" in html and "tickMarkFormatter: lwTickMark" in html
    daily = LW.build_lw_html(_ohlc(), "BTCUSDT", "1d", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    assert "var TOOLTIP_CLOCK = false;" in daily
    # LW 시간대 옵션·tz 객체 없이 PAYLOAD 시프트만 쓴다
    assert "timezone" not in html.lower() and "Asia/Seoul" not in html
    assert "(KST)" in html
