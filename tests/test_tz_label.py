"""시각 표기 UTC 라벨 — 차트 캡션·알람 탭(마지막 봉·이력 표 헤더)이 같은 라벨을 쓰고, 시간대 변환은 없다."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import charts.lw_builder as LW  # noqa: E402
import display.alarm_panel as AP  # noqa: E402
from display.tz_label import UTC_LABEL  # noqa: E402


def _ohlc(n=30):
    idx = pd.date_range("2026-09-19 00:00", periods=n, freq="h")
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx)


def test_label_is_single_constant_used_by_chart_and_alarm_tab():
    assert UTC_LABEL == "(UTC)"
    html = LW.build_lw_html(_ohlc(), "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    caption = html.split('id="lw-caption"', 1)[1].split("</div>", 1)[0]
    assert caption.rstrip().endswith(UTC_LABEL)                                  # 캡션 끝 = (UTC)
    assert AP.build_bar_caption(_ohlc()) == f"마지막 봉 2026-09-20 05:00 {UTC_LABEL} (미확정 가능)  ·  종가 110"
    assert AP.HISTORY_TIME_HEADER == f"시각 {UTC_LABEL}"
    src = open(AP.__file__, encoding="utf-8").read()
    assert 'col_bar.metric(f"마지막 봉 {UTC_LABEL}"' in src
    assert "DatetimeColumn(HISTORY_TIME_HEADER" in src
    # 두 모듈 모두 상수를 import 해 쓴다(문자열 하드코딩 없음)
    assert "from display.tz_label import UTC_LABEL" in src
    assert "from display.tz_label import UTC_LABEL" in open(LW.__file__, encoding="utf-8").read()


def test_no_timezone_conversion_anywhere():
    df = _ohlc()
    assert LW._unix_seconds(df.index[-1]) == int(df.index[-1].timestamp())      # naive = UTC, 이동 없음
    html = LW.build_lw_html(df, "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    assert "Asia/Seoul" not in html and "tz_convert" not in open(AP.__file__, encoding="utf-8").read()
    frame = pd.DataFrame({"시각": [pd.Timestamp("2026-09-19 05:00")]})
    assert "시각" in frame.columns and AP.filter_history_frame(frame).equals(frame)   # 컬럼 키 불변
