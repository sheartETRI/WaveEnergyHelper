"""조정 후 도달·역행폭 검증 — 대파동 쌍바닥 후 2파(소파동 쌍봉)가 먼저 왔을 때 (SPEC §11-2).

규칙 후보: "대파동 쌍바닥이면 최소 60MA 는 간다 → 조정이 와도 3파가 60 에 닿으니 롱 대응".
§11 도달률은 조정이 먼저 온 부분집단을 따로 보지 않았고 경로(역행폭)를 모른다. 여기서는
정의를 §11-2 에 동결한 뒤 그대로 잰다:

  · 모집단   대파동 쌍바닥 확정 c, close_c < MA60_c, 창 c+60
  · 2파 조정 c 이후 MA60 터치 전에 소파동(5,3,3) 쌍봉 확정 p
  · 도달     p 이후 창 끝까지 high ≥ MA60/80/120 (대파동 쌍봉 확정 시 종료)
  · 기준가   close_p (가상 대응 기준점 — 실제 진입 규칙과 별개)
  · MAE      p 이후 MA60 도달 봉(미도달이면 창 끝)까지 min(low)/close_p − 1
  · 피격     MA60 도달 전에 low ≤ close_p×0.97 (−3%) / low ≤ 구조저점×0.995 (구조저점 = min low[c−20..c])

사용: python validation/wave_reach_after_pullback.py   (logs/ohlcv_BTCUSDT_<tf>.csv)
출력: validation/REPORT_REACH_PULLBACK.md + 콘솔
"""
from __future__ import annotations

import os
import sys
import warnings
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from validation.wave_reach_rate import LAYERS, TFS, WINDOW, enrich, load, positions

N_WIN = WINDOW["대"]          # 60
STRUCT_LOOKBACK = 20
STOP_PCT = 0.97               # 현행 −3%
STRUCT_BUF = 0.995
MIN_N = 5


def _first_touch(pos: int, end: int, price: np.ndarray, ma: np.ndarray) -> Optional[int]:
    """(pos, end] 에서 high ≥ MA 첫 봉 위치. 없으면 None."""
    for i in range(pos + 1, end + 1):
        if not np.isnan(ma[i]) and price[i] >= ma[i]:
            return i
    return None


def analyze(df: pd.DataFrame) -> dict:
    large, small = LAYERS["대"], LAYERS["소"]
    conf = positions(df, f"stoch_db_{large}")
    large_dt = positions(df, f"stoch_dt_{large}")
    small_dt = positions(df, f"stoch_dt_{small}")
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    ma = {m: df[f"MA{m}"].to_numpy(dtype=float) for m in (60, 80, 120)}
    n = len(df)

    pull = {"n": 0, "reach": {60: 0, 80: 0, 120: 0}, "app": {60: 0, 80: 0, 120: 0},
            "mae": [], "hit_pct": 0, "hit_struct": 0, "reach60_after_hit": 0}
    nopull = {"n": 0, "reach": {60: 0, 80: 0, 120: 0}, "app": {60: 0, 80: 0, 120: 0}}

    for c in conf:
        if np.isnan(ma[60][c]) or not close[c] < ma[60][c]:
            continue
        end = min(c + N_WIN, n - 1)
        stops = large_dt[(large_dt > c) & (large_dt <= end)]
        if len(stops):
            end = int(stops[0])
        t60 = _first_touch(c, end, high, ma[60])
        pb = small_dt[(small_dt > c) & (small_dt <= (t60 if t60 is not None else end))]
        if not len(pb):
            # 무조정군 — c 기준 도달
            nopull["n"] += 1
            for m in (60, 80, 120):
                if np.isnan(ma[m][c]) or not close[c] < ma[m][c]:
                    continue
                nopull["app"][m] += 1
                nopull["reach"][m] += int(_first_touch(c, end, high, ma[m]) is not None)
            continue

        p = int(pb[0])
        pull["n"] += 1
        ref = close[p]
        struct_low = float(np.nanmin(low[max(0, c - STRUCT_LOOKBACK):c + 1])) * STRUCT_BUF
        r60 = _first_touch(p, end, high, ma[60])
        path_end = r60 if r60 is not None else end
        seg_low = low[p + 1:path_end + 1]
        if len(seg_low):
            pull["mae"].append(float(seg_low.min() / ref - 1.0))
            hit_pct = bool((seg_low <= ref * STOP_PCT).any())
            hit_struct = bool((seg_low <= struct_low).any())
        else:
            hit_pct = hit_struct = False
        pull["hit_pct"] += int(hit_pct)
        pull["hit_struct"] += int(hit_struct)
        if hit_pct and r60 is not None:
            pull["reach60_after_hit"] += 1
        for m in (60, 80, 120):
            if np.isnan(ma[m][p]) or not close[p] < ma[m][p]:
                continue
            pull["app"][m] += 1
            pull["reach"][m] += int(_first_touch(p, end, high, ma[m]) is not None)
    return {"pull": pull, "nopull": nopull}


def _pct(num: int, den: int) -> str:
    return "—" if den == 0 else f"{num / den * 100:.0f}% ({num}/{den})"


def report_tf(tf: str, res: dict) -> list[str]:
    pull, nopull = res["pull"], res["nopull"]
    flag = " *" if 0 < pull["n"] < MIN_N else ""
    lines = [f"## {tf}", "",
             f"조정군(소파동 쌍봉이 MA60 터치 전에 옴){flag}: n={pull['n']} · 무조정군: n={nopull['n']}", "",
             "| 군 | MA60 도달 | MA80 도달 | MA120 도달 |", "|---|---|---|---|",
             f"| 조정군 (p 기준) | {_pct(pull['reach'][60], pull['app'][60])} | {_pct(pull['reach'][80], pull['app'][80])} | {_pct(pull['reach'][120], pull['app'][120])} |",
             f"| 무조정군 (c 기준, 대조) | {_pct(nopull['reach'][60], nopull['app'][60])} | {_pct(nopull['reach'][80], nopull['app'][80])} | {_pct(nopull['reach'][120], nopull['app'][120])} |",
             ""]
    if pull["mae"]:
        mae = np.array(pull["mae"]) * 100
        lines += ["| 조정군 경로 (p → MA60 도달/창 끝) | 값 |", "|---|---|",
                  f"| MAE 중앙값 | {np.median(mae):.1f}% |",
                  f"| MAE 하위 25% | {np.percentile(mae, 25):.1f}% |",
                  f"| MAE 최악 | {mae.min():.1f}% |",
                  f"| −3% 피격률 (도달 전) | {_pct(pull['hit_pct'], pull['n'])} |",
                  f"| 구조 손절 피격률 (도달 전) | {_pct(pull['hit_struct'], pull['n'])} |",
                  f"| −3% 피격 후 결국 MA60 도달 | {_pct(pull['reach60_after_hit'], pull['hit_pct'])} |",
                  ""]
    return lines


def main() -> int:
    lines = ["# 조정 후 도달·역행폭 검증 — SPEC §11-2", "",
             "정의는 §11-2 에 데이터를 보기 전에 동결. `*` = 조정군 n < 5 (해석하지 않음). "
             "기준가 close_p 는 2파 신호 확정 봉 종가(가상 기준점, 실제 진입 규칙과 별개). "
             "판정 관문: 도달률이 아니라 **도달 전 피격률** — 피격 후 도달은 롱 실패다.", ""]
    for tf in TFS:
        df = load(tf)
        if df is None or df.empty:
            lines += [f"## {tf} — 데이터 없음", ""]
            continue
        lines += report_tf(tf, analyze(enrich(df)))
    out = os.path.join(ROOT, "validation", "REPORT_REACH_PULLBACK.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
