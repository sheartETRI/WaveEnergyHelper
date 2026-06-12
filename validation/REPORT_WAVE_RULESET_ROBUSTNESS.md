# REPORT_WAVE_RULESET_ROBUSTNESS

Rule Set Robustness Validation

- events: 71

## 1. 기본 성과

| rule | n | win_rate | expectancy | profit_factor | payoff_ratio | avg_return | median_return | avg_survival |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RULE_A | 5 | 100.00% | 3.00 | inf | inf | 3.00 | 3.00 | 24.40 |
| RULE_B | 4 | 100.00% | 3.00 | inf | inf | 3.00 | 3.00 | 12.75 |
| RULE_C | 11 | 72.73% | 1.49 | 3.16 | 1.18 | 1.49 | 3.00 | 35.91 |
| RULE_D | 8 | 87.50% | 2.25 | 7.00 | 1.00 | 2.25 | 3.00 | 15.88 |
| RULE_E | 14 | 78.57% | 1.71 | 3.67 | 1.00 | 1.71 | 3.00 | 23.79 |

## 2. Walk Forward

| rule | quarter | n | win_rate | expectancy | profit_factor |
|---|---|---:|---:|---:|---:|
| RULE_A | Q1 | 2 | 100.00% | 3.00 | inf |
| RULE_A | Q2 | 1 | 100.00% | 3.00 | inf |
| RULE_A | Q3 | 1 | 100.00% | 3.00 | inf |
| RULE_A | Q4 | 1 | 100.00% | 3.00 | inf |
| RULE_B | Q1 | 1 | 100.00% | 3.00 | inf |
| RULE_B | Q2 | 1 | 100.00% | 3.00 | inf |
| RULE_B | Q3 | 1 | 100.00% | 3.00 | inf |
| RULE_B | Q4 | 1 | 100.00% | 3.00 | inf |
| RULE_C | Q1 | 3 | 66.67% | 1.00 | 2.00 |
| RULE_C | Q2 | 3 | 100.00% | 3.00 | inf |
| RULE_C | Q3 | 3 | 66.67% | 1.00 | 2.00 |
| RULE_C | Q4 | 2 | 50.00% | 0.70 | 1.87 |
| RULE_D | Q1 | 2 | 100.00% | 3.00 | inf |
| RULE_D | Q2 | 2 | 100.00% | 3.00 | inf |
| RULE_D | Q3 | 2 | 50.00% | -0.00 | 1.00 |
| RULE_D | Q4 | 2 | 100.00% | 3.00 | inf |
| RULE_E | Q1 | 4 | 75.00% | 1.50 | 3.00 |
| RULE_E | Q2 | 4 | 75.00% | 1.50 | 3.00 |
| RULE_E | Q3 | 3 | 66.67% | 1.00 | 2.00 |
| RULE_E | Q4 | 3 | 100.00% | 3.00 | inf |

## 3. Rolling Window

| rule | n | windows | avg_exp | min_exp | max_exp | variance | neg_ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| RULE_A | 5 | 4 | 3.00 | 3.00 | 3.00 | 0.00 | 0.00 |
| RULE_B | 4 | 3 | 3.00 | 3.00 | 3.00 | 0.00 | 0.00 |
| RULE_C | 11 | 10 | 1.87 | 0.00 | 3.00 | 1.95 | 0.00 |
| RULE_D | 8 | 7 | 2.14 | -0.00 | 3.00 | 1.84 | 0.29 |
| RULE_E | 14 | 12 | 1.67 | 1.00 | 3.00 | 0.89 | 0.00 |

## 4. Exit Policy Stability

| rule | policy | n | win_rate | expectancy | rank |
|---|---|---:|---:|---:|---:|
| RULE_A | TP3_SL3_TIMEOUT20 | 5 | 100.00% | 3.00 | 1 |
| RULE_A | TP5_SL3_TIMEOUT40 | 5 | 60.00% | 1.80 | 4 |
| RULE_A | TP5_KTURN_TIMEOUT40 | 5 | 60.00% | 0.81 | 5 |
| RULE_A | K_CROSS_DOWN_TIMEOUT40 | 5 | 60.00% | 2.47 | 2 |
| RULE_A | WAVE_INVALIDATION_EXIT | 5 | 60.00% | 2.45 | 3 |
| RULE_B | TP3_SL3_TIMEOUT20 | 4 | 100.00% | 3.00 | 3 |
| RULE_B | TP5_SL3_TIMEOUT40 | 4 | 75.00% | 3.00 | 4 |
| RULE_B | TP5_KTURN_TIMEOUT40 | 4 | 75.00% | 1.25 | 5 |
| RULE_B | K_CROSS_DOWN_TIMEOUT40 | 4 | 75.00% | 3.32 | 1 |
| RULE_B | WAVE_INVALIDATION_EXIT | 4 | 75.00% | 3.22 | 2 |
| RULE_C | TP3_SL3_TIMEOUT20 | 11 | 72.73% | 1.49 | 3 |
| RULE_C | TP5_SL3_TIMEOUT40 | 11 | 54.55% | 1.61 | 2 |
| RULE_C | TP5_KTURN_TIMEOUT40 | 11 | 72.73% | 1.93 | 1 |
| RULE_C | K_CROSS_DOWN_TIMEOUT40 | 11 | 54.55% | 0.96 | 4 |
| RULE_C | WAVE_INVALIDATION_EXIT | 11 | 45.45% | -1.27 | 5 |
| RULE_D | TP3_SL3_TIMEOUT20 | 8 | 87.50% | 2.25 | 1 |
| RULE_D | TP5_SL3_TIMEOUT40 | 8 | 62.50% | 2.00 | 2 |
| RULE_D | TP5_KTURN_TIMEOUT40 | 8 | 50.00% | 0.42 | 5 |
| RULE_D | K_CROSS_DOWN_TIMEOUT40 | 8 | 50.00% | 1.68 | 3 |
| RULE_D | WAVE_INVALIDATION_EXIT | 8 | 50.00% | 1.07 | 4 |
| RULE_E | TP3_SL3_TIMEOUT20 | 14 | 78.57% | 1.71 | 1 |
| RULE_E | TP5_SL3_TIMEOUT40 | 14 | 50.00% | 1.00 | 2 |
| RULE_E | TP5_KTURN_TIMEOUT40 | 14 | 57.14% | 0.22 | 4 |
| RULE_E | K_CROSS_DOWN_TIMEOUT40 | 14 | 42.86% | 0.48 | 3 |
| RULE_E | WAVE_INVALIDATION_EXIT | 14 | 50.00% | -1.73 | 5 |

| rule | exit_policy_sensitivity |
|---|---:|
| RULE_A | 2.19 |
| RULE_B | 2.07 |
| RULE_C | 3.20 |
| RULE_D | 1.83 |
| RULE_E | 3.45 |

## 5. Symbol Robustness

| rule | symbol | n | win_rate | expectancy |
|---|---|---:|---:|---:|
| RULE_A | ETHUSDT | 5 | 100.00% | 3.00 |
| RULE_A | BTCUSDT | 0 | — | — |
| RULE_A | SOLUSDT | 0 | — | — |
| RULE_A | BNBUSDT | 0 | — | — |
| RULE_B | ETHUSDT | 4 | 100.00% | 3.00 |
| RULE_B | BTCUSDT | 0 | — | — |
| RULE_B | SOLUSDT | 0 | — | — |
| RULE_B | BNBUSDT | 0 | — | — |
| RULE_C | ETHUSDT | 11 | 72.73% | 1.49 |
| RULE_C | BTCUSDT | 0 | — | — |
| RULE_C | SOLUSDT | 0 | — | — |
| RULE_C | BNBUSDT | 0 | — | — |
| RULE_D | ETHUSDT | 7 | 85.71% | 2.14 |
| RULE_D | BTCUSDT | 1 | 100.00% | 3.00 |
| RULE_D | SOLUSDT | 0 | — | — |
| RULE_D | BNBUSDT | 0 | — | — |
| RULE_E | ETHUSDT | 12 | 75.00% | 1.50 |
| RULE_E | BTCUSDT | 2 | 100.00% | 3.00 |
| RULE_E | SOLUSDT | 0 | — | — |
| RULE_E | BNBUSDT | 0 | — | — |

- RULE_A symbol_positive_ratio: 100.00%
- RULE_B symbol_positive_ratio: 100.00%
- RULE_C symbol_positive_ratio: 100.00%
- RULE_D symbol_positive_ratio: 100.00%
- RULE_E symbol_positive_ratio: 100.00%

## 6. Timeframe Robustness

| rule | timeframe | n | win_rate | expectancy |
|---|---|---:|---:|---:|
| RULE_A | 1h | 0 | — | — |
| RULE_A | 4h | 5 | 100.00% | 3.00 |
| RULE_A | 1d | 0 | — | — |
| RULE_B | 1h | 0 | — | — |
| RULE_B | 4h | 4 | 100.00% | 3.00 |
| RULE_B | 1d | 0 | — | — |
| RULE_C | 1h | 0 | — | — |
| RULE_C | 4h | 11 | 72.73% | 1.49 |
| RULE_C | 1d | 0 | — | — |
| RULE_D | 1h | 0 | — | — |
| RULE_D | 4h | 7 | 85.71% | 2.14 |
| RULE_D | 1d | 1 | 100.00% | 3.00 |
| RULE_E | 1h | 0 | — | — |
| RULE_E | 4h | 12 | 75.00% | 1.50 |
| RULE_E | 1d | 2 | 100.00% | 3.00 |

- RULE_A timeframe_positive_ratio: 100.00%
- RULE_B timeframe_positive_ratio: 100.00%
- RULE_C timeframe_positive_ratio: 100.00%
- RULE_D timeframe_positive_ratio: 100.00%
- RULE_E timeframe_positive_ratio: 100.00%

## 7. Regime Robustness

| rule | regime | n | win_rate | expectancy |
|---|---|---:|---:|---:|
| RULE_A | MID_VOL | 5 | 100.00% | 3.00 |
| RULE_B | MID_VOL | 4 | 100.00% | 3.00 |
| RULE_C | MID_VOL | 11 | 72.73% | 1.49 |
| RULE_D | MID_VOL | 8 | 87.50% | 2.25 |
| RULE_E | MID_VOL | 14 | 78.57% | 1.71 |
| RULE_A | TREND_UP | 4 | 100.00% | 3.00 |
| RULE_B | TREND_UP | 3 | 100.00% | 3.00 |
| RULE_C | TREND_UP | 5 | 100.00% | 3.00 |
| RULE_D | TREND_UP | 5 | 80.00% | 1.80 |
| RULE_E | TREND_UP | 8 | 87.50% | 2.25 |
| RULE_A | TREND_DOWN | 1 | 100.00% | 3.00 |
| RULE_B | TREND_DOWN | 1 | 100.00% | 3.00 |
| RULE_C | TREND_DOWN | 6 | 50.00% | 0.23 |
| RULE_D | TREND_DOWN | 3 | 100.00% | 3.00 |
| RULE_E | TREND_DOWN | 6 | 66.67% | 1.00 |

- RULE_A regime_positive_ratio: 100.00%
- RULE_B regime_positive_ratio: 100.00%
- RULE_C regime_positive_ratio: 100.00%
- RULE_D regime_positive_ratio: 100.00%
- RULE_E regime_positive_ratio: 100.00%

## 8. Robustness Score

| rule | overall | walk | rolling | exit | symbol | tf | regime |
|---|---:|---:|---:|---:|---:|---:|---:|
| RULE_A | 93.91 | 100.00 | 100.00 | 63.45 | 100.00 | 100.00 | 100.00 |
| RULE_B | 94.24 | 100.00 | 100.00 | 65.42 | 100.00 | 100.00 | 100.00 |
| RULE_C | 91.12 | 100.00 | 100.00 | 46.71 | 100.00 | 100.00 | 100.00 |
| RULE_D | 85.98 | 75.00 | 71.43 | 69.48 | 100.00 | 100.00 | 100.00 |
| RULE_E | 90.42 | 100.00 | 100.00 | 42.54 | 100.00 | 100.00 | 100.00 |

## 9. Champion Rule

**RULE_B** — robustness=94.24, n=4, win_rate=100.00%, expectancy=3.00

## 10. 실전 사용 가능성

**PASS**

- robustness_score=94.24, expectancy=3.00, n=4

- PNG: `wave_ruleset_robustness.png`
