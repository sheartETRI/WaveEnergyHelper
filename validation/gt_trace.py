"""정답 구간 역추적 — 관측 라운드 4 (ETHUSDT 4h, 읽기 전용).

검토자 지정 정답 구간에서 엔진이 왜 침묵했는지 게이트 단위로 해부한다.
엔진·앱·파라미터 무수정. 평가 의미론 C0(현행 엄격) 고정.

실행: python validation/gt_trace.py
"""
import os
import sys
import datetime
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CUSTOM_INTERVALS, WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES
from data.binance import fetch_klines_paginated
from data.processor import build_dataframe, resample_timeframe, get_fetch_interval
from indicators.moving_averages import add_moving_averages
from indicators.ma_patterns import add_ma_patterns
from indicators.stochastic import add_stochastic_slow_layers
from analysis.dynamics_rules import (
    RULE_TABLE,
    TRANSITION_RULE_TABLE,
    classify_structure_at,
    evaluate_rule,
    parse_transition_row,
    pair_formation_completion,
    _regime_at,
    _zone_at,
    _atom_columns,
    _atom_kr,
)
from validation.sweep import (
    atom_confirm_positions,
    enumerate_completion_events,
    fmt_ts,
    RECENT,
)

# --- 검토자 정답 구간 (날짜 조정 가능) ---
GROUND_TRUTH_ZONES = [
    ("Z1", "top",    "2026-01-05", "2026-01-28"),
    ("Z2", "bottom", "2026-02-10", "2026-03-02"),
    ("Z3", "top",    "2026-04-14", "2026-05-10"),
]
ZONE_BUFFER_BARS = 30
SYMBOL = "ETHUSDT"
INTERVAL = "4h"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MA_WARMUP_BARS = 240
WARMUP_EXTRA = 60  # 240 + 60봉 Z1 이전 확보 목표

# 직전 라운드(단건 1,000봉 fetch) 스냅샷 — before/after 비교용
# 규칙 수정 1 스냅샷(첫 확정봉 구조·MA윈도96) — 수정 2 before/after 비교용
PREV_SEMANTICS_R1 = {
    "Z1": {
        "trans_stage": 2,
        "trans_modes": "STRUCT_BLOCKED=8",
        "trans_hits": 0,
    },
    "Z2": {
        "trans_stage": 2,
        "trans_modes": "STRUCT_BLOCKED=6, ATOM_ABSENT=2",
        "trans_hits": 0,
        "w96_form_d3": 0,
        "form_label_dist": "None=6",
    },
}

# 규칙 수정 1 이전(완성봉 구조·윈도24 통일) — 참고용
PREV_SEMANTICS_R0 = {
    "Z1": {
        "trans_stage": 2,
        "trans_modes": "STRUCT_BLOCKED=6, NOT_PAIRED=1, ATOM_ABSENT=1",
        "trans_hits": 0,
        "f6_4_family": "STRUCT_BLOCKED",
    },
    "Z2": {
        "trans_stage": 1,
        "trans_modes": "NOT_PAIRED=2, ATOM_ABSENT=6",
        "trans_hits": 0,
        "f6_5c_w96_form_d3": 0,
        "f6_5c_w96_comp_d3": 0,
    },
}

PREV_ROUND = {
    "fetch_bars": 1000,
    "warmup_ok": False,
    "shortfall_bars": 154,
    "Z1": {
        "trend_stage": 0,
        "trans_stage": 2,
        "trend_modes": "NO_RULE_MATCH=29",
        "trans_modes": "STRUCT_BLOCKED=6, NOT_PAIRED=1, ATOM_ABSENT=1",
        "d3_buffer_bars": 8,
        "family_cmp": "④⑤ 변곡점이 더 멀리 진행",
    },
    "Z3": {"trend_hit_count": 8},
}

LARGE_SUFFIX = WAVE_LAYER_ROLES["large"]
Z2_HEAVY_ATOMS = [
    {"name": "MA5 쌍바닥", "rule": "F6-5c-a", "sig": "ma5_db", "kind_col": "ma5_db_kind", "req_kind": None},
    {"name": "대파동 쓰리바닥", "rule": "F6-5c-a",
     "sig": f"stoch_tb_{LARGE_SUFFIX}", "kind_col": f"stoch_tb_kind_{LARGE_SUFFIX}", "req_kind": None},
    {"name": "MA10 쌍바닥 kind=LL", "rule": "F6-5c-b",
     "sig": "ma10_db", "kind_col": "ma10_db_kind", "req_kind": "LL"},
    {"name": "대파동 쌍바닥 kind=HL", "rule": "F6-5c-b",
     "sig": f"stoch_db_{LARGE_SUFFIX}", "kind_col": f"stoch_db_kind_{LARGE_SUFFIX}", "req_kind": "HL"},
]

STRUCT_COLORS = {
    "U1": "#1565C0", "U2": "#1976D2", "U3": "#42A5F5",
    "D1": "#C62828", "D2": "#E53935", "D3": "#EF5350",
    None: "#BDBDBD",
}
ZONE_COLORS = {"top": "#FFCDD2", "bottom": "#C8E6C9"}

WAVE_LAYERS = ["small", "mid", "large"]
WAVE_PATTERNS = ["db", "dt", "tb", "tt"]
MA_PERIODS = [5, 10]
MA_PATTERNS = ["db", "dt"]
TREND_LAYERS = ["small", "mid"]
TREND_PATTERNS = ["db", "dt"]

TRANS_STAGE = {"ATOM_ABSENT": 0, "NOT_PAIRED": 1, "STRUCT_BLOCKED": 2, "HIT": 3}
TREND_STAGE = {"NO_SIGNAL": 0, "NO_RULE_MATCH": 1, "RULE_BLOCKED": 2, "HIT": 3}


def compute_paginated_limit():
    """Z1 시작 - (240+60)봉 이전까지 덮도록 total_limit 산출."""
    z1_start = pd.Timestamp(GROUND_TRUTH_ZONES[0][2])
    need_before = z1_start - pd.Timedelta(hours=4 * (MA_WARMUP_BARS + WARMUP_EXTRA))
    span_bars = int((pd.Timestamp.now() - need_before) / pd.Timedelta(hours=4)) + 50
    return max(1600, span_bars)


def load_df_gt(symbol, interval):
    """페이지네이션 fetch + 앱과 동일한 지표 파이프라인."""
    limit = compute_paginated_limit()
    raw = fetch_klines_paginated(symbol, get_fetch_interval(interval), limit)
    if not raw:
        raise RuntimeError("fetch_klines_paginated 빈 응답")
    df = build_dataframe(raw)
    if df is None:
        raise RuntimeError("build_dataframe 실패")
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)
    df = add_moving_averages(df)
    df = add_ma_patterns(df)
    df = add_stochastic_slow_layers(df)
    return df, limit


def _ts_end(date_str):
    return pd.Timestamp(date_str) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)


def zone_ranges(df):
    """구간·버퍼 위치 집합과 메타."""
    out = []
    for zid, ztype, start_d, end_d in GROUND_TRUTH_ZONES:
        start_ts = pd.Timestamp(start_d)
        end_ts = _ts_end(end_d)
        in_zone = (df.index >= start_ts) & (df.index <= end_ts)
        zone_pos = np.where(in_zone)[0].tolist()
        if zone_pos:
            lo = max(0, min(zone_pos) - ZONE_BUFFER_BARS)
            hi = min(len(df) - 1, max(zone_pos) + ZONE_BUFFER_BARS)
        else:
            lo, hi = 0, 0
        out.append({
            "id": zid, "type": ztype,
            "start": start_ts, "end": end_ts,
            "start_d": start_d, "end_d": end_d,
            "zone_pos": zone_pos, "buffer_pos": set(range(lo, hi + 1)),
            "buffer_lo": lo, "buffer_hi": hi,
        })
    return out


def history_coverage(df, zones, fetch_limit):
    """Z1 워밍업 포함 히스토리 확보 확인."""
    first, last = df.index[0], df.index[-1]
    z1 = zones[0]
    need_before = z1["start"] - pd.Timedelta(hours=4 * (MA_WARMUP_BARS + WARMUP_EXTRA))
    ok = first <= need_before
    shortfall = 0 if ok else int((first - need_before) / pd.Timedelta(hours=4))
    return {
        "first_ts": first, "last_ts": last, "bars": len(df),
        "fetch_limit": fetch_limit,
        "z1_start": z1["start"], "need_before": need_before,
        "ok": ok,
        "shortfall_bars": shortfall,
        "paginated": True,
    }


def z1_quality_gate(df, zone_info):
    """Z1 구간 및 직전 MA240 워밍업 봉: MA240 non-NaN + 레짐 판단가능. 미충족 시 중단."""
    if not zone_info["zone_pos"]:
        raise AssertionError("Z1 zone_pos empty")
    zone_lo = min(zone_info["zone_pos"])
    zone_hi = max(zone_info["zone_pos"])
    warmup_start = zone_lo - MA_WARMUP_BARS
    if warmup_start < 0:
        raise AssertionError(
            f"Z1 검증 게이트 실패: 구간 시작 이전 {MA_WARMUP_BARS}봉 미달 "
            f"(부족 {-warmup_start}봉, first={fmt_ts(df.index[0])})"
        )
    bad_ma, bad_reg = [], []
    for pos in range(warmup_start, zone_hi + 1):
        row = df.iloc[pos]
        if pd.isna(row.get("MA240")):
            bad_ma.append(pos)
        if _regime_at(row) == "판단불가":
            bad_reg.append(pos)
    if bad_ma or bad_reg:
        parts = []
        if bad_ma:
            parts.append(f"MA240 NaN {len(bad_ma)}봉 (first={fmt_ts(df.index[bad_ma[0]])})")
        if bad_reg:
            parts.append(f"레짐 판단불가 {len(bad_reg)}봉 (first={fmt_ts(df.index[bad_reg[0]])})")
        raise AssertionError("Z1 검증 게이트 실패: " + "; ".join(parts))
    return {
        "warmup_start_pos": warmup_start,
        "zone_lo": zone_lo,
        "zone_hi": zone_hi,
        "checked_bars": zone_hi - warmup_start + 1,
        "ma240_valid": zone_hi - warmup_start + 1,
        "regime_valid": zone_hi - warmup_start + 1,
    }


def _atom_positions_filtered(df, sig_col, kind_col, req_kind=None):
    """전 구간 원자 확정 봉 (kind 필터 optional)."""
    out = []
    if sig_col not in df.columns:
        return out
    for pos in range(len(df)):
        row = df.iloc[pos]
        if pd.isna(row.get(sig_col)):
            continue
        k = row.get(kind_col) if kind_col in df.columns else None
        k = None if k is None or pd.isna(k) else str(k)
        if req_kind is not None and k != req_kind:
            continue
        out.append((pos, df.index[pos], k))
    return out


Z2_WINDOW_SIZES = [24, 48, 96]
Z2_CF_RULE_IDS = ["F6-5c-a", "F6-5c-b"]


def _compress_label_timeline(df, positions, label_fn):
    """positions 순서대로 label_fn(pos) 압축 구간."""
    if not positions:
        return [], Counter()
    labels = [(df.index[p], label_fn(df.iloc[p])) for p in positions]
    counts = Counter(lab for _, lab in labels)
    segments = []
    cur, start, end, n = labels[0][1], labels[0][0], labels[0][0], 1
    for ts, lab in labels[1:]:
        if lab == cur:
            n += 1
            end = ts
        else:
            segments.append({"label": cur, "start": start, "end": end, "bars": n})
            cur, start, end, n = lab, ts, ts, 1
    segments.append({"label": cur, "start": start, "end": end, "bars": n})
    return segments, counts


def regime_timeline_full(df):
    """전 구간 레짐(MA120 vs MA240) 압축 타임라인."""
    positions = list(range(len(df)))
    segments, counts = _compress_label_timeline(df, positions, lambda row: _regime_at(row))
    return segments, counts


def regime_z1_buffer_summary(df, zone_info):
    """Z1±버퍼 레짐 요약 + UP 존재 여부."""
    buffer_pos = sorted(zone_info["buffer_pos"])
    segments, counts = _compress_label_timeline(df, buffer_pos, lambda row: _regime_at(row))
    up_bars = [p for p in buffer_pos if _regime_at(df.iloc[p]) == "UP"]
    return {
        "segments": segments,
        "counts": counts,
        "total": len(buffer_pos),
        "up_count": len(up_bars),
        "has_up": len(up_bars) > 0,
        "up_timestamps": [fmt_ts(df.index[p]) for p in up_bars[:20]],
    }


def u_label_counts_full(df):
    """전체 1,600봉 U1/U2/U3 출현 수."""
    counts = Counter()
    for pos in range(len(df)):
        lab = classify_structure_at(df, pos)
        if lab in ("U1", "U2", "U3"):
            counts[lab] += 1
    return {k: counts.get(k, 0) for k in ("U1", "U2", "U3")}


def z1_trend_hits_detail(diag):
    """Z1 ①② rule 매칭(allowed True/False) 상세."""
    hits = []
    for c in diag["trend_confirms"]:
        if not c["result"].startswith("HIT:"):
            continue
        rid_part = c["result"].split("HIT:")[1]
        rid = rid_part.split()[0]
        allowed = "allowed=True" in c["result"]
        direction = "상승" if c["pattern"] == "db" else "하락"
        hits.append({
            "rule_id": rid,
            "direction": direction,
            "allowed": allowed,
            "ts": c["ts"],
            "regime": c["regime"],
            "zone": c["zone"],
            "kind": c["kind"],
            "layer": c["layer"],
            "pattern": c["pattern"],
        })
    return hits


def z1_d3_context(df, zone_info):
    """Z1 버퍼 D3 봉 위치·가격 맥락."""
    buffer_pos = zone_info["buffer_pos"]
    zone_pos_set = set(zone_info["zone_pos"])
    zone_lo = min(zone_info["zone_pos"])
    zone_hi = max(zone_info["zone_pos"])
    bars = []
    for pos in sorted(buffer_pos):
        if classify_structure_at(df, pos) != "D3":
            continue
        if pos < zone_lo:
            ctx = "버퍼 좌측(구간 전)"
        elif pos in zone_pos_set:
            ctx = "정답 구간 내"
        else:
            ctx = "버퍼 우측(구간 후·폭락부)"
        bars.append({
            "pos": pos,
            "ts": df.index[pos],
            "close": float(df.iloc[pos]["close"]),
            "ctx": ctx,
        })
    if bars:
        closes = [b["close"] for b in bars]
        price_note = f"close {min(closes):.2f}~{max(closes):.2f}"
        date_range = f"{fmt_ts(bars[0]['ts'])} ~ {fmt_ts(bars[-1]['ts'])}"
    else:
        price_note = "-"
        date_range = "없음"
    ctx_counts = Counter(b["ctx"] for b in bars)
    return {
        "bars": bars,
        "count": len(bars),
        "date_range": date_range,
        "price_note": price_note,
        "ctx_counts": ctx_counts,
    }


def _rule_atoms(rule_id):
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rid, bullish, _window = parse_transition_row(row)
        if rid == rule_id:
            return structure, atoms, bullish
    raise KeyError(rule_id)


def _event_atom_bars(early, comp, a_pos, b_pos):
    """완성 사건 (early, comp)에서 A/B 원자 확정 봉 위치."""
    if early in a_pos and comp in b_pos:
        return early, comp
    if comp in a_pos and early in b_pos:
        return comp, early
    a_bar = next((p for p in (early, comp) if p in a_pos), None)
    b_bar = next((p for p in (early, comp) if p in b_pos), None)
    return a_bar, b_bar


def z2_window_structure_cross(df, buffer_pos):
    """Z2 F6-5c-a/b 윈도×구조 교차 (관측 시나리오, 엔진 불변)."""
    buf = set(buffer_pos)
    d3_bars = []
    for pos in sorted(buffer_pos):
        if classify_structure_at(df, pos) == "D3":
            d3_bars.append({"pos": pos, "ts": df.index[pos], "close": float(df.iloc[pos]["close"])})

    per_rule = {}
    w96_comps = []

    for rule_id in Z2_CF_RULE_IDS:
        structure, atoms, bullish = _rule_atoms(rule_id)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        per_rule[rule_id] = {"structure": structure, "windows": {}}

        for w in Z2_WINDOW_SIZES:
            events = enumerate_completion_events(
                a_pos, b_pos, recent=w, df=df, atoms=atoms, structure=structure,
            )
            rows = []
            for comp in sorted(events):
                if comp not in buf:
                    continue
                early, _ = events[comp]
                a_bar, b_bar = _event_atom_bars(early, comp, a_pos, b_pos)
                if a_bar is not None and b_bar is not None:
                    form_pos, _, _ = pair_formation_completion(df, atoms, a_bar, b_bar)
                else:
                    form_pos = early
                form_struct = classify_structure_at(df, form_pos)
                comp_struct = classify_structure_at(df, comp)
                row = {
                    "window": w,
                    "rule_id": rule_id,
                    "early_ts": df.index[early],
                    "comp_ts": df.index[comp],
                    "gap": comp - early,
                    "a_ts": df.index[a_bar] if a_bar is not None else None,
                    "b_ts": df.index[b_bar] if b_bar is not None else None,
                    "struct_a": classify_structure_at(df, a_bar) if a_bar is not None else None,
                    "struct_b": classify_structure_at(df, b_bar) if b_bar is not None else None,
                    "struct_form": form_struct,
                    "struct_comp": comp_struct,
                    "form_is_d3": form_struct == structure,
                    "comp_is_d3": comp_struct == structure,
                    "comp_pos": comp,
                }
                rows.append(row)
                if w == 96:
                    w96_comps.append(comp)
            per_rule[rule_id]["windows"][w] = {"events": rows, "count": len(rows)}

    # D3 봉 ↔ 가장 가까운 완성 봉 (w=96, 두 공식 합산)
    w96_set = sorted(set(w96_comps))
    for d3 in d3_bars:
        if w96_set:
            dist = min(abs(d3["pos"] - c) for c in w96_set)
            nearest = min(w96_set, key=lambda c: abs(c - d3["pos"]))
            d3["nearest_comp_dist_w96"] = dist
            d3["nearest_comp_ts_w96"] = fmt_ts(df.index[nearest])
        else:
            d3["nearest_comp_dist_w96"] = None
            d3["nearest_comp_ts_w96"] = None

    w96_form_d3_hits = sum(
        1 for rid in Z2_CF_RULE_IDS
        for row in per_rule[rid]["windows"][96]["events"]
        if row["form_is_d3"]
    )
    w96_comp_d3_hits = sum(
        1 for rid in Z2_CF_RULE_IDS
        for row in per_rule[rid]["windows"][96]["events"]
        if row["comp_is_d3"]
    )

    return {
        "per_rule": per_rule,
        "d3_bars": d3_bars,
        "w96_form_d3_count": w96_form_d3_hits,
        "w96_d3_completion_count": w96_comp_d3_hits,
        "w96_form_d3_by_rule": {
            rid: sum(1 for row in per_rule[rid]["windows"][96]["events"] if row["form_is_d3"])
            for rid in Z2_CF_RULE_IDS
        },
        "w96_comp_d3_by_rule": {
            rid: sum(1 for row in per_rule[rid]["windows"][96]["events"] if row["comp_is_d3"])
            for rid in Z2_CF_RULE_IDS
        },
    }


def analyze_4c(df, zones, zone_results):
    """관측 라운드 4c: Z1 레짐 상세 + Z2 윈도×구조 교차."""
    z1_info = zones[0]
    z2_info = zones[1]
    z1_diag = next(d for z, d in zone_results if z["id"] == "Z1")

    reg_full_seg, reg_full_counts = regime_timeline_full(df)
    return {
        "regime_full": {"segments": reg_full_seg, "counts": reg_full_counts},
        "regime_z1_buffer": regime_z1_buffer_summary(df, z1_info),
        "u_counts": u_label_counts_full(df),
        "z1_trend_hits": z1_trend_hits_detail(z1_diag),
        "z1_d3": z1_d3_context(df, z1_info),
        "z2_cross": z2_window_structure_cross(df, z2_info["buffer_pos"]),
    }


def z2_heavy_atoms(df, buffer_pos):
    """Z2±버퍼 D3 공식(F6-5c-a/b) 중량 원자 4종 상세."""
    buf = sorted(buffer_pos)
    reports = []
    for spec in Z2_HEAVY_ATOMS:
        all_c = _atom_positions_filtered(df, spec["sig"], spec["kind_col"], spec["req_kind"])
        in_buf = [(p, ts, k) for p, ts, k in all_c if p in buffer_pos]
        entry = {
            "name": spec["name"], "rule": spec["rule"],
            "in_buffer": in_buf, "global_count": len(all_c),
        }
        if in_buf:
            entry["status"] = "확정"
            entry["nearest_dist"] = 0
            entry["nearest_ts"] = None
        elif not all_c:
            entry["status"] = "없음(전구간)"
            entry["nearest_dist"] = None
            entry["nearest_ts"] = None
        else:
            best_d, best = None, None
            for p, ts, k in all_c:
                d = min(abs(p - b) for b in buf)
                if best_d is None or d < best_d:
                    best_d, best = d, (ts, k)
            entry["status"] = "없음(버퍼外)"
            entry["nearest_dist"] = best_d
            entry["nearest_ts"] = best
        reports.append(entry)
    return reports


def z3_trend_hit_count(diag):
    return sum(1 for c in diag["trend_confirms"]
               if "HIT:" in c["result"] and "allowed=True" in c["result"])


def atom_inventory(df, buffer_pos):
    """A. 구간±버퍼 내 모든 확정 신호."""
    items = []
    layer_kr = {"small": "소", "mid": "중", "large": "대"}
    pat_kr = {"db": "쌍바닥", "dt": "쌍봉", "tb": "쓰리바닥", "tt": "쓰리봉"}

    for layer in WAVE_LAYERS:
        suffix = WAVE_LAYER_ROLES[layer]
        for pat in WAVE_PATTERNS:
            sig = f"stoch_{pat}_{suffix}"
            kind_col = f"stoch_{pat}_kind_{suffix}"
            found = []
            if sig in df.columns:
                for pos in buffer_pos:
                    if pd.notna(df.iloc[pos].get(sig)):
                        k = df.iloc[pos].get(kind_col) if kind_col in df.columns else None
                        k = None if k is None or pd.isna(k) else str(k)
                        found.append((df.index[pos], k))
            items.append({
                "category": "wave",
                "label": f"{layer_kr[layer]}파동 {pat_kr[pat]}",
                "key": f"wave/{layer}/{pat}",
                "entries": found,
            })

    for period in MA_PERIODS:
        for pat in MA_PATTERNS:
            sig = f"ma{period}_{pat}"
            kind_col = f"ma{period}_{pat}_kind"
            found = []
            if sig in df.columns:
                for pos in buffer_pos:
                    if pd.notna(df.iloc[pos].get(sig)):
                        k = df.iloc[pos].get(kind_col) if kind_col in df.columns else None
                        k = None if k is None or pd.isna(k) else str(k)
                        found.append((df.index[pos], k))
            items.append({
                "category": "ma",
                "label": f"MA{period} {pat_kr[pat]}",
                "key": f"ma/{period}/{pat}",
                "entries": found,
            })
    return items


def _trend_mismatch(regime, zone, layer, pattern, kind):
    """어느 키가 불일치인지 (동일 layer·pattern RULE_TABLE 행 대비)."""
    parts = []
    for r, z, lay, pat, k, rule_id, _ in RULE_TABLE:
        if lay != layer or pat != pattern:
            continue
        fails = []
        if r != regime:
            fails.append(f"regime={regime}≠{r}")
        if z != zone:
            fails.append(f"zone={zone}≠{z}")
        if k is not None and kind != k:
            fails.append(f"kind={kind}≠{k}")
        if fails:
            parts.append(f"{rule_id}({','.join(fails)})")
    return "; ".join(parts) if parts else "RULE_TABLE 매칭 행 없음"


def evaluate_trend_in_zone(df, buffer_pos):
    """B. 추세 8행 — 구간±버퍼 내 확정 봉별 평가."""
    confirms = []
    rule_summary = {row[5]: {"status": "NO_SIGNAL", "stage": 0, "detail": "구간 내 확정 없음"}
                    for row in RULE_TABLE}

    for layer in TREND_LAYERS:
        suffix = WAVE_LAYER_ROLES[layer]
        for pattern in TREND_PATTERNS:
            sig_col = f"stoch_{pattern}_{suffix}"
            kind_col = f"stoch_{pattern}_kind_{suffix}"
            if sig_col not in df.columns:
                continue
            for pos in sorted(buffer_pos):
                row = df.iloc[pos]
                if pd.isna(row.get(sig_col)):
                    continue
                ts = df.index[pos]
                regime = _regime_at(row)
                zone = _zone_at(regime, row.get("close"), row.get("MA20"), row.get("MA60"))
                raw_k = row.get(kind_col) if kind_col in df.columns else None
                kind = None if raw_k is None or pd.isna(raw_k) else str(raw_k)

                if kind == "EQ":
                    result = "SKIP:kind=EQ"
                    stage = 1
                else:
                    matched = evaluate_rule(regime, zone, layer, pattern, kind)
                    if matched:
                        rid, allowed = matched
                        result = f"HIT:{rid} allowed={allowed}"
                        stage = 3 if allowed else 2
                        st = "HIT" if allowed else "RULE_BLOCKED"
                        if TRANS_STAGE.get(st, 0) >= 0:
                            prev = rule_summary[rid]["stage"]
                            if stage > prev:
                                rule_summary[rid] = {"status": st, "stage": stage,
                                                       "detail": f"{fmt_ts(ts)} {result}"}
                    else:
                        result = f"NO_MATCH: {_trend_mismatch(regime, zone, layer, pattern, kind)}"
                        stage = 1

                confirms.append({
                    "ts": ts, "layer": layer, "pattern": pattern, "kind": kind,
                    "regime": regime, "zone": zone, "result": result, "stage": stage,
                })

    max_stage = max((c["stage"] for c in confirms), default=0)
    family_stage = max((v["stage"] for v in rule_summary.values()), default=0)
    return confirms, rule_summary, family_stage


def _min_pair_gap(a_pos, b_pos):
    if not a_pos or not b_pos:
        return None
    a_arr = np.array(a_pos)
    b_arr = np.array(b_pos)
    return int(np.min(np.abs(a_arr[:, None] - b_arr[None, :])))


def evaluate_transition_in_zone(df, buffer_pos):
    """B. 변곡점 8행 — 완성 봉이 버퍼에 떨어지는 완성 사건 게이트 분류."""
    per_rule = []
    all_events = []

    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        a_buf = [p for p in a_pos if p in buffer_pos]
        b_buf = [p for p in b_pos if p in buffer_pos]

        zone_events = []
        for i in a_pos:
            for j in b_pos:
                if abs(i - j) > window - 1:
                    continue
                form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                if comp_pos not in buffer_pos:
                    continue
                actual = classify_structure_at(df, form_pos)
                if actual == structure:
                    mode = "HIT"
                else:
                    mode = f"STRUCT_BLOCKED:{actual}"
                ev = {
                    "comp_pos": comp_pos, "comp_ts": df.index[comp_pos],
                    "form_pos": form_pos, "form_ts": df.index[form_pos],
                    "gap": comp_pos - form_pos,
                    "mode": mode, "actual": actual,
                }
                zone_events.append(ev)
                all_events.append({**ev, "rule_id": rule_id, "bullish": bullish})

        gap = None
        if zone_events:
            best = max(zone_events, key=lambda e: TRANS_STAGE.get(e["mode"].split(":")[0], 0))
            summary_mode = best["mode"]
            stage = TRANS_STAGE.get(summary_mode.split(":")[0], 0)
            gap = min(e["gap"] for e in zone_events)
        elif not a_buf and not b_buf:
            summary_mode = "ATOM_ABSENT"
            stage = 0
        elif not a_buf or not b_buf:
            missing = _atom_kr(atoms[0]) if not a_buf else _atom_kr(atoms[1])
            summary_mode = f"ATOM_ABSENT:{missing}"
            stage = 0
            gap = _min_pair_gap(a_buf or a_pos, b_buf or b_pos)
        else:
            summary_mode = "NOT_PAIRED"
            stage = 1
            gap = _min_pair_gap(a_buf, b_buf)

        per_rule.append({
            "rule_id": rule_id, "structure": structure, "bullish": bullish,
            "a_buf": len(a_buf), "b_buf": len(b_buf),
            "zone_events": zone_events, "summary_mode": summary_mode, "stage": stage,
            "min_gap": gap,
        })

    family_stage = max((r["stage"] for r in per_rule), default=0)
    return per_rule, all_events, family_stage


def structure_timeline(df, buffer_pos):
    """C. 구간±버퍼 구조 라벨 타임라인 압축."""
    labels = [(df.index[p], classify_structure_at(df, p)) for p in sorted(buffer_pos)]
    if not labels:
        return [], Counter(), 0

    counts = Counter(lab for _, lab in labels)
    segments = []
    cur_label, cur_start, cur_end, cur_n = labels[0][1], labels[0][0], labels[0][0], 1
    for ts, lab in labels[1:]:
        if lab == cur_label:
            cur_n += 1
            cur_end = ts
        else:
            segments.append({"label": cur_label, "start": cur_start, "end": cur_end, "bars": cur_n})
            cur_label, cur_start, cur_end, cur_n = lab, ts, ts, 1
    segments.append({"label": cur_label, "start": cur_start, "end": cur_end, "bars": cur_n})
    return segments, counts, len(labels)


def proximity(df, zone_pos, buffer_pos, trend_confirms, trans_events):
    """D. 구간 경계에서 가장 가까운 C0 HIT 신호까지 봉 거리."""
    zone_lo = min(zone_pos) if zone_pos else 0
    zone_hi = max(zone_pos) if zone_pos else 0

    trend_hits = [df.index.get_loc(c["ts"]) for c in trend_confirms if c["result"].startswith("HIT:") and "allowed=True" in c["result"]]
    trans_hits = [e["comp_pos"] for e in trans_events if e["mode"] == "HIT"]
    all_hits = sorted(set(trend_hits + trans_hits))

    def nearest_dist(ref_pos, positions, direction):
        if not positions:
            return None, None
        if direction == "before":
            cands = [p for p in positions if p < ref_pos]
            if not cands:
                return None, None
            p = max(cands)
            return ref_pos - p, df.index[p]
        cands = [p for p in positions if p > ref_pos]
        if not cands:
            return None, None
        p = min(cands)
        return p - ref_pos, df.index[p]

    trans_all = [e["comp_pos"] for e in trans_events]
    trend_all = [df.index.get_loc(c["ts"]) for c in trend_confirms]

    return {
        "hit_trend": nearest_dist(zone_lo, all_hits, "before"),
        "hit_trend_after": nearest_dist(zone_hi, all_hits, "after"),
        "any_trend_before": nearest_dist(zone_lo, trend_all, "before"),
        "any_trend_after": nearest_dist(zone_hi, trend_all, "after"),
        "any_trans_before": nearest_dist(zone_lo, trans_all, "before"),
        "any_trans_after": nearest_dist(zone_hi, trans_all, "after"),
        "hit_count_in_buffer": len([p for p in all_hits if p in buffer_pos]),
    }


def draw_gt_chart(df, zone_info, inventory, trans_events, trend_confirms, segments):
    """E. 구간별 확대 PNG."""
    zid = zone_info["id"]
    buf_lo, buf_hi = zone_info["buffer_lo"], zone_info["buffer_hi"]
    sub = df.iloc[buf_lo:buf_hi + 1]
    zone_start, zone_end = zone_info["start"], zone_info["end"]

    fig, (ax, ax_strip) = plt.subplots(
        2, 1, figsize=(14, 6), gridspec_kw={"height_ratios": [4, 0.4]}, sharex=True)

    ax.plot(sub.index, sub["close"], color="#222", lw=0.9)
    ax.axvspan(zone_start, zone_end, color=ZONE_COLORS.get(zone_info["type"], "#EEE"), alpha=0.25)

    glyph_map = {
        "wave/db": ("v", "#2E7D32"), "wave/dt": ("^", "#C62828"),
        "wave/tb": ("D", "#00897B"), "wave/tt": ("D", "#AD1457"),
        "ma/db": ("s", "#1565C0"), "ma/dt": ("s", "#E65100"),
    }
    for item in inventory:
        parts = item["key"].split("/")
        gkey = f"{parts[0]}/{parts[2]}" if parts[0] == "wave" else f"{parts[0]}/{parts[2]}"
        marker, color = glyph_map.get(gkey, ("o", "#666"))
        for ts, _ in item["entries"]:
            if buf_lo <= df.index.get_loc(ts) <= buf_hi:
                ax.scatter(ts, df.loc[ts, "close"], marker=marker, s=28, color=color,
                           edgecolors="white", linewidths=0.3, zorder=5)

    for e in trans_events:
        color = "#0B8F45" if e["bullish"] else "#C62828"
        ls = "-" if e["mode"] == "HIT" else "--"
        ax.axvline(e["comp_ts"], color=color, lw=1.0, alpha=0.75, linestyle=ls)

    for c in trend_confirms:
        if "HIT:" in c["result"] and "allowed=True" in c["result"]:
            ax.axvline(c["ts"], color="#6A1B9A", lw=0.9, alpha=0.6, linestyle=":")

    ax.set_ylabel("close")
    ax.set_title(f"{SYMBOL} {INTERVAL} — {zid} ({zone_info['type']}) "
                 f"{zone_info['start_d']}~{zone_info['end_d']} ±{ZONE_BUFFER_BARS}봉")

    # 구조 스트립
    buf_positions = sorted(zone_info["buffer_pos"])
    if buf_positions:
        strip_labels = [classify_structure_at(df, p) for p in buf_positions]
        strip_ts = [df.index[p] for p in buf_positions]
        colors = [STRUCT_COLORS.get(l, "#BDBDBD") for l in strip_labels]
        for i in range(len(strip_ts) - 1):
            ax_strip.axvspan(strip_ts[i], strip_ts[i + 1], color=colors[i], alpha=0.9)
        if len(strip_ts) == 1:
            ax_strip.axvspan(strip_ts[0], strip_ts[0] + pd.Timedelta(hours=4),
                             color=colors[0], alpha=0.9)
    ax_strip.set_yticks([])
    ax_strip.set_ylabel("구조", fontsize=8)
    ax_strip.set_xlabel("time")

    legend_elems = [
        Patch(facecolor=ZONE_COLORS.get(zone_info["type"], "#EEE"), alpha=0.4, label="정답구간"),
        plt.Line2D([0], [0], color="#0B8F45", ls="-", label="변곡 HIT"),
        plt.Line2D([0], [0], color="#C62828", ls="--", label="변곡 차단"),
        plt.Line2D([0], [0], color="#6A1B9A", ls=":", label="추세 HIT"),
    ]
    ax.legend(handles=legend_elems, loc="upper left", fontsize=7)
    fig.autofmt_xdate()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, f"gt_{zid}.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def diagnose_zone(df, zone_info, zid=None):
    buffer_pos = zone_info["buffer_pos"]
    inventory = atom_inventory(df, buffer_pos)
    trend_confirms, trend_rules, trend_family_stage = evaluate_trend_in_zone(df, buffer_pos)
    trans_rules, trans_events, trans_family_stage = evaluate_transition_in_zone(df, buffer_pos)
    segments, struct_counts, struct_total = structure_timeline(df, buffer_pos)
    prox = proximity(df, zone_info["zone_pos"], buffer_pos, trend_confirms, trans_events)

    if trend_family_stage > trans_family_stage:
        family_cmp = "①② 추세가 더 멀리 진행"
    elif trans_family_stage > trend_family_stage:
        family_cmp = "④⑤ 변곡점이 더 멀리 진행"
    else:
        family_cmp = f"동일 단계 (stage={trend_family_stage})"

    result = {
        "inventory": inventory,
        "trend_confirms": trend_confirms,
        "trend_rules": trend_rules,
        "trans_rules": trans_rules,
        "trans_events": trans_events,
        "segments": segments,
        "struct_counts": struct_counts,
        "struct_total": struct_total,
        "proximity": prox,
        "trend_family_stage": trend_family_stage,
        "trans_family_stage": trans_family_stage,
        "family_cmp": family_cmp,
    }
    if zid == "Z2":
        result["heavy_atoms"] = z2_heavy_atoms(df, buffer_pos)
    return result


def append_report_4c(L, r4c):
    """관측 라운드 4c 섹션."""
    L.append("---")
    L.append("")
    L.append("## 관측 라운드 4c — Z1 레짐 상세 + Z2 윈도×구조 교차")
    L.append("")

    # 작업 1-1: 레짐 타임라인
    L.append("### 4c-1. 레짐 타임라인 (전 구간)")
    L.append("")
    rf = r4c["regime_full"]
    parts = []
    for seg in rf["segments"]:
        if seg["label"] == "판단불가":
            continue
        parts.append(f"{seg['label']} {fmt_ts(seg['start'])}~{fmt_ts(seg['end'])} ({seg['bars']}봉)")
    if parts:
        L.append("- " + " / ".join(parts[:40]))
        if len(parts) > 40:
            L.append(f"- … 외 {len(parts)-40}구간")
    L.append("")
    L.append("| 레짐 | 전 구간 봉수 |")
    L.append("|---|---|")
    for k in ("UP", "DOWN", "판단불가"):
        L.append(f"| {k} | {rf['counts'].get(k, 0)} |")
    L.append("")

    rz1 = r4c["regime_z1_buffer"]
    L.append("**Z1±버퍼 레짐:**")
    z1parts = [f"{s['label']} {fmt_ts(s['start'])}~{fmt_ts(s['end'])} ({s['bars']}봉)"
               for s in rz1["segments"]]
    L.append("- " + (" / ".join(z1parts) if z1parts else "없음"))
    L.append(f"- UP 봉 수: {rz1['up_count']}/{rz1['total']}")
    L.append(f"- **Z1±버퍼 UP 존재: {'예' if rz1['has_up'] else '아니오'}**")
    if rz1["up_timestamps"]:
        L.append(f"- UP 타임스탬프(일부): {', '.join(rz1['up_timestamps'])}")
    L.append("")

    # 1-2: Z1 trend hits
    L.append("### 4c-2. Z1 ①② rule 매칭 상세")
    L.append("")
    hits = r4c["z1_trend_hits"]
    if hits:
        L.append("| rule_id | 방향 | allowed | 확정 봉 | regime | zone | kind |")
        L.append("|---|---|---|---|---|---|---|")
        for h in hits:
            L.append(f"| {h['rule_id']} | {h['direction']} | {h['allowed']} | {fmt_ts(h['ts'])} | "
                     f"{h['regime']} | {h['zone']} | {h['kind'] or '-'} |")
    else:
        L.append("- rule 매칭(HIT) 없음")
    L.append("")

    # 1-3: Z1 D3
    d3 = r4c["z1_d3"]
    L.append("### 4c-3. Z1 D3 봉 위치·가격 맥락")
    L.append("")
    L.append(f"- D3 봉 수(버퍼): {d3['count']}")
    L.append(f"- 날짜 범위: {d3['date_range']}")
    L.append(f"- close 범위: {d3['price_note']}")
    for ctx, n in d3["ctx_counts"].items():
        L.append(f"- {ctx}: {n}봉")
    if d3["bars"]:
        L.append("")
        L.append("| 시각 | close | 맥락 |")
        L.append("|---|---|---|")
        for b in d3["bars"]:
            L.append(f"| {fmt_ts(b['ts'])} | {b['close']:.2f} | {b['ctx']} |")
    L.append("")

    # 1-4: U labels
    uc = r4c["u_counts"]
    L.append("### 4c-4. U 라벨 전수 (전체 fetch 봉)")
    L.append("")
    L.append(f"| U1 | U2 | U3 |")
    L.append(f"|---|---|---|")
    L.append(f"| {uc['U1']} | {uc['U2']} | {uc['U3']} |")
    L.append("")

    # 작업 2: Z2 cross
    z2 = r4c["z2_cross"]
    L.append("### 4c-5. Z2 F6-5c 윈도×구조 교차 (관측 시나리오)")
    L.append("")
    for rule_id in Z2_CF_RULE_IDS:
        rd = z2["per_rule"][rule_id]
        L.append(f"#### `{rule_id}` (요구 구조 {rd['structure']})")
        L.append("")
        for w in Z2_WINDOW_SIZES:
            evs = rd["windows"][w]["events"]
            L.append(f"**윈도 {w}봉 — 완성 사건 {len(evs)}건**")
            if evs:
                L.append("")
                L.append("| 완성봉 | gap | A봉 | A구조 | B봉 | B구조 | 형성구조 | 형성=D3 | 완성구조 |")
                L.append("|---|---|---|---|---|---|---|---|---|")
                for e in evs:
                    L.append(
                        f"| {fmt_ts(e['comp_ts'])} | {e['gap']} | "
                        f"{fmt_ts(e['a_ts']) if e['a_ts'] else '-'} | {e['struct_a']} | "
                        f"{fmt_ts(e['b_ts']) if e['b_ts'] else '-'} | {e['struct_b']} | "
                        f"{e['struct_form']} | {e['form_is_d3']} | {e['struct_comp']} |"
                    )
            else:
                L.append("- 없음")
            L.append("")

    L.append("### 4c-6. Z2 D3 성립 봉 ↔ 완성 사건 거리")
    L.append("")
    if z2["d3_bars"]:
        L.append("| D3 봉 | close | w96 최근접 완성봉 | 거리(봉) |")
        L.append("|---|---|---|---|")
        for d in z2["d3_bars"]:
            prox = (f"{d['nearest_comp_ts_w96']} ({d['nearest_comp_dist_w96']}봉)"
                    if d["nearest_comp_dist_w96"] is not None else "없음")
            L.append(f"| {fmt_ts(d['ts'])} | {d['close']:.2f} | {prox} | "
                     f"{d['nearest_comp_dist_w96'] if d['nearest_comp_dist_w96'] is not None else '-'} |")
    else:
        L.append("- Z2±버퍼 D3 성립 봉: 없음")
    L.append("")

    L.append("### 4c-7. 교차 사실 (윈도 96 · 형성봉/완성봉 D3)")
    L.append("")
    by_form = z2["w96_form_d3_by_rule"]
    by_comp = z2["w96_comp_d3_by_rule"]
    L.append(f"- F6-5c-a 형성=D3: {by_form['F6-5c-a']}건 / 완성=D3: {by_comp['F6-5c-a']}건")
    L.append(f"- F6-5c-b 형성=D3: {by_form['F6-5c-b']}건 / 완성=D3: {by_comp['F6-5c-b']}건")
    L.append(f"- **F6-5c 합산 형성=D3: {z2['w96_form_d3_count']}건 / 완성=D3: {z2['w96_d3_completion_count']}건**")
    L.append("")


def append_semantics_r2_ladder(L, zone_results, r4c):
    """규칙 수정 2: ④⑤ 첫 피봇 형성 기준 before/after 사다리 (수정1→2)."""
    prev = PREV_SEMANTICS_R1
    z1 = next(d for z, d in zone_results if z["id"] == "Z1")
    z2 = next(d for z, d in zone_results if z["id"] == "Z2")
    z1_hits = sum(1 for e in z1["trans_events"] if e["mode"] == "HIT")
    z2_hits = sum(1 for e in z2["trans_events"] if e["mode"] == "HIT")
    z2_cross = r4c["z2_cross"]

    z2_form_dist = Counter()
    for e in z2["trans_events"]:
        z2_form_dist[e.get("actual", "HIT")] += 1
    form_dist_str = ", ".join(f"{k}={v}" for k, v in sorted(z2_form_dist.items(), key=lambda x: str(x[0])))

    L.append("## 규칙 수정 2 before/after (④⑤ 첫 피봇 형성 + MA윈도96)")
    L.append("")
    L.append("| 구간 | 지표 | 수정1(첫 확정봉) | 수정2(첫 피봇) |")
    L.append("|---|---|---|---|")
    L.append(f"| Z1 | ④⑤ stage | {prev['Z1']['trans_stage']} | {z1['trans_family_stage']} |")
    L.append(f"| Z1 | ④⑤ 주요모드 | {prev['Z1']['trans_modes']} | {_summarize_trans_modes(z1)} |")
    L.append(f"| Z1 | 버퍼 HIT 수 | {prev['Z1']['trans_hits']} | {z1_hits} |")
    L.append(f"| Z2 | ④⑤ stage | {prev['Z2']['trans_stage']} | {z2['trans_family_stage']} |")
    L.append(f"| Z2 | ④⑤ 주요모드 | {prev['Z2']['trans_modes']} | {_summarize_trans_modes(z2)} |")
    L.append(f"| Z2 | 버퍼 HIT 수 | {prev['Z2']['trans_hits']} | {z2_hits} |")
    L.append(f"| Z2 | w96 피봇형성=D3 (F6-5c) | {prev['Z2']['w96_form_d3']} | "
             f"{z2_cross['w96_form_d3_count']} |")
    L.append(f"| Z2 | 버퍼 형성봉 라벨 분포 | {prev['Z2']['form_label_dist']} | {form_dist_str or '-'} |")
    L.append("")


def write_report(coverage, zone_results, z1_gate, z3_regression, r4c):
    L = []
    L.append("# 정답 구간 역추적 리포트 — ETHUSDT 4h (관측 라운드 4b/4c + 규칙수정2)")
    L.append("")
    L.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"- 대상: {SYMBOL} {INTERVAL}")
    L.append(f"- fetch: `fetch_klines_paginated` limit={coverage['fetch_limit']}봉 (페이지네이션)")
    L.append("- 평가 의미론: C0 엄격, ④⑤ 구조=첫 피봇, MA원자 윈도=96봉 (규칙 수정 2)")
    L.append("- 관측 전용: 수치·사실만 (제안·결론 없음)")
    L.append("")
    L.append("## 히스토리 확보")
    L.append("")
    L.append(f"- 데이터 범위: {fmt_ts(coverage['first_ts'])} ~ {fmt_ts(coverage['last_ts'])} ({coverage['bars']}봉)")
    L.append(f"- Z1 시작: {fmt_ts(coverage['z1_start'])}")
    L.append(f"- MA240+{WARMUP_EXTRA} 워밍업 필요 시점: {fmt_ts(coverage['need_before'])}")
    if coverage["ok"]:
        L.append("- Z1 워밍업 포함: **확보**")
    else:
        L.append(f"- Z1 워밍업 포함: **불충분** (부족 약 {coverage['shortfall_bars']}봉)")
    L.append("")
    L.append("### Z1 검증 게이트 (워밍업+구간)")
    L.append("")
    L.append(f"- 검사 범위: 워밍업 시작 pos={z1_gate['warmup_start_pos']} "
             f"({fmt_ts(df_index_ts_by_pos(z1_gate['warmup_start_pos']))}) "
             f"~ Z1 종료 ({fmt_ts(df_index_ts_by_pos(z1_gate['zone_hi']))})")
    L.append(f"- 검사 봉 수: {z1_gate['checked_bars']}")
    L.append(f"- MA240 유효: {z1_gate['ma240_valid']}/{z1_gate['checked_bars']}")
    L.append(f"- 레짐 판단가능: {z1_gate['regime_valid']}/{z1_gate['checked_bars']}")
    L.append("- 결과: **통과**")
    L.append("")

    matrix = []
    z1_diag = None

    for zone_info, diag in zone_results:
        zid = zone_info["id"]
        if zid == "Z1":
            z1_diag = diag
        L.append(f"## {zid} — {zone_info['type']} ({zone_info['start_d']} ~ {zone_info['end_d']})")
        L.append("")
        L.append(f"- 분석 범위: ±{ZONE_BUFFER_BARS}봉 버퍼 "
                 f"({fmt_ts(df_index_ts(zone_info, 'lo'))} ~ {fmt_ts(df_index_ts(zone_info, 'hi'))})")
        L.append(f"- 차트: [gt_{zid}.png](./gt_{zid}.png)")
        L.append("")

        L.append("### A. 원자 인벤토리")
        L.append("")
        L.append("| 검출기 | 확정 수 | 타임스탬프 (kind) |")
        L.append("|---|---|---|")
        for item in diag["inventory"]:
            if item["entries"]:
                ts_str = ", ".join(f"{fmt_ts(t)}({k or '-'})" for t, k in item["entries"])
            else:
                ts_str = "없음"
            L.append(f"| {item['label']} | {len(item['entries'])} | {ts_str} |")
        L.append("")

        L.append("### B-①. 추세 공식 (8행) — 확정 봉 평가")
        L.append("")
        if diag["trend_confirms"]:
            L.append("| 시각 | 층 | 패턴 | kind | regime | zone | 결과 |")
            L.append("|---|---|---|---|---|---|---|")
            for c in diag["trend_confirms"]:
                L.append(f"| {fmt_ts(c['ts'])} | {c['layer']} | {c['pattern']} | {c['kind'] or '-'} | "
                         f"{c['regime']} | {c['zone']} | {c['result']} |")
        else:
            L.append("- 구간±버퍼 내 소/중파동 db/dt 확정: **없음**")
        L.append("")
        L.append("**추세 8행 요약 (구간 내 최고 도달):**")
        L.append("")
        L.append("| rule_id | 상태 | 상세 |")
        L.append("|---|---|---|")
        for row in RULE_TABLE:
            rid = row[5]
            s = diag["trend_rules"][rid]
            L.append(f"| {rid} | {s['status']} | {s['detail']} |")
        L.append("")

        L.append("### B-②. 변곡점 공식 (8행) — 완성 사건 게이트 (구조=첫 피봇)")
        L.append("")
        L.append("| rule_id | 구조 | 버퍼내 A | 버퍼내 B | 버퍼내 완성사건 | 요약 모드 | 최소간격 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in diag["trans_rules"]:
            gap_s = str(r["min_gap"]) if r["min_gap"] is not None else "-"
            L.append(f"| {r['rule_id']} | {r['structure']} | {r['a_buf']} | {r['b_buf']} | "
                     f"{len(r['zone_events'])} | {r['summary_mode']} | {gap_s} |")
        L.append("")
        if diag["trans_events"]:
            L.append("**완성 사건 상세:**")
            for e in diag["trans_events"]:
                L.append(f"- `{e['rule_id']}` {fmt_ts(e['comp_ts'])}: {e['mode']} (간격={e['gap']}봉)")
        else:
            L.append("- 버퍼 내 완성 사건: 없음")
        L.append("")

        L.append("### C. 구조 라벨 타임라인")
        L.append("")
        total = diag["struct_total"] or 1
        none_pct = diag["struct_counts"].get(None, 0) / total * 100
        parts = [f"None {none_pct:.0f}%"]
        for seg in diag["segments"]:
            if seg["label"] is not None:
                lbl = seg["label"]
                parts.append(f"{lbl} {fmt_ts(seg['start'])}~{fmt_ts(seg['end'])} {seg['bars']}봉")
        L.append("- " + " / ".join(parts))
        L.append("")
        L.append("| 구조 | 봉수 | 비율 |")
        L.append("|---|---|---|")
        for lbl in ["U1", "U2", "U3", "D1", "D2", "D3", None]:
            n = diag["struct_counts"].get(lbl, 0)
            L.append(f"| {lbl if lbl else 'None'} | {n} | {n/total*100:.1f}% |")
        L.append("")

        L.append("### D. 근접도 (구간 경계 ↔ C0 HIT)")
        L.append("")
        p = diag["proximity"]
        def _fmt_dist(pair):
            if pair[0] is None:
                return "없음"
            return f"{pair[0]}봉 ({fmt_ts(pair[1])})"
        L.append(f"- 구간 시작 이전 최근 HIT: {_fmt_dist(p['hit_trend'])}")
        L.append(f"- 구간 종료 이후 최근 HIT: {_fmt_dist(p['hit_trend_after'])}")
        L.append(f"- 버퍼 내 HIT 수: {p['hit_count_in_buffer']}")
        L.append(f"- 구간 시작 이전 추세 확정(전체): {_fmt_dist(p['any_trend_before'])}")
        L.append(f"- 구간 시작 이전 변곡 완성사건(전체): {_fmt_dist(p['any_trans_before'])}")
        L.append("")

        L.append("### 교차: ①② vs ④⑤ 진행 단계")
        L.append("")
        L.append(f"- ①② 추세 최고 stage: {diag['trend_family_stage']} "
                 f"(0=신호없음, 1=룰불일치, 2=불가판정, 3=HIT)")
        L.append(f"- ④⑤ 변곡 최고 stage: {diag['trans_family_stage']} "
                 f"(0=ATOM_ABSENT, 1=NOT_PAIRED, 2=STRUCT_BLOCKED, 3=HIT)")
        L.append(f"- **{diag['family_cmp']}**")
        L.append("")

        if zid == "Z2" and "heavy_atoms" in diag:
            L.append("### Z2 중량 원자 상세 (F6-5c-a / F6-5c-b)")
            L.append("")
            L.append("| 원자 | 공식 | 버퍼 내 | 전구간 | 상태 | 버퍼外 최근접 |")
            L.append("|---|---|---|---|---|---|")
            for ha in diag["heavy_atoms"]:
                if ha["in_buffer"]:
                    ts_str = ", ".join(f"{fmt_ts(t)}({k or '-'})" for _, t, k in ha["in_buffer"])
                    prox = "-"
                elif ha["nearest_dist"] is None:
                    ts_str = "없음"
                    prox = "-"
                else:
                    ts_str = "없음"
                    prox = f"{ha['nearest_dist']}봉 ({fmt_ts(ha['nearest_ts'][0])}, {ha['nearest_ts'][1] or '-'})"
                L.append(f"| {ha['name']} | {ha['rule']} | {len(ha['in_buffer'])} | "
                         f"{ha['global_count']} | {ha['status']} | {prox} |")
            L.append("")

        if zid == "Z3":
            L.append("### Z3 회귀 확인")
            L.append("")
            L.append(f"- ①② HIT 수(버퍼): {z3_regression['actual']} "
                     f"(직전 라운드: {z3_regression['expected']})")
            L.append(f"- 일치: {'**예**' if z3_regression['ok'] else '**아니오**'}")
            L.append("")

        matrix.append({
            "zid": zid,
            "trend_stage": diag["trend_family_stage"],
            "trans_stage": diag["trans_family_stage"],
            "trend_modes": _summarize_trend_modes(diag),
            "trans_modes": _summarize_trans_modes(diag),
            "family_cmp": diag["family_cmp"],
        })

    # Z1 before/after
    if z1_diag:
        prev = PREV_ROUND["Z1"]
        d3_now = z1_diag["struct_counts"].get("D3", 0)
        L.append("## Z1 before/after (워밍업 보강 전후)")
        L.append("")
        L.append("| 지표 | 직전(1,000봉) | 현재(페이지네이션) |")
        L.append("|---|---|---|")
        L.append(f"| fetch 봉수 | {PREV_ROUND['fetch_bars']} | {coverage['bars']} |")
        L.append(f"| 워밍업 | 불충분({PREV_ROUND['shortfall_bars']}봉 부족) | "
                 f"{'확보' if coverage['ok'] else '불충분'} |")
        L.append(f"| ①② stage | {prev['trend_stage']} | {z1_diag['trend_family_stage']} |")
        L.append(f"| ④⑤ stage | {prev['trans_stage']} | {z1_diag['trans_family_stage']} |")
        L.append(f"| ①② 주요모드 | {prev['trend_modes']} | {_summarize_trend_modes(z1_diag)} |")
        L.append(f"| ④⑤ 주요모드 | {prev['trans_modes']} | {_summarize_trans_modes(z1_diag)} |")
        L.append(f"| 더 멀리 진행 | {prev['family_cmp']} | {z1_diag['family_cmp']} |")
        L.append(f"| Z1 버퍼 D3 봉수 | {prev['d3_buffer_bars']} | {d3_now} |")
        L.append("")
        if prev["d3_buffer_bars"] > 0 and d3_now == 0:
            L.append("- Z1 버퍼 D3: 직전 8봉 → 현재 0봉. 워밍업 보강 후 D3 라벨은 Z1 버퍼에서 **소멸** "
                     "(직전 D3는 버퍼 하단 2026-02-01~02 구간에 집중 — 워밍업 오염·경계 혼입 가능성 있었음).")
        elif d3_now > 0:
            L.append(f"- Z1 버퍼 D3: 직전 {prev['d3_buffer_bars']}봉 → 현재 {d3_now}봉. "
                     "워밍업 보강 후에도 D3 라벨 **잔존** (NaN 구간 제외 후에도 출현).")
        else:
            L.append("- Z1 버퍼 D3: 직전·현재 모두 0봉.")
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 구간×공식가족 실패 모드 요약 매트릭스")
    L.append("")
    L.append("| 구간 | ①② 최고stage | ①② 주요모드 | ④⑤ 최고stage | ④⑤ 주요모드 | 더 멀리 진행 |")
    L.append("|---|---|---|---|---|---|")
    for m in matrix:
        L.append(f"| {m['zid']} | {m['trend_stage']} | {m['trend_modes']} | "
                 f"{m['trans_stage']} | {m['trans_modes']} | {m['family_cmp']} |")
    L.append("")
    L.append("### 차트 링크")
    L.append("")
    for zid, *_ in GROUND_TRUTH_ZONES:
        L.append(f"- [gt_{zid}.png](./gt_{zid}.png)")
    L.append("")

    append_semantics_r2_ladder(L, zone_results, r4c)
    append_report_4c(L, r4c)

    path = os.path.join(OUT_DIR, "REPORT_GT.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"REPORT_GT 작성: {path}")


def _summarize_trend_modes(diag):
    modes = Counter()
    for c in diag["trend_confirms"]:
        if "HIT:" in c["result"] and "allowed=True" in c["result"]:
            modes["HIT"] += 1
        elif "allowed=False" in c["result"]:
            modes["RULE_BLOCKED"] += 1
        elif c["result"].startswith("NO_MATCH"):
            modes["NO_RULE_MATCH"] += 1
    if not diag["trend_confirms"]:
        return "NO_SIGNAL"
    return ", ".join(f"{k}={v}" for k, v in modes.most_common()) or "NO_SIGNAL"


def _summarize_trans_modes(diag):
    modes = Counter(r["summary_mode"].split(":")[0] for r in diag["trans_rules"])
    return ", ".join(f"{k}={v}" for k, v in modes.most_common())


# module-level for report helper
_df_ref = None


def df_index_ts_by_pos(pos):
    global _df_ref
    if _df_ref is None:
        return None
    return _df_ref.index[pos]


def df_index_ts(zone_info, which):
    global _df_ref
    if _df_ref is None:
        return None
    pos = zone_info["buffer_lo"] if which == "lo" else zone_info["buffer_hi"]
    return _df_ref.index[pos]


def main():
    global _df_ref
    print(f"Loading {SYMBOL} {INTERVAL} (paginated)...")
    df, fetch_limit = load_df_gt(SYMBOL, INTERVAL)
    _df_ref = df
    zones = zone_ranges(df)
    coverage = history_coverage(df, zones, fetch_limit)

    z1_gate = z1_quality_gate(df, zones[0])

    zone_results = []
    z3_regression = {"expected": PREV_ROUND["Z3"]["trend_hit_count"], "actual": 0, "ok": False}
    for zone_info in zones:
        zid = zone_info["id"]
        print(f"Diagnosing {zid}...")
        diag = diagnose_zone(df, zone_info, zid=zid)
        if zid == "Z3":
            z3_regression["actual"] = z3_trend_hit_count(diag)
            z3_regression["ok"] = z3_regression["actual"] == z3_regression["expected"]
        png = draw_gt_chart(df, zone_info, diag["inventory"],
                            diag["trans_events"], diag["trend_confirms"], diag["segments"])
        zone_results.append((zone_info, diag))
        print(f"  -> {png}")

    r4c = analyze_4c(df, zones, zone_results)
    write_report(coverage, zone_results, z1_gate, z3_regression, r4c)
    print("Done.")


if __name__ == "__main__":
    main()
