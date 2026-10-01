"""스윕 재탈환 검출기 — 실봉 스캔 리포트 (수동 실행 스크립트).

회사망·원격 컨테이너에서는 Binance 가 차단될 수 있어, 네트워크가 되는 PC 에서
직접 돌리는 관측 스크립트다. 기록 전용 — 게이팅·알람·판정 없음
(docs/SPEC_SWEEP_RECLAIM.md §0 비목표 그대로).

사용:
    python scripts/sweep_scan_report.py
    python scripts/sweep_scan_report.py --symbol BTCUSDT --intervals 1d,6h --since 2025-10-01
    python scripts/sweep_scan_report.py --deep          # 2017~ 전체 역사 (페이지네이션)

--deep: DEEP_LIMITS 봉까지 과거를 채운다. 대파동 이벤트가 TF 당 4~8건뿐이라 §11 급4 층화가
판정 불가였던 표본 문제를 푸는 용도.

수신은 OHLCV 로컬 저장소(data/ohlcv_store.py → data/cache/ohlcv_<SYMBOL>_<tf>.csv, 앱과 같은
파일) 경유 — 저장된 봉은 다시 받지 않고 꼬리만 갱신, 모자란 과거만 endTime 커서로 채운다(SPEC §12).
수신 실패 시 저장본이 있으면 그것으로 진행하고 콘솔에 표시, 없으면 예외. 실행 끝에 TF 별
요청 수·새 봉·저장 봉·틈을 한 줄씩 출력한다.

출력:
    · 콘솔 — since 이후 이벤트 요약표 (+ 합류 이벤트, SPEC §6)
    · logs/sweep_events_<symbol>_<interval>.csv — 전 구간 스윕 이벤트 (utf-8-sig, 엑셀 호환)
    · logs/sweep_confluence_<symbol>_<interval>.csv — 전 구간 합류 이벤트 (스토캐 검출
      가능 환경에서만 — indicators.stochastic 임포트 실패 시 그 부분만 건너뜀)

streamlit 무의존 — data/binance.py 를 임포트하지 않고 같은 엔드포인트를 직접
두드린다(그쪽은 st.cache_data 데코레이터 때문에 streamlit 이 따라온다; data/ohlcv_store.py 는
무의존). 요청 주소 자동 대체(api.binance.com -> data-api.binance.vision)는 data/binance.py 와 같은 순서.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests

from analysis.sweep_reclaim import events_to_frame, scan_sweep_events
from config.settings import OHLCV_STORE_PARAMS
from data import ohlcv_store

# OHLCV 로컬 저장소 — 앱(data/binance)과 같은 경로 (SPEC §12)
STORE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), OHLCV_STORE_PARAMS["dir"]
))
_PAGE_SLEEP_SEC = 0.2       # 요청 간 대기 — data/binance 페이지네이션과 같은 값

_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://data-api.binance.vision/api/v3/klines",
]

# --deep 일 때 인터벌별 수집 봉 수 — 바이낸스 BTCUSDT 역사(2017-08~) 기준 전체를 덮는 값.
DEEP_LIMITS = {
    "1w": 600, "3d": 1200, "1d": 3500, "12h": 7000, "6h": 14000,
    "4h": 21000, "2h": 42000, "1h": 84000,
}

_SHOW_COLUMNS = [
    "timestamp", "kind", "level", "depth_pct", "dwell_bars", "bars_from_start",
    "touch_count", "level_age_bars", "dev_vol_ratio", "reclaim_vol_ratio", "detail",
]


def fetch_klines(symbol: str, interval: str, limit: int = 1000,
                 start_time: int | None = None, end_time: int | None = None) -> list:
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time is not None:
        params["startTime"] = int(start_time)
    if end_time is not None:
        params["endTime"] = int(end_time)
    last_err: Exception | None = None
    for url in _URLS:
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as err:  # 다음 주소로 대체
            last_err = err
    raise RuntimeError(f"klines 수신 실패 ({symbol} {interval}): {last_err}")


def _fetch_page(symbol: str, interval: str, limit: int,
                start_time: int | None = None, end_time: int | None = None) -> list:
    """저장소에 주입하는 전송 계층 — 요청 간 대기 후 fetch_klines (두 주소 대체 그대로)."""
    time.sleep(_PAGE_SLEEP_SEC)
    return fetch_klines(symbol, interval, limit, start_time=start_time, end_time=end_time)


# 이번 실행의 저장소 갱신 결과 [(interval, RefreshResult)] — 실행 끝 요약용
_STORE_RESULTS: list = []


def fetch_history(symbol: str, interval: str, limit: int, deep: bool) -> list:
    """로컬 저장소 경유 수신 — deep 이면 DEEP_LIMITS 봉, 아니면 limit 봉 (마지막 N봉, 오름차순 raw 행).

    저장된 봉은 다시 받지 않는다(꼬리 + 모자란 과거만). 수신 실패 시 저장본이 있으면 그것으로 진행, 없으면 예외.
    """
    min_bars = DEEP_LIMITS.get(interval, limit) if deep else limit
    res = ohlcv_store.refresh(symbol, interval, _fetch_page, min_bars, base_dir=STORE_DIR)
    _STORE_RESULTS.append((interval, res))
    if res.error:
        print(f"({interval} 수신 오류: {res.error} — 저장본 {len(res.rows)}봉{' · stale' if res.stale else ''})")
    if not res.rows:
        raise RuntimeError(f"klines 수신 실패 ({symbol} {interval}): 빈 응답")
    return ohlcv_store.tail(res.rows, min_bars)


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
        from analysis.stoch_near_miss import near_miss_to_frame, scan_near_miss_events
        from analysis.sweep_confluence import confluence_to_frame, scan_confluence_events
        from config.settings import SWEEP_CONFLUENCE_PARAMS, WAVE_LAYER_ROLES
    except Exception as err:
        print(f"(합류 스캔 생략 — 임포트 실패: {err})")
        return None, None, None
    enriched = add_stochastic_slow_layers(df.copy())
    roles = SWEEP_CONFLUENCE_PARAMS.get("layer_roles", [])
    missing = [
        r for r in roles
        if f"stoch_db_{WAVE_LAYER_ROLES.get(r, '')}" not in enriched.columns
    ]
    if missing:
        print(f"(합류 스캔 생략 — 검출 컬럼 없음: {missing})")
        return None, None, None

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
    near = near_miss_to_frame(scan_near_miss_events(enriched))
    return confluence_to_frame(scan_confluence_events(enriched)), confirms, near


def scan_alarm_events_frame(df: pd.DataFrame):
    """스토캐·RSI·MACD·스윕·합류 전 이벤트를 알람 행 원장으로 덤프 (기록 전용).

    조합 가설(예: 합류의 MACD 0선 동반 여부, 히스토그램 쌍바닥 동반 여부)을 열람 때
    조인으로 층화하기 위한 원장 — 판정·게이팅에 쓰지 않는다. 불가 환경이면 None.
    """
    try:
        from analysis.alarm_signals import scan_alarm_signals, signals_to_frame
        from indicators.oscillators import add_macd, add_rsi
        from indicators.stochastic import add_stochastic_slow_layers
    except Exception as err:
        print(f"(알람 이벤트 원장 생략 — {err})")
        return None
    enriched = add_macd(add_rsi(add_stochastic_slow_layers(df.copy())))
    return signals_to_frame(scan_alarm_signals(enriched))


def main() -> int:
    parser = argparse.ArgumentParser(description="스윕 재탈환 검출기 실봉 스캔 (기록 전용)")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--intervals",
        default="1w,3d,1d,6h",
        help="쉼표 구분 (Binance 네이티브 인터벌). 상위 TF 포함 — HTF 신뢰성 가설 표본 축적",
    )
    parser.add_argument("--since", default="2025-10-01", help="콘솔 요약 시작일 (CSV 는 전 구간)")
    parser.add_argument("--limit", type=int, default=1000, help="인터벌당 수신 봉 수 (최대 1000)")
    parser.add_argument("--deep", action="store_true",
                        help="DEEP_LIMITS 봉까지 과거를 저장소에 채움 (data/ohlcv_store, 저장된 봉은 재수신 안 함)")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)

    for interval in [s.strip() for s in args.intervals.split(",") if s.strip()]:
        df = build_dataframe(fetch_history(args.symbol, interval, args.limit, args.deep))

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

        alarm_frame = scan_alarm_events_frame(df)
        if alarm_frame is not None:
            alarm_path = os.path.join(
                logs_dir, f"alarm_events_{args.symbol}_{interval}.csv"
            )
            alarm_frame.to_csv(alarm_path, index=False, encoding="utf-8-sig")
            print(f"-> 알람 이벤트 원장 CSV: {os.path.relpath(alarm_path, root)} ({len(alarm_frame)}행)")

        conf, confirms, near = scan_confluence_frame(df)
        if near is not None:
            near_path = os.path.join(
                logs_dir, f"stoch_near_miss_{args.symbol}_{interval}.csv"
            )
            near.to_csv(near_path, index=False, encoding="utf-8-sig")
            print(f"-> 구역 니어미스 진단 CSV: {os.path.relpath(near_path, root)} ({len(near)}건)")
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

    # 월봉 맥락 레코드 (SPEC §8) — 이벤트가 아니라 사이클 위치의 월별 시계열.
    try:
        from analysis.monthly_context import monthly_context_frame

        ctx = monthly_context_frame(build_dataframe(fetch_history(args.symbol, "1M", args.limit, False)))
        ctx_path = os.path.join(logs_dir, f"monthly_context_{args.symbol}.csv")
        ctx.to_csv(ctx_path, encoding="utf-8-sig")
        print(f"\n===== 월봉 맥락 ({args.symbol}) — {len(ctx)}개월 -> {os.path.relpath(ctx_path, root)} =====")
        tail = ctx.dropna(subset=["large_k"]).tail(2)
        if len(tail):
            print(tail.round(2).to_string())
    except Exception as err:
        print(f"(월봉 맥락 생략 — {err})")

    print(f"\n===== OHLCV 저장소 ({os.path.relpath(STORE_DIR, root)}) =====")
    for interval, res in _STORE_RESULTS:
        print(f"{interval}: 요청 {res.requests}회 · 새 봉 {res.added} · 저장 {len(res.rows)}봉 · 틈 {len(res.gaps)}"
              + (" · stale" if res.stale else ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
