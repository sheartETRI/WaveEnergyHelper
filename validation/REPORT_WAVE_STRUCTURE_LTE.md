# REPORT_WAVE_STRUCTURE_LTE

Structure LTE — Long-Term MA Context Observation

- events: 71

## 1. 성공 vs 실패 LTE 구조 차이

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| ma960_slope | -7.65 | -5.94 | 0.58 |
| ma480_slope | -71.72 | -33.85 | 0.32 |
| price_below_ma120 | 48.39 | 75.00 | 0.27 |
| ma120_slope | -262.08 | -135.19 | 0.26 |
| price_vs_ma240 | -6.14 | -9.26 | 0.26 |
| price_vs_ma120 | -3.62 | -5.67 | 0.23 |
| price_below_ma240 | 54.84 | 75.00 | 0.20 |
| ma240_slope | -111.95 | -60.65 | 0.20 |
| price_vs_ma960 | -21.48 | -20.25 | 0.11 |
| lte_position_score | 2.58 | 2.52 | 0.07 |
| price_below_ma960 | 64.52 | 67.50 | 0.03 |
| price_below_ma480 | 77.42 | 80.00 | 0.03 |
| price_vs_ma480 | -11.92 | -11.69 | 0.02 |

## 2. Top LTE Separators

| feature | success_mean | failure_mean | effect_size |
|---|---:|---:|---:|
| ma960_slope | -7.65 | -5.94 | 0.58 |
| ma480_slope | -71.72 | -33.85 | 0.32 |
| price_below_ma120 | 48.39 | 75.00 | 0.27 |
| ma120_slope | -262.08 | -135.19 | 0.26 |
| price_vs_ma240 | -6.14 | -9.26 | 0.26 |
| price_vs_ma120 | -3.62 | -5.67 | 0.23 |
| price_below_ma240 | 54.84 | 75.00 | 0.20 |
| ma240_slope | -111.95 | -60.65 | 0.20 |
| price_vs_ma960 | -21.48 | -20.25 | 0.11 |
| lte_position_score | 2.58 | 2.52 | 0.07 |

## 3. MA 위치별 성과

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| price_below_MA120 | 45 | 33.33% | -0.71 | 0.58 |
| price_above_MA120 | 26 | 61.54% | 0.69 | 1.60 |
| price_below_MA240 | 47 | 36.17% | -0.61 | 0.64 |
| price_above_MA240 | 24 | 58.33% | 0.61 | 1.54 |
| price_below_MA480 | 56 | 42.86% | -0.25 | 0.84 |
| price_above_MA480 | 15 | 46.67% | -0.02 | 0.99 |
| price_below_MA960 | 47 | 42.55% | -0.22 | 0.85 |
| price_above_MA960 | 24 | 45.83% | -0.15 | 0.90 |

## 4. MA slope별 성과

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| MA120_slope_up | 22 | 59.09% | 0.55 | 1.44 |
| MA120_slope_down | 49 | 36.73% | -0.53 | 0.67 |
| MA240_slope_up | 21 | 52.38% | 0.27 | 1.21 |
| MA240_slope_down | 50 | 40.00% | -0.40 | 0.75 |
| MA480_slope_up | 11 | 18.18% | -1.41 | 0.28 |
| MA480_slope_down | 57 | 49.12% | 0.08 | 1.06 |
| MA960_slope_up | 0 | — | — | — |
| MA960_slope_down | 45 | 42.22% | -0.23 | 0.85 |

## 5–7. TB + MA 조합

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TB+Structure>=3 + price<MA240 | 1 | 100.00% | 3.00 | inf |
| TB+Structure>=3 + price<MA480 | 6 | 83.33% | 2.00 | 5.00 |
| TB+Structure>=3 + MA480_slope>0 | 1 | 100.00% | 3.00 | inf |
| TB+Structure>=3 + MA960_slope>0 | 0 | — | — | — |
| TB+Structure>=3 + MA480_slope>0 + price<MA480 | 0 | — | — | — |
| TB+Structure>=3 + price<MA960 | 7 | 85.71% | 2.14 | 6.00 |

## 8. WAVE3 + LTE

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| WAVE3 + LTE (all) | 21 | 28.57% | -0.93 | 0.48 |
| WAVE3 + price<MA480 | 19 | 31.58% | -0.71 | 0.57 |
| WAVE3 + MA480_slope>0 | 4 | 0.00% | -2.32 | 0.00 |
| WAVE3 + MA480_slope>0 + price<MA480 | 2 | 0.00% | -1.64 | 0.00 |

## 9. ETH/BTC/SOL/BNB

| symbol | lte_score_avg | win_rate | expectancy | n |
|---|---:|---:|---:|---:|
| ETHUSDT | 2.65 | 38.60% | -0.46 | 57 |
| BTCUSDT | 2.14 | 64.29% | 0.86 | 14 |

## 10. 1h/4h/1d 비교

| tf | lte_score_avg | win_rate | expectancy | n |
|---|---:|---:|---:|---:|
| 4h | 2.65 | 38.60% | -0.46 | 57 |
| 1d | 2.14 | 64.29% | 0.86 | 14 |

## 최종 Structure + LTE Pattern

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TB + Structure>=3 + price<MA480 + MA480_slope>0 | 0 | — | — | — |

- PNG: `wave_structure_lte.png`
