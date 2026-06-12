# REPORT_WAVE_CONFIRMATION_GATE

Confirmation Gate Analysis — Post Early Warning Survival

- SUCCESS: 46
- FAILURE: 2099

## Top Gates

| gate | precision | recall | coverage | future GradeA rate |
|---|---:|---:|---:|---:|
| RSI_HOLD_+2 | 2.73% | 52.17% | 40.98% | 2.73% |
| RSI_HOLD_CUM_+2 | 2.65% | 39.13% | 31.70% | 2.65% |
| EMA20_RISE_+3 | 2.57% | 41.30% | 34.50% | 2.57% |
| RSI_HOLD_+1 | 2.57% | 58.70% | 49.04% | 2.57% |
| RSI_HOLD_CUM_+1 | 2.57% | 58.70% | 49.04% | 2.57% |
| EMA20_RISE_+2 | 2.56% | 47.83% | 40.00% | 2.56% |
| RSI_HOLD_+3 | 2.56% | 43.48% | 36.46% | 2.56% |
| EMA20_POS_+3 | 2.37% | 97.83% | 88.44% | 2.37% |
| K_SLOPE3_POS_+2 | 2.34% | 91.30% | 83.82% | 2.34% |
| EMA60_POS_+3 | 2.30% | 91.30% | 84.99% | 2.30% |
| K_SLOPE3_POS_+1 | 2.28% | 100.00% | 93.89% | 2.28% |
| KD_POS_+3 | 2.28% | 93.48% | 87.83% | 2.28% |
| K_SLOPE1_POS_+1 | 2.27% | 84.78% | 80.05% | 2.27% |
| EMA20_POS_+2 | 2.26% | 97.83% | 93.01% | 2.26% |
| K_SLOPE3_POS_+3 | 2.25% | 73.91% | 70.35% | 2.25% |
| K_SLOPE1_POS_+2 | 2.25% | 71.74% | 68.44% | 2.25% |
| EMA20_POS_+1 | 2.23% | 100.00% | 96.13% | 2.23% |
| KD_POS_+2 | 2.23% | 97.83% | 94.13% | 2.23% |
| RSI_HOLD_CUM_+3 | 2.21% | 23.91% | 23.22% | 2.21% |
| EMA20_RISE_+1 | 2.21% | 45.65% | 44.34% | 2.21% |

## Composite Gates

| gate | precision | recall | coverage | future GradeA rate |
|---|---:|---:|---:|---:|
| RSI_HOLD AND KD_POS AND EMA20_POS_+2 | 2.85% | 52.17% | 39.25% | 2.85% |
| RSI_HOLD AND EMA20_POS_+2 | 2.80% | 52.17% | 39.95% | 2.80% |
| RSI_HOLD AND KD_POS_+2 | 2.78% | 52.17% | 40.28% | 2.78% |
| RSI_HOLD AND K_SLOPE3_POS AND EMA20_POS_+2 | 2.73% | 47.83% | 37.53% | 2.73% |
| RSI_HOLD AND KD_POS AND EMA20_POS_+3 | 2.73% | 43.48% | 34.17% | 2.73% |
| RSI_HOLD AND K_SLOPE3_POS AND EMA20_POS_+1 | 2.71% | 58.70% | 46.43% | 2.71% |
| RSI_HOLD AND KD_POS_+3 | 2.67% | 43.48% | 34.87% | 2.67% |
| RSI_HOLD AND K_SLOPE3_POS_+2 | 2.67% | 47.83% | 38.37% | 2.67% |
| RSI_HOLD AND K_SLOPE3_POS AND KD_POS_+2 | 2.67% | 47.83% | 38.37% | 2.67% |
| RSI_HOLD AND K_SLOPE3_POS AND KD_POS_+1 | 2.66% | 58.70% | 47.27% | 2.66% |
| RSI_HOLD AND K_SLOPE3_POS_+1 | 2.65% | 58.70% | 47.41% | 2.65% |
| RSI_HOLD AND KD_POS AND EMA20_POS_+1 | 2.65% | 58.70% | 47.46% | 2.65% |
| RSI_HOLD AND EMA20_POS_+1 | 2.63% | 58.70% | 47.83% | 2.63% |
| RSI_HOLD AND EMA20_POS_+3 | 2.63% | 43.48% | 35.48% | 2.63% |
| RSI_HOLD AND KD_POS_+1 | 2.59% | 58.70% | 48.67% | 2.59% |
| RSI_HOLD AND K_SLOPE1_POS AND EMA20_POS_+1 | 2.48% | 50.00% | 43.22% | 2.48% |
| RSI_HOLD AND K_SLOPE1_POS AND K_SLOPE3_POS_+1 | 2.45% | 50.00% | 43.68% | 2.45% |
| K_SLOPE3_POS AND KD_POS AND EMA20_POS_+2 | 2.44% | 91.30% | 80.28% | 2.44% |
| RSI_HOLD AND K_SLOPE1_POS AND KD_POS_+1 | 2.44% | 50.00% | 44.01% | 2.44% |
| RSI_HOLD AND K_SLOPE1_POS_+1 | 2.43% | 50.00% | 44.06% | 2.43% |

## Gate Funnel

| stage | survivors |
|---|---:|
| Early Warning | 2145 |
| Gate +1 | 691 |
| Gate +2 | 425 |
| Gate +3 | 299 |
| Grade A | 46 |

## Best Horizon

- horizon: **+2**
- gate: RSI_HOLD_+2
- precision: 2.73%
- recall: 52.17%

## Success vs Failure

| feature | horizon | success | failure | effect |
|---|---:|---:|---:|---:|
| major_k_minus_d | 1 | 15.86 | 12.62 | 0.41 |
| major_k_minus_d | 2 | 14.40 | 11.49 | 0.36 |
| macd_hist | 1 | 12.66 | 60.55 | 0.30 |
| major_k_minus_d | 3 | 12.16 | 9.76 | 0.28 |
| macd_hist | 2 | 11.99 | 52.87 | 0.26 |
| major_k_slope_3 | 1 | 10.12 | 8.50 | 0.26 |
| macd_hist | 3 | 8.82 | 44.47 | 0.24 |
| major_k_slope_3 | 2 | 8.06 | 6.71 | 0.20 |
| major_k | 3 | 77.00 | 75.04 | 0.18 |
| major_k_slope_1 | 1 | 2.66 | 2.22 | 0.17 |
| major_k | 2 | 76.10 | 74.34 | 0.15 |
| major_k_slope_1 | 2 | 1.83 | 1.40 | 0.15 |
| major_k_slope_3 | 3 | 5.39 | 4.31 | 0.14 |
| major_k | 1 | 74.27 | 72.95 | 0.11 |
| ema20_slope_3 | 1 | 0.61 | 0.69 | 0.09 |
| ema20_slope_3 | 2 | 0.57 | 0.63 | 0.07 |
| major_k_slope_1 | 3 | 0.89 | 0.70 | 0.07 |
| ema60_slope_3 | 1 | 0.26 | 0.29 | 0.05 |
| ema20_slope_3 | 3 | 0.52 | 0.56 | 0.05 |
| ema60_slope_3 | 2 | 0.26 | 0.28 | 0.04 |

## ETH / BTC / SOL / BNB 비교

- reference gate: RSI_HOLD_+2

| symbol | n | precision | recall | future GradeA rate |
|---|---:|---:|---:|---:|
| ETHUSDT | 487 | 8.70% | 46.15% | 8.70% |
| BTCUSDT | 548 | 0.45% | 100.00% | 0.45% |
| SOLUSDT | 509 | 2.43% | 83.33% | 2.43% |
| BNBUSDT | 601 | 0.00% | — | 0.00% |

- PNG: `wave_confirmation_gate.png`
