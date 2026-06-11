# REPORT_WAVE_REGIME_GATED

Regime-Gated Validation — RULE_B + Regime Filter

## BASE_RULE (RULE_B)

- filter: BASE_RULE
- n: 37
- win_rate: 64.86%
- expectancy: 0.91%
- profit_factor: 2.24
- robustness_gap: 0.83

## Top Improvements

| filter | n | Δexp | Δwin | improvement |
|---|---:|---:|---:|---:|
| BASE_RULE+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+ema20_slope_3>0+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+atr_pct<=2.5+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+atr_pct<=3.0+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+volatility_20<=1.5+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+volatility_20<=2.0+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+volatility_20<=3.0+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+major_k>=40+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+major_k>=50+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+major_k>=60+major_k>=70 | 7 | 1.12 | 6.56 | 1.12 |
| BASE_RULE+dist_ema60_pct<=1.5+major_k>=70 | 3 | 0.99 | 1.80 | 0.99 |
| BASE_RULE+atr_pct<=2.0+major_k>=70 | 6 | 0.96 | 1.80 | 0.96 |
| BASE_RULE+rsi_slope_1>0+major_k>=70 | 6 | 0.96 | 1.80 | 0.96 |
| BASE_RULE+major_k>=60 | 11 | 0.93 | 7.86 | 0.93 |
| BASE_RULE+ema20_slope_3>0+major_k>=60 | 11 | 0.93 | 7.86 | 0.93 |

## Top Robust Rules

| filter | n | robustness_gap | expectancy |
|---|---:|---:|---:|
| BASE_RULE+dist_ema60_pct<=3.5+dist_ema60_pct<=5.0 | 34 | 0.04 | 0.90 |
| BASE_RULE+dist_ema60_pct<=5.0 | 34 | 0.04 | 0.90 |
| BASE_RULE+volatility_20<=3.0+dist_ema60_pct<=3.5 | 34 | 0.04 | 0.90 |
| BASE_RULE+dist_ema60_pct<=3.5 | 34 | 0.04 | 0.90 |
| BASE_RULE+volatility_20<=3.0+dist_ema60_pct<=5.0 | 34 | 0.04 | 0.90 |
| BASE_RULE+rsi_slope_1>0+major_k>=40 | 21 | 0.08 | 1.16 |
| BASE_RULE+rsi_slope_1>0+dist_ema60_pct<=2.5 | 23 | 0.17 | 0.73 |
| BASE_RULE+rsi_slope_1>0+atr_pct<=3.0 | 27 | 0.17 | 1.07 |
| BASE_RULE+rsi_slope_1>0+volatility_20<=2.0 | 27 | 0.17 | 1.07 |
| BASE_RULE+rsi_slope_1>0+volatility_20<=1.5 | 27 | 0.17 | 1.07 |
| BASE_RULE+rsi_slope_1>0+atr_pct<=2.5 | 27 | 0.17 | 1.07 |
| BASE_RULE+atr_pct<=2.0+major_k>=50 | 17 | 0.20 | 1.39 |
| BASE_RULE+atr_pct<=2.5+volatility_20<=1.5 | 33 | 0.20 | 1.02 |
| BASE_RULE+atr_pct<=3.0+volatility_20<=1.5 | 33 | 0.20 | 1.02 |
| BASE_RULE+volatility_20<=1.5 | 33 | 0.20 | 1.02 |

## Worst Filters

| filter | n | improvement |
|---|---:|---:|
| BASE_RULE+volatility_20<=0.5+major_k>=70 | 1 | -1.43 |
| BASE_RULE+volatility_20<=0.5+major_k>=60 | 4 | -0.29 |
| BASE_RULE+dist_ema60_pct<=1.5+major_k>=60 | 4 | -0.23 |
| BASE_RULE+volatility_20<=0.5+dist_ema60_pct<=1.5 | 8 | -0.22 |
| BASE_RULE+atr_pct<=1.5+major_k>=70 | 3 | -0.18 |
| BASE_RULE+rsi_slope_1>0+dist_ema60_pct<=2.5 | 23 | -0.18 |
| BASE_RULE+atr_pct<=2.5+dist_ema60_pct<=2.5 | 29 | -0.16 |
| BASE_RULE+dist_ema60_pct<=2.5+dist_ema60_pct<=5.0 | 29 | -0.16 |
| BASE_RULE+volatility_20<=2.0+dist_ema60_pct<=2.5 | 29 | -0.16 |
| BASE_RULE+atr_pct<=3.0+dist_ema60_pct<=2.5 | 29 | -0.16 |

## ETH / BTC / SOL / BNB (best filter vs BASE)

- best filter: BASE_RULE+major_k>=70

| symbol | base_n | gated_n | base exp | gated exp | Δexp | reduction% |
|---|---:|---:|---:|---:|---:|---:|
| ETHUSDT | 6 | 5 | 1.45 | 2.34 | 0.89 | 16.67 |
| BTCUSDT | 7 | 1 | -0.24 | 3.00 | 3.24 | 85.71 |
| SOLUSDT | 11 | 1 | 1.30 | -0.52 | -1.82 | 90.91 |
| BNBUSDT | 13 | 0 | 0.95 | — | — | 100.00 |

## 1h / 4h / 1d

| tf | base_n | gated_n | base exp | gated exp | Δexp | reduction% |
|---|---:|---:|---:|---:|---:|---:|
| 1h | 10 | 1 | 0.61 | -0.52 | -1.13 | 90.00 |
| 4h | 25 | 6 | 1.34 | 2.45 | 1.11 | 76.00 |
| 1d | 2 | 0 | -3.00 | — | — | 100.00 |

- Best Gated Rule: BASE_RULE+major_k>=70
- Best improvement: 1.12%
- PNG: `wave_regime_gated.png`
