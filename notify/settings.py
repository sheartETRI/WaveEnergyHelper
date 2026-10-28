"""푸시 운영 기본값. 지표·연구 설정과 독립적으로 관리한다."""
from typing import Dict, Tuple

PUSH_TARGETS: Dict[str, Tuple[str, ...]] = {
    "symbols": ("BTCUSDT",),
    "intervals": ("1h", "2h", "4h", "6h", "12h", "1d", "2d"),
}

LEDGER_INTERVALS: Tuple[str, ...] = PUSH_TARGETS["intervals"]      # ledger 는 대상 7셀 전부

STATE_LEGACY_SUFFIX = ".legacy.json"

TITLE_PREFIX = "[WEH] "

STATE_VERSION = 1         # (예전 경로) 이력 파일 버전

SENT_KEEP = 5000          # (예전 경로) 이력 파일에 남기는 최근 키 수
