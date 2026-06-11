# REPORT_WAVE_GENERALIZATION

Candidate Rule Generalization — 4 symbols × 3 timeframes

- CSV: `wave_generalization.csv`
- PNG: `wave_generalization.png`
- 총 셀: 12

### Rule Summary

| rule | positive cells | median expectancy |
|---|---:|---:|
| RULE_C | 6 | 0.89 |
| RULE_D | 6 | 0.84 |
| RULE_B | 6 | 0.49 |
| RULE_A | 6 | 0.00 |
| RULE_SCORE_3 | 5 | 0.00 |

### Rule Variance

| rule | variance |
|---|---:|
| RULE_SCORE_3 | 0.99 |
| RULE_A | 1.22 |
| RULE_C | 2.39 |
| RULE_D | 3.26 |
| RULE_B | 3.43 |

### Top Cells

| symbol | tf | rule | expectancy | n |
|---|---|---|---:|---:|
| ETHUSDT | 4h | RULE_A | 1.67 | 7 |
| ETHUSDT | 4h | RULE_B | 2.34 | 5 |
| ETHUSDT | 4h | RULE_C | 2.18 | 4 |
| ETHUSDT | 4h | RULE_D | 2.18 | 4 |
| ETHUSDT | 4h | RULE_SCORE_3 | 2.18 | 4 |

### Worst Cells

| symbol | tf | rule | expectancy | n |
|---|---|---|---:|---:|
| BTCUSDT | 1d | RULE_A | -3.00 | 2 |
| BNBUSDT | 1d | RULE_B | -3.00 | 1 |
| ETHUSDT | 1d | RULE_C | -3.00 | 1 |
| BNBUSDT | 1d | RULE_D | -3.00 | 1 |
| BTCUSDT | 1h | RULE_SCORE_3 | -1.19 | 4 |

### ETH / BTC / SOL / BNB 비교 (RULE_B)

| symbol | data cells | positive | median exp |
|---|---:|---:|---:|
| ETHUSDT | 2 | 1 | -0.33 |
| BTCUSDT | 2 | 1 | 0.07 |
| SOLUSDT | 2 | 2 | 1.23 |
| BNBUSDT | 3 | 2 | 0.84 |

### 1h / 4h / 1d 비교 (RULE_B)

| tf | data cells | positive | median exp |
|---|---:|---:|---:|
| 1h | 3 | 3 | 0.49 |
| 4h | 4 | 3 | 1.75 |
| 1d | 2 | 0 | -3.00 |

- Most General Rule: RULE_C
- Least General Rule: RULE_SCORE_3
- RULE_B positive cells: 6 / 12 (data cells: 9)
