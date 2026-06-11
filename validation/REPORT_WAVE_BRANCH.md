# REPORT_WAVE_BRANCH

DOUBLE_BOTTOM 분기(WAVE3_COMPLETED vs TRIPLE_BOTTOM_REQUIRED) Feature 비교

## ETHUSDT 4h

- CSV: `wave_branch_ETHUSDT_4h.csv`
- PNG: `wave_branch_ETHUSDT_4h.png`
- DOUBLE_BOTTOM 이벤트: 25
- 분석 대상: 25
- 기타 분기: 0

### Branch Count

| branch | count |
|---|---:|
| WAVE3_COMPLETED | 16 |
| TRIPLE_BOTTOM_REQUIRED | 9 |

### Branch Performance

| branch | n(linked) | win% | avg return | expectancy |
|---|---:|---:|---:|---:|
| WAVE3_COMPLETED | 14 | 21.43 | -1.64 | -1.64 |
| TRIPLE_BOTTOM_REQUIRED | 7 | 71.43 | 1.67 | 1.67 |

### Numeric Feature Comparison

| feature | completed avg | required avg | effect_size |
|---|---:|---:|---:|
| major_k | 34.88 | 60.79 | 1.06 |
| major_d | 30.15 | 57.27 | 1.29 |
| major_k_minus_d | 4.73 | 3.52 | 0.16 |
| major_k_slope_1 | 1.06 | -1.41 | 1.19 |
| major_k_slope_3 | 3.05 | -2.12 | 1.03 |
| major_d_slope_3 | 1.61 | 6.30 | 0.68 |
| bars_since_major_ll | 108.62 | 54.11 | 0.50 |
| bars_since_major_oversold | 10.38 | 22.67 | 0.54 |
| small_k | 48.88 | 41.69 | 0.50 |
| small_d | 53.61 | 38.73 | 1.20 |
| small_k_minus_d | -4.73 | 2.96 | 0.66 |
| recent_small_db_count_20 | 1.19 | 0.44 | 1.38 |
| ret_10 | -0.35 | -1.06 | 0.15 |
| ret_20 | -4.07 | -0.47 | 0.50 |
| ret_40 | -6.32 | -0.83 | 0.80 |
| volatility_20 | 1.45 | 1.13 | 0.58 |
| drawdown_20 | -5.59 | -4.16 | 0.29 |

### Categorical Feature Lift

| feature=value | n | required_rate% | lift |
|---|---:|---:|---:|
| major_k_level_bucket=20-40 | 6 | 0.00 | 0.00 |
| major_k_level_bucket=40-60 | 3 | 33.33 | 0.93 |
| major_k_level_bucket=60-80 | 6 | 66.67 | 1.85 |
| major_k_level_bucket=80+ | 3 | 66.67 | 1.85 |
| major_k_level_bucket=<20 | 7 | 28.57 | 0.79 |
| major_was_oversold_recent=False | 13 | 53.85 | 1.50 |
| major_was_oversold_recent=True | 12 | 16.67 | 0.46 |
| major_ll_recent=False | 17 | 41.18 | 1.14 |
| major_ll_recent=True | 8 | 25.00 | 0.69 |
| small_db_kind= | 25 | 36.00 | 1.00 |
| small_tb_recent=False | 16 | 31.25 | 0.87 |
| small_tb_recent=True | 9 | 44.44 | 1.23 |
| family_at_db=BUY_FAMILY | 3 | 66.67 | 1.85 |
| family_at_db=NEUTRAL | 14 | 21.43 | 0.60 |
| family_at_db=SELL_FAMILY | 8 | 50.00 | 1.39 |
| stable_family_at_db=BUY_FAMILY | 3 | 66.67 | 1.85 |
| stable_family_at_db=NEUTRAL | 14 | 21.43 | 0.60 |
| stable_family_at_db=SELL_FAMILY | 8 | 50.00 | 1.39 |
| category_at_db=관망/혼조 | 4 | 50.00 | 1.39 |
| category_at_db=기술적반등 | 10 | 10.00 | 0.28 |
| category_at_db=매도대기 | 1 | 0.00 | 0.00 |
| category_at_db=매도유효 | 6 | 50.00 | 1.39 |
| category_at_db=매수유효 | 3 | 66.67 | 1.85 |
| category_at_db=하락지속 | 1 | 100.00 | 2.78 |
| structure_label_at_db= | 19 | 36.84 | 1.02 |

### Top Numeric Separators

1. recent_small_db_count_20 — effect_size 1.38 (C:1.19 / R:0.44)
2. major_d — effect_size 1.29 (C:30.15 / R:57.27)
3. small_d — effect_size 1.20 (C:53.61 / R:38.73)
4. major_k_slope_1 — effect_size 1.19 (C:1.06 / R:-1.41)
5. major_k — effect_size 1.06 (C:34.88 / R:60.79)
6. major_k_slope_3 — effect_size 1.03 (C:3.05 / R:-2.12)
7. ret_40 — effect_size 0.80 (C:-6.32 / R:-0.83)
8. major_d_slope_3 — effect_size 0.68 (C:1.61 / R:6.30)
9. small_k_minus_d — effect_size 0.66 (C:-4.73 / R:2.96)
10. volatility_20 — effect_size 0.58 (C:1.45 / R:1.13)

### Top Categorical Separators

1. category_at_db=하락지속 — lift 2.78 (req rate 100.00%, n=1)
2. structure_label_at_db=U3 — lift 2.78 (req rate 100.00%, n=1)
3. zone_at_db=ABOVE_MA20 — lift 2.22 (req rate 80.00%, n=5)
4. major_k_level_bucket=60-80 — lift 1.85 (req rate 66.67%, n=6)
5. major_k_level_bucket=80+ — lift 1.85 (req rate 66.67%, n=3)
6. family_at_db=BUY_FAMILY — lift 1.85 (req rate 66.67%, n=3)
7. stable_family_at_db=BUY_FAMILY — lift 1.85 (req rate 66.67%, n=3)
8. category_at_db=매수유효 — lift 1.85 (req rate 66.67%, n=3)
9. major_was_oversold_recent=False — lift 1.50 (req rate 53.85%, n=13)
10. family_at_db=SELL_FAMILY — lift 1.39 (req rate 50.00%, n=8)

## BTCUSDT 1d

- CSV: `wave_branch_BTCUSDT_1d.csv`
- PNG: `wave_branch_BTCUSDT_1d.png`
- DOUBLE_BOTTOM 이벤트: 3
- 분석 대상: 3
- 기타 분기: 0

### Branch Count

| branch | count |
|---|---:|
| TRIPLE_BOTTOM_REQUIRED | 2 |
| WAVE3_COMPLETED | 1 |

### Branch Performance

| branch | n(linked) | win% | avg return | expectancy |
|---|---:|---:|---:|---:|
| WAVE3_COMPLETED | 1 | 100.00 | 3.00 | 3.00 |
| TRIPLE_BOTTOM_REQUIRED | 2 | 0.00 | -3.00 | -3.00 |

### Numeric Feature Comparison

| feature | completed avg | required avg | effect_size |
|---|---:|---:|---:|
| major_k | 80.76 | 22.05 | 6.99 |
| major_d | 52.90 | 23.63 | 25.02 |
| major_k_minus_d | 27.86 | -1.58 | 3.08 |
| major_k_slope_1 | 5.22 | -0.31 | 36.05 |
| major_k_slope_3 | 19.13 | -0.13 | 5.30 |
| major_d_slope_3 | 16.56 | -3.81 | 1.78 |
| bars_since_major_ll | 1.00 | 32.50 | 0.87 |
| bars_since_major_oversold | 10.00 | 3.50 | 1.31 |
| small_k | 77.49 | 36.08 | 1.71 |
| small_d | 64.50 | 42.91 | 0.70 |
| small_k_minus_d | 12.99 | -6.83 | 2.99 |
| recent_small_db_count_20 | 1.00 | 1.50 | 0.71 |
| ret_10 | 8.37 | -7.35 | 2.33 |
| ret_20 | 8.70 | -20.94 | 6.05 |
| ret_40 | 9.83 | -18.04 | 2.51 |
| volatility_20 | 2.00 | 3.66 | 0.90 |
| drawdown_20 | 0.00 | -19.52 | 18.78 |

### Categorical Feature Lift

| feature=value | n | required_rate% | lift |
|---|---:|---:|---:|
| major_k_level_bucket=20-40 | 1 | 100.00 | 1.50 |
| major_k_level_bucket=80+ | 1 | 0.00 | 0.00 |
| major_k_level_bucket=<20 | 1 | 100.00 | 1.50 |
| major_was_oversold_recent=False | 2 | 50.00 | 0.75 |
| major_was_oversold_recent=True | 1 | 100.00 | 1.50 |
| major_ll_recent=False | 1 | 100.00 | 1.50 |
| major_ll_recent=True | 2 | 50.00 | 0.75 |
| small_db_kind= | 3 | 66.67 | 1.00 |
| small_tb_recent=False | 2 | 100.00 | 1.50 |
| small_tb_recent=True | 1 | 0.00 | 0.00 |
| family_at_db=BUY_FAMILY | 1 | 0.00 | 0.00 |
| family_at_db=NEUTRAL | 1 | 100.00 | 1.50 |
| family_at_db=SELL_FAMILY | 1 | 100.00 | 1.50 |
| stable_family_at_db=BUY_FAMILY | 1 | 0.00 | 0.00 |
| stable_family_at_db=NEUTRAL | 1 | 100.00 | 1.50 |
| stable_family_at_db=SELL_FAMILY | 1 | 100.00 | 1.50 |
| category_at_db=기술적반등 | 1 | 100.00 | 1.50 |
| category_at_db=매도유효 | 1 | 100.00 | 1.50 |
| category_at_db=매수유효 | 1 | 0.00 | 0.00 |
| structure_label_at_db= | 1 | 100.00 | 1.50 |
| structure_label_at_db=D3 | 1 | 100.00 | 1.50 |
| structure_label_at_db=U1 | 1 | 0.00 | 0.00 |
| regime_at_db=DOWN | 3 | 66.67 | 1.00 |
| zone_at_db=BELOW_MA20 | 2 | 100.00 | 1.50 |
| zone_at_db=OUT_OF_SCOPE | 1 | 0.00 | 0.00 |

### Top Numeric Separators

1. major_k_slope_1 — effect_size 36.05 (C:5.22 / R:-0.31)
2. major_d — effect_size 25.02 (C:52.90 / R:23.63)
3. drawdown_20 — effect_size 18.78 (C:0.00 / R:-19.52)
4. major_k — effect_size 6.99 (C:80.76 / R:22.05)
5. ret_20 — effect_size 6.05 (C:8.70 / R:-20.94)
6. major_k_slope_3 — effect_size 5.30 (C:19.13 / R:-0.13)
7. major_k_minus_d — effect_size 3.08 (C:27.86 / R:-1.58)
8. small_k_minus_d — effect_size 2.99 (C:12.99 / R:-6.83)
9. ret_40 — effect_size 2.51 (C:9.83 / R:-18.04)
10. ret_10 — effect_size 2.33 (C:8.37 / R:-7.35)

### Top Categorical Separators

1. major_k_level_bucket=20-40 — lift 1.50 (req rate 100.00%, n=1)
2. major_k_level_bucket=<20 — lift 1.50 (req rate 100.00%, n=1)
3. major_was_oversold_recent=True — lift 1.50 (req rate 100.00%, n=1)
4. major_ll_recent=False — lift 1.50 (req rate 100.00%, n=1)
5. small_tb_recent=False — lift 1.50 (req rate 100.00%, n=2)
6. family_at_db=NEUTRAL — lift 1.50 (req rate 100.00%, n=1)
7. family_at_db=SELL_FAMILY — lift 1.50 (req rate 100.00%, n=1)
8. stable_family_at_db=NEUTRAL — lift 1.50 (req rate 100.00%, n=1)
9. stable_family_at_db=SELL_FAMILY — lift 1.50 (req rate 100.00%, n=1)
10. category_at_db=기술적반등 — lift 1.50 (req rate 100.00%, n=1)

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| WAVE3_COMPLETED count | 16 | 1 |
| WAVE3_COMPLETED win% | 21.43 | 100.00 |
| WAVE3_COMPLETED exp | -1.64 | 3.00 |
| TRIPLE_BOTTOM_REQUIRED count | 9 | 2 |
| TRIPLE_BOTTOM_REQUIRED win% | 71.43 | 0.00 |
| TRIPLE_BOTTOM_REQUIRED exp | 1.67 | -3.00 |
