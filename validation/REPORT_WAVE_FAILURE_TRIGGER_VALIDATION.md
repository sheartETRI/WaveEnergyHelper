# Wave Failure Trigger Validation Report

실패 이벤트 조기 무효화 trigger 검증 (관측 전용).

## 1. Trigger 성능 (Precision / Recall / F1)

| trigger | n | precision | recall | f1 | false_exit_rate |
|---|---:|---:|---:|---:|---:|
| STRUCTURE_FAIL | 1586 | 60.09% | 91.55% | 72.55% | 58.92% |
| MONEY_FLOW_DROP | 1862 | 55.91% | 100.00% | 71.72% | 94.19% |
| ENERGY_DROP | 1890 | 55.08% | 100.00% | 71.03% | 100.00% |
| STOP_LOSS_3 | 845 | 78.22% | 63.50% | 70.10% | 26.14% |
| NEW_LL | 126 | 46.83% | 5.67% | 10.11% | 8.51% |
| K_TURN_DOWN | 1796 | 54.57% | 94.14% | 69.09% | 97.72% |
| K_CROSS_DOWN | 1647 | 55.86% | 88.38% | 68.45% | 86.10% |
| RE_OVERSOLD | 258 | 98.06% | 24.30% | 38.95% | 0.41% |
| TIMEOUT | 1890 | 55.08% | 100.00% | 71.03% | 100.00% |

## 2. Trigger Timing

| trigger | n | avg_bars | median_bars | early_ratio |
|---|---:|---:|---:|---:|
| STRUCTURE_FAIL | 1586 | 6.77 | 5.00 | 52.96% |
| MONEY_FLOW_DROP | 1862 | 4.29 | 3.00 | 71.97% |
| ENERGY_DROP | 1890 | 2.72 | 2.00 | 88.89% |
| STOP_LOSS_3 | 845 | 7.24 | 6.00 | 45.33% |
| NEW_LL | 126 | 7.02 | 5.00 | 53.97% |
| K_TURN_DOWN | 1796 | 5.98 | 5.00 | 52.78% |
| K_CROSS_DOWN | 1647 | 8.72 | 8.00 | 26.90% |
| RE_OVERSOLD | 258 | 14.47 | 15.00 | 1.55% |
| TIMEOUT | 1890 | 20.00 | 20.00 | 0.00% |

## 3. FAILED_20 First Trigger 분포

- **ENERGY_DROP**: 288
- **STRUCTURE_FAIL**: 268
- **K_TURN_DOWN**: 182
- **MONEY_FLOW_DROP**: 154
- **STOP_LOSS_3**: 110
- **K_CROSS_DOWN**: 28
- **NEW_LL**: 11

## 4. Trigger별 Failure Rate (triggered events)

| trigger | n | failure_rate | survival_rate | avg_return_20 |
|---|---:|---:|---:|---:|
| STRUCTURE_FAIL | 1586 | 60.09% | 17.91% | -0.87% |
| MONEY_FLOW_DROP | 1862 | 55.91% | 24.38% | 0.11% |
| ENERGY_DROP | 1890 | 55.08% | 25.50% | 0.27% |
| STOP_LOSS_3 | 845 | 78.22% | 14.91% | -2.36% |
| NEW_LL | 126 | 46.83% | 32.54% | 1.17% |
| K_TURN_DOWN | 1796 | 54.57% | 26.22% | 0.29% |
| K_CROSS_DOWN | 1647 | 55.86% | 25.20% | 0.21% |
| RE_OVERSOLD | 258 | 98.06% | 0.78% | -5.25% |
| TIMEOUT | 1890 | 55.08% | 25.50% | 0.27% |

## 5. Rule별 Trigger

- RULE_A: n=548, fail=56.57%, top=ENERGY_DROP, false_exit=100.00%
- RULE_B: n=410, fail=53.41%, top=ENERGY_DROP, false_exit=100.00%
- RULE_C: n=932, fail=54.94%, top=ENERGY_DROP, false_exit=100.00%

## 6. Symbol별 Trigger

- BNBUSDT: n=571, top=ENERGY_DROP, false_exit=100.00%
- BTCUSDT: n=438, top=MONEY_FLOW_DROP, false_exit=100.00%
- ETHUSDT: n=440, top=ENERGY_DROP, false_exit=100.00%
- SOLUSDT: n=441, top=ENERGY_DROP, false_exit=100.00%

## 7. Regime별 Trigger

- BEAR: n=252, top=STRUCTURE_FAIL, false_exit=100.00%
- BULL: n=1275, top=ENERGY_DROP, false_exit=100.00%
- SIDEWAYS: n=363, top=ENERGY_DROP, false_exit=100.00%

## 8. Trigger Combination (OR)

| combo | n | f1 | precision | recall | false_exit |
|---|---:|---:|---:|---:|---:|
| STRUCTURE_FAIL OR MONEY_FLOW_DROP | 1862 | 71.72% | 55.91% | 100.00% | 94.19% |
| STRUCTURE_FAIL OR STOP_LOSS_3 | 1684 | 73.54% | 59.50% | 96.25% | 68.05% |
| MONEY_FLOW_DROP OR ENERGY_DROP | 1890 | 71.03% | 55.08% | 100.00% | 100.00% |
| STRUCTURE_FAIL OR MONEY_FLOW_DROP OR STOP_LOSS_3 | 1862 | 71.72% | 55.91% | 100.00% | 94.19% |

## 9. Best Trigger Top 10

| rank | trigger | score | f1 | false_exit | early_ratio |
|---:|---|---:|---:|---:|---:|
| 1 | STOP_LOSS_3 | 54.73 | 70.10% | 26.14% | 45.33% |
| 2 | STRUCTURE_FAIL | 53.16 | 72.55% | 58.92% | 52.96% |
| 3 | MONEY_FLOW_DROP | 49.34 | 71.72% | 94.19% | 71.97% |
| 4 | ENERGY_DROP | 48.87 | 71.03% | 100.00% | 88.89% |
| 5 | K_TURN_DOWN | 45.36 | 69.09% | 97.72% | 52.78% |
| 6 | K_CROSS_DOWN | 44.66 | 68.45% | 86.10% | 26.90% |
| 7 | TIMEOUT | 44.43 | 71.03% | 100.00% | 0.00% |
| 8 | RE_OVERSOLD | 40.07 | 38.95% | 0.41% | 1.55% |
| 9 | NEW_LL | 15.97 | 10.11% | 8.51% | 53.97% |

## 10. Active Candidate Risk Overlay

| rank | symbol | tf | rule | risk | trigger | status |
|---:|---|---|---|---:|---|---|
| 1 | BNBUSDT | 1d | RULE_C | 100 | STOP_LOSS_3 | TRIGGERED:STOP_LOSS_3 |
| 2 | SOLUSDT | 1d | RULE_C | 100 | STOP_LOSS_3 | TRIGGERED:STOP_LOSS_3 |
| 3 | SOLUSDT | 1h | RULE_B | 80 | STRUCTURE_FAIL | TRIGGERED:STRUCTURE_FAIL |
| 4 | ETHUSDT | 4h | RULE_C | 80 | STRUCTURE_FAIL | TRIGGERED:STRUCTURE_FAIL |
| 5 | SOLUSDT | 4h | RULE_C | 80 | STRUCTURE_FAIL | TRIGGERED:STRUCTURE_FAIL |
| 6 | BTCUSDT | 1d | RULE_C | 80 | STRUCTURE_FAIL | TRIGGERED:STRUCTURE_FAIL |
| 7 | SOLUSDT | 1h | RULE_A | 80 | STRUCTURE_FAIL | TRIGGERED:STRUCTURE_FAIL |
| 8 | BNBUSDT | 1h | RULE_B | 70 | MONEY_FLOW_DROP | TRIGGERED:MONEY_FLOW_DROP |
| 9 | ETHUSDT | 1h | RULE_C | 70 | MONEY_FLOW_DROP | TRIGGERED:MONEY_FLOW_DROP |
| 10 | ETHUSDT | 1h | RULE_A | 70 | MONEY_FLOW_DROP | TRIGGERED:MONEY_FLOW_DROP |
| 11 | ETHUSDT | 1h | RULE_B | 70 | MONEY_FLOW_DROP | TRIGGERED:MONEY_FLOW_DROP |
| 12 | BTCUSDT | 1h | RULE_B | 50 | ENERGY_DROP | TRIGGERED:ENERGY_DROP |
| 13 | BTCUSDT | 1h | RULE_A | 50 | ENERGY_DROP | TRIGGERED:ENERGY_DROP |
| 14 | SOLUSDT | 1h | RULE_C | 50 | ENERGY_DROP | TRIGGERED:ENERGY_DROP |
| 15 | BNBUSDT | 4h | RULE_C | 50 | ENERGY_DROP | TRIGGERED:ENERGY_DROP |

## 11. 현재 추적 우선순위 (Trigger Risk)

- #1 BNBUSDT 1d RULE_C risk=100 trigger=STOP_LOSS_3
- #2 SOLUSDT 1d RULE_C risk=100 trigger=STOP_LOSS_3
- #3 SOLUSDT 1h RULE_B risk=80 trigger=STRUCTURE_FAIL
- #4 ETHUSDT 4h RULE_C risk=80 trigger=STRUCTURE_FAIL
- #5 SOLUSDT 4h RULE_C risk=80 trigger=STRUCTURE_FAIL
- #6 BTCUSDT 1d RULE_C risk=80 trigger=STRUCTURE_FAIL
- #7 SOLUSDT 1h RULE_A risk=80 trigger=STRUCTURE_FAIL
- #8 BNBUSDT 1h RULE_B risk=70 trigger=MONEY_FLOW_DROP
- #9 ETHUSDT 1h RULE_C risk=70 trigger=MONEY_FLOW_DROP
- #10 ETHUSDT 1h RULE_A risk=70 trigger=MONEY_FLOW_DROP

## 12. 핵심 결론

**FAILED_20 최다 first trigger: ENERGY_DROP** — Best trigger: STOP_LOSS_3 (score 54.73, f1 70.10%, false_exit 26.14%).
- 최고 F1 단일 trigger: STRUCTURE_FAIL (72.55%)

- PNG: `wave_failure_trigger_validation.png`
