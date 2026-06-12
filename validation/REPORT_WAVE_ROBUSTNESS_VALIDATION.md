# Wave Robustness Validation Report

Champion: RULE_A+BNB+mf>=5+struct>=5 — verdict **CONDITIONAL**, robustness_score 81.87, overfit_risk 1.00

## 1. Temporal Split Validation (CHAMPION)

| split | n | expectancy | avg_return_20 | survival | PF | tier |
|---|---:|---:|---:|---:|---:|---|
| first_half | 29 | 6.85 | 6.85% | 44.83% | 9.62 | LOW |
| second_half | 30 | 1.42 | 1.42% | 40.00% | 1.88 | LOW |
| recent_180d | 51 | 1.02 | 1.02% | 33.33% | 1.72 | MEDIUM |
| recent_90d | 51 | 1.02 | 1.02% | 33.33% | 1.72 | MEDIUM |
| recent_30d | 43 | 1.17 | 1.17% | 34.88% | 1.77 | LOW |

## 2. Timeframe Robustness (CHAMPION)

| tf | n | expectancy | survival | PF |
|---|---:|---:|---:|---:|
| 1h | 29 | 3.66 | 51.72% | 14.98 |
| 4h | 22 | -2.47 | 9.09% | 0.15 |
| 1d | 8 | 23.69 | 100.00% | 999.00 |

## 3. Symbol Robustness

| filter | symbol | n | expectancy | survival |
|---|---|---:|---:|---:|
| CHAMPION | BNBUSDT | 59 | 4.09 | 42.37% |
| CHAMPION | BTCUSDT | 0 | — | — |
| CHAMPION | ETHUSDT | 0 | — | — |
| CHAMPION | SOLUSDT | 0 | — | — |
| CHAMPION | BNB_only | 59 | 4.09 | 42.37% |
| CHAMPION | without_BNB | 85 | -0.16 | 25.88% |
| Filter_Q | with_BNB | 750 | 0.91 | 27.60% |
| Filter_Q | without_BNB | 474 | -0.17 | 22.78% |
| Filter_C | with_BNB | 932 | 0.40 | 28.65% |
| Filter_C | without_BNB | 658 | 0.11 | 25.38% |
| Filter_BNB | BNB_only | 571 | 1.56 | 32.75% |
| Filter_BNB | without_BNB | 1319 | -0.29 | 22.37% |
| Filter_STRUCT | with_BNB | 904 | 0.78 | 31.53% |
| Filter_STRUCT | without_BNB | 571 | -0.14 | 28.20% |
| Filter_MF | with_BNB | 924 | 0.70 | 29.11% |
| Filter_MF | without_BNB | 623 | -0.10 | 24.40% |
| Filter_BNB_CORE | BNB_only | 213 | 3.02 | 41.31% |
| Filter_BNB_CORE | without_BNB | 322 | -0.09 | 27.95% |

## 4. Regime Robustness (CHAMPION)

| regime | n | expectancy | survival | PF |
|---|---:|---:|---:|---:|
| BULL | 55 | 4.23 | 41.82% | 4.24 |
| BEAR | 0 | — | — | — |
| SIDEWAYS | 4 | 2.23 | 50.00% | 999.00 |

## 5. Leave-One-Out (CHAMPION)

| condition | n | expectancy | delta |
|---|---:|---:|---:|
| remove_1h | 30 | 4.51 | 0.42 |
| remove_4h | 37 | 7.99 | 3.90 |
| remove_1d | 51 | 1.02 | -3.07 |
| remove_BULL | 4 | 2.23 | -1.86 |
| remove_SIDEWAYS | 55 | 4.23 | 0.14 |
| remove_BEAR | 59 | 4.09 | 0.00 |
| remove_recent_30d | 16 | 11.93 | 7.84 |
| remove_recent_90d | 8 | 23.69 | 19.60 |

## 6. Minimum Sample Check (CHAMPION highlights)

| context | n | tier | expectancy |
|---|---:|---|---:|
| first_half | 29 | LOW | 6.85 |
| second_half | 30 | LOW | 1.42 |
| recent_30d | 43 | LOW | 1.17 |
| 1h | 29 | LOW | 3.66 |
| 4h | 22 | LOW | -2.47 |
| 1d | 8 | UNSTABLE | 23.69 |
| BEAR | 0 | UNSTABLE | — |
| SIDEWAYS | 4 | UNSTABLE | 2.23 |

## 7. Robustness Score

| filter | score | split_cons | tf_cons | reg_cons | verdict |
|---|---:|---:|---:|---:|---|
| CHAMPION | 81.87 | 100.00% | 66.67% | 100.00% | CONDITIONAL |
| Filter_Q | 59.39 | 40.00% | 66.67% | 100.00% | CONDITIONAL |
| Filter_C | 45.46 | 20.00% | 66.67% | 66.67% | CONDITIONAL |
| Filter_BNB | 76.87 | 100.00% | 66.67% | 100.00% | ROBUST |
| Filter_STRUCT | 49.25 | 20.00% | 66.67% | 50.00% | CONDITIONAL |
| Filter_MF | 49.59 | 20.00% | 66.67% | 66.67% | CONDITIONAL |
| Filter_BNB_CORE | 86.98 | 100.00% | 66.67% | 100.00% | ROBUST |

## 8. Overfitting Risk

- CHAMPION: risk=1 flags=symbol_single_BNB
- Filter_Q: risk=1 flags=temporal_inconsistency
- Filter_C: risk=1 flags=temporal_inconsistency
- Filter_BNB: risk=1 flags=symbol_single_BNB
- Filter_STRUCT: risk=1 flags=temporal_inconsistency
- Filter_MF: risk=1 flags=temporal_inconsistency
- Filter_BNB_CORE: risk=1 flags=symbol_single_BNB

## 9. Champion 유지/기각 판단

- **Verdict: CONDITIONAL**
- n=59, expectancy=4.09, split_consistency=100.00%

## 10. Alternative Robust Filter

| rank | filter | robustness | expectancy | verdict |
|---:|---|---:|---:|---|
| 1 | Filter_BNB_CORE | 86.98 | 3.02 | ROBUST |
| 2 | Filter_BNB | 76.87 | 1.56 | ROBUST |
| 3 | Filter_Q | 59.39 | 0.91 | CONDITIONAL |
| 4 | Filter_BNB_MF | 53.06 | 2.36 | CONDITIONAL |
| 5 | Filter_BNB_STRUCT | 52.15 | 2.37 | CONDITIONAL |
| 6 | Filter_MF | 49.59 | 0.70 | CONDITIONAL |
| 7 | Filter_STRUCT | 49.25 | 0.78 | CONDITIONAL |
| 8 | Filter_C | 45.46 | 0.40 | CONDITIONAL |

## 11. Active Candidate Overlay

| rank | symbol | tf | rule | robust_match | score | risk |
|---:|---|---|---|---|---:|---:|
| 1 | BNBUSDT | 1h | RULE_A | Filter_BNB | 76.87 | 1 |
| 2 | BNBUSDT | 1h | RULE_B | Filter_BNB | 76.87 | 1 |
| 3 | BNBUSDT | 4h | RULE_C | Filter_BNB | 76.87 | 1 |
| 4 | BNBUSDT | 1h | RULE_C | Filter_BNB | 76.87 | 1 |
| 5 | BNBUSDT | 1d | RULE_C | Filter_BNB | 76.87 | 1 |
| 6 | BTCUSDT | 1h | RULE_B | Filter_Q | 59.39 | 1 |
| 7 | BTCUSDT | 1h | RULE_A | Filter_Q | 59.39 | 1 |
| 8 | ETHUSDT | 1h | RULE_C | Filter_Q | 59.39 | 1 |
| 9 | SOLUSDT | 1h | RULE_C | Filter_MF | 49.59 | 1 |
| 10 | BTCUSDT | 4h | RULE_C | Filter_MF | 49.59 | 1 |
| 11 | BTCUSDT | 1d | RULE_C | Filter_MF | 49.59 | 1 |
| 12 | SOLUSDT | 1h | RULE_B | Filter_STRUCT | 49.25 | 1 |

## 12. 현재 관측 우선순위

- #1 BNBUSDT 1h RULE_A match=Filter_BNB score=76.87
- #2 BNBUSDT 1h RULE_B match=Filter_BNB score=76.87
- #3 BNBUSDT 4h RULE_C match=Filter_BNB score=76.87
- #4 BNBUSDT 1h RULE_C match=Filter_BNB score=76.87
- #5 BNBUSDT 1d RULE_C match=Filter_BNB score=76.87
- #6 BTCUSDT 1h RULE_B match=Filter_Q score=59.39
- #7 BTCUSDT 1h RULE_A match=Filter_Q score=59.39
- #8 ETHUSDT 1h RULE_C match=Filter_Q score=59.39
- #9 SOLUSDT 1h RULE_C match=Filter_MF score=49.59
- #10 BTCUSDT 4h RULE_C match=Filter_MF score=49.59

## 13. 핵심 결론

Champion Filter verdict: **CONDITIONAL** — overfit_risk 1.00, split_consistency 100.00%.
- Best alternative: Filter_BNB_CORE (robustness 86.98, verdict ROBUST)

- PNG: `wave_robustness_validation.png`
