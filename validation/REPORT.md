# 실데이터 검증 리포트 — §6 역학관계 공식 엔진

- 생성 시각: 2026-06-06 16:53:26
- 데이터 소스: 앱과 동일한 엔진 함수(`analyze_wave_energy`, `trace_transitions`, `structure_distribution`, `get_ma_alignment`)와 동일 파이프라인(Binance 실데이터)
- 검증 매트릭스: BTCUSDT, ETHUSDT × 1d, 4h, 1h (6조합)
- 윈도: transition_recent_bars = 24봉
- 본 리포트는 관측 전용이다. 파라미터/규칙 변경 제안은 포함하지 않는다 (해석은 검토자의 몫).

## BTCUSDT 1d

- 봉 수: 500
- 레짐: `DOWN` / 캔들존: `BELOW_MA20`
- verdict: ✅ 매도 관점 유효 (추세·대파동·타이밍 정렬)
- MA 배열: Mixed / Consolidation (혼조세) ⚖️
- 스크린샷: [BTCUSDT_1d.png](./BTCUSDT_1d.png)

**추세 hit (①②):**
- `F6-2a` 소파동 HH 쌍봉 @ MA20 아래 → 하락 가능

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:소파동 쓰리봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:대파동 쌍봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:대파동 쓰리봉` | U3/None | - |
| F6-4c-b | `WINDOW_BLOCKED:MA10 쌍봉(HH)` | U3/None | - |
| F6-5a | `WINDOW_BLOCKED:중파동 쌍바닥` | D1/None | - |
| F6-5b | `WINDOW_BLOCKED:대파동 쌍바닥` | D2/None | - |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=8, KIND_MISMATCH=0, STRUCTURE_MISMATCH=0

**구조 분포** (총 500봉): U1=26(5.2%), U2=0(0.0%), U3=4(0.8%), D1=2(0.4%), D2=14(2.8%), D3=21(4.2%), None=433(86.6%)
- None 비율: **86.6%**

## BTCUSDT 4h

- 봉 수: 1000
- 레짐: `DOWN` / 캔들존: `BELOW_MA20`
- verdict: ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰
- MA 배열: Bearish Alignment (역배열) 📉
- 스크린샷: [BTCUSDT_4h.png](./BTCUSDT_4h.png)

**추세 hit (①②):** 없음

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:소파동 쓰리봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:중파동 쓰리봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:대파동 쓰리봉` | U3/None | - |
| F6-4c-b | `STRUCTURE_MISMATCH:D3` | U3/D3 | 2026-06-04 08:00 |
| F6-5a | `STRUCTURE_MISMATCH:D3` | D1/D3 | 2026-06-05 04:00 |
| F6-5b | `STRUCTURE_MISMATCH:D3` | D2/D3 | 2026-06-06 00:00 |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=5, KIND_MISMATCH=0, STRUCTURE_MISMATCH=3

**구조 분포** (총 1000봉): U1=19(1.9%), U2=27(2.7%), U3=44(4.4%), D1=30(3.0%), D2=29(2.9%), D3=63(6.3%), None=788(78.8%)
- None 비율: **78.8%**

## BTCUSDT 1h

- 봉 수: 1000
- 레짐: `DOWN` / 캔들존: `MA20_MA60_BAND`
- verdict: ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰
- MA 배열: Mixed / Consolidation (혼조세) ⚖️
- 스크린샷: [BTCUSDT_1h.png](./BTCUSDT_1h.png)

**추세 hit (①②):** 없음

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:소파동 쓰리봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:대파동 쌍봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:MA5 쌍봉` | U3/None | - |
| F6-4c-b | `WINDOW_BLOCKED:MA10 쌍봉(HH)` | U3/None | - |
| F6-5a | `WINDOW_BLOCKED:소파동 쓰리바닥` | D1/None | - |
| F6-5b | `STRUCTURE_MISMATCH:None` | D2/None | 2026-06-06 00:00 |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=7, KIND_MISMATCH=0, STRUCTURE_MISMATCH=1

**구조 분포** (총 1000봉): U1=33(3.3%), U2=0(0.0%), U3=10(1.0%), D1=21(2.1%), D2=2(0.2%), D3=112(11.2%), None=822(82.2%)
- None 비율: **82.2%**

## ETHUSDT 1d

- 봉 수: 500
- 레짐: `DOWN` / 캔들존: `BELOW_MA20`
- verdict: 🟡 매도 관점 — 소파동 타이밍 대기
- MA 배열: Mixed / Consolidation (혼조세) ⚖️
- 스크린샷: [ETHUSDT_1d.png](./ETHUSDT_1d.png)

**추세 hit (①②):** 없음

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:소파동 쓰리봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:중파동 쓰리봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:대파동 쓰리봉` | U3/None | - |
| F6-4c-b | `STRUCTURE_MISMATCH:None` | U3/None | 2026-06-04 00:00 |
| F6-5a | `WINDOW_BLOCKED:중파동 쌍바닥` | D1/None | - |
| F6-5b | `WINDOW_BLOCKED:대파동 쌍바닥` | D2/None | - |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=7, KIND_MISMATCH=0, STRUCTURE_MISMATCH=1

**구조 분포** (총 500봉): U1=11(2.2%), U2=0(0.0%), U3=0(0.0%), D1=12(2.4%), D2=10(2.0%), D3=20(4.0%), None=447(89.4%)
- None 비율: **89.4%**

## ETHUSDT 4h

- 봉 수: 1000
- 레짐: `DOWN` / 캔들존: `BELOW_MA20`
- verdict: 🟡 매도 관점 — 소파동 타이밍 대기
- MA 배열: Bearish Alignment (역배열) 📉
- 스크린샷: [ETHUSDT_4h.png](./ETHUSDT_4h.png)

**추세 hit (①②):** 없음

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:소파동 쓰리봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:중파동 쓰리봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:대파동 쓰리봉` | U3/None | - |
| F6-4c-b | `STRUCTURE_MISMATCH:D3` | U3/D3 | 2026-06-04 08:00 |
| F6-5a | `WINDOW_BLOCKED:중파동 쌍바닥` | D1/None | - |
| F6-5b | `WINDOW_BLOCKED:대파동 쌍바닥` | D2/None | - |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=7, KIND_MISMATCH=0, STRUCTURE_MISMATCH=1

**구조 분포** (총 1000봉): U1=8(0.8%), U2=10(1.0%), U3=27(2.7%), D1=37(3.7%), D2=21(2.1%), D3=90(9.0%), None=807(80.7%)
- None 비율: **80.7%**

## ETHUSDT 1h

- 봉 수: 1000
- 레짐: `DOWN` / 캔들존: `BELOW_MA20`
- verdict: ⚠️ 하락 추세 중 대파동 쌍바닥 — 추세 전환 가능성 관찰
- MA 배열: Bearish Alignment (역배열) 📉
- 스크린샷: [ETHUSDT_1h.png](./ETHUSDT_1h.png)

**추세 hit (①②):** 없음

**변곡점 hit (④⑤):** 없음

**8행 트레이스:**

| rule_id | result | 구조(req/actual) | 완성 봉 |
|---|---|---|---|
| F6-4a | `WINDOW_BLOCKED:중파동 쌍봉` | U1/None | - |
| F6-4b | `WINDOW_BLOCKED:대파동 쌍봉` | U2/None | - |
| F6-4c-a | `WINDOW_BLOCKED:대파동 쓰리봉` | U3/None | - |
| F6-4c-b | `WINDOW_BLOCKED:MA10 쌍봉(HH)` | U3/None | - |
| F6-5a | `WINDOW_BLOCKED:소파동 쓰리바닥` | D1/None | - |
| F6-5b | `WINDOW_BLOCKED:중파동 쓰리바닥` | D2/None | - |
| F6-5c-a | `WINDOW_BLOCKED:MA5 쌍바닥` | D3/None | - |
| F6-5c-b | `WINDOW_BLOCKED:MA10 쌍바닥(LL)` | D3/None | - |

- result 분포: HIT=0, ATOM_MISSING=0, WINDOW_BLOCKED=8, KIND_MISMATCH=0, STRUCTURE_MISMATCH=0

**구조 분포** (총 1000봉): U1=30(3.0%), U2=0(0.0%), U3=3(0.3%), D1=14(1.4%), D2=6(0.6%), D3=120(12.0%), None=827(82.7%)
- None 비율: **82.7%**

---

## 종합 (관측만)

### 1) 전 조합 합산 차단 게이트 빈도

| 게이트 | 건수 | 비율 |
|---|---|---|
| HIT | 0 | 0.0% |
| ATOM_MISSING | 0 | 0.0% |
| WINDOW_BLOCKED | 42 | 87.5% |
| KIND_MISMATCH | 0 | 0.0% |
| STRUCTURE_MISMATCH | 6 | 12.5% |
| (합계) | 48 | 100.0% |

### 2) WINDOW_BLOCKED 총 건수

- 원자는 데이터에 존재하나 transition_recent_bars(24봉) 윈도에 들어오지 못해 차단된 규칙: **42건** (8행 × 6조합 = 48행 중)

### 3) 검출된 kind 분포 (HL/LL/HH/LH)

| kind | 건수 | 비율 |
|---|---|---|
| HL | 579 | 27.7% |
| LL | 404 | 19.3% |
| HH | 527 | 25.2% |
| LH | 583 | 27.9% |
| EQ | 0 | 0.0% |
| (합계) | 2093 | 100.0% |

### 4) 구조 None 비율이 높은 조합

- ETHUSDT 1d: None **89.4%**
- BTCUSDT 1d: None **86.6%**
- ETHUSDT 1h: None **82.7%**
- BTCUSDT 1h: None **82.2%**
- ETHUSDT 4h: None **80.7%**
- BTCUSDT 4h: None **78.8%**

### 스크린샷 링크

- [BTCUSDT_1d.png](./BTCUSDT_1d.png)
- [BTCUSDT_4h.png](./BTCUSDT_4h.png)
- [BTCUSDT_1h.png](./BTCUSDT_1h.png)
- [ETHUSDT_1d.png](./ETHUSDT_1d.png)
- [ETHUSDT_4h.png](./ETHUSDT_4h.png)
- [ETHUSDT_1h.png](./ETHUSDT_1h.png)
