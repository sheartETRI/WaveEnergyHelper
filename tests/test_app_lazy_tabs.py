"""차트 첫 화면이 전체 TF 레이더를 실행하지 않는지 실제 AppTest로 확인한다."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import data.binance as B
import main
from display import analysis_cache
from test_page_render_smoke import _Resp, _synthetic_klines


def test_default_chart_skips_radars_and_alarm_tab_loads_them_on_selection(monkeypatch):
    import display.tf_radar_panel as radar
    import display.wave_basis_radar as basis
    calls, requests, responses = [], [], {}
    original_radar, original_basis = radar.render_tf_radar_section, basis.render_basis_radar_section

    def get(url, params=None, **kwargs):
        params = params or {}
        interval, limit = params.get("interval", "1h"), min(int(params.get("limit", 1000)), 1000)
        requests.append(interval)
        return _Resp(responses.setdefault((interval, limit), _synthetic_klines(interval, limit)))

    def render_radar(*args, **kwargs):
        calls.append("radar")
        return original_radar(*args, **kwargs)

    def render_basis(*args, **kwargs):
        calls.append("basis")
        return original_basis(*args, **kwargs)

    monkeypatch.setattr(B.requests, "get", get)
    monkeypatch.setattr(radar, "render_tf_radar_section", render_radar)
    monkeypatch.setattr(basis, "render_basis_radar_section", render_basis)
    analysis_cache.clear_analysis_cache()
    app = AppTest.from_file(str(Path(main.__file__)), default_timeout=180).run()
    assert not app.exception
    assert calls == []
    assert "1w" not in requests and "3d" not in requests and "12h" not in requests
    assert not app.code  # 복사 텍스트는 알람 탭에서만 생성
    app.session_state[main.ACTIVE_TAB_KEY] = "알람"
    app.run()
    assert not app.exception
    assert calls == ["radar", "basis"]
    assert any("전체" in e.label for e in app.expander)
    assert app.code
    calls.clear()
    app.session_state[main.ACTIVE_TAB_KEY] = "차트"
    app.run()
    assert not app.exception and calls == []
