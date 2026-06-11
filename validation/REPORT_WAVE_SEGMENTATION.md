# REPORT_WAVE_SEGMENTATION

TP3_SL3_TIMEOUT20 기준 성공/실패 Segmentation

## ETHUSDT 4h

- CSV: `wave_segmentation_ETHUSDT_4h.csv`
- PNG: `wave_segmentation_ETHUSDT_4h.png`
- TP3 에피소드: 57
- 전체 성공률: 38.6%

### 성공률 by feature

| feature | value | n | rate |
|---|---|---:|---:|
| initial_type | CROSS | 14 | 50.0% |
| initial_type | SLOPE | 36 | 36.1% |
| initial_type | TB | 7 | 28.6% |
| state | TRIPLE_BOTTOM_REQUIRED | 9 | 77.8% |
| state | TRIPLE_BOTTOM_CONFIRMED | 3 | 66.7% |
| state | OTHER | 20 | 35.0% |
| state | WAVE3_CANDIDATE | 8 | 25.0% |
| state | WAVE3_COMPLETED | 17 | 23.5% |
| survival_bucket | 40+ | 13 | 46.2% |
| survival_bucket | <10 | 7 | 42.9% |
| survival_bucket | 20-39 | 17 | 35.3% |
| survival_bucket | 10-19 | 20 | 35.0% |
| verdict | ✅ 매수 관점 유효 (추세·대파동·타이밍 정렬) | 1 | 100.0% |
| verdict | ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 55.6% |
| verdict | ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 7 | 42.9% |
| verdict | ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 12 | 41.7% |
| verdict | ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 5 | 40.0% |
| verdict | ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 6 | 33.3% |
| verdict | 🟡 매도 관점 — 소파동 타이밍 대기 | 6 | 33.3% |
| verdict | 🟠 대파동 하락 — 상위 프레임 검증 미충족 | 5 | 20.0% |
| verdict | ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 6 | 16.7% |
| category | 매수유효 | 1 | 100.0% |
| category | 기술적반등 | 16 | 50.0% |
| category | 매도유효 | 12 | 41.7% |
| category | 매도대기 | 6 | 33.3% |
| category | 매수계열기타 | 6 | 33.3% |
| category | 관망/혼조 | 11 | 27.3% |
| category | 하락지속 | 5 | 20.0% |
| family | BUY_FAMILY | 7 | 42.9% |
| family | NEUTRAL | 27 | 40.7% |
| family | SELL_FAMILY | 23 | 34.8% |
| stable_family | BUY_FAMILY | 7 | 42.9% |
| stable_family | NEUTRAL | 27 | 40.7% |
| stable_family | SELL_FAMILY | 23 | 34.8% |

### 실패율 by feature

| feature | value | n | rate |
|---|---|---:|---:|
| initial_type | TB | 7 | 71.4% |
| initial_type | SLOPE | 36 | 63.9% |
| initial_type | CROSS | 14 | 50.0% |
| state | WAVE3_COMPLETED | 17 | 76.5% |
| state | WAVE3_CANDIDATE | 8 | 75.0% |
| state | OTHER | 20 | 65.0% |
| state | TRIPLE_BOTTOM_CONFIRMED | 3 | 33.3% |
| state | TRIPLE_BOTTOM_REQUIRED | 9 | 22.2% |
| survival_bucket | 10-19 | 20 | 65.0% |
| survival_bucket | 20-39 | 17 | 64.7% |
| survival_bucket | <10 | 7 | 57.1% |
| survival_bucket | 40+ | 13 | 53.8% |
| verdict | ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 6 | 83.3% |
| verdict | 🟠 대파동 하락 — 상위 프레임 검증 미충족 | 5 | 80.0% |
| verdict | ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 6 | 66.7% |
| verdict | 🟡 매도 관점 — 소파동 타이밍 대기 | 6 | 66.7% |
| verdict | ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 5 | 60.0% |
| verdict | ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 12 | 58.3% |
| verdict | ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 7 | 57.1% |
| verdict | ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 44.4% |
| verdict | ✅ 매수 관점 유효 (추세·대파동·타이밍 정렬) | 1 | 0.0% |
| category | 하락지속 | 5 | 80.0% |
| category | 관망/혼조 | 11 | 72.7% |
| category | 매도대기 | 6 | 66.7% |
| category | 매수계열기타 | 6 | 66.7% |
| category | 매도유효 | 12 | 58.3% |
| category | 기술적반등 | 16 | 50.0% |
| category | 매수유효 | 1 | 0.0% |
| family | SELL_FAMILY | 23 | 65.2% |
| family | NEUTRAL | 27 | 59.3% |
| family | BUY_FAMILY | 7 | 57.1% |
| stable_family | SELL_FAMILY | 23 | 65.2% |
| stable_family | NEUTRAL | 27 | 59.3% |
| stable_family | BUY_FAMILY | 7 | 57.1% |

### TOP_SUCCESS_FACTORS

1. state=TRIPLE_BOTTOM_REQUIRED — success 77.8% (n=9)
2. verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 — success 55.6% (n=9)
3. initial_type=CROSS — success 50.0% (n=14)
4. category=기술적반등 — success 50.0% (n=16)
5. survival_bucket=40+ — success 46.2% (n=13)
6. survival_bucket=<10 — success 42.9% (n=7)
7. verdict=⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 — success 42.9% (n=7)
8. family=BUY_FAMILY — success 42.9% (n=7)
9. stable_family=BUY_FAMILY — success 42.9% (n=7)
10. verdict=✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) — success 41.7% (n=12)
11. category=매도유효 — success 41.7% (n=12)
12. family=NEUTRAL — success 40.7% (n=27)
13. stable_family=NEUTRAL — success 40.7% (n=27)
14. verdict=⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 — success 40.0% (n=5)
15. initial_type=SLOPE — success 36.1% (n=36)
16. survival_bucket=20-39 — success 35.3% (n=17)
17. state=OTHER — success 35.0% (n=20)
18. survival_bucket=10-19 — success 35.0% (n=20)
19. family=SELL_FAMILY — success 34.8% (n=23)
20. stable_family=SELL_FAMILY — success 34.8% (n=23)

### TOP_FAILURE_FACTORS

1. verdict=⚖️ 60MA 횡보 — 추세 미형성, 관망 — failure 83.3% (n=6)
2. verdict=🟠 대파동 하락 — 상위 프레임 검증 미충족 — failure 80.0% (n=5)
3. category=하락지속 — failure 80.0% (n=5)
4. state=WAVE3_COMPLETED — failure 76.5% (n=17)
5. state=WAVE3_CANDIDATE — failure 75.0% (n=8)
6. category=관망/혼조 — failure 72.7% (n=11)
7. initial_type=TB — failure 71.4% (n=7)
8. verdict=⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 — failure 66.7% (n=6)
9. verdict=🟡 매도 관점 — 소파동 타이밍 대기 — failure 66.7% (n=6)
10. category=매도대기 — failure 66.7% (n=6)
11. category=매수계열기타 — failure 66.7% (n=6)
12. family=SELL_FAMILY — failure 65.2% (n=23)
13. stable_family=SELL_FAMILY — failure 65.2% (n=23)
14. state=OTHER — failure 65.0% (n=20)
15. survival_bucket=10-19 — failure 65.0% (n=20)
16. survival_bucket=20-39 — failure 64.7% (n=17)
17. initial_type=SLOPE — failure 63.9% (n=36)
18. verdict=⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 — failure 60.0% (n=5)
19. family=NEUTRAL — failure 59.3% (n=27)
20. stable_family=NEUTRAL — failure 59.3% (n=27)

### 조건 조합 (n≥5)

| condition | n | success | success% |
|---|---|---:|---:|
| survival_bucket=10-19 & state=TRIPLE_BOTTOM_REQUIRED | 5 | 4 | 80.0 |
| survival>=20 & category=기술적반등 | 5 | 4 | 80.0 |
| initial_type=SLOPE & state=TRIPLE_BOTTOM_REQUIRED | 7 | 5 | 71.4 |
| survival>=20 & initial_type=CROSS | 8 | 5 | 62.5 |
| initial_type=CROSS & survival_bucket=20-39 | 5 | 3 | 60.0 |
| survival_bucket=<10 & family=NEUTRAL | 5 | 3 | 60.0 |
| survival_bucket=<10 & stable_family=NEUTRAL | 5 | 3 | 60.0 |
| survival_bucket=<10 & category=기술적반등 | 5 | 3 | 60.0 |
| initial_type=CROSS & family=NEUTRAL | 9 | 5 | 55.6 |
| initial_type=CROSS & stable_family=NEUTRAL | 9 | 5 | 55.6 |
| family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 5 | 55.6 |
| stable_family=NEUTRAL & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 5 | 55.6 |
| category=기술적반등 & verdict=⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 9 | 5 | 55.6 |
| initial_type=SLOPE & category=기술적반등 | 6 | 3 | 50.0 |
| survival_bucket=10-19 & family=SELL_FAMILY | 8 | 4 | 50.0 |

- strongest pair: survival_bucket=10-19 & state=TRIPLE_BOTTOM_REQUIRED — 80.0% (n=5)
- weakest pair: state=WAVE3_COMPLETED & stable_family=SELL_FAMILY — 0.0% (n=5)

## BTCUSDT 1d

- CSV: `wave_segmentation_BTCUSDT_1d.csv`
- PNG: `wave_segmentation_BTCUSDT_1d.png`
- TP3 에피소드: 14
- 전체 성공률: 64.3%

### 성공률 by feature

| feature | value | n | rate |
|---|---|---:|---:|
| initial_type | SLOPE | 12 | 66.7% |
| initial_type | CROSS | 2 | 50.0% |
| state | WAVE3_CANDIDATE | 1 | 100.0% |
| state | WAVE3_COMPLETED | 1 | 100.0% |
| state | OTHER | 8 | 62.5% |
| state | TRIPLE_BOTTOM_REQUIRED | 4 | 50.0% |
| survival_bucket | 20-39 | 6 | 100.0% |
| survival_bucket | <10 | 2 | 50.0% |
| survival_bucket | 10-19 | 3 | 33.3% |
| survival_bucket | 40+ | 3 | 33.3% |
| verdict | ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 3 | 100.0% |
| verdict | ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 1 | 100.0% |
| verdict | ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 4 | 75.0% |
| verdict | ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 2 | 50.0% |
| verdict | ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 3 | 33.3% |
| verdict | ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 1 | 0.0% |
| category | 매도유효 | 4 | 75.0% |
| category | 관망/혼조 | 3 | 66.7% |
| category | 기술적반등 | 6 | 66.7% |
| category | 매수계열기타 | 1 | 0.0% |
| family | SELL_FAMILY | 4 | 75.0% |
| family | NEUTRAL | 9 | 66.7% |
| family | BUY_FAMILY | 1 | 0.0% |
| stable_family | SELL_FAMILY | 4 | 75.0% |
| stable_family | NEUTRAL | 9 | 66.7% |
| stable_family | BUY_FAMILY | 1 | 0.0% |

### 실패율 by feature

| feature | value | n | rate |
|---|---|---:|---:|
| initial_type | CROSS | 2 | 50.0% |
| initial_type | SLOPE | 12 | 33.3% |
| state | TRIPLE_BOTTOM_REQUIRED | 4 | 50.0% |
| state | OTHER | 8 | 37.5% |
| state | WAVE3_CANDIDATE | 1 | 0.0% |
| state | WAVE3_COMPLETED | 1 | 0.0% |
| survival_bucket | 10-19 | 3 | 66.7% |
| survival_bucket | 40+ | 3 | 66.7% |
| survival_bucket | <10 | 2 | 50.0% |
| survival_bucket | 20-39 | 6 | 0.0% |
| verdict | ⏸️ 상승 추세이나 대파동 하락 — 눌림 진행 중 | 1 | 100.0% |
| verdict | ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰 | 3 | 66.7% |
| verdict | ⚖️ 60MA 횡보 — 추세 미형성, 관망 | 2 | 50.0% |
| verdict | ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬) | 4 | 25.0% |
| verdict | ⏸️ 하락 추세이나 대파동 상승 — 반등 진행 중 | 3 | 0.0% |
| verdict | ⚠️ 상승 추세 중 대파동 쌍봉 — 고점 경계 / 비중 축소 관점 | 1 | 0.0% |
| category | 매수계열기타 | 1 | 100.0% |
| category | 관망/혼조 | 3 | 33.3% |
| category | 기술적반등 | 6 | 33.3% |
| category | 매도유효 | 4 | 25.0% |
| family | BUY_FAMILY | 1 | 100.0% |
| family | NEUTRAL | 9 | 33.3% |
| family | SELL_FAMILY | 4 | 25.0% |
| stable_family | BUY_FAMILY | 1 | 100.0% |
| stable_family | NEUTRAL | 9 | 33.3% |
| stable_family | SELL_FAMILY | 4 | 25.0% |

### TOP_SUCCESS_FACTORS

1. survival_bucket=20-39 — success 100.0% (n=6)
2. initial_type=SLOPE — success 66.7% (n=12)
3. category=기술적반등 — success 66.7% (n=6)
4. family=NEUTRAL — success 66.7% (n=9)
5. stable_family=NEUTRAL — success 66.7% (n=9)
6. state=OTHER — success 62.5% (n=8)

### TOP_FAILURE_FACTORS

1. state=OTHER — failure 37.5% (n=8)
2. initial_type=SLOPE — failure 33.3% (n=12)
3. category=기술적반등 — failure 33.3% (n=6)
4. family=NEUTRAL — failure 33.3% (n=9)
5. stable_family=NEUTRAL — failure 33.3% (n=9)
6. survival_bucket=20-39 — failure 0.0% (n=6)

### 조건 조합 (n≥5)

| condition | n | success | success% |
|---|---|---:|---:|
| initial_type=SLOPE & survival_bucket=20-39 | 6 | 6 | 100.0 |
| survival>=20 & survival_bucket=20-39 | 6 | 6 | 100.0 |
| survival>=20 & initial_type=SLOPE | 9 | 7 | 77.8 |
| initial_type=SLOPE & state=OTHER | 7 | 5 | 71.4 |
| initial_type=SLOPE & family=NEUTRAL | 7 | 5 | 71.4 |
| initial_type=SLOPE & stable_family=NEUTRAL | 7 | 5 | 71.4 |
| survival>=20 & family=NEUTRAL | 7 | 5 | 71.4 |
| survival>=20 & stable_family=NEUTRAL | 7 | 5 | 71.4 |
| family=NEUTRAL & stable_family=NEUTRAL | 9 | 6 | 66.7 |
| family=NEUTRAL & category=기술적반등 | 6 | 4 | 66.7 |
| stable_family=NEUTRAL & category=기술적반등 | 6 | 4 | 66.7 |
| initial_type=SLOPE & category=기술적반등 | 5 | 3 | 60.0 |
| survival>=20 & category=기술적반등 | 5 | 3 | 60.0 |

- strongest pair: initial_type=SLOPE & survival_bucket=20-39 — 100.0% (n=6)
- weakest pair: survival>=20 & category=기술적반등 — 60.0% (n=5)

## ETH / BTC 비교

| 지표 | ETH | BTC |
|---|---:|---:|
| 전체 성공률 | 38.6% | 64.3% |
| | | |
| initial_type=CROSS | 50.0% | 50.0 |
| initial_type=SLOPE | 36.1% | 66.7 |
| initial_type=TB | 28.6% | — |
| | | |
| family=BUY_FAMILY | 42.9% | 0.0 |
| family=NEUTRAL | 40.7% | 66.7 |
| family=SELL_FAMILY | 34.8% | 75.0 |
| | | |
| stable_family=BUY_FAMILY | 42.9% | 0.0 |
| stable_family=NEUTRAL | 40.7% | 66.7 |
| stable_family=SELL_FAMILY | 34.8% | 75.0 |
| | | |
| survival_bucket=10-19 | 35.0% | 33.3 |
| survival_bucket=20-39 | 35.3% | 100.0 |
| survival_bucket=40+ | 46.2% | 33.3 |
| survival_bucket=<10 | 42.9% | 50.0 |
