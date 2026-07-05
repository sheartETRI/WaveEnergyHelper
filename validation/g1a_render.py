"""G1-a 차트 렌더 — MA 쌍바닥/쌍봉 S0 이벤트 1건 → PNG (검토용).

기존 mplfinance 스타일(charles + config MA색) 재사용. 검출기·규칙 무수정, 표시만.
확정 봉 전 120봉/후 30봉 맥락 + 바닥1·바닥2 피봇 마커 + 넥라인 수평선 +
확정 봉 세로선 + kind·S0 주석.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as _fm  # noqa: E402
# 한글 라벨(김박사 검토용) — Windows 기본 Malgun Gothic. 없으면 폴백.
_AVAIL = {f.name for f in _fm.fontManager.ttflist}
KFONT = next((f for f in ("Malgun Gothic", "NanumGothic", "Gulim", "Batang") if f in _AVAIL), None)
if KFONT:
    matplotlib.rcParams["font.family"] = KFONT
matplotlib.rcParams["axes.unicode_minus"] = False

import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

from config.settings import MA_COLORS  # noqa: E402

_CTX_MA = [5, 10, 20, 60]   # 맥락 이평 (패턴 MA는 강조)


def _second_pivot_pos(full_df, period, pattern, first_pos, confirm_pos):
    """바닥2(db)/천장2(dt) 위치 = first_pos 이후 confirm 이전 마지막 피봇."""
    col = f"ma{period}_pivot_{'low' if pattern == 'db' else 'high'}"
    if col not in full_df.columns:
        return None
    s = full_df[col]
    cands = [i for i in range(int(first_pos) + 1, confirm_pos) if not pd.isna(s.iloc[i])]
    return cands[-1] if cands else None


def render_ma_event(
    full_df: pd.DataFrame,
    symbol: str,
    tf: str,
    period: int,
    pattern: str,          # "db" | "dt"
    confirm_pos: int,
    kind,
    neckline,
    out_path: str,
) -> bool:
    """MA 쌍바닥/쌍봉 확정 봉 차트 저장. 성공 True."""
    fp_col = f"ma{period}_{pattern}_first_pos"
    raw_fp = full_df.iloc[confirm_pos].get(fp_col) if fp_col in full_df.columns else None
    first_pos = int(raw_fp) if raw_fp is not None and not pd.isna(raw_fp) else max(0, confirm_pos - 20)
    second_pos = _second_pivot_pos(full_df, period, pattern, first_pos, confirm_pos)

    lo = max(0, min(confirm_pos - 120, first_pos - 5))
    hi = min(len(full_df), confirm_pos + 31)
    sub = full_df.iloc[lo:hi]
    if sub.empty:
        return False
    ohlc = sub[["open", "high", "low", "close", "volume"]].copy()
    confirm_ts = pd.Timestamp(full_df.index[confirm_pos])

    aps = []
    ma_col = f"MA{period}"
    for p in sorted(set(_CTX_MA + [period])):
        col = f"MA{p}"
        if col in sub.columns and not sub[col].dropna().empty:
            emph = (p == period)
            aps.append(mpf.make_addplot(
                sub[col], color=MA_COLORS.get(p, "#000"),
                width=2.2 if emph else 0.9, panel=0,
            ))

    # 바닥1·바닥2 마커 (패턴 MA 값 위에).
    def _marker_series(pos):
        ser = pd.Series(index=sub.index, dtype=float)
        if pos is not None and lo <= pos < hi:
            ts = full_df.index[pos]
            val = full_df[ma_col].iloc[pos] if ma_col in full_df.columns else full_df["close"].iloc[pos]
            if not pd.isna(val):
                ser.loc[ts] = float(val)
        return ser

    marker = "^" if pattern == "db" else "v"
    mcolor = "#12b886" if pattern == "db" else "#e03131"
    for pos in (first_pos, second_pos):
        ms = _marker_series(pos)
        if ms.notna().any():
            aps.append(mpf.make_addplot(ms, type="scatter", markersize=180,
                                        marker=marker, color=mcolor, panel=0))

    mc = mpf.make_marketcolors(up=(1.0, 0.2, 0.2, 0.7), down=(0.2, 0.4, 1.0, 0.7),
                               edge="inherit", wick={"up": "#ff3b3b", "down": "#2979ff"},
                               volume="inherit")
    style = mpf.make_mpf_style(base_mpf_style="charles", marketcolors=mc,
                               gridstyle="--", facecolor="#f7f7f7", y_on_right=True,
                               rc={"font.family": KFONT or "DejaVu Sans",
                                   "axes.unicode_minus": False})

    pat_ko = "쌍바닥" if pattern == "db" else "쌍봉"
    nl = "—" if neckline is None or pd.isna(neckline) else f"{float(neckline):.6g}"
    price = float(full_df["close"].iloc[confirm_pos])
    title = (f"{symbol} {tf} · MA{period} {pat_ko}({kind}) · 넥라인 {nl}\n"
             f"S0 확정 {confirm_ts:%Y-%m-%d %H:%M} · 종가 {price:.6g}")

    hlines = dict(hlines=[float(neckline)], colors=["#1c7ed6"], linestyle="--", linewidths=1.1) \
        if neckline is not None and not pd.isna(neckline) else None
    vlines = dict(vlines=[confirm_ts], colors=["#7048e8"], linewidths=1.3, alpha=0.8)

    kwargs = dict(type="candle", addplot=aps, style=style, title=title,
                  ylabel="Price", volume=True, figsize=(13, 8), tight_layout=True,
                  savefig=dict(fname=out_path, dpi=90), vlines=vlines)
    if hlines:
        kwargs["hlines"] = hlines
    try:
        mpf.plot(ohlc, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"render fail {out_path}: {exc}")
        return False


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
