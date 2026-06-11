"""Wave Outcome UI Playwright 스크린샷."""

from __future__ import annotations



import os

import sys

import time



sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wave_outcome_ui")

APP_URL = os.environ.get("WAVE_APP_URL", "http://localhost:8501")

TARGETS = [("ETHUSDT", "4h"), ("BTCUSDT", "1d")]





def _select(page, label_substr: str, value: str) -> None:

    combo = page.locator(

        f'[aria-label*="Select {label_substr}"], [aria-label*="{label_substr}"]'

    ).first

    combo.click()

    page.get_by_role("option", name=value, exact=True).click()

    page.wait_for_timeout(800)





def _ensure_outcome_on(page) -> None:

    sidebar = page.locator('[data-testid="stSidebar"]')

    cb = page.locator('[aria-label="Show Wave Outcome"]')

    if not cb.is_checked():

        sidebar.get_by_text("Show Wave Outcome", exact=True).click()

    page.wait_for_timeout(2000)





def run_screenshots(base_url: str = APP_URL) -> list[str]:

    from playwright.sync_api import sync_playwright



    os.makedirs(OUT_DIR, exist_ok=True)

    paths: list[str] = []



    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        for symbol, interval in TARGETS:

            page = browser.new_page(viewport={"width": 1400, "height": 1200})

            page.goto(base_url, wait_until="networkidle", timeout=120_000)

            _select(page, "Symbol", symbol)

            _select(page, "Timeframe", interval)

            page.wait_for_timeout(15000)

            _ensure_outcome_on(page)

            page.locator('[data-testid="stMainBlockContainer"]').get_by_text(

                "Wave Outcome", exact=True,

            ).wait_for(timeout=180_000)

            page.wait_for_timeout(2000)

            fname = f"{symbol}_{interval}_wave_outcome_on.png"

            fpath = os.path.join(OUT_DIR, fname)

            page.screenshot(path=fpath, full_page=True)

            paths.append(fpath)

            print(fname)

            page.close()

        browser.close()

    return paths





def main():

    t0 = time.perf_counter()

    paths = run_screenshots()

    print(f"saved {len(paths)} -> {OUT_DIR} ({time.perf_counter()-t0:.1f}s)")





if __name__ == "__main__":

    main()


