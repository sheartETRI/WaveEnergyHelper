"""LW 크로스헤어 상시 표시 + 커서 봉 정보 오버레이(#lw-ohlc) — 옵션·배선·캡션 겹침 회피. 정의 무접촉."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import charts.lw_builder as LW  # noqa: E402


def _ohlc(n=30):
    idx = pd.date_range("2026-09-01", periods=n, freq="h")
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0}, index=idx)


def test_crosshair_is_normal_mode_with_lines_and_axis_labels():
    ch = LW.chart_options()["crosshair"]
    assert ch["mode"] == 0                                             # Normal (Magnet=1 아님)
    assert ch["vertLine"] == {"visible": True, "labelVisible": True}
    assert ch["horzLine"] == {"visible": True, "labelVisible": True}


def test_html_has_info_overlay_below_caption_and_subscribes_crosshair():
    html = LW.build_lw_html(_ohlc(), "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    assert 'id="lw-ohlc"' in html and f"top:{6 + LW.OHLC_OVERLAY_OFFSET_PX}px" in html   # 캡션(top 6px) 아래
    assert "chart.subscribeCrosshairMove(" in html and "renderInfo(lastTime)" in html   # 커서 밖 = 마지막 봉
    assert "candles.priceFormatter().format" in html                    # 축과 같은 가격 포맷
    assert "시 ' + fmtPrice(c.open)" in html and "' 저 ' + fmtPrice(c.low)" in html
    assert "toFixed(2) + '%'" in html                                   # 직전 종가 대비 변화율
    assert "'스토캐 K '" in html and "'MACD '" in html and "'RSI '" in html   # 하위 pane 값도 같은 오버레이
    assert f"var OHLC_OFFSET = {LW.OHLC_OVERLAY_OFFSET_PX};" in html
    assert "getElementById('lw-ohlc').style.top = (overlayTop + OHLC_OFFSET)" in html   # 단독 모드에서도 캡션 따라 이동


def test_overlay_uses_candle_color_tokens_not_hardcoded():
    html = LW.build_lw_html(_ohlc(), "BTCUSDT", "1h", "[게이트 미적용 TF]", chart_height=600, vendor_js="")
    assert "CANDLE_OPTS.upColor : CANDLE_OPTS.downColor" in html
