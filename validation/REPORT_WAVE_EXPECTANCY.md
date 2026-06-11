# REPORT_WAVE_EXPECTANCY

TP3_SL3_TIMEOUT20 기준 Expectancy 분석

## ETHUSDT 4h

- CSV: `wave_expectancy_ETHUSDT_4h.csv`
- PNG: `wave_expectancy_ETHUSDT_4h.png`
- 에피소드: 57
- 전체 Expectancy: -0.46%
- 전체 승률: 38.60%

### Initial Type

| type | n | win | avg win | avg loss | expectancy |
|---|---:|---:|---:|---:|---:|
| SLOPE | 36 | 13 | 3.00 | 2.54 | -0.54 |
| CROSS | 14 | 7 | 3.00 | 2.67 | 0.16 |
| TB | 7 | 2 | 3.00 | 3.00 | -1.29 |

### State

| state | n | expectancy |
|---|---:|---:|
| TRIPLE_BOTTOM_REQUIRED | 9 | 1.97 |
| TRIPLE_BOTTOM_CONFIRMED | 3 | 1.00 |
| OTHER | 20 | -0.76 |
| WAVE3_CANDIDATE | 8 | -1.16 |
| WAVE3_COMPLETED | 17 | -1.31 |

### Family

| family | n | win | avg win | avg loss | expectancy |
|---|---:|---:|---:|---:|---:|
| BUY | 7 | 3 | 3.00 | 2.32 | -0.04 |
| NEUTRAL | 27 | 11 | 3.00 | 2.53 | -0.28 |
| SELL | 23 | 8 | 3.00 | 2.82 | -0.80 |

### Survival

| bucket | n | expectancy |
|---|---:|---:|
| 10-19 | 20 | -0.90 |
| 20-39 | 17 | -0.28 |
| 40+ | 13 | -0.02 |
| <10 | 7 | -0.43 |

### Verdict

| verdict | n | expectancy |
|---|---:|---:|
| ✅ 매수 관점 유효 (추세·대파동·타이밍 정렬) | 1 | 3.00 |
| ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 0.59 |
| ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 12 | -0.27 |
| ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 7 | -0.43 |
| ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 6 | -0.55 |
| ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 5 | -0.60 |
| 🟡 매도 관점 — 소파동 타이밍 대기 | 6 | -1.00 |
| ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 6 | -1.14 |
| 🟠 대파동 하락 — 상위 프레임 검증 미충족 | 5 | -1.80 |

### TOP_EXPECTANCY

1. state=TRIPLE_BOTTOM_REQUIRED — exp 1.97% (n=9, win 77.8%)
2. survival_bucket=10-19 & state=TRIPLE_BOTTOM_REQUIRED — exp 1.80% (n=5, win 80.0%)
3. initial_type=SLOPE & state=TRIPLE_BOTTOM_REQUIRED — exp 1.67% (n=7, win 71.4%)
4. initial_type=CROSS & survival_bucket=20-39 — exp 1.06% (n=5, win 60.0%)
5. survival_bucket=20-39 & family=NEUTRAL — exp 0.93% (n=8, win 50.0%)
6. survival_bucket=20-39 & stable_family=NEUTRAL — exp 0.93% (n=8, win 50.0%)
7. survival_bucket=<10 & family=NEUTRAL — exp 0.60% (n=5, win 60.0%)
8. survival_bucket=<10 & stable_family=NEUTRAL — exp 0.60% (n=5, win 60.0%)
9. verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 — exp 0.59% (n=9, win 55.6%)
10. family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 — exp 0.59% (n=9, win 55.6%)
11. stable_family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 — exp 0.59% (n=9, win 55.6%)
12. initial_type=CROSS & family=NEUTRAL — exp 0.59% (n=9, win 55.6%)
13. initial_type=CROSS & stable_family=NEUTRAL — exp 0.59% (n=9, win 55.6%)
14. initial_type=CROSS — exp 0.16% (n=14, win 50.0%)
15. survival_bucket=10-19 & family=SELL_FAMILY — exp -0.00% (n=8, win 50.0%)
16. survival_bucket=10-19 & stable_family=SELL_FAMILY — exp -0.00% (n=8, win 50.0%)
17. survival_bucket=40+ — exp -0.02% (n=13, win 46.2%)
18. initial_type=SLOPE & verdict=✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) — exp -0.03% (n=9, win 44.4%)
19. survival_bucket=20-39 & state=OTHER — exp -0.04% (n=7, win 42.9%)
20. family=BUY_FAMILY — exp -0.04% (n=7, win 42.9%)

### WORST_EXPECTANCY

1. survival_bucket=10-19 & state=WAVE3_COMPLETED — exp -3.00% (n=7, win 0.0%)
2. state=WAVE3_COMPLETED & family=SELL_FAMILY — exp -3.00% (n=5, win 0.0%)
3. state=WAVE3_COMPLETED & stable_family=SELL_FAMILY — exp -3.00% (n=5, win 0.0%)
4. initial_type=SLOPE & state=WAVE3_COMPLETED — exp -2.16% (n=10, win 10.0%)
5. state=WAVE3_CANDIDATE & family=SELL_FAMILY — exp -1.80% (n=5, win 20.0%)
6. state=WAVE3_CANDIDATE & stable_family=SELL_FAMILY — exp -1.80% (n=5, win 20.0%)
7. survival_bucket=10-19 & family=NEUTRAL — exp -1.80% (n=10, win 20.0%)
8. survival_bucket=10-19 & stable_family=NEUTRAL — exp -1.80% (n=10, win 20.0%)
9. verdict=🟠 대파동 하락 — 상위 프레임 검증 미충족 — exp -1.80% (n=5, win 20.0%)
10. family=SELL_FAMILY & verdict=🟠 대파동 하락 — 상위 프레임 검증 미충족 — exp -1.80% (n=5, win 20.0%)
11. stable_family=SELL_FAMILY & verdict=🟠 대파동 하락 — 상위 프레임 검증 미충족 — exp -1.80% (n=5, win 20.0%)
12. state=WAVE3_COMPLETED — exp -1.31% (n=17, win 23.5%)
13. initial_type=TB — exp -1.29% (n=7, win 28.6%)
14. survival_bucket=20-39 & family=SELL_FAMILY — exp -1.29% (n=7, win 28.6%)
15. survival_bucket=20-39 & stable_family=SELL_FAMILY — exp -1.29% (n=7, win 28.6%)
16. state=WAVE3_CANDIDATE — exp -1.16% (n=8, win 25.0%)
17. verdict=⚖️ 60MA 횡보 — 추세 미형성, 관망 — exp -1.14% (n=6, win 16.7%)
18. family=NEUTRAL & verdict=⚖️ 60MA 횡보 — 추세 미형성, 관망 — exp -1.14% (n=6, win 16.7%)
19. stable_family=NEUTRAL & verdict=⚖️ 60MA 횡보 — 추세 미형성, 관망 — exp -1.14% (n=6, win 16.7%)
20. survival_bucket=40+ & state=OTHER — exp -1.00% (n=6, win 33.3%)

### 조건 조합 (n≥5)

| condition | n | expectancy |
|---|---:|---:|
| survival_bucket=10-19 & state=TRIPLE_BOTTOM_REQUIRED | 5 | 1.80 |
| initial_type=SLOPE & state=TRIPLE_BOTTOM_REQUIRED | 7 | 1.67 |
| initial_type=CROSS & survival_bucket=20-39 | 5 | 1.06 |
| survival_bucket=20-39 & family=NEUTRAL | 8 | 0.93 |
| survival_bucket=20-39 & stable_family=NEUTRAL | 8 | 0.93 |
| survival_bucket=<10 & family=NEUTRAL | 5 | 0.60 |
| survival_bucket=<10 & stable_family=NEUTRAL | 5 | 0.60 |
| family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 0.59 |
| stable_family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 0.59 |
| initial_type=CROSS & family=NEUTRAL | 9 | 0.59 |
| initial_type=CROSS & stable_family=NEUTRAL | 9 | 0.59 |
| survival_bucket=10-19 & family=SELL_FAMILY | 8 | -0.00 |
| survival_bucket=10-19 & stable_family=SELL_FAMILY | 8 | -0.00 |
| initial_type=SLOPE & verdict=✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 9 | -0.03 |
| survival_bucket=20-39 & state=OTHER | 7 | -0.04 |

- Highest Profit Factor: state=TRIPLE_BOTTOM_REQUIRED — 6.39 (n=9)
- Highest Payoff Ratio: survival_bucket=20-39 & family=NEUTRAL — 2.65 (n=8)

### High Win / Low Expectancy

- survival_bucket=10-19 & family=SELL_FAMILY: win 50.0%, exp -0.00% (n=8)
- survival_bucket=10-19 & stable_family=SELL_FAMILY: win 50.0%, exp -0.00% (n=8)

### Low Win / High Expectancy


## BTCUSDT 1d

- CSV: `wave_expectancy_BTCUSDT_1d.csv`
- PNG: `wave_expectancy_BTCUSDT_1d.png`
- 에피소드: 14
- 전체 Expectancy: 0.86%
- 전체 승률: 64.29%

### Initial Type

| type | n | win | avg win | avg loss | expectancy |
|---|---:|---:|---:|---:|---:|
| SLOPE | 12 | 8 | 3.00 | 3.00 | 1.00 |
| CROSS | 2 | 1 | 3.00 | 3.00 | 0.00 |

### State

| state | n | expectancy |
|---|---:|---:|
| WAVE3_CANDIDATE | 1 | 3.00 |
| WAVE3_COMPLETED | 1 | 3.00 |
| OTHER | 8 | 0.75 |
| TRIPLE_BOTTOM_REQUIRED | 4 | -0.00 |

### Family

| family | n | win | avg win | avg loss | expectancy |
|---|---:|---:|---:|---:|---:|
| SELL | 4 | 3 | 3.00 | 3.00 | 1.50 |
| NEUTRAL | 9 | 6 | 3.00 | 3.00 | 1.00 |
| BUY | 1 | 0 | 0.00 | 3.00 | -3.00 |

### Survival

| bucket | n | expectancy |
|---|---:|---:|
| 40+ | 3 | -1.00 |
| 20-39 | 6 | 3.00 |
| 10-19 | 3 | -1.00 |
| <10 | 2 | 0.00 |

### Verdict

| verdict | n | expectancy |
|---|---:|---:|
| ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 3 | 3.00 |
| ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 1 | 3.00 |
| ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 4 | 1.50 |
| ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 2 | 0.00 |
| ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 3 | -1.00 |
| ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 1 | -3.00 |

### TOP_EXPECTANCY

1. survival_bucket=20-39 — exp 3.00% (n=6, win 100.0%)
2. initial_type=SLOPE & survival_bucket=20-39 — exp 3.00% (n=6, win 100.0%)
3. initial_type=SLOPE & state=OTHER — exp 1.29% (n=7, win 71.4%)
4. initial_type=SLOPE & family=NEUTRAL — exp 1.29% (n=7, win 71.4%)
5. initial_type=SLOPE & stable_family=NEUTRAL — exp 1.29% (n=7, win 71.4%)
6. family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
7. stable_family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
8. family=NEUTRAL & stable_family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
9. initial_type=SLOPE — exp 1.00% (n=12, win 66.7%)
10. state=OTHER — exp 0.75% (n=8, win 62.5%)

### WORST_EXPECTANCY

1. state=OTHER — exp 0.75% (n=8, win 62.5%)
2. initial_type=SLOPE — exp 1.00% (n=12, win 66.7%)
3. family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
4. stable_family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
5. family=NEUTRAL & stable_family=NEUTRAL — exp 1.00% (n=9, win 66.7%)
6. initial_type=SLOPE & family=NEUTRAL — exp 1.29% (n=7, win 71.4%)
7. initial_type=SLOPE & stable_family=NEUTRAL — exp 1.29% (n=7, win 71.4%)
8. initial_type=SLOPE & state=OTHER — exp 1.29% (n=7, win 71.4%)
9. survival_bucket=20-39 — exp 3.00% (n=6, win 100.0%)
10. initial_type=SLOPE & survival_bucket=20-39 — exp 3.00% (n=6, win 100.0%)

### 조건 조합 (n≥5)

| condition | n | expectancy |
|---|---:|---:|
| initial_type=SLOPE & survival_bucket=20-39 | 6 | 3.00 |
| initial_type=SLOPE & state=OTHER | 7 | 1.29 |
| initial_type=SLOPE & family=NEUTRAL | 7 | 1.29 |
| initial_type=SLOPE & stable_family=NEUTRAL | 7 | 1.29 |
| family=NEUTRAL & stable_family=NEUTRAL | 9 | 1.00 |

- Highest Profit Factor: initial_type=SLOPE & state=OTHER — 2.50 (n=7)
- Highest Payoff Ratio: state=OTHER — 1.00 (n=8)

### High Win / Low Expectancy


### Low Win / High Expectancy


## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| 전체 Expectancy | -0.46% | 0.86% |
| 전체 승률 | 38.60% | 64.29% |
| initial_type=SLOPE | -0.54 | 1.00 |
| initial_type=CROSS | 0.16 | 0.00 |
| initial_type=TB | -1.29 | — |
| family=NEUTRAL | -0.28 | 1.00 |
| family=SELL | -0.80 | 1.50 |
| family=BUY | -0.04 | -3.00 |
| survival_bucket=10-19 | -0.90 | -1.00 |
| survival_bucket=20-39 | -0.28 | 3.00 |
| survival_bucket=40+ | -0.02 | -1.00 |
| survival_bucket=<10 | -0.43 | 0.00 |
