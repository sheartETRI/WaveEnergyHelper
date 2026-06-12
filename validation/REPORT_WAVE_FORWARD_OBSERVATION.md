# Wave Forward Observation Report

실시간 Forward 관측 운영 모드 (#27). 연구 종료 후 관측 전용.

**Maintenance Verdict: NOT_MAINTAINED**

## 1. Tier별 성과

| tier | filter | n | expectancy | survival | win_rate | research_exp | research_surv |
|---|---|---:|---:|---:|---:|---:|---:|
| TIER_1 | Filter_BNB_CORE | 229 | 2.92 | 40.37% | 61.93% | 3.02 | 41.31% |
| TIER_2 | quality>=4 | 654 | 0.20 | 23.79% | 47.09% | 0.91 | 27.60% |
| TIER_3 | RULE_C | 704 | 0.13 | 28.25% | 43.79% | 0.40 | 28.37% |

## 2. 현재 Candidate Queue

| rank | symbol | tf | rule | tier | filter | status |
|---:|---|---|---|---|---|---|
| 1 | BTCUSDT | 1h | RULE_B | TIER_2 | quality>=4 | +10_COMPLETE |
| 2 | BTCUSDT | 1h | RULE_A | TIER_2 | quality>=4 | +10_COMPLETE |
| 3 | ETHUSDT | 1h | RULE_C | TIER_2 | quality>=4 | +5_COMPLETE |
| 4 | SOLUSDT | 1h | RULE_C | TIER_3 | RULE_C | +10_COMPLETE |
| 5 | BNBUSDT | 4h | RULE_C | TIER_3 | RULE_C | PENDING |
| 6 | BNBUSDT | 1h | RULE_C | TIER_3 | RULE_C | PENDING |
| 7 | BTCUSDT | 1h | RULE_C | TIER_3 | RULE_C | PENDING |
| 8 | ETHUSDT | 4h | RULE_C | TIER_3 | RULE_C | PENDING |
| 9 | BNBUSDT | 1d | RULE_C | TIER_3 | RULE_C | +10_COMPLETE |
| 10 | SOLUSDT | 4h | RULE_C | TIER_3 | RULE_C | PENDING |
| 11 | SOLUSDT | 1d | RULE_C | TIER_3 | RULE_C | +20_COMPLETE |
| 12 | BTCUSDT | 4h | RULE_C | TIER_3 | RULE_C | PENDING |

## 3. Rolling 30/60/90일 성과

| window | tier | n | expectancy | survival |
|---:|---|---:|---:|---:|
| 30d | TIER_1 | 139 | 1.03 | 33.59% |
| 30d | TIER_2 | 387 | -0.20 | 16.24% |
| 30d | TIER_3 | 239 | -0.74 | 11.85% |
| 60d | TIER_1 | 175 | 0.80 | 32.32% |
| 60d | TIER_2 | 549 | -0.50 | 16.37% |
| 60d | TIER_3 | 374 | -0.48 | 19.94% |
| 90d | TIER_1 | 180 | 0.69 | 31.36% |
| 90d | TIER_2 | 630 | -0.17 | 21.72% |
| 90d | TIER_3 | 445 | -0.64 | 19.66% |

## 4. Drift 분석

| tier | metric | live | baseline | drift% | flag |
|---|---|---:|---:|---:|---|
| TIER_1 | expectancy | 0.69 | 3.02 | -77.20% | DRIFT_DOWN |
| TIER_1 | survival_rate | 31.36 | 41.31 | -24.09% | DRIFT_DOWN |
| TIER_1 | failure_rate | 36.24 | 58.69 | — | STABLE |
| TIER_2 | expectancy | -0.17 | 0.91 | -118.59% | DRIFT_DOWN |
| TIER_2 | survival_rate | 21.72 | 27.60 | -21.30% | DRIFT_DOWN |
| TIER_2 | failure_rate | 50.00 | 72.40 | — | STABLE |
| TIER_3 | expectancy | -0.64 | 0.40 | -259.05% | DRIFT_DOWN |
| TIER_3 | survival_rate | 19.66 | 28.37 | -30.70% | DRIFT_DOWN |
| TIER_3 | failure_rate | 53.98 | 71.63 | — | STABLE |

## 5. Observation Summary

- Total observation events: 1587
- TIER_1: n=229, exp=2.92
- TIER_2: n=654, exp=0.20
- TIER_3: n=704, exp=0.13

## 6. Alerts

- [BNB_CORE_SIGNAL] 36 events in last 7d (Filter_BNB_CORE)
- [QUALITY_SIGNAL] 216 events in last 7d (quality>=4)
- [RULE_C_SIGNAL] 92 events in last 7d (RULE_C)
- [ACTIVE_CANDIDATE] ACTIVE ETHUSDT 1h RULE_C (quality>=4)
- [ACTIVE_CANDIDATE] ACTIVE BNBUSDT 4h RULE_C (RULE_C)

## 7. 현재 관측 우선순위

- #1 BTCUSDT 1h RULE_B TIER_2 drift=DRIFT_DOWN
- #2 BTCUSDT 1h RULE_A TIER_2 drift=DRIFT_DOWN
- #3 ETHUSDT 1h RULE_C TIER_2 drift=DRIFT_DOWN
- #4 SOLUSDT 1h RULE_C TIER_3 drift=DRIFT_DOWN
- #5 BNBUSDT 4h RULE_C TIER_3 drift=DRIFT_DOWN
- #6 BNBUSDT 1h RULE_C TIER_3 drift=DRIFT_DOWN
- #7 BTCUSDT 1h RULE_C TIER_3 drift=DRIFT_DOWN
- #8 ETHUSDT 4h RULE_C TIER_3 drift=DRIFT_DOWN
- #9 BNBUSDT 1d RULE_C TIER_3 drift=DRIFT_DOWN
- #10 SOLUSDT 4h RULE_C TIER_3 drift=DRIFT_DOWN

## 8. 실시간 유지 여부

- **Verdict: NOT_MAINTAINED** (drift_down=3)
- 연구 baseline 대비 90일 rolling expectancy/survival drift로 판정

- PNG: `wave_forward_observation.png`
