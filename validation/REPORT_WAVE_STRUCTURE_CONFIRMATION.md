# REPORT_WAVE_STRUCTURE_CONFIRMATION

Structure Confirmation — HH/HL/Neckline Recovery Observation

- events: 71

## 1. 성공 vs 실패 Structure 차이

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| structure_score | 2.48 | 1.88 | 0.39 |
| hh | 61.29 | 30.00 | 0.31 |
| hhhl | 35.48 | 17.50 | 0.18 |
| hl | 48.39 | 40.00 | 0.08 |
| resistance_break | 6.45 | 5.00 | 0.01 |
| support_hold | 83.87 | 82.50 | 0.01 |
| neckline_recovery | 12.90 | 12.50 | 0.00 |

## 2. Top Structure Separators

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| structure_score | 2.48 | 1.88 | 0.39 |
| hh | 61.29 | 30.00 | 0.31 |
| hhhl | 35.48 | 17.50 | 0.18 |
| hl | 48.39 | 40.00 | 0.08 |
| resistance_break | 6.45 | 5.00 | 0.01 |
| support_hold | 83.87 | 82.50 | 0.01 |
| neckline_recovery | 12.90 | 12.50 | 0.00 |

## 3. Structure Score별 성과

| score | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| 0 | 4 | 75.00% | 1.50 | 3.00 |
| 1 | 29 | 20.69% | -1.49 | 0.29 |
| 2 | 18 | 55.56% | 0.33 | 1.25 |
| 3 | 3 | 33.33% | -0.10 | 0.91 |
| 4 | 10 | 80.00% | 1.80 | 4.00 |
| 5 | 4 | 50.00% | 0.57 | 1.62 |
| 6 | 3 | 33.33% | -1.00 | 0.50 |

## 4. Energy + Structure

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + Structure>=3 | 7 | 71.43% | 1.29 | 2.50 |
| Energy>=3 + Structure>=4 | 7 | 71.43% | 1.29 | 2.50 |

## 5. Money Flow + Structure

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| MF>=3 + Structure>=3 | 17 | 58.82% | 0.82 | 1.88 |
| MF>=4 + Structure>=4 | 11 | 63.64% | 1.03 | 2.16 |

## 6. TB + Structure

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TB + Structure>=3 | 8 | 87.50% | 2.25 | 7.00 |
| TB + Structure>=4 | 8 | 87.50% | 2.25 | 7.00 |

## 7. WAVE3_COMPLETED + Structure

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| WAVE3 + Structure (all) | 21 | 28.57% | -0.93 | 0.48 |
| WAVE3 + Structure>=3 | 6 | 33.33% | -0.62 | 0.62 |
| WAVE3 + Structure>=4 | 5 | 40.00% | -0.14 | 0.89 |

## 8. Failure Reclassification

| cause | count | pct |
|---|---:|---:|
| STRUCTURE_SCORE<=2 | 32 | 80.00% |
| STRUCTURE_SCORE>2 | 8 | 20.00% |

## 9. ETH/BTC/SOL/BNB

| symbol | structure_score_avg | win_rate | expectancy | n |
|---|---:|---:|---:|---:|
| ETHUSDT | 2.11 | 38.60% | -0.46 | 57 |
| BTCUSDT | 2.29 | 64.29% | 0.86 | 14 |

## 10. 최종 Structure Pattern

### Energy + MF + Structure

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + MF>=3 + Structure>=3 | 6 | 66.67% | 1.00 | 2.00 |

### Structure Timing

| offset | score | n |
|---|---:|---:|
| -20 | 2.58 | 71 |
| -10 | 2.34 | 71 |
| -5 | 1.87 | 71 |
| 0 | 2.14 | 71 |
| 5 | 2.25 | 71 |
| 10 | 2.31 | 71 |

- PNG: `wave_structure_confirmation.png`
