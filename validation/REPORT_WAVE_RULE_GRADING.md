# REPORT_WAVE_RULE_GRADING

Rule Confidence Grading — BASE_RULE A/B/C/D

## Grade Summary

| grade | count | win_rate | expectancy | PF | payoff | avg_return | median_return | avg_survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 7 | 71.43 | 2.03 | 18.55 | 7.42 | 2.03 | 3.00 | 43.80 |
| B | 34 | 64.71 | 0.90 | 2.27 | 1.24 | 0.90 | 2.06 | 40.33 |
| C | 37 | 64.86 | 0.91 | 2.24 | 1.21 | 0.91 | 3.00 | 43.80 |
| D | 142 | 50.70 | 0.06 | 1.05 | 1.02 | 0.06 | 0.14 | 33.78 |

## Grade Separation

| comparison | Δexpectancy | Δwin_rate | ΔPF |
|---|---:|---:|---:|
| A vs B | 1.13 | 6.72 | 16.28 |
| B vs C | -0.01 | -0.16 | 0.03 |
| C vs D | 0.85 | 14.16 | 1.19 |

## Monotonicity Test

- result: **FAIL**

| metric | A | B | C | D | pass |
|---|---:|---:|---:|---:|:---:|
| win_rate | 71.43 | 64.71 | 64.86 | 50.70 | FAIL |
| expectancy | 2.03 | 0.90 | 0.91 | 0.06 | FAIL |
| profit_factor | 18.55 | 2.27 | 2.24 | 1.05 | PASS |

## Calibration

| grade | actual win |
|---|---:|
| A | 71.43% |
| B | 64.71% |
| C | 64.86% |
| D | 50.70% |

## Robustness

| grade | 1st half exp | 2nd half exp | robustness_gap |
|---|---:|---:|---:|
| A | 3.00 | 1.30 | 1.70 |
| B | 0.88 | 0.92 | 0.04 |
| C | 1.33 | 0.51 | 0.83 |
| D | 0.07 | 0.05 | 0.02 |

## Cross Market

| grade | symbol | expectancy | n |
|---|---|---:|---:|
| A | ETHUSDT | 2.34 | 5 |
| A | BTCUSDT | 3.00 | 1 |
| A | SOLUSDT | -0.52 | 1 |
| A | BNBUSDT | — | 0 |
| B | ETHUSDT | 0.68 | 4 |
| B | BTCUSDT | -0.24 | 7 |
| B | SOLUSDT | 1.30 | 11 |
| B | BNBUSDT | 1.28 | 12 |
| C | ETHUSDT | 1.45 | 6 |
| C | BTCUSDT | -0.24 | 7 |
| C | SOLUSDT | 1.30 | 11 |
| C | BNBUSDT | 0.95 | 13 |
| D | ETHUSDT | 1.06 | 11 |
| D | BTCUSDT | -0.47 | 37 |
| D | SOLUSDT | -0.17 | 49 |
| D | BNBUSDT | 0.49 | 45 |

## ETH / BTC / SOL / BNB 비교

| grade | ETH | BTC | SOL | BNB |
|---|---:|---:|---:|---:|
| A | 2.34 | 3.00 | -0.52 | — |
| B | 0.68 | -0.24 | 1.30 | 1.28 |
| C | 1.45 | -0.24 | 1.30 | 0.95 |
| D | 1.06 | -0.47 | -0.17 | 0.49 |

- Recommended Grade: **A**
- PNG: `wave_rule_grading.png`
