"""스윕 재탈환 검출기 — 실봉 스캔 리포트 (수동 실행 스크립트).

회사망·원격 컨테이너에서는 Binance 가 차단될 수 있어, 네트워크가 되는 PC 에서
직접 돌리는 관측 스크립트다. 기록 전용 — 게이팅·알람·판정 없음
(docs/SPEC_SWEEP_RECLAIM.md §0 비목표 그대로).

사용:
    python scripts/sweep_scan_report.py
    python scripts/sweep_scan_report.py --symbol BTCUSDT --intervals 1d,6h --since 2025-10-01

출력:
    · 콘솔 — since 이후 이벤트 요약표
    · logs/sweep_events_<symbol>_<interval>.csv — 전 구간 이벤트 (utf-8-sig, 엑셀 호환)

streamlit 무의존 — data/binance.py 를 임포트하지 않고 같은 엔드포인트를 직접
두드린다(그쪽은 st.cache_data 데코레이터 때문에 streamlit 이 따라온다). 요청 주소
자동 대체(api.binance.com -> data-api.binance.vision)는 data/binance.py 와 같은 순서.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests

from analysis.sweep_reclaim import events_to_frame, scan_sweep_events

_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://data-api.binance.vision/api/v3/klines",
]

_SHOW_COLUMNS = [
    "timestamp", "kind", "level", "depth_pct", "dwell_bars", "bars_from_start",
    "touch_count", "level_age_bars", "dev_vol_ratio", "reclaim_vol_ratio", "detail",
]


def fetch_klines(symbol: str, interval: str, limit: int = 1000) -> list:
    last_err: Exception | None = None
    for url in _URLS:
        try:
            resp = requests.get(
                url,
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as err:  # 다음 주소로 대체
            last_err = err
    raise RuntimeError(f"klines 수신 실패 ({symbol} {interval}): {last_err}")


def build_dataframe(raw: list) -> pd.DataFrame:
    """data/processor.build_dataframe 와 같은 스키마 (streamlit 무의존 복제)."""
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "qav", "num_trades", "taker_base", "taker_quote", "ignore",
    ]
    df = pd.DataFrame(raw, columns=columns)
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("open_time")


def main() -> int:
    parser = argparse.ArgumentParser(description="스윕 재탈환 검출기 실봉 스캔 (기록 전용)")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--intervals", default="1d,6h", help="쉼표 구분 (Binance 네이티브 인터벌)")
    parser.add_argument("--since", default="2025-10-01", help="콘솔 요약 시작일 (CSV 는 전 구간)")
    parser.add_argument("--limit", type=int, default=1000, help="인터벌당 수신 봉 수 (최대 1000)")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)

    for interval in [s.strip() for s in args.intervals.split(",") if s.strip()]:
        df = build_dataframe(fetch_klines(args.symbol, interval, args.limit))
        frame = events_to_frame(scan_sweep_events(df))

        out_path = os.path.join(logs_dir, f"sweep_events_{args.symbol}_{interval}.csv")
        frame.to_csv(out_path, index=False, encoding="utf-8-sig")

        recent = frame[frame["timestamp"] >= args.since]
        show = recent[_SHOW_COLUMNS].copy()
        for col in ["level", "depth_pct", "dev_vol_ratio", "reclaim_vol_ratio"]:
            show[col] = show[col].map(
                lambda v: None if v is None or pd.isna(v) else round(float(v), 2)
            )
        print(
            f"\n===== {args.symbol} {interval} — 봉 {len(df)}개"
            f" ({df.index[0].date()} ~ {df.index[-1].date()}),"
            f" 전 구간 이벤트 {len(frame)}건 / {args.since} 이후 {len(show)}건 ====="
        )
        print(show.to_string(index=False) if len(show) else "(해당 기간 이벤트 없음)")
        print(f"-> CSV: {os.path.relpath(out_path, root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
