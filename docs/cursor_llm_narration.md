# AI 해설 (LLM Narration)

OpenAI 호환 HTTP 단일 경로로 LLM 해설을 생성한다. 프로바이더는 `config/settings.py`의 `NARRATION_CONFIG`만 변경하면 교체 가능하다.

## 기본 프로바이더 (Gemini 무료 티어)

| 항목 | 값 |
|---|---|
| base_url | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| model | `gemini-2.5-flash` |
| api_key_env | `GEMINI_API_KEY` |

공식 문서: [OpenAI compatibility \| Gemini API](https://ai.google.dev/gemini-api/docs/openai)

## API 키

`.env` 또는 환경변수 `GEMINI_API_KEY` (코드·리포 하드코딩 금지).

## 호출량 방어

- **옵트인**: 사이드바 "AI 해설" 체크(기본 해제). 해제 시 LLM·폴백·캐시 조회 없음
- **마스터 스위치** `NARRATION_CONFIG["enabled"]`: False면 체크박스 자체 숨김
- **봉 단위 캐시** (`narration/cache.py`): 동일 symbol·interval·마지막 봉 → 재호출 없음 (세션 내 재체크 포함)
- **429/RESOURCE_EXHAUSTED**: 재시도 없이 즉시 폴백 + "한도 도달 — 기본 요약 표시"

## 모듈

- `input_builder.py` — 판정·레이더 JSON
- `client.py` — OpenAI 호환 POST
- `validator.py` — 예측성 문구 차단
- `fallback.py` — 템플릿 요약
- `service.py` — 오케스트레이션

## 프로바이더 교체 예 (SGLang 로컬)

```python
NARRATION_CONFIG = {
    "enabled": True,
    "base_url": "http://127.0.0.1:30000/v1",
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "api_key_env": "OPENAI_API_KEY",
    ...
}
```
