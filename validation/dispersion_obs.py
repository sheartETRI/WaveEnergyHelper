"""이평 이격도(dispersion) ↔ 변곡 상관 관측 (ETHUSDT 4h, 읽기 전용).

표시·관측 전용. ④⑤/①② 게이트 연결 없음.
실행: python validation/dispersion_obs.py
"""
import os
import sys
import datetime
from collections import Counter

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CUSTOM_INTERVALS
from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    parse_transition_row,
    classify_structure_at,
    pair_formation_completion,
)
from indicators.ma_dispersion import add_ma_dispersion, dispersion_percentile_rank
from validation.gt_trace import (
    GROUND_TRUTH_ZONES,
    ZONE_BUFFER_BARS,
    load_df_gt,
    zone_ranges,
    evaluate_transition_in_zone,
    SYMBOL,
    INTERVAL,
    fmt_ts,
)
from validation.sweep import atom_confirm_positions

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RANDOM_SEED = 42
PIVOT_NEAR_BARS = 10
PCT_LABELS = ["P10", "P25", "P50", "P75", "P90"]


def _valid_dispersion(df):
    return df["ma_dispersion"].dropna()


def global_percentile_bounds(df):
    s = _valid_dispersion(df)
    return {k: float(np.percentile(s, p)) for k, p in zip(PCT_LABELS, [10, 25, 50, 75, 90])}


def zone_dispersion_stats(df, zone_info):
    buf = sorted(zone_info["buffer_pos"])
    pcts = []
    rows = []
    for pos in buf:
        v = df.iloc[pos].get("ma_dispersion")
        if v is None or pd.isna(v):
            continue
        pr = dispersion_percentile_rank(df, pos)
        pcts.append(pr)
        rows.append({"pos": pos, "ts": df.index[pos], "disp": float(v), "pct": pr})
    if not rows:
        return {"count": 0, "pct_dist": Counter(), "min_pct": None, "min_row": None}
    min_row = min(rows, key=lambda r: r["pct"])
    return {
        "count": len(rows),
        "pct_dist": Counter(int(r["pct"] // 10) * 10 for r in rows),
        "min_pct": min_row["pct"],
        "min_row": min_row,
        "pcts": pcts,
    }


def collect_engine_hits(df, zones):
    """정답 구간 버퍼 내 엔진 HIT — 형성 봉(피봇) 기준."""
    hits = []
    for zone_info in zones:
        _, events, _ = evaluate_transition_in_zone(df, zone_info["buffer_pos"])
        for e in events:
            if e["mode"] != "HIT":
                continue
            hits.append({
                "zone": zone_info["id"],
                "rule_id": e["rule_id"],
                "form_pos": e["form_pos"],
                "form_ts": e["form_ts"],
                "comp_ts": e["comp_ts"],
            })
    return hits


def collect_sweep_would_hits(df):
    """전 구간 WOULD_HIT (피봇 formation 구조 일치)."""
    events = []
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        a_pos = atom_confirm_positions(df, atoms[0])
        b_pos = atom_confirm_positions(df, atoms[1])
        for i in a_pos:
            for j in b_pos:
                if abs(i - j) > window - 1:
                    continue
                form_pos, comp_pos, _ = pair_formation_completion(df, atoms, i, j)
                if classify_structure_at(df, form_pos) != structure:
                    continue
                events.append({
                    "rule_id": rule_id,
                    "form_pos": form_pos,
                    "form_ts": df.index[form_pos],
                    "comp_ts": df.index[comp_pos],
                    "bullish": bullish,
                })
    return events


def hit_dispersion_metrics(df, formations):
    """형성 봉 dispersion 백분위·pivot_low 근접·양쪽 꼬리 비율."""
    pcts = []
    near_pivot = 0
    p25_or_below = 0
    p75_or_above = 0
    tail = 0
    pivot_low_pos = set(
        i for i, v in enumerate(df["ma_dispersion_pivot_low"].notna().values) if v
    )
    for item in formations:
        pos = item["form_pos"]
        pr = dispersion_percentile_rank(df, pos)
        if pr is None:
            continue
        pcts.append(pr)
        if pr <= 25:
            p25_or_below += 1
        if pr >= 75:
            p75_or_above += 1
        if pr <= 25 or pr >= 75:
            tail += 1
        if any(abs(pos - p) <= PIVOT_NEAR_BARS for p in pivot_low_pos):
            near_pivot += 1
    n = len(pcts)
    return {
        "n": n,
        "pcts": pcts,
        "p25_or_below": p25_or_below,
        "p25_or_below_pct": (p25_or_below / n * 100) if n else 0.0,
        "p75_or_above": p75_or_above,
        "p75_or_above_pct": (p75_or_above / n * 100) if n else 0.0,
        "tail": tail,
        "tail_pct": (tail / n * 100) if n else 0.0,
        "near_pivot": near_pivot,
        "near_pivot_pct": (near_pivot / n * 100) if n else 0.0,
    }


def random_baseline(df, n, exclude_pos=None):
    """무작위 봉 표본(동수) 동일 지표."""
    exclude = exclude_pos or set()
    candidates = [
        p for p in range(len(df))
        if p not in exclude and not pd.isna(df.iloc[p].get("ma_dispersion"))
    ]
    rng = np.random.default_rng(RANDOM_SEED)
    if len(candidates) < n:
        sample = candidates
    else:
        sample = rng.choice(candidates, size=n, replace=False).tolist()
    items = [{"form_pos": p} for p in sample]
    return hit_dispersion_metrics(df, items)


def draw_chart(df, zones, engine_hits, path):
    fig, (ax_p, ax_d) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})

    zone_colors = {"Z1": "#FFCDD2", "Z2": "#C8E6C9", "Z3": "#BBDEFB"}
    for z in zones:
        lo, hi = z["buffer_lo"], z["buffer_hi"]
        for ax in (ax_p, ax_d):
            ax.axvspan(df.index[lo], df.index[hi], alpha=0.25, color=zone_colors.get(z["id"], "#EEE"), lw=0)

    ax_p.plot(df.index, df["close"], color="#333", lw=0.8)
    ax_p.set_ylabel("Close")
    ax_p.set_title(f"{SYMBOL} {INTERVAL} — price + MA dispersion (Z buffer shaded)")

    disp = df["ma_dispersion"]
    ax_d.plot(df.index, disp, color="#7B1FA2", lw=0.9, label="ma_dispersion")
    piv = df["ma_dispersion_pivot_low"]
    pm = piv.notna()
    if pm.any():
        ax_d.scatter(df.index[pm], piv[pm], marker="v", s=28, c="#4CAF50", label="pivot_low", zorder=3)

    hit_colors = {"Z1": "#C62828", "Z2": "#2E7D32", "Z3": "#1565C0"}
    for h in engine_hits:
        ts = h["form_ts"]
        ax_d.axvline(ts, color=hit_colors.get(h["zone"], "#000"), ls="--", lw=1.0, alpha=0.85)
        ax_p.axvline(ts, color=hit_colors.get(h["zone"], "#000"), ls="--", lw=0.8, alpha=0.6)

    ax_d.set_ylabel("Dispersion")
    ax_d.legend(loc="upper right", fontsize=8)
    ax_d.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_report(bounds, zone_stats, engine_hits, engine_m, sweep_m, sweep_events, rand_m, png_name):
    L = []
    L.append("# MA Dispersion 관측 리포트 — ETHUSDT 4h")
    L.append("")
    L.append(f"- 생성 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("- 지표: ma_dispersion = Σ|MA_i−MA_j| / (15 × close), CORE 6 MA")
    L.append("- 관측 전용 (게이트·필터·점수 연결 없음)")
    L.append("")
    L.append("## 1. 전역 dispersion 백분위 경계")
    L.append("")
    L.append("| 경계 | 값 |")
    L.append("|---|---|")
    for k in PCT_LABELS:
        L.append(f"| {k} | {bounds[k]:.6f} |")
    L.append("")

    L.append("## 2. 정답 구간 (Z±30봉 버퍼)")
    L.append("")
    for zid, st in zone_stats.items():
        L.append(f"### {zid}")
        L.append(f"- 유효 봉 수: {st['count']}")
        if st["min_row"]:
            mr = st["min_row"]
            L.append(f"- 구간 내 최저 백분위: **{mr['pct']:.1f}%** @ {fmt_ts(mr['ts'])} (disp={mr['disp']:.6f})")
        else:
            L.append("- 구간 내 유효 dispersion: 없음")
        if st["pcts"]:
            hist = Counter(int(p // 10) * 10 for p in st["pcts"])
            L.append(f"- 백분위 구간 분포(10% bin): {', '.join(f'{k}~{k+9}%={v}' for k, v in sorted(hist.items()))}")
        L.append("")

    L.append("## 3. HIT 상관 — 형성 봉(피봇) dispersion")
    L.append("")
    L.append("### 3a. 엔진 HIT (정답 구간 버퍼)")
    L.append("")
    L.append(f"- HIT 수: {engine_m['n']}")
    L.append(f"- 형성 봉 백분위 목록: {[round(p, 1) for p in engine_m['pcts']]}")
    L.append(f"- 전역 P25 이하 비율: {engine_m['p25_or_below']}/{engine_m['n']} ({engine_m['p25_or_below_pct']:.1f}%)")
    L.append(f"- 전역 P75 이상 비율: {engine_m['p75_or_above']}/{engine_m['n']} ({engine_m['p75_or_above_pct']:.1f}%)")
    L.append(f"- 양쪽 꼬리 합산(P≤25 또는 P≥75): {engine_m['tail']}/{engine_m['n']} ({engine_m['tail_pct']:.1f}%)")
    L.append(f"- pivot_low ±{PIVOT_NEAR_BARS}봉 이내 비율: {engine_m['near_pivot']}/{engine_m['n']} ({engine_m['near_pivot_pct']:.1f}%)")
    L.append("")
    L.append("| zone | rule_id | 형성 시각 | 형성 백분위 |")
    L.append("|---|---|---|---|")
    for h in engine_hits:
        pr = dispersion_percentile_rank(df_ref, h["form_pos"])
        L.append(f"| {h['zone']} | {h['rule_id']} | {fmt_ts(h['form_ts'])} | {pr:.1f}% |")
    L.append("")

    L.append("### 3b. 전체 스윕 WOULD_HIT (피봇 formation 구조 일치)")
    L.append("")
    L.append(f"- WOULD_HIT 수: {sweep_m['n']}")
    L.append(f"- 형성 봉 백분위 목록(전체): {[round(p, 1) for p in sweep_m['pcts']]}")
    L.append(f"- 전역 P25 이하 비율: {sweep_m['p25_or_below']}/{sweep_m['n']} ({sweep_m['p25_or_below_pct']:.1f}%)")
    L.append(f"- 전역 P75 이상 비율: {sweep_m['p75_or_above']}/{sweep_m['n']} ({sweep_m['p75_or_above_pct']:.1f}%)")
    L.append(f"- 양쪽 꼬리 합산(P≤25 또는 P≥75): {sweep_m['tail']}/{sweep_m['n']} ({sweep_m['tail_pct']:.1f}%)")
    L.append(f"- pivot_low ±{PIVOT_NEAR_BARS}봉 이내 비율: {sweep_m['near_pivot']}/{sweep_m['n']} ({sweep_m['near_pivot_pct']:.1f}%)")
    L.append("")

    L.append("## 4. 반대 검증 — 무작위 표본 (엔진 HIT 동수)")
    L.append("")
    L.append(f"- 표본 수: {rand_m['n']}")
    L.append(f"- 전역 P25 이하 비율: {rand_m['p25_or_below']}/{rand_m['n']} ({rand_m['p25_or_below_pct']:.1f}%)")
    L.append(f"- 전역 P75 이상 비율: {rand_m['p75_or_above']}/{rand_m['n']} ({rand_m['p75_or_above_pct']:.1f}%)")
    L.append(f"- 양쪽 꼬리 합산(P≤25 또는 P≥75): {rand_m['tail']}/{rand_m['n']} ({rand_m['tail_pct']:.1f}%)")
    L.append(f"- pivot_low ±{PIVOT_NEAR_BARS}봉 이내 비율: {rand_m['near_pivot']}/{rand_m['n']} ({rand_m['near_pivot_pct']:.1f}%)")
    L.append("")
    L.append("| 지표 | 엔진 HIT | 무작위 |")
    L.append("|---|---|---|")
    L.append(f"| P25 이하 % | {engine_m['p25_or_below_pct']:.1f} | {rand_m['p25_or_below_pct']:.1f} |")
    L.append(f"| P75 이상 % | {engine_m['p75_or_above_pct']:.1f} | {rand_m['p75_or_above_pct']:.1f} |")
    L.append(f"| 양쪽 꼬리 % | {engine_m['tail_pct']:.1f} | {rand_m['tail_pct']:.1f} |")
    L.append(f"| pivot_low ±{PIVOT_NEAR_BARS}봉 % | {engine_m['near_pivot_pct']:.1f} | {rand_m['near_pivot_pct']:.1f} |")
    L.append("")

    L.append("## 5. 차트")
    L.append("")
    L.append(f"- [dispersion_ETHUSDT_4h.png](./{png_name})")
    L.append("")

    path = os.path.join(OUT_DIR, "REPORT_DISPERSION.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"REPORT_DISPERSION 작성: {path}")


# module ref for report helper
df_ref = None


def main():
    global df_ref
    print(f"Loading {SYMBOL} {INTERVAL}...")
    df, limit = load_df_gt(SYMBOL, INTERVAL)
    df = add_ma_dispersion(df)
    df_ref = df
    zones = zone_ranges(df)

    bounds = global_percentile_bounds(df)
    zone_stats = {z["id"]: zone_dispersion_stats(df, z) for z in zones}

    engine_hits = collect_engine_hits(df, zones)
    engine_m = hit_dispersion_metrics(df, engine_hits)

    sweep_events = collect_sweep_would_hits(df)
    sweep_m = hit_dispersion_metrics(df, sweep_events)

    exclude = {h["form_pos"] for h in engine_hits}
    rand_m = random_baseline(df, engine_m["n"], exclude_pos=exclude)

    png_name = "dispersion_ETHUSDT_4h.png"
    png_path = os.path.join(OUT_DIR, png_name)
    draw_chart(df, zones, engine_hits, png_path)
    print(f"PNG: {png_path}")

    write_report(bounds, zone_stats, engine_hits, engine_m, sweep_m, sweep_events, rand_m, png_name)
    print("Done.")


if __name__ == "__main__":
    main()
