# REPORT_WAVE_SURVIVAL

INITIAL 경로별 생존(Survival) 분석

## ETHUSDT 4h

- CSV: `wave_survival_ETHUSDT_4h.csv`
- PNG: `wave_survival_ETHUSDT_4h.png`
- 분석 대상 에피소드: 57

### INITIAL 분포

| type | count |
|---|---:|
| SLOPE_CONFIRMED | 36 |
| CROSS_CONFIRMED | 14 |
| TB_CONFIRMED | 7 |

### 생존 통계

| type | avg | median | max |
|---|---:|---:|---:|
| SLOPE_CONFIRMED | 27.1 | 20.0 | 90 |
| CROSS_CONFIRMED | 26.4 | 24.5 | 71 |
| TB_CONFIRMED | 32.3 | 19.0 | 81 |

### 생존율 (%)

| type | 5 | 10 | 20 | 40 | 80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 100.0 | 91.7 | 52.8 | 22.2 | 2.8 |
| CROSS_CONFIRMED | 78.6 | 78.6 | 57.1 | 21.4 | 0.0 |
| TB_CONFIRMED | 100.0 | 85.7 | 42.9 | 28.6 | 14.3 |

### 종료 원인 (%)

| type | NEW_LL | RE_OVERSOLD | OTHER |
|---|---:|---:|---:|
| SLOPE_CONFIRMED | 30.6 | 69.4 | 0.0 |
| CROSS_CONFIRMED | 21.4 | 78.6 | 0.0 |
| TB_CONFIRMED | 42.9 | 57.1 | 0.0 |

### 최장 생존 사례

- timestamp: 2026-04-13 16:00:00
- type: SLOPE_CONFIRMED
- survival_bars: 90
- censored: False

## BTCUSDT 1d

- CSV: `wave_survival_BTCUSDT_1d.csv`
- PNG: `wave_survival_BTCUSDT_1d.png`
- 분석 대상 에피소드: 14

### INITIAL 분포

| type | count |
|---|---:|
| SLOPE_CONFIRMED | 12 |
| CROSS_CONFIRMED | 2 |

### 생존 통계

| type | avg | median | max |
|---|---:|---:|---:|
| SLOPE_CONFIRMED | 26.8 | 26.0 | 45 |
| CROSS_CONFIRMED | 13.0 | 13.0 | 19 |

### 생존율 (%)

| type | 5 | 10 | 20 | 40 | 80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 100.0 | 91.7 | 75.0 | 25.0 | 0.0 |
| CROSS_CONFIRMED | 100.0 | 50.0 | 0.0 | 0.0 | 0.0 |

### 종료 원인 (%)

| type | NEW_LL | RE_OVERSOLD | OTHER |
|---|---:|---:|---:|
| SLOPE_CONFIRMED | 18.2 | 81.8 | 0.0 |
| CROSS_CONFIRMED | 50.0 | 50.0 | 0.0 |

### 최장 생존 사례

- timestamp: 2025-09-28 00:00:00
- type: SLOPE_CONFIRMED
- survival_bars: 45
- censored: False

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| SLOPE avg | 27.1 | 26.8 |
| CROSS avg | 26.4 | 13.0 |
| TB avg | 32.3 | — |
| SLOPE 20봉 생존율 | 52.8% | 75.0% |
| CROSS 20봉 생존율 | 57.1% | 0.0% |
| SLOPE 40봉 생존율 | 22.2% | 25.0% |
| CROSS 40봉 생존율 | 21.4% | 0.0% |
| SLOPE 80봉 생존율 | 2.8% | 0.0% |
| CROSS 80봉 생존율 | 0.0% | 0.0% |
