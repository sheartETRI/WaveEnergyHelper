# REPORT_WAVE_CROSS_MARKET_VALIDATION

Cross Market Validation — Champion Rule 다시장 재현

- cells: 12

## 1. Cross Market Matrix

| symbol | tf | rule | n | win_rate | expectancy |
|---|---|---|---:|---:|---:|
| ETHUSDT | 1h | RULE_A | 0 | — | — |
| ETHUSDT | 1h | RULE_B | 0 | — | — |
| ETHUSDT | 1h | RULE_C | 0 | — | — |
| ETHUSDT | 1h | RULE_D | 0 | — | — |
| ETHUSDT | 1h | RULE_E | 0 | — | — |
| ETHUSDT | 4h | RULE_A | 1 | 0.00% | -0.29 |
| ETHUSDT | 4h | RULE_B | 1 | 0.00% | -0.29 |
| ETHUSDT | 4h | RULE_C | 1 | 0.00% | -0.29 |
| ETHUSDT | 4h | RULE_D | 4 | 75.00% | 2.18 |
| ETHUSDT | 4h | RULE_E | 0 | — | — |
| ETHUSDT | 1d | RULE_A | 1 | 0.00% | -3.00 |
| ETHUSDT | 1d | RULE_B | 1 | 0.00% | -3.00 |
| ETHUSDT | 1d | RULE_C | 1 | 0.00% | -3.00 |
| ETHUSDT | 1d | RULE_D | 2 | 50.00% | 0.00 |
| ETHUSDT | 1d | RULE_E | 0 | — | — |
| BTCUSDT | 1h | RULE_A | 1 | 100.00% | 0.49 |
| BTCUSDT | 1h | RULE_B | 1 | 100.00% | 0.49 |
| BTCUSDT | 1h | RULE_C | 1 | 100.00% | 0.49 |
| BTCUSDT | 1h | RULE_D | 4 | 25.00% | -1.19 |
| BTCUSDT | 1h | RULE_E | 0 | — | — |
| BTCUSDT | 4h | RULE_A | 6 | 33.33% | -0.11 |
| BTCUSDT | 4h | RULE_B | 6 | 33.33% | -0.11 |
| BTCUSDT | 4h | RULE_C | 6 | 33.33% | -0.11 |
| BTCUSDT | 4h | RULE_D | 13 | 46.15% | 0.13 |
| BTCUSDT | 4h | RULE_E | 0 | — | — |
| BTCUSDT | 1d | RULE_A | 0 | — | — |
| BTCUSDT | 1d | RULE_B | 0 | — | — |
| BTCUSDT | 1d | RULE_C | 0 | — | — |
| BTCUSDT | 1d | RULE_D | 0 | — | — |
| BTCUSDT | 1d | RULE_E | 0 | — | — |
| SOLUSDT | 1h | RULE_A | 2 | 0.00% | -1.61 |
| SOLUSDT | 1h | RULE_B | 2 | 0.00% | -1.61 |
| SOLUSDT | 1h | RULE_C | 2 | 0.00% | -1.61 |
| SOLUSDT | 1h | RULE_D | 6 | 50.00% | 0.46 |
| SOLUSDT | 1h | RULE_E | 0 | — | — |
| SOLUSDT | 4h | RULE_A | 4 | 75.00% | 1.50 |
| SOLUSDT | 4h | RULE_B | 4 | 75.00% | 1.50 |
| SOLUSDT | 4h | RULE_C | 4 | 75.00% | 1.50 |
| SOLUSDT | 4h | RULE_D | 10 | 60.00% | 0.60 |
| SOLUSDT | 4h | RULE_E | 0 | — | — |
| SOLUSDT | 1d | RULE_A | 0 | — | — |
| SOLUSDT | 1d | RULE_B | 0 | — | — |
| SOLUSDT | 1d | RULE_C | 0 | — | — |
| SOLUSDT | 1d | RULE_D | 0 | — | — |
| SOLUSDT | 1d | RULE_E | 0 | — | — |
| BNBUSDT | 1h | RULE_A | 3 | 100.00% | 0.80 |
| BNBUSDT | 1h | RULE_B | 3 | 100.00% | 0.80 |
| BNBUSDT | 1h | RULE_C | 4 | 100.00% | 0.88 |
| BNBUSDT | 1h | RULE_D | 7 | 85.71% | 0.52 |
| BNBUSDT | 1h | RULE_E | 0 | — | — |
| BNBUSDT | 4h | RULE_A | 4 | 100.00% | 3.00 |
| BNBUSDT | 4h | RULE_B | 4 | 100.00% | 3.00 |
| BNBUSDT | 4h | RULE_C | 4 | 100.00% | 3.00 |
| BNBUSDT | 4h | RULE_D | 9 | 77.78% | 1.67 |
| BNBUSDT | 4h | RULE_E | 0 | — | — |
| BNBUSDT | 1d | RULE_A | 0 | — | — |
| BNBUSDT | 1d | RULE_B | 0 | — | — |
| BNBUSDT | 1d | RULE_C | 0 | — | — |
| BNBUSDT | 1d | RULE_D | 1 | 0.00% | -3.00 |
| BNBUSDT | 1d | RULE_E | 0 | — | — |

## 2. Positive Cell Ratio

| rule | positive_cells | total_cells | positive_ratio |
|---|---:|---:|---:|
| RULE_A | 4 | 8 | 50.00% |
| RULE_B | 4 | 8 | 50.00% |
| RULE_C | 4 | 8 | 50.00% |
| RULE_D | 7 | 9 | 77.78% |
| RULE_E | 0 | 0 | 0.00% |

## 3. Train/Test Split

| rule | symbol | tf | dataset | n | win_rate | expectancy |
|---|---|---|---|---:|---:|---:|
| RULE_A | ETHUSDT | 4h | TRAIN | 1 | 0.00% | -0.29 |
| RULE_B | ETHUSDT | 4h | TRAIN | 1 | 0.00% | -0.29 |
| RULE_C | ETHUSDT | 4h | TRAIN | 1 | 0.00% | -0.29 |
| RULE_D | ETHUSDT | 4h | TRAIN | 2 | 100.00% | 3.00 |
| RULE_D | ETHUSDT | 4h | TEST | 2 | 50.00% | 1.36 |
| RULE_A | ETHUSDT | 1d | TRAIN | 1 | 0.00% | -3.00 |
| RULE_B | ETHUSDT | 1d | TRAIN | 1 | 0.00% | -3.00 |
| RULE_C | ETHUSDT | 1d | TRAIN | 1 | 0.00% | -3.00 |
| RULE_D | ETHUSDT | 1d | TRAIN | 1 | 100.00% | 3.00 |
| RULE_D | ETHUSDT | 1d | TEST | 1 | 0.00% | -3.00 |
| RULE_A | BTCUSDT | 1h | TRAIN | 1 | 100.00% | 0.49 |
| RULE_B | BTCUSDT | 1h | TRAIN | 1 | 100.00% | 0.49 |
| RULE_C | BTCUSDT | 1h | TRAIN | 1 | 100.00% | 0.49 |
| RULE_D | BTCUSDT | 1h | TRAIN | 2 | 50.00% | -0.13 |
| RULE_D | BTCUSDT | 1h | TEST | 2 | 0.00% | -2.25 |
| RULE_A | BTCUSDT | 4h | TRAIN | 4 | 50.00% | 0.59 |
| RULE_A | BTCUSDT | 4h | TEST | 2 | 0.00% | -1.51 |
| RULE_B | BTCUSDT | 4h | TRAIN | 4 | 50.00% | 0.59 |
| RULE_B | BTCUSDT | 4h | TEST | 2 | 0.00% | -1.51 |
| RULE_C | BTCUSDT | 4h | TRAIN | 4 | 50.00% | 0.59 |
| RULE_C | BTCUSDT | 4h | TEST | 2 | 0.00% | -1.51 |
| RULE_D | BTCUSDT | 4h | TRAIN | 9 | 55.56% | 0.59 |
| RULE_D | BTCUSDT | 4h | TEST | 4 | 25.00% | -0.92 |
| RULE_A | SOLUSDT | 1h | TRAIN | 2 | 0.00% | -1.61 |
| RULE_B | SOLUSDT | 1h | TRAIN | 2 | 0.00% | -1.61 |
| RULE_C | SOLUSDT | 1h | TRAIN | 2 | 0.00% | -1.61 |
| RULE_D | SOLUSDT | 1h | TRAIN | 4 | 75.00% | 1.50 |
| RULE_D | SOLUSDT | 1h | TEST | 2 | 0.00% | -1.61 |
| RULE_A | SOLUSDT | 4h | TRAIN | 2 | 50.00% | -0.00 |
| RULE_A | SOLUSDT | 4h | TEST | 2 | 100.00% | 3.00 |
| RULE_B | SOLUSDT | 4h | TRAIN | 2 | 50.00% | -0.00 |
| RULE_B | SOLUSDT | 4h | TEST | 2 | 100.00% | 3.00 |
| RULE_C | SOLUSDT | 4h | TRAIN | 3 | 66.67% | 1.00 |
| RULE_C | SOLUSDT | 4h | TEST | 1 | 100.00% | 3.00 |
| RULE_D | SOLUSDT | 4h | TRAIN | 7 | 57.14% | 0.43 |
| RULE_D | SOLUSDT | 4h | TEST | 3 | 66.67% | 1.00 |
| RULE_A | BNBUSDT | 1h | TRAIN | 2 | 100.00% | 1.01 |
| RULE_A | BNBUSDT | 1h | TEST | 1 | 100.00% | 0.37 |
| RULE_B | BNBUSDT | 1h | TRAIN | 2 | 100.00% | 1.01 |
| RULE_B | BNBUSDT | 1h | TEST | 1 | 100.00% | 0.37 |
| RULE_C | BNBUSDT | 1h | TRAIN | 2 | 100.00% | 1.01 |
| RULE_C | BNBUSDT | 1h | TEST | 2 | 100.00% | 0.74 |
| RULE_D | BNBUSDT | 1h | TRAIN | 4 | 100.00% | 1.49 |
| RULE_D | BNBUSDT | 1h | TEST | 3 | 66.67% | -0.79 |
| RULE_A | BNBUSDT | 4h | TRAIN | 2 | 100.00% | 3.00 |
| RULE_A | BNBUSDT | 4h | TEST | 2 | 100.00% | 3.00 |
| RULE_B | BNBUSDT | 4h | TRAIN | 2 | 100.00% | 3.00 |
| RULE_B | BNBUSDT | 4h | TEST | 2 | 100.00% | 3.00 |
| RULE_C | BNBUSDT | 4h | TRAIN | 2 | 100.00% | 3.00 |
| RULE_C | BNBUSDT | 4h | TEST | 2 | 100.00% | 3.00 |
| RULE_D | BNBUSDT | 4h | TRAIN | 6 | 66.67% | 1.00 |
| RULE_D | BNBUSDT | 4h | TEST | 3 | 100.00% | 3.00 |
| RULE_D | BNBUSDT | 1d | TRAIN | 1 | 0.00% | -3.00 |

## 4. Drift Analysis

| rule | symbol | tf | train_exp | test_exp | exp_drift | wr_drift |
|---|---|---|---:|---:|---:|---:|
| RULE_A | SOLUSDT | 1h | -1.61 | — | — | — |
| RULE_A | SOLUSDT | 4h | -0.00 | 3.00 | 3.00 | 50.00% |
| RULE_A | SOLUSDT | 1d | — | — | — | — |
| RULE_A | BTCUSDT | 1h | 0.49 | — | — | — |
| RULE_A | BTCUSDT | 4h | 0.59 | -1.51 | -2.10 | -50.00% |
| RULE_A | BTCUSDT | 1d | — | — | — | — |
| RULE_A | BNBUSDT | 1h | 1.01 | 0.37 | -0.64 | 0.00% |
| RULE_A | BNBUSDT | 4h | 3.00 | 3.00 | 0.00 | 0.00% |
| RULE_A | BNBUSDT | 1d | — | — | — | — |
| RULE_A | ETHUSDT | 1h | — | — | — | — |
| RULE_A | ETHUSDT | 4h | -0.29 | — | — | — |
| RULE_A | ETHUSDT | 1d | -3.00 | — | — | — |
| RULE_B | SOLUSDT | 1h | -1.61 | — | — | — |
| RULE_B | SOLUSDT | 4h | -0.00 | 3.00 | 3.00 | 50.00% |
| RULE_B | SOLUSDT | 1d | — | — | — | — |
| RULE_B | BTCUSDT | 1h | 0.49 | — | — | — |
| RULE_B | BTCUSDT | 4h | 0.59 | -1.51 | -2.10 | -50.00% |
| RULE_B | BTCUSDT | 1d | — | — | — | — |
| RULE_B | BNBUSDT | 1h | 1.01 | 0.37 | -0.64 | 0.00% |
| RULE_B | BNBUSDT | 4h | 3.00 | 3.00 | 0.00 | 0.00% |
| RULE_B | BNBUSDT | 1d | — | — | — | — |
| RULE_B | ETHUSDT | 1h | — | — | — | — |
| RULE_B | ETHUSDT | 4h | -0.29 | — | — | — |
| RULE_B | ETHUSDT | 1d | -3.00 | — | — | — |
| RULE_C | SOLUSDT | 1h | -1.61 | — | — | — |
| RULE_C | SOLUSDT | 4h | 1.00 | 3.00 | 2.00 | 33.33% |
| RULE_C | SOLUSDT | 1d | — | — | — | — |
| RULE_C | BTCUSDT | 1h | 0.49 | — | — | — |
| RULE_C | BTCUSDT | 4h | 0.59 | -1.51 | -2.10 | -50.00% |
| RULE_C | BTCUSDT | 1d | — | — | — | — |
| RULE_C | BNBUSDT | 1h | 1.01 | 0.74 | -0.27 | 0.00% |
| RULE_C | BNBUSDT | 4h | 3.00 | 3.00 | 0.00 | 0.00% |
| RULE_C | BNBUSDT | 1d | — | — | — | — |
| RULE_C | ETHUSDT | 1h | — | — | — | — |
| RULE_C | ETHUSDT | 4h | -0.29 | — | — | — |
| RULE_C | ETHUSDT | 1d | -3.00 | — | — | — |
| RULE_D | SOLUSDT | 1h | 1.50 | -1.61 | -3.11 | -75.00% |
| RULE_D | SOLUSDT | 4h | 0.43 | 1.00 | 0.57 | 9.52% |
| RULE_D | SOLUSDT | 1d | — | — | — | — |
| RULE_D | BTCUSDT | 1h | -0.13 | -2.25 | -2.12 | -50.00% |
| RULE_D | BTCUSDT | 4h | 0.59 | -0.92 | -1.51 | -30.56% |
| RULE_D | BTCUSDT | 1d | — | — | — | — |
| RULE_D | BNBUSDT | 1h | 1.49 | -0.79 | -2.28 | -33.33% |
| RULE_D | BNBUSDT | 4h | 1.00 | 3.00 | 2.00 | 33.33% |
| RULE_D | BNBUSDT | 1d | -3.00 | — | — | — |
| RULE_D | ETHUSDT | 1h | — | — | — | — |
| RULE_D | ETHUSDT | 4h | 3.00 | 1.36 | -1.64 | -50.00% |
| RULE_D | ETHUSDT | 1d | 3.00 | -3.00 | -6.00 | -100.00% |
| RULE_E | SOLUSDT | 1h | — | — | — | — |
| RULE_E | SOLUSDT | 4h | — | — | — | — |
| RULE_E | SOLUSDT | 1d | — | — | — | — |
| RULE_E | BTCUSDT | 1h | — | — | — | — |
| RULE_E | BTCUSDT | 4h | — | — | — | — |
| RULE_E | BTCUSDT | 1d | — | — | — | — |
| RULE_E | BNBUSDT | 1h | — | — | — | — |
| RULE_E | BNBUSDT | 4h | — | — | — | — |
| RULE_E | BNBUSDT | 1d | — | — | — | — |
| RULE_E | ETHUSDT | 1h | — | — | — | — |
| RULE_E | ETHUSDT | 4h | — | — | — | — |
| RULE_E | ETHUSDT | 1d | — | — | — | — |

## 5. Symbol Independence

| rule | scope | cells | positive | mean_exp | positive_ratio |
|---|---|---:|---:|---:|---:|
| RULE_A | WITH_ETH | 8 | 4 | 0.10 | 50.00% |
| RULE_A | WITHOUT_ETH | 6 | 4 | 0.68 | 66.67% |
| RULE_B | WITH_ETH | 8 | 4 | 0.10 | 50.00% |
| RULE_B | WITHOUT_ETH | 6 | 4 | 0.68 | 66.67% |
| RULE_C | WITH_ETH | 8 | 4 | 0.11 | 50.00% |
| RULE_C | WITHOUT_ETH | 6 | 4 | 0.69 | 66.67% |
| RULE_D | WITH_ETH | 9 | 7 | 0.15 | 77.78% |
| RULE_D | WITHOUT_ETH | 7 | 5 | -0.12 | 71.43% |
| RULE_E | WITH_ETH | 0 | 0 | — | 0.00% |
| RULE_E | WITHOUT_ETH | 0 | 0 | — | 0.00% |

## 6. Timeframe Robustness

| rule | timeframe | n | expectancy |
|---|---|---:|---:|
| RULE_A | 1h | 6 | -0.05 |
| RULE_A | 4h | 15 | 1.14 |
| RULE_A | 1d | 1 | -3.00 |
| RULE_B | 1h | 6 | -0.05 |
| RULE_B | 4h | 15 | 1.14 |
| RULE_B | 1d | 1 | -3.00 |
| RULE_C | 1h | 7 | 0.11 |
| RULE_C | 4h | 15 | 1.14 |
| RULE_C | 1d | 1 | -3.00 |
| RULE_D | 1h | 17 | 0.10 |
| RULE_D | 4h | 36 | 0.87 |
| RULE_D | 1d | 3 | -1.00 |
| RULE_E | 1h | 0 | — |
| RULE_E | 4h | 0 | — |
| RULE_E | 1d | 0 | — |

## 7. Rule Survival

- **RULE_A**: survival_market_count=4 (BTCUSDT_1h, SOLUSDT_4h, BNBUSDT_1h, BNBUSDT_4h)
- **RULE_B**: survival_market_count=4 (BTCUSDT_1h, SOLUSDT_4h, BNBUSDT_1h, BNBUSDT_4h)
- **RULE_C**: survival_market_count=4 (BTCUSDT_1h, SOLUSDT_4h, BNBUSDT_1h, BNBUSDT_4h)
- **RULE_D**: survival_market_count=7 (ETHUSDT_4h, ETHUSDT_1d, BTCUSDT_4h, SOLUSDT_1h, SOLUSDT_4h, BNBUSDT_1h, BNBUSDT_4h)
- **RULE_E**: survival_market_count=0 (—)

## 8. Champion Rule v2

**RULE_C** — test_exp_avg=1.31, positive_ratio=50.00%, survival=4, variance=2.98

## 9. Overfitting Risk

| rule | total_n | cells | positive_ratio | avg_drift | variance | risk |
|---|---:|---:|---:|---:|---:|---|
| RULE_A | 22 | 8 | 50.00% | 1.44 | 2.97 | MEDIUM |
| RULE_B | 22 | 8 | 50.00% | 1.44 | 2.97 | MEDIUM |
| RULE_C | 23 | 8 | 50.00% | 1.09 | 2.98 | MEDIUM |
| RULE_D | 56 | 9 | 77.78% | 2.40 | 2.06 | HIGH |
| RULE_E | 0 | 0 | 0.00% | 0.00 | 0.00 | HIGH |

## 10. 최종 결론

**PASS** — Champion: RULE_C

- ETH 특화: NO
- 다시장 재현: YES

- PNG: `wave_cross_market_validation.png`
