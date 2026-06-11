# REPORT_STABILITY

- symbol: ETHUSDT 4h
- source: `verdict_timeline_ETHUSDT_4h.csv` (읽기 전용)
- 평가 봉 수: 1360

## 구간 정의

- A: 2026-01-16 ~ 2026-01-25 (A Jan UP)
- B: 2026-04-08 ~ 2026-05-16 (B Apr-May)

## 전체 타임라인

### 1. 전환 횟수

| 시퀀스 | 전환 수 |
|---|---:|
| 원본 category | 141 |
| smoothed_2 | 131 |
| smoothed_3 | 121 |
| smoothed_5 | 113 |
| 원본 family | 73 |
| family_smoothed_2 | 71 |
| family_smoothed_3 | 65 |
| family_smoothed_5 | 61 |

- confirm=3 category: 141 → 121 (감소율 14.2%)
- confirm=3 family: 73 → 65 (감소율 11.0%)
- family grouping (category→family): 141 → 73 (감소율 48.2%)

### 2. spell 길이

| 시퀀스 | 구간 수 | 평균 | 중앙 | 최대 |
|---|---:|---:|---:|---:|
| 원본 category | 142 | 9.6 | 6 | 66 |
| smoothed_2 | 132 | 10.3 | 7 | 66 |
| smoothed_3 | 122 | 11.1 | 7 | 66 |
| smoothed_5 | 114 | 11.9 | 8 | 66 |
| 원본 family | 74 | 18.4 | 18 | 81 |
| family_smoothed_2 | 72 | 18.9 | 18 | 81 |
| family_smoothed_3 | 66 | 20.6 | 19 | 81 |
| family_smoothed_5 | 62 | 21.9 | 20 | 81 |

### 3. ≤2봉 비율

| 시퀀스 | 비율 |
|---|---:|
| 원본 category | 18.3% |
| smoothed_2 | 15.2% |
| smoothed_3 | 11.5% |
| smoothed_5 | 13.2% |
| 원본 family | 8.1% |
| family_smoothed_2 | 6.9% |
| family_smoothed_3 | 3.0% |
| family_smoothed_5 | 3.2% |

- confirm=3 category ≤2봉: 18.3% → 11.5% (감소율 37.3%)

## 구간 A Jan UP

### 전환 횟수

| 시퀀스 | 전환 수 |
|---|---:|
| 원본 category | 4 |
| smoothed_3 | 4 |
| 원본 family | 3 |
| family_smoothed_3 | 3 |

- confirm=3 category 감소율: 0.0% (4→4)
- confirm=3 family 감소율: 0.0% (3→3)

### spell 길이

| 시퀀스 | 평균 | 중앙 | 최대 |
|---|---:|---:|---:|
| 원본 category | 12.0 | 12 | 18 |
| smoothed_3 | 12.0 | 12 | 18 |
| 원본 family | 15.0 | 10 | 35 |
| family_smoothed_3 | 15.0 | 10 | 35 |

### ≤2봉 비율

| 시퀀스 | 비율 |
|---|---:|
| 원본 category | 0.0% |
| smoothed_3 | 0.0% |
| 원본 family | 0.0% |
| family_smoothed_3 | 0.0% |
- confirm=3 category ≤2봉 감소율: —

## 구간 B Apr-May

### 전환 횟수

| 시퀀스 | 전환 수 |
|---|---:|
| 원본 category | 29 |
| smoothed_3 | 25 |
| 원본 family | 11 |
| family_smoothed_3 | 9 |

- confirm=3 category 감소율: 13.8% (29→25)
- confirm=3 family 감소율: 18.2% (11→9)

### spell 길이

| 시퀀스 | 평균 | 중앙 | 최대 |
|---|---:|---:|---:|
| 원본 category | 7.8 | 6 | 24 |
| smoothed_3 | 9.0 | 6 | 26 |
| 원본 family | 19.5 | 14 | 50 |
| family_smoothed_3 | 23.4 | 20 | 50 |

### ≤2봉 비율

| 시퀀스 | 비율 |
|---|---:|
| 원본 category | 20.0% |
| smoothed_3 | 11.5% |
| 원본 family | 8.3% |
| family_smoothed_3 | 0.0% |
- confirm=3 category ≤2봉 감소율: 42.3%

## 구간 A vs B (confirm=3 관측)

| 지표 | A (1월) | B (4~5월) |
|---|---:|---:|
| 원본 category 전환 | 4 | 29 |
| smoothed_3 전환 | 4 | 25 |
| 원본 family 전환 | 3 | 11 |
| family_smoothed_3 전환 | 3 | 9 |

| ≤2봉 비율 (원본 category) | 0.0% | 20.0% |
| ≤2봉 비율 (smoothed_3) | 0.0% | 11.5% |
| spell 평균 (원본 category) | 12.0 | 7.8 |
| spell 평균 (smoothed_3) | 12.0 | 9.0 |

## PNG

- `verdict_original.png`
- `verdict_smoothed_3.png`
- `family_original.png`
- `family_smoothed_3.png`
