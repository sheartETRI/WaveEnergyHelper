# REPORT_WAVE_GRADE_ORIGIN

Grade A Origin Analysis — BASE_RULE + major_k≥70

- GRADE_A events: 7
- GRADE_BC events: 30
- GRADE_D (RULE_A ref): 142

## Grade A vs BC

| feature | A mean | BC mean | delta | effect |
|---|---:|---:|---:|---:|
| major_k | 76.51 | 47.64 | 28.87 | 3.02 |
| major_k_minus_d | 4.59 | -13.19 | 17.78 | 2.50 |
| major_k_slope_3 | -0.97 | -8.17 | 7.20 | 1.42 |
| major_d | 71.92 | 60.83 | 11.09 | 1.18 |
| ema20_slope_3 | 0.40 | 0.09 | 0.31 | 1.12 |
| macd | 105.01 | 21.37 | 83.64 | 0.83 |
| dist_ema20_pct | 1.46 | 0.66 | 0.80 | 0.80 |
| rsi | 59.53 | 55.88 | 3.65 | 0.73 |
| ema60_slope_3 | 0.22 | 0.13 | 0.09 | 0.58 |
| macd_signal | 127.13 | 47.35 | 79.77 | 0.54 |
| rsi_slope_3 | 3.35 | 6.57 | -3.22 | 0.53 |
| major_k_slope_1 | -1.18 | -1.90 | 0.71 | 0.46 |
| dist_ema60_pct | 2.42 | 1.68 | 0.74 | 0.45 |
| rsi_slope_1 | 0.76 | 2.25 | -1.50 | 0.35 |
| atr_pct | 1.48 | 1.35 | 0.13 | 0.10 |

## Top Separators

| rank | feature | effect_size | A | BC |
|---:|---|---:|---:|---:|
| 1 | major_k | 3.02 | 76.51 | 47.64 |
| 2 | major_k_minus_d | 2.50 | 4.59 | -13.19 |
| 3 | major_k_slope_3 | 1.42 | -0.97 | -8.17 |
| 4 | major_d | 1.18 | 71.92 | 60.83 |
| 5 | ema20_slope_3 | 1.12 | 0.40 | 0.09 |
| 6 | macd | 0.83 | 105.01 | 21.37 |
| 7 | dist_ema20_pct | 0.80 | 1.46 | 0.66 |
| 8 | rsi | 0.73 | 59.53 | 55.88 |
| 9 | ema60_slope_3 | 0.58 | 0.22 | 0.13 |
| 10 | macd_signal | 0.54 | 127.13 | 47.35 |
| 11 | rsi_slope_3 | 0.53 | 3.35 | 6.57 |
| 12 | major_k_slope_1 | 0.46 | -1.18 | -1.90 |
| 13 | dist_ema60_pct | 0.45 | 2.42 | 1.68 |
| 14 | rsi_slope_1 | 0.35 | 0.76 | 2.25 |
| 15 | atr_pct | 0.10 | 1.48 | 1.35 |
| 16 | macd_hist | 0.06 | -22.11 | -25.98 |
| 17 | macd_gap | 0.06 | -22.11 | -25.98 |
| 18 | ema120_slope_3 | 0.05 | 0.10 | 0.09 |
| 19 | dist_ema120_pct | 0.03 | 2.24 | 2.11 |
| 20 | volatility_20 | 0.00 | 0.92 | 0.92 |

## Lead Indicators

| feature | effect_size | lead_bars | A | BC |
|---|---:|---:|---:|---:|
| major_k_slope_1 | 3.00 | 5 | 3.18 | -3.13 |
| major_k_slope_3 | 2.96 | 5 | 10.13 | -6.95 |
| major_k_minus_d | 2.81 | 5 | 15.95 | -6.20 |
| dist_ema20_pct | 1.97 | 5 | 1.45 | -0.29 |
| major_d | 1.66 | 10 | 44.53 | 70.09 |
| major_k_slope_3 | 1.63 | 10 | 10.58 | 1.14 |
| major_k | 1.53 | 20 | 38.55 | 65.45 |
| major_k_slope_1 | 1.51 | 10 | 4.14 | 0.40 |
| ema20_slope_3 | 1.51 | 5 | 0.51 | 0.01 |
| rsi | 1.47 | 5 | 58.85 | 50.61 |
| rsi | 1.23 | 20 | 47.98 | 58.65 |
| major_k | 1.21 | 10 | 55.12 | 72.37 |
| rsi_slope_3 | 1.08 | 10 | 6.96 | -1.41 |
| major_k_minus_d | 1.05 | 10 | 10.59 | 2.28 |
| major_d | 0.97 | 5 | 57.42 | 70.12 |
| major_k | 0.90 | 5 | 73.37 | 63.92 |
| major_k_minus_d | 0.88 | 20 | -5.15 | 5.83 |
| major_d | 0.85 | 20 | 43.70 | 59.61 |
| ema20_slope_3 | 0.79 | 20 | -0.16 | 0.46 |
| rsi_slope_1 | 0.77 | 5 | 0.44 | -2.62 |

## Origin Timeline

| offset | major_k | rsi | macd | ema20_slope | atr |
|---:|---:|---:|---:|---:|---:|
| -20 | 38.55 | 47.98 | -13.42 | -0.16 | 1.52 |
| -10 | 55.12 | 59.71 | 159.42 | 0.49 | 1.37 |
| -5 | 73.37 | 58.85 | 148.65 | 0.51 | 1.47 |
| -3 | 77.49 | 56.18 | 126.20 | 0.38 | 1.44 |
| -1 | 77.70 | 58.78 | 111.56 | 0.34 | 1.45 |
| 0 | 76.51 | 59.53 | 105.01 | 0.40 | 1.48 |

## Path Distribution (GRADE_A)

| path | count | pct |
|---|---:|---:|
| WAVE3_CANDIDATE → WAVE3_ACTIVE → DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRE | 1 | 25.00 |
| WAVE3_CANDIDATE → WAVE3_ACTIVE → DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRE | 1 | 25.00 |
| WAVE3_CANDIDATE → WAVE3_ACTIVE → DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRE | 1 | 25.00 |
| WAVE3_CANDIDATE → WAVE3_ACTIVE → DOUBLE_BOTTOM → TRIPLE_BOTTOM_REQUIRE | 1 | 25.00 |

## Branch Distribution

| branch | A | BC |
|---|---:|---:|
| TRIPLE_BOTTOM_REQUIRED | 5 | 0 |

## Pseudo-Causality Order (관측용)

| order | feature | bars_before |
|---:|---|---:|
| 1 | EMA slope | 20 |
| 2 | RSI | 20 |
| 3 | major_k | 20 |
| 4 | MACD | 18 |

## ETH / BTC / SOL / BNB 비교

| symbol | A n | BC n | top separator | effect | A major_k | BC major_k |
|---|---:|---:|---|---:|---:|---:|
| ETHUSDT | 5 | 1 | macd_hist | 5.67 | 77.18 | 51.26 |
| BTCUSDT | 1 | 6 | macd | 9.90 | 70.82 | 41.45 |
| SOLUSDT | 1 | 10 | major_k_minus_d | 3.94 | 78.86 | 51.92 |
| BNBUSDT | 0 | 13 | ema20_slope_3 | 0.00 | — | 46.93 |

- PNG: `wave_grade_origin.png`
