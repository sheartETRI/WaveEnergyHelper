# Wave Entry Filter Refinement Report

Baseline (NO_EXIT cohort): n=1890, avg_return_20=0.27%, expectancy=0.27, survival=25.50%

## 1. Rule Filter 성과

| rule | n | avg_return_20 | expectancy | profit_factor | survival_rate | delta |
|---|---:|---:|---:|---:|---:|---:|
| RULE_A | 548 | 0.00% | 0.00 | 1.00 | 22.08% | -0.27 |
| RULE_B | 410 | 0.34% | 0.34 | 1.24 | 22.93% | 0.07 |
| RULE_C | 932 | 0.40% | 0.40 | 1.17 | 28.65% | 0.13 |

## 2. Symbol Filter 성과

| symbol | n | expectancy | profit_factor | survival_rate | delta |
|---|---:|---:|---:|---:|---:|
| BNBUSDT | 571 | 1.56 | 1.94 | 32.75% | 1.29 |
| BTCUSDT | 438 | 0.27 | 1.19 | 29.00% | 0.00 |
| ETHUSDT | 440 | -0.07 | 0.97 | 21.14% | -0.34 |
| SOLUSDT | 441 | -1.06 | 0.58 | 17.01% | -1.33 |

## 3. Regime Filter 성과

| regime | n | expectancy | survival_rate | delta |
|---|---:|---:|---:|---:|
| BULL | 1275 | 0.53 | 25.25% | 0.26 |
| BEAR | 252 | -1.26 | 19.05% | -1.53 |
| SIDEWAYS | 363 | 0.41 | 30.85% | 0.14 |

## 4. Feature Threshold 성과 (Top 12)

| feature | n | expectancy | profit_factor | survival_rate |
|---|---:|---:|---:|---:|
| quality_score>=4 | 750 | 0.91 | 1.70 | 27.60% |
| structure_score>=5 | 904 | 0.78 | 1.40 | 31.53% |
| money_flow_score>=5 | 924 | 0.70 | 1.37 | 29.11% |
| energy_score>=3 | 1477 | 0.56 | 1.28 | 28.17% |
| structure_score>=3 | 1463 | 0.45 | 1.24 | 26.52% |
| quality_score>=3 | 1553 | 0.42 | 1.23 | 26.40% |
| structure_score>=4 | 1331 | 0.41 | 1.22 | 26.45% |
| energy_score>=4 | 943 | 0.39 | 1.19 | 27.57% |
| money_flow_score>=4 | 1890 | 0.27 | 1.14 | 25.50% |
| watchlist_score>=20 | 777 | 0.12 | 1.08 | 24.84% |
| watchlist_score>=30 | 455 | -0.01 | 0.99 | 23.74% |

## 5. Champion Filter Top 20

| rank | filter_id | n | expectancy | pf | survival | delta | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | R_RULE_A|S_BNBUSDT|G_ALL|F_mf>=5,struct>=5 | 59 | 4.09 | 4.37 | 42.37% | 3.82 | 3.67 |
| 2 | R_RULE_A|S_BNBUSDT|G_ALL|F_mf>=5,qual>=3,struct>=5 | 59 | 4.09 | 4.37 | 42.37% | 3.82 | 3.67 |
| 3 | R_RULE_B|S_BNBUSDT|G_ALL|F_mf>=5,struct>=5 | 59 | 4.09 | 4.37 | 42.37% | 3.82 | 3.67 |
| 4 | R_RULE_B|S_BNBUSDT|G_ALL|F_mf>=5,qual>=3,struct>=5 | 59 | 4.09 | 4.37 | 42.37% | 3.82 | 3.67 |
| 5 | R_RULE_A|S_BNBUSDT|G_BULL|F_mf>=5,struct>=5 | 55 | 4.23 | 4.24 | 41.82% | 3.95 | 3.65 |
| 6 | R_RULE_A|S_BNBUSDT|G_BULL|F_mf>=5,qual>=3,struct>= | 55 | 4.23 | 4.24 | 41.82% | 3.95 | 3.65 |
| 7 | R_RULE_B|S_BNBUSDT|G_BULL|F_mf>=5,struct>=5 | 55 | 4.23 | 4.24 | 41.82% | 3.95 | 3.65 |
| 8 | R_RULE_B|S_BNBUSDT|G_BULL|F_mf>=5,qual>=3,struct>= | 55 | 4.23 | 4.24 | 41.82% | 3.95 | 3.65 |
| 9 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=4 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 10 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,struct>=3 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 11 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=3,st | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 12 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=4,st | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 13 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,struct>=4 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 14 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=3,st | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 15 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=4,st | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 16 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 17 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,wl>=20 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 18 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=3 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 19 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=3,wl | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |
| 20 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5,qual>=4 | 51 | 4.13 | 3.91 | 47.06% | 3.86 | 3.62 |

## 6. Worst Filter Top 20

| rank | filter_id | n | expectancy | score |
|---:|---|---:|---:|---:|
| 1 | R_ALL|S_SOLUSDT|G_BEAR|F_qual>=3 | 18 | -5.46 | -1.70 |
| 2 | R_ALL|S_SOLUSDT|G_BEAR|F_mf>=4,qual>=3 | 18 | -5.46 | -1.70 |
| 3 | R_RULE_C|S_SOLUSDT|G_SIDEWAYS|F_eng>=4,struct>=4 | 15 | -4.75 | -1.58 |
| 4 | R_RULE_C|S_SOLUSDT|G_SIDEWAYS|F_eng>=4,qual>=3,str | 15 | -4.75 | -1.58 |
| 5 | R_RULE_C|S_SOLUSDT|G_SIDEWAYS|F_eng>=4,mf>=4,struc | 15 | -4.75 | -1.58 |
| 6 | R_RULE_C|S_SOLUSDT|G_SIDEWAYS|F_eng>=4,mf>=4,qual> | 15 | -4.75 | -1.58 |
| 7 | R_RULE_C|S_SOLUSDT|G_ALL|F_mf>=5,struct>=5,wl>=20 | 24 | -4.68 | -1.42 |
| 8 | R_RULE_C|S_SOLUSDT|G_ALL|F_mf>=5,qual>=3,struct>=5 | 24 | -4.68 | -1.42 |
| 9 | R_RULE_C|S_SOLUSDT|G_ALL|F_eng>=3,mf>=5,struct>=5, | 24 | -4.68 | -1.42 |
| 10 | R_RULE_C|S_SOLUSDT|G_ALL|F_eng>=3,mf>=5,qual>=3,st | 24 | -4.68 | -1.42 |
| 11 | R_RULE_C|S_SOLUSDT|G_BULL|F_mf>=5,struct>=5,wl>=20 | 21 | -4.48 | -1.35 |
| 12 | R_RULE_C|S_SOLUSDT|G_BULL|F_mf>=5,qual>=3,struct>= | 21 | -4.48 | -1.35 |
| 13 | R_RULE_C|S_SOLUSDT|G_BULL|F_eng>=3,mf>=5,struct>=5 | 21 | -4.48 | -1.35 |
| 14 | R_RULE_C|S_SOLUSDT|G_BULL|F_eng>=3,mf>=5,qual>=3,s | 21 | -4.48 | -1.35 |
| 15 | R_RULE_C|S_SOLUSDT|G_ALL|F_eng>=4,mf>=5,struct>=5, | 23 | -4.35 | -1.31 |
| 16 | R_RULE_C|S_SOLUSDT|G_ALL|F_eng>=4,mf>=5,qual>=3,st | 23 | -4.35 | -1.31 |
| 17 | R_ALL|S_SOLUSDT|G_BEAR|F_mf>=5 | 16 | -4.18 | -1.25 |
| 18 | R_RULE_C|S_SOLUSDT|G_BULL|F_eng>=4,mf>=5,struct>=5 | 20 | -4.09 | -1.21 |
| 19 | R_RULE_C|S_SOLUSDT|G_BULL|F_eng>=4,mf>=5,qual>=3,s | 20 | -4.09 | -1.21 |
| 20 | R_ALL|S_SOLUSDT|G_SIDEWAYS|F_eng>=4,struct>=5 | 16 | -3.54 | -1.13 |

## 7. Robustness 분석

| rank | filter_id | cell+ | symbol+ | regime+ |
|---:|---|---:|---:|---:|
| 1 | R_RULE_A|S_BNBUSDT|G_ALL|F_mf>=5,struct> | 100.00% | 100.00% | 100.00% |
| 2 | R_RULE_A|S_BNBUSDT|G_ALL|F_mf>=5,qual>=3 | 100.00% | 100.00% | 100.00% |
| 3 | R_RULE_B|S_BNBUSDT|G_ALL|F_mf>=5,struct> | 100.00% | 100.00% | 100.00% |
| 4 | R_RULE_B|S_BNBUSDT|G_ALL|F_mf>=5,qual>=3 | 100.00% | 100.00% | 100.00% |
| 5 | R_RULE_A|S_BNBUSDT|G_BULL|F_mf>=5,struct | 100.00% | 100.00% | 100.00% |
| 6 | R_RULE_A|S_BNBUSDT|G_BULL|F_mf>=5,qual>= | 100.00% | 100.00% | 100.00% |
| 7 | R_RULE_B|S_BNBUSDT|G_BULL|F_mf>=5,struct | 100.00% | 100.00% | 100.00% |
| 8 | R_RULE_B|S_BNBUSDT|G_BULL|F_mf>=5,qual>= | 100.00% | 100.00% | 100.00% |
| 9 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 10 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 11 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 12 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 13 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 14 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 15 | R_RULE_A|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 16 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5 | 100.00% | 100.00% | 100.00% |
| 17 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 18 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 19 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |
| 20 | R_RULE_B|S_BNBUSDT|G_ALL|F_eng>=4,mf>=5, | 100.00% | 100.00% | 100.00% |

## 8. False Discovery 분석

| rank | n | confidence | stability | expectancy |
|---:|---:|---:|---:|---:|
| 1 | 59 | 73.75 | 100.00 | 4.09 |
| 2 | 59 | 73.75 | 100.00 | 4.09 |
| 3 | 59 | 73.75 | 100.00 | 4.09 |
| 4 | 59 | 73.75 | 100.00 | 4.09 |
| 5 | 55 | 68.75 | 100.00 | 4.23 |
| 6 | 55 | 68.75 | 100.00 | 4.23 |
| 7 | 55 | 68.75 | 100.00 | 4.23 |
| 8 | 55 | 68.75 | 100.00 | 4.23 |
| 9 | 51 | 63.75 | 100.00 | 4.13 |
| 10 | 51 | 63.75 | 100.00 | 4.13 |
| 11 | 51 | 63.75 | 100.00 | 4.13 |
| 12 | 51 | 63.75 | 100.00 | 4.13 |
| 13 | 51 | 63.75 | 100.00 | 4.13 |
| 14 | 51 | 63.75 | 100.00 | 4.13 |
| 15 | 51 | 63.75 | 100.00 | 4.13 |
| 16 | 51 | 63.75 | 100.00 | 4.13 |
| 17 | 51 | 63.75 | 100.00 | 4.13 |
| 18 | 51 | 63.75 | 100.00 | 4.13 |
| 19 | 51 | 63.75 | 100.00 | 4.13 |
| 20 | 51 | 63.75 | 100.00 | 4.13 |

## 9. Active Candidate Overlay

| rank | symbol | tf | rule | filter_match | exp | survival |
|---:|---|---|---|---|---:|---:|
| 1 | BTCUSDT | 1d | RULE_C | none | — | — |
| 2 | BTCUSDT | 1h | RULE_C | none | — | — |
| 3 | SOLUSDT | 1h | RULE_C | none | — | — |
| 4 | ETHUSDT | 1h | RULE_C | none | — | — |
| 5 | BNBUSDT | 1h | RULE_C | none | — | — |

## 10. 현재 관측 우선순위

- #1 BTCUSDT 1d RULE_C filter=none exp=—
- #2 BTCUSDT 1h RULE_C filter=none exp=—
- #3 SOLUSDT 1h RULE_C filter=none exp=—
- #4 ETHUSDT 1h RULE_C filter=none exp=—
- #5 BNBUSDT 1h RULE_C filter=none exp=—

## 11. 핵심 결론

**Champion #1: R_RULE_A|S_BNBUSDT|G_ALL|F_mf>=5,struct>=5** — expectancy 4.09 (delta 3.82), survival 42.37% (delta 16.87%).
- Expectancy+Survival 동시 개선 필터: **20**개

- PNG: `wave_entry_filter_refinement.png`
