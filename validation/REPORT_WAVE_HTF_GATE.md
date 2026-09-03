# REPORT_WAVE_HTF_GATE

SPEC_WAVE_HTF_GATE R1 — 상위 TF 파동 상태 게이트의 배열 게이트 대비 증분 검증.

## 1. 판정

**REJECT**

주 비교 대상: PAIR_B 통합. §2 캘리브레이션에서 PAIR_A 는 corr < 0.90 으로 폐기되어 주 비교에서 제외했다 (§2 규칙 그대로 적용, 대체 쌍 탐색 없음). §4.1 문면의 'PAIR_A + PAIR_B 통합' 값도 아래에 함께 보고한다.

| # | 기준 (§4.1) | 결과 | 값 |
|---|---|---|---|
| 1 | Δ > 0 & bootstrap 95% CI가 0 배제 | FAIL | Δ=None CI=[None, None] |
| 2 | 셀별 n >= 30 (G_BOTH 기준) | FAIL | PAIR_B=0 |
| 3 | 전/후 반분 양쪽에서 Δ > 0 | FAIL | first_half=None, second_half=None |
| 4 | {BTC, ETH, BNB} 중 2개 이상에서 Δ > 0 | FAIL | BTCUSDT=None, ETHUSDT=None, BNBUSDT=None |

### 참고: §4.1 문면 그대로 (PAIR_A + PAIR_B 통합, §2 폐기쌍 포함)

판정: **REJECT**

| # | 기준 (§4.1) | 결과 | 값 |
|---|---|---|---|
| 1 | Δ > 0 & bootstrap 95% CI가 0 배제 | FAIL | Δ=None CI=[None, None] |
| 2 | 셀별 n >= 30 (G_BOTH 기준) | FAIL | PAIR_A=0, PAIR_B=0 |
| 3 | 전/후 반분 양쪽에서 Δ > 0 | FAIL | first_half=None, second_half=None |
| 4 | {BTC, ETH, BNB} 중 2개 이상에서 Δ > 0 | FAIL | BTCUSDT=None, ETHUSDT=None, BNBUSDT=None |

주 비교: Δ = E[G_BOTH] − E[G_ALIGN] = **—** (bootstrap 0회, 95% CI [—, —], n_G_ALIGN=0, n_G_BOTH=0)

**REJECT 사유는 '증분 없음'이 아니라 '식별 불가'다.** 관측 창 안에서 베이스라인 게이트 G_ALIGN 이 걸린 이벤트가 0건이므로 E[G_ALIGN] · E[G_BOTH] 가 정의되지 않고, 기준 1·3·4 는 값 부재로 FAIL 처리됐다. 즉 이번 라운드는 H1 을 반증한 것이 아니라 **검정할 표본이 없었다**. 원인은 §6 진단표에 있다.

**결론(§4.1 사전등록 문구): TF 연계 게이트는 배열 게이트의 재포장 — 기록 후 종료.** 주 비교와 §4.1 문면 통합값이 모두 REJECT 이다. §5 정지점에 따라 라운드를 종료하고 관측 도구 포지셔닝을 유지한다. 다만 위 식별 불가 사유상 이 기록은 '재포장임이 입증됐다'가 아니라 '재포장이 아님을 보이지 못했다'로 읽어야 한다.

## 2. §2 F5-c 캘리브레이션 상관표

corr( HTF 소파동 %K(5,3,3) , HTF 봉 마감 시점으로 asof-align 한 LTF 대파동 %K(20,10,10) )

| pair | HTF→LTF | symbol | n | corr | 구간 |
|---|---|---|---|---|---|
| PAIR_A | 1d→4h | BTCUSDT | 263 | 0.8175 | 2025-12-15 ~ 2026-09-03 |
| PAIR_A | 1d→4h | ETHUSDT | 263 | 0.7950 | 2025-12-15 ~ 2026-09-03 |
| PAIR_A | 1d→4h | BNBUSDT | 263 | 0.7993 | 2025-12-15 ~ 2026-09-03 |
| PAIR_B | 4h→1h | BTCUSDT | 1243 | 0.9796 | 2026-02-08 ~ 2026-09-03 |
| PAIR_B | 4h→1h | ETHUSDT | 1243 | 0.9775 | 2026-02-08 ~ 2026-09-03 |
| PAIR_B | 4h→1h | BNBUSDT | 1243 | 0.9782 | 2026-02-08 ~ 2026-09-03 |

| pair | mean corr | min corr | 임계 | 판정 |
|---|---|---|---|---|
| PAIR_A | 0.8039 | 0.7950 | 0.90 | 쌍 폐기(보고만) |
| PAIR_B | 0.9784 | 0.9775 | 0.90 | 쌍 유지 |

## 3. 4열 비교표 (무게이트 / G_ALIGN / G_WAVE / G_BOTH)

트리거: RULE_C OR quality>=4 (기존 Filter_C ∪ Filter_Q 코호트, 신규 검출 없음)

### PAIR_A + PAIR_B 통합

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 894 | 846 | -0.0048 | 0.9959 | 22.34 | 47.04 | -0.0048 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 500 | 464 | -0.4252 | 0.5902 | 11.64 | 40.73 | -0.4252 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_A (HTF=1d, LTF=4h)

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 453 | 445 | -0.8004 | 0.5383 | 21.57 | 42.02 | -0.8004 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 174 | 171 | -1.4153 | 0.2277 | 9.36 | 25.15 | -1.4153 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_B (HTF=4h, LTF=1h)

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 441 | 401 | 0.8781 | 2.5260 | 23.19 | 52.62 | 0.8781 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 326 | 293 | 0.1527 | 1.2663 | 12.97 | 49.83 | 0.1527 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_A|BNBUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 182 | 179 | -1.2479 | 0.4355 | 21.79 | 46.37 | -1.2479 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 0 | 0 | — | — | — | — | — |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_A|BTCUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 133 | 129 | 0.3789 | 1.4691 | 25.58 | 52.71 | 0.3789 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 83 | 81 | -0.5822 | 0.4779 | 7.41 | 37.04 | -0.5822 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_A|ETHUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 138 | 137 | -1.3262 | 0.3310 | 17.52 | 26.28 | -1.3262 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 91 | 90 | -2.1652 | 0.1263 | 11.11 | 14.44 | -2.1652 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_B|BNBUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 180 | 167 | 1.8374 | 4.3588 | 33.53 | 63.47 | 1.8374 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 111 | 98 | -0.0183 | 0.9685 | 8.16 | 55.10 | -0.0183 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_B|BTCUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 142 | 122 | 0.1972 | 1.4277 | 13.11 | 52.46 | 0.1972 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 138 | 118 | 0.2436 | 1.5572 | 13.56 | 54.24 | 0.2436 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_B|ETHUSDT

| gate | n | n(return_20) | expectancy_20 | PF | survival% | win% | avg20 |
|---|---|---|---|---|---|---|---|
| NO_GATE | 119 | 112 | 0.1893 | 1.2550 | 18.75 | 36.61 | 0.1893 |
| G_ALIGN | 0 | 0 | — | — | — | — | — |
| G_WAVE | 77 | 77 | 0.2312 | 1.2999 | 18.18 | 36.36 | 0.2312 |
| G_BOTH | 0 | 0 | — | — | — | — | — |

### PAIR_X (HTF=1d, LTF=6h) — 참고, 판정 미사용

NOT EVALUABLE — 현재 파이프라인 산출물에 6h 이벤트가 없다 (forward journal timeframe = 1h/4h/1d, 6h = 0건). 신규 이벤트 검출 로직 작성은 §3.3에서 금지되어 있고 PAIR_X 는 판정에 미사용이므로, R1 에서는 미평가로 기록한다.

### BNB 단독 — Filter_BNB_CORE 중첩률 (§4.2)

G_BOTH 가 기존 BNB 필터의 대리변수인지 확인. Filter_BNB_CORE = BNBUSDT & mf>=5 & struct>=5.

| 범위 | n(BNB) | n(BNB_CORE) | n(G_BOTH) | 교집합 | Jaccard | P(CORE\|BOTH) | P(BOTH\|CORE) | E[BNB_CORE] | E[G_BOTH] |
|---|---|---|---|---|---|---|---|---|---|
| 주 비교 | 180 | 86 | 0 | 0 | 0.0000 | — | 0.0000 | 3.3055 | — |
| PAIR_A | 182 | 76 | 0 | 0 | 0.0000 | — | 0.0000 | -2.1017 | — |
| PAIR_B | 180 | 86 | 0 | 0 | 0.0000 | — | 0.0000 | 3.3055 | — |

## 4. half-split 표

| split | n | 구간 | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |
|---|---|---|---|---|---|---|---|
| first_half | 220 | 2026-05-22 ~ 2026-06-05 | 0 | 0 | — | — | — |
| second_half | 221 | 2026-06-05 ~ 2026-06-12 | 0 | 0 | — | — | — |

### 심볼별 Δ

| symbol | n | n(G_ALIGN) | n(G_BOTH) | E[G_ALIGN] | E[G_BOTH] | Δ |
|---|---|---|---|---|---|---|
| BTCUSDT | 142 | 0 | 0 | — | — | — |
| ETHUSDT | 119 | 0 | 0 | — | — | — |
| BNBUSDT | 180 | 0 | 0 | — | — | — |

### 셀별 G_BOTH 표본 수 (§4.1-2)

| cell | level | n(G_ALIGN) | n(G_BOTH) | n>=30 |
|---|---|---|---|---|
| PAIR_B | pair | 0 | 0 | FAIL |
| PAIR_B / BTCUSDT | pair_symbol | 0 | 0 | FAIL |
| PAIR_B / ETHUSDT | pair_symbol | 0 | 0 | FAIL |
| PAIR_B / BNBUSDT | pair_symbol | 0 | 0 | FAIL |

## 5. 한계

- **게이트 지연 1 HTF봉**: §3.4 asof 규칙상 이벤트 시각 t 에 대해 close_time < t 인 마감봉만 사용한다. 진행 중 HTF 봉의 상태는 반영되지 않으며, 게이트는 최대 1 HTF 봉만큼 지연된다 (설계 비용으로 수용).
- **이벤트 정의 상속**: 트리거는 기존 forward journal 이벤트(RULE_C ∪ quality>=4)를 그대로 상속한다. 신규 검출기·신규 이벤트 정의는 만들지 않았다.
- **표본 축소가 아니라 표본 부재**: G_ALIGN 코호트가 0건이라 CI 자체를 낼 수 없다. 관측 창을 넓히지 않는 한 이 비교는 표본 수 문제로 계속 식별 불가다.
- **관측 창 불일치**: LTF 이벤트는 기존 journal 의 관측 창(1h: 약 3주, 4h: 약 3개월)에 묶여 있다. TF쌍별 표본 기간이 다르므로 PAIR_A/PAIR_B 통합값은 기간 가중이 균등하지 않다.
- **§4.1-2 셀 정의**: 스펙의 '셀'을 TF쌍 단위로 읽었다. TF쌍×심볼 단위 표본 수도 위 표에 함께 보고한다.
- **베이스라인 게이트 공집합**: 본 라운드 관측 창에서 G_ALIGN 이 걸린 이벤트가 0건이라 주 비교가 식별되지 않았다. 이는 게이트의 효과 크기가 아니라 관측 창 커버리지 문제이며, §6 부록에 봉 단위 가용성을 실었다.
- **§4.3 부차 연구 미실행**: §5 가 정의한 R1 범위는 §2 캘리브레이션 + §4.1 주 비교다. §4.3(LTF 중파동 쌍봉 청산 vs POLICY_H)은 선택 실행 항목이므로 R1 에 포함하지 않았다.
- **§2 와 §4.1 의 문면 충돌**: §2 는 corr < 0.90 인 쌍을 폐기하라고 하고, §4.1 은 'PAIR_A + PAIR_B 통합'을 주 비교로 지정한다. 본 라운드에서 PAIR_A 가 폐기되었으므로 주 비교는 잔존 쌍만으로 계산하고, §4.1 문면 그대로의 통합값도 §1 에 함께 실었다. 기준·게이트·TF쌍 정의는 변경하지 않았다.


## 6. 부록 — 게이트 가용성 진단 (판정 미사용)

게이트가 애초에 열리는 구간이 있었는지, 그 구간이 LTF 이벤트 관측 창과 겹치는지 확인한다. HTF 봉 단위 카운트이며 이벤트 가중이 아니다.

| pair | HTF | symbol | HTF봉 | align | wave | both | 이벤트창 봉 | 창내 align | 창내 wave | 창내 both |
|---|---|---|---|---|---|---|---|---|---|---|
| PAIR_A | 1d | BTCUSDT | 260 | 0 | 129 | 0 | 82 | 0 | 45 | 0 |
| PAIR_A | 1d | ETHUSDT | 260 | 0 | 58 | 0 | 82 | 0 | 57 | 0 |
| PAIR_A | 1d | BNBUSDT | 260 | 0 | 63 | 0 | 82 | 0 | 1 | 0 |
| PAIR_B | 4h | BTCUSDT | 1360 | 117 | 670 | 68 | 124 | 0 | 103 | 0 |
| PAIR_B | 4h | ETHUSDT | 1360 | 130 | 695 | 92 | 124 | 0 | 85 | 0 |
| PAIR_B | 4h | BNBUSDT | 1360 | 112 | 631 | 27 | 124 | 4 | 73 | 0 |

이벤트 관측 창은 각 TF쌍의 LTF 이벤트 시각 범위다 (PAIR_A 4h 이벤트: 약 3개월, PAIR_B 1h 이벤트: 약 3주).

산출물: `wave_htf_gate_events.csv`, `wave_htf_gate.csv`, `wave_htf_gate_calibration.csv`, `wave_htf_gate.png`
