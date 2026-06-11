"""Verdict stability spell 분석 · REPORT_STABILITY · PNG (읽기 전용).

실행: python validation/spell_analysis.py

기존 verdict CSV/REPORT/엔진은 변경하지 않음.
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.verdict_stability import (
    FAMILY_COLORS,
    enrich_timeline_stability,
)
from display.asof import fetch_ohlcv_bare
from validation.verdict_categories import CATEGORY_COLORS

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SYMBOL = "ETHUSDT"
INTERVAL = "4h"
TIMELINE_CSV = os.path.join(OUT_DIR, f"verdict_timeline_{SYMBOL}_{INTERVAL}.csv")

# 스펙 구간 (타임라인 실제 연도 2026)
WINDOW_A = ("2026-01-16", "2026-01-25 23:59:59", "A Jan UP")
WINDOW_B = ("2026-04-08", "2026-05-16 23:59:59", "B Apr-May")

SEQUENCE_SPECS = [
    ("원본 category", "category", "category"),
    ("smoothed_2", "verdict_smoothed_2", "category"),
    ("smoothed_3", "verdict_smoothed_3", "category"),
    ("smoothed_5", "verdict_smoothed_5", "category"),
    ("원본 family", "family", "family"),
    ("family_smoothed_2", "family_smoothed_2", "family"),
    ("family_smoothed_3", "family_smoothed_3", "family"),
    ("family_smoothed_5", "family_smoothed_5", "family"),
]


def count_transitions(seq: list) -> int:
    if len(seq) <= 1:
        return 0
    return sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])


def spell_lengths(seq: list) -> list[int]:
    if not seq:
        return []
    runs = []
    cur = seq[0]
    n = 1
    for v in seq[1:]:
        if v == cur:
            n += 1
        else:
            runs.append(n)
            cur, n = v, 1
    runs.append(n)
    return runs


def spell_stats(seq: list) -> dict:
    spells = spell_lengths(seq)
    if not spells:
        return {
            "spell_count": 0,
            "mean": 0.0,
            "median": 0.0,
            "max": 0,
            "le2_ratio": 0.0,
            "transitions": 0,
        }
    s = pd.Series(spells, dtype=float)
    return {
        "spell_count": len(spells),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "max": int(s.max()),
        "le2_ratio": float((s <= 2).mean()),
        "transitions": count_transitions(seq),
    }


def slice_window(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()


def pct_reduction(before: float, after: float) -> str:
    if before == 0:
        return "—"
    return f"{(before - after) / before * 100:.1f}%"


def load_timeline() -> pd.DataFrame:
    if not os.path.isfile(TIMELINE_CSV):
        raise FileNotFoundError(f"run verdict_sweep first: {TIMELINE_CSV}")
    return pd.read_csv(TIMELINE_CSV, parse_dates=["timestamp"])


def analyze_sequences(df: pd.DataFrame) -> dict[str, dict]:
    enriched = enrich_timeline_stability(df)
    out: dict[str, dict] = {}
    for label, col, _kind in SEQUENCE_SPECS:
        seq = enriched[col].tolist()
        out[label] = {**spell_stats(seq), "column": col}
    out["_enriched"] = enriched
    return out


def analyze_windows(enriched: pd.DataFrame) -> dict:
    windows = {}
    for start, end, name in (WINDOW_A, WINDOW_B):
        w = slice_window(enriched, start, end)
        rows = {}
        for label, col, _ in SEQUENCE_SPECS:
            if label.startswith("smoothed_") and label != "smoothed_3":
                continue
            if label.startswith("family_smoothed_") and label != "family_smoothed_3":
                continue
            key = label
            rows[key] = spell_stats(w[col].tolist())
        windows[name] = rows
    return windows


def plot_colored_timeline(
    bare: pd.DataFrame,
    timeline: pd.DataFrame,
    value_col: str,
    color_map: dict,
    title: str,
    out_path: str,
    highlight_windows: tuple = (WINDOW_A, WINDOW_B),
) -> str:
    fig, ax = plt.subplots(figsize=(16, 6))
    close = bare["close"].astype(float)
    ax.plot(bare.index, close, color="#333333", linewidth=0.8)

    t1 = bare.index[-1]
    seg_start = None
    prev_val = None
    for _, row in timeline.iterrows():
        ts, val = row["timestamp"], row[value_col]
        if seg_start is None:
            seg_start, prev_val = ts, val
            continue
        if val != prev_val:
            ax.axvspan(
                seg_start, ts,
                color=color_map.get(prev_val, "#eee"),
                alpha=0.25,
            )
            seg_start, prev_val = ts, val
    if seg_start is not None and prev_val is not None:
        ax.axvspan(seg_start, t1, color=color_map.get(prev_val, "#eee"), alpha=0.25)

    for start, end, label in highlight_windows:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        ax.axvspan(s, e, color="#1565c0", alpha=0.08)
        ax.text(
            s + (e - s) / 2,
            ax.get_ylim()[1] * 0.98 if ax.get_ylim()[1] else 1,
            label,
            ha="center",
            va="top",
            fontsize=8,
            color="#1565c0",
            alpha=0.9,
        )

    ax.set_title(title)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def write_report(
    full_stats: dict[str, dict],
    window_stats: dict,
    enriched: pd.DataFrame,
) -> str:
    path = os.path.join(OUT_DIR, "REPORT_STABILITY.md")
    lines = [
        "# REPORT_STABILITY",
        "",
        f"- symbol: {SYMBOL} {INTERVAL}",
        f"- source: `{os.path.basename(TIMELINE_CSV)}` (읽기 전용)",
        f"- 평가 봉 수: {len(enriched)}",
        "",
        "## 구간 정의",
        "",
        f"- A: {WINDOW_A[0]} ~ {WINDOW_A[1].split()[0]} ({WINDOW_A[2]})",
        f"- B: {WINDOW_B[0]} ~ {WINDOW_B[1].split()[0]} ({WINDOW_B[2]})",
        "",
    ]

    # Full timeline tables
    lines.append("## 전체 타임라인")
    lines.append("")
    lines.append("### 1. 전환 횟수")
    lines.append("")
    lines.append("| 시퀀스 | 전환 수 |")
    lines.append("|---|---:|")
    for label, _, _ in SEQUENCE_SPECS:
        lines.append(f"| {label} | {full_stats[label]['transitions']} |")
    lines.append("")

    orig_t = full_stats["원본 category"]["transitions"]
    s3_t = full_stats["smoothed_3"]["transitions"]
    fo_t = full_stats["원본 family"]["transitions"]
    fs3_t = full_stats["family_smoothed_3"]["transitions"]
    lines.append(
        f"- confirm=3 category: {orig_t} → {s3_t} "
        f"(감소율 {pct_reduction(orig_t, s3_t)})"
    )
    lines.append(
        f"- confirm=3 family: {fo_t} → {fs3_t} "
        f"(감소율 {pct_reduction(fo_t, fs3_t)})"
    )
    lines.append(
        f"- family grouping (category→family): {orig_t} → {fo_t} "
        f"(감소율 {pct_reduction(orig_t, fo_t)})"
    )
    lines.append("")

    lines.append("### 2. spell 길이")
    lines.append("")
    lines.append("| 시퀀스 | 구간 수 | 평균 | 중앙 | 최대 |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, _, _ in SEQUENCE_SPECS:
        st = full_stats[label]
        lines.append(
            f"| {label} | {st['spell_count']} | {st['mean']:.1f} | "
            f"{st['median']:.0f} | {st['max']} |"
        )
    lines.append("")

    lines.append("### 3. ≤2봉 비율")
    lines.append("")
    lines.append("| 시퀀스 | 비율 |")
    lines.append("|---|---:|")
    for label, _, _ in SEQUENCE_SPECS:
        st = full_stats[label]
        lines.append(f"| {label} | {st['le2_ratio'] * 100:.1f}% |")
    lines.append("")

    orig_le2 = full_stats["원본 category"]["le2_ratio"]
    s3_le2 = full_stats["smoothed_3"]["le2_ratio"]
    lines.append(
        f"- confirm=3 category ≤2봉: {orig_le2 * 100:.1f}% → {s3_le2 * 100:.1f}% "
        f"(감소율 {pct_reduction(orig_le2, s3_le2)})"
    )
    lines.append("")

    # Window comparisons
    for wname, rows in window_stats.items():
        lines.append(f"## 구간 {wname}")
        lines.append("")
        compare_keys = [
            "원본 category",
            "smoothed_3",
            "원본 family",
            "family_smoothed_3",
        ]
        lines.append("### 전환 횟수")
        lines.append("")
        lines.append("| 시퀀스 | 전환 수 |")
        lines.append("|---|---:|")
        for k in compare_keys:
            lines.append(f"| {k} | {rows[k]['transitions']} |")
        lines.append("")

        o_t = rows["원본 category"]["transitions"]
        s_t = rows["smoothed_3"]["transitions"]
        of_t = rows["원본 family"]["transitions"]
        sf_t = rows["family_smoothed_3"]["transitions"]
        lines.append(
            f"- confirm=3 category 감소율: {pct_reduction(o_t, s_t)} "
            f"({o_t}→{s_t})"
        )
        lines.append(
            f"- confirm=3 family 감소율: {pct_reduction(of_t, sf_t)} "
            f"({of_t}→{sf_t})"
        )
        lines.append("")

        lines.append("### spell 길이")
        lines.append("")
        lines.append("| 시퀀스 | 평균 | 중앙 | 최대 |")
        lines.append("|---|---:|---:|---:|")
        for k in compare_keys:
            st = rows[k]
            lines.append(
                f"| {k} | {st['mean']:.1f} | {st['median']:.0f} | {st['max']} |"
            )
        lines.append("")

        lines.append("### ≤2봉 비율")
        lines.append("")
        lines.append("| 시퀀스 | 비율 |")
        lines.append("|---|---:|")
        for k in compare_keys:
            st = rows[k]
            lines.append(f"| {k} | {st['le2_ratio'] * 100:.1f}% |")
        o_l = rows["원본 category"]["le2_ratio"]
        s_l = rows["smoothed_3"]["le2_ratio"]
        lines.append(
            f"- confirm=3 category ≤2봉 감소율: {pct_reduction(o_l, s_l)}"
        )
        lines.append("")

    # A vs B summary (required item 4)
    lines.append("## 구간 A vs B (confirm=3 관측)")
    lines.append("")
    a = window_stats[WINDOW_A[2]]
    b = window_stats[WINDOW_B[2]]
    lines.append("| 지표 | A (1월) | B (4~5월) |")
    lines.append("|---|---:|---:|")
    for key, alabel, blabel in [
        ("원본 category", "원본 전환", "원본 전환"),
        ("smoothed_3", "smoothed_3 전환", "smoothed_3 전환"),
        ("원본 family", "family 전환", "family 전환"),
        ("family_smoothed_3", "family_s3 전환", "family_s3 전환"),
    ]:
        lines.append(
            f"| {key} 전환 | {a[key]['transitions']} | {b[key]['transitions']} |"
        )
    lines.append("")
    lines.append("| ≤2봉 비율 (원본 category) | "
                 f"{a['원본 category']['le2_ratio'] * 100:.1f}% | "
                 f"{b['원본 category']['le2_ratio'] * 100:.1f}% |")
    lines.append("| ≤2봉 비율 (smoothed_3) | "
                 f"{a['smoothed_3']['le2_ratio'] * 100:.1f}% | "
                 f"{b['smoothed_3']['le2_ratio'] * 100:.1f}% |")
    lines.append("| spell 평균 (원본 category) | "
                 f"{a['원본 category']['mean']:.1f} | "
                 f"{b['원본 category']['mean']:.1f} |")
    lines.append("| spell 평균 (smoothed_3) | "
                 f"{a['smoothed_3']['mean']:.1f} | "
                 f"{b['smoothed_3']['mean']:.1f} |")
    lines.append("")

    lines.append("## PNG")
    lines.append("")
    for name in (
        "verdict_original.png",
        "verdict_smoothed_3.png",
        "family_original.png",
        "family_smoothed_3.png",
    ):
        lines.append(f"- `{name}`")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    df = load_timeline()
    result = analyze_sequences(df)
    enriched: pd.DataFrame = result.pop("_enriched")
    window_stats = analyze_windows(enriched)

    bare = fetch_ohlcv_bare(SYMBOL, INTERVAL, 1600, paginated=True)
    if bare is None or bare.empty:
        raise RuntimeError(f"fetch failed {SYMBOL} {INTERVAL}")

    # align timeline to bare index range for plot
    plot_tl = enriched.copy()

    pngs = [
        (
            "category",
            CATEGORY_COLORS,
            f"{SYMBOL} {INTERVAL} — verdict original",
            "verdict_original.png",
        ),
        (
            "verdict_smoothed_3",
            CATEGORY_COLORS,
            f"{SYMBOL} {INTERVAL} — verdict smoothed_3",
            "verdict_smoothed_3.png",
        ),
        (
            "family",
            FAMILY_COLORS,
            f"{SYMBOL} {INTERVAL} — family original",
            "family_original.png",
        ),
        (
            "family_smoothed_3",
            FAMILY_COLORS,
            f"{SYMBOL} {INTERVAL} — family smoothed_3",
            "family_smoothed_3.png",
        ),
    ]
    for col, cmap, title, fname in pngs:
        plot_colored_timeline(
            bare,
            plot_tl,
            col,
            cmap,
            title,
            os.path.join(OUT_DIR, fname),
        )

    report_path = write_report(result, window_stats, enriched)
    print(f"REPORT_STABILITY -> {report_path}")
    print("PNG: verdict_original, verdict_smoothed_3, family_original, family_smoothed_3")


if __name__ == "__main__":
    main()
