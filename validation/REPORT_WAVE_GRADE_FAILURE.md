# REPORT_WAVE_GRADE_FAILURE

Grade A Failure Analysis — Early Warning Collapse

- SUCCESS: 46
- FAILURE: 2099

## Failure Causes

| cause | count | pct |
|---|---:|---:|
| RSI_DROP | 2095 | 99.81 |
| MAJOR_K_REVERSAL | 2015 | 96.00 |
| MACD_WEAKENING | 2096 | 99.86 |
| EMA_SLOPE_BAD | 999 | 47.59 |
| MULTI_FAILURE | 2090 | 99.57 |

## Failure Timing

| horizon | count | failure pct |
|---:|---:|---:|
| 1 | 1467 | 69.89 |
| 3 | 1983 | 94.47 |
| 5 | 2085 | 99.33 |
| 10 | 2099 | 100.00 |

## First Failure

| rank | first failure | count | pct |
|---:|---|---:|---:|
| 1 | RSI_DROP | 1654 | 78.80 |
| 2 | MACD_WEAKENING | 313 | 14.91 |
| 3 | MAJOR_K_REVERSAL | 125 | 5.96 |
| 4 | EMA_SLOPE_BAD | 7 | 0.33 |

## Success vs Failure

| feature | success | failure | delta | effect |
|---|---:|---:|---:|---:|
| major_k_minus_d | 16.52 | 12.91 | 3.60 | 0.45 |
| major_k_slope_3 | 11.43 | 9.46 | 1.97 | 0.32 |
| macd_hist | 14.09 | 65.00 | -50.91 | 0.31 |
| macd | 42.53 | 156.42 | -113.89 | 0.29 |
| major_k_slope_1 | 3.56 | 3.10 | 0.47 | 0.22 |
| rsi | 60.84 | 61.97 | -1.13 | 0.15 |
| atr_pct | 1.52 | 1.65 | -0.13 | 0.10 |
| ema20_slope_3 | 0.62 | 0.70 | -0.08 | 0.10 |
| rsi_slope_1 | 0.09 | 0.47 | -0.37 | 0.08 |
| major_k | 71.61 | 70.73 | 0.88 | 0.07 |
| ema60_slope_3 | 0.26 | 0.28 | -0.02 | 0.05 |
| volatility_20 | 1.07 | 1.10 | -0.03 | 0.04 |

## Top Separators

| rank | feature | effect_size | success | failure |
|---:|---|---:|---:|---:|
| 1 | major_k_minus_d | 0.45 | 16.52 | 12.91 |
| 2 | major_k_slope_3 | 0.32 | 11.43 | 9.46 |
| 3 | macd_hist | 0.31 | 14.09 | 65.00 |
| 4 | macd | 0.29 | 42.53 | 156.42 |
| 5 | major_k_slope_1 | 0.22 | 3.56 | 3.10 |
| 6 | rsi | 0.15 | 60.84 | 61.97 |
| 7 | atr_pct | 0.10 | 1.52 | 1.65 |
| 8 | ema20_slope_3 | 0.10 | 0.62 | 0.70 |
| 9 | rsi_slope_1 | 0.08 | 0.09 | 0.47 |
| 10 | major_k | 0.07 | 71.61 | 70.73 |
| 11 | ema60_slope_3 | 0.05 | 0.26 | 0.28 |
| 12 | volatility_20 | 0.04 | 1.07 | 1.10 |

## Failure Path

| path | count | pct |
|---|---:|---:|
| WAVE3_COMPLETED | 103 | 4.91 |
| TRIPLE_BOTTOM_REQUIRED | 35 | 1.67 |
| INVALIDATED | 2 | 0.10 |
| OTHER | 1959 | 93.33 |

## Failure Branch

| branch | success | failure |
|---|---:|---:|
| WAVE3_COMPLETED | 0 | 3 |
| TRIPLE_BOTTOM_REQUIRED | 0 | 1 |

## Failure Regime

| feature | success | failure | effect |
|---|---:|---:|---:|
| rsi | 60.84 | 61.97 | 0.15 |
| atr_pct | 1.52 | 1.65 | 0.10 |
| ema20_slope_3 | 0.62 | 0.70 | 0.10 |
| major_k | 71.61 | 70.73 | 0.07 |
| volatility_20 | 1.07 | 1.10 | 0.04 |

## Escalation Timeline

| offset | success major_k | failure major_k | success rsi | failure rsi |
|---:|---:|---:|---:|---:|
| 0 | 71.61 | 70.73 | 60.84 | 61.97 |
| 1 | 74.27 | 72.95 | 60.74 | 60.93 |
| 3 | 77.00 | 75.04 | 58.81 | 59.11 |
| 5 | 76.61 | 74.59 | 58.09 | 57.73 |
| 10 | 66.24 | 65.53 | 53.25 | 55.04 |

## False Positive Funnel

| stage | survivors |
|---|---:|
| Early Warning | 2145 |
| 5-bar maintain | 902 |
| 10-bar maintain | 336 |
| Grade A | 46 |

## ETH / BTC / SOL / BNB 비교

| symbol | success | failure | top cause | pct |
|---|---:|---:|---|---:|
| ETHUSDT | 39 | 448 | RSI_DROP | 100.00 |
| BTCUSDT | 1 | 547 | RSI_DROP | 100.00 |
| SOLUSDT | 6 | 503 | RSI_DROP | 100.00 |
| BNBUSDT | 0 | 601 | RSI_DROP | 99.33 |

- PNG: `wave_grade_failure.png`
