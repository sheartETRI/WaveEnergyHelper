# REPORT_WAVE_OUTCOME

INITIAL 경로별 가격 성과 분석

## ETHUSDT 4h

- CSV: `wave_outcome_ETHUSDT_4h.csv`
- PNG: `wave_outcome_ETHUSDT_4h.png`
- 에피소드: 57

### 평균 수익률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 0.26 | 0.04 | -1.21 | -2.29 | -3.80 |
| CROSS_CONFIRMED | 0.32 | -0.27 | -1.28 | -3.92 | -5.03 |
| TB_CONFIRMED | -2.29 | -1.36 | -7.18 | -5.52 | -2.20 |

### 중앙값 수익률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 0.44 | 0.21 | -0.72 | -1.40 | -4.21 |
| CROSS_CONFIRMED | 0.18 | 0.17 | -1.48 | -4.63 | -3.68 |
| TB_CONFIRMED | -2.68 | 0.20 | -3.90 | -3.96 | 1.32 |

### 승률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 61.11 | 55.56 | 38.24 | 38.24 | 40.62 |
| CROSS_CONFIRMED | 61.54 | 61.54 | 30.77 | 30.77 | 23.08 |
| TB_CONFIRMED | 28.57 | 57.14 | 28.57 | 16.67 | 60.00 |

### 평균 MFE (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 2.52 | 3.46 | 4.02 | 5.18 | 7.16 |
| CROSS_CONFIRMED | 2.48 | 3.29 | 4.15 | 5.23 | 6.31 |
| TB_CONFIRMED | 0.92 | 1.69 | 2.58 | 2.99 | 5.02 |

### 평균 MAE (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | -2.34 | -3.34 | -4.26 | -7.03 | -10.95 |
| CROSS_CONFIRMED | -2.29 | -3.19 | -5.24 | -9.64 | -12.31 |
| TB_CONFIRMED | -3.69 | -5.54 | -9.36 | -10.22 | -11.73 |

### 생존 조건별 평균 수익률 (%)

| type | filter | n | mean +20 | mean +40 | mean +80 |
|---|---|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 전체 | 36 | -1.21 | -2.29 | -3.80 |
| SLOPE_CONFIRMED | survival≥20 | 19 | -1.31 | -3.20 | -3.75 |
| SLOPE_CONFIRMED | survival≥40 | 8 | 0.02 | 0.54 | -1.62 |
| SLOPE_CONFIRMED | survival≥80 | 1 | 2.79 | 2.04 | 5.86 |
| CROSS_CONFIRMED | 전체 | 14 | -1.28 | -3.92 | -5.03 |
| CROSS_CONFIRMED | survival≥20 | 8 | -1.05 | -4.18 | -6.69 |
| CROSS_CONFIRMED | survival≥40 | 3 | 2.15 | 0.81 | -3.14 |
| TB_CONFIRMED | 전체 | 7 | -7.18 | -5.52 | -2.20 |
| TB_CONFIRMED | survival≥20 | 3 | -1.59 | -5.19 | -0.01 |
| TB_CONFIRMED | survival≥40 | 2 | -0.43 | -0.56 | 2.72 |
| TB_CONFIRMED | survival≥80 | 1 | 1.50 | -0.28 | 1.32 |

## BTCUSDT 1d

- CSV: `wave_outcome_BTCUSDT_1d.csv`
- PNG: `wave_outcome_BTCUSDT_1d.png`
- 에피소드: 14

### 평균 수익률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | -0.42 | -0.84 | -2.89 | -5.53 | -5.74 |
| CROSS_CONFIRMED | -2.58 | -2.01 | -4.91 | -7.05 | -16.22 |

### 중앙값 수익률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 1.23 | 1.54 | -3.50 | -5.24 | -12.27 |
| CROSS_CONFIRMED | -2.58 | -2.01 | -4.91 | -7.05 | -16.22 |

### 승률 (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 58.33 | 72.73 | 45.45 | 50.00 | 40.00 |
| CROSS_CONFIRMED | 0.00 | 50.00 | 50.00 | 50.00 | 0.00 |

### 평균 MFE (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 4.48 | 5.73 | 7.79 | 9.45 | 13.17 |
| CROSS_CONFIRMED | 2.16 | 5.32 | 6.12 | 8.46 | 1.73 |

### 평균 MAE (%)

| type | +5 | +10 | +20 | +40 | +80 |
|---|---:|---:|---:|---:|---:|
| SLOPE_CONFIRMED | -4.76 | -6.95 | -8.88 | -15.17 | -20.94 |
| CROSS_CONFIRMED | -4.43 | -7.66 | -10.26 | -15.70 | -29.36 |

### 생존 조건별 평균 수익률 (%)

| type | filter | n | mean +20 | mean +40 | mean +80 |
|---|---|---:|---:|---:|---:|
| SLOPE_CONFIRMED | 전체 | 12 | -2.89 | -5.53 | -5.74 |
| SLOPE_CONFIRMED | survival≥20 | 9 | -1.70 | -5.29 | -3.08 |
| SLOPE_CONFIRMED | survival≥40 | 3 | -0.42 | -3.44 | 4.95 |
| CROSS_CONFIRMED | 전체 | 2 | -4.91 | -7.05 | -16.22 |

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| SLOPE +20 avg | -1.21 | -2.89 |
| SLOPE +40 avg | -2.29 | -5.53 |
| SLOPE +80 avg | -3.80 | -5.74 |
| CROSS +20 avg | -1.28 | -4.91 |
| CROSS +40 avg | -3.92 | -7.05 |
| CROSS +80 avg | -5.03 | -16.22 |
| TB +20 avg | -7.18 | — |
| TB +40 avg | -5.52 | — |
| TB +80 avg | -2.20 | — |
