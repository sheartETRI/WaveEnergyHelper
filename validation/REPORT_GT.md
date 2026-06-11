# 정답 구간 역추적 리포트 — ETHUSDT 4h (관측 라운드 4b/4c + 규칙수정2)

- 생성 시각: 2026-06-07 07:08:50
- 대상: ETHUSDT 4h
- fetch: `fetch_klines_paginated` limit=1600봉 (페이지네이션)
- 평가 의미론: C0 엄격, ④⑤ 구조=첫 피봇, MA원자 윈도=96봉 (규칙 수정 2)
- 관측 전용: 수치·사실만 (제안·결론 없음)

## 히스토리 확보

- 데이터 범위: 2025-09-13 08:00 ~ 2026-06-06 20:00 (1600봉)
- Z1 시작: 2026-01-05 00:00
- MA240+60 워밍업 필요 시점: 2025-11-16 00:00
- Z1 워밍업 포함: **확보**

### Z1 검증 게이트 (워밍업+구간)

- 검사 범위: 워밍업 시작 pos=442 (2025-11-26 00:00) ~ Z1 종료 (2026-01-28 20:00)
- 검사 봉 수: 384
- MA240 유효: 384/384
- 레짐 판단가능: 384/384
- 결과: **통과**

## Z1 — top (2026-01-05 ~ 2026-01-28)

- 분석 범위: ±30봉 버퍼 (2025-12-31 00:00 ~ 2026-02-02 20:00)
- 차트: [gt_Z1.png](./gt_Z1.png)

### A. 원자 인벤토리

| 검출기 | 확정 수 | 타임스탬프 (kind) |
|---|---|---|
| 소파동 쌍바닥 | 7 | 2026-01-01 12:00(LL), 2026-01-11 08:00(HL), 2026-01-13 12:00(HL), 2026-01-17 00:00(LL), 2026-01-21 12:00(LL), 2026-01-26 08:00(LL), 2026-02-02 12:00(LL) |
| 소파동 쌍봉 | 8 | 2025-12-31 20:00(LH), 2026-01-03 04:00(HH), 2026-01-07 08:00(LH), 2026-01-12 12:00(HH), 2026-01-15 00:00(HH), 2026-01-18 20:00(LH), 2026-01-25 00:00(LH), 2026-01-28 20:00(HH) |
| 소파동 쓰리바닥 | 2 | 2026-01-27 00:00(HL), 2026-02-02 12:00(LL) |
| 소파동 쓰리봉 | 1 | 2026-01-19 04:00(LH) |
| 중파동 쌍바닥 | 8 | 2026-01-02 08:00(HL), 2026-01-10 12:00(HL), 2026-01-11 08:00(HL), 2026-01-13 20:00(HL), 2026-01-21 16:00(LL), 2026-01-26 16:00(LL), 2026-02-01 00:00(HL), 2026-02-02 16:00(LL) |
| 중파동 쌍봉 | 6 | 2026-01-04 16:00(LH), 2026-01-07 08:00(LH), 2026-01-16 00:00(HH), 2026-01-19 12:00(LH), 2026-01-25 08:00(LH), 2026-01-30 00:00(HH) |
| 중파동 쓰리바닥 | 2 | 2026-01-26 16:00(HL), 2026-02-02 16:00(LL) |
| 중파동 쓰리봉 | 1 | 2026-01-20 04:00(LH) |
| 대파동 쌍바닥 | 5 | 2026-01-02 00:00(LL), 2026-01-14 20:00(LL), 2026-01-23 16:00(HL), 2026-01-27 00:00(HL), 2026-02-02 12:00(HL) |
| 대파동 쌍봉 | 2 | 2026-01-06 12:00(LH), 2026-01-17 04:00(HH) |
| 대파동 쓰리바닥 | 1 | 2026-01-14 20:00(HL) |
| 대파동 쓰리봉 | 1 | 2026-01-06 16:00(LH) |
| MA5 쌍바닥 | 9 | 2026-01-01 00:00(HL), 2026-01-01 16:00(HL), 2026-01-02 12:00(LL), 2026-01-03 04:00(LL), 2026-01-04 00:00(HL), 2026-01-06 12:00(LL), 2026-01-13 16:00(HL), 2026-01-28 00:00(LL), 2026-01-28 08:00(LL) |
| MA5 쌍봉 | 13 | 2026-01-09 16:00(HH), 2026-01-15 16:00(LH), 2026-01-19 04:00(LH), 2026-01-20 16:00(HH), 2026-01-20 20:00(LH), 2026-01-21 08:00(HH), 2026-01-23 00:00(LH), 2026-01-25 04:00(LH), 2026-01-25 12:00(HH), 2026-01-25 16:00(HH), 2026-01-30 00:00(HH), 2026-01-30 08:00(HH), 2026-01-30 16:00(HH) |
| MA10 쌍바닥 | 5 | 2026-01-02 12:00(HL), 2026-01-04 00:00(LL), 2026-01-14 16:00(HL), 2026-01-15 04:00(HL), 2026-01-28 04:00(LL) |
| MA10 쌍봉 | 7 | 2026-01-19 08:00(LH), 2026-01-21 04:00(HH), 2026-01-23 20:00(HH), 2026-01-25 08:00(LH), 2026-01-25 20:00(HH), 2026-01-30 08:00(LH), 2026-01-30 16:00(HH) |

### B-①. 추세 공식 (8행) — 확정 봉 평가

| 시각 | 층 | 패턴 | kind | regime | zone | 결과 |
|---|---|---|---|---|---|---|
| 2026-01-01 12:00 | small | db | LL | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-01-11 08:00 | small | db | HL | DOWN | MA20_MA60_BAND | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=MA20_MA60_BAND≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,kind=HL≠LL); F6-1c(regime=DOWN≠UP) |
| 2026-01-13 12:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-01-17 00:00 | small | db | LL | UP | MA20_MA60_BAND | HIT:F6-1b allowed=False |
| 2026-01-21 12:00 | small | db | LL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1a(zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-1c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-01-26 08:00 | small | db | LL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1a(zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-1c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-02-02 12:00 | small | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=LL≠HL) |
| 2025-12-31 20:00 | small | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-03 04:00 | small | dt | HH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-01-07 08:00 | small | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-12 12:00 | small | dt | HH | DOWN | MA20_MA60_BAND | HIT:F6-2b allowed=False |
| 2026-01-15 00:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-01-18 20:00 | small | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=MA20_MA60_BAND≠BELOW_MA20); F6-2b(regime=UP≠DOWN,kind=LH≠HH); F6-2c(regime=UP≠DOWN) |
| 2026-01-25 00:00 | small | dt | LH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-28 20:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-01-02 08:00 | mid | db | HL | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-10 12:00 | mid | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-01-11 08:00 | mid | db | HL | DOWN | MA20_MA60_BAND | NO_MATCH: F6-1d(regime=DOWN≠UP) |
| 2026-01-13 20:00 | mid | db | HL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-01-21 16:00 | mid | db | LL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1d(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-26 16:00 | mid | db | LL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-02-01 00:00 | mid | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-02 16:00 | mid | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-01-04 16:00 | mid | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2d(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-07 08:00 | mid | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2d(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-16 00:00 | mid | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-01-19 12:00 | mid | dt | LH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-25 08:00 | mid | dt | LH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-01-30 00:00 | mid | dt | HH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |

**추세 8행 요약 (구간 내 최고 도달):**

| rule_id | 상태 | 상세 |
|---|---|---|
| F6-1a | HIT | 2026-01-13 12:00 HIT:F6-1a allowed=True |
| F6-1b | RULE_BLOCKED | 2026-01-17 00:00 HIT:F6-1b allowed=False |
| F6-1c | NO_SIGNAL | 구간 내 확정 없음 |
| F6-1d | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2a | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2b | RULE_BLOCKED | 2026-01-12 12:00 HIT:F6-2b allowed=False |
| F6-2c | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2d | NO_SIGNAL | 구간 내 확정 없음 |

### B-②. 변곡점 공식 (8행) — 완성 사건 게이트 (구조=첫 피봇)

| rule_id | 구조 | 버퍼내 A | 버퍼내 B | 버퍼내 완성사건 | 요약 모드 | 최소간격 |
|---|---|---|---|---|---|---|
| F6-4a | U1 | 6 | 1 | 2 | HIT | 97 |
| F6-4b | U2 | 2 | 1 | 1 | STRUCT_BLOCKED:U1 | 103 |
| F6-4c-a | U3 | 13 | 1 | 8 | STRUCT_BLOCKED:None | 38 |
| F6-4c-b | U3 | 4 | 1 | 2 | STRUCT_BLOCKED:None | 49 |
| F6-5a | D1 | 8 | 2 | 3 | STRUCT_BLOCKED:None | 23 |
| F6-5b | D2 | 5 | 2 | 3 | HIT | 22 |
| F6-5c-a | D3 | 9 | 1 | 9 | STRUCT_BLOCKED:None | 191 |
| F6-5c-b | D3 | 2 | 3 | 5 | STRUCT_BLOCKED:None | 29 |

**완성 사건 상세:**
- `F6-4a` 2026-01-19 04:00: HIT (간격=97봉)
- `F6-4a` 2026-01-19 12:00: HIT (간격=99봉)
- `F6-4b` 2026-01-20 04:00: STRUCT_BLOCKED:U1 (간격=103봉)
- `F6-4c-a` 2026-01-06 16:00: STRUCT_BLOCKED:None (간격=104봉)
- `F6-4c-a` 2026-01-06 16:00: STRUCT_BLOCKED:None (간격=91봉)
- `F6-4c-a` 2026-01-09 16:00: STRUCT_BLOCKED:None (간격=38봉)
- `F6-4c-a` 2026-01-15 16:00: STRUCT_BLOCKED:U2 (간격=69봉)
- `F6-4c-a` 2026-01-19 04:00: STRUCT_BLOCKED:U2 (간격=90봉)
- `F6-4c-a` 2026-01-20 16:00: STRUCT_BLOCKED:U2 (간격=99봉)
- `F6-4c-a` 2026-01-20 20:00: STRUCT_BLOCKED:U2 (간격=100봉)
- `F6-4c-a` 2026-01-21 08:00: STRUCT_BLOCKED:None (간격=122봉)
- `F6-4c-b` 2026-01-06 12:00: STRUCT_BLOCKED:None (간격=49봉)
- `F6-4c-b` 2026-01-21 04:00: STRUCT_BLOCKED:U2 (간격=93봉)
- `F6-5a` 2026-01-27 00:00: STRUCT_BLOCKED:None (간격=47봉)
- `F6-5a` 2026-02-02 12:00: STRUCT_BLOCKED:None (간격=23봉)
- `F6-5a` 2026-02-02 16:00: STRUCT_BLOCKED:None (간격=24봉)
- `F6-5b` 2026-01-26 16:00: STRUCT_BLOCKED:None (간격=43봉)
- `F6-5b` 2026-01-27 00:00: STRUCT_BLOCKED:None (간격=45봉)
- `F6-5b` 2026-02-02 16:00: HIT (간격=22봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=205봉)
- `F6-5c-a` 2026-01-14 20:00: STRUCT_BLOCKED:None (간격=191봉)
- `F6-5c-a` 2026-01-28 00:00: STRUCT_BLOCKED:None (간격=270봉)
- `F6-5c-a` 2026-01-28 08:00: STRUCT_BLOCKED:None (간격=272봉)
- `F6-5c-b` 2026-01-04 00:00: STRUCT_BLOCKED:None (간격=126봉)
- `F6-5c-b` 2026-01-04 00:00: STRUCT_BLOCKED:None (간격=126봉)
- `F6-5c-b` 2026-01-28 04:00: STRUCT_BLOCKED:D1 (간격=41봉)
- `F6-5c-b` 2026-01-28 04:00: STRUCT_BLOCKED:D1 (간격=29봉)
- `F6-5c-b` 2026-02-02 12:00: STRUCT_BLOCKED:None (간격=57봉)

### C. 구조 라벨 타임라인

- None 62% / U1 2025-12-31 04:00~2025-12-31 12:00 3봉 / U1 2026-01-01 12:00~2026-01-03 00:00 10봉 / U2 2026-01-03 16:00~2026-01-04 08:00 5봉 / U2 2026-01-04 20:00~2026-01-06 12:00 11봉 / U2 2026-01-06 20:00~2026-01-07 00:00 2봉 / U3 2026-01-14 04:00~2026-01-14 04:00 1봉 / U3 2026-01-14 12:00~2026-01-14 20:00 3봉 / U3 2026-01-15 08:00~2026-01-15 08:00 1봉 / U3 2026-01-18 08:00~2026-01-18 16:00 3봉 / D1 2026-01-20 16:00~2026-01-21 08:00 5봉 / D1 2026-01-21 20:00~2026-01-21 20:00 1봉 / D1 2026-01-22 12:00~2026-01-22 20:00 3봉 / D1 2026-01-23 04:00~2026-01-23 08:00 2봉 / D2 2026-01-25 00:00~2026-01-26 00:00 7봉 / D2 2026-01-29 20:00~2026-01-31 20:00 13봉 / D3 2026-02-01 00:00~2026-02-02 04:00 8봉

| 구조 | 봉수 | 비율 |
|---|---|---|
| U1 | 13 | 6.4% |
| U2 | 18 | 8.8% |
| U3 | 8 | 3.9% |
| D1 | 11 | 5.4% |
| D2 | 20 | 9.8% |
| D3 | 8 | 3.9% |
| None | 126 | 61.8% |

### D. 근접도 (구간 경계 ↔ C0 HIT)

- 구간 시작 이전 최근 HIT: 없음
- 구간 종료 이후 최근 HIT: 29봉 (2026-02-02 16:00)
- 버퍼 내 HIT 수: 4
- 구간 시작 이전 추세 확정(전체): 2봉 (2026-01-04 16:00)
- 구간 시작 이전 변곡 완성사건(전체): 6봉 (2026-01-04 00:00)

### 교차: ①② vs ④⑤ 진행 단계

- ①② 추세 최고 stage: 3 (0=신호없음, 1=룰불일치, 2=불가판정, 3=HIT)
- ④⑤ 변곡 최고 stage: 3 (0=ATOM_ABSENT, 1=NOT_PAIRED, 2=STRUCT_BLOCKED, 3=HIT)
- **동일 단계 (stage=3)**

## Z2 — bottom (2026-02-10 ~ 2026-03-02)

- 분석 범위: ±30봉 버퍼 (2026-02-05 00:00 ~ 2026-03-07 20:00)
- 차트: [gt_Z2.png](./gt_Z2.png)

### A. 원자 인벤토리

| 검출기 | 확정 수 | 타임스탬프 (kind) |
|---|---|---|
| 소파동 쌍바닥 | 9 | 2026-03-04 12:00(HL), 2026-03-07 08:00(LL), 2026-02-06 16:00(LL), 2026-02-12 00:00(HL), 2026-02-13 12:00(HL), 2026-02-17 20:00(HL), 2026-02-20 00:00(HL), 2026-02-24 16:00(LL), 2026-02-28 16:00(LL) |
| 소파동 쌍봉 | 8 | 2026-03-05 16:00(HH), 2026-02-09 04:00(LH), 2026-02-10 08:00(LH), 2026-02-14 12:00(LH), 2026-02-18 16:00(HH), 2026-02-22 00:00(HH), 2026-02-26 04:00(HH), 2026-02-27 12:00(LH) |
| 소파동 쓰리바닥 | 1 | 2026-02-12 08:00(HL) |
| 소파동 쓰리봉 | 2 | 2026-02-05 16:00(LH), 2026-02-27 16:00(HH) |
| 중파동 쌍바닥 | 6 | 2026-03-04 16:00(LL), 2026-02-06 20:00(LL), 2026-02-11 20:00(LL), 2026-02-13 12:00(HL), 2026-02-21 00:00(HL), 2026-02-25 00:00(LL) |
| 중파동 쌍봉 | 4 | 2026-03-03 16:00(LH), 2026-03-06 08:00(HH), 2026-02-08 20:00(HH), 2026-02-23 04:00(HH) |
| 중파동 쓰리바닥 | 1 | 2026-02-14 04:00(LL) |
| 중파동 쓰리봉 | 1 | 2026-02-24 08:00(LH) |
| 대파동 쌍바닥 | 5 | 2026-02-07 04:00(LL), 2026-02-14 20:00(HL), 2026-02-19 04:00(HL), 2026-02-21 04:00(LL), 2026-02-26 08:00(LL) |
| 대파동 쌍봉 | 2 | 2026-03-06 12:00(HH), 2026-02-24 04:00(LH) |
| 대파동 쓰리바닥 | 1 | 2026-02-07 04:00(LL) |
| 대파동 쓰리봉 | 0 | 없음 |
| MA5 쌍바닥 | 9 | 2026-03-04 12:00(HL), 2026-03-04 16:00(HL), 2026-03-04 20:00(HL), 2026-03-05 00:00(HL), 2026-02-13 12:00(LL), 2026-02-14 20:00(LL), 2026-02-25 20:00(LL), 2026-02-26 00:00(LL), 2026-03-02 20:00(HL) |
| MA5 쌍봉 | 4 | 2026-02-10 08:00(LH), 2026-02-19 08:00(LH), 2026-02-23 00:00(LH), 2026-02-23 16:00(LH) |
| MA10 쌍바닥 | 5 | 2026-03-05 00:00(HL), 2026-03-05 08:00(HL), 2026-03-05 16:00(HL), 2026-02-26 08:00(LL), 2026-02-26 12:00(LL) |
| MA10 쌍봉 | 4 | 2026-02-10 04:00(LH), 2026-02-12 12:00(LH), 2026-02-19 12:00(LH), 2026-02-23 04:00(LH) |

### B-①. 추세 공식 (8행) — 확정 봉 평가

| 시각 | 층 | 패턴 | kind | regime | zone | 결과 |
|---|---|---|---|---|---|---|
| 2026-02-06 16:00 | small | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-02-12 00:00 | small | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-13 12:00 | small | db | HL | DOWN | MA20_MA60_BAND | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=MA20_MA60_BAND≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,kind=HL≠LL); F6-1c(regime=DOWN≠UP) |
| 2026-02-17 20:00 | small | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-20 00:00 | small | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-24 16:00 | small | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-02-28 16:00 | small | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-03-04 12:00 | small | db | HL | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-03-07 08:00 | small | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1a(regime=DOWN≠UP,zone=BELOW_MA20≠ABOVE_MA20); F6-1b(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND); F6-1c(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-02-09 04:00 | small | dt | LH | DOWN | MA20_MA60_BAND | HIT:F6-2c allowed=True |
| 2026-02-10 08:00 | small | dt | LH | DOWN | BELOW_MA20 | HIT:F6-2a allowed=True |
| 2026-02-14 12:00 | small | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-02-18 16:00 | small | dt | HH | DOWN | BELOW_MA20 | HIT:F6-2a allowed=True |
| 2026-02-22 00:00 | small | dt | HH | DOWN | MA20_MA60_BAND | HIT:F6-2b allowed=False |
| 2026-02-26 04:00 | small | dt | HH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-02-27 12:00 | small | dt | LH | DOWN | BELOW_MA20 | HIT:F6-2a allowed=True |
| 2026-03-05 16:00 | small | dt | HH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2a(zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-2c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-02-06 20:00 | mid | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-11 20:00 | mid | db | LL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-13 12:00 | mid | db | HL | DOWN | MA20_MA60_BAND | NO_MATCH: F6-1d(regime=DOWN≠UP) |
| 2026-02-21 00:00 | mid | db | HL | DOWN | BELOW_MA20 | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-02-25 00:00 | mid | db | LL | DOWN | MA20_MA60_BAND | NO_MATCH: F6-1d(regime=DOWN≠UP) |
| 2026-03-04 16:00 | mid | db | LL | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-1d(regime=DOWN≠UP,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-02-08 20:00 | mid | dt | HH | DOWN | MA20_MA60_BAND | HIT:F6-2d allowed=True |
| 2026-02-23 04:00 | mid | dt | HH | DOWN | BELOW_MA20 | NO_MATCH: F6-2d(zone=BELOW_MA20≠MA20_MA60_BAND) |
| 2026-03-03 16:00 | mid | dt | LH | DOWN | OUT_OF_SCOPE | NO_MATCH: F6-2d(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-03-06 08:00 | mid | dt | HH | DOWN | BELOW_MA20 | NO_MATCH: F6-2d(zone=BELOW_MA20≠MA20_MA60_BAND) |

**추세 8행 요약 (구간 내 최고 도달):**

| rule_id | 상태 | 상세 |
|---|---|---|
| F6-1a | NO_SIGNAL | 구간 내 확정 없음 |
| F6-1b | NO_SIGNAL | 구간 내 확정 없음 |
| F6-1c | NO_SIGNAL | 구간 내 확정 없음 |
| F6-1d | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2a | HIT | 2026-02-10 08:00 HIT:F6-2a allowed=True |
| F6-2b | RULE_BLOCKED | 2026-02-22 00:00 HIT:F6-2b allowed=False |
| F6-2c | HIT | 2026-02-09 04:00 HIT:F6-2c allowed=True |
| F6-2d | HIT | 2026-02-08 20:00 HIT:F6-2d allowed=True |

### B-②. 변곡점 공식 (8행) — 완성 사건 게이트 (구조=첫 피봇)

| rule_id | 구조 | 버퍼내 A | 버퍼내 B | 버퍼내 완성사건 | 요약 모드 | 최소간격 |
|---|---|---|---|---|---|---|
| F6-4a | U1 | 4 | 2 | 2 | STRUCT_BLOCKED:None | 58 |
| F6-4b | U2 | 2 | 1 | 1 | STRUCT_BLOCKED:None | 96 |
| F6-4c-a | U3 | 4 | 0 | 0 | ATOM_ABSENT:대파동 쓰리봉 | 74 |
| F6-4c-b | U3 | 0 | 1 | 0 | ATOM_ABSENT:MA10 쌍봉(HH) | 147 |
| F6-5a | D1 | 6 | 1 | 2 | STRUCT_BLOCKED:None | 17 |
| F6-5b | D2 | 5 | 1 | 1 | STRUCT_BLOCKED:D3 | 54 |
| F6-5c-a | D3 | 9 | 1 | 4 | STRUCT_BLOCKED:None | 78 |
| F6-5c-b | D3 | 2 | 2 | 4 | HIT | 53 |

**완성 사건 상세:**
- `F6-4a` 2026-02-05 16:00: STRUCT_BLOCKED:None (간격=58봉)
- `F6-4a` 2026-02-08 20:00: STRUCT_BLOCKED:None (간격=77봉)
- `F6-4b` 2026-02-24 08:00: STRUCT_BLOCKED:None (간격=96봉)
- `F6-5a` 2026-02-12 08:00: STRUCT_BLOCKED:None (간격=17봉)
- `F6-5a` 2026-02-13 12:00: STRUCT_BLOCKED:None (간격=24봉)
- `F6-5b` 2026-02-14 20:00: STRUCT_BLOCKED:D3 (간격=54봉)
- `F6-5c-a` 2026-02-07 04:00: STRUCT_BLOCKED:None (간격=86봉)
- `F6-5c-a` 2026-02-07 04:00: STRUCT_BLOCKED:D1 (간격=101봉)
- `F6-5c-a` 2026-02-13 12:00: STRUCT_BLOCKED:D2 (간격=78봉)
- `F6-5c-a` 2026-02-14 20:00: STRUCT_BLOCKED:D2 (간격=86봉)
- `F6-5c-b` 2026-02-26 08:00: HIT (간격=122봉)
- `F6-5c-b` 2026-02-26 08:00: STRUCT_BLOCKED:None (간격=53봉)
- `F6-5c-b` 2026-02-26 12:00: HIT (간격=123봉)
- `F6-5c-b` 2026-02-26 12:00: STRUCT_BLOCKED:None (간격=56봉)

### C. 구조 라벨 타임라인

- None 79% / D3 2026-02-05 00:00~2026-02-06 04:00 8봉 / D3 2026-02-10 08:00~2026-02-10 16:00 3봉 / D3 2026-02-11 00:00~2026-02-11 20:00 6봉 / D3 2026-02-13 04:00~2026-02-13 04:00 1봉 / D3 2026-02-19 08:00~2026-02-19 20:00 4봉 / D3 2026-02-20 08:00~2026-02-20 08:00 1봉 / D3 2026-02-23 00:00~2026-02-23 04:00 2봉 / D3 2026-02-23 12:00~2026-02-24 08:00 6봉 / U1 2026-03-02 00:00~2026-03-02 00:00 1봉 / U1 2026-03-02 16:00~2026-03-02 20:00 2봉 / U1 2026-03-04 08:00~2026-03-04 20:00 4봉 / U1 2026-03-05 08:00~2026-03-05 08:00 1봉

| 구조 | 봉수 | 비율 |
|---|---|---|
| U1 | 8 | 4.3% |
| U2 | 0 | 0.0% |
| U3 | 0 | 0.0% |
| D1 | 0 | 0.0% |
| D2 | 0 | 0.0% |
| D3 | 31 | 16.7% |
| None | 147 | 79.0% |

### D. 근접도 (구간 경계 ↔ C0 HIT)

- 구간 시작 이전 최근 HIT: 5봉 (2026-02-09 04:00)
- 구간 종료 이후 최근 HIT: 없음
- 버퍼 내 HIT 수: 7
- 구간 시작 이전 추세 확정(전체): 5봉 (2026-02-09 04:00)
- 구간 시작 이전 변곡 완성사건(전체): 7봉 (2026-02-08 20:00)

### 교차: ①② vs ④⑤ 진행 단계

- ①② 추세 최고 stage: 3 (0=신호없음, 1=룰불일치, 2=불가판정, 3=HIT)
- ④⑤ 변곡 최고 stage: 3 (0=ATOM_ABSENT, 1=NOT_PAIRED, 2=STRUCT_BLOCKED, 3=HIT)
- **동일 단계 (stage=3)**

### Z2 중량 원자 상세 (F6-5c-a / F6-5c-b)

| 원자 | 공식 | 버퍼 내 | 전구간 | 상태 | 버퍼外 최근접 |
|---|---|---|---|---|---|
| MA5 쌍바닥 | F6-5c-a | 9 | 62 | 확정 | - |
| 대파동 쓰리바닥 | F6-5c-a | 1 | 6 | 확정 | - |
| MA10 쌍바닥 kind=LL | F6-5c-b | 2 | 16 | 확정 | - |
| 대파동 쌍바닥 kind=HL | F6-5c-b | 2 | 22 | 확정 | - |

## Z3 — top (2026-04-14 ~ 2026-05-10)

- 분석 범위: ±30봉 버퍼 (2026-04-09 00:00 ~ 2026-05-15 20:00)
- 차트: [gt_Z3.png](./gt_Z3.png)

### A. 원자 인벤토리

| 검출기 | 확정 수 | 타임스탬프 (kind) |
|---|---|---|
| 소파동 쌍바닥 | 11 | 2026-04-10 16:00(HL), 2026-04-13 16:00(HL), 2026-04-16 20:00(HL), 2026-04-20 08:00(HL), 2026-04-22 04:00(HL), 2026-04-26 04:00(HL), 2026-04-28 16:00(HL), 2026-05-02 16:00(HL), 2026-05-05 08:00(HL), 2026-05-08 08:00(HL), 2026-05-13 04:00(LL) |
| 소파동 쌍봉 | 11 | 2026-04-09 04:00(LH), 2026-04-12 00:00(LH), 2026-04-18 04:00(HH), 2026-04-23 04:00(HH), 2026-04-27 12:00(HH), 2026-05-03 00:00(HH), 2026-05-06 00:00(HH), 2026-05-06 20:00(LH), 2026-05-10 04:00(LH), 2026-05-11 04:00(HH), 2026-05-12 08:00(LH) |
| 소파동 쓰리바닥 | 3 | 2026-04-14 00:00(LL), 2026-04-26 12:00(HL), 2026-05-10 20:00(HL) |
| 소파동 쓰리봉 | 3 | 2026-04-12 08:00(LH), 2026-04-27 12:00(HH), 2026-05-06 20:00(HH) |
| 중파동 쌍바닥 | 7 | 2026-04-14 08:00(LL), 2026-04-22 12:00(LL), 2026-04-26 08:00(HL), 2026-05-01 12:00(HL), 2026-05-09 16:00(LL), 2026-05-13 08:00(LL), 2026-05-14 16:00(HL) |
| 중파동 쌍봉 | 9 | 2026-04-10 04:00(LH), 2026-04-12 08:00(LH), 2026-04-18 16:00(LH), 2026-04-23 08:00(HH), 2026-04-27 16:00(HH), 2026-05-02 20:00(LH), 2026-05-04 20:00(LH), 2026-05-06 16:00(HH), 2026-05-11 00:00(LH) |
| 중파동 쓰리바닥 | 0 | 없음 |
| 중파동 쓰리봉 | 2 | 2026-04-12 08:00(LH), 2026-05-07 16:00(HH) |
| 대파동 쌍바닥 | 2 | 2026-05-01 04:00(HL), 2026-05-15 16:00(HL) |
| 대파동 쌍봉 | 7 | 2026-04-10 04:00(HH), 2026-04-12 12:00(HH), 2026-04-17 04:00(LH), 2026-04-18 08:00(LH), 2026-04-28 16:00(LH), 2026-05-05 16:00(LH), 2026-05-06 16:00(HH) |
| 대파동 쓰리바닥 | 0 | 없음 |
| 대파동 쓰리봉 | 0 | 없음 |
| MA5 쌍바닥 | 8 | 2026-04-11 04:00(HL), 2026-04-14 08:00(HL), 2026-04-17 12:00(HL), 2026-04-17 16:00(HL), 2026-04-22 00:00(HL), 2026-04-26 12:00(LL), 2026-05-03 08:00(LL), 2026-05-05 04:00(LL) |
| MA5 쌍봉 | 10 | 2026-04-19 08:00(HH), 2026-04-19 16:00(LH), 2026-04-25 08:00(LH), 2026-04-27 20:00(HH), 2026-04-28 04:00(LH), 2026-04-29 20:00(LH), 2026-05-06 20:00(LH), 2026-05-12 16:00(LH), 2026-05-13 16:00(LH), 2026-05-15 16:00(HH) |
| MA10 쌍바닥 | 7 | 2026-04-14 04:00(HL), 2026-04-15 00:00(HL), 2026-04-16 20:00(HL), 2026-04-17 12:00(HL), 2026-05-02 16:00(LL), 2026-05-04 20:00(LL), 2026-05-06 00:00(HL) |
| MA10 쌍봉 | 7 | 2026-04-19 16:00(HH), 2026-04-19 20:00(HH), 2026-04-28 08:00(LH), 2026-04-28 12:00(LH), 2026-04-29 20:00(LH), 2026-05-13 08:00(LH), 2026-05-15 12:00(LH) |

### B-①. 추세 공식 (8행) — 확정 봉 평가

| 시각 | 층 | 패턴 | kind | regime | zone | 결과 |
|---|---|---|---|---|---|---|
| 2026-04-10 16:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-04-13 16:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-04-16 20:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-04-20 08:00 | small | db | HL | UP | MA20_MA60_BAND | HIT:F6-1c allowed=True |
| 2026-04-22 04:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-04-26 04:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-04-28 16:00 | small | db | HL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1a(zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-05-02 16:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-05-05 08:00 | small | db | HL | UP | ABOVE_MA20 | HIT:F6-1a allowed=True |
| 2026-05-08 08:00 | small | db | HL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1a(zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HL≠LL); F6-1c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-05-13 04:00 | small | db | LL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1a(zone=OUT_OF_SCOPE≠ABOVE_MA20); F6-1b(zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-1c(zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LL≠HL) |
| 2026-04-09 04:00 | small | dt | LH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-04-12 00:00 | small | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=MA20_MA60_BAND≠BELOW_MA20); F6-2b(regime=UP≠DOWN,kind=LH≠HH); F6-2c(regime=UP≠DOWN) |
| 2026-04-18 04:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-04-23 04:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-04-27 12:00 | small | dt | HH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-05-03 00:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-05-06 00:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-05-06 20:00 | small | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=MA20_MA60_BAND≠BELOW_MA20); F6-2b(regime=UP≠DOWN,kind=LH≠HH); F6-2c(regime=UP≠DOWN) |
| 2026-05-10 04:00 | small | dt | LH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-11 04:00 | small | dt | HH | UP | ABOVE_MA20 | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=ABOVE_MA20≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND); F6-2c(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND,kind=HH≠LH) |
| 2026-05-12 08:00 | small | dt | LH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2a(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠BELOW_MA20); F6-2b(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND,kind=LH≠HH); F6-2c(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-04-14 08:00 | mid | db | LL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-04-22 12:00 | mid | db | LL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-04-26 08:00 | mid | db | HL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-01 12:00 | mid | db | HL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-09 16:00 | mid | db | LL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-13 08:00 | mid | db | LL | UP | OUT_OF_SCOPE | NO_MATCH: F6-1d(zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-05-14 16:00 | mid | db | HL | UP | ABOVE_MA20 | NO_MATCH: F6-1d(zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-04-10 04:00 | mid | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2d(regime=UP≠DOWN) |
| 2026-04-12 08:00 | mid | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2d(regime=UP≠DOWN) |
| 2026-04-18 16:00 | mid | dt | LH | UP | MA20_MA60_BAND | NO_MATCH: F6-2d(regime=UP≠DOWN) |
| 2026-04-23 08:00 | mid | dt | HH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-04-27 16:00 | mid | dt | HH | UP | OUT_OF_SCOPE | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=OUT_OF_SCOPE≠MA20_MA60_BAND) |
| 2026-05-02 20:00 | mid | dt | LH | UP | ABOVE_MA20 | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-04 20:00 | mid | dt | LH | UP | ABOVE_MA20 | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |
| 2026-05-06 16:00 | mid | dt | HH | UP | MA20_MA60_BAND | NO_MATCH: F6-2d(regime=UP≠DOWN) |
| 2026-05-11 00:00 | mid | dt | LH | UP | ABOVE_MA20 | NO_MATCH: F6-2d(regime=UP≠DOWN,zone=ABOVE_MA20≠MA20_MA60_BAND) |

**추세 8행 요약 (구간 내 최고 도달):**

| rule_id | 상태 | 상세 |
|---|---|---|
| F6-1a | HIT | 2026-04-10 16:00 HIT:F6-1a allowed=True |
| F6-1b | NO_SIGNAL | 구간 내 확정 없음 |
| F6-1c | HIT | 2026-04-20 08:00 HIT:F6-1c allowed=True |
| F6-1d | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2a | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2b | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2c | NO_SIGNAL | 구간 내 확정 없음 |
| F6-2d | NO_SIGNAL | 구간 내 확정 없음 |

### B-②. 변곡점 공식 (8행) — 완성 사건 게이트 (구조=첫 피봇)

| rule_id | 구조 | 버퍼내 A | 버퍼내 B | 버퍼내 완성사건 | 요약 모드 | 최소간격 |
|---|---|---|---|---|---|---|
| F6-4a | U1 | 9 | 3 | 5 | STRUCT_BLOCKED:None | 35 |
| F6-4b | U2 | 7 | 2 | 4 | STRUCT_BLOCKED:None | 35 |
| F6-4c-a | U3 | 10 | 0 | 0 | ATOM_ABSENT:대파동 쓰리봉 | 254 |
| F6-4c-b | U3 | 2 | 4 | 7 | STRUCT_BLOCKED:None | 17 |
| F6-5a | D1 | 7 | 3 | 5 | HIT | 41 |
| F6-5b | D2 | 2 | 0 | 0 | ATOM_ABSENT:중파동 쓰리바닥 | 29 |
| F6-5c-a | D3 | 8 | 0 | 0 | ATOM_ABSENT:대파동 쓰리바닥 | 91 |
| F6-5c-b | D3 | 2 | 2 | 4 | STRUCT_BLOCKED:None | 22 |

**완성 사건 상세:**
- `F6-4a` 2026-04-12 08:00: STRUCT_BLOCKED:None (간격=35봉)
- `F6-4a` 2026-04-12 08:00: STRUCT_BLOCKED:None (간격=35봉)
- `F6-4a` 2026-04-27 16:00: STRUCT_BLOCKED:U3 (간격=81봉)
- `F6-4a` 2026-05-06 20:00: STRUCT_BLOCKED:None (간격=45봉)
- `F6-4a` 2026-05-06 20:00: STRUCT_BLOCKED:None (간격=45봉)
- `F6-4b` 2026-04-12 08:00: STRUCT_BLOCKED:None (간격=35봉)
- `F6-4b` 2026-04-12 12:00: STRUCT_BLOCKED:None (간격=36봉)
- `F6-4b` 2026-05-07 16:00: STRUCT_BLOCKED:U3 (간격=140봉)
- `F6-4b` 2026-05-07 16:00: STRUCT_BLOCKED:U3 (간격=140봉)
- `F6-4c-b` 2026-04-19 16:00: STRUCT_BLOCKED:None (간격=26봉)
- `F6-4c-b` 2026-04-19 16:00: STRUCT_BLOCKED:None (간격=17봉)
- `F6-4c-b` 2026-04-28 16:00: STRUCT_BLOCKED:None (간격=71봉)
- `F6-4c-b` 2026-04-19 20:00: STRUCT_BLOCKED:None (간격=27봉)
- `F6-4c-b` 2026-04-19 20:00: STRUCT_BLOCKED:None (간격=27봉)
- `F6-4c-b` 2026-04-28 16:00: STRUCT_BLOCKED:None (간격=80봉)
- `F6-4c-b` 2026-05-05 16:00: STRUCT_BLOCKED:None (간격=122봉)
- `F6-5a` 2026-04-14 08:00: STRUCT_BLOCKED:None (간격=41봉)
- `F6-5a` 2026-04-26 12:00: STRUCT_BLOCKED:None (간격=69봉)
- `F6-5a` 2026-05-10 20:00: HIT (간격=66봉)
- `F6-5a` 2026-05-13 08:00: HIT (간격=81봉)
- `F6-5a` 2026-05-14 16:00: HIT (간격=89봉)
- `F6-5c-b` 2026-05-02 16:00: STRUCT_BLOCKED:None (간격=22봉)
- `F6-5c-b` 2026-05-15 16:00: STRUCT_BLOCKED:None (간격=100봉)
- `F6-5c-b` 2026-05-04 20:00: STRUCT_BLOCKED:D1 (간격=53봉)
- `F6-5c-b` 2026-05-15 16:00: STRUCT_BLOCKED:D1 (간격=118봉)

### C. 구조 라벨 타임라인

- None 82% / U3 2026-04-10 08:00~2026-04-11 00:00 5봉 / U3 2026-04-11 08:00~2026-04-11 20:00 4봉 / U3 2026-04-14 04:00~2026-04-14 08:00 2봉 / U3 2026-04-15 20:00~2026-04-16 00:00 2봉 / U3 2026-04-16 16:00~2026-04-16 16:00 1봉 / U3 2026-04-17 12:00~2026-04-17 20:00 3봉 / D1 2026-04-24 04:00~2026-04-24 04:00 1봉 / D1 2026-04-25 08:00~2026-04-25 16:00 3봉 / D1 2026-04-26 00:00~2026-04-26 00:00 1봉 / D1 2026-04-28 08:00~2026-04-28 12:00 2봉 / D1 2026-04-29 20:00~2026-04-30 00:00 2봉 / D1 2026-04-30 20:00~2026-04-30 20:00 1봉 / D1 2026-05-12 08:00~2026-05-12 20:00 4봉 / D1 2026-05-13 12:00~2026-05-14 00:00 4봉 / D1 2026-05-14 08:00~2026-05-14 08:00 1봉 / D2 2026-05-15 12:00~2026-05-15 20:00 3봉

| 구조 | 봉수 | 비율 |
|---|---|---|
| U1 | 0 | 0.0% |
| U2 | 0 | 0.0% |
| U3 | 17 | 7.7% |
| D1 | 19 | 8.6% |
| D2 | 3 | 1.4% |
| D3 | 0 | 0.0% |
| None | 183 | 82.4% |

### D. 근접도 (구간 경계 ↔ C0 HIT)

- 구간 시작 이전 최근 HIT: 2봉 (2026-04-13 16:00)
- 구간 종료 이후 최근 HIT: 15봉 (2026-05-13 08:00)
- 버퍼 내 HIT 수: 11
- 구간 시작 이전 추세 확정(전체): 2봉 (2026-04-13 16:00)
- 구간 시작 이전 변곡 완성사건(전체): 9봉 (2026-04-12 12:00)

### 교차: ①② vs ④⑤ 진행 단계

- ①② 추세 최고 stage: 3 (0=신호없음, 1=룰불일치, 2=불가판정, 3=HIT)
- ④⑤ 변곡 최고 stage: 3 (0=ATOM_ABSENT, 1=NOT_PAIRED, 2=STRUCT_BLOCKED, 3=HIT)
- **동일 단계 (stage=3)**

### Z3 회귀 확인

- ①② HIT 수(버퍼): 8 (직전 라운드: 8)
- 일치: **예**

## Z1 before/after (워밍업 보강 전후)

| 지표 | 직전(1,000봉) | 현재(페이지네이션) |
|---|---|---|
| fetch 봉수 | 1000 | 1600 |
| 워밍업 | 불충분(154봉 부족) | 확보 |
| ①② stage | 0 | 3 |
| ④⑤ stage | 2 | 3 |
| ①② 주요모드 | NO_RULE_MATCH=29 | NO_RULE_MATCH=26, RULE_BLOCKED=2, HIT=1 |
| ④⑤ 주요모드 | STRUCT_BLOCKED=6, NOT_PAIRED=1, ATOM_ABSENT=1 | STRUCT_BLOCKED=6, HIT=2 |
| 더 멀리 진행 | ④⑤ 변곡점이 더 멀리 진행 | 동일 단계 (stage=3) |
| Z1 버퍼 D3 봉수 | 8 | 8 |

- Z1 버퍼 D3: 직전 8봉 → 현재 8봉. 워밍업 보강 후에도 D3 라벨 **잔존** (NaN 구간 제외 후에도 출현).

---

## 구간×공식가족 실패 모드 요약 매트릭스

| 구간 | ①② 최고stage | ①② 주요모드 | ④⑤ 최고stage | ④⑤ 주요모드 | 더 멀리 진행 |
|---|---|---|---|---|---|
| Z1 | 3 | NO_RULE_MATCH=26, RULE_BLOCKED=2, HIT=1 | 3 | STRUCT_BLOCKED=6, HIT=2 | 동일 단계 (stage=3) |
| Z2 | 3 | NO_RULE_MATCH=21, HIT=5, RULE_BLOCKED=1 | 3 | STRUCT_BLOCKED=5, ATOM_ABSENT=2, HIT=1 | 동일 단계 (stage=3) |
| Z3 | 3 | NO_RULE_MATCH=30, HIT=8 | 3 | STRUCT_BLOCKED=4, ATOM_ABSENT=3, HIT=1 | 동일 단계 (stage=3) |

### 차트 링크

- [gt_Z1.png](./gt_Z1.png)
- [gt_Z2.png](./gt_Z2.png)
- [gt_Z3.png](./gt_Z3.png)

## 규칙 수정 2 before/after (④⑤ 첫 피봇 형성 + MA윈도96)

| 구간 | 지표 | 수정1(첫 확정봉) | 수정2(첫 피봇) |
|---|---|---|---|
| Z1 | ④⑤ stage | 2 | 3 |
| Z1 | ④⑤ 주요모드 | STRUCT_BLOCKED=8 | STRUCT_BLOCKED=6, HIT=2 |
| Z1 | 버퍼 HIT 수 | 0 | 3 |
| Z2 | ④⑤ stage | 2 | 3 |
| Z2 | ④⑤ 주요모드 | STRUCT_BLOCKED=6, ATOM_ABSENT=2 | STRUCT_BLOCKED=5, ATOM_ABSENT=2, HIT=1 |
| Z2 | 버퍼 HIT 수 | 0 | 2 |
| Z2 | w96 피봇형성=D3 (F6-5c) | 0 | 0 |
| Z2 | 버퍼 형성봉 라벨 분포 | None=6 | D1=1, D2=2, D3=3, None=8 |

---

## 관측 라운드 4c — Z1 레짐 상세 + Z2 윈도×구조 교차

### 4c-1. 레짐 타임라인 (전 구간)

- DOWN 2025-10-23 04:00~2025-12-20 20:00 (353봉) / UP 2025-12-21 00:00~2025-12-30 16:00 (59봉) / DOWN 2025-12-30 20:00~2026-01-13 04:00 (81봉) / UP 2026-01-13 08:00~2026-01-31 20:00 (112봉) / DOWN 2026-02-01 00:00~2026-03-15 12:00 (256봉) / UP 2026-03-15 16:00~2026-05-17 04:00 (376봉) / DOWN 2026-05-17 08:00~2026-06-06 20:00 (124봉)

| 레짐 | 전 구간 봉수 |
|---|---|
| UP | 547 |
| DOWN | 814 |
| 판단불가 | 239 |

**Z1±버퍼 레짐:**
- DOWN 2025-12-31 00:00~2026-01-13 04:00 (80봉) / UP 2026-01-13 08:00~2026-01-31 20:00 (112봉) / DOWN 2026-02-01 00:00~2026-02-02 20:00 (12봉)
- UP 봉 수: 112/204
- **Z1±버퍼 UP 존재: 예**
- UP 타임스탬프(일부): 2026-01-13 08:00, 2026-01-13 12:00, 2026-01-13 16:00, 2026-01-13 20:00, 2026-01-14 00:00, 2026-01-14 04:00, 2026-01-14 08:00, 2026-01-14 12:00, 2026-01-14 16:00, 2026-01-14 20:00, 2026-01-15 00:00, 2026-01-15 04:00, 2026-01-15 08:00, 2026-01-15 12:00, 2026-01-15 16:00, 2026-01-15 20:00, 2026-01-16 00:00, 2026-01-16 04:00, 2026-01-16 08:00, 2026-01-16 12:00

### 4c-2. Z1 ①② rule 매칭 상세

| rule_id | 방향 | allowed | 확정 봉 | regime | zone | kind |
|---|---|---|---|---|---|---|
| F6-1a | 상승 | True | 2026-01-13 12:00 | UP | ABOVE_MA20 | HL |
| F6-1b | 상승 | False | 2026-01-17 00:00 | UP | MA20_MA60_BAND | LL |
| F6-2b | 하락 | False | 2026-01-12 12:00 | DOWN | MA20_MA60_BAND | HH |

### 4c-3. Z1 D3 봉 위치·가격 맥락

- D3 봉 수(버퍼): 8
- 날짜 범위: 2026-02-01 00:00 ~ 2026-02-02 04:00
- close 범위: close 2228.93~2445.46
- 버퍼 우측(구간 후·폭락부): 8봉

| 시각 | close | 맥락 |
|---|---|---|
| 2026-02-01 00:00 | 2445.46 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-01 04:00 | 2411.22 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-01 08:00 | 2411.86 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-01 12:00 | 2315.39 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-01 16:00 | 2320.35 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-01 20:00 | 2270.15 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-02 00:00 | 2239.02 | 버퍼 우측(구간 후·폭락부) |
| 2026-02-02 04:00 | 2228.93 | 버퍼 우측(구간 후·폭락부) |

### 4c-4. U 라벨 전수 (전체 fetch 봉)

| U1 | U2 | U3 |
|---|---|---|
| 33 | 40 | 35 |

### 4c-5. Z2 F6-5c 윈도×구조 교차 (관측 시나리오)

#### `F6-5c-a` (요구 구조 D3)

**윈도 24봉 — 완성 사건 0건**
- 없음

**윈도 48봉 — 완성 사건 2건**

| 완성봉 | gap | A봉 | A구조 | B봉 | B구조 | 형성구조 | 형성=D3 | 완성구조 |
|---|---|---|---|---|---|---|---|---|
| 2026-02-13 12:00 | 38 | 2026-02-13 12:00 | None | 2026-02-07 04:00 | None | D2 | False | None |
| 2026-02-14 20:00 | 46 | 2026-02-14 20:00 | None | 2026-02-07 04:00 | None | D2 | False | None |

**윈도 96봉 — 완성 사건 3건**

| 완성봉 | gap | A봉 | A구조 | B봉 | B구조 | 형성구조 | 형성=D3 | 완성구조 |
|---|---|---|---|---|---|---|---|---|
| 2026-02-07 04:00 | 59 | 2026-01-28 08:00 | None | 2026-02-07 04:00 | None | D1 | False | None |
| 2026-02-13 12:00 | 38 | 2026-02-13 12:00 | None | 2026-02-07 04:00 | None | D2 | False | None |
| 2026-02-14 20:00 | 46 | 2026-02-14 20:00 | None | 2026-02-07 04:00 | None | D2 | False | None |

#### `F6-5c-b` (요구 구조 D3)

**윈도 24봉 — 완성 사건 0건**
- 없음

**윈도 48봉 — 완성 사건 2건**

| 완성봉 | gap | A봉 | A구조 | B봉 | B구조 | 형성구조 | 형성=D3 | 완성구조 |
|---|---|---|---|---|---|---|---|---|
| 2026-02-26 08:00 | 43 | 2026-02-26 08:00 | None | 2026-02-19 04:00 | None | None | False | None |
| 2026-02-26 12:00 | 44 | 2026-02-26 12:00 | None | 2026-02-19 04:00 | None | None | False | None |

**윈도 96봉 — 완성 사건 2건**

| 완성봉 | gap | A봉 | A구조 | B봉 | B구조 | 형성구조 | 형성=D3 | 완성구조 |
|---|---|---|---|---|---|---|---|---|
| 2026-02-26 08:00 | 43 | 2026-02-26 08:00 | None | 2026-02-19 04:00 | None | None | False | None |
| 2026-02-26 12:00 | 44 | 2026-02-26 12:00 | None | 2026-02-19 04:00 | None | None | False | None |

### 4c-6. Z2 D3 성립 봉 ↔ 완성 사건 거리

| D3 봉 | close | w96 최근접 완성봉 | 거리(봉) |
|---|---|---|---|
| 2026-02-05 00:00 | 2110.00 | 2026-02-07 04:00 (13봉) | 13 |
| 2026-02-05 04:00 | 2091.40 | 2026-02-07 04:00 (12봉) | 12 |
| 2026-02-05 08:00 | 2079.98 | 2026-02-07 04:00 (11봉) | 11 |
| 2026-02-05 12:00 | 1961.12 | 2026-02-07 04:00 (10봉) | 10 |
| 2026-02-05 16:00 | 1928.76 | 2026-02-07 04:00 (9봉) | 9 |
| 2026-02-05 20:00 | 1826.83 | 2026-02-07 04:00 (8봉) | 8 |
| 2026-02-06 00:00 | 1891.82 | 2026-02-07 04:00 (7봉) | 7 |
| 2026-02-06 04:00 | 1899.42 | 2026-02-07 04:00 (6봉) | 6 |
| 2026-02-10 08:00 | 2003.21 | 2026-02-07 04:00 (19봉) | 19 |
| 2026-02-10 12:00 | 2022.66 | 2026-02-13 12:00 (18봉) | 18 |
| 2026-02-10 16:00 | 2017.95 | 2026-02-13 12:00 (17봉) | 17 |
| 2026-02-11 00:00 | 2009.59 | 2026-02-13 12:00 (15봉) | 15 |
| 2026-02-11 04:00 | 1950.89 | 2026-02-13 12:00 (14봉) | 14 |
| 2026-02-11 08:00 | 1953.66 | 2026-02-13 12:00 (13봉) | 13 |
| 2026-02-11 12:00 | 1929.46 | 2026-02-13 12:00 (12봉) | 12 |
| 2026-02-11 16:00 | 1952.28 | 2026-02-13 12:00 (11봉) | 11 |
| 2026-02-11 20:00 | 1941.18 | 2026-02-13 12:00 (10봉) | 10 |
| 2026-02-13 04:00 | 1935.75 | 2026-02-13 12:00 (2봉) | 2 |
| 2026-02-19 08:00 | 1949.58 | 2026-02-14 20:00 (27봉) | 27 |
| 2026-02-19 12:00 | 1926.30 | 2026-02-14 20:00 (28봉) | 28 |
| 2026-02-19 16:00 | 1941.34 | 2026-02-14 20:00 (29봉) | 29 |
| 2026-02-19 20:00 | 1949.08 | 2026-02-14 20:00 (30봉) | 30 |
| 2026-02-20 08:00 | 1943.98 | 2026-02-14 20:00 (33봉) | 33 |
| 2026-02-23 00:00 | 1862.87 | 2026-02-26 08:00 (20봉) | 20 |
| 2026-02-23 04:00 | 1885.50 | 2026-02-26 08:00 (19봉) | 19 |
| 2026-02-23 12:00 | 1895.65 | 2026-02-26 08:00 (17봉) | 17 |
| 2026-02-23 16:00 | 1857.19 | 2026-02-26 08:00 (16봉) | 16 |
| 2026-02-23 20:00 | 1856.30 | 2026-02-26 08:00 (15봉) | 15 |
| 2026-02-24 00:00 | 1832.03 | 2026-02-26 08:00 (14봉) | 14 |
| 2026-02-24 04:00 | 1825.70 | 2026-02-26 08:00 (13봉) | 13 |
| 2026-02-24 08:00 | 1826.75 | 2026-02-26 08:00 (12봉) | 12 |

### 4c-7. 교차 사실 (윈도 96 · 형성봉/완성봉 D3)

- F6-5c-a 형성=D3: 0건 / 완성=D3: 0건
- F6-5c-b 형성=D3: 0건 / 완성=D3: 0건
- **F6-5c 합산 형성=D3: 0건 / 완성=D3: 0건**
