"""LLM 불가 시 템플릿 요약."""
from __future__ import annotations


def build_fallback_summary(context: dict) -> str:
    """구조화 입력 → 기본 요약 (예측 없음)."""
    lines = [f"**{context.get('verdict', '판단불가')}**"]
    trend = context.get("trend_1d") or {}
    if trend.get("valid"):
        lines.append(
            f"일봉 60MA 추세 {trend.get('direction')} "
            f"({trend.get('slope_pct', 0):+.2f}%)."
        )
    bl = context.get("base_large") or {}
    bs = context.get("base_small") or {}
    lines.append(
        f"대파동 {bl.get('direction', '-')} · {bl.get('zone', '-')} / "
        f"소파동 {bs.get('direction', '-')} · {bs.get('zone', '-')}."
    )
    lines.append(f"MA 배열: {context.get('ma_alignment', '-')} · MTF {context.get('mtf_agreement', '-')}.")
    radar = context.get("radar") or {}
    if radar.get("environment"):
        lines.append(radar["environment"])
    forming = radar.get("forming") or []
    if forming:
        lines.append(f"변곡 형성 중 {len(forming)}건.")
    else:
        lines.append("변곡 형성 중인 패턴 없음.")
    if radar.get("recent"):
        lines.append(radar["recent"])
    dyn = context.get("dynamics") or {}
    if dyn.get("headline"):
        lines.append(f"역학: {dyn['headline']}")
    return "\n\n".join(lines)
