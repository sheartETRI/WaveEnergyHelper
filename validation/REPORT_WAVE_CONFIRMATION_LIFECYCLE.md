# REPORT_WAVE_CONFIRMATION_LIFECYCLE

DB → INITIAL → POST 생존(lifecycle) 분석

## ETHUSDT 4h

- CSV: `wave_confirmation_lifecycle_ETHUSDT_4h.csv`
- PNG: `wave_confirmation_lifecycle_ETHUSDT_4h.png`
- DB 에피소드: 66

### INITIAL 분포

| outcome | count | ratio |
|---|---:|---:|
| CROSS_CONFIRMED | 14 | 21.2% |
| SLOPE_CONFIRMED | 36 | 54.5% |
| TB_CONFIRMED | 7 | 10.6% |
| NO_CONFIRM | 9 | 13.6% |

### POST 분포

| outcome | count | ratio |
|---|---:|---:|
| LATER_NEW_LL | 17 | 25.8% |
| LATER_RE_OVERSOLD | 40 | 60.6% |
| EXPIRED | 9 | 13.6% |

### INITIAL → POST 전이

| INITIAL | POST | count |
|---|---|---:|
| SLOPE_CONFIRMED | LATER_RE_OVERSOLD | 25 |
| CROSS_CONFIRMED | LATER_RE_OVERSOLD | 11 |
| SLOPE_CONFIRMED | LATER_NEW_LL | 11 |
| NO_CONFIRM | EXPIRED | 9 |
| TB_CONFIRMED | LATER_RE_OVERSOLD | 4 |
| TB_CONFIRMED | LATER_NEW_LL | 3 |
| CROSS_CONFIRMED | LATER_NEW_LL | 3 |

### 평균 유지 기간 (INITIAL별 avg held)

| INITIAL | avg held |
|---|---:|
| CROSS_CONFIRMED | 26.36 |
| SLOPE_CONFIRMED | 27.11 |
| TB_CONFIRMED | 32.29 |

### 핵심 관측

- 평균 bars_until_initial: 2.44
- 평균 bars_held_after_initial: 27.56
- 최장 bars_held: 90.0
- CROSS → HELD: 0.0%
- SLOPE → HELD: 0.0%
- CROSS → NEW_LL: 21.4%
- SLOPE → NEW_LL: 30.6%

## BTCUSDT 1d

- CSV: `wave_confirmation_lifecycle_BTCUSDT_1d.csv`
- PNG: `wave_confirmation_lifecycle_BTCUSDT_1d.png`
- DB 에피소드: 15

### INITIAL 분포

| outcome | count | ratio |
|---|---:|---:|
| CROSS_CONFIRMED | 2 | 13.3% |
| SLOPE_CONFIRMED | 12 | 80.0% |
| NO_CONFIRM | 1 | 6.7% |

### POST 분포

| outcome | count | ratio |
|---|---:|---:|
| HELD | 1 | 6.7% |
| LATER_NEW_LL | 3 | 20.0% |
| LATER_RE_OVERSOLD | 10 | 66.7% |
| EXPIRED | 1 | 6.7% |

### INITIAL → POST 전이

| INITIAL | POST | count |
|---|---|---:|
| SLOPE_CONFIRMED | LATER_RE_OVERSOLD | 9 |
| SLOPE_CONFIRMED | LATER_NEW_LL | 2 |
| CROSS_CONFIRMED | LATER_RE_OVERSOLD | 1 |
| NO_CONFIRM | EXPIRED | 1 |
| CROSS_CONFIRMED | LATER_NEW_LL | 1 |
| SLOPE_CONFIRMED | HELD | 1 |

### 평균 유지 기간 (INITIAL별 avg held)

| INITIAL | avg held |
|---|---:|
| CROSS_CONFIRMED | 13.00 |
| SLOPE_CONFIRMED | 26.75 |
| TB_CONFIRMED | — |

### 핵심 관측

- 평균 bars_until_initial: 3.86
- 평균 bars_held_after_initial: 24.79
- 최장 bars_held: 45.0
- CROSS → HELD: 0.0%
- SLOPE → HELD: 8.3%
- CROSS → NEW_LL: 50.0%
- SLOPE → NEW_LL: 16.7%

## ETH / BTC 비교

| 지표 | ETHUSDT_4h | BTCUSDT_1d |
|---|---:|---:|
| 에피소드 수 | 66 | 15 |
| 평균 bars_until_initial | 2.4 | 3.9 |
| 평균 bars_held | 27.6 | 24.8 |
| CROSS→HELD % | 0.0 | 0.0 |
| SLOPE→HELD % | 0.0 | 8.3 |
| CROSS→NEW_LL % | 21.4 | 50.0 |
| SLOPE→NEW_LL % | 30.6 | 16.7 |
