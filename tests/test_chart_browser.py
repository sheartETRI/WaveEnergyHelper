"""분리된 차트 템플릿의 브라우저 렌더·집중 보기·확대 동작을 합성 데이터로 검증."""
import pytest

pytestmark = pytest.mark.browser


def test_chart_panels_zoom_and_focus_in_browser(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    from charts.lw_builder import build_lw_html
    from test_slim_app_smoke import _pipeline_frame

    html = build_lw_html(_pipeline_frame(), "BTCUSDT", "1h", "[검증 게이트]", chart_height=900)
    path = tmp_path / "chart.html"
    path.write_text(html, encoding="utf-8")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        page.goto(path.as_uri())
        page.wait_for_function("window.__lw && window.__lw.chart.panes().length === 4")
        assert page.locator("#lw-chart canvas").count() >= 4
        assert "BTCUSDT" in page.locator("#lw-caption").inner_text()
        page.locator('#lw-solo button[data-kind="stoch"]').click()
        assert page.evaluate("window.__lw.solo.kind") == "stoch"
        page.locator('#lw-solo button[data-kind="all"]').click()
        assert page.evaluate("window.__lw.solo.kind") == "all"
        before = page.evaluate("window.__lw.chart.timeScale().getVisibleLogicalRange()")
        page.mouse.move(600, 400)
        page.mouse.wheel(0, -250)
        page.wait_for_function("(before) => { const r = window.__lw.chart.timeScale().getVisibleLogicalRange(); return r.to-r.from < before.to-before.from; }", arg=before)
        page.mouse.move(700, 200)
        page.wait_for_function("document.getElementById('lw-ohlc').textContent.length > 0")
        assert not errors, errors
        browser.close()
