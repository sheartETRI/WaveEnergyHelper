# REPORT_WAVE_REGIME

Timeframe Regime Analysis — Rule이 동작하는 시장 구조

- 분석 Rule: RULE_A, RULE_B, RULE_D
- RULE_B 셀: 10 (success 6, failure 4)

## 4h vs 1d 차이 (RULE_B)

| feature | 4h avg | 1d avg | effect_size |
|---|---:|---:|---:|
| volatility_20 | 0.91 | 4.17 | 2.99 |
| atr_pct | 1.42 | 5.36 | 2.69 |
| rsi | 56.49 | 51.92 | 2.20 |
| dist_ema60_pct | 1.88 | 4.89 | 1.88 |
| ema20_slope_3 | 0.22 | -0.25 | 1.74 |
| major_k_slope_1 | -1.76 | -2.50 | 1.47 |
| ema60_slope_3 | 0.16 | 0.42 | 1.41 |
| rsi_slope_1 | 1.61 | 0.08 | 0.72 |
| dist_ema120_pct | 2.01 | 7.71 | 0.70 |
| ema120_slope_3 | 0.08 | 0.35 | 0.64 |
| major_k | 55.05 | 49.37 | 0.45 |
| macd_hist | -34.96 | -14.77 | 0.32 |

## Top Regime Separators (success vs failure cells, RULE_B)

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| volatility_20 | 0.65 | 2.50 | 1.29 |
| atr_pct | 1.03 | 3.11 | 1.07 |
| dist_ema60_pct | 1.41 | 3.06 | 0.90 |
| ema20_slope_3 | 0.18 | -0.05 | 0.87 |
| ema60_slope_3 | 0.12 | 0.27 | 0.80 |
| rsi_slope_1 | 1.72 | -0.19 | 0.75 |
| macd_hist | -9.99 | -42.29 | 0.70 |
| rsi | 56.54 | 54.77 | 0.51 |
| dist_ema120_pct | 1.34 | 4.48 | 0.50 |
| ema120_slope_3 | 0.05 | 0.20 | 0.46 |
| major_k_slope_1 | -2.00 | -1.67 | 0.29 |
| major_k | 54.69 | 55.24 | 0.04 |

## Timeframe Regime Profile (RULE_B cells)

| feature | 1h | 4h | 1d |
|---|---|---|---|
| ema20_slope_3 | 0.12 | 0.22 | -0.25 |
| ema60_slope_3 | 0.08 | 0.16 | 0.42 |
| ema120_slope_3 | 0.03 | 0.08 | 0.35 |
| atr_pct | 0.56 | 1.42 | 5.36 |
| volatility_20 | 0.48 | 0.91 | 4.17 |
| macd_hist | -14.93 | -34.96 | -14.77 |
| rsi | 57.12 | 56.49 | 51.92 |
| rsi_slope_1 | 0.74 | 1.61 | 0.08 |
| dist_ema60_pct | 0.85 | 1.88 | 4.89 |
| dist_ema120_pct | 0.62 | 2.01 | 7.71 |
| major_k | 57.55 | 55.05 | 49.37 |
| major_k_slope_1 | -1.65 | -1.76 | -2.50 |

## Regime Clusters (RULE_B events)

| cluster | n | win% | expectancy |
|---|---:|---:|---:|
| MID_VOL|TREND_DOWN | 1 | 100.00 | 3.00 |
| HIGH_VOL|TREND_UP | 9 | 88.89 | 2.33 |
| LOW_VOL|TREND_FLAT | 1 | 100.00 | 0.90 |
| LOW_VOL|TREND_UP | 10 | 70.00 | 0.83 |
| MID_VOL|TREND_UP | 8 | 50.00 | 0.65 |
| LOW_VOL|TREND_DOWN | 1 | 100.00 | 0.37 |
| MID_VOL|TREND_FLAT | 3 | 33.33 | 0.28 |
| HIGH_VOL|TREND_FLAT | 4 | 25.00 | -1.50 |

- Best Cluster: MID_VOL|TREND_DOWN (exp 3.00)
- Worst Cluster: HIGH_VOL|TREND_FLAT (exp -1.50)

## ETH / BTC / SOL / BNB (RULE_B)

| symbol | cells | success | avg exp | avg ATR% | avg major_k |
|---|---:|---:|---:|---:|---:|
| ETHUSDT | 3 | 1 | -0.33 | 1.88 | 68.56 |
| BTCUSDT | 2 | 1 | 0.07 | 0.75 | 48.85 |
| SOLUSDT | 2 | 2 | 1.23 | 1.33 | 54.50 |
| BNBUSDT | 3 | 2 | -0.22 | 2.94 | 45.59 |

## Rule Comparison

| rule | cells | success | top separator |
|---|---:|---:|---|
| RULE_A | 12 | 6 | rsi (1.29) |
| RULE_B | 10 | 6 | volatility_20 (1.29) |
| RULE_D | 10 | 6 | volatility_20 (1.27) |
