# REPORT — Wave Survival Segmentation

## 생존 정의

SURVIVED_20: return_20 > 2.0%; FAILED_20: return_20 <= 0%; NEUTRAL_20: 0 < return_20 <= 2.0%

Survival Feature = structure_score + money_flow_score + energy_score

## 1. Survival Cohort

| label | n | avg5 | avg10 | avg20 | avg40 |
|---|---:|---:|---:|---:|---:|
| SURVIVED_20 | 501 | 1.78% | 3.25% | 7.94% | 7.83% |
| FAILED_20 | 1067 | -1.08% | -1.93% | -3.60% | -5.60% |
| NEUTRAL_20 | 414 | -0.25% | 0.20% | 0.83% | 0.30% |

## 2. Rule Survival

| rule | n | survival | failure | neutral |
|---|---:|---:|---:|---:|
| RULE_A | 573 | 21.82% | 54.80% | 23.39% |
| RULE_B | 429 | 22.84% | 51.52% | 25.64% |
| RULE_C | 980 | 28.37% | 54.29% | 17.35% |

## 3. Symbol Survival

| symbol | n | survival | failure | avg20 | avg40 |
|---|---:|---:|---:|---:|---:|
| BNBUSDT | 597 | 31.66% | 42.55% | 1.50% | 0.01% |
| BTCUSDT | 479 | 27.77% | 46.97% | 0.25% | -1.37% |
| ETHUSDT | 449 | 22.05% | 65.92% | -0.02% | -0.22% |
| SOLUSDT | 457 | 17.51% | 63.89% | -1.14% | -2.86% |

## 4. Regime Survival

| regime | n | survival | failure | avg20 | avg40 |
|---|---:|---:|---:|---:|---:|
| BULL | 1333 | 24.61% | 54.69% | 0.45% | -0.76% |
| BEAR | 264 | 21.21% | 63.64% | -1.11% | -2.81% |
| SIDEWAYS | 385 | 30.39% | 44.16% | 0.45% | -0.75% |

## 5. Feature Difference (SURVIVED vs FAILED)

| feature | survived | failed | delta |
|---|---:|---:|---:|
| money_flow_score | 4.55 | 4.47 | 0.08 |
| energy_score | 3.69 | 3.51 | 0.17 |
| structure_score | 4.21 | 3.84 | 0.36 |
| quality_score | 3.27 | 3.15 | 0.12 |
| watchlist_score | 21.01 | 21.58 | -0.57 |
| bars_elapsed | 258.47 | 249.29 | 9.18 |

## 6. Failure Cause 분석

| cause | n | pct | avg20 | avg40 | avg_bars |
|---|---:|---:|---:|---:|---:|
| STRUCTURE_FAIL | 581 | 53.00% | -2.69% | -5.34% | 236.55 |
| MONEY_FLOW_DROP | 299 | 27.30% | -2.37% | -2.81% | 266.67 |
| STOP_LOSS_3 | 217 | 19.80% | -7.24% | -9.88% | 264.95 |

## 7. Survival Curve

| horizon | n | survival_rate (>2%) |
|---:|---:|---:|
| +5 | 2071 | 12.89% |
| +10 | 2058 | 19.24% |
| +20 | 1982 | 25.28% |
| +40 | 1890 | 29.31% |

## 8. Champion Survivor (return_40 Top 20)

| rank | rule | symbol | tf | return_40 | mfe_40 |
|---:|---|---|---|---:|---:|
| 1 | RULE_C | ETHUSDT | 1d | 77.15% | 79.05% |
| 2 | RULE_C | ETHUSDT | 1d | 64.30% | 69.87% |
| 3 | RULE_C | ETHUSDT | 1d | 58.56% | 62.18% |
| 4 | RULE_C | ETHUSDT | 1d | 55.77% | 72.93% |
| 5 | RULE_C | ETHUSDT | 1d | 52.34% | 57.97% |
| 6 | RULE_C | ETHUSDT | 1d | 51.43% | 64.03% |
| 7 | RULE_A | ETHUSDT | 1d | 50.48% | 56.32% |
| 8 | RULE_C | ETHUSDT | 1d | 50.45% | 56.29% |
| 9 | RULE_C | ETHUSDT | 1d | 46.58% | 61.85% |
| 10 | RULE_C | ETHUSDT | 1d | 46.55% | 57.55% |
| 11 | RULE_C | ETHUSDT | 1d | 46.12% | 56.23% |
| 12 | RULE_C | ETHUSDT | 1d | 44.58% | 58.75% |
| 13 | RULE_C | ETHUSDT | 1d | 43.56% | 62.68% |
| 14 | RULE_C | SOLUSDT | 1d | 42.93% | 52.28% |
| 15 | RULE_C | SOLUSDT | 1d | 40.16% | 55.30% |
| 16 | RULE_C | SOLUSDT | 1d | 38.50% | 41.19% |
| 17 | RULE_C | ETHUSDT | 1d | 38.10% | 62.23% |
| 18 | RULE_C | SOLUSDT | 1d | 37.54% | 40.88% |
| 19 | RULE_C | SOLUSDT | 1d | 35.87% | 39.81% |
| 20 | RULE_C | BNBUSDT | 1d | 35.70% | 36.04% |

## 9. Contribution 분석 (SS %)

- 이전 Regime Seg #20: Rule 0.03%, Symbol 1.89%, Regime 0.57%, Residual 97.51%
- **Rule**: 0.03%
- **Symbol**: 1.89%
- **Regime**: 0.57%
- **Survival Feature**: 1.13%
- **Residual**: 96.38%

## 10. Active Candidate Survival Overlay

| rank | symbol | tf | rule | surv_rate | fail_rate | score |
|---:|---|---|---|---:|---:|---:|
| 1 | BNBUSDT | 4h | RULE_C | 35.54% | 45.30% | 11.56 |
| 2 | BNBUSDT | 1h | RULE_C | 35.54% | 45.30% | 8.89 |
| 3 | BNBUSDT | 1d | RULE_C | 35.54% | 45.30% | 5.00 |
| 4 | BTCUSDT | 1h | RULE_B | 30.77% | 39.42% | 66.67 |
| 5 | BTCUSDT | 4h | RULE_B | 30.77% | 39.42% | 6.67 |
| 6 | BNBUSDT | 1h | RULE_A | 29.41% | 40.00% | 17.78 |
| 7 | BTCUSDT | 1h | RULE_C | 27.07% | 51.09% | 8.00 |
| 8 | BTCUSDT | 4h | RULE_C | 27.07% | 51.09% | 3.33 |
| 9 | BTCUSDT | 1d | RULE_C | 27.07% | 51.09% | 2.89 |
| 10 | BTCUSDT | 1h | RULE_A | 26.71% | 45.89% | 44.44 |
| 11 | BTCUSDT | 4h | RULE_A | 26.71% | 45.89% | 4.44 |
| 12 | BNBUSDT | 1h | RULE_B | 26.43% | 40.00% | 13.33 |
| 13 | ETHUSDT | 1h | RULE_C | 25.00% | 63.39% | 13.33 |
| 14 | ETHUSDT | 4h | RULE_C | 25.00% | 63.39% | 5.78 |
| 15 | SOLUSDT | 1h | RULE_C | 24.17% | 59.58% | 27.78 |

## 11. 현재 추적 우선순위

- #1 BNBUSDT 4h RULE_C surv=35.54% fail=45.30%
- #2 BNBUSDT 1h RULE_C surv=35.54% fail=45.30%
- #3 BNBUSDT 1d RULE_C surv=35.54% fail=45.30%
- #4 BTCUSDT 1h RULE_B surv=30.77% fail=39.42%
- #5 BTCUSDT 4h RULE_B surv=30.77% fail=39.42%
- #6 BNBUSDT 1h RULE_A surv=29.41% fail=40.00%
- #7 BTCUSDT 1h RULE_C surv=27.07% fail=51.09%
- #8 BTCUSDT 4h RULE_C surv=27.07% fail=51.09%
- #9 BTCUSDT 1d RULE_C surv=27.07% fail=51.09%
- #10 BTCUSDT 1h RULE_A surv=26.71% fail=45.89%

## 12. 핵심 결론

**RULE_B survival rate 22.84%** — 생존 이벤트는 structure(+0.36) 및 money_flow(+0.08) score가 높음.
- Survival Feature Contribution: 1.13% (Rule/Symbol/Regime 대비 유사)

- PNG: `wave_survival_segmentation.png`
