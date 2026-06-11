# REPORT_WAVE_TRACKER

대파동 3파 하락 종료 추적 (가설 레이어)

## ETHUSDT 4h

- CSV: `wave_tracker_ETHUSDT_4h.csv`
- 평가 봉 수: 1360

### 상태별 spell

| state | 발생 횟수 | 평균 지속(봉) | 최대 지속(봉) |
|---|---:|---:|---:|
| NONE | 19 | 15.7 | 74 |
| WAVE3_CANDIDATE | 25 | 6.9 | 19 |
| WAVE3_ACTIVE | 25 | 1.3 | 5 |
| DOUBLE_BOTTOM_CANDIDATE | 25 | 1.0 | 1 |
| WAVE3_COMPLETED | 16 | 30.6 | 57 |
| TRIPLE_BOTTOM_REQUIRED | 9 | 25.4 | 64 |
| TRIPLE_BOTTOM_CONFIRMED | 4 | 22.5 | 49 |
| INVALIDATED | 24 | 1.0 | 1 |

### DB 에피소드 결과

- DOUBLE_BOTTOM_CANDIDATE 에피소드: 25
- DB → WAVE3_COMPLETED: 16/25 (64.0%)
- DB → TRIPLE_BOTTOM_REQUIRED: 9/25 (36.0%)
- DB → TRIPLE_BOTTOM_CONFIRMED (직접): 0/25 (0.0%)
- DB → INVALIDATED: 0/25 (0.0%)
- INVALIDATED 봉 비율: 1.8% (24/1360)

## BTCUSDT 1d

- CSV: `wave_tracker_BTCUSDT_1d.csv`
- 평가 봉 수: 260

### 상태별 spell

| state | 발생 횟수 | 평균 지속(봉) | 최대 지속(봉) |
|---|---:|---:|---:|
| NONE | 3 | 47.3 | 132 |
| WAVE3_CANDIDATE | 4 | 3.8 | 8 |
| WAVE3_ACTIVE | 3 | 1.0 | 1 |
| DOUBLE_BOTTOM_CANDIDATE | 3 | 1.0 | 1 |
| WAVE3_COMPLETED | 1 | 42.0 | 42 |
| TRIPLE_BOTTOM_REQUIRED | 2 | 26.0 | 45 |
| INVALIDATED | 3 | 1.0 | 1 |

### DB 에피소드 결과

- DOUBLE_BOTTOM_CANDIDATE 에피소드: 3
- DB → WAVE3_COMPLETED: 1/3 (33.3%)
- DB → TRIPLE_BOTTOM_REQUIRED: 2/3 (66.7%)
- DB → TRIPLE_BOTTOM_CONFIRMED (직접): 0/3 (0.0%)
- DB → INVALIDATED: 0/3 (0.0%)
- INVALIDATED 봉 비율: 1.2% (3/260)
