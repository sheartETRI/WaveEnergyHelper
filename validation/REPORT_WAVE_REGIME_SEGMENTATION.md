# REPORT — Wave Regime Segmentation

## Regime 정의

BULL: ema20_slope_3 > 0 AND ema60_slope_3 > 0; BEAR: ema20_slope_3 < 0 AND ema60_slope_3 < 0; SIDEWAYS: mixed slopes or missing

## 1. Rule × Regime 성과

| rule | regime | n | completed | wr20 | avg20 | exp20 | avg40 |
|---|---|---:|---:|---:|---:|---:|---:|
| RULE_A | BULL | 401 | 353 | 42.12% | 0.45% | 0.45% | -0.99% |
| RULE_A | BEAR | 89 | 87 | 33.71% | -1.91% | -1.91% | -3.42% |
| RULE_A | SIDEWAYS | 120 | 108 | 53.45% | 0.26% | 0.26% | -1.23% |
| RULE_B | BULL | 336 | 295 | 45.31% | 0.69% | 0.69% | -1.11% |
| RULE_B | BEAR | 28 | 26 | 32.14% | -1.41% | -1.41% | -5.47% |
| RULE_B | SIDEWAYS | 94 | 89 | 54.35% | -0.09% | -0.09% | -2.29% |
| RULE_C | BULL | 686 | 627 | 44.51% | 0.33% | 0.33% | -0.47% |
| RULE_C | BEAR | 151 | 139 | 37.41% | -0.57% | -0.57% | -1.93% |
| RULE_C | SIDEWAYS | 186 | 166 | 51.98% | 0.85% | 0.85% | 0.39% |

## 2. Symbol × Regime 성과

| symbol | regime | n | wr20 | avg20 | avg40 |
|---|---|---:|---:|---:|---:|
| BNBUSDT | BULL | 503 | 53.30% | 1.66% | -0.08% |
| BNBUSDT | BEAR | 60 | 61.02% | 0.97% | 0.25% |
| BNBUSDT | SIDEWAYS | 71 | 72.46% | 0.84% | 0.49% |
| BTCUSDT | BULL | 362 | 54.17% | 0.34% | -1.61% |
| BTCUSDT | BEAR | 57 | 39.29% | -0.57% | -0.27% |
| BTCUSDT | SIDEWAYS | 94 | 49.43% | 0.40% | -1.20% |
| ETHUSDT | BULL | 277 | 28.20% | -0.20% | 0.06% |
| ETHUSDT | BEAR | 92 | 25.00% | -1.47% | -3.83% |
| ETHUSDT | SIDEWAYS | 94 | 53.85% | 1.97% | 2.44% |
| SOLUSDT | BULL | 281 | 30.53% | -0.92% | -1.80% |
| SOLUSDT | BEAR | 59 | 22.81% | -3.21% | -6.76% |
| SOLUSDT | SIDEWAYS | 141 | 44.93% | -0.72% | -3.23% |

## 3. Rule × Symbol × Regime (sample)

| rule | symbol | regime | n | wr20 | avg20 | exp20 |
|---|---|---|---:|---:|---:|---:|
| RULE_A | BNBUSDT | BULL | 147 | 54.14% | 2.07% | 2.07% |
| RULE_A | BNBUSDT | BEAR | 20 | 65.00% | 1.01% | 1.01% |
| RULE_A | BNBUSDT | SIDEWAYS | 17 | 82.35% | 1.57% | 1.57% |
| RULE_A | BTCUSDT | BULL | 105 | 56.25% | 0.79% | 0.79% |
| RULE_A | BTCUSDT | BEAR | 19 | 36.84% | -2.34% | -2.34% |
| RULE_A | BTCUSDT | SIDEWAYS | 34 | 48.39% | 0.53% | 0.53% |
| RULE_A | ETHUSDT | BULL | 69 | 21.21% | -1.20% | -1.20% |
| RULE_A | ETHUSDT | BEAR | 38 | 15.79% | -2.94% | -2.94% |
| RULE_A | ETHUSDT | SIDEWAYS | 27 | 61.54% | 1.71% | 1.71% |
| RULE_A | SOLUSDT | BULL | 80 | 20.55% | -1.45% | -1.45% |
| RULE_A | SOLUSDT | BEAR | 12 | 33.33% | -2.84% | -2.84% |
| RULE_A | SOLUSDT | SIDEWAYS | 42 | 40.48% | -1.36% | -1.36% |
| RULE_B | BNBUSDT | BULL | 132 | 55.37% | 2.16% | 2.16% |
| RULE_B | BNBUSDT | BEAR | 6 | 50.00% | -0.12% | -0.12% |
| RULE_B | BNBUSDT | SIDEWAYS | 13 | 84.62% | 1.24% | 1.24% |
| RULE_B | BTCUSDT | BULL | 94 | 58.82% | 1.06% | 1.06% |
| RULE_B | BTCUSDT | BEAR | 1 | 100.00% | 0.87% | 0.87% |
| RULE_B | BTCUSDT | SIDEWAYS | 19 | 55.56% | 0.39% | 0.39% |
| RULE_B | ETHUSDT | BULL | 59 | 21.43% | -1.22% | -1.22% |
| RULE_B | ETHUSDT | BEAR | 16 | 31.25% | -0.38% | -0.38% |
| RULE_B | ETHUSDT | SIDEWAYS | 24 | 60.87% | 0.98% | 0.98% |
| RULE_B | SOLUSDT | BULL | 51 | 23.40% | -1.46% | -1.46% |
| RULE_B | SOLUSDT | BEAR | 5 | 0.00% | -6.71% | -6.71% |
| RULE_B | SOLUSDT | SIDEWAYS | 38 | 39.47% | -1.41% | -1.41% |
| RULE_C | BNBUSDT | BULL | 224 | 51.63% | 1.12% | 1.12% |
| RULE_C | BNBUSDT | BEAR | 34 | 60.61% | 1.14% | 1.14% |
| RULE_C | BNBUSDT | SIDEWAYS | 41 | 64.10% | 0.38% | 0.38% |
| RULE_C | BTCUSDT | BULL | 163 | 50.32% | -0.33% | -0.33% |
| RULE_C | BTCUSDT | BEAR | 37 | 38.89% | 0.32% | 0.32% |
| RULE_C | BTCUSDT | SIDEWAYS | 41 | 47.37% | 0.30% | 0.30% |
| RULE_C | ETHUSDT | BULL | 149 | 34.03% | 0.66% | 0.66% |
| RULE_C | ETHUSDT | BEAR | 38 | 31.58% | -0.46% | -0.46% |
| RULE_C | ETHUSDT | SIDEWAYS | 43 | 45.24% | 2.68% | 2.68% |
| RULE_C | SOLUSDT | BULL | 150 | 38.03% | -0.47% | -0.47% |
| RULE_C | SOLUSDT | BEAR | 42 | 22.50% | -2.89% | -2.89% |
| RULE_C | SOLUSDT | SIDEWAYS | 61 | 51.72% | 0.20% | 0.20% |

## 4. Champion Regime (avg20 Top 20)

| rank | rule | symbol | regime | n | avg20 |
|---:|---|---|---|---:|---:|
| 1 | RULE_C | ETHUSDT | SIDEWAYS | 43 | 2.68% |
| 2 | RULE_B | BNBUSDT | BULL | 132 | 2.16% |
| 3 | RULE_A | BNBUSDT | BULL | 147 | 2.07% |
| 4 | RULE_A | ETHUSDT | SIDEWAYS | 27 | 1.71% |
| 5 | RULE_A | BNBUSDT | SIDEWAYS | 17 | 1.57% |
| 6 | RULE_B | BNBUSDT | SIDEWAYS | 13 | 1.24% |
| 7 | RULE_C | BNBUSDT | BEAR | 34 | 1.14% |
| 8 | RULE_C | BNBUSDT | BULL | 224 | 1.12% |
| 9 | RULE_B | BTCUSDT | BULL | 94 | 1.06% |
| 10 | RULE_A | BNBUSDT | BEAR | 20 | 1.01% |
| 11 | RULE_B | ETHUSDT | SIDEWAYS | 24 | 0.98% |
| 12 | RULE_B | BTCUSDT | BEAR | 1 | 0.87% |
| 13 | RULE_A | BTCUSDT | BULL | 105 | 0.79% |
| 14 | RULE_C | ETHUSDT | BULL | 149 | 0.66% |
| 15 | RULE_A | BTCUSDT | SIDEWAYS | 34 | 0.53% |
| 16 | RULE_B | BTCUSDT | SIDEWAYS | 19 | 0.39% |
| 17 | RULE_C | BNBUSDT | SIDEWAYS | 41 | 0.38% |
| 18 | RULE_C | BTCUSDT | BEAR | 37 | 0.32% |
| 19 | RULE_C | BTCUSDT | SIDEWAYS | 41 | 0.30% |
| 20 | RULE_C | SOLUSDT | SIDEWAYS | 61 | 0.20% |

## 5. Worst Regime (avg20 Bottom 20)

| rank | rule | symbol | regime | n | avg20 |
|---:|---|---|---|---:|---:|
| 1 | RULE_B | SOLUSDT | BEAR | 5 | -6.71% |
| 2 | RULE_A | ETHUSDT | BEAR | 38 | -2.94% |
| 3 | RULE_C | SOLUSDT | BEAR | 42 | -2.89% |
| 4 | RULE_A | SOLUSDT | BEAR | 12 | -2.84% |
| 5 | RULE_A | BTCUSDT | BEAR | 19 | -2.34% |
| 6 | RULE_B | SOLUSDT | BULL | 51 | -1.46% |
| 7 | RULE_A | SOLUSDT | BULL | 80 | -1.45% |
| 8 | RULE_B | SOLUSDT | SIDEWAYS | 38 | -1.41% |
| 9 | RULE_A | SOLUSDT | SIDEWAYS | 42 | -1.36% |
| 10 | RULE_B | ETHUSDT | BULL | 59 | -1.22% |
| 11 | RULE_A | ETHUSDT | BULL | 69 | -1.20% |
| 12 | RULE_C | SOLUSDT | BULL | 150 | -0.47% |
| 13 | RULE_C | ETHUSDT | BEAR | 38 | -0.46% |
| 14 | RULE_B | ETHUSDT | BEAR | 16 | -0.38% |
| 15 | RULE_C | BTCUSDT | BULL | 163 | -0.33% |
| 16 | RULE_B | BNBUSDT | BEAR | 6 | -0.12% |
| 17 | RULE_C | SOLUSDT | SIDEWAYS | 61 | 0.20% |
| 18 | RULE_C | BTCUSDT | SIDEWAYS | 41 | 0.30% |
| 19 | RULE_C | BTCUSDT | BEAR | 37 | 0.32% |
| 20 | RULE_C | BNBUSDT | SIDEWAYS | 41 | 0.38% |

## 6. Positive Regime Ratio

| rule | regime_ratio | cell_ratio | symbol_ratio | signs |
|---|---:|---:|---:|---|
| RULE_A | 66.70% | 50.00% | 50.00% | BULL: +, BEAR: -, SIDE: + |
| RULE_B | 33.30% | 50.00% | 50.00% | BULL: +, BEAR: -, SIDE: - |
| RULE_C | 66.70% | 66.70% | 50.00% | BULL: +, BEAR: -, SIDE: + |

## 7. Failure Cause × Regime

| regime | n | STRUCTURE | MF_DROP | SL3 |
|---|---:|---:|---:|---:|
| BULL | 746 | 58.00% | 23.30% | 18.60% |
| BEAR | 170 | 26.50% | 52.90% | 20.60% |
| SIDEWAYS | 181 | 56.90% | 19.30% | 23.80% |

## 8. Contribution 분석 (SS %)

- 이전 (Symbol Seg #19): Rule 0.03%, Symbol 1.89%
- **Rule**: 0.03%
- **Symbol**: 1.89%
- **Regime**: 0.57%
- **Residual**: 97.51%

## 9. Active Candidate Regime Overlay

| rank | symbol | tf | rule | regime | hist20_regime | exp20_regime | score |
|---:|---|---|---|---|---:|---:|---:|
| 1 | ETHUSDT | 4h | RULE_C | SIDEWAYS | 2.68% | 2.68% | 5.78 |
| 2 | BNBUSDT | 1h | RULE_B | BULL | 2.16% | 2.16% | 13.33 |
| 3 | BNBUSDT | 1h | RULE_A | BULL | 2.07% | 2.07% | 17.78 |
| 4 | ETHUSDT | 4h | RULE_A | SIDEWAYS | 1.71% | 1.71% | 0.00 |
| 5 | BNBUSDT | 1h | RULE_C | BULL | 1.12% | 1.12% | 8.89 |
| 6 | BNBUSDT | 1d | RULE_C | BULL | 1.12% | 1.12% | 5.00 |
| 7 | BTCUSDT | 1h | RULE_B | BULL | 1.06% | 1.06% | 66.67 |
| 8 | ETHUSDT | 4h | RULE_B | SIDEWAYS | 0.98% | 0.98% | 0.00 |
| 9 | BTCUSDT | 1h | RULE_A | BULL | 0.79% | 0.79% | 44.44 |
| 10 | ETHUSDT | 1h | RULE_C | BULL | 0.66% | 0.66% | 13.33 |
| 11 | BTCUSDT | 4h | RULE_A | SIDEWAYS | 0.53% | 0.53% | 4.44 |
| 12 | BTCUSDT | 4h | RULE_B | SIDEWAYS | 0.39% | 0.39% | 6.67 |
| 13 | BNBUSDT | 4h | RULE_C | SIDEWAYS | 0.38% | 0.38% | 11.56 |
| 14 | BTCUSDT | 4h | RULE_C | SIDEWAYS | 0.30% | 0.30% | 3.33 |
| 15 | SOLUSDT | 4h | RULE_C | SIDEWAYS | 0.20% | 0.20% | 4.62 |

## 10. 현재 관측 우선순위

- #1 ETHUSDT 4h RULE_C regime=SIDEWAYS hist20=2.68%
- #2 BNBUSDT 1h RULE_B regime=BULL hist20=2.16%
- #3 BNBUSDT 1h RULE_A regime=BULL hist20=2.07%
- #4 ETHUSDT 4h RULE_A regime=SIDEWAYS hist20=1.71%
- #5 BNBUSDT 1h RULE_C regime=BULL hist20=1.12%
- #6 BNBUSDT 1d RULE_C regime=BULL hist20=1.12%
- #7 BTCUSDT 1h RULE_B regime=BULL hist20=1.06%
- #8 ETHUSDT 4h RULE_B regime=SIDEWAYS hist20=0.98%
- #9 BTCUSDT 1h RULE_A regime=BULL hist20=0.79%
- #10 ETHUSDT 1h RULE_C regime=BULL hist20=0.66%

## 11. 핵심 결론

**Symbol 효과 > Regime > Rule — BNB + 특정 Regime 조합 주목**
- RULE_B Positive Regime Ratio: 33.30% (BULL: +, BEAR: -, SIDE: -)

- PNG: `wave_regime_segmentation.png`
