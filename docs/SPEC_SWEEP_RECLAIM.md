# 스윕 재탈환 검출기 — 동결 스펙 (SPEC_SWEEP_RECLAIM)

작성일: 2026-09-23 / 확정: 김박사 / 상태: **동결 스펙** (기록 전용 관측 검출기, experiment 브랜치)

## 0. 배경과 목적

뻔한 레벨(모두가 보는 채널 경계)의 이탈은 두 갈래로 갈린다 — 손절 물량을 걷어가는
**유동성 사냥(스윕: 이탈 후 빠른 재탈환)** 이거나, **진짜 붕괴/돌파(이탈 지속)** 다.
급등 직전에 뻔한 채널을 잠깐 이탈시키는 트랩이 반복 관측된다는 가설을 검증하기 위해,
본 검출기는 그 판별에 쓸 이벤트를 **기록만** 한다.

- 게이팅·진입 신호·알람 발송·백테스트 판정은 전부 **비목표**.
- 백테스트 숙성 방침(2027-03 열람까지 라운드 중단)에 따라, 본 이벤트는 표본만 쌓는다.

## 1. 핵심 정의 (하단 기준 — 상단은 전부 미러)

| 항목 | 정의 |
|---|---|
| 레벨 | Donchian 하단 `L_t = min(low[t-N..t-1])` — 당봉 제외(shift 1), 워밍업 N봉. 상단은 `H_t = max(high[t-N..t-1])` |
| 에피소드 시작 | `low_s < L_s` 인 첫 봉 s. 레벨은 이 시점 값으로 **동결** (이탈이 만든 신저가가 레벨을 끌어내리지 않게) |
| 재탈환 | `close_r ≥ L` 인 첫 봉 r. s 자신일 수 있음(봉내 스윕, dwell 0) |
| 확정 | r+1 봉 종가도 `≥ L` 일 때만 발화, timestamp = r+1. MACD 알람의 t+1 확정 규칙과 동형. 왕복(재탈환 직후 재이탈)은 발화 없이 에피소드 지속·왕복 횟수만 기록. r 이 마지막 봉이면 보류(lookahead 없음) |
| 체류(dwell) | 에피소드 중 종가 기준 레벨 밖 봉 수 |
| 진짜 이탈 | `dwell > reclaim_max_bars` 가 되는 봉에서 발화(하단 붕괴 / 상단 돌파 지속). 이후 종가가 롤링 레벨 안으로 돌아올 때까지 신규 에피소드를 열지 않음 |

## 2. 사전등록 파라미터 (`config.settings.SWEEP_RECLAIM_PARAMS`)

| 키 | 값 | 의미 |
|---|---|---|
| `donchian_n` | 60 | 레벨 창(봉). 60봉 = 1d에서 약 3개월 저점/고점 |
| `touch_tol_pct` | 0.005 | 터치 판정 폭(레벨 대비 비율) — 뻔함 프록시 계산에만 사용 |
| `reclaim_max_bars` | 3 | 종가 기준 체류 허용 최대 봉수. 초과 = 진짜 이탈 |
| `vol_ma_n` | 20 | 거래량 기준선 SMA 창 |

값 변경은 이 문서 개정으로만 한다 (post-hoc 튜닝 금지). 타임프레임별 별도 튜닝 없음 —
전 TF 동일 파라미터(봉 수 기준)로 기록하고, 차이는 열람 시점에 해석한다.

## 3. 이벤트 종류 (4)

| kind | direction | 의미 |
|---|---|---|
| `sweep_low_reclaim` | bull | 하단 스윕 재탈환 (스프링 성격 — 진입 관점 관찰 대상) |
| `sweep_low_breakdown` | bear | 하단 붕괴 지속 (진짜 이탈) |
| `sweep_high_reclaim` | bear | 상단 페이크 돌파 회귀 (업스러스트 성격 — 청산·관망 관점) |
| `sweep_high_breakout` | bull | 상단 돌파 지속 (진성 돌파) |

## 4. 기록 필드 (이벤트당)

`level`(동결 레벨), `start_ts`, `reclaim_ts`(진짜 이탈이면 없음), `depth_pct`(레벨 대비 최대
이탈 깊이 %), `dwell_bars`, `bars_from_start`, `level_age_bars`(레벨 극값 형성 후 이탈까지
경과 봉), `touch_count`(직전 N봉 창에서 레벨 ±tol 이내 터치 봉 수 — 뻔함 프록시),
`dev_vol_ratio`(이탈 시작 봉 거래량 / 직전 vol_ma_n 평균), `reclaim_vol_ratio`(재탈환 봉 동),
`detail`(왕복 횟수 등).

판별 변수(깊이·체류·터치·거래량)는 **기록만** 하고 이벤트를 거르는 데 쓰지 않는다 —
"스파이크 후 후속 없음 = 스윕" 같은 해석은 열람 시점의 가설 검정 몫이다.

## 5. 구현 계약

- `analysis/sweep_reclaim.py` — 순수 pandas, streamlit 무의존, 기존 모듈 무수정
  (`config/settings.py` 파라미터 추가만).
- 입력: `high`/`low`/`close` 필수, `volume` 선택(없으면 거래량 비율 None). 인덱스는 open_time.
- 상·하단 상태기계는 독립(한 봉이 양쪽 에피소드에 속할 수 있음).
- 테스트: `tests/test_sweep_reclaim.py` — 봉내 스윕·다봉 재탈환·왕복·붕괴·보류(마지막 봉)·
  상단 미러·거래량 비율·입력 결측 각 1건 이상.

## 6. 부록 — 합류(confluence) 판정 (2026-09-23 동결, 기록 전용)

목적: "같은 TF에서 스윕 재탈환과 스토캐 쌍바닥이 함께 확정되면 트랩 완료" 가설의 표본
축적. 2026-09 BTCUSDT 6h 사례(9/15 이탈 → 9/17 00:00 재탈환 확정, 대파동 쌍바닥 동반,
저점 74,968)가 원형이다. 판정은 여기서 동결하고 해석은 열람 시점(2027-03 이후)의 몫.

### 정의

| 항목 | 정의 |
|---|---|
| bull 합류 | `sweep_low_reclaim` 확정 봉과 `stoch_db_{layer}` 확정 봉의 부호 있는 간격 gap = (쌍바닥 확정 − 스윕 확정, 봉)이 \|gap\| ≤ `max_gap_bars` |
| bear 합류 | `sweep_high_reclaim` × `stoch_dt_{layer}` — 전부 미러 |
| 제외 | 붕괴/돌파 지속(`*_breakdown`/`*_breakout`) 이벤트는 합류에 참여하지 않음 |
| timestamp | 두 확정 봉 중 **나중** 봉 — 그 시점에 양쪽이 모두 기지(lookahead 없음) |
| 중복 규칙 | 스윕 이벤트 1건당 레이어별 합류 최대 1건 — 창 내 확정이 여럿이면 \|gap\| 최소(동률이면 앞선 봉). 쌍바닥 확정 1건이 복수 스윕과 짝지어지는 것은 허용(기록 전용) |
| 레이어 | 기본 대파동(large). `layer_roles` 로 사전등록, 레이어 컬럼이 없으면 그 레이어만 조용히 건너뜀 |

### 사전등록 파라미터 (`config.settings.SWEEP_CONFLUENCE_PARAMS`)

| 키 | 값 | 의미 |
|---|---|---|
| `max_gap_bars` | 8 | 두 확정 봉 간 허용 간격(봉). 6h 기준 2일, 1d 기준 8일 |
| `layer_roles` | ["large"] | 참여 스토캐 레이어 역할 (WAVE_LAYER_ROLES 키) |

### 기록 필드

`layer`(suffix), `gap_bars`(부호 있음 — 음수면 쌍바닥이 먼저), `sweep_ts`, `stoch_ts`,
`db_kind`(HL/LL 등, 검출기 kind 컬럼 승계), 스윕 필드 승계(`level`, `depth_pct`,
`dwell_bars`).

### 구현 계약

- `analysis/sweep_confluence.py` — 검출기 무수정: `stoch_db_{suffix}`/`stoch_dt_{suffix}`
  확정 컬럼과 `scan_sweep_events` 출력을 읽는 조인 레이어(alarm_signals 와 같은 태도).
- 비목표: §0과 동일 — 게이팅·알람 발송·백테스트 판정 없음.

## 7. 부록 — 구역 니어미스 기록 (2026-09-23 동결, 기록 전용 진단)

배경: 2026-09 BTCUSDT 6h 조정의 1차 바닥은 대파동 K 20.49 — 침체선 20.0에 **0.49
미달**로 구역 진입에 실패해 쌍바닥 후보가 아예 열리지 않았다(모양은 교과서적
쌍바닥, 이후 K 89까지 직행). 연속 변수에 하드 문턱을 걸 때 생기는 FN 클래스의
빈도를 세기 위한 진단 레이어다. **검출기 판정은 바꾸지 않는다** — 침체선 완화
여부는 이 기록이 쌓인 뒤(2027-03 열람 이후) 표본으로 판단한다.

### 정의 (하단 기준 — 상단은 미러)

| 항목 | 정의 |
|---|---|
| 국소 극소 | `K[i-1] > K[i] < K[i+1]` 인 봉 i (엄격 부등호 — 동값 플래토는 판정하지 않음: 이중 스무딩된 K 에서 드묾). 확정 봉 = i+1 (t+1, lookahead 없음) |
| db 니어미스 | `oversold < K[i] ≤ oversold + near_band` — 구역 진입 실패 바닥. `K[i] ≤ oversold` 는 본 검출기 영역이므로 기록하지 않음 |
| dt 니어미스 | `overbought − near_band ≤ K[i] < overbought` — 미러 |
| margin | 경계까지 거리: db 는 `K[i] − oversold`, dt 는 `overbought − K[i]` |
| 구역 값 | `STOCH_DOUBLE_PARAMS` 의 oversold(20.0)/overbought(80.0) 재사용 — 중복 정의 금지 |

### 사전등록 파라미터 (`config.settings.STOCH_NEAR_MISS_PARAMS`)

| 키 | 값 | 의미 |
|---|---|---|
| `near_band` | 5.0 | 구역 경계 바깥 기록 폭(K 포인트) |
| `layer_roles` | ["large"] | 대상 레이어 (§6과 동일 관례) |

### 구현 계약

- `analysis/stoch_near_miss.py` — 검출기·지표 무수정: 이미 계산된
  `stoch_k_{suffix}` 컬럼만 읽는다. 순수 pandas.
- 비목표: §0과 동일. 니어미스는 신호가 아니라 FN 클래스 빈도 표본이다.
