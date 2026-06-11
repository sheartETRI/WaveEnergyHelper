"""[F7-a] 깔끔함(clean) 관측용 판정 — 규칙 게이트 아님, 표기·관측 전용."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import CORE_MA_PERIODS, STOCH_LAYERS, WAVE_LAYER_ROLES


def atom_prev_opp_column(atom: dict) -> Optional[str]:
    """db/dt 원자의 prev_opp 컬럼명. tb/tt는 None."""
    pat = atom.get("pattern")
    if pat not in ("db", "dt"):
        return None
    if atom["src"] == "wave":
        suffix = WAVE_LAYER_ROLES[atom["layer"]]
        if pat == "db":
            return f"stoch_db_prev_opp_{suffix}"
        return f"stoch_dt_prev_opp_{suffix}"
    return f"ma{atom['period']}_{pat}_prev_opp"


def atom_neckline_column(atom: dict) -> Optional[str]:
    """스토캐스틱 db/dt 넥라인 컬럼. MA는 None(관측 시 재계산)."""
    pat = atom.get("pattern")
    if pat not in ("db", "dt") or atom["src"] != "wave":
        return None
    suffix = WAVE_LAYER_ROLES[atom["layer"]]
    if pat == "db":
        return f"stoch_neckline_{suffix}"
    return f"stoch_dt_neckline_{suffix}"


def ma_neckline_at_confirm(df: pd.DataFrame, period: int, pattern: str, confirm_pos: int) -> Optional[float]:
    """MA db/dt 확정 봉의 넥라인(M1/T1) 재계산 (기록 컬럼 없음)."""
    if pattern == "db":
        fp_col = f"ma{period}_db_first_pos"
        if fp_col not in df.columns:
            return None
        raw_fp = df.iloc[confirm_pos].get(fp_col)
        if raw_fp is None or pd.isna(raw_fp):
            return None
        fp = int(raw_fp)
        pl = df[f"ma{period}_pivot_low"]
        ph = df[f"ma{period}_pivot_high"]
        lows = [i for i in range(fp + 1, confirm_pos) if not pd.isna(pl.iloc[i])]
        if not lows:
            return None
        pb = lows[-1]
        highs = [i for i in range(fp + 1, pb) if not pd.isna(ph.iloc[i])]
        if not highs:
            return None
        return float(max(float(ph.iloc[i]) for i in highs))

    if pattern == "dt":
        fp_col = f"ma{period}_dt_first_pos"
        if fp_col not in df.columns:
            return None
        raw_fp = df.iloc[confirm_pos].get(fp_col)
        if raw_fp is None or pd.isna(raw_fp):
            return None
        fp = int(raw_fp)
        pl = df[f"ma{period}_pivot_low"]
        ph = df[f"ma{period}_pivot_high"]
        highs = [i for i in range(fp + 1, confirm_pos) if not pd.isna(ph.iloc[i])]
        if not highs:
            return None
        pb = highs[-1]
        lows = [i for i in range(fp + 1, pb) if not pd.isna(pl.iloc[i])]
        if not lows:
            return None
        return float(min(float(pl.iloc[i]) for i in lows))

    return None


def classify_clean(pattern: str, kind, neckline, prev_opp) -> str:
    """clean / not-clean / indeterminate (관측용)."""
    if kind is None or pd.isna(kind):
        return "indeterminate"
    if neckline is None or pd.isna(neckline):
        return "indeterminate"
    if prev_opp is None or pd.isna(prev_opp):
        return "indeterminate"

    nl = float(neckline)
    po = float(prev_opp)
    if pattern == "db":
        kind_ok = str(kind) == "HL"
        swing_ok = nl > po
    elif pattern == "dt":
        kind_ok = str(kind) == "LH"
        swing_ok = nl < po
    else:
        return "indeterminate"

    if kind_ok and swing_ok:
        return "clean"
    return "not-clean"


def atom_clean_at_confirm(df: pd.DataFrame, atom: dict, confirm_pos: int) -> dict:
    """원자 1개 확정 봉의 깔끔함 판정 결과."""
    pat = atom.get("pattern")
    if pat not in ("db", "dt"):
        return {"status": "n/a", "kind": None, "neckline": None, "prev_opp": None}

    from analysis.dynamics_rules import _atom_columns

    sig_col, kind_col = _atom_columns(atom)
    kind = df.iloc[confirm_pos].get(kind_col) if kind_col in df.columns else None

    prev_col = atom_prev_opp_column(atom)
    prev_opp = df.iloc[confirm_pos].get(prev_col) if prev_col and prev_col in df.columns else None

    nl_col = atom_neckline_column(atom)
    if nl_col and nl_col in df.columns:
        neckline = df.iloc[confirm_pos].get(nl_col)
    elif atom["src"] == "ma":
        neckline = ma_neckline_at_confirm(df, atom["period"], pat, confirm_pos)
    else:
        neckline = None

    status = classify_clean(pat, kind, neckline, prev_opp)
    return {
        "status": status,
        "kind": None if kind is None or pd.isna(kind) else str(kind),
        "neckline": None if neckline is None or pd.isna(neckline) else float(neckline),
        "prev_opp": None if prev_opp is None or pd.isna(prev_opp) else float(prev_opp),
    }


def iter_db_dt_confirmations(df: pd.DataFrame):
    """전역 db/dt 확정 봉 열거 (스토캐스틱 3레이어 + MA 코어 6)."""
    layer_map = {"Top": "large", "Mid": "mid", "Bot": "small"}
    for layer in STOCH_LAYERS:
        suffix = layer["label"]
        layer_name = layer_map[layer["name"]]
        for pat in ("db", "dt"):
            sig = f"stoch_db_{suffix}" if pat == "db" else f"stoch_dt_{suffix}"
            kind_col = f"stoch_db_kind_{suffix}" if pat == "db" else f"stoch_dt_kind_{suffix}"
            if sig not in df.columns:
                continue
            for pos in df.index[df[sig].notna()]:
                iloc = int(df.index.get_loc(pos))
                atom = {"src": "wave", "layer": layer_name, "pattern": pat}
                yield {
                    "detector": f"stoch_{layer['name']}_{pat}",
                    "pattern": pat,
                    "confirm_pos": iloc,
                    "confirm_ts": pos,
                    "kind": df.at[pos, kind_col] if kind_col in df.columns else None,
                    "atom": atom,
                }

    for n in CORE_MA_PERIODS:
        for pat in ("db", "dt"):
            sig = f"ma{n}_{pat}"
            kind_col = f"ma{n}_{pat}_kind"
            if sig not in df.columns:
                continue
            for pos in df.index[df[sig].notna()]:
                iloc = int(df.index.get_loc(pos))
                atom = {"src": "ma", "period": n, "pattern": pat}
                yield {
                    "detector": f"ma{n}_{pat}",
                    "pattern": pat,
                    "confirm_pos": iloc,
                    "confirm_ts": pos,
                    "kind": df.at[pos, kind_col] if kind_col in df.columns else None,
                    "atom": atom,
                }
