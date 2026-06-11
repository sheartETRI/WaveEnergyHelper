# REPORT_WAVE_CONFIRMATION

소파동 DB 이후 대파동 K 전환 지연시간 (관측 레이어)

## ETHUSDT 4h

- CSV: `wave_confirmation_ETHUSDT_4h.csv`
- PNG: `wave_confirmation_delay_ETHUSDT_4h.png`
- DB 에피소드 수: 66

### outcome 비율

- CROSS_CONFIRMED: 0.0%
- SLOPE_CONFIRMED: 0.0%
- TB_REQUIRED: 0.0%
- TB_CONFIRMED: 0.0%
- INVALIDATED: 100.0%
- NO_CONFIRM_WITHIN_WINDOW: 0.0%
- 평균 cross delay: 12.55 봉
- 평균 slope delay: 7.77 봉

### delay 분포

| delay | cross count | slope count |
|---:|---:|---:|
| 0 | 4 | 13 |
| 1 | 9 | 5 |
| 2 | 4 | 5 |
| 3 | 6 | 4 |
| 4 | 3 | 4 |
| 5 | 5 | 4 |
| 6 | 3 | 3 |
| 7 | 1 | 2 |
| 8 | 2 | 3 |
| 9 | 1 | 1 |
| 10 | 0 | 1 |
| 11 | 1 | 1 |
| 12 | 0 | 1 |
| 13 | 3 | 2 |
| 14 | 1 | 2 |
| 15 | 2 | 2 |
| 16 | 1 | 3 |
| 17 | 1 | 1 |
| 18 | 1 | 1 |
| 19 | 0 | 1 |
| 20 | 2 | 1 |
| 21 | 0 | 1 |
| 22 | 1 | 0 |
| 23 | 2 | 1 |
| 24 | 2 | 0 |
| 25 | 2 | 0 |
| 28 | 1 | 1 |
| 29 | 2 | 0 |
| 32 | 1 | 1 |
| 34 | 0 | 1 |
| 38 | 1 | 0 |
| 39 | 1 | 0 |
| 47 | 1 | 0 |
| 50 | 1 | 0 |
| 63 | 1 | 0 |

### 윈도별 확인 비율

| window | cross within % | slope within % |
|---:|---:|---:|
| 3 | 34.8 | 40.9 |
| 5 | 47.0 | 53.0 |
| 8 | 56.1 | 65.2 |
| 13 | 63.6 | 74.2 |

## BTCUSDT 1d

- CSV: `wave_confirmation_BTCUSDT_1d.csv`
- PNG: `wave_confirmation_delay_BTCUSDT_1d.png`
- DB 에피소드 수: 15

### outcome 비율

- CROSS_CONFIRMED: 0.0%
- SLOPE_CONFIRMED: 0.0%
- TB_REQUIRED: 0.0%
- TB_CONFIRMED: 0.0%
- INVALIDATED: 100.0%
- NO_CONFIRM_WITHIN_WINDOW: 0.0%
- 평균 cross delay: 19.79 봉
- 평균 slope delay: 7.33 봉

### delay 분포

| delay | cross count | slope count |
|---:|---:|---:|
| 0 | 0 | 2 |
| 1 | 2 | 1 |
| 2 | 1 | 0 |
| 3 | 0 | 3 |
| 4 | 0 | 2 |
| 5 | 1 | 0 |
| 6 | 2 | 1 |
| 7 | 0 | 1 |
| 9 | 1 | 0 |
| 10 | 0 | 1 |
| 11 | 0 | 1 |
| 12 | 1 | 0 |
| 14 | 0 | 1 |
| 16 | 1 | 1 |
| 28 | 0 | 1 |
| 35 | 1 | 0 |
| 38 | 1 | 0 |
| 39 | 1 | 0 |
| 50 | 1 | 0 |
| 57 | 1 | 0 |

### 윈도별 확인 비율

| window | cross within % | slope within % |
|---:|---:|---:|
| 3 | 20.0 | 40.0 |
| 5 | 26.7 | 53.3 |
| 8 | 40.0 | 66.7 |
| 13 | 53.3 | 80.0 |

## ETH / BTC 비교

| 지표 | ETHUSDT_4h | BTCUSDT_1d |
|---|---:|---:|
| DB 에피소드 | 66 | 15 |
| CROSS_CONFIRMED % | 0.0 | 0.0 |
| SLOPE_CONFIRMED % | 0.0 | 0.0 |
| TB_REQUIRED % | 0.0 | 0.0 |
| NO_CONFIRM % | 0.0 | 0.0 |
| 평균 cross delay | 12.55 | 19.79 |
| 평균 slope delay | 7.77 | 7.33 |

- window=3 cross within: 34.8% vs 20.0%
- window=5 cross within: 47.0% vs 26.7%
- window=8 cross within: 56.1% vs 40.0%
- window=13 cross within: 63.6% vs 53.3%
