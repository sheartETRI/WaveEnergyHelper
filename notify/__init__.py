"""알림 스캐너 (GitHub Actions 전용, 미검증 · 관측 알림).

검출 로직은 **재구현하지 않는다** — signal-alarm 브랜치의 표시 모듈을 내용 무변경으로 복사(체리픽)해
import 소비만 한다. 복사본은 CHERRYPICK 매니페스트(sha256, LF 정규화)로 고정하고 테스트가 원본 커밋 blob 과 대조한다.

- 60MA 전환: ``display.ma60_turn_tracker`` (→ ``validation.wave_ma60_turn_probe.extract_signals``)
- 60MA 하방 전환(거울상): ``display.ma60_down_tracker`` (→ 위 모듈 + probe 의 쌍봉 경로 ``stoch_tops``)
- 대파동 쌍바닥 후보·다이버전스: ``display.ma60_turn_tracker`` 후보 행 + ``display.divergence_flag`` (단일 정의, main 870f025)
- 구조 훼손(LL): ``display.trend_structure`` (→ ``analysis.wave_structure_confirmation`` swing 검출기)

이 패키지에 남는 것은 데이터 소스(스캐너 전용 fetch) · 닫힌 봉 절단 · 이벤트 키 · 중복 이력 · 메시지 · 전달뿐이다.
정의 파일·전방 추적 파일·data/binance.py 무접촉.
"""
from __future__ import annotations

# signal-alarm 9bb606c 에서 내용 무변경 복사. probe 는 main 26dfe9c 원본(양 브랜치 동일 blob).
# ma60_down_tracker 는 signal-alarm 68454ff, divergence_flag 는 signal-alarm 6e4a6d5 에서 내용 무변경 복사.
# (main 의 ma60_turn_tracker 는 9bb606c 판 그대로 — '다이버전스' 열은 signal-alarm 표시 전용이며 스캐너는 divergence_flag 를 직접 쓴다.)
CHERRYPICK_SOURCE_COMMIT = "9bb606c"
CHERRYPICK_SOURCE_COMMIT_DOWN = "68454ff"
CHERRYPICK_SOURCE_COMMIT_DIV = "6e4a6d5"
CHERRYPICK = {
    "display/divergence_flag.py": "30be19bfac1ba600596c0203220b82aac9e2b016bb16fb72b82872b176f4da8b",
    "display/ma60_down_tracker.py": "5a3f32d9a44ba615a16d8ba8cf1455b708debd674f842bdfdf2b5d2acd7ff098",
    "display/tz_label.py": "c117278221d732dfe0c65174d5b54dde9e72e38c8fcd1763c0f59d76b753ee50",
    "display/ma60_turn_tracker.py": "295e11ff421e2ee5608713f482ff391e13ff2d2d74d0964afb4d8e9a6b6a5def",
    "display/trend_structure.py": "88a516dca67c8028f220da7d3958f76968b42403231ab74b6cce829d7c97763d",
    "validation/wave_ma60_turn_probe.py": "95cc6bef99c280870b198ac87003ac7efcaa0cb2183fc606af2ea73560a8bc3d",
}
