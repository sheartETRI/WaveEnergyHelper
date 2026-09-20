"""화면 시각 표기 — KST 변환 헬퍼 + 라벨 (표시 계층 공용).

원칙: **데이터·계산·기록은 naive UTC 그대로**(프레임 인덱스 = 바이낸스 open_time, 검출기 입력, 사이드카·저널).
변환은 렌더 직전 1회, 이 모듈의 ``to_kst`` 로만 한다. 한국은 DST 가 없으므로 고정 +9h 이며 tz 객체를 붙이지 않는다
(naive → naive; 어디에도 tz-aware 값이 흘러 들어가지 않는다).

- 차트(LW): 시간축 자체를 옮기지 않고 PAYLOAD 의 time 을 +9h 시프트한 뒤(LW 는 UTC 로 그림) 라벨을 KST 로 붙인다.
- 알람 탭·60MA 추적·사이드바: 표시용 문자열을 만들 때만 ``to_kst`` / ``kst_text``.
"""
from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

KST_LABEL = "(KST)"
KST_OFFSET = timedelta(hours=9)     # Asia/Seoul: DST 없음(1988년 이후) → 고정 오프셋

_TS_TEXT = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def to_kst(ts) -> pd.Timestamp:
    """naive UTC → naive KST (+9h). tz-aware 입력은 UTC 로 맞춘 뒤 같은 처리. NaT 는 NaT."""
    t = pd.Timestamp(ts)
    if pd.isna(t):
        return pd.NaT
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t + KST_OFFSET


def kst_text(text: str) -> str:
    """문자열 안의 'YYYY-MM-DD HH:MM'(UTC) 를 KST 로 치환 — 정의 계층이 만든 비고 문구 표시용."""
    if text is None:
        return text
    return _TS_TEXT.sub(lambda m: f"{to_kst(pd.Timestamp(m.group(0))):%Y-%m-%d %H:%M}", str(text))
