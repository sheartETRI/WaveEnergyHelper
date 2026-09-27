"""도달률 검증 — 레이어별 쌍바닥/쌍봉 확정 후 목표 MA 도달률 (SPEC_SWEEP_RECLAIM §11).

규칙(파동에너지): 소파동 쌍바닥 → 10~20MA, 중파동 → 20~60MA, 대파동 → 60~120MA
까지 도달할 힘. 정의는 §11 에 데이터를 보기 전에 동결했고 여기서는 그대로 계산만 한다.

  · 이벤트   레이어 쌍바닥 확정 봉 c (검출기 확정 컬럼, 후보 제외)
  · 적용     확정 봉에서 close_c < MA_c 인 목표만 (이미 위면 분모 제외)
  · 도달     창 안 어느 봉이든 high ≥ 그 봉의 MA
  · 창       3 × k_len — 소 15 / 중 30 / 대 60 봉
  · 종료     창 안 같은 레이어 쌍봉 확정이 먼저 오면 그 봉까지 (종료 없는 값도 병기)
  · 베이스   이벤트 조건 없이 전 봉에 같은 정의(종료 없음) → 리프트 = 이벤트 − 베이스
  · 급4 층화 대파동 이벤트를 (40,20,20) 쌍바닥 확정 동반([c−N, c+N]) 여부로 나눠 80·120 비교
  쌍봉은 전부 미러(low ≤ MA, close_c > MA_c).

검출기 무수정: indicators.stochastic.add_stochastic_slow_layers 로 확정 컬럼을 얻는다.
급4 층은 STOCH_LAYERS 에 (40,20,20) 항목을 런타임에 덧붙여 같은 검출기를 통과시킨다
(연구 스크립트 한정 — 앱 설정은 건드리지 않는다).

사용: python validation/wave_reach_rate.py            # logs/ohlcv_BTCUSDT_<tf>.csv 사용
출력: validation/REPORT_REACH_RATE.md + 콘솔 요약
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from dataclasses import dataclass
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from config.settings import WAVE_LAYER_ROLES
import indicators.stochastic as S

LAYERS = {"소": WAVE_LAYER_ROLES["small"], "중": WAVE_LAYER_ROLES["mid"], "대": WAVE_LAYER_ROLES["large"]}
GRADE4 = "(40,20,20)"
WINDOW = {"소": 15, "중": 30, "대": 60}          # 3 × k_len (사전등록)
TARGETS = (10, 20, 40, 60, 80, 120)
TFS = ("1w", "3d", "1d", "6h")
MIN_N = 5                                        # 이보다 작은 셀은 해석하지 않음 (표기만)


def ensure_grade4_layer() -> None:
    """검출기가 (40,20,20) 층도 계산하도록 STOCH_LAYERS 에 런타임 추가 (같은 리스트 객체)."""
    if not any(layer["label"] == GRADE4 for layer in S.STOCH_LAYERS):
        S.STOCH_LAYERS.append({
            "name": "G4", "label": GRADE4, "k_len": 40, "k_smooth": 20, "d_len": 20,
            "k_color": "#888888", "d_color": "#000000", "offset": 330.0,
        })


def load(tf: str) -> Optional[pd.DataFrame]:
    path = os.path.join(ROOT, "logs", f"ohlcv_BTCUSDT_{tf}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col])
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    out = S.add_stochastic_slow_layers(df.copy())
    close = out["close"].astype(float)
    for m in TARGETS:
        out[f"MA{m}"] = close.rolling(m, min_periods=m).mean()
    return out


def positions(df: pd.DataFrame, col: str) -> np.ndarray:
    if col not in df.columns:
        return np.array([], dtype=int)
    return np.flatnonzero(df[col].notna().to_numpy())


@dataclass
class Cell:
    n_conf: int = 0        # 확정 이벤트 수
    n_app: int = 0         # 적용(목표가 반대편에 있던) 이벤트 수
    reached: int = 0       # 종료 규칙 적용 도달
    reached_nostop: int = 0

    def rate(self) -> Optional[float]:
        return self.reached / self.n_app if self.n_app else None

    def rate_nostop(self) -> Optional[float]:
        return self.reached_nostop / self.n_app if self.n_app else None


def _reach_from(pos: int, end: int, up: bool, price: np.ndarray, ma: np.ndarray) -> bool:
    """(pos, end] 구간 도달 여부. up: high ≥ MA / down: low ≤ MA."""
    if end <= pos:
        return False
    seg_p, seg_m = price[pos + 1:end + 1], ma[pos + 1:end + 1]
    ok = ~np.isnan(seg_m)
    if not ok.any():
        return False
    return bool((seg_p[ok] >= seg_m[ok]).any() if up else (seg_p[ok] <= seg_m[ok]).any())


def event_cells(df: pd.DataFrame, layer: str, up: bool) -> dict[int, Cell]:
    """한 레이어·한 방향의 목표별 셀. up=True 는 쌍바닥→상방 도달, False 는 쌍봉→하방."""
    suffix, n_win = LAYERS[layer], WINDOW[layer]
    conf = positions(df, f"stoch_{'db' if up else 'dt'}_{suffix}")
    stop = positions(df, f"stoch_{'dt' if up else 'db'}_{suffix}")
    close = df["close"].to_numpy(dtype=float)
    price = df["high" if up else "low"].to_numpy(dtype=float)
    n = len(df)
    cells = {m: Cell() for m in TARGETS}
    for c in conf:
        end_nostop = min(c + n_win, n - 1)
        later_stops = stop[(stop > c) & (stop <= end_nostop)]
        end_stop = int(later_stops[0]) if len(later_stops) else end_nostop
        for m in TARGETS:
            ma = df[f"MA{m}"].to_numpy(dtype=float)
            cell = cells[m]
            cell.n_conf += 1
            if np.isnan(ma[c]):
                continue
            applicable = close[c] < ma[c] if up else close[c] > ma[c]
            if not applicable:
                continue
            cell.n_app += 1
            cell.reached += int(_reach_from(c, end_stop, up, price, ma))
            cell.reached_nostop += int(_reach_from(c, end_nostop, up, price, ma))
    return cells


def base_rates(df: pd.DataFrame, up: bool) -> dict[tuple[str, int], Optional[float]]:
    """(레이어 창, 목표) → 무조건부 도달률 (적용 조건·창·도달 동일, 종료 없음)."""
    close = df["close"].to_numpy(dtype=float)
    price = df["high" if up else "low"].to_numpy(dtype=float)
    n = len(df)
    out: dict[tuple[str, int], Optional[float]] = {}
    for layer, n_win in WINDOW.items():
        for m in TARGETS:
            ma = df[f"MA{m}"].to_numpy(dtype=float)
            hits = trials = 0
            for t in range(n - 1):
                if np.isnan(ma[t]):
                    continue
                applicable = close[t] < ma[t] if up else close[t] > ma[t]
                if not applicable:
                    continue
                trials += 1
                hits += int(_reach_from(t, min(t + n_win, n - 1), up, price, ma))
            out[(layer, m)] = hits / trials if trials else None
    return out


def grade4_split(df: pd.DataFrame, up: bool) -> dict[str, dict[int, Cell]]:
    """대파동 이벤트를 급4(40,20,20) 동반 여부로 층화 — 80·120 만 본다 (사전등록)."""
    suffix, n_win = LAYERS["대"], WINDOW["대"]
    kind = "db" if up else "dt"
    conf = positions(df, f"stoch_{kind}_{suffix}")
    g4 = positions(df, f"stoch_{kind}_{GRADE4}")
    stop = positions(df, f"stoch_{'dt' if up else 'db'}_{suffix}")
    close = df["close"].to_numpy(dtype=float)
    price = df["high" if up else "low"].to_numpy(dtype=float)
    n = len(df)
    groups = {"급4 동반": {m: Cell() for m in (80, 120)}, "급4 없음": {m: Cell() for m in (80, 120)}}
    for c in conf:
        with_g4 = bool(len(g4) and ((g4 >= c - n_win) & (g4 <= c + n_win)).any())
        group = groups["급4 동반" if with_g4 else "급4 없음"]
        end_nostop = min(c + n_win, n - 1)
        later_stops = stop[(stop > c) & (stop <= end_nostop)]
        end_stop = int(later_stops[0]) if len(later_stops) else end_nostop
        for m in (80, 120):
            ma = df[f"MA{m}"].to_numpy(dtype=float)
            cell = group[m]
            cell.n_conf += 1
            if np.isnan(ma[c]):
                continue
            applicable = close[c] < ma[c] if up else close[c] > ma[c]
            if not applicable:
                continue
            cell.n_app += 1
            cell.reached += int(_reach_from(c, end_stop, up, price, ma))
            cell.reached_nostop += int(_reach_from(c, end_nostop, up, price, ma))
    return groups


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _lift(ev: Optional[float], base: Optional[float]) -> str:
    if ev is None or base is None:
        return "—"
    return f"{(ev - base) * 100:+.0f}p"


def report_tf(tf: str, df: pd.DataFrame) -> list[str]:
    lines = [f"## {tf} — 봉 {len(df)}개 ({df.index[0].date()} ~ {df.index[-1].date()})", ""]
    for up, title in ((True, "쌍바닥 → 상방 목표 MA 도달"), (False, "쌍봉 → 하방 목표 MA 도달")):
        base = base_rates(df, up)
        lines += [f"### {title}", "",
                  "| 레이어 | 확정 n | 목표 | 적용 n | 도달(종료) | 도달(무종료) | 베이스 | 리프트 |",
                  "|---|---|---|---|---|---|---|---|"]
        for layer in LAYERS:
            cells = event_cells(df, layer, up)
            for m in TARGETS:
                cell = cells[m]
                flag = " *" if 0 < cell.n_app < MIN_N else ""
                lines.append(
                    f"| {layer}{flag} | {cell.n_conf} | MA{m} | {cell.n_app} | {_pct(cell.rate())} | "
                    f"{_pct(cell.rate_nostop())} | {_pct(base[(layer, m)])} | {_lift(cell.rate(), base[(layer, m)])} |"
                )
        lines.append("")
        groups = grade4_split(df, up)
        lines += [f"#### 대파동 급4(40,20,20) 층화 — 80·120 {'상방' if up else '하방'}", "",
                  "| 군 | 확정 n | 목표 | 적용 n | 도달(종료) | 도달(무종료) |", "|---|---|---|---|---|---|"]
        for gname, cells in groups.items():
            for m in (80, 120):
                cell = cells[m]
                flag = " *" if 0 < cell.n_app < MIN_N else ""
                lines.append(f"| {gname}{flag} | {cell.n_conf} | MA{m} | {cell.n_app} | {_pct(cell.rate())} | {_pct(cell.rate_nostop())} |")
        lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="도달률 검증 (SPEC §11)")
    parser.add_argument("--tfs", default=",".join(TFS))
    args = parser.parse_args()

    ensure_grade4_layer()
    lines = [
        "# 도달률 검증 보고 — SPEC_SWEEP_RECLAIM §11", "",
        "정의는 §11 에 데이터를 보기 전에 동결. 셀 `*` = 적용 n < 5 (해석하지 않음). "
        "리프트 = 도달(종료) − 베이스레이트(무조건부, 같은 창·적용 조건, 종료 없음). "
        "베이스가 높은 것은 이평선이 늘 가격 근처에 있기 때문 — 규칙의 힘은 리프트로 읽는다.", "",
    ]
    for tf in [s.strip() for s in args.tfs.split(",") if s.strip()]:
        df = load(tf)
        if df is None or df.empty:
            lines += [f"## {tf} — 데이터 없음 (logs/ohlcv_BTCUSDT_{tf}.csv)", ""]
            continue
        lines += report_tf(tf, enrich(df))

    out = os.path.join(ROOT, "validation", "REPORT_REACH_RATE.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n-> {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
