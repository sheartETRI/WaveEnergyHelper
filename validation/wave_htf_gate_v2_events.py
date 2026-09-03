"""SPEC_WAVE_HTF_GATE_V2 §2.4 — LTF 이벤트 캐시 재생성 (2021–2026).

이벤트 검출 로직은 변경하지 않는다 (§2.3). 기존 함수를 그대로 호출하되,
데이터 로딩 한도만 관측 구간에 맞게 주입한다. R1 산출물은 덮어쓰지 않고
_htf_gate_v2_cache/ 아래에 따로 쓴다.

사용법:
    python validation/wave_htf_gate_v2_events.py [--ltf 1h,6h] [--symbols BTCUSDT,...]
                                                 [--window main|extended] [--smoke]
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import ExitStack, contextmanager

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import wave_generalization as GEN
from analysis import wave_live_forward_journal as JOURNAL
from analysis import wave_live_watchlist as WATCH
from analysis.wave_htf_gate_v2 import (
    MA_WARMUP,
    SYMBOLS_V2,
    WINDOW_EXTENDED,
    WINDOW_MAIN,
    _bars_between,
    fetch_window_bare,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LTFS = ("1h", "6h")
WINDOWS = {"main": WINDOW_MAIN, "extended": WINDOW_EXTENDED}
PAD_BARS = MA_WARMUP + 60


def cache_dir() -> str:
    path = os.path.join(OUT_DIR, "_htf_gate_v2_cache")
    os.makedirs(path, exist_ok=True)
    return path


def confluence_path(symbol: str, ltf: str) -> str:
    return os.path.join(cache_dir(), f"confluence_{symbol}_{ltf}.csv")


def journal_path(ltf: str) -> str:
    return os.path.join(cache_dir(), f"forward_journal_{ltf}.csv")


@contextmanager
def _patched_loaders(symbol: str, ltf: str, bare: pd.DataFrame, pipe: pd.DataFrame):
    """OHLCV/파이프라인 로더를 구간 프레임으로 고정 (기본 한도 대신 주입)."""
    saved = {
        "watch_ohlcv": WATCH._load_ohlcv,
        "watch_pipe": WATCH._load_pipeline,
        "watch_confpath": WATCH._confluence_path,
        "journal_ohlcv": JOURNAL._load_ohlcv,
        "journal_pipe": JOURNAL._load_pipeline,
        "gen_cell_limit": GEN._cell_limit,
    }

    def _ohlcv(sym, tf):
        return bare if (sym, tf) == (symbol, ltf) else saved["watch_ohlcv"](sym, tf)

    def _pipe(sym, tf):
        return pipe if (sym, tf) == (symbol, ltf) else saved["watch_pipe"](sym, tf)

    def _confpath(sym, tf):
        path = confluence_path(sym, tf)
        return path if os.path.isfile(path) else saved["watch_confpath"](sym, tf)

    WATCH._load_ohlcv = _ohlcv
    WATCH._load_pipeline = _pipe
    WATCH._confluence_path = _confpath
    JOURNAL._load_ohlcv = _ohlcv
    JOURNAL._load_pipeline = _pipe
    GEN._cell_limit = lambda interval: len(bare) if interval == ltf else saved["gen_cell_limit"](interval)
    try:
        yield
    finally:
        WATCH._load_ohlcv = saved["watch_ohlcv"]
        WATCH._load_pipeline = saved["watch_pipe"]
        WATCH._confluence_path = saved["watch_confpath"]
        JOURNAL._load_ohlcv = saved["journal_ohlcv"]
        JOURNAL._load_pipeline = saved["journal_pipe"]
        GEN._cell_limit = saved["gen_cell_limit"]


def build_cell(symbol: str, ltf: str, window: tuple[str, str]) -> pd.DataFrame:
    """한 (symbol, LTF) 셀의 confluence 재생성 + 이벤트 추출."""
    from analysis.wave_confluence import add_confluence_indicators
    from display.asof import run_indicator_pipeline

    t0 = time.time()
    bare = fetch_window_bare(symbol, ltf, window[0], window[1], pad_bars=PAD_BARS)
    pipe = add_confluence_indicators(run_indicator_pipeline(bare))
    print(f"  [{symbol} {ltf}] bars={len(bare)} "
          f"{bare.index.min()} ~ {bare.index.max()} ({time.time()-t0:.0f}s)", flush=True)

    with _patched_loaders(symbol, ltf, bare, pipe):
        t = time.time()
        conf = GEN.build_cell_confluence_live(symbol, ltf)
        if not conf.empty:
            conf.to_csv(confluence_path(symbol, ltf), index=False)
        print(f"  [{symbol} {ltf}] confluence rows={len(conf)} ({time.time()-t:.0f}s)", flush=True)

        t = time.time()
        scan = WATCH.scan_cell(symbol, ltf, ohlcv=bare, pipeline=pipe, scan_bars=len(bare))
        events = WATCH.extract_rule_events(scan) if not scan.empty else pd.DataFrame()
        print(f"  [{symbol} {ltf}] scan={len(scan)} events={len(events)} "
              f"({time.time()-t:.0f}s)", flush=True)

    return events


def build_ltf(ltf: str, symbols: tuple[str, ...], window: tuple[str, str]) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        ev = build_cell(sym, ltf, window)
        if not ev.empty:
            frames.append((sym, ev))
    if not frames:
        return pd.DataFrame()

    rows = []
    for sym, ev in frames:
        bare = fetch_window_bare(sym, ltf, window[0], window[1], pad_bars=PAD_BARS)
        from analysis.wave_confluence import add_confluence_indicators
        from display.asof import run_indicator_pipeline
        pipe = add_confluence_indicators(run_indicator_pipeline(bare))
        t = time.time()
        with _patched_loaders(sym, ltf, bare, pipe):
            j = JOURNAL.build_forward_journal(ev)
        print(f"  [{sym} {ltf}] journal rows={len(j)} ({time.time()-t:.0f}s)", flush=True)
        if not j.empty:
            rows.append(j)

    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not out.empty:
        out = out[pd.to_datetime(out["timestamp"]) >= pd.Timestamp(window[0])]
        out.to_csv(journal_path(ltf), index=False)
        print(f"[{ltf}] journal -> {journal_path(ltf)} rows={len(out)}", flush=True)
    return out


def main() -> None:
    args = sys.argv[1:]

    def _opt(name, default):
        return args[args.index(name) + 1] if name in args else default

    window = WINDOWS[_opt("--window", "main")]
    ltfs = tuple(_opt("--ltf", ",".join(LTFS)).split(","))
    symbols = tuple(_opt("--symbols", ",".join(SYMBOLS_V2)).split(","))
    if "--smoke" in args:
        window = ("2026-01-01", "2026-09-01")
        print(f"[smoke] window={window}", flush=True)

    for ltf in ltfs:
        n_bars = _bars_between(pd.Timestamp(window[0]), pd.Timestamp(window[1]), ltf)
        print(f"[{ltf}] window={window} ~{n_bars} bars × {len(symbols)} symbols", flush=True)
        build_ltf(ltf, symbols, window)


if __name__ == "__main__":
    main()
