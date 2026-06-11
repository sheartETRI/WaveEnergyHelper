# analysis/dynamics_rules.py
"""실전 역학관계 공식 엔진 1단계 — §6-①② (추세 매매 공식 F6-1a~1d, F6-2a~2d).

판정표(RULE_TABLE)를 코드 분기가 아니라 '데이터'로 선언한다. 감사·확장이 쉽도록.
검출기(스토캐스틱/이평선 패턴)는 수정하지 않고 '소비만' 한다.

확정 규칙 대응(파동에너지_공식_정리.md):
  전제 R-UP   : MA120 > MA240 (상승 레짐)
  전제 R-DOWN : MA120 < MA240 (하락 레짐)
판정·존은 CORE_MA_PERIODS 체계(MA20/60/120/240)만 사용한다. 40·80은 사용 금지.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Union

import pandas as pd

from analysis.structure import classify_structure_at
from config.settings import WAVE_ENERGY_PARAMS, WAVE_LAYER_ROLES
from indicators.ma_dispersion import (
    classify_dispersion_type,
    compute_ma_dispersion_series,
    dispersion_percentile_rank,
)


# (레짐, 캔들존, 파동층, 패턴종류, kind) -> (rule_id, 유효여부)
# kind=None 은 "kind 무관" 와일드카드. ("EQ"는 이론 미정의이므로 매칭에서 제외된다.)
RULE_TABLE = [
    ("UP",   "ABOVE_MA20",     "small", "db", None, "F6-1a", True),
    ("UP",   "MA20_MA60_BAND", "small", "db", "LL", "F6-1b", False),
    ("UP",   "MA20_MA60_BAND", "small", "db", "HL", "F6-1c", True),
    ("UP",   "MA20_MA60_BAND", "mid",   "db", None, "F6-1d", True),
    ("DOWN", "BELOW_MA20",     "small", "dt", None, "F6-2a", True),
    ("DOWN", "MA20_MA60_BAND", "small", "dt", "HH", "F6-2b", False),
    ("DOWN", "MA20_MA60_BAND", "small", "dt", "LH", "F6-2c", True),
    ("DOWN", "MA20_MA60_BAND", "mid",   "dt", None, "F6-2d", True),
]


@dataclass
class RuleHit:
    rule_id: str
    layer: str                  # "small" / "mid"
    pattern: str                # "db" / "dt"
    kind: Optional[str]         # "HL"/"LL"/"HH"/"LH"
    allowed: bool               # True=가능, False=불가
    bar_index: object           # 패턴 확정 봉의 인덱스(타임스탬프)
    description: str


@dataclass
class TransitionHit:
    """변곡점 추세전환(§6-④⑤) 복합 패턴 hit."""
    rule_id: str                # "F6-4b" 등
    structure: str              # "U1".."U3" / "D1".."D3"
    bullish: bool               # True=상방 전환, False=하방 전환
    bar_index: object           # 완성 봉(짝의 늦은 확정 봉)
    description: str
    formation_bar: object       # 형성 봉(짝의 이른 확정 봉) — 구조 판정 시점
    structure_label: str        # 형성 봉에서의 classify_structure_at 라벨
    signal_bars: List[tuple] = field(default_factory=list)  # [(원자 설명, 확정 봉), ...]
    dispersion_pct: Optional[float] = None   # 형성 봉 ma_dispersion 전역 rank 백분위 (표기 전용)
    dispersion_type: Optional[str] = None      # 응축형/과이격형/중간 (표기 전용)


@dataclass
class AtomTrace:
    """trace_transitions용 조건 원자 관측 결과."""
    atom: str                       # 원자 표기 (_atom_kr)
    satisfied: bool
    confirm_bars: List[object] = field(default_factory=list)   # 윈도 내 충족(확정+kind 일치) 봉
    last_outside_bar: Optional[object] = None                  # 윈도 밖 최근 충족 봉(있으면)
    block_reason: Optional[str] = None                         # ATOM_MISSING/WINDOW_BLOCKED/KIND_MISMATCH/None
    pivot_pos_missing: bool = False                            # first_pos 결측으로 확정봉 폴백 사용


@dataclass
class RuleTrace:
    """trace_transitions용 TRANSITION_RULE_TABLE 한 행의 관측 결과."""
    rule_id: str
    atoms: List[AtomTrace]
    completion_bar: Optional[object]
    formation_bar: Optional[object]
    structure_required: str
    structure_actual: Optional[str]
    result: str                     # "HIT" / 차단 게이트 라벨
    dispersion_pct: Optional[float] = None   # HIT 시 형성 봉 백분위 (표기 전용)
    dispersion_type: Optional[str] = None    # HIT 시 응축형/과이격형/중간


@dataclass
class DynamicsReport:
    regime: str                 # "UP" / "DOWN" / "판단불가"
    candle_zone: str            # "ABOVE_MA20" / "BELOW_MA20" / "MA20_MA60_BAND" / "OUT_OF_SCOPE" / "판단불가"
    hits: List[RuleHit] = field(default_factory=list)
    headline: Optional[Union[RuleHit, TransitionHit]] = None
    notes: List[str] = field(default_factory=list)
    transition_hits: List[TransitionHit] = field(default_factory=list)


def evaluate_rule(regime: str, zone: str, layer: str, pattern: str, kind: Optional[str]):
    """순수 함수: (regime, zone, layer, pattern, kind) -> (rule_id, allowed) 또는 None.

    - kind=None 인 테이블 항목은 와일드카드(kind 무관)다.
    - 입력 kind="EQ"는 이론 미정의이므로 항상 None을 반환한다(와일드카드에도 매칭 금지).
    - RULE_TABLE에 없는 조합은 None (임의 보간 금지).
    """
    if kind == "EQ":
        return None
    for r, z, lay, pat, k, rule_id, allowed in RULE_TABLE:
        if r == regime and z == zone and lay == layer and pat == pattern and (k is None or k == kind):
            return rule_id, allowed
    return None


def _regime_at(row: pd.Series) -> str:
    ma120 = row.get("MA120")
    ma240 = row.get("MA240")
    if ma120 is None or ma240 is None or pd.isna(ma120) or pd.isna(ma240):
        return "판단불가"
    if ma120 > ma240:
        return "UP"
    if ma120 < ma240:
        return "DOWN"
    return "판단불가"  # 동치는 레짐 미형성


def _zone_at(regime: str, close, ma20, ma60) -> str:
    if any(v is None or pd.isna(v) for v in (close, ma20, ma60)):
        return "판단불가"
    if regime == "UP":
        if close > ma20:
            return "ABOVE_MA20"
        if close > ma60:          # MA60 < close <= MA20 (경계 close==MA20 은 BAND)
            return "MA20_MA60_BAND"
        return "OUT_OF_SCOPE"     # close <= MA60
    if regime == "DOWN":
        if close < ma20:
            return "BELOW_MA20"
        if close < ma60:          # MA20 <= close < MA60 (경계 close==MA20 은 BAND)
            return "MA20_MA60_BAND"
        return "OUT_OF_SCOPE"     # close >= MA60
    return "판단불가"


_ZONE_KR = {
    "ABOVE_MA20": "MA20 위",
    "BELOW_MA20": "MA20 아래",
    "MA20_MA60_BAND": "MA20~60 구간",
    "OUT_OF_SCOPE": "범위 밖",
}


def _describe(layer: str, pattern: str, kind: Optional[str], zone: str, allowed: bool) -> str:
    layer_kr = "중파동" if layer == "mid" else "소파동"
    pat_kr = "쌍바닥" if pattern == "db" else "쌍봉"
    kind_part = f"{kind} " if kind else ""
    zone_kr = _ZONE_KR.get(zone, zone)
    dir_kr = "상승" if pattern == "db" else "하락"
    allow_kr = "가능" if allowed else "불가"
    return f"{layer_kr} {kind_part}{pat_kr} @ {zone_kr} → {dir_kr} {allow_kr}"


def _select_headline(hits: List[RuleHit], notes: List[str]) -> Optional[RuleHit]:
    """우선순위: ① mid > small (힘의 위계 [F1-b]) ② 더 최근 확정 봉 ③ 충돌 시 불가 우선."""
    if not hits:
        return None
    mids = [h for h in hits if h.layer == "mid"]
    pool = mids if mids else hits

    latest = sorted(pool, key=lambda h: h.bar_index)[-1]
    same = [h for h in pool if h.bar_index == latest.bar_index and h.layer == latest.layer]
    if len({h.allowed for h in same}) > 1:
        notes.append("동일 봉·층에서 가능/불가 충돌 — 불가 우선")
        latest = next(h for h in same if not h.allowed)
    return latest


# ----------------------------------------------------------------------------
# §6-④⑤ 변곡점 추세전환 — 복합 조건 테이블 (①② RULE_TABLE과 별도, AND 결합)
# ----------------------------------------------------------------------------

def wave(layer: str, pattern: str, kind: Optional[str] = None) -> dict:
    """파동(스토캐스틱) 조건 원자. layer=small/mid/large, pattern=db/dt/tb/tt."""
    return {"src": "wave", "layer": layer, "pattern": pattern, "kind": kind}


def ma(period: int, pattern: str, kind: Optional[str] = None) -> dict:
    """이평선 조건 원자. period=5/10, pattern=db/dt."""
    return {"src": "ma", "period": period, "pattern": pattern, "kind": kind}


# (구조 라벨, [조건 원자 AND...], rule_id, bullish)  bullish: True=상방 전환 / False=하방 전환
# 8행이 전부다 (파동에너지_공식_정리.md §6-④⑤와 1:1). 임의 보간 금지.
# 근사: 이론 원문은 대파동의 '깔끔한' LH/HL 쌍봉/쌍바닥을 요구하지만 깔끔함 판정([F7-a])이
#       미구현이라 kind="LH"/"HL"로 근사한다.
# TODO: 방어 조건(대파동 쌍봉을 막는 중파동 쌍바닥 등)은 다음 라운드. 여기서는 미구현.
_MA_TRANS_WINDOW = WAVE_ENERGY_PARAMS["transition_recent_bars_ma"]

# 선택 필드 window: 없으면 transition_recent_bars(24). MA 원자 4행만 transition_recent_bars_ma(96).
TRANSITION_RULE_TABLE = [
    ("U1", [wave("mid", "dt"),  wave("small", "tt")],          "F6-4a",   False),
    ("U2", [wave("large", "dt"), wave("mid", "tt")],           "F6-4b",   False),
    ("U3", [ma(5, "dt"),         wave("large", "tt")],         "F6-4c-a", False, _MA_TRANS_WINDOW),
    # F6-4c-b: 하락 다이버전스. 대파동 LH는 '깔끔함' 근사.
    ("U3", [ma(10, "dt", "HH"),  wave("large", "dt", "LH")],   "F6-4c-b", False, _MA_TRANS_WINDOW),  # TODO: 깔끔함 판정 도입 시 강화 (F7-a)
    ("D1", [wave("mid", "db"),  wave("small", "tb")],          "F6-5a",   True),
    ("D2", [wave("large", "db"), wave("mid", "tb")],           "F6-5b",   True),
    ("D3", [ma(5, "db"),         wave("large", "tb")],         "F6-5c-a", True, _MA_TRANS_WINDOW),
    # F6-5c-b: 상승 다이버전스. 대파동 HL은 '깔끔함' 근사.
    ("D3", [ma(10, "db", "LL"),  wave("large", "db", "HL")],   "F6-5c-b", True, _MA_TRANS_WINDOW),   # TODO: 깔끔함 판정 도입 시 강화 (F7-a)
]


def parse_transition_row(row):
    """(structure, atoms, rule_id, bullish[, window]) -> 5-tuple."""
    if len(row) == 5:
        return row[0], row[1], row[2], row[3], int(row[4])
    if len(row) == 4:
        return row[0], row[1], row[2], row[3], int(WAVE_ENERGY_PARAMS["transition_recent_bars"])
    raise ValueError(f"invalid TRANSITION_RULE_TABLE row: {row!r}")


_LAYER_KR = {"small": "소파동", "mid": "중파동", "large": "대파동"}
_PATTERN_KR = {"db": "쌍바닥", "dt": "쌍봉", "tb": "쓰리바닥", "tt": "쓰리봉"}


def _atom_columns(atom: dict) -> tuple:
    """조건 원자 -> (신호 컬럼, kind 컬럼)."""
    if atom["src"] == "wave":
        suffix = WAVE_LAYER_ROLES[atom["layer"]]
        return f"stoch_{atom['pattern']}_{suffix}", f"stoch_{atom['pattern']}_kind_{suffix}"
    return f"ma{atom['period']}_{atom['pattern']}", f"ma{atom['period']}_{atom['pattern']}_kind"


def _atom_first_pos_column(atom: dict) -> str:
    """조건 원자 -> 첫 피봇 위치(iloc) 기록 컬럼."""
    if atom["src"] == "wave":
        suffix = WAVE_LAYER_ROLES[atom["layer"]]
        return f"stoch_{atom['pattern']}_first_pos_{suffix}"
    return f"ma{atom['period']}_{atom['pattern']}_first_pos"


def _atom_pivot_pos_at_confirm(df: pd.DataFrame, confirm_ts, atom: dict) -> tuple:
    """확정 봉의 first_pos(첫 피봇 iloc). 결측 시 (확정봉 pos, True) 폴백."""
    confirm_pos = int(df.index.get_loc(confirm_ts))
    first_pos_col = _atom_first_pos_column(atom)
    if first_pos_col not in df.columns:
        return confirm_pos, True
    raw = df.loc[confirm_ts, first_pos_col]
    if raw is None or pd.isna(raw):
        return confirm_pos, True
    return int(raw), False


def pair_formation_completion(df: pd.DataFrame, atoms: list, a_confirm_pos: int, b_confirm_pos: int) -> tuple:
    """짝의 형성(피봇 min)·완성(max 확정) 위치와 피봇 폴백 여부."""
    a_ts = df.index[a_confirm_pos]
    b_ts = df.index[b_confirm_pos]
    a_pivot, a_fb = _atom_pivot_pos_at_confirm(df, a_ts, atoms[0])
    b_pivot, b_fb = _atom_pivot_pos_at_confirm(df, b_ts, atoms[1])
    form_pos = min(a_pivot, b_pivot)
    comp_pos = max(a_confirm_pos, b_confirm_pos)
    return form_pos, comp_pos, a_fb or b_fb


def _atom_kr(atom: dict) -> str:
    if atom["src"] == "wave":
        base = f"{_LAYER_KR[atom['layer']]} {_PATTERN_KR[atom['pattern']]}"
    else:
        base = f"MA{atom['period']} {_PATTERN_KR[atom['pattern']]}"
    return f"{base}({atom['kind']})" if atom["kind"] else base


def _atom_confirm_bars(df: pd.DataFrame, window_index, atom: dict) -> list:
    """윈도 내에서 원자가 충족(확정 notna, kind 지정 시 일치)되는 봉 목록."""
    sig_col, kind_col = _atom_columns(atom)
    if sig_col not in df.columns:
        return []
    sub = df.loc[df.index.isin(window_index) & df[sig_col].notna()]
    bars = []
    for ts, row in sub.iterrows():
        if atom["kind"] is not None:
            value = row.get(kind_col) if kind_col in df.columns else None
            if value is None or pd.isna(value) or str(value) != atom["kind"]:
                continue
        bars.append(ts)
    return bars


def _fmt_bar_short(ts) -> str:
    try:
        return ts.strftime("%m-%d")
    except (AttributeError, ValueError):
        return str(ts)


def enumerate_transition_pairs(df: pd.DataFrame, atoms: list, window_bars: int) -> list:
    """윈도 내 원자 확정 봉 짝 (a,b). formation=min(첫 피봇), completion=max(확정), |확정|<=window-1."""
    recent = max(int(window_bars), 1)
    window_index = set(df.tail(recent).index)
    a_bars = _atom_confirm_bars(df, window_index, atoms[0])
    b_bars = _atom_confirm_bars(df, window_index, atoms[1])
    pairs = []
    for a_ts in a_bars:
        a_pos = int(df.index.get_loc(a_ts))
        for b_ts in b_bars:
            b_pos = int(df.index.get_loc(b_ts))
            if abs(a_pos - b_pos) <= recent - 1:
                form_pos, comp_pos, pivot_fallback = pair_formation_completion(
                    df, atoms, a_pos, b_pos,
                )
                pairs.append({
                    "a_bar": a_ts,
                    "b_bar": b_ts,
                    "formation_bar": df.index[form_pos],
                    "completion_bar": df.index[comp_pos],
                    "formation_pos": form_pos,
                    "completion_pos": comp_pos,
                    "structure_label": classify_structure_at(df, form_pos),
                    "pivot_fallback": pivot_fallback,
                })
    return pairs


def _select_hit_pair(pairs: list, structure: str):
    """구조 일치 짝 중 completion_bar가 가장 최근인 대표 사건."""
    matching = [p for p in pairs if p["structure_label"] == structure]
    if not matching:
        return None
    return max(matching, key=lambda p: p["completion_bar"])


def _ensure_ma_dispersion(df: pd.DataFrame) -> pd.DataFrame:
    """ma_dispersion 컬럼이 없으면 내부 계산 (스토캐스틱 폴백과 동일 패턴, 표시 체크박스 무관)."""
    if "ma_dispersion" in df.columns:
        return df
    out = df.copy()
    out["ma_dispersion"] = compute_ma_dispersion_series(out)
    return out


def _annotate_formation_dispersion(df: pd.DataFrame, formation_bar) -> tuple[Optional[float], Optional[str]]:
    """형성 봉 이격도 백분위·유형 주석 (hit 선정과 무관, 표기 전용)."""
    work = _ensure_ma_dispersion(df)
    if formation_bar not in work.index:
        return None, None
    pos = int(work.index.get_loc(formation_bar))
    pct = dispersion_percentile_rank(work, pos)
    return pct, classify_dispersion_type(pct)


def evaluate_transitions(df: pd.DataFrame) -> List[TransitionHit]:
    """변곡점 전환 복합 패턴을 평가한다.

    - 조건은 AND 결합. 각 원자는 행별 window 내 확정 신호(+kind)가 1개 이상이면 충족.
    - 짝 (bar_a, bar_b): formation_bar=min(첫 피봇), completion_bar=max(확정).
    - 구조는 formation_bar(첫 피봇)에서 classify_structure_at으로 평가.
    - 복수 짝: 구조 일치 짝이 하나라도 있으면 hit; 대표는 completion_bar 최근.
    """
    if df is None or df.empty:
        return []

    hits: List[TransitionHit] = []
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        recent = max(int(window), 1)
        window_index = set(df.tail(recent).index)
        atom_bars = [_atom_confirm_bars(df, window_index, atom) for atom in atoms]
        if any(len(bars) == 0 for bars in atom_bars):
            continue

        pairs = enumerate_transition_pairs(df, atoms, window)
        best = _select_hit_pair(pairs, structure)
        if best is None:
            continue

        signal_bars = [(_atom_kr(atoms[0]), best["a_bar"]), (_atom_kr(atoms[1]), best["b_bar"])]
        direction = "상방" if bullish else "하방"
        form_lbl = best["structure_label"]
        description = (
            f"형성 {_fmt_bar_short(best['formation_bar'])}({form_lbl}) "
            f"→ 완성 {_fmt_bar_short(best['completion_bar'])} → {direction} 전환 가능"
        )
        disp_pct, disp_type = _annotate_formation_dispersion(df, best["formation_bar"])
        hits.append(
            TransitionHit(
                rule_id=rule_id,
                structure=structure,
                bullish=bullish,
                bar_index=best["completion_bar"],
                description=description,
                formation_bar=best["formation_bar"],
                structure_label=form_lbl,
                signal_bars=signal_bars,
                dispersion_pct=disp_pct,
                dispersion_type=disp_type,
            )
        )
    return hits


def _atom_has_pivot_fallback(df: pd.DataFrame, confirm_bars: list, atom: dict) -> bool:
    """윈도 내 확정 봉 중 first_pos 결측이 하나라도 있으면 True."""
    for ts in confirm_bars:
        _, fb = _atom_pivot_pos_at_confirm(df, ts, atom)
        if fb:
            return True
    return False


def _atom_trace(df: pd.DataFrame, window_index: set, atom: dict) -> AtomTrace:
    """원자 1개의 충족/차단 상태를 관측한다 (evaluate_transitions를 변경하지 않는 순수 관측).

    게이트 우선순위: ATOM_MISSING > KIND_MISMATCH > WINDOW_BLOCKED > 충족.
    """
    sig_col, kind_col = _atom_columns(atom)
    label = _atom_kr(atom)

    if sig_col not in df.columns:
        return AtomTrace(label, False, [], None, "ATOM_MISSING")
    notna = df[df[sig_col].notna()]
    if notna.empty:
        return AtomTrace(label, False, [], None, "ATOM_MISSING")

    if atom["kind"] is not None:
        if kind_col in df.columns:
            kind_match = notna[notna[kind_col].astype(str) == atom["kind"]]
        else:
            kind_match = notna.iloc[0:0]
    else:
        kind_match = notna

    if kind_match.empty:
        # 신호는 있으나 요구 kind가 데이터 어디에도 없음
        return AtomTrace(label, False, [], None, "KIND_MISMATCH")

    in_window = [ts for ts in kind_match.index if ts in window_index]
    outside = [ts for ts in kind_match.index if ts not in window_index]
    last_outside = max(outside) if outside else None

    if in_window:
        pivot_missing = _atom_has_pivot_fallback(df, in_window, atom)
        return AtomTrace(label, True, in_window, last_outside, None, pivot_missing)
    return AtomTrace(label, False, [], last_outside, "WINDOW_BLOCKED")


def trace_transitions(df: pd.DataFrame) -> List[RuleTrace]:
    """TRANSITION_RULE_TABLE 8행 각각에 대해 충족/차단을 관측한다(리포트용).

    HIT 판정 경로는 evaluate_transitions와 동일해 결과가 일치한다. 이 함수는 부수효과가
    없으며 evaluate_transitions/evaluate_dynamics의 반환을 일절 바꾸지 않는다.
    """
    if df is None or df.empty:
        return []

    traces: List[RuleTrace] = []
    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        recent = max(int(window), 1)
        window_index = set(df.tail(recent).index)
        atom_traces = [_atom_trace(df, window_index, atom) for atom in atoms]
        blocking = next((at for at in atom_traces if not at.satisfied), None)
        if blocking is not None:
            result = f"{blocking.block_reason}:{blocking.atom}"
            traces.append(RuleTrace(rule_id, atom_traces, None, None, structure, None, result))
            continue

        pairs = enumerate_transition_pairs(df, atoms, window)
        best = _select_hit_pair(pairs, structure)
        if best is not None:
            disp_pct, disp_type = _annotate_formation_dispersion(df, best["formation_bar"])
            traces.append(RuleTrace(
                rule_id, atom_traces,
                best["completion_bar"], best["formation_bar"],
                structure, best["structure_label"], "HIT",
                dispersion_pct=disp_pct,
                dispersion_type=disp_type,
            ))
            continue

        if not pairs:
            traces.append(RuleTrace(rule_id, atom_traces, None, None, structure, None, "NOT_PAIRED"))
            continue

        dist = Counter(p["structure_label"] for p in pairs)
        dist_str = ",".join(f"{k}={v}" for k, v in sorted(dist.items(), key=lambda x: str(x[0])))
        traces.append(RuleTrace(
            rule_id, atom_traces, None, None, structure, None, f"STRUCTURE_MISMATCH:{dist_str}",
        ))
    return traces


def structure_distribution(df: pd.DataFrame) -> dict:
    """전체 봉에 대해 classify_structure_at을 돌려 라벨별 카운트(None 포함)를 반환한다."""
    counts = {"U1": 0, "U2": 0, "U3": 0, "D1": 0, "D2": 0, "D3": 0, None: 0}
    if df is None or df.empty:
        return counts
    for pos in range(len(df)):
        label = classify_structure_at(df, pos)
        counts[label] = counts.get(label, 0) + 1
    return counts


def evaluate_dynamics(df: pd.DataFrame) -> DynamicsReport:
    """확정 패턴 신호 각각을 그 봉의 레짐/존으로 평가해 RULE_TABLE과 대조한다.

    - 평가 시점: 마지막 봉이 아니라 '각 패턴 확정 봉'에서 레짐·존을 계산한다.
    - 후보(candidate) 신호는 이번 라운드에서 평가하지 않는다(확정만).
    """
    notes: List[str] = []
    if df is None or df.empty:
        return DynamicsReport("판단불가", "판단불가", [], None, ["데이터 없음"])

    recent = max(int(WAVE_ENERGY_PARAMS["db_recent_bars"]), 1)
    window = df.tail(recent)

    layers = {"small": WAVE_LAYER_ROLES["small"], "mid": WAVE_LAYER_ROLES["mid"]}
    patterns = {
        "db": ("stoch_db_", "stoch_db_kind_"),
        "dt": ("stoch_dt_", "stoch_dt_kind_"),
    }

    hits: List[RuleHit] = []
    for layer_name, suffix in layers.items():
        for pattern, (sig_prefix, kind_prefix) in patterns.items():
            sig_col = f"{sig_prefix}{suffix}"
            kind_col = f"{kind_prefix}{suffix}"
            if sig_col not in window.columns:
                continue
            confirmed = window[window[sig_col].notna()]
            for ts, row in confirmed.iterrows():
                regime = _regime_at(row)
                zone = _zone_at(regime, row.get("close"), row.get("MA20"), row.get("MA60"))
                raw_kind = row.get(kind_col) if kind_col in confirmed.columns else None
                kind = None if (raw_kind is None or pd.isna(raw_kind)) else str(raw_kind)

                if kind == "EQ":
                    notes.append(f"{layer_name} {pattern} EQ @ {ts}: kind 이론 미정의로 보류")
                    continue

                result = evaluate_rule(regime, zone, layer_name, pattern, kind)
                if result is None:
                    continue
                rule_id, allowed = result
                hits.append(
                    RuleHit(
                        rule_id=rule_id,
                        layer=layer_name,
                        pattern=pattern,
                        kind=kind,
                        allowed=allowed,
                        bar_index=ts,
                        description=_describe(layer_name, pattern, kind, zone, allowed),
                    )
                )

    transition_hits = evaluate_transitions(df)

    last = df.iloc[-1]
    report_regime = _regime_at(last)
    report_zone = _zone_at(report_regime, last.get("close"), last.get("MA20"), last.get("MA60"))

    # headline 우선순위: 추세 전환 신호(④⑤) > 추세 내 매매 신호(①②).
    # transition이 있으면 완성 봉 최근 순으로 headline. 없으면 기존 trend headline 로직 불변.
    if transition_hits:
        headline = max(transition_hits, key=lambda h: h.bar_index)
    else:
        headline = _select_headline(hits, notes)

    return DynamicsReport(
        regime=report_regime,
        candle_zone=report_zone,
        hits=hits,
        headline=headline,
        notes=notes,
        transition_hits=transition_hits,
    )
