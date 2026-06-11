"""LLM·폴백용 구조화 입력 (사실 데이터만)."""
from __future__ import annotations

import json
from typing import Any, List, Optional

from display.transition_radar import TransitionRadarContent


def _dynamics_facts(dynamics) -> dict:
    if dynamics is None:
        return {"headline": None, "transition_hits": [], "rule_hits": []}
    transition_hits = getattr(dynamics, "transition_hits", []) or []
    hits = getattr(dynamics, "hits", []) or []
    head = getattr(dynamics, "headline", None)
    return {
        "headline": getattr(head, "description", None) if head else None,
        "transition_hits": [getattr(h, "description", str(h)) for h in transition_hits],
        "rule_hits": [getattr(h, "description", str(h)) for h in hits],
    }


def build_narration_context(
    report,
    alignment: str,
    radar: Optional[TransitionRadarContent],
) -> dict:
    """판정·레이더에서 추출한 사실 dict."""
    forming = []
    if radar and radar.forming_items:
        forming = [
            {"rule_id": item.rule_id, "headline": item.headline_html, "detail": item.detail}
            for item in radar.forming_items
        ]
    ctx = {
        "symbol": report.symbol,
        "interval": report.interval,
        "verdict": report.verdict,
        "ma_alignment": alignment,
        "mtf_agreement": report.mtf_agreement,
        "trend_1d": {
            "direction": report.trend.direction,
            "slope_pct": report.trend.slope_pct,
            "valid": report.trend.valid,
        },
        "base_large": {
            "direction": report.base_large.direction,
            "zone": report.base_large.zone,
            "double_bottom": report.base_large.double_bottom,
            "double_top": report.base_large.double_top,
        },
        "base_small": {
            "direction": report.base_small.direction,
            "zone": report.base_small.zone,
            "double_bottom": report.base_small.double_bottom,
            "double_top": report.base_small.double_top,
        },
        "dynamics": _dynamics_facts(report.dynamics),
        "radar": {
            "environment": radar.environment_line if radar else None,
            "forming": forming,
            "recent": radar.recent_caption if radar else None,
        },
        "notes": list(report.notes or []),
    }
    return ctx


def build_prompt_messages(context: dict) -> List[dict]:
    """OpenAI 호환 messages."""
    system = (
        "당신은 암호화폐 파동에너지 차트 해설가입니다. "
        "제공된 JSON 사실만 바탕으로 3~5문장 한국어 해설을 작성하세요. "
        "매매 권유·예측·확률·'임박' 같은 표현은 금지합니다. "
        "현재 상태(추세·파동·역학·변곡 레이더)를 중립적으로 서술하세요."
    )
    user = (
        "다음 분석 JSON을 해설하세요:\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
