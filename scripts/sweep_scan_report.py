"""스윕 재탈환 검출기 — 실봉 스캔 리포트 (수동 실행 스크립트).

회사망·원격 컨테이너에서는 Binance 가 차단될 수 있어, 네트워크가 되는 PC 에서
직접 돌리는 관측 스크립트다. 기록 전용 — 게이팅·알람·판정 없음
(docs/SPEC_SWEEP_RECLAIM.md §0 비목표 그대로).

사용:
    python scripts/sweep_scan_report.py
    python scripts/sweep_scan_report.py --symbol BTCUSDT --intervals 1d,6h --since 2025-10-01

출력:
    · 콘솔 — since 이후 이벤트 요약표 (+ 합류 이벤트, SPEC §6)
    · logs/sweep_events_<symbol>_<interval>.csv — 전 구간 스윕 이벤트 (utf-8-sig, 엑셀 호환)
    · logs/sweep_confluence_<symbol>_<interval>.csv — 전 구간 합류 이벤트 (스토캐 검출
      가능 환경에서만 — indicators.stochastic 임포트 실패 시 그 부분만 건너뜀)

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


def scan_confluence_frame(df: pd.DataFrame):
    """스토캐 검출 컬럼을 채워 합류 이벤트 + 확정 봉 목록(진단용)을 스캔.

    불가 환경이면 (None, None) — 그 부분만 생략. 두 번째 반환값은 레이어별
    쌍바닥/쌍봉 확정 봉 목록으로, 합류 미성립 원인(확정 시점·gap)을 사후에
    확인하는 진단 기록이다.
    """
    try:
        from indicators.stochastic import add_stochastic_slow_layers
        from analysis.sweep_confluence import confluence_to_frame, scan_confluence_events
        from config.settings import SWEEP_CONFLUENCE_PARAMS, WAVE_LAYER_ROLES
    except Exception as err:
        print(f"(합류 스캔 생략 — 임포트 실패: {err})")
        return None, None
    enriched = add_stochastic_slow_layers(df.copy())
    roles = SWEEP_CONFLUENCE_PARAMS.get("layer_roles", [])
    missing = [
        r for r in roles
        if f"stoch_db_{WAVE_LAYER_ROLES.get(r, '')}" not in enriched.columns
    ]
    if missing:
        print(f"(합류 스캔 생략 — 검출 컬럼 없음: {missing})")
        return None, None

    rows = []
    for role in roles:
        suffix = WAVE_LAYER_ROLES[role]
        for prefix, name in (
            ("stoch_db", "db"),
            ("stoch_dt", "dt"),
            ("stoch_db_candidate", "db_candidate"),
            ("stoch_dt_candidate", "dt_candidate"),
        ):
            col = f"{prefix}_{suffix}"
            if col not in enriched.columns:
                continue
            kind_col = f"{prefix}_kind_{suffix}"
            confirmed = enriched[enriched[col].notna()]
            for ts, row in confirmed.iterrows():
                rows.append({
                    "timestamp": ts,
                    "layer": suffix,
                    "kind": name,
                    "db_kind": row.get(kind_col),
                    "value": float(row[col]),
                })
    confirms = pd.DataFrame(
        rows, columns=["timestamp", "layer", "kind", "db_kind", "value"]
    ).sort_values("timestamp")
    return confluence_to_frame(scan_confluence_events(enriched)), confirms


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

        # 원봉 덤프 — 원격 진단 재현용 (스냅샷, 매 실행 덮어씀).
        ohlcv_path = os.path.join(logs_dir, f"ohlcv_{args.symbol}_{interval}.csv")
        df.to_csv(ohlcv_path, encoding="utf-8-sig")

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

        conf, confirms = scan_confluence_frame(df)
        if confirms is not None:
            confirms_path = os.path.join(
                logs_dir, f"stoch_confirms_{args.symbol}_{interval}.csv"
            )
            confirms.to_csv(confirms_path, index=False, encoding="utf-8-sig")
            print(f"-> 확정 봉 진단 CSV: {os.path.relpath(confirms_path, root)}")
        if conf is not None:
            conf_path = os.path.join(
                logs_dir, f"sweep_confluence_{args.symbol}_{interval}.csv"
            )
            conf.to_csv(conf_path, index=False, encoding="utf-8-sig")
            recent_conf = conf[conf["timestamp"] >= args.since]
            print(
                f"--- 합류 이벤트 — 전 구간 {len(conf)}건 / {args.since} 이후 {len(recent_conf)}건 ---"
            )
            if len(recent_conf):
                cols = [
                    "timestamp", "kind", "layer", "gap_bars", "sweep_ts", "stoch_ts",
                    "db_kind", "level", "depth_pct",
                ]
                print(recent_conf[cols].to_string(index=False))
            print(f"-> CSV: {os.path.relpath(conf_path, root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
