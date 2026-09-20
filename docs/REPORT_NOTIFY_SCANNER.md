# 알림 스캐너 — GitHub Actions 구성 보고 (미검증 · 관측 알림)

작성 2026-09-20. 브랜치 `notify-scan`(origin/main 0be06d7 에서 분기, **main 에는 푸시하지 않음** — §8). 신설:
`notify/`(6 모듈), `.github/workflows/notify_scan.yml`, `tests/test_notify_scanner.py`(26건), 체리픽 3파일(`display/`).
정의 파일·전방 추적 파일·INTEGRITY_FILES·`data/binance.py` 무접촉(테스트가 `data/binance.py` 를 0be06d7 blob 과 대조).

> 알림은 **미검증**이다. 모든 메시지 첫 줄에 "(미검증)" 이 붙고 "매수/진입/매도" 어휘는 없다(테스트 단언).

## 1. 커밋 (분리, notify-scan)

| 구분 | 해시 |
|---|---|
| signal-alarm 표시 모듈 3종 체리픽(내용 무변경) `display/tz_label.py`·`ma60_turn_tracker.py`·`trend_structure.py` | cfc2e52 |
| 스캐너 모듈 `notify/` + `notify/requirements.txt` + `.gitignore`(notify/sent.json) | d3bd270 |
| 워크플로 `.github/workflows/notify_scan.yml` | 28eda1f |
| 테스트 24건 | c2412b7 |
| 최초 실행 모드 = '발송 성공 기록 없음' (§4) + 테스트 | efb4866 |
| [임시] push 트리거 추가 → 검수 실행 2회 → 제거 (§7) | 2dc431b → a5bc1bc |
| 같은 실행 안 동일 키 1건만 (§7 관찰) + 테스트 | 974dc18 |
| 보고(이 문서) | (이 문서 커밋) |

## 2. 검출 로직은 import 로만 소비

| 조건 | 소비 경로 | 이 패키지에 남는 것 |
|---|---|---|
| 60MA 전환 | `display.ma60_turn_tracker.track_candidates` 의 '전환 발생' 행 → `validation.wave_ma60_turn_probe.extract_signals`(main 26dfe9c 원본, 양 브랜치 같은 blob) | 행 → 이벤트 변환, 메시지 |
| 구조 훼손(LL) | `display.trend_structure.analyze` 의 chain 행 중 `cls == LL` → `analysis.wave_structure_confirmation` swing 검출기 | 직전 저점 조회(연쇄 안 앞 저점, 없으면 기준 저점), 메시지 |

- 체리픽 매니페스트 `notify/__init__.py CHERRYPICK`(sha256, LF 정규화, 원본 signal-alarm 9bb606c). 테스트가 파일 해시와
  `git show 9bb606c:<path>` blob 을 함께 대조하고, `notify/events.py` 본문에 피봇·스윙·MA 계산 흔적이 없음을 단언한다.
- 체리픽 모듈은 `charts.lw_builder` 를 함수 안에서만 lazy import 하므로 main 에 그 모듈이 없어도 import·스캔에 지장 없다
  (`tracker_reference_lines` 는 호출하지 않음). 앱(main.py) 배선은 하지 않았다 — 모듈 추가만.
- 지표 파이프라인은 앱·계측과 같은 `display.asof.run_indicator_pipeline(include_dispersion=False)`.

## 3. 데이터 소스 · 닫힌 봉

- `notify/fetch.py`: `https://data-api.binance.vision/api/v3/klines` 만 본다(스캐너 전용). `limit=1000`(MA240·스토캐 워밍업 충분).
- **닫힌 봉만**: kline `close_time < now` 인 봉만 남긴다. 두 검출 모듈은 프레임 마지막 봉을 현재로 보므로 진행 중 봉을
  넣지 않으면 진행 중 봉으로는 발화하지 않는다. 테스트: 전환봉이 진행 중이면 이벤트 없음 → 닫힌 뒤 1건, `bars_since_known == 0`.
- 이벤트의 확정봉(known): 전환 = 전환봉, LL = 스윙봉 + PIVOT(3, 스윙 확정 후행). 중복 키 = `SYMBOL|tf|kind|이벤트 봉 UTC`.

## 4. 이력 · 중복 차단 · 최초 실행 제한

- `sent.json`: `{"version":1,"sent":{key:{event_ts, sent_at, delivered}}}`. 발송 성공만 `delivered: true`.
  발송 실패 → 기록하지 않음(다음 실행 재시도, 테스트). 이벤트 봉 30일 지나면 회전.
- 스캔 창 20일(< 회전 30일): 회전으로 지운 키가 다시 발송되는 경로 없음(테스트가 상수 관계 고정).
- **최초 실행 제한**: 발송 성공 기록이 0건이면 최근 2봉 이내 확정분만 발송, 나머지는 `delivered:false` 기록만.
  위임의 '이력이 비어 있으면' 을 **'발송 성공 0건'** 으로 읽었다 — Secrets 없이 며칠 돌다 Secrets 를 넣는 순간 미발송분이
  한꺼번에 나가는 것을 막기 위해(efb4866). 판정을 좁히려면 `history.nothing_delivered` → `is_empty` 로 한 줄 교체.
- 같은 실행 안에서 같은 키가 두 번 나오면(두 쌍바닥 후보가 같은 봉에서 전환 — 검수 실행에서 실제 관찰) 1건만(974dc18).
- Secrets 부재: 발송 대상은 메시지를 로그에 남기고 **미기록**, rc 0. `--dry-run`: 발송·저장 모두 없음.

## 5. 메시지 (KST, 3줄 고정)

```
[BTCUSDT 4h] 60MA 전환 발생 (미검증)
쌍바닥 확정 09-18 17:00 → 전환 09-18 21:00 (소요 1봉)
가격 80,726 · 패턴 저점 74,968 / 기준선 74,593
```
```
[BTCUSDT 1d] 구조 훼손 — 저점 LL 발생 (미검증)
저점 09-15 09:00 74,968 < 직전 저점 76,047 (-1.42%) · 확정 09-18 09:00
기준 저점 62,535 (쌍바닥 확정 08-20 09:00) · 현재 구조: 훼손 (LL 발생)
```
첫 예는 위임장 예시와 같은 실제 건(BTCUSDT 4h 09-18)이며 테스트가 이 문자열을 고정한다. 가격은 1,000 이상 정수·미만 소수 2자리.

## 6. 워크플로 (`notify_scan.yml`)

- `schedule: */15 * * * *` + `workflow_dispatch(dry_run: boolean)`. `concurrency: notify-scan`(직렬, 취소 없음). `permissions: contents: write`.
- Secrets `TELEGRAM_TOKEN`·`TELEGRAM_CHAT_ID` 는 Scan 스텝 env 로만 전달. 텔레그램 모듈은 실패 사유 문자열에서 토큰을 마스킹.
- **발송 이력은 main 이 아니라 별도 브랜치 `notify-state`(`notify/sent.json`)에 커밋·푸시한다.** 이유: 전방 추적 클론의
  `publish_survival_signal` 은 pull 없이 `push HEAD:main` 하므로(scripts/daily_tracking.py) main 에 15분마다 커밋하면 추적 push
  가 non-fast-forward 로 매일 실패한다. 워크플로는 main 에 어떤 커밋도 만들지 않는다(테스트: `HEAD:main`·`--force` 부재, push 대상은 `$STATE_BRANCH`).
- 이력 브랜치 적재: `git ls-remote --exit-code` 로 존재 확인 → rc 0 fetch+worktree / rc 2 orphan 생성(최초) / 그 외 오류는
  **실패 처리**(네트워크 오류를 '최초 실행' 으로 오인해 중복 발송하는 경로 차단). 변경 없으면 커밋·푸시 생략.
- 의존성 `notify/requirements.txt`(requests, numpy==2.4.4, pandas==3.0.2, streamlit==1.58.0 — 루트 핀과 동일). 러너 실행 시간
  ≈ 50초(설치 포함, pip 캐시), 스캔 자체 ≈ 25~40초/9셀.

## 7. 검수 실행 2회 (Actions, 브랜치 notify-scan)

`gh` 계정(auto-code-etri)에 이 저장소 push 권한이 없어 `workflow_dispatch` API 호출이 403 이었다. 대신 **[임시] push 트리거**를
커밋해 2회 실행한 뒤 제거했다(2dc431b → a5bc1bc). 실제 모드(dry_run 아님), Secrets 미설정 상태.

| 실행 | 결과 | 핵심 로그 |
|---|---|---|
| [35501883638](https://github.com/sheartETRI/WaveEnergyHelper/actions/runs/35501883638) (2dc431b, 09:17 UTC) | 성공 | `history branch absent - initial run` → 9셀 모두 `closed bars=999`(1h·4h 는 진행 중 봉 제외 확인: last 08:00/04:00 UTC) → events 85 = old 53 · record_only 30 · **secrets absent — not sent 2**(BTC·ETH 1d LL 09-15, 확정 1봉 전) → `history saved {'total': 28}` → `pushed 036881d -> origin/notify-state` |
| [35502005990](https://github.com/sheartETRI/WaveEnergyHelper/actions/runs/35502005990) (974dc18, 09:20 UTC) | 성공 | `history branch loaded: 036881d` → events 85 = old 53 · **dup 30** · not sent 2 → `history unchanged`(커밋·푸시 없음) |

1회차 record_only 30 vs 이력 28 의 차이(2건)가 §4 의 '같은 키 두 번' 사례였고 974dc18 로 고쳤다(2회차에서 dup 30 으로 흡수).
`origin/notify-state` 현재 1커밋(036881d), 28키 모두 `delivered:false`.

## 8. 남은 결정 (김박사)

1. **main 병합**: 스케줄은 기본 브랜치의 워크플로만 돈다. `notify-scan` → main 병합(fast-forward 가능) 여부.
2. **Secrets 등록** `TELEGRAM_TOKEN`·`TELEGRAM_CHAT_ID`(Settings → Secrets and variables → Actions). 등록 전까지는 로그만 남는다.
   등록 후 첫 발송은 '최초 실행 제한'(최근 2봉)으로 시작한다.
3. **전방 추적 클론 복구(이 작업 범위 밖, 접촉하지 않음)**: `Desktop\WaveEnergyHelper-tracking` 은 origin/main 이 0be06d7(09-19 probe
   워크플로 푸시)로 앞서간 뒤 **09-20 17:36 push 가 non-fast-forward 로 실패**했다(`logs/daily_tracking.log`
   `git_publish=warning`, 로컬은 `main...origin/main [ahead 1]`). 클론에서 `git pull --rebase origin main` 1회가 필요하며,
   main 에 어떤 커밋(이 병합 포함)을 푸시하든 같은 조치가 다시 필요하다 — 추적 스크립트에 pull 을 넣는 것은 별도 위임.
4. 이력 브랜치 이름(`notify-state`)·회전 30일·스캔 창 20일·최초 2봉은 상수(`notify/history.py`, 워크플로 env).

## 9. 테스트

`tests/test_notify_scanner.py` 26건(픽스처는 계측 캐시 CSV, 네트워크 없음): 체리픽 해시·blob, import 소비·재구현 금지,
vision 엔드포인트·`data/binance.py` 무접촉, 이벤트 = 두 모듈 출력 동일, 닫힌 봉만 발화, 메시지 형식(위임 예시)·미검증·권고 어휘,
최초 실행 2봉·'발송 성공 0건' 모드, 동일 키 1건, 중복 차단(2회 실행), 발송 실패 미기록·재시도, Secrets 부재 rc 0, dry-run,
회전·스캔 창, 셀 실패 격리, 토큰 마스킹, 워크플로 계약, RSI/MACD/5m 부재.
전체 스위트(notify-scan 워크트리): **699 통과 / 1 스킵 / 2 실패** — 실패 2건은 기존 `test_wave_ruleset_robustness`
(numpy 2 / pandas 3 회귀, 무관). 스위트가 바꾼 `validation/wave_mm_shadow.csv`·`wave_final_synthesis.png` 는 checkout 으로 원복.
