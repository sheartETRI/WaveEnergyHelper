# Wave Exit Policy Simulation Report

Exit 정책별 성과 시뮬레이션 (관측 전용). Baseline: NO_EXIT (+20봉 보유).

## 1. Policy Summary

| policy | n | avg_return | expectancy | win_rate | profit_factor |
|---|---:|---:|---:|---:|---:|
| POLICY_A | 1890 | -0.01% | -0.01 | 35.19% | 0.99 |
| POLICY_B | 1890 | 0.17% | 0.17 | 34.81% | 1.15 |
| POLICY_C | 1890 | -0.10% | -0.10 | 30.63% | 0.91 |
| POLICY_D | 1890 | -0.10% | -0.10 | 32.80% | 0.88 |
| POLICY_E | 1890 | -0.00% | -0.00 | 35.93% | 1.00 |
| POLICY_F | 1890 | -0.12% | -0.12 | 32.01% | 0.90 |
| POLICY_G | 1890 | -0.20% | -0.20 | 27.35% | 0.83 |
| POLICY_H | 1890 | 0.28% | 0.28 | 44.66% | 1.14 |
| POLICY_I | 1890 | 0.27% | 0.27 | 44.92% | 1.14 |
| NO_EXIT | 1890 | 0.27% | 0.27 | 44.92% | 1.14 |

## 2. Drawdown 분석

| policy | avg_mae | max_mae | avg_mfe | max_mfe |
|---|---:|---:|---:|---:|
| POLICY_A | -2.73% | 0.00% | 3.49% | 54.75% |
| POLICY_B | -2.54% | 0.00% | 3.20% | 48.65% |
| POLICY_C | -1.99% | 0.00% | 2.57% | 42.34% |
| POLICY_D | -1.54% | 0.00% | 2.20% | 42.34% |
| POLICY_E | -1.44% | 0.00% | 2.11% | 42.34% |
| POLICY_F | -2.21% | 0.00% | 2.78% | 42.34% |
| POLICY_G | -2.12% | 0.00% | 2.70% | 42.34% |
| POLICY_H | -4.23% | 0.00% | 4.55% | 54.75% |
| POLICY_I | -4.39% | 0.00% | 4.57% | 54.75% |
| NO_EXIT | -4.39% | 0.00% | 4.57% | 54.75% |

## 3. False Exit 분석

| policy | n | false_exit_n | false_exit_rate |
|---|---:|---:|---:|
| POLICY_A | 482 | 126 | 26.14% |
| POLICY_B | 482 | 278 | 57.68% |
| POLICY_C | 482 | 324 | 67.22% |
| POLICY_D | 482 | 450 | 93.36% |
| POLICY_E | 482 | 450 | 93.36% |
| POLICY_F | 482 | 292 | 60.58% |
| POLICY_G | 482 | 314 | 65.15% |
| POLICY_H | 482 | 2 | 0.41% |
| POLICY_I | 482 | 0 | 0.00% |
| NO_EXIT | 482 | 0 | 0.00% |

## 4. Saved Failure 분석

| policy | n | saved_failure_n | saved_failure_rate |
|---|---:|---:|---:|
| POLICY_A | 1041 | 421 | 40.44% |
| POLICY_B | 1041 | 735 | 70.61% |
| POLICY_C | 1041 | 778 | 74.74% |
| POLICY_D | 1041 | 904 | 86.84% |
| POLICY_E | 1041 | 918 | 88.18% |
| POLICY_F | 1041 | 725 | 69.64% |
| POLICY_G | 1041 | 725 | 69.64% |
| POLICY_H | 1041 | 96 | 9.22% |
| POLICY_I | 1041 | 0 | 0.00% |
| NO_EXIT | 1041 | 0 | 0.00% |

## 5. Exit Timing

| policy | avg_exit_bar | median_exit_bar | early_exit_ratio |
|---|---:|---:|---:|
| POLICY_A | 14.29 | 20.00 | 20.26% |
| POLICY_B | 8.90 | 7.00 | 44.44% |
| POLICY_C | 7.12 | 4.00 | 55.19% |
| POLICY_D | 4.31 | 3.00 | 72.86% |
| POLICY_E | 3.60 | 2.00 | 79.05% |
| POLICY_F | 8.66 | 6.00 | 45.98% |
| POLICY_G | 8.28 | 6.00 | 46.56% |
| POLICY_H | 19.24 | 20.00 | 0.21% |
| POLICY_I | 20.00 | 20.00 | 0.00% |
| NO_EXIT | 20.00 | 20.00 | 0.00% |

## 6. Rule별 Exit 효과 (best policy per rule)

- RULE_A: best=POLICY_B exp=0.30 false_exit=54.55% saved=73.23%
- RULE_B: best=POLICY_B exp=0.46 false_exit=41.49% saved=65.30%
- RULE_C: best=POLICY_H exp=0.43 false_exit=0.37% saved=8.40%

## 7. Symbol별 Exit 효과

- BNBUSDT: best=POLICY_B exp=1.68 avg_return=1.68%
- BTCUSDT: best=POLICY_H exp=0.41 avg_return=0.41%
- ETHUSDT: best=POLICY_H exp=-0.00 avg_return=-0.00%
- SOLUSDT: best=POLICY_E exp=-0.57 avg_return=-0.57%

## 8. Regime별 Exit 효과

- BULL: best=POLICY_H exp=0.59 saved=9.42%
- SIDEWAYS: best=POLICY_I exp=0.41 saved=0.00%
- BEAR: best=POLICY_E exp=-0.13 saved=93.94%

## 9. Champion Policy Top 10

| rank | policy | score | expectancy | false_exit | saved_failure |
|---:|---|---:|---:|---:|---:|
| 1 | POLICY_B | 9.27 | 0.17 | 57.68% | 70.61% |
| 2 | POLICY_C | 8.71 | -0.10 | 67.22% | 74.74% |
| 3 | POLICY_F | 8.43 | -0.12 | 60.58% | 69.64% |
| 4 | POLICY_E | 8.21 | -0.00 | 93.36% | 88.18% |
| 5 | POLICY_D | 7.82 | -0.10 | 93.36% | 86.84% |
| 6 | POLICY_G | 7.70 | -0.20 | 65.15% | 69.64% |
| 7 | POLICY_A | 6.35 | -0.01 | 26.14% | 40.44% |
| 8 | POLICY_H | 2.56 | 0.28 | 0.41% | 9.22% |
| 9 | POLICY_I | -14.69 | 0.27 | 0.00% | 0.00% |

## 10. Worst Policy Top 10

| rank | policy | score | expectancy | false_exit | saved_failure |
|---:|---|---:|---:|---:|---:|
| 1 | POLICY_I | -14.69 | 0.27 | 0.00% | 0.00% |
| 2 | POLICY_H | 2.56 | 0.28 | 0.41% | 9.22% |
| 3 | POLICY_A | 6.35 | -0.01 | 26.14% | 40.44% |
| 4 | POLICY_G | 7.70 | -0.20 | 65.15% | 69.64% |
| 5 | POLICY_D | 7.82 | -0.10 | 93.36% | 86.84% |
| 6 | POLICY_E | 8.21 | -0.00 | 93.36% | 88.18% |
| 7 | POLICY_F | 8.43 | -0.12 | 60.58% | 69.64% |
| 8 | POLICY_C | 8.71 | -0.10 | 67.22% | 74.74% |
| 9 | POLICY_B | 9.27 | 0.17 | 57.68% | 70.61% |

## 11. Active Candidate Overlay

| rank | symbol | tf | rule | recommended | protection | risk |
|---:|---|---|---|---|---:|---:|
| 1 | BTCUSDT | 1h | RULE_B | POLICY_B | 65.30% | 66.67 |
| 2 | BTCUSDT | 1h | RULE_A | POLICY_B | 73.23% | 44.44 |
| 3 | SOLUSDT | 1h | RULE_C | POLICY_H | 8.40% | 27.78 |
| 4 | SOLUSDT | 1h | RULE_B | POLICY_B | 65.30% | 26.67 |
| 5 | BNBUSDT | 1h | RULE_A | POLICY_B | 73.23% | 17.78 |
| 6 | BNBUSDT | 1h | RULE_B | POLICY_B | 65.30% | 13.33 |
| 7 | ETHUSDT | 1h | RULE_C | POLICY_H | 8.40% | 13.33 |
| 8 | BNBUSDT | 4h | RULE_C | POLICY_H | 8.40% | 11.56 |
| 9 | BNBUSDT | 1h | RULE_C | POLICY_H | 8.40% | 8.89 |
| 10 | BTCUSDT | 1h | RULE_C | POLICY_H | 8.40% | 8.00 |
| 11 | BTCUSDT | 4h | RULE_B | POLICY_B | 65.30% | 6.67 |
| 12 | ETHUSDT | 4h | RULE_C | POLICY_H | 8.40% | 5.78 |
| 13 | BNBUSDT | 1d | RULE_C | POLICY_H | 8.40% | 5.00 |
| 14 | SOLUSDT | 4h | RULE_C | POLICY_H | 8.40% | 4.62 |
| 15 | BTCUSDT | 4h | RULE_A | POLICY_B | 73.23% | 4.44 |

## 12. 현재 추적 우선순위

- #1 BTCUSDT 1h RULE_B policy=POLICY_B protection=65.30%
- #2 BTCUSDT 1h RULE_A policy=POLICY_B protection=73.23%
- #3 SOLUSDT 1h RULE_C policy=POLICY_H protection=8.40%
- #4 SOLUSDT 1h RULE_B policy=POLICY_B protection=65.30%
- #5 BNBUSDT 1h RULE_A policy=POLICY_B protection=73.23%
- #6 BNBUSDT 1h RULE_B policy=POLICY_B protection=65.30%
- #7 ETHUSDT 1h RULE_C policy=POLICY_H protection=8.40%
- #8 BNBUSDT 4h RULE_C policy=POLICY_H protection=8.40%
- #9 BNBUSDT 1h RULE_C policy=POLICY_H protection=8.40%
- #10 BTCUSDT 1h RULE_C policy=POLICY_H protection=8.40%

## 13. 핵심 결론

**Champion: POLICY_B** (score 9.27, expectancy 0.17, false_exit 57.68%, saved_failure 70.61%).
- Baseline NO_EXIT expectancy: 0.27 → Champion delta: -0.10

- PNG: `wave_exit_policy_simulation.png`
