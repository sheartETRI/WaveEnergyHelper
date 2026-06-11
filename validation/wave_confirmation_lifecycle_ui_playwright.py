"""Wave Lifecycle UI Playwright 스크린샷."""

from __future__ import annotations



import os

import sys

import time



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wave_confirmation_lifecycle_ui")

APP_URL = os.environ.get("WAVE_APP_URL", "http://localhost:8501")



TARGETS = [("ETHUSDT", "4h"), ("BTCUSDT", "1d")]





def _select_streamlit_option(page, label_substr: str, value: str) -> None:

    combo = page.locator(

        f'[aria-label*="Select {label_substr}"], [aria-label*="{label_substr}"]'

    ).first

    combo.click()

    page.get_by_role("option", name=value, exact=True).click()

    page.wait_for_timeout(500)





def _set_lifecycle(page, enabled: bool) -> None:

    sidebar = page.locator('[data-testid="stSidebar"]')

    sidebar.get_by_text("Show Wave Lifecycle", exact=True).click()

    cb = page.locator('[aria-label="Show Wave Lifecycle"]')

    if cb.is_checked() != enabled:

        sidebar.get_by_text("Show Wave Lifecycle", exact=True).click()

    page.wait_for_timeout(1500 if enabled else 800)





def run_screenshots(base_url: str = APP_URL) -> list[str]:

    from playwright.sync_api import sync_playwright



    os.makedirs(OUT_DIR, exist_ok=True)

    paths: list[str] = []



    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(viewport={"width": 1400, "height": 1200})

        page.goto(base_url, wait_until="networkidle", timeout=120_000)



        for symbol, interval in TARGETS:

            _select_streamlit_option(page, "Symbol", symbol)

            _select_streamlit_option(page, "Timeframe", interval)

            page.wait_for_timeout(8000)

            _set_lifecycle(page, True)

            page.locator('[data-testid="stMainBlockContainer"]').get_by_text(

                "Wave Lifecycle", exact=True,

            ).wait_for(timeout=120_000)

            page.wait_for_timeout(2000)

            fname = f"{symbol}_{interval}_wave_lifecycle_on.png"

            fpath = os.path.join(OUT_DIR, fname)

            page.screenshot(path=fpath, full_page=True)

            paths.append(fpath)

            print(fname)



        browser.close()

    return paths





def main():

    paths = run_screenshots()

    print(f"saved {len(paths)} -> {OUT_DIR}")





if __name__ == "__main__":

    main()


