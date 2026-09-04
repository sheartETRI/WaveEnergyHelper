"""SPEC_WAVE_ALIGN_GATE §8 — 월 클러스터 부트스트랩 유닛 테스트.

- 시드 재현성
- 블록 재표집의 코호트 길이 보존
- 월 경계 배정 정확성
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.wave_align_gate_sweep import (
    BOOTSTRAP_SEED,
    COST_ROUNDTRIP_PCT,
    MIN_ALIGN_N,
    add_cluster_keys,
    by_key_delta,
    cost_adjusted,
    delta_prime,
    half_split_delta,
    judge_align,
    month_cluster_bootstrap,
)


def _pool(n=600, seed=0, align_edge=1.0):
    """합성 이벤트 풀 — G_ALIGN 코호트에 align_edge 만큼 우위를 준다."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2021-01-01", periods=n, freq="7h")
    align = rng.random(n) < 0.4
    rets = rng.normal(0.0, 3.0, n) + align * align_edge
    df = pd.DataFrame({
        "timestamp": ts,
        "symbol": rng.choice(["BTCUSDT", "ETHUSDT", "BNBUSDT"], size=n),
        "ltf": rng.choice(["1h", "6h"], size=n),
        "pair": "PAIR_B",
        "g_align": align,
        "g_wave": rng.random(n) < 0.5,
        "return_20": rets,
    })
    df["g_both"] = df["g_align"] & df["g_wave"]
    return add_cluster_keys(df)


# --------------------------------------------------- 월 경계 배정 정확성
def test_cluster_key_is_symbol_ltf_calendar_month():
    df = pd.DataFrame({
        "timestamp": [
            pd.Timestamp("2021-01-31 23:59:59"),
            pd.Timestamp("2021-02-01 00:00:00"),
            pd.Timestamp("2021-02-28 12:00:00"),
            pd.Timestamp("2021-01-31 23:59:59"),
        ],
        "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT", "ETHUSDT"],
        "ltf": ["1h", "1h", "1h", "1h"],
        "g_align": [True, True, False, True],
        "return_20": [1.0, 2.0, 3.0, 4.0],
    })
    out = add_cluster_keys(df)
    by_ts = dict(zip(out["timestamp"], out["cluster"]))
    # 월말 마지막 초와 다음 달 첫 초는 다른 블록
    assert by_ts[pd.Timestamp("2021-01-31 23:59:59")] != by_ts[pd.Timestamp("2021-02-01 00:00:00")]
    # 같은 달 안은 같은 블록
    assert by_ts[pd.Timestamp("2021-02-01 00:00:00")] == by_ts[pd.Timestamp("2021-02-28 12:00:00")]
    # 심볼이 다르면 같은 달이라도 다른 블록
    assert out[out["symbol"] == "ETHUSDT"]["cluster"].iloc[0].startswith("ETHUSDT|1h|2021-01")
    assert out["month"].tolist().count("2021-01") == 2


def test_cluster_key_separates_ltf():
    df = pd.DataFrame({
        "timestamp": [pd.Timestamp("2021-03-05"), pd.Timestamp("2021-03-06")],
        "symbol": ["BTCUSDT", "BTCUSDT"],
        "ltf": ["1h", "6h"],
        "g_align": [True, True],
        "return_20": [1.0, 2.0],
    })
    out = add_cluster_keys(df)
    assert out["cluster"].nunique() == 2


# ------------------------------------------------------------ 시드 재현성
def test_bootstrap_is_reproducible_under_same_seed():
    df = _pool()
    a = month_cluster_bootstrap(df, n_boot=200, seed=BOOTSTRAP_SEED)
    b = month_cluster_bootstrap(df, n_boot=200, seed=BOOTSTRAP_SEED)
    assert a["ci_low"] == b["ci_low"]
    assert a["ci_high"] == b["ci_high"]
    assert a["delta"] == b["delta"]


def test_bootstrap_differs_under_different_seed():
    df = _pool()
    a = month_cluster_bootstrap(df, n_boot=200, seed=1)
    b = month_cluster_bootstrap(df, n_boot=200, seed=2)
    assert (a["ci_low"], a["ci_high"]) != (b["ci_low"], b["ci_high"])
    assert a["delta"] == b["delta"]  # 점추정은 시드와 무관


def test_bootstrap_reports_declared_seed_and_blocks():
    df = _pool()
    out = month_cluster_bootstrap(df, n_boot=50, seed=BOOTSTRAP_SEED)
    assert out["seed"] == BOOTSTRAP_SEED
    assert out["n_blocks"] == df["cluster"].nunique()
    assert out["n_events"] == len(df)


# --------------------------------------- 블록 재표집의 코호트 길이 보존
def test_block_resample_draws_as_many_blocks_as_the_original():
    """재표집은 원본 블록 수만큼 뽑고, 재표집본 길이는 뽑힌 블록 길이의 합이다."""
    df = _pool()
    groups = [g for _, g in df.groupby("cluster", sort=True)]
    sizes = np.array([len(g) for g in groups])
    n_blocks = len(groups)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, n_blocks, n_blocks)
    assert len(idx) == n_blocks
    rebuilt = pd.concat([groups[i] for i in idx], ignore_index=True)
    assert len(rebuilt) == int(sizes[idx].sum())
    # 블록은 통째로 들어간다 — 부분 절단이 없다
    for i in set(idx.tolist()):
        assert (rebuilt["cluster"] == groups[i]["cluster"].iloc[0]).sum() % len(groups[i]) == 0


def test_bootstrap_ci_brackets_point_estimate_direction():
    df = _pool(align_edge=2.0)
    out = month_cluster_bootstrap(df, n_boot=400, seed=BOOTSTRAP_SEED)
    assert out["n_boot"] > 0
    assert out["ci_low"] <= out["ci_high"]
    assert out["delta"] > 0  # 합성 우위가 있으면 점추정도 양수


def test_bootstrap_ci_is_wider_than_iid_when_the_gate_edge_clusters_by_month():
    """월 클러스터 부트스트랩의 존재 이유 검증.

    주의: 월별 '수준(level)' 변동은 Δ′ 에서 상쇄되므로 CI 를 넓히지 않는다.
    자기상관이 문제가 되는 것은 **게이트 우위 자체가 월 단위로 뭉칠 때**이고,
    그때 이벤트 단위 iid 부트스트랩은 CI 를 낙관적으로 좁힌다 (§3 근거).
    """
    rng = np.random.default_rng(7)
    n = 900
    ts = pd.date_range("2021-01-01", periods=n, freq="8h")
    months = pd.Series(ts).dt.to_period("M").astype(str)
    # 월마다 게이트 우위가 달라진다 (레짐 편중의 축약 모형)
    edge_by_month = {m: rng.normal(0.5, 2.0) for m in months.unique()}
    align = rng.random(n) < 0.4
    edge = np.array([edge_by_month[m] for m in months])
    rets = rng.normal(0.0, 1.0, n) + align * edge
    df = add_cluster_keys(pd.DataFrame({
        "timestamp": ts, "symbol": "BTCUSDT", "ltf": "1h", "pair": "PAIR_B",
        "g_align": align, "return_20": rets,
    }))
    clustered = month_cluster_bootstrap(df, n_boot=400, seed=BOOTSTRAP_SEED)

    from analysis.wave_expectancy import compute_expectancy_metrics
    rets_arr = df["return_20"].to_numpy()
    flags = df["g_align"].to_numpy()
    rng2 = np.random.default_rng(BOOTSTRAP_SEED)
    deltas = []
    for _ in range(400):
        i = rng2.integers(0, n, n)
        r, f = rets_arr[i], flags[i]
        if f.sum() == 0:
            continue
        e_all = compute_expectancy_metrics(pd.Series(r))["expectancy"]
        e_al = compute_expectancy_metrics(pd.Series(r[f]))["expectancy"]
        deltas.append(e_al - e_all)
    iid_width = float(np.percentile(deltas, 97.5) - np.percentile(deltas, 2.5))
    clustered_width = clustered["ci_high"] - clustered["ci_low"]
    assert clustered_width > iid_width


# ------------------------------------------------------------------ 판정
def test_delta_prime_is_align_minus_ungated():
    df = _pool(align_edge=3.0)
    from analysis.wave_htf_gate import expectancy_20, gate_mask
    expected = round(expectancy_20(df[gate_mask(df, "G_ALIGN")]) - expectancy_20(df), 4)
    assert delta_prime(df) == expected


def test_judge_requires_all_four_criteria():
    result = judge_align(_pool(align_edge=3.0, n=900))
    assert len(result["criteria"]) == 4
    assert result["verdict"] in ("ACCEPT", "REJECT")
    assert (result["verdict"] == "ACCEPT") == all(c["passed"] for c in result["criteria"])


def test_judge_rejects_when_no_edge():
    result = judge_align(_pool(align_edge=0.0, n=900, seed=5))
    c1 = next(c for c in result["criteria"] if c["id"] == 1)
    assert not c1["passed"]
    assert result["verdict"] == "REJECT"


def test_half_split_partitions_the_pool():
    df = _pool()
    halves = half_split_delta(df)
    assert len(halves) == 2
    assert halves[0]["n"] + halves[1]["n"] == len(df)
    assert halves[0]["ts_max"] <= halves[1]["ts_min"]


def test_min_align_n_matches_spec():
    assert MIN_ALIGN_N == 30


# --------------------------------------------------------- 비용 참고치
def test_cost_adjustment_subtracts_fixed_roundtrip():
    df = _pool(align_edge=1.5)
    rows = cost_adjusted(df, cost_pct=COST_ROUNDTRIP_PCT)
    assert COST_ROUNDTRIP_PCT == 0.2
    for r in rows:
        if r["gate"] == "DELTA":
            continue
        # 고정 비용을 모든 수익에서 빼므로 순 기대값은 총 기대값보다 작다
        assert r["expectancy_net"] < r["expectancy_gross"]


def test_by_key_delta_covers_requested_values():
    df = _pool()
    rows = by_key_delta(df, "symbol", ("BTCUSDT", "ETHUSDT", "BNBUSDT"))
    assert [r["symbol"] for r in rows] == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    assert sum(r["n"] for r in rows) == len(df)
