"""라이브-백테스트 트리거 불일치 원인 규명 (진단 전용, 읽기 전용).

프로덕션 파일을 수정하지 않고, 몽키패치·오버라이드 없이 기존 함수를 그대로 호출한다.
- 라이브 경로: wave_live_watchlist.scan_cell(symbol, tf) 를 인자 없이 호출 = 실제 라이브 경로
- 백테스트 경로: V2 가 남긴 forward_journal_{tf}.csv 의 저장값을 읽는다
  (재계산하지 않는다). flag_* 는 저장된 score 와 scan_cell 의 임계로 역산한다.

실행: python validation/diagnostics/trigger_mismatch_diag.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from analysis import wave_live_watchlist as WATCH
from analysis.wave_htf_gate import TRIGGER_QUALITY, TRIGGER_RULE
from analysis.wave_htf_gate_v2 import SYMBOLS_V2
from analysis.wave_outcome import _find_bar_index
from analysis.wave_structure_confirmation import _confirmed, find_swing_lows

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BT_DIR = os.path.join(ROOT, "validation", "_htf_gate_v2_cache")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# scan_cell(analysis/wave_live_watchlist.py:196-198) 의 플래그 임계.
# 저장된 score 에서 flag 를 역산하기 위한 것이며 새 정의가 아니다.
MF_MIN, STRUCT_MIN, ENERGY_MIN = 4, 3, 3

# 직전 라운드에서 확정된 6h 비수렴 19건 (관측 결과 데이터)
NONCONVERGED_6H = [
    ("BNBUSDT", "2026-05-03 06:00:00"), ("BNBUSDT", "2026-07-01 12:00:00"),
    ("BNBUSDT", "2026-08-04 12:00:00"), ("BNBUSDT", "2026-08-10 06:00:00"),
    ("BNBUSDT", "2026-08-11 06:00:00"), ("BTCUSDT", "2026-06-11 06:00:00"),
    ("BTCUSDT", "2026-06-11 12:00:00"), ("BTCUSDT", "2026-06-12 06:00:00"),
    ("BTCUSDT", "2026-06-12 12:00:00"), ("BTCUSDT", "2026-07-01 12:00:00"),
    ("BTCUSDT", "2026-08-06 12:00:00"), ("BTCUSDT", "2026-08-07 12:00:00"),
    ("BTCUSDT", "2026-08-17 12:00:00"), ("BTCUSDT", "2026-08-18 00:00:00"),
    ("ETHUSDT", "2026-05-11 12:00:00"), ("ETHUSDT", "2026-08-04 06:00:00"),
    ("ETHUSDT", "2026-08-17 00:00:00"), ("ETHUSDT", "2026-08-18 00:00:00"),
    ("ETHUSDT", "2026-08-19 06:00:00"),
]

FLAGS = ("flag_tb", "flag_money_flow", "flag_structure", "flag_energy")


def trigger_of(rule: str, quality: float) -> tuple[bool, bool, bool]:
    """Filter_C, Filter_Q, 트리거(합집합)."""
    fc = str(rule) == TRIGGER_RULE
    fq = float(quality) >= TRIGGER_QUALITY
    return fc, fq, (fc or fq)


def live_scan(symbol: str, tf: str) -> pd.DataFrame:
    """실제 라이브 경로 — 로더를 주입하지 않고 scan_cell 이 스스로 읽게 둔다."""
    scan = WATCH.scan_cell(symbol, tf)
    if scan.empty:
        return scan
    scan = scan.copy()
    scan["timestamp"] = pd.to_datetime(scan["timestamp"])
    return scan.set_index("timestamp")


def live_rules(row: pd.Series) -> list[str]:
    """scan 행에서 발생한 rule 전부.

    한 봉은 WATCH_RULES 중 여러 개를 동시에 만족할 수 있고, extract_rule_events 는
    rule 마다 별도 이벤트를 낸다 (실측 최대 3건/봉). 봉당 하나만 보면 비교가 깨진다.
    """
    filters = WATCH.rule_filters()
    frame = pd.DataFrame([row])
    return [r for r in WATCH.WATCH_RULES if bool(filters[r](frame).iloc[0])]


def backtest_journal(tf: str) -> pd.DataFrame:
    path = os.path.join(BT_DIR, f"forward_journal_{tf}.csv")
    bt = pd.read_csv(path, parse_dates=["timestamp"])
    return bt[bt["symbol"].isin(SYMBOLS_V2)]


def bt_flags(row: pd.Series) -> dict:
    """저장된 score 에서 flag 역산. quality = tb+struct+energy+mf 항등식의 역산이다."""
    mf = bool(float(row["money_flow_score"]) >= MF_MIN)
    st = bool(float(row["structure_score"]) >= STRUCT_MIN)
    en = bool(float(row["energy_score"]) >= ENERGY_MIN)
    tb = int(row["quality_score"]) - (int(mf) + int(st) + int(en))
    return {
        "flag_money_flow": mf, "flag_structure": st, "flag_energy": en,
        "flag_tb": bool(tb), "tb_derived_raw": tb,
    }


def agreement(tf: str) -> dict:
    """트리거 일치율 — **이벤트 단위** (symbol, timestamp, rule).

    트리거(Filter_C ∪ Filter_Q)는 저널의 행(=이벤트)에 적용되는 필터다.
    (symbol, timestamp) 로만 키를 잡으면 같은 봉의 여러 rule 이벤트가 서로를 덮어써
    판정이 파일 행 순서에 좌우된다. 봉 단위 집계가 필요하면 OR 로 접는다.
    """
    live = pd.read_csv(os.path.join(ROOT, "validation", "wave_live_forward_journal.csv"),
                       parse_dates=["timestamp"])
    L = live[(live["timeframe"] == tf) & (live["symbol"].isin(SYMBOLS_V2))].copy()
    B = backtest_journal(tf).copy()
    if L.empty or B.empty:
        return {"tf": tf, "event_union": 0, "bar_union": 0}
    lo = max(L["timestamp"].min(), B["timestamp"].min())
    hi = min(L["timestamp"].max(), B["timestamp"].max())
    L = L[(L["timestamp"] >= lo) & (L["timestamp"] <= hi)]
    B = B[(B["timestamp"] >= lo) & (B["timestamp"] <= hi)]

    def trig_map(df, by_bar=False):
        out = {}
        for r in df.itertuples():
            v = trigger_of(r.rule, r.quality_score)[2]
            key = (r.symbol, r.timestamp) if by_bar else (r.symbol, r.timestamp, r.rule)
            out[key] = (out.get(key, False) or v) if by_bar else v
        return out

    res = {"tf": tf, "lo": lo, "hi": hi}
    for label, by_bar in (("event", False), ("bar", True)):
        lm, bm = trig_map(L, by_bar), trig_map(B, by_bar)
        keys = set(lm) | set(bm)
        mism = [k for k in keys if lm.get(k, False) != bm.get(k, False)]
        res[f"{label}_union"] = len(keys)
        res[f"{label}_match"] = len(keys) - len(mism)
        res[f"{label}_rate"] = round((len(keys) - len(mism)) / len(keys) * 100, 2) if keys else None
        res[f"{label}_mismatch"] = sorted(str(k) for k in mism)
    return res


def controls(tf: str, live_by_symbol: dict, n=3) -> list[tuple[str, pd.Timestamp]]:
    """대조군 — 양쪽이 일치하는 봉 심볼별 n건."""
    bt = backtest_journal(tf)
    out = []
    for sym in SYMBOLS_V2:
        scan = live_by_symbol.get(sym)
        if scan is None or scan.empty:
            continue
        b = bt[bt["symbol"] == sym]
        common = [t for t in b["timestamp"] if t in scan.index]
        picked = 0
        for ts in sorted(common, reverse=True):
            brow = b[b["timestamp"] == ts].iloc[0]
            lrow = scan.loc[ts]
            lrules = live_rules(lrow)
            if not lrules:
                continue
            ltrig = any(trigger_of(r, lrow["quality_score"])[2] for r in lrules)
            if ltrig == trigger_of(brow["rule"], brow["quality_score"])[2]:
                out.append((sym, ts))
                picked += 1
                if picked >= n:
                    break
    return out


def dump_bar(sym: str, tf: str, ts: pd.Timestamp, scan: pd.DataFrame,
             bt: pd.DataFrame, ohlcv: pd.DataFrame) -> dict:
    """봉 하나의 라이브·백테스트 나란한 덤프 + 첫 분기점 특정."""
    rec: dict = {"symbol": sym, "tf": tf, "timestamp": str(ts)}

    in_live = ts in scan.index
    bsub = bt[(bt["symbol"] == sym) & (bt["timestamp"] == ts)]
    brow = bsub
    rec["in_live_scan"] = bool(in_live)
    rec["in_backtest"] = bool(len(brow))

    if in_live:
        lrow = scan.loc[ts]
        lrules = live_rules(lrow)
        lfc = any(trigger_of(r, lrow["quality_score"])[0] for r in lrules)
        lfq = float(lrow["quality_score"]) >= TRIGGER_QUALITY
        ltrig = lfc or lfq
        rec.update({
            "live_rule": ",".join(lrules) or "NONE", "live_filter_c": lfc, "live_filter_q": lfq,
            "live_trigger": ltrig, "live_quality": int(lrow["quality_score"]),
            "live_mf_score": int(lrow["money_flow_score"]),
            "live_struct_score": int(lrow["structure_score"]),
            "live_energy_score": int(lrow["energy_score"]),
            **{f"live_{f}": bool(lrow[f]) for f in FLAGS},
            "live_bar_index": int(lrow["bar_index"]),
        })
    if len(brow):
        b = brow.iloc[0]
        bfc = any(trigger_of(r, b["quality_score"])[0] for r in bsub["rule"])
        bfq = float(b["quality_score"]) >= TRIGGER_QUALITY
        btrig = bfc or bfq
        rec["bt_rules_all"] = ",".join(sorted(bsub["rule"]))
        bf = bt_flags(b)
        rec.update({
            "bt_rule": ",".join(sorted(bsub["rule"])), "bt_filter_c": bfc, "bt_filter_q": bfq,
            "bt_trigger": btrig, "bt_quality": int(b["quality_score"]),
            "bt_mf_score": int(b["money_flow_score"]),
            "bt_struct_score": int(b["structure_score"]),
            "bt_energy_score": int(b["energy_score"]),
            **{f"bt_{f}": bf[f] for f in FLAGS},
            "bt_tb_derived_raw": bf["tb_derived_raw"],
        })

    # 갈린 필터 / 플래그 / 점수
    if in_live and len(brow):
        split_filters = [n for n, a, b_ in (("Filter_C", rec["live_filter_c"], rec["bt_filter_c"]),
                                            ("Filter_Q", rec["live_filter_q"], rec["bt_filter_q"]))
                         if a != b_]
        rec["split_filter"] = ",".join(split_filters) or "-"
        rec["split_flags"] = ",".join(f for f in FLAGS
                                      if rec[f"live_{f}"] != rec[f"bt_{f}"]) or "-"
        rec["split_scores"] = ",".join(
            k for k in ("mf_score", "struct_score", "energy_score")
            if rec[f"live_{k}"] != rec[f"bt_{k}"]) or "-"
    else:
        rec["split_filter"] = "EVENT_PRESENCE"
        rec["split_flags"] = "-"
        rec["split_scores"] = "-"

    # flag_tb 입력값 (라이브 측) — 기존 함수만 호출
    if in_live and not ohlcv.empty:
        pos = _find_bar_index(ohlcv, ts)
        if pos is not None:
            swing_lows = find_swing_lows(ohlcv["low"])
            tb_cache = WATCH.load_tb_bar_indices(sym, tf, ohlcv)
            rec["live_pos"] = pos
            rec["live_frame_len"] = len(ohlcv)
            rec["live_bars_from_frame_start"] = pos
            rec["live_tb_cache_size"] = len(tb_cache)
            rec["live_tb_in_cache"] = bool(pos in tb_cache)
            rec["live_tb_proxy"] = bool(WATCH.is_tb_proxy(swing_lows, pos))
            rec["live_confirmed_lows_n"] = len(_confirmed(swing_lows, pos))
    return rec


def classify(rec: dict) -> str:
    """분류 — 억지로 끼워 넣지 않는다."""
    if rec["split_filter"] == "EVENT_PRESENCE":
        return "EVENT_PRESENCE"
    if rec["split_flags"] == "-" and rec["split_filter"] == "-":
        return "MATCH"
    scores = rec.get("split_scores", "-")
    flags = rec.get("split_flags", "-")
    if scores != "-":
        # 같은 봉에 대해 positional feature 값이 다름
        return "FEATURE_SCORE_DIFF"
    if flags == "flag_tb":
        if rec.get("live_tb_cache_size", 0) == 0:
            return "CACHE_TIMING"      # 라이브에 tb 캐시가 없어 프록시만으로 판정
        return "CACHE_TIMING"
    if flags == "-" and rec["split_filter"] != "-":
        return "RULE_ASSIGNMENT_DIFF"
    return "UNCLASSIFIED"


def main() -> None:
    tfs = ("6h", "1h")
    live: dict = {}
    ohlcv: dict = {}
    for tf in tfs:
        for sym in SYMBOLS_V2:
            live[(sym, tf)] = live_scan(sym, tf)
            ohlcv[(sym, tf)] = WATCH._load_ohlcv(sym, tf)
            print(f"[live] {sym} {tf} scan={len(live[(sym, tf)])} "
                  f"frame={len(ohlcv[(sym, tf)])}", flush=True)

    targets: list[tuple[str, str, pd.Timestamp, str]] = []
    for sym, ts in NONCONVERGED_6H:
        targets.append((sym, "6h", pd.Timestamp(ts), "mismatch"))

    print("=== 트리거 일치율 (이벤트 단위 / 봉 OR) ===")
    for tf in tfs:
        a = agreement(tf)
        print(f"{tf}: 이벤트 {a['event_match']}/{a['event_union']} = {a['event_rate']}%  |  "
              f"봉(OR) {a['bar_match']}/{a['bar_union']} = {a['bar_rate']}%  "
              f"[{a['lo']} ~ {a['hi']}]")
        for m in a["event_mismatch"][:20]:
            print("   불일치:", m)

    for tf in tfs:
        lb = {s: live[(s, tf)] for s in SYMBOLS_V2}
        for sym, ts in controls(tf, lb):
            targets.append((sym, tf, ts, "control"))

    rows = []
    for sym, tf, ts, kind in targets:
        bt = backtest_journal(tf)
        rec = dump_bar(sym, tf, ts, live[(sym, tf)], bt, ohlcv[(sym, tf)])
        rec["kind"] = kind
        rec["classification"] = "MATCH" if kind == "control" and rec["split_filter"] == "-" \
            else classify(rec)
        rows.append(rec)

    df = pd.DataFrame(rows)
    out = os.path.join(OUT_DIR, "trigger_mismatch_diag.csv")
    df.to_csv(out, index=False)
    print(f"\n[out] {out}  rows={len(df)}")

    print("\n=== 봉별 분류표 ===")
    cols = ["symbol", "tf", "timestamp", "kind", "split_filter", "split_flags",
            "split_scores", "classification"]
    print(df[cols].to_string(index=False))

    print("\n=== 분류별 집계 (TF x 분류) ===")
    mm = df[df["kind"] == "mismatch"]
    print(pd.crosstab(mm["tf"], mm["classification"]).to_string())

    print("\n=== 대조군 ===")
    ctl = df[df["kind"] == "control"]
    print(f"대조군 {len(ctl)}건, 전부 일치: "
          f"{bool((ctl['split_filter'] == '-').all() and (ctl['split_flags'] == '-').all())}")
    print(ctl[["symbol", "tf", "timestamp", "split_filter", "split_flags"]].to_string(index=False))


if __name__ == "__main__":
    main()
