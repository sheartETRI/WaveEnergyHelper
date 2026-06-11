"""Wave Generalization UI Playwright."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wave_generalization_ui")
APP_URL = os.environ.get("WAVE_APP_URL", "http://localhost:8501")
TARGETS = [("ETHUSDT", "4h"), ("BTCUSDT", "1d")]


def run_screenshots(base_url: str = APP_URL) -> list[str]:
    from playwright.sync_api import sync_playwright

    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for symbol, interval in TARGETS:
            page = browser.new_page(viewport={"width": 1400, "height": 1200})
            page.goto(base_url, wait_until="networkidle", timeout=120_000)
            for label, val in [("Symbol", symbol), ("Timeframe", interval)]:
                c = page.locator(f'[aria-label*="{label}"]').first
                c.click()
                page.get_by_role("option", name=val, exact=True).click()
                page.wait_for_timeout(800)
            page.wait_for_timeout(15000)
            sb = page.locator('[data-testid="stSidebar"]')
            cb = page.locator('[aria-label="Show Generalization"]')
            if not cb.is_checked():
                sb.get_by_text("Show Generalization", exact=True).click()
            page.wait_for_timeout(2000)
            page.locator('[data-testid="stMainBlockContainer"]').get_by_text(
                "Generalization", exact=True,
            ).wait_for(timeout=180_000)
            fpath = os.path.join(OUT_DIR, f"{symbol}_{interval}_generalization_on.png")
            page.screenshot(path=fpath, full_page=True)
            paths.append(fpath)
            print(os.path.basename(fpath))
            page.close()
        browser.close()
    return paths


def main():
    print(f"saved {len(run_screenshots())} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
