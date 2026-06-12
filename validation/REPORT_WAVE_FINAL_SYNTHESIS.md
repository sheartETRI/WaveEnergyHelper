# Wave Final Synthesis — Research Conclusion (#1~#25)

## Executive Summary

- **Final Verdict: CONDITIONAL**
- Baseline (n=1890): avg_return_20 0.27%, expectancy 0.27, survival 25.50%, PF 1.14
- Champion Filter (BNB): expectancy 4.09 (delta +3.82), verdict CONDITIONAL
- Robust Alternative: Filter_BNB_CORE (ROBUST, score 86.98)
- 범용 필터: Filter_Q quality>=4 (expectancy 0.91, n=750)
- Exit: baseline 유지(POLICY_H) 또는 손실방어(POLICY_A/B)
- 파동에너지 이론은 baseline +0.27%로 약한 양(+) 신호를 보이나, 유의미한 개선은 BNB + 고품질 feature(mf>=5, struct>=5, quality>=4) + BULL 레짐 + RULE_C/B 조건에서만 확인. 범용 STRONG 판정 불가. Filter_BNB_CORE는 ROBUST(86.98)이나 BNB 전용.

## Research Timeline (#1~#25)

| # | 단계 | 핵심 발견 |
|---:|---|---|
| 1 | Wave Validation | Wave 경로·에너지 기본 검증 |
| 2 | Multi-Indicator Validation | Money Flow·Volume·Structure 지표 유효성 확인 |
| 3 | Structure Confirmation | 구조 확인 레이어 분리 |
| 4 | Regime Analysis | BULL/BEAR/SIDEWAYS 레짐 분류 |
| 5 | Outcome Analysis | +5/+10/+20/+40 forward return 체계 |
| 6 | Expectancy Analysis | 기대값·PF 프레임워크 |
| 7 | Survival Analysis | INITIAL 경로 생존율 |
| 8 | Exit Analysis | 청산 규칙 사후 검증 |
| 9 | Segmentation | 다차원 세그먼트 분해 |
| 10 | Quality Score | 품질 점수 체계 |
| 11 | Rule Discovery | RULE_A/B/C 후보 도출 |
| 12 | Rule Grading | Rule 등급화 |
| 13 | Ruleset Robustness | Rule 세트 견고성 |
| 14 | Cross Market Validation | 다시장 재현 검증 |
| 15 | Generalization | 일반화 한계 확인 |
| 16 | Live Watchlist | 500봉 실시간 스캔·ACTIVE 37 |
| 17 | Live Forward Journal | 2,091 events forward 추적 |
| 18 | Symbol Segmentation | BNB 우위, SOL/ETH 약세 |
| 19 | Regime Segmentation | Regime 기여 0.57% |
| 20 | Survival Segmentation | RULE_C surv 28.37%, residual 96% |
| 21 | Failure Trigger Validation | STOP_LOSS_3 균형, STRUCTURE F1 최고 |
| 22 | Exit Policy Simulation | Exit는 손실방어, 수익 개선 제한 |
| 23 | Entry Filter Refinement | BNB+고품질 feature 대폭 개선 |
| 24 | Robustness Validation | Champion CONDITIONAL, Filter_BNB_CORE ROBUST |
| 25 | Final Synthesis | 통합 결론 도출 |

## Hypothesis Validation

| 가설 | 판정 | 근거 |
|---|---|---|
| Wave 단독 가설 | **PARTIAL** | Baseline expectancy +0.27, PF 1.14 — 약한 양(+)이나 residual 96% |
| Triple Bottom 가설 | **PARTIAL** | structure>=5 expectancy 0.78 — 단독 TB 신호만으로는 불충분 |
| Money Flow 가설 | **PARTIAL** | mf>=5 expectancy 0.70; trigger로는 false exit 94% |
| Structure 가설 | **PARTIAL** | STRUCTURE_FAIL F1 72.55%; structure>=5 PF 1.40 |
| Rule 범용성 가설 | **REJECTED** | RULE_A exp 0.00 vs RULE_C 0.40; Rule contribution 0.03% |
| Symbol 가설 | **PARTIAL** | BNB exp 1.56 vs SOL -1.06; Symbol contribution 1.89% |
| Regime 가설 | **PARTIAL** | BULL 0.53 vs BEAR -1.26; Regime contribution 0.57% |
| Exit 개선 가설 | **REJECTED** | 어떤 Exit Policy도 baseline expectancy 0.27 초과 못함 |

## Contribution Analysis

| 요인 | SS Contribution |
|---|---:|
| Rule | 0.03% |
| Symbol | 1.89% |
| Regime | 0.57% |
| Survival Feature | 1.13% |
| Residual | 96.38% |

## Champion Rules

| Rule | expectancy | survival | verdict |
|---|---:|---:|---|
| RULE_A | 0.00 | 22.08% | WEAK |
| RULE_B | 0.34 | 22.93% | CONDITIONAL |
| RULE_C | 0.40 | 28.37% | PROMISING |

## Champion Filters

| Filter | n | expectancy | PF | survival | verdict |
|---|---:|---:|---:|---:|---|
| RULE_A+BNB+mf>=5+struct>=5 | 59 | 4.09 | 4.37 | 42.37% | CONDITIONAL |
| BNB+mf>=5+struct>=5 | 213 | 3.02 | — | 41.31% | ROBUST |
| quality>=4 | 750 | 0.91 | 1.70 | 27.60% | CONDITIONAL |

## Champion Exit Policies

| Policy | expectancy | false_exit | saved_failure |
|---|---:|---:|---:|
| POLICY_A (STOP_LOSS_3) | -0.01 | 26.14% | 40.44% |
| POLICY_B (STRUCTURE_FAIL) | 0.17 | 57.68% | 70.61% |
| POLICY_H (RE_OVERSOLD) | 0.28 | 0.41% | 9.22% |

## Failure Analysis

| Cause | F1 | false_exit | first_trigger_n |
|---|---:|---:|---:|
| STRUCTURE_FAIL | 72.55% | 58.92% | 268 |
| MONEY_FLOW_DROP | 71.72% | 94.19% | 154 |
| STOP_LOSS_3 | 70.10% | 26.14% | 110 |

## Final Observation Model

- **Entry**: Filter_Q (quality>=4) 범용 / Filter_BNB_CORE (BNB) / RULE_C 단독 소폭 개선
- **Survival**: SURVIVED_20 >+2% at +20 bars; structure+mf+energy feature
- **Failure**: STRUCTURE_FAIL(고 recall) + STOP_LOSS_3(저 false exit) 조합 관측
- **Exit**: POLICY_H 수익 보존 / POLICY_A 균형 / POLICY_B 손실 회피

## Final Champion Framework

- **Entry Filter**: quality_score >= 4 (범용) | BNB + mf>=5 + struct>=5 (BNB)
- **Symbol Filter**: BNBUSDT 우선; SOL·BEAR 회피
- **Regime Filter**: BULL (exp 0.53); BEAR 회피 (exp -1.26)
- **Survival Condition**: return_20 > +2%; RULE_C survival 28.37%
- **Failure Trigger**: STOP_LOSS_3 (F1 70.10%, false exit 26.14%)
- **Exit Policy**: POLICY_H (baseline 수익 보존) 또는 POLICY_A (균형)

## Limitations

- 표본: Champion n=59 (LOW tier), 1d TF n=8 (UNSTABLE)
- BNB 편중: Champion은 BNB 외 0건
- Regime 편중: Champion BEAR 0건, SIDEWAYS n=4
- Residual 96.38%: 설명 변수 대부분 미포착
- 과최적화: BNB+고품질 feature 조합에 성과 집중

## Future Work

- Out-of-Sample Validation (미래 데이터 홀드아웃)
- 실시간 Forward Journal 누적 관측
- 장기 Forward Tracking (+40/+80)
- Cross-symbol 확장 (BTC/ETH 조건부 필터)
- Regime 전환 시점 동적 필터

## Final Verdict

### **CONDITIONAL**

판정 기준:
- FAILED: baseline 음수, robust champion 없음
- WEAK: baseline ~0, 조건부 개선만 존재
- CONDITIONAL: 특정 Symbol/Feature/Regime에서만 유효
- PROMISING: robust filter + 다중 split 양(+) consistency
- STRONG: 범용 양(+) expectancy, 다심볼·다레짐 재현

파동에너지 이론은 baseline +0.27%로 약한 양(+) 신호를 보이나, 유의미한 개선은 BNB + 고품질 feature(mf>=5, struct>=5, quality>=4) + BULL 레짐 + RULE_C/B 조건에서만 확인. 범용 STRONG 판정 불가. Filter_BNB_CORE는 ROBUST(86.98)이나 BNB 전용.

- Input check: 24/24 reports, 6/6 CSVs present
