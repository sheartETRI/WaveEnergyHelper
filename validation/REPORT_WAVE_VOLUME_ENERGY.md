# REPORT_WAVE_VOLUME_ENERGY

Volume Energy Layer — Success vs Failure Observation

- events: 71
- success: 31
- failure: 40

## 1. Volume Feature 성공/실패 비교

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| vol_slope_5 | 18352.69 | -11895.66 | 0.57 |
| vol_ratio_20 | 1.19 | 0.87 | 0.44 |
| obv_slope_10 | -15015.22 | -94596.59 | 0.42 |
| vol_percentile_20 | 54.03 | 42.38 | 0.38 |
| energy_score | 2.42 | 1.88 | 0.35 |
| vol_slope_3 | 9148.20 | -5577.41 | 0.25 |
| obv | -2750733.11 | -3123538.53 | 0.25 |
| vol_percentile_60 | 51.40 | 45.58 | 0.18 |
| volume | 56898.56 | 68961.53 | 0.17 |
| vol_ratio_60 | 1.09 | 0.98 | 0.14 |
| obv_slope_3 | 85008.50 | 97318.18 | 0.07 |
| vol_slope_10 | -4428.43 | 816.18 | 0.06 |
| obv_slope_5 | 54074.70 | 47212.07 | 0.03 |

## 2. Top Volume Separators

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| vol_slope_5 | 18352.69 | -11895.66 | 0.57 |
| vol_ratio_20 | 1.19 | 0.87 | 0.44 |
| obv_slope_10 | -15015.22 | -94596.59 | 0.42 |
| vol_percentile_20 | 54.03 | 42.38 | 0.38 |
| energy_score | 2.42 | 1.88 | 0.35 |
| vol_slope_3 | 9148.20 | -5577.41 | 0.25 |
| obv | -2750733.11 | -3123538.53 | 0.25 |
| vol_percentile_60 | 51.40 | 45.58 | 0.18 |
| volume | 56898.56 | 68961.53 | 0.17 |
| vol_ratio_60 | 1.09 | 0.98 | 0.14 |

## 3. Energy Score별 성과

| score | n | win_rate | expectancy | profit_factor | avg_return |
|---|---:|---:|---:|---:|---:|
| 0 | 11 | 27.27% | -1.12 | 0.42 | -1.12 |
| 1 | 17 | 41.18% | -0.47 | 0.73 | -0.47 |
| 2 | 20 | 40.00% | -0.21 | 0.85 | -0.21 |
| 3 | 8 | 62.50% | 0.75 | 1.67 | 0.75 |
| 4 | 6 | 50.00% | 0.00 | 1.00 | 0.00 |
| 5 | 9 | 55.56% | 0.49 | 1.41 | 0.49 |

## 4. Wave + Energy 조합 성과

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TRIPLE_BOTTOM_REQUIRED + energy_score>=3 | 2 | 100.00% | 3.00 | inf |
| TRIPLE_BOTTOM_REQUIRED + vol_ratio_20>1.2 | 2 | 100.00% | 3.00 | inf |
| TRIPLE_BOTTOM_REQUIRED + obv_slope_5>0 | 8 | 75.00% | 1.84 | 5.48 |
| GRADE_A + energy_score>=3 | 0 | — | — | — |
| GRADE_A + obv_slope_5>0 | 0 | — | — | — |

## 5. Volume Event Timing

### Success

| offset | vol_ratio_20 | obv_slope_5 | n |
|---|---:|---:|---:|
| -10 | 1.14 | -46854.81 | 31 |
| -5 | 0.81 | -69089.92 | 31 |
| 0 | 1.19 | 54074.70 | 31 |
| 5 | 1.21 | 76242.24 | 31 |
| 10 | 0.91 | 65993.57 | 31 |

### Failure

| offset | vol_ratio_20 | obv_slope_5 | n |
|---|---:|---:|---:|
| -10 | 1.18 | -90785.18 | 40 |
| -5 | 1.16 | -141808.66 | 40 |
| 0 | 0.87 | 47212.07 | 40 |
| 5 | 1.02 | -103377.54 | 40 |
| 10 | 1.01 | -31155.36 | 40 |

## 6. Failure Reclassification

| failure_cause | count | pct |
|---|---:|---:|
| ENERGY_DEFICIENT (any) | 32 | 80.00% |
| Energy Score <= 1 | 18 | 45.00% |
| vol_ratio_20 < 1 | 31 | 77.50% |
| OBV slope 5 <= 0 | 19 | 47.50% |
| OTHER | 8 | 20.00% |

## 7. Symbol/TF 비교

| symbol | tf | energy_score_avg | expectancy | win_rate | n |
|---|---|---:|---:|---:|---:|
| ETHUSDT | 4h | 2.30 | -0.46 | 38.60% | 57 |
| BTCUSDT | 1d | 1.36 | 0.86 | 64.29% | 14 |

- PNG: `wave_volume_energy.png`
