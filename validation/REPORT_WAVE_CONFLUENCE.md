# REPORT_WAVE_CONFLUENCE

MACD/RSI/EMA/변동성 Confluence 관측

## ETHUSDT 4h

- CSV: `wave_confluence_ETHUSDT_4h.csv`
- PNG: `wave_confluence_ETHUSDT_4h.png`
- 이벤트: 25 (success cohort 7, failure 11)

### Top Confluence Factors

1. rsi_bucket=60-70 — lift 2.62 (win 100.0%, n=5)
2. MACD_ABOVE_ZERO=True — lift 2.25 (win 85.7%, n=7)
3. MACD_BELOW_ZERO=False — lift 2.25 (win 85.7%, n=7)
4. PRICE_ABOVE_20=True — lift 2.19 (win 83.3%, n=6)
5. PRICE_ABOVE_60=True — lift 2.19 (win 83.3%, n=6)
6. EMA20_GT_60=True — lift 1.75 (win 66.7%, n=6)
7. RSI_RECOVERING=False — lift 1.53 (win 58.3%, n=12)
8. MACD_GC_RECENT=False — lift 1.31 (win 50.0%, n=14)
9. RSI_OVERSOLD=True — lift 1.31 (win 50.0%, n=2)
10. RSI_CROSS_50_RECENT=True — lift 1.31 (win 50.0%, n=6)
11. rsi_bucket=<30 — lift 1.31 (win 50.0%, n=2)
12. rsi — effect 1.27 (S:50.02 / F:36.03)
13. MACD_DC_RECENT=False — lift 1.24 (win 47.1%, n=17)
14. macd_signal — effect 1.22 (S:-1.23 / F:-51.37)
15. macd — effect 1.06 (S:-3.41 / F:-50.59)

### Top Confluence Bundles (n≥5)

| bundle | n | win | expectancy |
|---|---:|---:|---:|
| MACD_GC_RECENT=False & rsi_bucket=60-70 | 5 | 5 | 3.00 |
| MACD_DC_RECENT=False & rsi_bucket=60-70 | 5 | 5 | 3.00 |
| MACD_ABOVE_ZERO=True & RSI_RECOVERING=False | 6 | 6 | 3.00 |
| MACD_ABOVE_ZERO=True & rsi_bucket=60-70 | 5 | 5 | 3.00 |
| RSI_RECOVERING=False & rsi_bucket=60-70 | 5 | 5 | 3.00 |
| RSI_RECOVERING=False & PRICE_ABOVE_20=True | 5 | 5 | 3.00 |
| RSI_RECOVERING=False & PRICE_ABOVE_60=True | 5 | 5 | 3.00 |
| RSI_OVERSOLD=False & rsi_bucket=60-70 | 5 | 5 | 3.00 |
| rsi_bucket=60-70 & PRICE_ABOVE_20=True | 5 | 5 | 3.00 |
| rsi_bucket=60-70 & PRICE_ABOVE_60=True | 5 | 5 | 3.00 |
| branch_label=TRIPLE_BOTTOM_REQUIRED & RSI_RECOVERING=False | 5 | 5 | 3.00 |
| MACD_GC_RECENT=False & MACD_ABOVE_ZERO=True | 7 | 6 | 2.53 |
| MACD_DC_RECENT=False & MACD_ABOVE_ZERO=True | 7 | 6 | 2.53 |
| MACD_ABOVE_ZERO=True & RSI_OVERSOLD=False | 7 | 6 | 2.53 |
| MACD_GC_RECENT=False & PRICE_ABOVE_20=True | 6 | 5 | 2.45 |

### Score vs Win Rate

| score | count | win% |
|---:|---:|---:|
| 0 | 2 | 0.00 |
| 1 | 8 | 37.50 |
| 2 | 7 | 28.57 |
| 3 | 3 | 100.00 |
| 4 | 1 | 0.00 |

### Score vs Expectancy

| score | count | expectancy |
|---:|---:|---:|
| 0 | 2 | -2.48 |
| 1 | 8 | -0.75 |
| 2 | 7 | -1.29 |
| 3 | 3 | 3.00 |
| 4 | 1 | -0.29 |

### MACD Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| macd | -3.41 | -50.59 | 1.06 |
| macd_signal | -1.23 | -51.37 | 1.22 |
| macd_hist | -2.18 | 0.78 | 0.27 |
| macd_gap | -2.18 | 0.78 | 0.27 |

### RSI Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| rsi | 50.02 | 36.03 | 1.27 |
| rsi_slope_1 | -1.35 | 1.12 | 0.43 |
| rsi_slope_3 | -0.84 | -2.46 | 0.19 |

### EMA Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| ema20 | 2629.42 | 2567.36 | 0.11 |
| ema60 | 2633.10 | 2665.26 | 0.06 |
| ema120 | 2637.10 | 2731.13 | 0.16 |

## BTCUSDT 1d

- CSV: `wave_confluence_BTCUSDT_1d.csv`
- PNG: `wave_confluence_BTCUSDT_1d.png`
- 이벤트: 3 (success cohort 1, failure 2)

### Top Confluence Factors

1. rsi_slope_3 — effect 15.67 (S:9.73 / F:-3.74)
2. atr14 — effect 8.57 (S:2469.99 / F:3704.09)
3. rsi — effect 8.53 (S:62.50 / F:31.78)
4. atr_pct — effect 5.02 (S:3.30 / F:5.09)
5. macd — effect 4.02 (S:1245.38 / F:-3861.65)
6. ema120 — effect 3.68 (S:77167.06 / F:91901.40)
7. MACD_ABOVE_ZERO=True — lift 3.00 (win 100.0%, n=1)
8. MACD_BELOW_ZERO=False — lift 3.00 (win 100.0%, n=1)
9. PRICE_ABOVE_20=True — lift 3.00 (win 100.0%, n=1)
10. PRICE_ABOVE_60=True — lift 3.00 (win 100.0%, n=1)
11. rsi_bucket=60-70 — lift 3.00 (win 100.0%, n=1)
12. ema60 — effect 2.43 (S:71771.80 / F:86026.18)
13. macd_signal — effect 1.56 (S:596.81 / F:-3317.16)
14. MACD_GC_RECENT=False — lift 1.50 (win 50.0%, n=2)
15. RSI_RECOVERING=False — lift 1.50 (win 50.0%, n=2)

### Top Confluence Bundles (n≥5)

| bundle | n | win | expectancy |
|---|---:|---:|---:|

### Score vs Win Rate

| score | count | win% |
|---:|---:|---:|
| 1 | 1 | 100.00 |
| 2 | 2 | 0.00 |

### Score vs Expectancy

| score | count | expectancy |
|---:|---:|---:|
| 1 | 1 | 3.00 |
| 2 | 2 | -3.00 |

### MACD Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| macd | 1245.38 | -3861.65 | 4.02 |
| macd_signal | 596.81 | -3317.16 | 1.56 |
| macd_hist | 648.57 | -544.49 | 0.96 |
| macd_gap | 648.57 | -544.49 | 0.96 |

### RSI Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| rsi | 62.50 | 31.78 | 8.53 |
| rsi_slope_1 | 1.54 | 2.05 | 0.09 |
| rsi_slope_3 | 9.73 | -3.74 | 15.67 |

### EMA Comparison

| feature | success avg | failure avg | effect_size |
|---|---:|---:|---:|
| ema20 | 71179.33 | 79576.16 | 0.87 |
| ema60 | 71771.80 | 86026.18 | 2.43 |
| ema120 | 77167.06 | 91901.40 | 3.68 |

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| success cohort | 7 | 1 |
| failure cohort | 11 | 2 |
| top factor | rsi_bucket=60-70 | rsi_slope_3 |
