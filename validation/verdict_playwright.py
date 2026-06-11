"""Playwright UI verdict 파리티 — as-of 컨트롤 vs 스윕 CSV.

실행 (Streamlit 별도 기동 필요):
  streamlit run main.py --server.port 8501
  python validation/verdict_playwright.py

불일치 시 수정하지 않고 상세 보고만.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from validation.verdict_categories import is_buy_category

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_URL = os.environ.get("WAVE_APP_URL", "http://localhost:8501")
RANDOM_SEED = 42

# (symbol, interval, transitions_csv)
PARITY_TARGETS = [
    ("ETHUSDT", "4h", "verdict_transitions_ETHUSDT_4h.csv"),
    ("BTCUSDT", "1d", "verdict_transitions_BTCUSDT_1d.csv"),
]


def _load_timeline(symbol, interval):
    path = os.path.join(OUT_DIR, f"verdict_timeline_{symbol}_{interval}.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"run verdict_sweep first: {path}")
    return pd.read_csv(path, parse_dates=["timestamp"])


def _pick_check_points(trans_path: str, timeline: pd.DataFrame) -> list[pd.Timestamp]:
    df = pd.read_csv(trans_path, parse_dates=["timestamp"])
    valid = set(pd.Timestamp(t) for t in timeline["timestamp"])
    buy_entries = [
        pd.Timestamp(t) for t in df[df["to_category"].map(is_buy_category)]["timestamp"]
        if pd.Timestamp(t) in valid
    ]
    others = [
        pd.Timestamp(t) for t in df["timestamp"]
        if pd.Timestamp(t) in valid and pd.Timestamp(t) not in buy_entries
    ]
    rng = random.Random(RANDOM_SEED)
    sample = rng.sample(others, min(5, len(others))) if others else []
    return sorted(set(buy_entries + sample))


def _format_asof_input(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d %H:%M")


def _select_streamlit_option(page, label_substr: str, value: str) -> None:
    """Streamlit selectbox(combobox) 선택."""
    combo = page.locator(f'[aria-label*="Select {label_substr}"], [aria-label*="{label_substr}"]').first
    combo.click()
    page.get_by_role("option", name=value, exact=True).click()
    page.wait_for_timeout(500)


_VERDICT_PREFIXES = ("✅", "🟡", "🟠", "⚠️", "⏸️", "⚖️", "데이터")


def _extract_verdict_text(page) -> str:
    """요약 패널 ### verdict heading (사이드바 h3 제외)."""
    headings = page.locator("h3")
    for i in range(headings.count()):
        text = headings.nth(i).inner_text().strip()
        if text.startswith(_VERDICT_PREFIXES):
            return text
    raise RuntimeError("verdict h3 not found")


def run_parity(base_url: str = APP_URL) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("playwright 미설치: pip install playwright && playwright install") from exc

    mismatches = []
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(base_url, wait_until="networkidle", timeout=120_000)

        for symbol, interval, trans_file in PARITY_TARGETS:
            timeline = _load_timeline(symbol, interval)
            trans_path = os.path.join(OUT_DIR, trans_file)
            if not os.path.isfile(trans_path):
                continue
            points = _pick_check_points(trans_path, timeline)

            # symbol / interval 선택
            _select_streamlit_option(page, "Symbol", symbol)
            _select_streamlit_option(page, "Timeframe", interval)
            page.wait_for_timeout(8000)

            for ts in points:
                sweep_row = timeline.loc[timeline["timestamp"] == ts]
                if sweep_row.empty:
                    continue
                expected = sweep_row["verdict"].iloc[0]

                asof_input = page.get_by_role("textbox", name="기준 시점 (백트레이스)")
                asof_input.fill(_format_asof_input(ts))
                asof_input.press("Enter")
                page.wait_for_timeout(20000)

                ui_verdict = _extract_verdict_text(page)

                safe_name = ts.strftime("%Y%m%d_%H%M")
                shot = os.path.join(OUT_DIR, f"asof_{symbol}_{interval}_{safe_name}.png")
                page.screenshot(path=shot, full_page=False)

                ok = ui_verdict.strip() == expected.strip()
                results.append({
                    "symbol": symbol,
                    "interval": interval,
                    "timestamp": str(ts),
                    "expected": expected,
                    "ui": ui_verdict,
                    "match": ok,
                    "screenshot": os.path.basename(shot),
                })
                if not ok:
                    mismatches.append(results[-1])

                asof_input.fill("")
                asof_input.press("Enter")
                page.wait_for_timeout(3000)

        browser.close()

    return results


def write_parity_report(rows: list[dict]) -> str:
    path = os.path.join(OUT_DIR, "REPORT_VERDICT_PARITY.md")
    lines = ["# Playwright verdict 파리티", ""]
    if not rows:
        lines.append("- (결과 없음)")
    else:
        mismatches = [r for r in rows if r.get("match") is False]
        if mismatches:
            lines.append(f"- **불일치 {len(mismatches)}건**")
            lines.append("")
            for m in mismatches:
                lines.append(f"## {m['symbol']} {m['interval']} @ {m['timestamp']}")
                lines.append(f"- UI: `{m['ui']}`")
                lines.append(f"- 스윕: `{m['expected']}`")
                lines.append(f"- screenshot: `{m.get('screenshot', '-')}`")
                lines.append("")
        else:
            lines.append(f"- 전건 일치 ({len(rows)} checkpoints)")
            lines.append("")
            lines.append("| symbol | interval | timestamp | match |")
            lines.append("|---|---|---|---|")
            for r in rows:
                lines.append(
                    f"| {r['symbol']} | {r['interval']} | {r['timestamp']} | OK |"
                )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    results = run_parity()
    path = write_parity_report(results)
    mismatches = [r for r in results if r.get("match") is False]
    if mismatches:
        print(f"PARITY MISMATCH {len(mismatches)} — see {path}")
        for m in mismatches:
            print(f"  {m['timestamp']}: UI={m['ui']!r} sweep={m['expected']!r}")
        raise SystemExit(1)
    print(f"parity OK — {path}")


if __name__ == "__main__":
    main()
