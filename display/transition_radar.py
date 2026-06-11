"""변곡 레이더 — trace/evaluate 결과의 표시 계층 재표현 (평가 로직 무수정)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from analysis.dynamics_rules import (
    TRANSITION_RULE_TABLE,
    AtomTrace,
    RuleTrace,
    _annotate_formation_dispersion,
    _atom_confirm_bars,
    _atom_pivot_pos_at_confirm,
    _fmt_bar_short,
    pair_formation_completion,
    parse_transition_row,
)
from analysis.structure import classify_structure_at

_DISPERSION_ZONE = {
    "응축형": "응축 구간",
    "과이격형": "과이격 구간",
    "중간": "중간",
}

_RULE_ROWS = {
    parse_transition_row(row)[2]: parse_transition_row(row)
    for row in TRANSITION_RULE_TABLE
}


@dataclass
class FormingItem:
    """형성 중(FORMING) 한 행의 표시 데이터."""
    rule_id: str
    headline_html: str
    detail: str
    structure_match: bool


@dataclass
class TransitionRadarContent:
    environment_line: Optional[str]
    forming_items: List[FormingItem]
    recent_caption: Optional[str]


def prepare_trace_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """trace_transitions에 필요한 패턴 컬럼을 보장한다 (표시 전용)."""
    trace_df = df
    if "ma5_db" not in trace_df.columns:
        from indicators.ma_patterns import add_ma_patterns

        trace_df = add_ma_patterns(trace_df)
    sample_suffix = "(20,10,10)"
    if f"stoch_k_{sample_suffix}" not in trace_df.columns:
        from indicators.stochastic import add_stochastic_slow_layers

        trace_df = add_stochastic_slow_layers(trace_df)
    return trace_df


def format_environment_line(df: pd.DataFrame) -> Optional[str]:
    """마지막 봉 이격도 백분위 + 구간. NaN이면 None."""
    if df is None or df.empty:
        return None
    last_ts = df.index[-1]
    pct, typ = _annotate_formation_dispersion(df, last_ts)
    if pct is None or typ is None:
        return None
    zone = _DISPERSION_ZONE.get(typ, typ)
    return f"변곡 환경: 이격도 P{int(round(pct))} · {zone}"


def is_forming_trace(tr: RuleTrace) -> bool:
    """원자 1개 충족 + 1개 미충족 (HIT 제외)."""
    if tr.result == "HIT" or len(tr.atoms) != 2:
        return False
    satisfied = sum(1 for at in tr.atoms if at.satisfied)
    return satisfied == 1


def _elapsed_bars(df: pd.DataFrame, confirm_ts) -> int:
    last_pos = len(df) - 1
    confirm_pos = int(df.index.get_loc(confirm_ts))
    return max(0, last_pos - confirm_pos)


def _structure_html(actual: Optional[str], required: str) -> tuple[str, bool]:
    if actual is None:
        return "", False
    if actual == required:
        return f"형성 피봇 구조 {actual} ✓", True
    return f'<span style="color:#888">형성 피봇 구조 {actual}</span>', False


def _formation_structure(
    df: pd.DataFrame,
    atom_dict: dict,
    atom_trace: AtomTrace,
    structure_required: str,
) -> tuple[str, bool]:
    if not atom_trace.confirm_bars:
        return "", False
    confirm_ts = max(atom_trace.confirm_bars)
    pivot_pos, _ = _atom_pivot_pos_at_confirm(df, confirm_ts, atom_dict)
    actual = classify_structure_at(df, pivot_pos)
    return _structure_html(actual, structure_required)


def build_forming_item(
    df: pd.DataFrame,
    tr: RuleTrace,
    structure: str,
    atoms: list,
    window: int,
) -> FormingItem:
    satisfied_idx = next(i for i, at in enumerate(tr.atoms) if at.satisfied)
    pending_idx = 1 - satisfied_idx
    sat_trace = tr.atoms[satisfied_idx]
    pend_trace = tr.atoms[pending_idx]
    sat_atom = atoms[satisfied_idx]

    confirm_ts = max(sat_trace.confirm_bars)
    date_str = _fmt_bar_short(confirm_ts)
    struct_html, struct_match = _formation_structure(
        df, sat_atom, sat_trace, structure,
    )
    struct_suffix = f", {struct_html}" if struct_html else ""
    satisfied_part = f"{sat_trace.atom} 확정({date_str}{struct_suffix})"

    elapsed = _elapsed_bars(df, confirm_ts)
    pending_part = (
        f"{pend_trace.atom} 대기 (윈도 {window}봉 중 {elapsed}봉 경과)"
    )

    headline = (
        f"🔶 변곡 형성 중 [{tr.rule_id}]: {satisfied_part}"
    )
    detail = f"   — {pending_part}"
    return FormingItem(tr.rule_id, headline, detail, struct_match)


def extract_forming_items(df: pd.DataFrame, traces: List[RuleTrace]) -> List[FormingItem]:
    """trace 8행 중 FORMING 행을 구조 일치 우선 정렬해 반환."""
    items: List[FormingItem] = []
    for tr in traces:
        if not is_forming_trace(tr):
            continue
        structure, atoms, _rule_id, _bullish, window = _RULE_ROWS[tr.rule_id]
        items.append(build_forming_item(df, tr, structure, atoms, window))
    items.sort(key=lambda x: (not x.structure_match, x.rule_id))
    return items


def find_most_recent_hit(df: pd.DataFrame) -> Optional[dict]:
    """로딩된 df 전체에서 가장 최 recent completion hit (윈도 밖 포함)."""
    if df is None or df.empty:
        return None

    best: Optional[dict] = None
    best_comp_pos = -1
    full_index = set(df.index)

    for row in TRANSITION_RULE_TABLE:
        structure, atoms, rule_id, bullish, window = parse_transition_row(row)
        recent = max(int(window), 1)
        a_bars = _atom_confirm_bars(df, full_index, atoms[0])
        b_bars = _atom_confirm_bars(df, full_index, atoms[1])
        for a_ts in a_bars:
            a_pos = int(df.index.get_loc(a_ts))
            for b_ts in b_bars:
                b_pos = int(df.index.get_loc(b_ts))
                if abs(a_pos - b_pos) > recent - 1:
                    continue
                form_pos, comp_pos, _ = pair_formation_completion(
                    df, atoms, a_pos, b_pos,
                )
                if classify_structure_at(df, form_pos) != structure:
                    continue
                if comp_pos <= best_comp_pos:
                    continue
                formation_bar = df.index[form_pos]
                completion_bar = df.index[comp_pos]
                disp_pct, disp_type = _annotate_formation_dispersion(df, formation_bar)
                best_comp_pos = comp_pos
                best = {
                    "rule_id": rule_id,
                    "bullish": bullish,
                    "completion_bar": completion_bar,
                    "dispersion_pct": disp_pct,
                    "dispersion_type": disp_type,
                    "comp_pos": comp_pos,
                }
    return best


def format_recent_hit_caption(df: pd.DataFrame, hit: Optional[dict]) -> Optional[str]:
    if hit is None or df is None or df.empty:
        return None
    last_pos = len(df) - 1
    bars_ago = last_pos - hit["comp_pos"]
    direction = "상방" if hit["bullish"] else "하방"
    comp_date = _fmt_bar_short(hit["completion_bar"])
    base = f"최근 변곡: [{hit['rule_id']}] {direction} · 완성 {comp_date} ({bars_ago}봉 전"
    disp_type = hit.get("dispersion_type")
    disp_pct = hit.get("dispersion_pct")
    if disp_type is not None and disp_pct is not None:
        return f"{base}, {disp_type} {disp_pct:.1f}%)"
    return f"{base})"


def build_transition_radar(
    df: pd.DataFrame,
    traces: List[RuleTrace],
) -> TransitionRadarContent:
    """레이더 섹션 전체 콘텐츠."""
    return TransitionRadarContent(
        environment_line=format_environment_line(df),
        forming_items=extract_forming_items(df, traces),
        recent_caption=format_recent_hit_caption(df, find_most_recent_hit(df)),
    )
