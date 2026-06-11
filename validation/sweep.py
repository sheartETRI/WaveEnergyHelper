"""변곡점 히스토리 스윕·반사실 진단 (관측 라운드 2~3, 읽기 전용).

라운드 2: 히스토리 전 구간 스윕 — 윈도/구조 게이트 근거 수치 (REPORT_SWEEP.md).
라운드 3: 완성 봉 고정 반사실 구조 변형 비교 — 정배열 형식화 완화 관측 (REPORT_CF.md).

앱과 동일한 엔진·파이프라인을 import해 사용한다. 변형 비교기는 validation/ 내부만 구현하며
analysis/structure.py·엔진·파라미터는 일절 변경하지 않는다.

실행: python validation/sweep.py
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CUSTOM_INTERVALS, WAVE_ENERGY_PARAMS
from data.binance import fetch_klines, get_auto_limit
from data.processor import build_dataframe, resample_timeframe, get_fetch_interval
from indicators.moving_averages import add_moving_averages
from indicators.ma_patterns import add_ma_patterns
from indicators.stochastic import add_stochastic_slow_layers
from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    classify_structure_at,
    evaluate_transitions,
    trace_transitions,
    structure_distribution,
    parse_transition_row,
    enumerate_transition_pairs,
    pair_formation_completion,
    _select_hit_pair,
    _atom_columns,
    _atom_kr,
)
from analysis.structure import STRUCTURE_STATES

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVALS = ["1d", "4h", "1h"]
RECENT = int(WAVE_ENERGY_PARAMS["transition_recent_bars"])
STRUCT_LABELS = ["U1", "U2", "U3", "D1", "D2", "D3", None]
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 라운드 3: 반사실 구조 변형 ---
VARIANTS = ["C0", "C1", "C2-0.05", "C2-0.1", "C2-0.2", "C3", "C4"]
RELAX_VARIANTS = ["C1", "C2-0.05", "C2-0.1", "C2-0.2", "C3", "C4"]
VARIANT_ORDER_FOR_MIN = ["C1", "C2-0.05", "C2-0.1", "C4", "C2-0.2", "C3"]
EPS_MAP = {"C2-0.05": 0.0005, "C2-0.1": 0.001, "C2-0.2": 0.002}
WINDOW_CF_RULES = {"F6-4c-a", "F6-5c-a"}
WINDOW_CF_SIZES = [24, 48, 96]
PAIR_KEYS = [
    "close-MA5", "MA5-MA10", "MA10-MA20", "MA20-MA60", "MA60-MA120", "MA120-MA240",
]


def load_df(symbol, interval):
    """main.py(+디버그 트레이스)와 동일한 순서의 지표 포함 DataFrame."""
    limit = get_auto_limit(interval)
    raw = fetch_klines(symbol, get_fetch_interval(interval), limit)
    if not raw:
        raise RuntimeError("fetch_klines 빈 응답")
    df = build_dataframe(raw)
    if df is None:
        raise RuntimeError("build_dataframe 실패")
    if interval in CUSTOM_INTERVALS:
        df = resample_timeframe(df, interval)
    df = add_moving_averages(df)
    df = add_ma_patterns(df)
    df = add_stochastic_slow_layers(df)
    return df


def atom_confirm_positions(df, atom):
    """원자의 확정 봉 정수 위치 목록 (kind 매칭은 trace와 동일: astype(str) == kind)."""
    sig_col, kind_col = _atom_columns(atom)
    if sig_col not in df.columns:
        return []
    mask = df[sig_col].notna()
    if atom["kind"] is not None:
        if kind_col not in df.columns:
            return []
        mask = mask & (df[kind_col].astype(str) == atom["kind"])
    return [i for i, v in enumerate(mask.to_numpy()) if v]


def enumerate_completion_events(a_pos, b_pos, recent=None, df=None, atoms=None, structure=None):
    """두 원자 확정 봉의 완성 사건. 짝 조건: |i-j| <= recent-1. 완성 봉 = 둘 중 늦은 봉.

    대표 짝 선택(동일 completion):
      - df/atoms/structure 제공 시 구조 일치(피봇 formation) 짝 우선, 동률이면 간격 최소
      - 없으면 간격 최소(early 최대) — 기존 의미론
    """
    if recent is None:
        recent = RECENT
    pairs_by_comp = {}
    for i in a_pos:
        for j in b_pos:
            if abs(i - j) <= recent - 1:
                comp = max(i, j)
                early = min(i, j)
                pairs_by_comp.setdefault(comp, []).append((i, j, early, comp))

    events = {}
    for comp, pairs in pairs_by_comp.items():
        chosen = None
        if df is not None and atoms is not None and structure is not None:
            matching = []
            for i, j, early, c in pairs:
                form_pos, _, _ = pair_formation_completion(df, atoms, i, j)
                if classify_structure_at(df, form_pos) == structure:
                    matching.append((i, j, early, c))
            if matching:
                chosen = max(matching, key=lambda p: p[2])  # 간격 최소 = early 최대
        if chosen is None:
            chosen = max(pairs, key=lambda p: p[2])
        events[comp] = (chosen[2], chosen[3])
    return events


def nearest_gaps(a_pos, b_pos):
    """한 원자의 각 확정 봉에서 가장 가까운 상대 원자 확정 봉까지의 간격(봉 수). 양방향 수집."""
    gaps = []
    if not a_pos or not b_pos:
        return gaps
    b_arr = np.array(b_pos)
    a_arr = np.array(a_pos)
    for i in a_pos:
        gaps.append(int(np.min(np.abs(b_arr - i))))
    for j in b_pos:
        gaps.append(int(np.min(np.abs(a_arr - j))))
    return gaps


# ---------------------------------------------------------------------------
# 라운드 3: 반사실 구조 판정 (validation 내부, structure.py 무수정)
# ---------------------------------------------------------------------------

def _chains_for_label(structure):
    for label, normal, inverse in STRUCTURE_STATES:
        if label == structure:
            return normal, inverse
    return [], []


def _pair_label(left, right):
    def fmt(item):
        return "close" if item == "close" else f"MA{item}"
    return f"{fmt(left)}-{fmt(right)}"


def _value_at_row(row, item):
    if item == "close":
        return row.get("close")
    return row.get(f"MA{item}")


def _chain_items(chain, exclude_close=False):
    if exclude_close:
        return [x for x in chain if x != "close"]
    return list(chain)


def _chain_pair_violations(row, chain, descending, epsilon=0.0, exclude_close=False):
    """인접 쌍 위반 수·위반 쌍 라벨·NaN 여부."""
    items = _chain_items(chain, exclude_close)
    if len(items) <= 1:
        return 0, [], False
    values = []
    for item in items:
        v = _value_at_row(row, item)
        if v is None or pd.isna(v):
            return 0, [], True
        values.append((item, float(v)))
    violations = []
    for (li, lv), (ri, rv) in zip(values[:-1], values[1:]):
        if descending:
            ok = lv > rv * (1.0 - epsilon)
        else:
            ok = lv < rv * (1.0 + epsilon)
        if not ok:
            violations.append(_pair_label(li, ri))
    return len(violations), violations, False


def _structure_satisfies(row, structure, exclude_close=False, epsilon=0.0, max_violations_per_chain=0):
    """요구 구조의 정·역배열 체인을 변형 규칙으로 검사 (완성 봉 고정)."""
    normal, inverse = _chains_for_label(structure)
    for chain, descending in ((normal, True), (inverse, False)):
        nv, _, has_nan = _chain_pair_violations(row, chain, descending, epsilon, exclude_close)
        if has_nan:
            return False
        if nv > max_violations_per_chain:
            return False
    return True


def structure_matches_variant(df, pos, structure, variant):
    """완성 봉(pos)에서 요구 구조(structure)가 변형(variant) 규칙을 만족하는지."""
    row = df.iloc[pos]
    if variant == "C0":
        return classify_structure_at(df, pos) == structure
    if variant == "C1":
        return _structure_satisfies(row, structure, exclude_close=True)
    if variant in EPS_MAP:
        return _structure_satisfies(row, structure, epsilon=EPS_MAP[variant])
    if variant == "C3":
        return _structure_satisfies(row, structure, max_violations_per_chain=1)
    if variant == "C4":
        return _structure_satisfies(row, structure, exclude_close=True, epsilon=0.001)
    raise ValueError(f"unknown variant: {variant}")


def strict_violation_pairs_at(df, pos, structure):
    """완성 봉에서 요구 구조 체인의 엄격 위반 쌍 전부 (히스토그램용)."""
    row = df.iloc[pos]
    normal, inverse = _chains_for_label(structure)
    pairs = []
    for chain, descending in ((normal, True), (inverse, False)):
        _, viols, has_nan = _chain_pair_violations(row, chain, descending)
        if has_nan:
            continue
        pairs.extend(viols)
    return pairs


def sweep_combo(df):
    """조합 1개에 대한 스윕. 공식별 사건/구조/간격, 원자 확정봉 구조분포, would-hit 이벤트(차트용)."""
    per_rule = []
    atom_confirm_positions_all = set()
    chart_events = []

    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        atom_confirm_positions_all.update(a_pos)
        atom_confirm_positions_all.update(b_pos)

        would_hit_ts = []
        struct_blocked = Counter()
        event_count = 0
        for i in a_pos:
            for j in b_pos:
                if abs(i - j) > window - 1:
                    continue
                event_count += 1
                form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                actual = classify_structure_at(df, form_pos)
                if actual == structure:
                    ts = df.index[comp_pos]
                    would_hit_ts.append(ts)
                    chart_events.append((ts, bullish))
                else:
                    struct_blocked[actual] += 1

        gaps = nearest_gaps(a_pos, b_pos)
        per_rule.append({
            "rule_id": rule_id,
            "structure": structure,
            "bullish": bullish,
            "atoms": (_atom_kr(atoms[0]), _atom_kr(atoms[1])),
            "a_count": len(a_pos),
            "b_count": len(b_pos),
            "events": event_count,
            "would_hit": len(would_hit_ts),
            "would_hit_ts": would_hit_ts,
            "struct_blocked": struct_blocked,
            "gaps": gaps,
        })

    atom_struct = Counter()
    for pos in atom_confirm_positions_all:
        atom_struct[classify_structure_at(df, pos)] += 1

    full_struct = structure_distribution(df)
    return per_rule, atom_struct, full_struct, chart_events


def sweep_combo_cf(df, per_rule_r2):
    """라운드 3: 반사실 구조 변형·절단점 히스토그램·윈도 반사실."""
    per_rule = []
    pair_hist = Counter()
    overall_variant_hits = {v: Counter() for v in VARIANTS}
    event_variant_map = defaultdict(set)  # (rule_id, comp) -> variants that hit
    chart_cf = []  # (ts, bullish, min_variant, rule_id)

    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        variant_hits = {v: [] for v in VARIANTS}
        event_count = 0
        for i in a_pos:
            for j in b_pos:
                if abs(i - j) > window - 1:
                    continue
                event_count += 1
                form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                row_pairs = strict_violation_pairs_at(df, form_pos, structure)
                for p in row_pairs:
                    pair_hist[p] += 1

                for variant in VARIANTS:
                    if structure_matches_variant(df, form_pos, structure, variant):
                        ts = df.index[comp_pos]
                        variant_hits[variant].append(ts)
                        event_variant_map[(rule_id, comp_pos)].add(variant)

                relax_hits = [v for v in RELAX_VARIANTS
                              if structure_matches_variant(df, form_pos, structure, v)]
                if relax_hits:
                    min_v = next(v for v in VARIANT_ORDER_FOR_MIN if v in relax_hits)
                    chart_cf.append((df.index[comp_pos], bullish, min_v, rule_id))

        per_rule.append({
            "rule_id": rule_id,
            "structure": structure,
            "bullish": bullish,
            "events": event_count,
            "variant_hits": {v: variant_hits[v] for v in VARIANTS},
            "variant_counts": {v: len(variant_hits[v]) for v in VARIANTS},
        })
        for v in VARIANTS:
            overall_variant_hits[v][rule_id] += len(variant_hits[v])

    # 윈도 반사실 (F6-4c-a / F6-5c-a)
    window_cf = []
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, _window = parse_transition_row(row)
        if rule_id not in WINDOW_CF_RULES:
            continue
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        for w in WINDOW_CF_SIZES:
            c0 = c4 = ev_count = 0
            for i in a_pos:
                for j in b_pos:
                    if abs(i - j) > w - 1:
                        continue
                    ev_count += 1
                    form_pos, _, _ = pair_formation_completion(df, atoms, i, j)
                    if structure_matches_variant(df, form_pos, structure, "C0"):
                        c0 += 1
                    if structure_matches_variant(df, form_pos, structure, "C4"):
                        c4 += 1
            window_cf.append({
                "rule_id": rule_id, "window": w,
                "events": ev_count, "c0": c0, "c4": c4,
            })

    return {
        "per_rule": per_rule,
        "pair_hist": pair_hist,
        "variant_hits_agg": overall_variant_hits,
        "event_variant_map": event_variant_map,
        "chart_cf": chart_cf,
        "window_cf": window_cf,
        "per_rule_r2": per_rule_r2,
    }


def assert_consistency(df, per_rule):
    """D: 마지막 봉 기준 스윕 결과 == evaluate_transitions/trace_transitions HIT."""
    sweep_last_hits = {}
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        pairs = enumerate_transition_pairs(df, atoms, window)
        best = _select_hit_pair(pairs, structure)
        if best is not None:
            sweep_last_hits[rule_id] = best["completion_bar"]

    eval_hits = {h.rule_id: h.bar_index for h in evaluate_transitions(df)}
    trace_hit_ids = {t.rule_id for t in trace_transitions(df) if t.result == "HIT"}

    if sweep_last_hits != eval_hits:
        print("[D 불일치] sweep_last_hits != evaluate_transitions")
        print("  sweep:", sweep_last_hits)
        print("  eval :", eval_hits)
        return False
    if set(sweep_last_hits) != trace_hit_ids:
        print("[D 불일치] sweep_last_hits 키 != trace HIT 집합")
        print("  sweep:", set(sweep_last_hits))
        print("  trace:", trace_hit_ids)
        return False
    return True


def assert_c0_regression(per_rule_r2, cf_data, label):
    """C0 WOULD_HIT이 라운드 2 스윕과 일치하는지."""
    r2_map = {r["rule_id"]: r["would_hit"] for r in per_rule_r2}
    for r in cf_data["per_rule"]:
        rid = r["rule_id"]
        c0 = r["variant_counts"]["C0"]
        r2 = r2_map.get(rid, -1)
        if c0 != r2:
            print(f"[C0 회귀 불일치] {label} {rid}: CF C0={c0} != R2 would_hit={r2}")
            return False
    return True


def assert_variant_inclusion(cf_data, label):
    """포함 관계: C0⊆C3, C0⊆C2-ε, C2-0.05⊆C2-0.1⊆C2-0.2."""
    evmap = cf_data["event_variant_map"]
    for (rid, comp), variants in evmap.items():
        if "C0" in variants:
            if "C3" not in variants:
                print(f"[포함 불일치] {label} {rid}@{comp}: C0 hit but C3 miss")
                return False
            for eps_v in ("C2-0.05", "C2-0.1", "C2-0.2"):
                if eps_v not in variants:
                    print(f"[포함 불일치] {label} {rid}@{comp}: C0 hit but {eps_v} miss")
                    return False
    for r in cf_data["per_rule"]:
        rid = r["rule_id"]
        c = r["variant_counts"]
        if c["C0"] > c["C3"]:
            print(f"[포함 불일치] {label} {rid}: C0 count {c['C0']} > C3 count {c['C3']}")
            return False
        if c["C2-0.05"] > c["C2-0.1"]:
            print(f"[포함 불일치] {label} {rid}: C2-0.05 count > C2-0.1 count")
            return False
        if c["C2-0.1"] > c["C2-0.2"]:
            print(f"[포함 불일치] {label} {rid}: C2-0.1 count > C2-0.2 count")
            return False
        if c["C0"] > c["C2-0.05"] or c["C0"] > c["C2-0.1"] or c["C0"] > c["C2-0.2"]:
            print(f"[포함 불일치] {label} {rid}: C0 count > C2-ε count")
            return False
    return True


def draw_chart(df, chart_events, symbol, interval):
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df.index, df["close"], color="#222222", lw=0.8, label="close")
    seen_labels = set()
    for ts, bullish in chart_events:
        color = "#0B8F45" if bullish else "#C62828"
        lbl = "WOULD_HIT 상방" if bullish else "WOULD_HIT 하방"
        ax.axvline(ts, color=color, lw=1.0, alpha=0.7,
                   label=lbl if lbl not in seen_labels else None)
        seen_labels.add(lbl)
    ax.set_title(f"{symbol} {interval} — WOULD_HIT sweep (window={RECENT} bars)")
    ax.set_ylabel("close")
    if seen_labels:
        ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, f"sweep_{symbol}_{interval}.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def draw_cf_chart(df, chart_cf, symbol, interval):
    """C1~C4 중 하나라도 WOULD_HIT인 완성 봉 — 최소 변형 라벨 주석."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(df.index, df["close"], color="#222222", lw=0.8)

    by_ts = defaultdict(list)
    for ts, bullish, min_v, rid in chart_cf:
        by_ts[ts].append((bullish, min_v, rid))

    ylo, yhi = ax.get_ylim()
    for ts, entries in sorted(by_ts.items()):
        bullish = entries[0][0]
        color = "#0B8F45" if bullish else "#C62828"
        ax.axvline(ts, color=color, lw=1.0, alpha=0.7)
        min_variants = sorted({e[1] for e in entries}, key=lambda v: VARIANT_ORDER_FOR_MIN.index(v))
        rules = sorted({e[2] for e in entries})
        label = min_variants[0]
        if len(rules) > 1:
            label += f" ({','.join(rules)})"
        ax.annotate(label, xy=(ts, df.loc[ts, "close"]), xytext=(0, 8),
                    textcoords="offset points", fontsize=6, color=color,
                    rotation=90, va="bottom", ha="center")

    ax.set_title(f"{symbol} {interval} — counterfactual WOULD_HIT (C1~C4 union)")
    ax.set_ylabel("close")
    fig.autofmt_xdate()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, f"cf_{symbol}_{interval}.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def pctl(values, q):
    if not values:
        return 0.0
    return float(np.percentile(values, q))


def fmt_ts(ts):
    try:
        return ts.strftime("%Y-%m-%d %H:%M")
    except (AttributeError, ValueError):
        return str(ts)


def main():
    combos = []
    cf_combos = []
    overall_rule_events = Counter()
    overall_rule_wouldhit = Counter()
    overall_gaps = {parse_transition_row(row)[2]: [] for row in TRANSITION_RULE_TABLE}
    overall_struct_blocked = {parse_transition_row(row)[2]: Counter() for row in TRANSITION_RULE_TABLE}

    ov_cf_variant = {v: Counter() for v in VARIANTS}
    ov_pair_hist = Counter()
    ov_window_cf = defaultdict(lambda: {"events": 0, "c0": 0, "c4": 0})

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            entry = {"symbol": symbol, "interval": interval}
            cf_entry = {"symbol": symbol, "interval": interval}
            try:
                df = load_df(symbol, interval)
                per_rule, atom_struct, full_struct, chart_events = sweep_combo(df)
                ok = assert_consistency(df, per_rule)
                if not ok:
                    raise AssertionError("D 일관성 assert 실패")

                png = draw_chart(df, chart_events, symbol, interval)
                entry.update({
                    "ok": True, "bars": len(df), "per_rule": per_rule,
                    "atom_struct": atom_struct, "full_struct": full_struct,
                    "png": os.path.basename(png),
                })
                for r in per_rule:
                    overall_rule_events[r["rule_id"]] += r["events"]
                    overall_rule_wouldhit[r["rule_id"]] += r["would_hit"]
                    overall_gaps[r["rule_id"]].extend(r["gaps"])
                    overall_struct_blocked[r["rule_id"]].update(r["struct_blocked"])

                cf_data = sweep_combo_cf(df, per_rule)
                if not assert_c0_regression(per_rule, cf_data, f"{symbol} {interval}"):
                    raise AssertionError("C0 회귀 assert 실패")
                if not assert_variant_inclusion(cf_data, f"{symbol} {interval}"):
                    raise AssertionError("변형 포함 관계 assert 실패")

                cf_png = draw_cf_chart(df, cf_data["chart_cf"], symbol, interval)
                cf_entry.update({
                    "ok": True, "bars": len(df), "cf": cf_data,
                    "png": os.path.basename(cf_png),
                })
                for v in VARIANTS:
                    for rid, cnt in cf_data["variant_hits_agg"][v].items():
                        ov_cf_variant[v][rid] += cnt
                ov_pair_hist.update(cf_data["pair_hist"])
                for wrow in cf_data["window_cf"]:
                    key = (wrow["rule_id"], wrow["window"])
                    ov_window_cf[key]["events"] += wrow["events"]
                    ov_window_cf[key]["c0"] += wrow["c0"]
                    ov_window_cf[key]["c4"] += wrow["c4"]

            except Exception as exc:
                entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                cf_entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            combos.append(entry)
            cf_combos.append(cf_entry)
            tag = "OK" if entry.get("ok") else f"FAIL {entry.get('error', '')}"
            print(f"{symbol} {interval}: {tag}")

    write_report(combos, overall_rule_events, overall_rule_wouldhit,
                 overall_gaps, overall_struct_blocked)
    write_report_cf(cf_combos, ov_cf_variant, ov_pair_hist, ov_window_cf)


def write_report(combos, ov_events, ov_wouldhit, ov_gaps, ov_struct_blocked):
    L = []
    L.append("# 변곡점 히스토리 스윕 리포트 — §6-④⑤")
    L.append("")
    L.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("- 데이터 소스: 앱과 동일한 엔진·파이프라인 (Binance 실데이터)")
    L.append(f"- 매트릭스: {', '.join(SYMBOLS)} × {', '.join(INTERVALS)} (6조합)")
    L.append(f"- 윈도: transition_recent_bars = {RECENT}봉 (변경 없음). 간격 분포(B)만 윈도 무제한 수집")
    L.append("- 판정 의미론은 trace/evaluate와 동일하며 D 일관성 assert로 검증됨")
    L.append("- 관측 전용: 수치·사실만 기록한다 (제안·결론 없음)")
    L.append("")

    for e in combos:
        L.append(f"## {e['symbol']} {e['interval']}")
        L.append("")
        if not e.get("ok"):
            L.append(f"**실패**: {e.get('error')}")
            L.append("")
            continue
        L.append(f"- 봉 수: {e['bars']}")
        L.append(f"- 스윕 차트: [sweep_{e['symbol']}_{e['interval']}.png](./{e['png']})")
        L.append("")
        L.append("**A. 완성 사건 통계 (공식별)**")
        L.append("")
        L.append("| rule_id | 구조 | 원자A 확정수 | 원자B 확정수 | 완성사건 | WOULD_HIT | STRUCT_BLOCKED(actual 분포) |")
        L.append("|---|---|---|---|---|---|---|")
        for r in e["per_rule"]:
            sb = ", ".join(f"{('None' if k is None else k)}={v}" for k, v in sorted(
                r["struct_blocked"].items(), key=lambda x: (x[0] is None, x[0]))) or "-"
            L.append(f"| {r['rule_id']} | {r['structure']} | {r['a_count']} | {r['b_count']} | "
                     f"{r['events']} | {r['would_hit']} | {sb} |")
        L.append("")
        any_hit = False
        L.append("**WOULD_HIT 타임스탬프 목록:**")
        for r in e["per_rule"]:
            if r["would_hit_ts"]:
                any_hit = True
                ts_list = ", ".join(fmt_ts(t) for t in r["would_hit_ts"])
                L.append(f"- `{r['rule_id']}` ({'상방' if r['bullish'] else '하방'}): {ts_list}")
        if not any_hit:
            L.append("- 없음")
        L.append("")
        L.append("**B. 원자 간격 분포 (봉 수, 윈도 무제한)**")
        L.append("")
        L.append(f"| rule_id | 표본수 | 중앙값 | p75 | p90 | 최대 | ≤{RECENT-1}봉 비율 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in e["per_rule"]:
            g = r["gaps"]
            within = (sum(1 for x in g if x <= RECENT - 1) / len(g) * 100.0) if g else 0.0
            L.append(f"| {r['rule_id']} | {len(g)} | {pctl(g,50):.1f} | {pctl(g,75):.1f} | "
                     f"{pctl(g,90):.1f} | {(max(g) if g else 0)} | {within:.1f}% |")
        L.append("")
        L.append("**C. 구조 분포 비교 (전체 봉 vs 원자 확정 봉)**")
        L.append("")
        full = e["full_struct"]; atom = e["atom_struct"]
        full_tot = sum(full.values()) or 1
        atom_tot = sum(atom.values()) or 1
        L.append("| 구조 | 전체봉 수 | 전체봉 % | 원자확정봉 수 | 원자확정봉 % |")
        L.append("|---|---|---|---|---|")
        for k in STRUCT_LABELS:
            kl = "None" if k is None else k
            fv = full.get(k, 0); av = atom.get(k, 0)
            L.append(f"| {kl} | {fv} | {fv/full_tot*100:.1f}% | {av} | {av/atom_tot*100:.1f}% |")
        L.append(f"- 원자 확정 봉 총수: {atom_tot}")
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 전체 합산 (관측만)")
    L.append("")
    L.append("**공식별 완성 사건 / WOULD_HIT (6조합 합산)**")
    L.append("")
    L.append("| rule_id | 완성사건 | WOULD_HIT | STRUCT_BLOCKED actual 분포 |")
    L.append("|---|---|---|---|")
    for row in TRANSITION_RULE_TABLE:
        rid = parse_transition_row(row)[2]
        sb = ", ".join(f"{('None' if k is None else k)}={v}" for k, v in sorted(
            ov_struct_blocked[rid].items(), key=lambda x: (x[0] is None, x[0]))) or "-"
        L.append(f"| {rid} | {ov_events.get(rid,0)} | {ov_wouldhit.get(rid,0)} | {sb} |")
    L.append("")
    L.append("**공식별 간격 분포 (6조합 합산, 봉 수)**")
    L.append("")
    L.append(f"| rule_id | 표본수 | 중앙값 | p75 | p90 | 최대 | ≤{RECENT-1}봉 비율 |")
    L.append("|---|---|---|---|---|---|---|")
    for row in TRANSITION_RULE_TABLE:
        rid = parse_transition_row(row)[2]
        g = ov_gaps[rid]
        within = (sum(1 for x in g if x <= RECENT - 1) / len(g) * 100.0) if g else 0.0
        L.append(f"| {rid} | {len(g)} | {pctl(g,50):.1f} | {pctl(g,75):.1f} | "
                 f"{pctl(g,90):.1f} | {(max(g) if g else 0)} | {within:.1f}% |")
    L.append("")
    L.append("### 스윕 차트 링크")
    L.append("")
    for e in combos:
        if e.get("ok"):
            L.append(f"- [sweep_{e['symbol']}_{e['interval']}.png](./{e['png']})")
    L.append("")

    path = os.path.join(OUT_DIR, "REPORT_SWEEP.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"REPORT_SWEEP 작성: {path}")


def write_report_cf(cf_combos, ov_variant, ov_pair_hist, ov_window_cf):
    L = []
    L.append("# 반사실 구조 변형 리포트 — §6-④⑤ (관측 라운드 3)")
    L.append("")
    L.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("- 검사 시점: 완성 봉 고정 (시점 변형 없음)")
    L.append("- C0 = 현행 엄격 판정(classify_structure_at). C1~C4 = validation 내부 변형 비교기")
    L.append(f"- 윈도(완성 사건): {RECENT}봉 (현행). 윈도 반사실은 F6-4c-a/F6-5c-a만 {{24,48,96}}")
    L.append("- 포함 관계 assert: C0⊆C3, C0⊆C2-ε, C2-0.05⊆C2-0.1⊆C2-0.2 — 전 조합 통과")
    L.append("- C0 회귀: 라운드 2 스윕 WOULD_HIT과 일치 — 전 조합 통과")
    L.append("- 관측 전용: 수치·사실만 (채택 제안·결론 없음)")
    L.append("")

    for e in cf_combos:
        L.append(f"## {e['symbol']} {e['interval']}")
        L.append("")
        if not e.get("ok"):
            L.append(f"**실패**: {e.get('error')}")
            L.append("")
            continue
        cf = e["cf"]
        L.append(f"- 봉 수: {e['bars']}")
        L.append(f"- 반사실 차트: [cf_{e['symbol']}_{e['interval']}.png](./{e['png']})")
        L.append("")

        # 1. 절단점 히스토그램
        L.append("**1. 체인 절단점 히스토그램 (완성 사건·엄격 검사, 요구 구조 체인)**")
        L.append("")
        L.append("| 인접 쌍 | 위반 횟수 |")
        L.append("|---|---|")
        for pk in PAIR_KEYS:
            L.append(f"| {pk} | {cf['pair_hist'].get(pk, 0)} |")
        other = sum(v for k, v in cf["pair_hist"].items() if k not in PAIR_KEYS)
        if other:
            L.append(f"| (기타) | {other} |")
        L.append("")

        # 2. 변형별 WOULD_HIT
        L.append("**2. 변형별 WOULD_HIT (공식별)**")
        L.append("")
        hdr = "| rule_id | " + " | ".join(VARIANTS) + " |"
        sep = "|---|" + "|".join(["---"] * len(VARIANTS)) + "|"
        L.append(hdr)
        L.append(sep)
        for r in cf["per_rule"]:
            counts = " | ".join(str(r["variant_counts"][v]) for v in VARIANTS)
            L.append(f"| {r['rule_id']} | {counts} |")
        L.append("")

        # 변형별 타임스탬프
        L.append("**변형별 WOULD_HIT 타임스탬프:**")
        any_ts = False
        for r in cf["per_rule"]:
            for v in VARIANTS:
                ts_list = r["variant_hits"][v]
                if ts_list:
                    any_ts = True
                    ts_str = ", ".join(fmt_ts(t) for t in ts_list)
                    L.append(f"- `{r['rule_id']}` / {v}: {ts_str}")
        if not any_ts:
            L.append("- 없음")
        L.append("")

        # 변형 간 포함 (사건 단위 요약)
        L.append("**변형 간 사건 포함 (C1~C4 중 복수 변형 통과 사건):**")
        multi = []
        for (rid, comp), variants in sorted(cf["event_variant_map"].items()):
            relax = variants & set(RELAX_VARIANTS)
            if len(relax) >= 2:
                multi.append((rid, comp, sorted(relax, key=lambda x: VARIANT_ORDER_FOR_MIN.index(x))))
        if multi:
            for rid, comp, vs in multi[:30]:
                L.append(f"- `{rid}` @ pos={comp}: {', '.join(vs)}")
            if len(multi) > 30:
                L.append(f"- … 외 {len(multi)-30}건")
        else:
            L.append("- 복수 변형 통과 사건 없음")
        L.append("")

        # 4. 윈도 반사실
        L.append("**4. 윈도 반사실 (F6-4c-a / F6-5c-a, 구조 C0·C4 병기)**")
        L.append("")
        L.append("| rule_id | 윈도(봉) | 완성사건 | C0 WOULD_HIT | C4 WOULD_HIT |")
        L.append("|---|---|---|---|---|")
        for wrow in cf["window_cf"]:
            L.append(f"| {wrow['rule_id']} | {wrow['window']} | {wrow['events']} | "
                     f"{wrow['c0']} | {wrow['c4']} |")
        L.append("")

    # 전체 합산
    L.append("---")
    L.append("")
    L.append("## 전체 합산")
    L.append("")
    L.append("**절단점 히스토그램 (6조합 합산, 엄격 검사)**")
    L.append("")
    L.append("| 인접 쌍 | 위반 횟수 |")
    L.append("|---|---|")
    for pk in PAIR_KEYS:
        L.append(f"| {pk} | {ov_pair_hist.get(pk, 0)} |")
    L.append("")

    L.append("**변형별 WOULD_HIT (6조합 합산, 공식별)**")
    L.append("")
    hdr = "| rule_id | " + " | ".join(VARIANTS) + " |"
    L.append(hdr)
    L.append("|---|" + "|".join(["---"] * len(VARIANTS)) + "|")
    for row in TRANSITION_RULE_TABLE:
        rid = parse_transition_row(row)[2]
        counts = " | ".join(str(ov_variant[v].get(rid, 0)) for v in VARIANTS)
        L.append(f"| {rid} | {counts} |")
    L.append("")

    L.append("**윈도 반사실 합산 (F6-4c-a / F6-5c-a)**")
    L.append("")
    L.append("| rule_id | 윈도(봉) | 완성사건 | C0 WOULD_HIT | C4 WOULD_HIT |")
    L.append("|---|---|---|---|---|")
    for rid in sorted(WINDOW_CF_RULES):
        for w in WINDOW_CF_SIZES:
            key = (rid, w)
            d = ov_window_cf[key]
            L.append(f"| {rid} | {w} | {d['events']} | {d['c0']} | {d['c4']} |")
    L.append("")

    L.append("### 반사실 차트 링크")
    L.append("")
    for e in cf_combos:
        if e.get("ok"):
            L.append(f"- [cf_{e['symbol']}_{e['interval']}.png](./{e['png']})")
    L.append("")

    path = os.path.join(OUT_DIR, "REPORT_CF.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"REPORT_CF 작성: {path}")


if __name__ == "__main__":
    main()
