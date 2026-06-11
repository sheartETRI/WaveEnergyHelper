# 깔끔함(clean) 관측 리포트 — ETHUSDT 4h

- 생성 시각: 2026-06-07 07:59:22
- [F7-a] 관측 전용 (규칙·게이트·UI 연결 없음)
- clean 쌍바닥: kind=HL ∧ M1>M0 / clean 쌍봉: kind=LH ∧ T1<T0

## 1. 전역 선택도 (db/dt 확정 전체)

- 확정 패턴 수: 655
- clean: 141 (21.5%)
- not-clean: 506 (77.3%)
- indeterminate: 8 (1.2%)

| detector | clean | not-clean | indeterminate |
|---|---|---|---|
| ma10_db | 11 | 23 | 1 |
| ma10_dt | 16 | 29 | 0 |
| ma120_db | 2 | 7 | 0 |
| ma120_dt | 4 | 7 | 0 |
| ma20_db | 5 | 16 | 1 |
| ma20_dt | 15 | 19 | 0 |
| ma240_db | 1 | 2 | 1 |
| ma240_dt | 0 | 3 | 0 |
| ma5_db | 20 | 41 | 1 |
| ma5_dt | 29 | 50 | 0 |
| ma60_db | 6 | 10 | 0 |
| ma60_dt | 8 | 14 | 0 |
| stoch_Bot_db | 6 | 68 | 3 |
| stoch_Bot_dt | 7 | 70 | 0 |
| stoch_Mid_db | 2 | 51 | 1 |
| stoch_Mid_dt | 3 | 43 | 0 |
| stoch_Top_db | 2 | 32 | 0 |
| stoch_Top_dt | 4 | 21 | 0 |

## 2. 기존 hit 생존 — 엔진 HIT db/dt 원자

- db/dt 원자 행 수: 10

### Z2 F6-5c-b (2 hit × 2 db 원자)

- MA10 쌍바닥(LL) @ 2026-02-26 08:00: kind=LL, prev_opp(M0)=1989.3360, neckline(M1)=1974.8840, **clean=not-clean**
- 대파동 쌍바닥(HL) @ 2026-02-14 20:00: kind=HL, prev_opp(M0)=87.7023, neckline(M1)=82.7189, **clean=not-clean**
- MA10 쌍바닥(LL) @ 2026-02-26 12:00: kind=LL, prev_opp(M0)=2073.4730, neckline(M1)=1989.3360, **clean=not-clean**
- 대파동 쌍바닥(HL) @ 2026-02-14 20:00: kind=HL, prev_opp(M0)=87.7023, neckline(M1)=82.7189, **clean=not-clean**

| zone | rule_id | atom | confirm | kind | clean |
|---|---|---|---|---|---|
| Z1 | F6-4a | 중파동 쌍봉 | 2026-01-16 00:00 | HH | not-clean |
| Z1 | F6-4a | 중파동 쌍봉 | 2026-01-19 12:00 | LH | clean |
| Z1 | F6-5b | 대파동 쌍바닥 | 2026-02-02 12:00 | HL | not-clean |
| Z2 | F6-5c-b | MA10 쌍바닥(LL) | 2026-02-26 08:00 | LL | not-clean |
| Z2 | F6-5c-b | 대파동 쌍바닥(HL) | 2026-02-14 20:00 | HL | not-clean |
| Z2 | F6-5c-b | MA10 쌍바닥(LL) | 2026-02-26 12:00 | LL | not-clean |
| Z2 | F6-5c-b | 대파동 쌍바닥(HL) | 2026-02-14 20:00 | HL | not-clean |
| Z3 | F6-5a | 중파동 쌍바닥 | 2026-05-09 16:00 | LL | not-clean |
| Z3 | F6-5a | 중파동 쌍바닥 | 2026-05-13 08:00 | LL | not-clean |
| Z3 | F6-5a | 중파동 쌍바닥 | 2026-05-14 16:00 | HL | not-clean |

## 2b. 스윕 WOULD_HIT db/dt 원자

- db/dt 원자 행 수: 26
- clean: 2 (7.7%)
- not-clean: 24 (92.3%)
- indeterminate: 0 (0.0%)

## 3. kind와의 관계

- kind 일치(HL/LH) 확정 수: 376
- kind 일치이나 not-clean: 231 (61.4% of kind-match)
