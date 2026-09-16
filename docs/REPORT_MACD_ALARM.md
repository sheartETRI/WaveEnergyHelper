# signal-alarm 브랜치 — MACD 알람·표시 추가 보고

작성 2026-09-17. 대상 브랜치 signal-alarm. main·v2-campaign·파동 연구 체인(analysis/wave_*, validation/) 무접촉.
MACD_PARAMS(12,26,9)·add_macd·기존 검출기 무수정. 권고형 문구·알림 발송 훅 없음(패널 내 표시까지).

## 1. 작업 1 — 수정 전 MACD 표시 현황

| 위치 | 수정 전 상태 | 이번 처리 |
|---|---|---|
| indicators/oscillators.py `add_macd` | macd·macd_signal·macd_hist·macd_hist_prev 4컬럼 기록 | 무수정, 읽기만 |
| charts/plotly_builder.py `add_macd_panel` | hist 막대(색 4단) + macd/signal 선 + 0선 이미 존재. 이벤트 마커 없음 | 패널 재구현 없음. `add_macd_event_markers` 병기 |
| charts/plotly_builder.py `_get_synced_chart_rows` | `show_macd` 플래그로 MACD 행 추가 가능 | 무수정 |
| main.py (슬림 앱) | `show_macd=False` 고정, `add_macd` 미호출 → 슬림 앱에서 MACD 미계산·미표시 | `add_macd` 추가, 사이드바 "MACD 패널" 토글(기본 켬) |
| display/detail_tab.py + panel_context.py (레거시 3탭) | MACD 체크박스·add_macd 호출 있음. 슬림 main.py에서 미도달 | 무수정 |
| analysis/alarm_signals.py | 스토캐·RSI만. MACD 종류 없음 | 4종 추가 |
| display/alarm_panel.py | 지표 이름을 `layer is None → "RSI"` 로 고정 | `AlarmSignal.metric_name` 으로 교체 |

## 2. 커밋

| 구분 | 해시 | 내용 |
|---|---|---|
| 알람 로직 | 98587e3 | KIND_MACD_GOLDEN/DEAD/ZERO_UP/ZERO_DOWN, `macd_event_positions`, `_macd_signals` |
| 표시 | f5f8c11 | alarm_panel 지표명, plotly_builder 이벤트 마커(GC/DC 원, 0↑/0↓ 마름모), main.py 연결 |
| 테스트 | 753233d | test_alarm_signals 8건 추가, test_slim_app_smoke 1건 추가·2건 보강 |

정의: 골든 `macd_hist_prev < 0 ≤ macd_hist`, 데드 `macd_hist_prev > 0 ≥ macd_hist`,
0선 상향/하향은 `macd` 의 shift(1) 부호 전이(이 레이어에서 추출). 직전 값 결측이면 전이 아님.
layer=None, value = 이벤트 봉의 macd_hist(크로스) / macd(0선), detail = 반대편 값(상태 기술). candidate 없음, 채터링 억제 없음.

## 3. 테스트

| 묶음 | 결과 |
|---|---|
| tests/test_alarm_signals.py | 19 passed (기존 11 + MACD 8) |
| tests/test_slim_app_smoke.py | 7 passed (기존 6 + 마커 1) |
| 기존 스토캐·RSI 테스트 | 무변경 전부 통과 |
| tests 전체 (test_context_panels_render_fast 제외) | 596 passed, 2 failed, 1 skipped (3분 42초). 실패 2건은 tests/test_wave_ruleset_robustness.py::test_walk_forward / test_robustness_score — 501a95d(수정 전) 워크트리에서도 동일 실패(AttributeError), 연구 체인 미접촉 |
| tests/test_panel_smoke.py::test_context_panels_render_fast | **수정 전부터 실패** — aeba3d3 에서 render_chart 의 show_stability 인자가 제거됐는데 display/panel_registry.py `_adapt_chart` 가 아직 넘김. 레거시 3탭 경로, 이번 범위 밖이라 미수정 |

MACD 테스트 항목: 교차 봉 정확히 1건(골든·데드), 0선 전이 각 1건, 무교차 구간 0건, 연속 재교차 시 교차마다 1건,
정확히 0 경계 1회, NaN 워밍업 무발화, 컬럼 누락 시 조용히 건너뜀, `macd_event_positions` 와 스캔 결과 일치,
실제 add_macd 파이프라인에서 4종 발생 + 각 이벤트 봉의 부호 전이 정의 검증 + 크로스 건수 == hist 부호 전이 수,
차트 마커 x·y 가 알람 봉·macd 값과 일치, 패널 끄면 마커 없음, 알람 줄에 권고형 문구 없음.

## 4. 관측 보고 — 최근 데이터 발생 빈도 (채터링 억제 없음, 파라미터 미발명)

적재: main.load_frame 과 동일 경로(fetch_klines auto limit). 15m/1h/4h 1000봉, 1d 500봉. 끝봉 2026-09-16.

### 4.1 심볼·TF별 건수

| 심볼 | TF | 봉수 | 기간(일) | GC | DC | 0↑ | 0↓ | 크로스/100봉 | 크로스 간격 중앙값(봉) | 인접 크로스 간격≤3봉 쌍 (비율) |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 15m | 1000 | 10.4 | 41 | 41 | 20 | 20 | 8.2 | 10 | 17 (21%) |
| BTC | 1h | 1000 | 41.6 | 38 | 38 | 20 | 21 | 7.6 | 11 | 13 (17%) |
| BTC | 4h | 1000 | 166.5 | 37 | 37 | 20 | 20 | 7.4 | 12 | 15 (21%) |
| BTC | 1d | 500 | 499 | 19 | 20 | 10 | 10 | 7.8 | 10 | 11 (29%) |
| ETH | 15m | 1000 | 10.4 | 36 | 35 | 22 | 21 | 7.1 | 12 | 9 (13%) |
| ETH | 1h | 1000 | 41.6 | 42 | 42 | 27 | 28 | 8.4 | 10 | 15 (18%) |
| ETH | 4h | 1000 | 166.5 | 41 | 41 | 17 | 17 | 8.2 | 10 | 20 (25%) |
| ETH | 1d | 500 | 499 | 17 | 17 | 7 | 6 | 6.8 | 13 | 7 (21%) |
| BNB | 15m | 1000 | 10.4 | 35 | 34 | 20 | 19 | 6.9 | 13 | 10 (15%) |
| BNB | 1h | 1000 | 41.6 | 35 | 35 | 18 | 19 | 7.0 | 11 | 11 (16%) |
| BNB | 4h | 1000 | 166.5 | 41 | 41 | 19 | 20 | 8.2 | 9 | 20 (25%) |
| BNB | 1d | 500 | 499 | 16 | 17 | 6 | 6 | 6.6 | 12.5 | 6 (19%) |
| SOL | 15m | 1000 | 10.4 | 43 | 42 | 22 | 21 | 8.5 | 10 | 19 (23%) |
| SOL | 1h | 1000 | 41.6 | 36 | 36 | 17 | 18 | 7.2 | 10 | 15 (21%) |
| SOL | 4h | 1000 | 166.5 | 41 | 42 | 20 | 21 | 8.3 | 9 | 20 (24%) |
| SOL | 1d | 500 | 499 | 18 | 19 | 9 | 9 | 7.4 | 11 | 9 (25%) |

TF 합산: 크로스 7.2~8.0건/100봉, 0선 3.2~4.2건/100봉 — 심볼·TF 무관하게 거의 일정(EMA 비율 지표라 스케일 프리).
1h 기준 크로스 약 1.8건/일, 1d 기준 약 4.3건/월. 인접 크로스 간격이 3봉 이하인 쌍이 전체의 18%(15m·1h)~24%(4h·1d).

### 4.2 채터링 구간 (10봉 창에 크로스 3건 이상, 병합) — 총 108구간

| TF | 구간 수 | 그중 4건 이상 |
|---|---|---|
| 15m | 31 (10일간) | 6 |
| 1h | 28 (42일간) | 5 |
| 4h | 35 (167일간) | 8 |
| 1d | 14 (500일간) | 6 |

예시(구간 |hist|max 를 그 시계열 중앙 |macd| 로 나눈 값이 0.1 아래면 0선 바로 옆 진동):

| 심볼 | TF | 구간 | 순서 | 봉수 | 구간 \|hist\|max | / 중앙\|macd\| |
|---|---|---|---|---|---|---|
| BTC | 15m | 2026-09-16 16:15 → 18:00 (가장 최근, 2시간) | GC→DC→GC→DC→GC | 8 | 16.8 | 0.24 |
| BNB | 15m | 2026-09-10 14:45 → 16:30 | GC→DC→GC→DC→GC | 8 | 0.071 | 0.09 |
| SOL | 15m | 2026-09-12 17:00 → 17:45 | GC→DC→GC→DC | 4 | 0.0053 | 0.04 |
| SOL | 1h | 2026-08-20 05:00 → 12:00 | DC→GC→DC→GC→DC | 8 | 0.079 | 0.26 |
| ETH | 4h | 2026-08-12 08:00 → 08-13 16:00 | GC→DC→GC→DC→GC | 9 | 1.11 | 0.10 |
| BTC | 4h | 2026-04-10 04:00 → 04-11 20:00 | DC→GC→DC→GC→DC | 11 | 47.3 | 0.14 |
| BTC | 1d | 2026-06-27 → 07-01 (5일) | DC→GC→DC→GC | 5 | 47.2 | 0.04 |
| BTC | 1d | 2026-09-02 → 09-04 (3일, 가장 최근) | DC→GC→DC | 3 | 92.2 | 0.07 |
| BTC | 1d | 2025-07-21 → 07-23 (3일) | DC→GC→DC | 3 | 61.7 | 0.05 |
| ETH·BNB·SOL | 1d | 2025-12-17 → 12-28 (동시) | DC→GC→DC→GC (3심볼 모두) | 10~11 | — | 0.14~0.31 |

일봉에서도 "며칠 새 여러 번" 구간이 심볼당 3~5회 있다. 특히 BTC 1d 2026-06-27~07-01 은 5일에 4번 교차했고 hist 진폭이 중앙 |macd| 의 4% 수준(0선 바로 옆 진동)이다.
2025-12-17~28 은 ETH·BNB·SOL 일봉이 같은 시기에 같은 순서로 4번 교차 — 시장 전체 횡보 구간에서 채터링이 동시에 난다.

### 4.3 판단 사항 (상위 결정)

채터링 억제(최소 hist 이격, 쿨다운 봉수 등)는 파라미터 발명이라 이번 위임에서 구현하지 않았다.
위 빈도(크로스 ~7.5건/100봉, 인접 간격≤3봉 약 1/5, 10봉 창 3건 이상 구간이 15m 에서 하루 3회꼴)가 알람으로 과한지는 상위 결정.

## 5. 범위 밖 관찰

- tests/test_panel_smoke.py::test_context_panels_render_fast 는 이번 변경 전부터 실패(위 3절). 레거시 3탭 차트 어댑터가 aeba3d3 이후 제거된 인자를 넘긴다.
- tests/test_wave_ruleset_robustness.py 2건도 수정 전부터 실패(연구 체인, 미접촉).
- 브랜치 최신 커밋 501a95d "delete list" 는 delete_list.txt / delete_list.z 를 추가한 사용자 커밋(이번 작업과 무관).
- 알람 이력 표의 "지표값" 컬럼은 기존 포맷(%.1f)이라 hist 가 0 근처인 크로스 값은 0.0 으로 보인다. 반대편 값은 "비고" 에 유효숫자 4자리로 있다. 포맷 변경은 신규 스타일이라 손대지 않았다.
