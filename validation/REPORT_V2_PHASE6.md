# REPORT_V2_PHASE6 — temporal 사전 점검(A) + 기법0 관측 계기(C)

선행: REPORT_V2_PHASE5(H2 통과: concordance_p1=in_progress, n=86). **엔진·검출기·게이트 무수정,
저널 컬럼 추가만.** 사전 등록 필터(동결): `concordance_p1 == in_progress`.

## A. temporal split 사전 점검 (go/no-go, 단발 기술통계)

> **go/no-go 기준(사전 등록, 변경 금지)**: 후반 net mean ≥ +0.5% **AND** 후반 n ≥ 20.
> GO → B(forward) 진행. NO-GO → B·forward 미수행, C만 수행하고 결론에 '전반 편중' 기록.

in_progress군(n=86) 캠페인 시작시각 기준 전/후반 50:50 분할:

| 구간 | n | net mean | net median | 승률 |
|------|---|------|--------|------|
| in_progress 전반 | 43 | +4.79% | +2.00% | 58% |
| in_progress 후반 | 43 | -0.44% | -0.45% | 47% |

- **판정: NO-GO** — 후반 mean -0.44% (< +0.50%), 후반 n 43 (≥ 20)

부가 기록(판정 아님) — confirmed·none 동일 분할:

| 구간 | n | net mean | net median | 승률 |
|------|---|------|--------|------|
| confirmed 전반 | 14 | +9.72% | +0.91% | 57% |
| confirmed 후반 | 15 | -0.02% | -1.02% | 27% |
| none 전반 | 54 | +0.51% | +0.04% | 52% |
| none 후반 | 54 | -0.51% | -1.22% | 37% |

in_progress TF별 분포: 1h=35, 4h=29, 1d=22

## B. forward 검증 — **미수행 (A NO-GO)**

사전 등록 규정에 따라 A가 NO-GO이므로 B(forward)·B-1~B-4를 수행하지 않는다.

> **결론(A 경로)**: **필터 엣지가 전반 편중** — in_progress 필터의 우위(PHASE5 in-sample +2.18%)는
> 전반(mean +4.79%)에 몰려 있고 후반(mean -0.44%)은 게이트 미달이다.
> **기법 1 + 상응 필터 forward 포기, v3(추세 레이어) 설계로 전환.** 아래 C는 v3에도 필요한
> 관측 인프라이므로 그대로 수행해 데이터 축적을 시작한다.

## C. 기법0 추세 레이어 관측 계기 (관측·저널·표시 전용 — 게이트/필터 금지)

⚠ **원 동결 스펙(`기법0_추세레이어_동결스펙.md`)이 리포에 부재** → 위임 §C 열거에 따른 보수적
형식화로 구현. T0~T4 전이 의미·slope 임계는 스펙 확보 시 재조정(미결). 현재는 관측 컬럼일 뿐이다.

| §C | 항목 | 구현 | 비고 |
|---|---|---|---|
| 1 | 스토캐 4층 (40,20,20) + 4패턴 | `trend_layer.add_trend_stoch_layer` | ★엔진 STOCH_LAYERS 미변경(관측 suffix) |
| 2 | MA20 이평선 패턴 | 기존 CORE_MA_PERIODS/DEFAULT_MA_PERIODS에 포함(ma20_db/dt) | 신규 코드 불요(확인) |
| 3 | MACD선 피봇 + 쌍봉(LH) | `trend_layer.add_macd_line_patterns` | 시계열 검출 재사용 |
| 4 | slope 판정기 + 계단식 GC | `ma_slope`/`slope_sign`/`stepwise_gc_at` | `TREND_SLOPE_N`, MA60/120 |
| 5 | 추세 상태 기계 T0~T4 | `TREND_FLOW`(데이터 선언) + `trend_state_at` | 전이표=데이터, 관측 |
| 6 | 저널 `trend_state_at_entry`,`bottom_width` | campaign_score/campaign_backtest 배선 | S0 봉 기준 |

**엔진 무영향 검증**: 4층 suffix `(40,20,20)` ∈ ALL_SUFFIXES? **아니오(정상 — 상태 기계 불변)** (단위 테스트 `test_trend_layer.py::test_engine_invariant_4th_layer_not_in_engine`).

### 추세 상태 기계 T0~T4 (전이표 데이터 선언)

| 상태 | 라벨 | 배열 | 기울기 |
|---|---|---|---|
| T0 | 하락 | fast<slow | down |
| T1 | 바닥형성 | fast<slow | up/flat |
| T2 | 상승전환 | cross_up | any |
| T3 | 상승 | fast>slow | up/flat |
| T4 | 천장형성 | fast>slow | down |

### 관측 스냅샷 — S0 진입 시 추세 상태 분포 (complete 캠페인)

| 추세 상태 | 건수 |
|---|---|
| 하락 | 60 |
| 바닥형성 | 41 |
| 상승 | 87 |
| 천장형성 | 29 |
| 미정 | 6 |

- **bottom_width**(S0 MA10 패턴 바닥 폭, 봉): min 6 · median 35 · max 1511 (n=223)

### 관측 계기 검출 카운트 (이력 전체, TF별)

| TF | 스토캐4층 쌍바닥 | 스토캐4층 쌍봉 | MACD선 쌍봉 |
|---|---|---|---|
| 1h | 133 | 142 | 452 |
| 4h | 147 | 135 | 432 |
| 1d | 76 | 79 | 209 |

## 미결 · 제안 (스코프 밖 — 기록만)

- **기법0 동결 스펙 부재**: `기법0_추세레이어_동결스펙.md`가 리포에 없어 T0~T4 전이 의미·slope 임계·
  계단식 GC 정의를 위임 §C 열거로 보수적 구현했다. 스펙 확보 시 정의 재조정 필요(관측 컬럼이라 안전).
- **C는 관측 전용**: trend_state·bottom_width로 캠페인 필터링/승격 금지(위임 규정). v3 게이트 미정.
- **A NO-GO 확정**: in_progress 필터는 전반 편중 — forward 미개시. B-3 발생률/도달 예상은 미산출(B 스킵).
- 통과 태그(PHASE5 H2)의 in-sample 재채점·필터 백테스트는 하지 않음(약속 유지).
