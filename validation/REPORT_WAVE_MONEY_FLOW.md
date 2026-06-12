# REPORT_WAVE_MONEY_FLOW

Money Flow Layer — MFI/CMF/AD Observation

- events: 71

## 1. 성공 vs 실패

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| money_flow_score | 3.03 | 2.38 | 0.46 |
| cmf | 0.02 | -0.02 | 0.41 |
| ad_slope_10 | 15228.74 | -25442.75 | 0.38 |
| mfi | 44.46 | 39.07 | 0.33 |
| ad_slope_5 | 49602.56 | 49732.92 | 0.00 |

## 2. Top Money Flow Separators

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| money_flow_score | 3.03 | 2.38 | 0.46 |
| cmf | 0.02 | -0.02 | 0.41 |
| ad_slope_10 | 15228.74 | -25442.75 | 0.38 |
| mfi | 44.46 | 39.07 | 0.33 |
| ad_slope_5 | 49602.56 | 49732.92 | 0.00 |

## 3. Score별 성과

| score | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| 0 | 5 | 20.00% | -1.80 | 0.25 |
| 1 | 13 | 38.46% | -0.48 | 0.71 |
| 2 | 13 | 30.77% | -1.07 | 0.46 |
| 3 | 18 | 44.44% | -0.18 | 0.88 |
| 4 | 14 | 57.14% | 0.89 | 2.07 |
| 5 | 8 | 62.50% | 0.75 | 1.67 |

## 4. Energy + Money Flow

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + MoneyFlow>=3 | 16 | 68.75% | 1.21 | 2.43 |
| Energy>=3 + MoneyFlow>=4 | 11 | 72.73% | 1.49 | 3.16 |

## 5. Divergence + Money Flow

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| BullishDiv + MoneyFlow>=3 | 6 | 50.00% | 0.45 | 1.43 |
| BullishDiv + MoneyFlow>=4 | 2 | 50.00% | -0.00 | 1.00 |

## 6. TB + Money Flow

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TB + MoneyFlow (all) | 18 | 61.11% | 0.82 | 1.80 |
| TB + MoneyFlow>=3 | 10 | 80.00% | 2.07 | 7.30 |
| TB + MoneyFlow>=4 | 5 | 100.00% | 3.00 | inf |

## 7. WAVE3_COMPLETED + Money Flow

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| WAVE3_COMPLETED + MoneyFlow (all) | 21 | 28.57% | -0.93 | 0.48 |
| WAVE3_COMPLETED + MoneyFlow>=3 | 16 | 25.00% | -1.27 | 0.37 |
| WAVE3_COMPLETED + MoneyFlow>=4 | 10 | 30.00% | -0.83 | 0.52 |

## 8. Failure Reclassification

| cause | count | pct |
|---|---:|---:|
| MONEY_FLOW_SCORE<=1 | 12 | 30.00% |
| MONEY_FLOW_SCORE>1 | 28 | 70.00% |

## 9. ETH/BTC/SOL/BNB

| symbol | money_flow_score_avg | win_rate | expectancy | n |
|---|---:|---:|---:|---:|
| ETHUSDT | 2.82 | 38.60% | -0.46 | 57 |
| BTCUSDT | 2.00 | 64.29% | 0.86 | 14 |

## 10. 최종 Money Flow Pattern

### Triple Combo (Energy>=3 + MoneyFlow>=3 + BullishDiv)

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + MoneyFlow>=3 + BullishDiv | 1 | 100.00% | 3.00 | inf |

### Money Flow Timing

| offset | score | n |
|---|---:|---:|
| -20 | 2.66 | 71 |
| -10 | 2.25 | 71 |
| -5 | 1.68 | 71 |
| 0 | 2.66 | 71 |
| 5 | 2.63 | 71 |
| 10 | 2.93 | 71 |

- PNG: `wave_money_flow.png`
