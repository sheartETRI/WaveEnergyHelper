"""알림 스캐너 (GitHub Actions 전용, 미검증 · 관측 알림).

검출 로직은 **재구현하지 않는다** — signal-alarm 브랜치의 표시 모듈을 내용 무변경으로 복사(체리픽)해
import 소비만 한다. 복사본은 CHERRYPICK 매니페스트(sha256, LF 정규화)로 고정하고 테스트가 원본 커밋 blob 과 대조한다.

- 60MA 전환: ``display.ma60_turn_tracker`` (→ ``validation.wave_ma60_turn_probe.extract_signals``)
- 구조 훼손(LL): ``display.trend_structure`` (→ ``analysis.wave_structure_confirmation`` swing 검출기)

이 패키지에 남는 것은 데이터 소스(스캐너 전용 fetch) · 닫힌 봉 절단 · 이벤트 키 · 중복 이력 · 메시지 · 전달뿐이다.
정의 파일·전방 추적 파일·data/binance.py 무접촉.
"""
from __future__ import annotations

# signal-alarm 9bb606c 에서 내용 무변경 복사. probe 는 main 26dfe9c 원본(양 브랜치 동일 blob).
CHERRYPICK_SOURCE_COMMIT = "9bb606c"
CHERRYPICK = {
    "display/tz_label.py": "c117278221d732dfe0c65174d5b54dde9e72e38c8fcd1763c0f59d76b753ee50",
    "display/ma60_turn_tracker.py": "295e11ff421e2ee5608713f482ff391e13ff2d2d74d0964afb4d8e9a6b6a5def",
    "display/trend_structure.py": "88a516dca67c8028f220da7d3958f76968b42403231ab74b6cce829d7c97763d",
    "validation/wave_ma60_turn_probe.py": "95cc6bef99c280870b198ac87003ac7efcaa0cb2183fc606af2ea73560a8bc3d",
}
