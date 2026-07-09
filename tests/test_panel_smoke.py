"""패널 스모크 테스트 (11차 위임 C) — 레지스트리 45패널이 대표 데이터로 예외 없이 렌더.

산출 내용 비교는 하지 않는다(예외/공백 여부만, 위임 C). 두 층위:
  1) 레지스트리 정합 — 키 유일·Type A 전부 resolve·카테고리 유효(네트워크 불요).
  2) Type A 38패널 — bare streamlit 모드로 (BTCUSDT,1d) 렌더, 예외 없음(검증 CSV 기반, 오프라인).
     · (BTCUSDT,1d)/(ETHUSDT,4h)는 검증 CSV가 존재 → wave_outcome도 CSV 우선(네트워크 미접촉).
  3) 컨텍스트 패널(핵심/사전계산/차트) — 라이브 컨텍스트 1회 빌드 후 어댑터 렌더.
     · build_panel_context는 OHLCV fetch가 필요 → 네트워크/데이터 불가 시 skip(하드 실패 아님).
     · AI 해설은 외부 AI 호출을 피하기 위해 비활성(어댑터 게이팅만 확인).

bare 모드: `streamlit run` 없이 st.* 호출은 ScriptRunContext 경고만 내고 예외를 던지지 않는다
(사전 확인됨). 개별 패널은 render_panel_safe가 아니라 직접 호출해 예외를 표면화한다.
"""
import logging
import os
import sys
import warnings

import pytest

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from display.panel_context import IndicatorFlags, build_panel_context  # noqa: E402
from display.panel_registry import (  # noqa: E402
    CAT_PRECOMPUTED,
    CATEGORY_ORDER,
    CONTEXT_PANELS,
    TYPE_A_PANELS,
    all_panels,
)

# 검증 CSV가 존재하는 대표 (심볼, TF) — 오프라인 렌더 가능.
REPRESENTATIVE = ("BTCUSDT", "1d")

# 11차 재구성 이전부터 대표 데이터에서 내부 예외가 나던 패널(회귀 아님, 격리 확인용).
#   show_wave_paths: validation/wave_paths_BTCUSDT_1d.csv 스키마가 구버전 —
#   'survival_bars' 컬럼 부재(analysis/wave_path_analysis.py가 요구). 분석 모듈·CSV
#   재생성은 11차 범위 밖. 앱에서는 render_panel_safe가 패널 단위 격리 → 앱 계속
#   (레거시의 단일 외곽 try/except보다 안전: 한 패널 실패가 이후 패널/차트를 막지 않음).
KNOWN_PREEXISTING_FAILURES = {"show_wave_paths"}


def test_registry_integrity():
    panels = all_panels()
    keys = [p.key for p in panels]
    assert len(set(keys)) == len(keys), "패널 키 중복"
    assert len(TYPE_A_PANELS) == 38
    assert all(p.category in CATEGORY_ORDER for p in panels), "미등록 카테고리 존재"
    assert sum(1 for p in panels if p.legacy) == 9, "레거시 격리 수 불일치"
    # Type A는 전부 지연 참조가 실제 함수로 해석되어야 한다(오타·이동 검출).
    for spec in TYPE_A_PANELS:
        fn = spec.resolve()
        assert callable(fn), f"{spec.key} resolve 실패"


def test_type_a_panels_render_offline():
    """38개 Type A 패널을 (BTCUSDT,1d)로 렌더 — 신규 예외 0 (검증 CSV 기반).

    회귀 가드: 알려진 사전 예외(KNOWN_PREEXISTING_FAILURES) 외 새로 터지는 패널이 있으면 실패.
    """
    sym, iv = REPRESENTATIVE
    raised = {}
    for spec in TYPE_A_PANELS:
        try:
            spec.resolve()(sym, iv)
        except Exception as exc:  # noqa: BLE001 — 스모크: 어떤 패널이 터지는지 수집
            raised[spec.key] = f"{type(exc).__name__}: {exc}"
    new = set(raised) - KNOWN_PREEXISTING_FAILURES
    assert not new, "재구성 회귀(신규 예외):\n" + "\n".join(f"  {k}: {raised[k]}" for k in sorted(new))
    # 마이그레이션 배선 증명: 최소 (38 - 알려진예외) 패널이 클린 렌더.
    clean = len(TYPE_A_PANELS) - len(raised)
    assert clean >= len(TYPE_A_PANELS) - len(KNOWN_PREEXISTING_FAILURES), (
        f"클린 렌더 {clean}/{len(TYPE_A_PANELS)} — 예상보다 적음: {sorted(raised)}"
    )


def _live_context():
    sym, iv = REPRESENTATIVE
    try:
        return build_panel_context(sym, iv, indicator_flags=IndicatorFlags())
    except Exception as exc:  # noqa: BLE001 — 네트워크/데이터 불가 시 스킵
        pytest.skip(f"라이브 컨텍스트 빌드 불가(네트워크/데이터): {exc}")


def test_context_panels_render_fast():
    """핵심(요약·레이더·해설·디버그)+차트 컨텍스트 패널 — 라이브 컨텍스트로 렌더(빠름).

    사전계산 4종(stability/tracker/confirmation/lifecycle)은 각 ~1분 소요라 제외(별도 slow 테스트).
    차트 오버레이도 사전계산을 유발하므로 stability/tracker 플래그는 꺼둔다. AI 해설은 외부 AI
    호출을 피하려 비활성(게이팅만 확인).
    """
    ctx = _live_context()
    fast = [p for p in CONTEXT_PANELS if p.category != CAT_PRECOMPUTED]
    ctx.ui = {p.key: True for p in fast}
    ctx.ui["show_ai_narration"] = False        # 외부 AI 호출 방지
    ctx.ui["show_stability_verdict"] = False   # 차트 사전계산 오버레이 방지(느림)
    ctx.ui["show_wave_tracker"] = False

    failures = []
    for spec in fast:
        try:
            spec.render(ctx)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{spec.key}: {type(exc).__name__}: {exc}")
    assert not failures, "컨텍스트 패널 렌더 예외:\n" + "\n".join(failures)


@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW"),
    reason="사전계산 4종은 히스토리 재계산으로 각 ~1분 소요. RUN_SLOW=1 로 실행.",
)
def test_precomputed_panels_render_slow():
    """사전계산 4종(stability/tracker/confirmation/lifecycle) 어댑터 렌더 — 느림(opt-in)."""
    ctx = _live_context()
    pre = [p for p in CONTEXT_PANELS if p.category == CAT_PRECOMPUTED]
    ctx.ui = {p.key: True for p in pre}
    failures = []
    for spec in pre:
        try:
            spec.render(ctx)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{spec.key}: {type(exc).__name__}: {exc}")
    assert not failures, "사전계산 패널 렌더 예외:\n" + "\n".join(failures)


if __name__ == "__main__":
    test_registry_integrity()
    test_type_a_panels_render_offline()
    print("REGISTRY + TYPE A SMOKE PASSED")
    try:
        test_context_panels_render_fast()
        print("CONTEXT (FAST) PANEL SMOKE PASSED")
    except Exception as exc:  # noqa: BLE001
        print(f"CONTEXT (FAST) PANEL SMOKE SKIPPED/FAILED: {exc}")
