# REPORT_WAVE_ENERGY_DIVERGENCE

Energy Divergence — OBV Accumulation Observation

- events: 71
- bullish_div_rate: 11.27%
- success_div_rate: 12.90%
- failure_div_rate: 10.00%

## 1. Bullish Divergence 발생률

- 전체: **11.27%**
- 성공 집단: **12.90%**
- 실패 집단: **10.00%**

## 2. 성공 vs 실패 비교

| metric | success | failure | effect_size |
|---|---:|---:|---:|
| obv_hl_pct | 114.45 | 2.85 | 0.74 |
| price_ll_pct | 2.44 | 1.88 | 0.30 |
| div_strength | 3.26 | 0.03 | 0.27 |
| bullish_div_rate | 12.90 | 10.00 | 0.03 |

## 3. Top Divergence Separators

| metric | success | failure | effect_size |
|---|---:|---:|---:|
| obv_hl_pct | 114.45 | 2.85 | 0.74 |
| price_ll_pct | 2.44 | 1.88 | 0.30 |
| div_strength | 3.26 | 0.03 | 0.27 |
| bullish_div_rate | 12.90 | 10.00 | 0.03 |

## 4. Wave + Divergence

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| TRIPLE_BOTTOM_REQUIRED + BULLISH_OBV_DIV | 1 | 0.00% | -0.29 | 0.00 |
| WAVE3_COMPLETED + BULLISH_OBV_DIV | 2 | 50.00% | -0.00 | 1.00 |
| DOUBLE_BOTTOM + BULLISH_OBV_DIV | 3 | 33.33% | -0.10 | 0.91 |

## 5. Energy Score + Divergence

| combo | n | win_rate | expectancy | profit_factor |
|---|---:|---:|---:|---:|
| Energy Score >= 3 + BULLISH_OBV_DIV | 2 | 100.00% | 3.00 | inf |
| Energy Score <= 1 + NO_DIV | 26 | 34.62% | -0.78 | 0.57 |

## 6. Failure Reclassification

| cause | count | pct |
|---|---:|---:|
| NO_BULLISH_DIV | 36 | 90.00% |
| HAS_BULLISH_DIV | 4 | 10.00% |

## 7. ETH/BTC/SOL/BNB 비교

| symbol | div_rate | expectancy | win_rate | n |
|---|---:|---:|---:|---:|
| ETHUSDT | 8.77% | -0.46 | 38.60% | 57 |
| BTCUSDT | 21.43% | 0.86 | 64.29% | 14 |

## Volume Event Timing

| offset | div_rate | n |
|---|---:|---:|
| -20 | 8.45% | 71 |
| -10 | 7.04% | 71 |
| -5 | 8.45% | 71 |
| 0 | 11.27% | 71 |
| 5 | 9.86% | 71 |
| 10 | 11.27% | 71 |

- PNG: `wave_energy_divergence.png`
