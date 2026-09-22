# 알림 시스템 apolo 통합 — push_alarms.py 를 notify 스캐너 기능으로 교체 (보고)

작성 2026-09-23. 브랜치 signal-alarm. 목표: apolo systemd 하나로 알림을 돌리고, 통합 검증 뒤 Actions notify 스캐너는 스케줄만 끈다(코드 유지).
이 PC에서 할 수 있는 것(이식·테스트·로컬 dry-run·빈도 추정)은 끝냈고, **apolo 에서 해야 하는 전환 절차(§5)는 아직 수행 전**이다.

## 0. 사전 확인 (수정 전)

**INTEGRITY_FILES(`analysis/wave_align_gate_forward.py`, 8개 항목)와 검출 정의 파일의 교집합**

| INTEGRITY 파일 | main vs signal-alarm blob | 비고 |
|---|---|---|
| analysis/wave_htf_gate_v2.py · wave_htf_gate.py · wave_align_gate_forward.py · wave_live_forward_journal.py | 동일 | — |
| indicators/moving_averages.py | 동일 | 정의 교체(ee2ba79)와 무관 |
| analysis/wave_live_watchlist.py · tests/test_align_gate_forward_integrity.py | 다름 | 이번 작업과 무관(기존 차이) |
| **config/settings.py** | 다름 | signal-alarm 쪽 변경(6c34fe9 BINANCE_FALLBACK 등). 이번 작업에서 **무접촉** — 대상 7셀은 스크립트 상수로 |

→ 스토캐 쌍봉/쌍바닥 정의 교체(ee2ba79)가 건드린 `indicators/stochastic.py`·`indicators/oscillators.py` 는 INTEGRITY 대상이 **아니다**.
main 정의를 맞추려면 그 두 파일만 옮기면 되고 INTEGRITY 파일에 걸리지 않는다(이번 범위 밖, 위임장대로 미수행).
단, 이번 통합 경로는 `config/settings.py` 의 `PUSH_WATCHLIST` 를 바꾸지 않고 `scripts/push_alarms.py` 의 `PUSH_TARGETS` 로 대상을 둔다(INTEGRITY 무접촉).

**2h·12h·2d 데이터 경로**: 2h·12h 는 바이낸스 kline 네이티브(`data/binance.fetch_klines` 그대로, 닫힘 판정 open_time+간격).
2d 는 `config/settings.CUSTOM_INTERVAL_BASE["2d"] = "1d"` 와 `data/processor.resample_timeframe` 의 기존 규칙(rule 2D, label/closed=right,
origin=**start**)이 있어 그것을 쓴다. 다만 origin=start 는 fetch 창의 첫 봉을 기준으로 묶기 때문에 **창이 하루 밀리면 2d 짝이 바뀐다**
(실측: 01-01 시작이면 (01-02,01-03)…, 01-02 시작이면 (01-03,01-04)…). 알림 키가 흔들리므로 첫 1d 봉을 epoch 일수 짝수에 정렬
(`align_base_frame`, 앞 봉 최대 1개 버림)하고, 1d 봉이 2개 안 찬 2d 봉(첫 홀·마지막 진행분)을 뺀다(`resample_closed`). 리샘플 규칙 자체는
config 함수를 그대로 호출한다(테스트가 결과 동일성 단언). 앱의 2d 차트는 창 기준이라 홀수 날에는 알림과 짝이 다를 수 있다 — 보고만.

## 1. 커밋 (분리)

| 구분 | 해시 | 내용 |
|---|---|---|
| 이식 | f46fafe | `notify/events.py` · `history.py` · `ledger.py` (main 0fa2be6 판 내용 무변경) + `notify/plan.py`(scanner.plan 이식) + `tests/test_notify_port.py` 12건 |
| 대상·종류 | 2af4f95 | `scripts/push_alarms.py` 통합판(7셀·종류·2d·이력·ledger·이관·예전 경로 옵션) + `tests/test_push_alarms.py` 17건 + `.gitignore` |
| 전환 문서 | (이 커밋) | 이 보고 + `docs/앱_사용법.md` 갱신 |

## 2. 대상·종류·주기

- 대상: `PUSH_TARGETS` = BTCUSDT × (1h, 2h, 4h, 6h, 12h, 1d, 2d). ledger 도 7셀 전부.
- 주기: `deploy/push_alarms.service` 무변경(`--loop 300 --offset 60`, 매시 :01·:06…).
- 종류(`notify.events.KINDS`): `stoch_db`(대파동 쌍바닥 후보, ★ 상승 다이버전스) · `ma60_turn`(60MA 전환, 다이버전스 줄) · `ma60_down`(하방 전환,
  하락 다이버전스 줄) · `structure_ll`(검출·기록만, 발송 꺼짐 — `notify/plan.SEND_DISABLED_KINDS`). 메시지는 `notify.events.format_message` 그대로.
- 예전 3층 확정·RSI·MACD 6종은 발송에서 제거. 코드는 `--legacy-signals` 옵션(기본 꺼짐, 이력 `pushbullet_state.legacy.json`)으로 남김.

## 3. 이식 내용

| 항목 | 구현 |
|---|---|
| 검출 소비 | `notify.events` → `display.ma60_turn_tracker`·`ma60_down_tracker`·`trend_structure`·`divergence_flag`(→ probe). signal-alarm 원본 직접 import, 체리픽·매니페스트 없음 |
| 데이터 | `data/binance.fetch_klines`(api.binance.com → 451/403 시 vision 자동 대체) → `build_dataframe` → 베이스 TF 닫힌 봉 → (2d) `resample_closed` → MA·스토캐 층 |
| 판정 | `notify.plan.plan`: old → dup → LL(record-only) → 새 종류(record-only) → 전역 최초 실행(최근 2봉) → send |
| 이력 | `notify.history` 형식을 `pushbullet_state.json` 에(키 심볼\|TF\|종류\|봉 UTC — 상승/하방은 종류가 다르다, 30일 회전·20일 스캔 창). 예전 형식(last_bar)은 `.legacy.json` 으로 이관 |
| ledger | `notify.ledger.finished_rows` + `finished_rows_down`(direction="down") → 이력 파일 "ledger"(서버 로컬, 브랜치 푸시 없음). `--export-ledger` CSV |
| 전송 | Pushbullet `push_note(token, title, body)` — 제목 "[WEH] " + 메시지 첫 줄, 본문 나머지. 실패 미기록 → 다음 순회 재시도 |

## 4. 로컬 dry-run (이 PC, 2026-09-23 01:03 KST, 빈 이력 = 첫 배포 실행 흉내)

```
cell BTCUSDT 1h:  closed bars=999 last=2026-09-22 15:00 UTC events=12 ledger_finished=8
cell BTCUSDT 2h:  closed bars=999 last=2026-09-22 14:00 UTC events=11 ledger_finished=8
cell BTCUSDT 4h:  closed bars=999 last=2026-09-22 12:00 UTC events=26 ledger_finished=12
cell BTCUSDT 6h:  closed bars=999 last=2026-09-22 06:00 UTC events=13 ledger_finished=9
cell BTCUSDT 12h: closed bars=999 last=2026-09-22 00:00 UTC events=14 ledger_finished=8
cell BTCUSDT 1d:  closed bars=499 last=2026-09-21 00:00 UTC events=8  ledger_finished=6
cell BTCUSDT 2d:  closed bars=498 last=2026-09-20 00:00 UTC events=5  ledger_finished=5
done {'events': 89, 'sent': 0, 'new_kind_record_only': 8, 'disabled_record_only': 18, 'old': 63, 'would_send': 0, ...}
by kind {'stoch_db': {'skip_old': 20, 'record_only_new_kind': 5}, 'ma60_turn': {'skip_old': 11, 'record_only_new_kind': 1},
         'ma60_down': {'skip_old': 19, 'record_only_new_kind': 2}, 'structure_ll': {'skip_old': 13, 'record_only_disabled_kind': 18}}
```
첫 실행 예상: 발송 0건, 창(20일) 안 26건 기록(후보 5·상승 1·하방 2·LL 18), kinds 4종 기록, ledger since 시작. 다음 실행부터 새 이벤트만 발송.

## 5. 전환 절차 (apolo — 미수행, 순서대로)

1. `git pull` (signal-alarm) 후 `python scripts/push_alarms.py --dry-run` — 7셀 × 종류별 건수(위 §4 형식)가 나오는지 확인. 예전 이력 파일이 있으면
   `pushbullet_state.legacy.json` 으로 옮겨졌다는 경고 1줄이 뜬다.
2. `python scripts/push_alarms.py --test` 로 Pushbullet 토큰 확인 → `sudo systemctl restart weh-push` (유닛 무변경, ExecStart 그대로).
3. **첫 24시간 Actions 와 병행**(중복 알림 감수). 대조: apolo `pushbullet_state.json` 의 sent 키(delivered=true) vs notify-state 브랜치 `notify/sent.json` 의
   BTCUSDT 1h/4h/1d 키(둘 다 `심볼|TF|종류|봉 UTC` 형식이라 그대로 비교 가능). 차이가 나면 정의 버전(main 원본 vs signal-alarm ee2ba79)에서
   후보 집합이 달라지는 것이 기대되는 원인이다(§6). 2h·6h·12h·2d 는 apolo 에만 있다.
4. 이상 없으면 `.github/workflows/notify_scan.yml` 의 `schedule:` 블록 주석 처리(코드는 유지) — 이 시점엔 스케줄 재등록 지연이 문제되지 않는다.

24시간 병행 대조표(작성 예정): 시각 · 셀 · 종류 · 봉 · apolo 발송 · Actions 발송 · 비고.

## 6. 예상 알림 빈도 — 최근 90일, 7셀, signal-alarm 정의(ee2ba79), 닫힌 봉, 키 = 종류|봉

| TF | 쌍바닥 후보 | 60MA 상방 | 60MA 하방 | (LL, 발송 안 함) | 발송 대상 |
|---|---|---|---|---|---|
| 1h | 10 | 1 | 5 | 5 | 16 |
| 2h | 6 | 3 | 3 | 0 | 12 |
| 4h | 3 | 2 | 3 | 11 | 8 |
| 6h | 1 | 1 | 2 | 5 | 4 |
| 12h | 1 | 1 | 0 | 7 | 2 |
| 1d | 1 | 0 | 0 | 3 | 1 |
| 2d | 1 | 1 | 1 | 0 | 3 |
| **합** | 23 (0.26/일) | 9 (0.10/일) | 14 (0.16/일) | 31 (0.34/일, 기록만) | **46 → 0.51건/일 (주 ≈3.6건)** |

Actions(3심볼×3TF, main 원본 정의) 대비 심볼은 줄고 TF 는 늘었다. 판정 아님 — 빈도 참고치.

## 7. 검수·테스트

- `tests/test_notify_port.py` 12건: import 소비·재구현 부재, 이벤트=추적기 행(상승/하방/후보/LL, known_pos), 메시지 4종 문구(main 그대로),
  plan 전역 2봉·종류별 첫 스캔 0건·발송 제외(되살림 경로)·중복·회전 창, history 회전/kinds/왕복, ledger 상승·하방 direction·키 충돌 없음·since·CSV.
- `tests/test_push_alarms.py` 17건: 토큰/푸시, 닫힌 봉(2h·12h 포함), **2d 정합**(1d 두 봉 = 2d 한 봉 OHLCV, 창 이동 불변, 미완 봉 제거, config 함수 결과와 동일),
  `load_closed_frame`(2d 는 1d fetch, 진행 봉 제외), 대상·종류·주기 고정·settings 무접촉·유닛 무변경, run 첫 배포 0건→기록→다음 실행 새 건만,
  전역 최초 실행 2봉, LL 기록만·dry-run 무기록·토큰 없음, 실패 미기록·재시도, ledger 양방향·CSV, 셀 격리, 예전 이력 이관, 예전 경로 계약.
- 인접 스위트(slim smoke·하방 추적) 33건 통과. 전체 스위트의 기존 실패(ee2ba79 임계·robustness·파리티 등)는 변동 없음.

## 8. 남은 것 / 결정 사항

- apolo 전환 절차(§5)와 24시간 병행 대조표는 이 PC에서 할 수 없어 미수행.
- 병행 기간의 정의 버전 차이(Actions = main 원본 스토캐 정의, apolo = ee2ba79 폭 기준)로 후보 집합이 다를 수 있음 — 스케줄을 끄면 자연 해소.
- 2d 짝 정렬(짝수 epoch 일수)은 알림 경로 전용이고 앱 차트(창 기준)와 홀수 날에 다를 수 있다 — config 규칙 변경은 이번 범위 밖.
- `docs/앱_사용법.md` 의 push_alarms 절 갱신.
