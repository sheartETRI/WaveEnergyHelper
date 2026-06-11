# REPORT_WAVE_EXIT

청산 규칙(Exit Policy) 사후 검증

## ETHUSDT 4h

- CSV: `wave_exit_ETHUSDT_4h.csv`
- PNG: `wave_exit_ETHUSDT_4h.png`
- episode×policy 행: 279

### 정책별 평균 수익률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | -0.46 |
| TP5_SL3_TIMEOUT40 | -0.97 |
| TP5_KTURN_TIMEOUT40 | -0.70 |
| K_CROSS_DOWN_TIMEOUT40 | -1.18 |
| WAVE_INVALIDATION_EXIT | -3.01 |

### 정책별 중앙 수익률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | -3.00 |
| TP5_SL3_TIMEOUT40 | -3.00 |
| TP5_KTURN_TIMEOUT40 | -0.70 |
| K_CROSS_DOWN_TIMEOUT40 | -1.30 |
| WAVE_INVALIDATION_EXIT | -2.92 |

### 정책별 승률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 38.6 |
| TP5_SL3_TIMEOUT40 | 25.0 |
| TP5_KTURN_TIMEOUT40 | 28.6 |
| K_CROSS_DOWN_TIMEOUT40 | 30.2 |
| WAVE_INVALIDATION_EXIT | 31.6 |

### 정책별 평균 보유 봉 수

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 8.1 |
| TP5_SL3_TIMEOUT40 | 11.7 |
| TP5_KTURN_TIMEOUT40 | 6.1 |
| K_CROSS_DOWN_TIMEOUT40 | 16.8 |
| WAVE_INVALIDATION_EXIT | 23.0 |

### 정책별 평균 MFE / MAE (%)

| policy | avg MFE | avg MAE |
|---|---:|---:|
| TP3_SL3_TIMEOUT20 | 2.42 | -2.73 |
| TP5_SL3_TIMEOUT40 | 3.09 | -3.36 |
| TP5_KTURN_TIMEOUT40 | 2.11 | -2.29 |
| K_CROSS_DOWN_TIMEOUT40 | 3.80 | -3.60 |
| WAVE_INVALIDATION_EXIT | 3.87 | -6.05 |

### initial_type별 정책 성과

| initial_type | policy | avg return | win rate |
|---|---|---:|---:|
| SLOPE_CONFIRMED | TP3_SL3_TIMEOUT20 | -0.54 | 36.1 |
| SLOPE_CONFIRMED | TP5_SL3_TIMEOUT40 | -0.59 | 30.6 |
| SLOPE_CONFIRMED | TP5_KTURN_TIMEOUT40 | -0.28 | 27.8 |
| SLOPE_CONFIRMED | K_CROSS_DOWN_TIMEOUT40 | -0.79 | 32.4 |
| SLOPE_CONFIRMED | WAVE_INVALIDATION_EXIT | -2.14 | 38.9 |
| CROSS_CONFIRMED | TP3_SL3_TIMEOUT20 | 0.16 | 50.0 |
| CROSS_CONFIRMED | TP5_SL3_TIMEOUT40 | -1.77 | 15.4 |
| CROSS_CONFIRMED | TP5_KTURN_TIMEOUT40 | -0.94 | 30.8 |
| CROSS_CONFIRMED | K_CROSS_DOWN_TIMEOUT40 | -1.24 | 30.8 |
| CROSS_CONFIRMED | WAVE_INVALIDATION_EXIT | -3.31 | 21.4 |
| TB_CONFIRMED | TP3_SL3_TIMEOUT20 | -1.29 | 28.6 |
| TB_CONFIRMED | TP5_SL3_TIMEOUT40 | -1.47 | 14.3 |
| TB_CONFIRMED | TP5_KTURN_TIMEOUT40 | -2.38 | 28.6 |
| TB_CONFIRMED | K_CROSS_DOWN_TIMEOUT40 | -3.24 | 16.7 |
| TB_CONFIRMED | WAVE_INVALIDATION_EXIT | -6.86 | 14.3 |

### 정책 랭킹 (score = avg_return × win_rate / 100)

1. **TP3_SL3_TIMEOUT20** — score -0.177, avg -0.46%, win 38.6%
2. **TP5_KTURN_TIMEOUT40** — score -0.199, avg -0.70%, win 28.6%
3. **TP5_SL3_TIMEOUT40** — score -0.243, avg -0.97%, win 25.0%
4. **K_CROSS_DOWN_TIMEOUT40** — score -0.355, avg -1.18%, win 30.2%
5. **WAVE_INVALIDATION_EXIT** — score -0.949, avg -3.01%, win 31.6%

## BTCUSDT 1d

- CSV: `wave_exit_BTCUSDT_1d.csv`
- PNG: `wave_exit_BTCUSDT_1d.png`
- episode×policy 행: 68

### 정책별 평균 수익률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 0.86 |
| TP5_SL3_TIMEOUT40 | 1.00 |
| TP5_KTURN_TIMEOUT40 | -0.41 |
| K_CROSS_DOWN_TIMEOUT40 | -0.69 |
| WAVE_INVALIDATION_EXIT | -5.55 |

### 정책별 중앙 수익률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 3.00 |
| TP5_SL3_TIMEOUT40 | 1.00 |
| TP5_KTURN_TIMEOUT40 | 1.08 |
| K_CROSS_DOWN_TIMEOUT40 | -0.69 |
| WAVE_INVALIDATION_EXIT | -2.95 |

### 정책별 승률 (%)

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 64.3 |
| TP5_SL3_TIMEOUT40 | 50.0 |
| TP5_KTURN_TIMEOUT40 | 57.1 |
| K_CROSS_DOWN_TIMEOUT40 | 30.8 |
| WAVE_INVALIDATION_EXIT | 30.8 |

### 정책별 평균 보유 봉 수

| policy | value |
|---|---:|
| TP3_SL3_TIMEOUT20 | 2.4 |
| TP5_SL3_TIMEOUT40 | 4.6 |
| TP5_KTURN_TIMEOUT40 | 3.7 |
| K_CROSS_DOWN_TIMEOUT40 | 18.5 |
| WAVE_INVALIDATION_EXIT | 25.4 |

### 정책별 평균 MFE / MAE (%)

| policy | avg MFE | avg MAE |
|---|---:|---:|
| TP3_SL3_TIMEOUT20 | 2.91 | -2.83 |
| TP5_SL3_TIMEOUT40 | 4.09 | -3.43 |
| TP5_KTURN_TIMEOUT40 | 3.47 | -3.46 |
| K_CROSS_DOWN_TIMEOUT40 | 7.97 | -7.29 |
| WAVE_INVALIDATION_EXIT | 7.57 | -10.01 |

### initial_type별 정책 성과

| initial_type | policy | avg return | win rate |
|---|---|---:|---:|
| SLOPE_CONFIRMED | TP3_SL3_TIMEOUT20 | 1.00 | 66.7 |
| SLOPE_CONFIRMED | TP5_SL3_TIMEOUT40 | 1.00 | 50.0 |
| SLOPE_CONFIRMED | TP5_KTURN_TIMEOUT40 | -0.35 | 58.3 |
| SLOPE_CONFIRMED | K_CROSS_DOWN_TIMEOUT40 | -0.72 | 27.3 |
| SLOPE_CONFIRMED | WAVE_INVALIDATION_EXIT | -5.37 | 27.3 |
| CROSS_CONFIRMED | TP3_SL3_TIMEOUT20 | 0.00 | 50.0 |
| CROSS_CONFIRMED | TP5_SL3_TIMEOUT40 | 1.00 | 50.0 |
| CROSS_CONFIRMED | TP5_KTURN_TIMEOUT40 | -0.80 | 50.0 |
| CROSS_CONFIRMED | K_CROSS_DOWN_TIMEOUT40 | -0.52 | 50.0 |
| CROSS_CONFIRMED | WAVE_INVALIDATION_EXIT | -6.58 | 50.0 |

### 정책 랭킹 (score = avg_return × win_rate / 100)

1. **TP3_SL3_TIMEOUT20** — score 0.551, avg 0.86%, win 64.3%
2. **TP5_SL3_TIMEOUT40** — score 0.500, avg 1.00%, win 50.0%
3. **K_CROSS_DOWN_TIMEOUT40** — score -0.211, avg -0.69%, win 30.8%
4. **TP5_KTURN_TIMEOUT40** — score -0.235, avg -0.41%, win 57.1%
5. **WAVE_INVALIDATION_EXIT** — score -1.709, avg -5.55%, win 30.8%

## ETH / BTC 비교

| policy | ETH avg | BTC avg | ETH win | BTC win |
|---|---:|---:|---:|---:|
| TP3_SL3_TIMEOUT20 | -0.46 | 0.86 | 38.6 | 64.3 |
| TP5_SL3_TIMEOUT40 | -0.97 | 1.00 | 25.0 | 50.0 |
| TP5_KTURN_TIMEOUT40 | -0.70 | -0.41 | 28.6 | 57.1 |
| K_CROSS_DOWN_TIMEOUT40 | -1.18 | -0.69 | 30.2 | 30.8 |
| WAVE_INVALIDATION_EXIT | -3.01 | -5.55 | 31.6 | 30.8 |
