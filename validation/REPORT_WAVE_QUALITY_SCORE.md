# REPORT_WAVE_QUALITY_SCORE

Wave Quality Score — 통합 관측 레이어 검증

- events: 71

## 1. Quality Score별 성능

| score | count | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| 0 | 0 | — | — | — |
| 1 | 20 | 25.00% | -1.31 | 0.36 |
| 2 | 24 | 33.33% | -0.89 | 0.53 |
| 3 | 13 | 53.85% | 0.72 | 1.81 |
| 4 | 9 | 88.89% | 2.33 | 8.00 |
| 5 | 4 | 50.00% | -0.00 | 1.00 |
| 6 | 1 | 100.00% | 3.00 | inf |
| 7 | 0 | — | — | — |

## 2. Score 누적 (score≥k)

| threshold | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| >=1 | 71 | 43.66% | -0.20 | 0.87 |
| >=2 | 51 | 50.98% | 0.24 | 1.18 |
| >=3 | 27 | 66.67% | 1.24 | 2.62 |
| >=4 | 14 | 78.57% | 1.71 | 3.67 |
| >=5 | 5 | 60.00% | 0.60 | 1.50 |
| >=6 | 1 | 100.00% | 3.00 | inf |
| >=7 | 0 | — | — | — |

## 3. Top Quality Combination (상위 20)

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + MoneyFlow>=4 + price<MA480 | 4 | 75.00% | 1.85 | 5.62 |
| Bullish_OBV_Div + price<MA480 | 2 | 50.00% | 0.00 | 1.00 |
| Structure>=3 + MA120_slope>0 | 2 | 50.00% | 0.00 | 1.00 |
| price<MA480 + MA120_slope>0 | 2 | 50.00% | 0.00 | 1.00 |
| TRIPLE_BOTTOM_REQUIRED + Structure>=3 + price<MA480 + MA120_slope>0 | 2 | 50.00% | -0.00 | 1.00 |
| TRIPLE_BOTTOM_REQUIRED + MA120_slope>0 | 2 | 50.00% | -0.00 | 1.00 |
| MoneyFlow>=4 + price<MA480 | 3 | 33.33% | -1.00 | 0.50 |
| TRIPLE_BOTTOM_REQUIRED + price<MA480 | 3 | 33.33% | -1.00 | 0.50 |
| price<MA480 | 18 | 27.78% | -1.12 | 0.43 |
| Energy>=3 + price<MA480 | 8 | 25.00% | -1.50 | 0.33 |

## 4. Worst Quality Combination (하위 20)

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy>=3 + price<MA480 | 8 | 25.00% | -1.50 | 0.33 |
| price<MA480 | 18 | 27.78% | -1.12 | 0.43 |
| TRIPLE_BOTTOM_REQUIRED + price<MA480 | 3 | 33.33% | -1.00 | 0.50 |
| MoneyFlow>=4 + price<MA480 | 3 | 33.33% | -1.00 | 0.50 |
| TRIPLE_BOTTOM_REQUIRED + MA120_slope>0 | 2 | 50.00% | -0.00 | 1.00 |
| TRIPLE_BOTTOM_REQUIRED + Structure>=3 + price<MA480 + MA120_slope>0 | 2 | 50.00% | -0.00 | 1.00 |
| price<MA480 + MA120_slope>0 | 2 | 50.00% | 0.00 | 1.00 |
| Structure>=3 + MA120_slope>0 | 2 | 50.00% | 0.00 | 1.00 |
| Bullish_OBV_Div + price<MA480 | 2 | 50.00% | 0.00 | 1.00 |
| Energy>=3 + MoneyFlow>=4 + price<MA480 | 4 | 75.00% | 1.85 | 5.62 |

## 5. Quality Score vs Failure Rate

| score | n | failure_rate | strong_failure_rate |
|---|---:|---:|---:|
| 1 | 20 | 75.00% | 60.00% |
| 2 | 24 | 66.67% | 54.17% |
| 3 | 13 | 46.15% | 15.38% |
| 4 | 9 | 11.11% | 11.11% |
| 5 | 4 | 50.00% | 25.00% |
| 6 | 1 | 0.00% | 0.00% |

## 6. Quality Score vs Survival

| score | n | avg_survival_bars | avg_bucket_mid |
|---|---:|---:|---:|
| 1 | 20 | 23.40 | 26.03 |
| 2 | 24 | 27.21 | 29.69 |
| 3 | 13 | 35.69 | 28.50 |
| 4 | 9 | 29.44 | 31.79 |
| 5 | 4 | 15.00 | 18.25 |
| 6 | 1 | 8.00 | — |

## 7. Quality Score vs Forward Return

| score | n | avg_return_20 | avg_return_40 | avg_return_80 |
|---|---:|---:|---:|---:|
| 1 | 20 | -0.66% | -7.39% | -7.12% |
| 2 | 24 | -4.42% | -4.12% | -5.92% |
| 3 | 13 | -2.86% | -0.79% | -2.93% |
| 4 | 9 | -0.18% | -1.78% | -1.12% |
| 5 | 4 | 0.49% | 2.04% | 1.81% |
| 6 | 1 | 3.51% | -1.92% | -7.98% |

## 8. ETH / BTC 비교

| symbol | n | avg_quality_score | win_rate | expectancy |
|---|---:|---:|---:|---:|
| ETHUSDT | 57 | 2.46 | 38.60% | -0.46 |
| BTCUSDT | 14 | 2.07 | 64.29% | 0.86 |

## 9. 4h / 1d 비교

| tf | n | avg_quality_score | win_rate | expectancy |
|---|---:|---:|---:|---:|
| 4h | 57 | 2.46 | 38.60% | -0.46 |
| 1d | 14 | 2.07 | 64.29% | 0.86 |

## 10. Monotonicity 판정

**결과: FAIL**

- win_rate: FAIL — {1: 25.0, 2: 33.33333333333333, 3: 53.84615384615385, 4: 88.88888888888889, 5: 50.0, 6: 100.0}
- expectancy: FAIL — {1: -1.311104735310804, 2: -0.8870175874153574, 3: 0.7235950418191774, 4: 2.3333333333333366, 5: -2.4424906541753444e-15, 6: 3.0000000000000098}
- profit_factor: FAIL — {1: 0.3638825272442569, 2: 0.5299367672400435, 3: 1.8113966156009123, 4: 7.99999999999998, 5: 0.9999999999999983, 6: inf}

## Feature Importance Ranking

| rank | feature | n_on | n_off | expectancy_on | expectancy_off | delta |
|---:|---|---:|---:|---:|---:|---:|
| 1 | MoneyFlow>=4 | 22 | 49 | 0.84 | -0.66 | 1.50 |
| 2 | Structure>=3 | 20 | 51 | 0.85 | -0.61 | 1.46 |
| 3 | TRIPLE_BOTTOM_REQUIRED | 18 | 53 | 0.82 | -0.54 | 1.36 |
| 4 | MA120_slope>0 | 22 | 49 | 0.55 | -0.53 | 1.08 |
| 5 | Energy>=3 | 23 | 48 | 0.45 | -0.51 | 0.96 |
| 6 | Bullish_OBV_Div | 8 | 63 | 0.34 | -0.27 | 0.61 |
| 7 | price<MA480 | 56 | 15 | -0.25 | -0.02 | -0.23 |

## Score≥5 유의미성

| group | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| score>=5 | 5 | 60.00% | 0.60 | 1.50 |
| score<5 | 66 | 42.42% | -0.26 | 0.83 |

## 실전 최소 조건

- **Energy>=3 + MoneyFlow>=4 + price<MA480** — n=4, win_rate=75.00%, expectancy=1.85

## 이론 최종 평가

- Monotonicity: FAIL
- Score≥5 유의미: YES
- Overall: **PARTIAL**
- Supported layers: Wave (TB), Structure, Energy, Money Flow, Divergence, LTE (MA120 slope)
- Weak layers: LTE (MA480)

- PNG: `wave_quality_score.png`
