# REPORT_WAVE_GRADE_EARLY_WARNING

Grade A Early Warning — Pre-Formation Observation

- Grade A events: 7
- Best Horizon: -5 (avg effect 0.58)

## Top Early Separators

| feature | effect | offset | pos_mean | neg_mean |
|---|---:|---:|---:|---:|
| major_k_minus_d | 1.28 | -5 | 15.95 | 0.00 |
| major_k_slope_1 | 1.22 | -10 | 4.14 | 0.00 |
| major_k_slope_3 | 1.11 | -10 | 10.58 | 0.01 |
| major_k | 1.10 | -5 | 73.37 | 48.30 |
| major_k_slope_3 | 1.07 | -5 | 10.13 | 0.01 |
| major_k_slope_1 | 0.93 | -5 | 3.18 | 0.00 |
| rsi | 0.93 | -10 | 59.71 | 48.25 |
| rsi_slope_3 | 0.89 | -10 | 6.96 | -0.03 |
| rsi | 0.86 | -5 | 58.85 | 48.25 |
| major_k_minus_d | 0.85 | -10 | 10.59 | 0.00 |
| ema20_slope_3 | 0.65 | -5 | 0.51 | -0.14 |
| ema20_slope_3 | 0.62 | -10 | 0.49 | -0.14 |
| ema60_slope_3 | 0.60 | -5 | 0.22 | -0.14 |
| rsi_slope_3 | 0.56 | -5 | -4.43 | -0.03 |
| ema60_slope_3 | 0.48 | -10 | 0.15 | -0.14 |
| major_d | 0.43 | -5 | 57.42 | 48.39 |
| macd_signal | 0.38 | -5 | 148.57 | -58.13 |
| macd | 0.38 | -10 | 159.42 | -57.92 |
| macd | 0.36 | -5 | 148.65 | -57.92 |
| atr_pct | 0.35 | -10 | 1.37 | 1.95 |

## Best Horizon

| offset | avg_effect |
|---:|---:|
| -10 | 0.56 |
| -5 ** | 0.58 |

## Top Candidates

| candidate | precision | recall | coverage | future GradeA rate |
|---|---:|---:|---:|---:|
| major_k_slope_1>0 AND major_k_minus_d>0 AND macd>0 | 0.29% | 85.71% | 17.58% | 0.29% |
| major_k_slope_1>0 AND major_k_slope_3>0 AND macd>0 | 0.26% | 85.71% | 19.02% | 0.26% |
| major_k_slope_3>0 AND major_k_minus_d>0 AND macd>0 | 0.25% | 85.71% | 19.75% | 0.25% |
| major_k_slope_1>0 AND rsi>50 AND macd>0 | 0.24% | 85.71% | 20.58% | 0.24% |
| major_k_slope_1>0 AND ema20_slope_3>0 AND macd>0 | 0.24% | 85.71% | 20.80% | 0.24% |
| major_k_slope_3>0 AND rsi>50 AND macd>0 | 0.24% | 85.71% | 21.03% | 0.24% |
| major_k_slope_1>0 AND macd>0 | 0.23% | 85.71% | 21.33% | 0.23% |
| major_k_slope_3>0 AND ema20_slope_3>0 AND macd>0 | 0.23% | 85.71% | 21.63% | 0.23% |
| major_k_minus_d>0 AND rsi>50 AND macd>0 | 0.23% | 85.71% | 21.68% | 0.23% |
| major_k_slope_3>0 AND macd>0 | 0.23% | 85.71% | 22.22% | 0.23% |
| major_k_minus_d>0 AND ema20_slope_3>0 AND macd>0 | 0.22% | 85.71% | 22.41% | 0.22% |
| major_k_slope_1>0 AND major_k_minus_d>0 AND rsi>50 | 0.22% | 85.71% | 22.88% | 0.22% |
| major_k_minus_d>0 AND macd>0 | 0.21% | 85.71% | 23.44% | 0.21% |
| major_k_slope_1>0 AND major_k_minus_d>0 AND ema20_slope_3>0 | 0.21% | 85.71% | 24.43% | 0.21% |
| major_k_slope_3>0 AND major_k_minus_d>0 AND rsi>50 | 0.20% | 85.71% | 24.66% | 0.20% |

## Precision / Recall (Best Candidate)

- candidate: major_k_slope_1>0 AND major_k_minus_d>0 AND macd>0
- precision: 0.29%
- recall: 85.71%
- TP/FP/FN: 6/2099/1

## Future Grade A Rate

| candidate | rate | fired |
|---|---:|---:|
| major_k_slope_1>0 AND major_k_minus_d>0 AND macd>0 | 0.29% | 2105 |
| major_k_slope_1>0 AND major_k_slope_3>0 AND macd>0 | 0.26% | 2278 |
| major_k_slope_3>0 AND major_k_minus_d>0 AND macd>0 | 0.25% | 2365 |
| major_k_slope_1>0 AND rsi>50 AND macd>0 | 0.24% | 2465 |
| major_k_slope_1>0 AND ema20_slope_3>0 AND macd>0 | 0.24% | 2491 |
| major_k_slope_3>0 AND rsi>50 AND macd>0 | 0.24% | 2519 |
| major_k_slope_1>0 AND macd>0 | 0.23% | 2555 |
| major_k_slope_3>0 AND ema20_slope_3>0 AND macd>0 | 0.23% | 2591 |
| major_k_minus_d>0 AND rsi>50 AND macd>0 | 0.23% | 2597 |
| major_k_slope_3>0 AND macd>0 | 0.23% | 2661 |

## False Positive Analysis

| cause | count | pct |
|---|---:|---:|
| major_k_reversal | 852 | 40.59 |
| rsi_drop | 1069 | 50.93 |
| ema_slope_bad | 247 | 11.77 |
| macd_weak | 378 | 18.01 |

## Formation Order (관측용)

| order | feature | offset | effect |
|---:|---|---:|---:|
| 1 | major_k_minus_d | -5 | 1.28 |
| 2 | major_k | -5 | 1.10 |
| 3 | major_k_slope_3 | -5 | 1.07 |
| 4 | major_k_slope_1 | -5 | 0.93 |
| 5 | rsi | -5 | 0.86 |
| 6 | ema20_slope_3 | -5 | 0.65 |
| 7 | ema60_slope_3 | -5 | 0.60 |
| 8 | rsi_slope_3 | -5 | 0.56 |
| 9 | major_d | -5 | 0.43 |
| 10 | macd_signal | -5 | 0.38 |

## ETH / BTC / SOL / BNB 비교

| symbol | pos snapshots | top feature | effect |
|---|---:|---|---:|
| ETHUSDT | 10 | major_k_minus_d | 1.23 |
| BTCUSDT | 2 | major_k_minus_d | 0.47 |
| SOLUSDT | 2 | major_k_minus_d | 0.98 |
| BNBUSDT | 0 | major_k_minus_d | 0.00 |

- PNG: `wave_grade_early_warning.png`
