"""Wave Cross Market Validation — Champion Rule 다시장 재현 검증.

기존 validation CSV만 소비. 엔진·신호·기존 CSV/REPORT 수정 없음.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from analysis.wave_expectancy import compute_expectancy_metrics

TARGET_SYMBOLS = (
    "ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT",
)
TIMEFRAMES = ("1h", "4h", "1d")
RULE_IDS = ("RULE_A", "RULE_B", "RULE_C", "RULE_D", "RULE_E")
TRAIN_FRAC = 0.70

CSV_EXPORT_COLS = (
    "symbol", "timeframe", "rule", "dataset", "n", "win_rate",
    "expectancy", "profit_factor", "positive", "drift",
)


def _validation_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "validation",
    )


def _confluence_path(symbol: str, tf: str) -> Optional[str]:
    for name in (
        f"wave_confluence_{symbol}_{tf}.csv",
        os.path.join("_generalization_cache", f"confluence_{symbol}_{tf}.csv"),
    ):
        path = os.path.join(_validation_dir(), name)
        if os.path.isfile(path):
            return path
    return None


def discover_cells() -> List[Tuple[str, str]]:
    cells: List[Tuple[str, str]] = []
    for sym in TARGET_SYMBOLS:
        for tf in TIMEFRAMES:
            if _confluence_path(sym, tf):
                cells.append((sym, tf))
    return cells


def _bool_val(val) -> bool:
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return bool(val)


def _is_tb(row: pd.Series) -> bool:
    branch = str(row.get("branch", row.get("branch_label", "")))
    path = str(row.get("path", ""))
    ws = str(row.get("wave_state", ""))
    return branch == "TRIPLE_BOTTOM_REQUIRED" or ws == "TRIPLE_BOTTOM_REQUIRED" or "TRIPLE_BOTTOM" in path


def _load_observation_merges() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    vdir = _validation_dir()
    mf = pd.read_csv(os.path.join(vdir, "wave_money_flow.csv"), parse_dates=["timestamp"]) if os.path.isfile(os.path.join(vdir, "wave_money_flow.csv")) else pd.DataFrame()
    sc = pd.read_csv(os.path.join(vdir, "wave_structure_confirmation.csv"), parse_dates=["timestamp"]) if os.path.isfile(os.path.join(vdir, "wave_structure_confirmation.csv")) else pd.DataFrame()
    ve = pd.read_csv(os.path.join(vdir, "wave_volume_energy.csv"), parse_dates=["timestamp"]) if os.path.isfile(os.path.join(vdir, "wave_volume_energy.csv")) else pd.DataFrame()
    qs = pd.read_csv(os.path.join(vdir, "wave_quality_score.csv"), parse_dates=["timestamp"]) if os.path.isfile(os.path.join(vdir, "wave_quality_score.csv")) else pd.DataFrame()
    return mf, sc, ve, qs


def enrich_cell_events(symbol: str, tf: str) -> pd.DataFrame:
    """Confluence + observation CSV 병합."""
    path = _confluence_path(symbol, tf)
    if not path:
        return pd.DataFrame()

    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["symbol"] = symbol
    df["timeframe"] = tf
    mf, sc, ve, qs = _load_observation_merges()
    key = ["timestamp", "symbol"]

    if not mf.empty:
        mc = [c for c in ("money_flow_score", "energy_score") if c in mf.columns]
        df = df.merge(mf[key + mc], on=key, how="left", suffixes=("", "_mf"))
    if not sc.empty:
        sc_cols = [c for c in ("structure_score", "energy_score", "money_flow_score") if c in sc.columns]
        df = df.merge(sc[key + sc_cols], on=key, how="left", suffixes=("", "_sc"))
    if not ve.empty and "energy_score" not in df.columns:
        ec = [c for c in ("energy_score",) if c in ve.columns]
        df = df.merge(ve[key + ec], on=key, how="left", suffixes=("", "_ve"))
    if not qs.empty:
        qc = [c for c in ("quality_score", "flag_tb", "flag_structure", "flag_energy", "flag_money_flow") if c in qs.columns]
        df = df.merge(qs[key + qc], on=key, how="left", suffixes=("", "_qs"))

    conf = pd.to_numeric(df.get("confluence_score", pd.Series(0, index=df.index)), errors="coerce").fillna(0)

    mf_score = pd.to_numeric(df.get("money_flow_score"), errors="coerce")
    for col in ("money_flow_score_sc", "money_flow_score_mf"):
        if col in df.columns:
            mf_score = mf_score.fillna(pd.to_numeric(df[col], errors="coerce"))
    struct_score = pd.to_numeric(df.get("structure_score"), errors="coerce")
    if "structure_score_sc" in df.columns:
        struct_score = struct_score.fillna(pd.to_numeric(df["structure_score_sc"], errors="coerce"))
    energy_score = pd.to_numeric(df.get("energy_score"), errors="coerce")
    for col in ("energy_score_ve", "energy_score_mf", "energy_score_sc"):
        if col in df.columns:
            energy_score = energy_score.fillna(pd.to_numeric(df[col], errors="coerce"))

    df["flag_tb"] = df.apply(_is_tb, axis=1)
    if "flag_tb_qs" in df.columns:
        df["flag_tb"] = df["flag_tb"] | df["flag_tb_qs"].map(_bool_val)

    df["flag_money_flow"] = (mf_score >= 4) | (mf_score.isna() & (conf >= 4))
    if "flag_money_flow_qs" in df.columns:
        df["flag_money_flow"] = df["flag_money_flow"] | df["flag_money_flow_qs"].map(_bool_val)

    df["flag_structure"] = (struct_score >= 3) | (struct_score.isna() & (conf >= 3))
    if "flag_structure_qs" in df.columns:
        df["flag_structure"] = df["flag_structure"] | df["flag_structure_qs"].map(_bool_val)

    df["flag_energy"] = (energy_score >= 3) | (energy_score.isna() & (conf >= 3))
    if "flag_energy_qs" in df.columns:
        df["flag_energy"] = df["flag_energy"] | df["flag_energy_qs"].map(_bool_val)

    if "quality_score" in df.columns:
        df["quality_score"] = pd.to_numeric(df["quality_score"], errors="coerce").fillna(0)
    else:
        df["quality_score"] = (
            df["flag_tb"].astype(int) + df["flag_structure"].astype(int)
            + df["flag_energy"].astype(int) + df["flag_money_flow"].astype(int)
        )

    if "return_pct" not in df.columns:
        df["return_pct"] = np.nan
    return df


def rule_filters() -> Dict[str, Callable[[pd.DataFrame], pd.Series]]:
    return {
        "RULE_A": lambda df: df["flag_tb"] & df["flag_money_flow"],
        "RULE_B": lambda df: df["flag_tb"] & df["flag_money_flow"] & df["flag_structure"],
        "RULE_C": lambda df: df["flag_energy"] & df["flag_money_flow"],
        "RULE_D": lambda df: df["flag_tb"] & df["flag_structure"],
        "RULE_E": lambda df: df["quality_score"] >= 4,
    }


def apply_rule(df: pd.DataFrame, rule_id: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[rule_filters()[rule_id](df)].copy()


def evaluate_events(sub: pd.DataFrame) -> dict:
    if sub.empty or "return_pct" not in sub.columns:
        return {"n": 0}
    rets = sub["return_pct"].dropna().astype(float)
    if len(rets) == 0:
        return {"n": 0}
    m = compute_expectancy_metrics(rets)
    exp = m.get("expectancy")
    return {
        "n": m.get("n", 0),
        "win_rate": m.get("win_rate"),
        "expectancy": exp,
        "profit_factor": m.get("profit_factor"),
        "positive": bool(exp is not None and exp > 0),
    }


def train_test_split(sub: pd.DataFrame, train_frac: float = TRAIN_FRAC) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if sub.empty:
        return sub, sub
    ordered = sub.sort_values("timestamp").reset_index(drop=True)
    n = len(ordered)
    if n < 2:
        return ordered, pd.DataFrame()
    cut = max(1, int(n * train_frac))
    if cut >= n:
        cut = n - 1
    return ordered.iloc[:cut], ordered.iloc[cut:]


def cross_market_matrix(events_by_cell: Dict[Tuple[str, str], pd.DataFrame]) -> List[dict]:
    rows = []
    for (sym, tf), df in events_by_cell.items():
        for rule_id in RULE_IDS:
            sub = apply_rule(df, rule_id)
            m = evaluate_events(sub)
            rows.append({
                "symbol": sym,
                "timeframe": tf,
                "rule": rule_id,
                "dataset": "ALL",
                **m,
            })
    return rows


def positive_cell_ratio(matrix: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        cells = [r for r in matrix if r["rule"] == rule_id and r.get("n", 0) >= 1]
        positive = sum(1 for r in cells if r.get("positive"))
        total = len(cells)
        rows.append({
            "rule": rule_id,
            "positive_cells": positive,
            "total_cells": total,
            "positive_ratio": positive / total if total else 0.0,
        })
    return rows


def train_test_analysis(events_by_cell: Dict[Tuple[str, str], pd.DataFrame]) -> List[dict]:
    rows = []
    for (sym, tf), df in events_by_cell.items():
        for rule_id in RULE_IDS:
            sub = apply_rule(df, rule_id)
            train, test = train_test_split(sub)
            for label, part in (("TRAIN", train), ("TEST", test)):
                m = evaluate_events(part)
                rows.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "rule": rule_id,
                    "dataset": label,
                    **m,
                })
    return rows


def drift_analysis(train_test_rows: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        for sym in {r["symbol"] for r in train_test_rows}:
            for tf in TIMEFRAMES:
                tr = next(
                    (r for r in train_test_rows if r["rule"] == rule_id and r["symbol"] == sym
                     and r["timeframe"] == tf and r["dataset"] == "TRAIN"),
                    None,
                )
                te = next(
                    (r for r in train_test_rows if r["rule"] == rule_id and r["symbol"] == sym
                     and r["timeframe"] == tf and r["dataset"] == "TEST"),
                    None,
                )
                if not tr or not te:
                    continue
                te_exp = te.get("expectancy")
                tr_exp = tr.get("expectancy")
                te_wr = te.get("win_rate")
                tr_wr = tr.get("win_rate")
                rows.append({
                    "rule": rule_id,
                    "symbol": sym,
                    "timeframe": tf,
                    "train_n": tr.get("n", 0),
                    "test_n": te.get("n", 0),
                    "train_expectancy": tr_exp,
                    "test_expectancy": te_exp,
                    "expectancy_drift": (te_exp - tr_exp) if te_exp is not None and tr_exp is not None else None,
                    "train_win_rate": tr_wr,
                    "test_win_rate": te_wr,
                    "win_rate_drift": (te_wr - tr_wr) if te_wr is not None and tr_wr is not None else None,
                })
    return rows


def market_robustness(matrix: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        cells = [r for r in matrix if r["rule"] == rule_id and r.get("n", 0) >= 1 and r.get("expectancy") is not None]
        if not cells:
            rows.append({"rule": rule_id})
            continue
        exps = [float(r["expectancy"]) for r in cells]
        best = max(cells, key=lambda x: x["expectancy"])
        worst = min(cells, key=lambda x: x["expectancy"])
        rows.append({
            "rule": rule_id,
            "mean_expectancy": float(np.mean(exps)),
            "median_expectancy": float(np.median(exps)),
            "variance": float(np.var(exps)) if len(exps) > 1 else 0.0,
            "best_cell": f"{best['symbol']}_{best['timeframe']}",
            "best_expectancy": best.get("expectancy"),
            "worst_cell": f"{worst['symbol']}_{worst['timeframe']}",
            "worst_expectancy": worst.get("expectancy"),
        })
    return rows


def symbol_independence(matrix: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        for label, filt in (("WITH_ETH", None), ("WITHOUT_ETH", lambda r: r["symbol"] != "ETHUSDT")):
            cells = [r for r in matrix if r["rule"] == rule_id and r.get("n", 0) >= 1]
            if filt:
                cells = [r for r in cells if filt(r)]
            exps = [r["expectancy"] for r in cells if r.get("expectancy") is not None]
            pos = sum(1 for e in exps if e > 0)
            rows.append({
                "rule": rule_id,
                "scope": label,
                "cells": len(cells),
                "positive_cells": pos,
                "mean_expectancy": float(np.mean(exps)) if exps else None,
                "positive_ratio": pos / len(exps) if exps else 0.0,
            })
    return rows


def timeframe_robustness(matrix: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        for tf in TIMEFRAMES:
            cells = [r for r in matrix if r["rule"] == rule_id and r["timeframe"] == tf and r.get("n", 0) >= 1]
            total_n = sum(c.get("n", 0) for c in cells)
            weighted = [
                float(c["expectancy"]) * c["n"]
                for c in cells
                if c.get("expectancy") is not None and c.get("n", 0) >= 1
            ]
            rows.append({
                "rule": rule_id,
                "timeframe": tf,
                "n": total_n,
                "cell_count": len(cells),
                "expectancy": sum(weighted) / total_n if total_n and weighted else None,
            })
    return rows


def rule_survival(matrix: List[dict]) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        markets = [
            f"{r['symbol']}_{r['timeframe']}"
            for r in matrix
            if r["rule"] == rule_id and r.get("n", 0) >= 1 and r.get("positive")
        ]
        rows.append({
            "rule": rule_id,
            "survival_market_count": len(markets),
            "markets": markets,
        })
    return rows


def aggregate_test_expectancy(train_test_rows: List[dict]) -> Dict[str, float]:
    out: Dict[str, List[float]] = {r: [] for r in RULE_IDS}
    for rule_id in RULE_IDS:
        tests = [
            r for r in train_test_rows
            if r["rule"] == rule_id and r["dataset"] == "TEST"
            and r.get("n", 0) >= 1 and r.get("expectancy") is not None
        ]
        for t in tests:
            out[rule_id].append(float(t["expectancy"]))
    return {k: float(np.mean(v)) if v else -999.0 for k, v in out.items()}


def select_champion_v2(
    positive_ratios: List[dict],
    survival: List[dict],
    market_stats: List[dict],
    test_exp: Dict[str, float],
) -> dict:
    pr_map = {r["rule"]: r for r in positive_ratios}
    surv_map = {r["rule"]: r for r in survival}
    mkt_map = {r["rule"]: r for r in market_stats}

    ranked = sorted(
        RULE_IDS,
        key=lambda rid: (
            test_exp.get(rid, -999),
            pr_map.get(rid, {}).get("positive_ratio", 0),
            surv_map.get(rid, {}).get("survival_market_count", 0),
            -(mkt_map.get(rid, {}).get("variance") or 999),
        ),
        reverse=True,
    )
    champ = ranked[0]
    return {
        "rule": champ,
        "test_expectancy_avg": test_exp.get(champ),
        "positive_ratio": pr_map.get(champ, {}).get("positive_ratio"),
        "survival_market_count": surv_map.get(champ, {}).get("survival_market_count"),
        "variance": mkt_map.get(champ, {}).get("variance"),
    }


def overfitting_risk(
    matrix: List[dict],
    drift_rows: List[dict],
    positive_ratios: List[dict],
) -> List[dict]:
    rows = []
    for rule_id in RULE_IDS:
        cells = [r for r in matrix if r["rule"] == rule_id and r.get("n", 0) >= 1]
        total_n = sum(c.get("n", 0) for c in cells)
        pr = next((r["positive_ratio"] for r in positive_ratios if r["rule"] == rule_id), 0)
        drifts = [
            abs(r["expectancy_drift"]) for r in drift_rows
            if r["rule"] == rule_id and r.get("expectancy_drift") is not None
        ]
        avg_drift = float(np.mean(drifts)) if drifts else 0.0
        exps = [r["expectancy"] for r in cells if r.get("expectancy") is not None]
        var = float(np.var(exps)) if len(exps) > 1 else 0.0

        risk = "LOW"
        if total_n < 10 or pr < 0.35 or avg_drift > 2.0 or var > 3.0:
            risk = "HIGH"
        elif total_n < 25 or pr < 0.5 or avg_drift > 1.0 or var > 1.5:
            risk = "MEDIUM"

        rows.append({
            "rule": rule_id,
            "total_n": total_n,
            "cell_count": len(cells),
            "positive_ratio": pr,
            "avg_drift": avg_drift,
            "variance": var,
            "risk": risk,
        })
    return rows


def final_verdict(
    champion: dict,
    symbol_indep: List[dict],
    positive_ratios: List[dict],
) -> dict:
    champ = champion.get("rule", "RULE_A")
    without_eth = next((r for r in symbol_indep if r["rule"] == champ and r["scope"] == "WITHOUT_ETH"), {})
    pr = next((r for r in positive_ratios if r["rule"] == champ), {})
    survives_without_eth = (without_eth.get("positive_ratio") or 0) >= 0.4
    multi_market = (pr.get("positive_cells") or 0) >= 2
    passes = survives_without_eth and multi_market and (champion.get("positive_ratio") or 0) >= 0.4
    return {
        "result": "PASS" if passes else "FAIL",
        "pass": passes,
        "champion": champ,
        "eth_specific": not survives_without_eth,
        "multi_market": multi_market,
    }


def build_cross_market_csv(all_rows: List[dict], drift_rows: List[dict]) -> pd.DataFrame:
    out = []
    for r in all_rows:
        out.append({c: r.get(c) for c in CSV_EXPORT_COLS})
    for d in drift_rows:
        if d.get("test_n", 0) < 1:
            continue
        out.append({
            "symbol": d.get("symbol"),
            "timeframe": d.get("timeframe"),
            "rule": d.get("rule"),
            "dataset": "DRIFT",
            "n": d.get("test_n"),
            "win_rate": d.get("test_win_rate"),
            "expectancy": d.get("test_expectancy"),
            "profit_factor": None,
            "positive": bool((d.get("test_expectancy") or 0) > 0),
            "drift": d.get("expectancy_drift"),
        })
    return pd.DataFrame(out)


def full_cross_market_summary() -> dict:
    cells = discover_cells()
    events_by_cell = {(sym, tf): enrich_cell_events(sym, tf) for sym, tf in cells}

    matrix = cross_market_matrix(events_by_cell)
    pos_ratio = positive_cell_ratio(matrix)
    tt = train_test_analysis(events_by_cell)
    drift = drift_analysis(tt)
    mkt = market_robustness(matrix)
    sym_indep = symbol_independence(matrix)
    tf_rob = timeframe_robustness(matrix)
    survival = rule_survival(matrix)
    test_exp = aggregate_test_expectancy(tt)
    champion = select_champion_v2(pos_ratio, survival, mkt, test_exp)
    overfit = overfitting_risk(matrix, drift, pos_ratio)
    verdict = final_verdict(champion, sym_indep, pos_ratio)

    all_rows = matrix + tt
    return {
        "dataframe": build_cross_market_csv(all_rows, drift),
        "cells": cells,
        "cell_count": len(cells),
        "matrix": matrix,
        "positive_cell_ratio": pos_ratio,
        "train_test": tt,
        "drift": drift,
        "market_robustness": mkt,
        "symbol_independence": sym_indep,
        "timeframe_robustness": tf_rob,
        "rule_survival": survival,
        "champion_v2": champion,
        "overfitting_risk": overfit,
        "final_verdict": verdict,
    }
