"""§5 네 팔의 프레임 선택 정책. 신호 규칙은 동일하고 이 파일만 다르다.

각 결정 시점 t에서 (a) 게이트 통과 프레임 집합과 (b) 그 점수가 주어졌을 때
어느 프레임을 '기준 차트'로 삼을지만 정한다. 신호 채택 여부는 backtest.py가
"그 시점 신호가 발생한 프레임 == 선택된 프레임"으로 판정한다.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.settings import TIMEFRAMES  # noqa: E402

from validation.keychart import params_v0 as P  # noqa: E402

FRAMES = list(TIMEFRAMES)
FRAME_INDEX = {f: i for i, f in enumerate(FRAMES)}
N_FRAMES = len(FRAMES)

ARMS = ("A", "B", "C1", "C2")
FIXED_FRAME_A = "1d"          # 현행 WAVE_ENERGY_PARAMS["trend_interval"] (읽기만 함)


def select_a() -> int:
    """A(현행): 1d 고정."""
    return FRAME_INDEX[FIXED_FRAME_A]


def select_b(gate_idx: np.ndarray, gate_score: np.ndarray) -> int:
    """B(영상): 게이트 통과 후보 중 KeyChartScore 1위.

    동점은 TIMEFRAMES 순서가 앞선 프레임(짧은 프레임)으로 결정적으로 깨뜨린다.
    gate_idx는 프레임 인덱스 오름차순이라 argmax가 그 규칙을 그대로 만족한다.
    """
    if gate_idx.size == 0:
        return -1
    return int(gate_idx[int(np.argmax(gate_score))])


def draws_c1(n_points: int, seeds: int, seed_base: int = P.SEED_BASE) -> np.ndarray:
    """C1(무차별 귀무): 19개 프레임 전체에서 균등 무작위. shape (n_points, seeds)."""
    rng = np.random.default_rng(seed_base + 1)
    return rng.integers(0, N_FRAMES, size=(n_points, seeds), dtype=np.int16)


def draws_c2(gate_sets: np.ndarray, gate_counts: np.ndarray, seeds: int,
             seed_base: int = P.SEED_BASE) -> np.ndarray:
    """C2(게이트 귀무): 게이트 통과 후보 중 균등 무작위. shape (n_points, seeds).

    gate_sets: (n_points, N_FRAMES) 패딩된 프레임 인덱스, gate_counts: 각 행의 유효 길이.
    통과 후보가 없는 시점은 -1을 돌려준다(그 시점에는 어떤 신호도 채택되지 않는다).
    """
    rng = np.random.default_rng(seed_base + 2)
    n = gate_sets.shape[0]
    out = np.full((n, seeds), -1, dtype=np.int16)
    if n == 0:
        return out
    counts = np.maximum(gate_counts, 1)
    picks = (rng.random((n, seeds)) * counts[:, None]).astype(np.int64)
    rows = np.arange(n)[:, None]
    chosen = gate_sets[rows, picks]
    out = np.where(gate_counts[:, None] > 0, chosen, -1).astype(np.int16)
    return out
