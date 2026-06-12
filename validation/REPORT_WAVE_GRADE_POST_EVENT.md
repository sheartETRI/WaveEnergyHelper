# REPORT_WAVE_GRADE_POST_EVENT

Grade A Post-Event Outcome — Delayed Entry Analysis

- Grade A events: 7
- reference policy: TP5_SL3_TIMEOUT40
- valid_until_delay: -1

## Delay Outcome

| delay | win_rate | expectancy | n |
|---|---:|---:|---:|
| 0 | 20.00% | -1.48 | 35 |
| 1 | 22.86% | -1.48 | 35 |
| 2 | 34.29% | -1.33 | 35 |
| 3 | 34.29% | -0.82 | 35 |

## Forward Return

| delay | +5 | +10 | +20 | +40 |
|---|---|---|---|---|
| 0 | -1.12% | -1.51% | -0.35% | -1.38% |
| 1 | -0.81% | -1.04% | -0.54% | -2.09% |
| 2 | -0.85% | -0.08% | -0.05% | -1.45% |
| 3 | -0.41% | -0.01% | -0.46% | -1.46% |

## Exit Policy by Delay

| delay | policy | expectancy | win_rate | profit_factor | avg_bars_held |
|---|---|---:|---:|---:|---:|
| 0 | TP3_SL3_TIMEOUT20 | -1.42 | 14.29% | 0.23 | 10.86 |
| 0 | TP5_SL3_TIMEOUT40 | -1.32 | 28.57% | 0.38 | 14.43 |
| 0 | TP5_KTURN_TIMEOUT40 | -2.62 | 0.00% | 0.00 | 11.00 |
| 0 | K_CROSS_DOWN_TIMEOUT40 | -0.96 | 14.29% | 0.18 | 12.14 |
| 0 | WAVE_INVALIDATION_EXIT | -1.09 | 42.86% | 0.59 | 30.29 |
| 1 | TP3_SL3_TIMEOUT20 | -1.56 | 14.29% | 0.22 | 9.29 |
| 1 | TP5_SL3_TIMEOUT40 | -1.30 | 28.57% | 0.39 | 12.71 |
| 1 | TP5_KTURN_TIMEOUT40 | -2.11 | 14.29% | 0.14 | 11.14 |
| 1 | K_CROSS_DOWN_TIMEOUT40 | -0.89 | 14.29% | 0.18 | 11.29 |
| 1 | WAVE_INVALIDATION_EXIT | -1.52 | 42.86% | 0.47 | 29.86 |
| 2 | TP3_SL3_TIMEOUT20 | -1.68 | 28.57% | 0.21 | 9.00 |
| 2 | TP5_SL3_TIMEOUT40 | -1.24 | 28.57% | 0.42 | 12.29 |
| 2 | TP5_KTURN_TIMEOUT40 | -1.16 | 28.57% | 0.39 | 10.57 |
| 2 | K_CROSS_DOWN_TIMEOUT40 | -1.66 | 42.86% | 0.32 | 21.14 |
| 2 | WAVE_INVALIDATION_EXIT | -0.89 | 42.86% | 0.64 | 29.43 |
| 3 | TP3_SL3_TIMEOUT20 | -0.58 | 42.86% | 0.61 | 13.71 |
| 3 | TP5_SL3_TIMEOUT40 | 0.21 | 42.86% | 1.14 | 19.57 |
| 3 | TP5_KTURN_TIMEOUT40 | -1.02 | 14.29% | 0.41 | 9.57 |
| 3 | K_CROSS_DOWN_TIMEOUT40 | -1.90 | 28.57% | 0.24 | 21.14 |
| 3 | WAVE_INVALIDATION_EXIT | -0.81 | 42.86% | 0.65 | 29.00 |

## Validity Window

- valid_until_delay: **-1**

| delay | expectancy | win_rate | valid |
|---|---:|---:|---|
| 0 | -1.32 | 28.57% | no |
| 1 | -1.30 | 28.57% | no |
| 2 | -1.24 | 28.57% | no |
| 3 | 0.21 | 42.86% | no |

## Failure After Grade A

| category | count | pct |
|---|---:|---:|
| STOP_LOSS | 9 | 27.27% |
| TIMEOUT | 8 | 24.24% |
| K_TURN_DOWN | 7 | 21.21% |
| K_CROSS_DOWN | 6 | 18.18% |
| NEW_LL | 0 | 0.00% |
| RE_OVERSOLD | 3 | 9.09% |

## Symbol/TF Comparison

| symbol | tf | delay | expectancy | win_rate | n |
|---|---|---|---:|---:|---:|
| ETHUSDT | 4h | 0 | -1.44 | 16.00% | 25 |
| ETHUSDT | 4h | 1 | -1.44 | 20.00% | 25 |
| ETHUSDT | 4h | 2 | -1.37 | 24.00% | 25 |
| ETHUSDT | 4h | 3 | -0.62 | 32.00% | 25 |
| BTCUSDT | 4h | 0 | -3.01 | 20.00% | 5 |
| BTCUSDT | 4h | 1 | -3.08 | 20.00% | 5 |
| BTCUSDT | 4h | 2 | -3.12 | 20.00% | 5 |
| BTCUSDT | 4h | 3 | -3.17 | 20.00% | 5 |
| SOLUSDT | 1h | 0 | -0.14 | 40.00% | 5 |
| SOLUSDT | 1h | 1 | -0.04 | 40.00% | 5 |
| SOLUSDT | 1h | 2 | 0.67 | 100.00% | 5 |
| SOLUSDT | 1h | 3 | 0.54 | 60.00% | 5 |

- PNG: `wave_grade_post_event.png`
